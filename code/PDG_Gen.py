#!/usr/bin/env python3
import argparse, subprocess, sys, os
import xml.etree.ElementTree as ET

class Node:
    def __init__(self, id, label, shape="box"):
        self.id = id
        self.label = label
        self.shape = shape

class Edge:
    def __init__(self, src, dst, label=""):
        self.src, self.dst, self.label = src, dst, label

class Graph:
    def __init__(self, name, rankdir="TB"):
        self.name, self.rankdir = name, rankdir
        self.nodes = []      # list of Node
        self.edges = []      # list of Edge
        self.var_node_map = {}  # for DFG: var name -> node id

    def add_node(self, label, shape="box"):
        nid = len(self.nodes)
        self.nodes.append(Node(nid, label, shape))
        return nid

    def get_or_add_var_node(self, varname):
        if varname in self.var_node_map:
            return self.var_node_map[varname]
        nid = self.add_node(varname, shape="ellipse")
        self.var_node_map[varname] = nid
        return nid

    def add_edge(self, src, dst, label=""):
        if src is None or dst is None: return
        self.edges.append(Edge(src, dst, label))

    def to_dot(self):
        lines = [f"digraph {self.name} {{", f"    rankdir={self.rankdir};"]
        for n in self.nodes:
            lbl = n.label.replace('"','\\"')
            lines.append(f'    N{n.id} [label="{lbl}" shape={n.shape}];')
        for e in self.edges:
            lbl = f' [label="{e.label}"]' if e.label else ""
            lines.append(f"    N{e.src} -> N{e.dst}{lbl};")
        lines.append("}")
        return "\n".join(lines)

def collect_var_names(elem, out):
    """Recursively find <var>, <varref> or <signal> name attributes."""
    tag = elem.tag.lower()
    if tag in ("var","varref","signal"):
        nm = elem.attrib.get("name")
        if nm: out.add(nm)
    for c in elem:
        collect_var_names(c, out)

def traverse_statement(elem, cfg, dfg, loop_ctx=None):
    """Returns (entry_node, exit_node) for CFG, adds DFG edges on the fly."""
    if elem is None: 
        return (None, None)
    tag = elem.tag.lower()
    if loop_ctx is None: 
        loop_ctx = []

    # ---- IF ----
    if tag == "if":
        # build condition label
        cond = elem.find("cond")
        lbl = "if"
        if cond is not None:
            first = next(iter(cond), None)
            if first is not None and first.attrib.get("name"):
                lbl += f" ({first.attrib['name']})"
        nid = cfg.add_node(lbl, shape="diamond")
        # then
        t_ent = t_exit = None
        then = elem.find("then")
        if then is not None:
            stmts = list(then)
            if stmts:
                t_ent, t_exit = traverse_statement(stmts[0], cfg, dfg, loop_ctx)
                prev = t_exit
                for s in stmts[1:]:
                    _, nxt = traverse_statement(s, cfg, dfg, loop_ctx)
                    cfg.add_edge(prev, nxt)
                    prev = nxt
        # else
        e_ent = e_exit = None
        els = elem.find("else")
        if els is not None:
            stmts = list(els)
            if stmts:
                e_ent, e_exit = traverse_statement(stmts[0], cfg, dfg, loop_ctx)
                prev = e_exit
                for s in stmts[1:]:
                    _, nxt = traverse_statement(s, cfg, dfg, loop_ctx)
                    cfg.add_edge(prev, nxt)
                    prev = nxt
        # connect
        if t_ent: cfg.add_edge(nid, t_ent, "T")
        if e_ent: cfg.add_edge(nid, e_ent, "F")
        elif not e_ent: # no else => false goes to merge
            pass
        # merge
        mid = cfg.add_node("<if_end>", shape="circle")
        if t_exit: cfg.add_edge(t_exit, mid)
        if e_exit: cfg.add_edge(e_exit, mid)
        elif not t_exit:
            cfg.add_edge(nid, mid, "F")
        return (nid, mid)

    # ---- CASE ----
    if tag == "case":
        expr = elem.find("expr")
        lbl = "case"
        if expr is not None:
            first = next(iter(expr), None)
            if first is not None and first.attrib.get("name"):
                lbl += f" ({first.attrib['name']})"
        nid = cfg.add_node(lbl, shape="diamond")
        mid = cfg.add_node("<case_end>", shape="circle")
        for item in elem.findall("item"):
            val = item.attrib.get("value","default")
            stmts = list(item)
            if stmts:
                ent, ex = traverse_statement(stmts[0], cfg, dfg, loop_ctx)
                cfg.add_edge(nid, ent, val)
                cfg.add_edge(ex, mid)
            else:
                cfg.add_edge(nid, mid, val)
        return (nid, mid)

    # ---- LOOPS ----
    if tag in ("for","while","repeat"):
        hdr_lbl = tag
        cond = elem.find("cond")
        if cond is not None:
            first = next(iter(cond), None)
            if first is not None and first.attrib.get("name"):
                hdr_lbl += f" ({first.attrib['name']})"
        hdr = cfg.add_node(hdr_lbl, shape="diamond")
        exit_node = cfg.add_node(f"<loop_exit_{len(loop_ctx)}>", shape="circle")
        loop_ctx.append({"hdr":hdr,"exit":exit_node})
        # body
        b_ent = b_exit = None
        body = elem.find("body")
        if body is not None:
            stmts = list(body)
            if stmts:
                b_ent, b_exit = traverse_statement(stmts[0], cfg, dfg, loop_ctx)
                prev = b_exit
                for s in stmts[1:]:
                    _, nxt = traverse_statement(s, cfg, dfg, loop_ctx)
                    cfg.add_edge(prev, nxt)
                    prev = nxt
        # connect
        if b_ent:
            cfg.add_edge(hdr, b_ent, "T")
            cfg.add_edge(prev, hdr)
        cfg.add_edge(hdr, exit_node, "F")
        loop_ctx.pop()
        return (hdr, exit_node)

    # ---- BREAK / CONTINUE ----
    if tag == "break":
        n = cfg.add_node("break", shape="box")
        if loop_ctx:
            cfg.add_edge(n, loop_ctx[-1]["exit"])
        return (n,n)
    if tag == "continue":
        n = cfg.add_node("continue", shape="box")
        if loop_ctx:
            cfg.add_edge(n, loop_ctx[-1]["hdr"])
        return (n,n)

    # ---- ASSIGNMENTS (any tag containing 'assign') ----
    if "assign" in tag:
        children = list(elem)
        dst = None
        srcs = set()
        # if explicit <lhs>/<rhs> exist, you could parse them; but for PicoRV32:
        # the last child is the varref = destination; the rest form the RHS.
        if len(children) >= 1:
            # assume last child with name attr is LHS
            last = children[-1]
            nm = last.attrib.get("name")
            if nm:
                dst = nm
            # everything except last is RHS
            for c in children[:-1]:
                collect_var_names(c, srcs)
        if not dst:
            dst = "<??>"  # fallback

        # build DFG edges
        dst_id = dfg.get_or_add_var_node(dst)
        for s in srcs:
            src_id = dfg.get_or_add_var_node(s)
            dfg.add_edge(src_id, dst_id)

        # build a CFG node for the assignment
        lbl = f"{dst} = ..."
        nid = cfg.add_node(lbl)
        return (nid, nid)

    # ---- GENERIC BLOCK ----
    # recursively sequence children
    stmts = list(elem)
    ent = exc = None
    prev_exit = None
    for st in stmts:
        e, x = traverse_statement(st, cfg, dfg, loop_ctx)
        if e and prev_exit:
            cfg.add_edge(prev_exit, e)
        if ent is None:
            ent = e
        prev_exit = x
        exc = x
    return (ent, exc)


def parse_module(mod, cfg, dfg):
    # handle always/initial processes
    procs = list(mod.findall(".//always")) + list(mod.findall(".//initial"))
    for p in procs:
        start = cfg.add_node(f"Start_{p.tag}", shape="circle")
        prev = start
        for stmt in list(p):
            ent, ex = traverse_statement(stmt, cfg, dfg)
            if ent:
                cfg.add_edge(prev, ent)
                prev = ex
        end = cfg.add_node(f"End_{p.tag}", shape="doublecircle")
        cfg.add_edge(prev, end)

    # module-scope continuous assigns
    conts = [e for e in mod if "assign" in e.tag.lower()]
    if conts:
        start = cfg.add_node("Start_cont", shape="circle")
        prev = start
        for c in conts:
            ent, ex = traverse_statement(c, cfg, dfg)
            if ent:
                cfg.add_edge(prev, ent)
                prev = ex
        end = cfg.add_node("End_cont", shape="doublecircle")
        cfg.add_edge(prev, end)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("verilog", help="Input Verilog file (.v)")
    parser.add_argument("--xml", action="store_true", help="Use --xml-only")
    parser.add_argument("--top-module", help="Verilator --top-module <name>")
    parser.add_argument("--out", default="out", help="Output basename")
    parser.add_argument("--format", choices=["dot","graphml","json"], default="dot")
    args = parser.parse_args()

    if not os.path.isfile(args.verilog):
        sys.exit(f"Error: '{args.verilog}' not found")

    # 1) run Verilator to get AST XML
    ast_file = f"{args.out}.ast.xml"
    cmd = ["verilator", "--xml-only", "--xml-output", ast_file]
    if args.top_module:
        cmd += ["--top-module", args.top_module]
    cmd += [args.verilog, "-Wno-fatal"]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        sys.exit("Verilator failed:\n" + e.stderr.decode())

    # 2) parse AST
    tree = ET.parse(ast_file)
    root = tree.getroot()

    # 3) build graphs
    cfg = Graph("CFG", rankdir="TB")
    dfg = Graph("DFG", rankdir="LR")

    # iterate *all* module tags
    for mod in root.iter("module"):
        mname = mod.attrib.get("name","?")
        print(f"Parsing module '{mname}' …")
        parse_module(mod, cfg, dfg)

    # 4) write out DOT
    if args.format == "dot":
        with open(f"{args.out}_cfg.dot","w") as f:
            f.write(cfg.to_dot())
        with open(f"{args.out}_dfg.dot","w") as f:
            f.write(dfg.to_dot())
        print(f"Wrote {args.out}_cfg.dot and {args.out}_dfg.dot")
    else:
        print("Only DOT export is implemented.")

if __name__ == "__main__":
    main()
