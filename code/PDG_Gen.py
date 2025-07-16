#!/usr/bin/env python3
import xml.etree.ElementTree as ET
import subprocess
import sys
import os
import argparse
import tempfile
import html
import re  # for style mapping

# --- Expression re-stringifier -----------------------------------------------
def expr_to_str(elem):
    """Recursively reconstruct a simple Verilog expression from the AST node."""
    if elem is None:
        return ""
    tag = elem.tag.lower()

    # leaf nodes
    if tag == "varref":
        return elem.get("name", "")
    if tag == "const":
        return elem.get("name", "")

    # binary comparison ops
    cmp_ops = {"lts": "<", "gt": ">", "eq": "==", "neq": "!=", "lte": "<=", "gte": ">="}
    if tag in cmp_ops:
        kids = list(elem)
        if len(kids) >= 2:
            left  = expr_to_str(kids[0])
            right = expr_to_str(kids[1])
            return f"{left} {cmp_ops[tag]} {right}"

    # logical AND/OR
    if tag in ("land", "lor"):
        op = "&&" if tag == "land" else "||"
        return op.join(expr_to_str(c) for c in elem)

    # ternary (rare)
    if tag == "cond":
        kids = list(elem)
        if len(kids) >= 3:
            return f"{expr_to_str(kids[0])} ? {expr_to_str(kids[1])} : {expr_to_str(kids[2])}"

    # fallback: concat children
    return "".join(expr_to_str(c) for c in elem)

# --- Visual-style map for Verilog constructs and data types ------------------
STYLE_MAP = [
    (r'^Module:',            dict(shape='folder',        style='filled', fillcolor='lightgray',    color='black')),
    (r'^initial',            dict(shape='octagon',       style='filled', fillcolor='lightgoldenrod', color='black')),
    (r'^always',             dict(shape='box',           style='filled', fillcolor='lightblue',      color='navy')),
    (r'^Function:',          dict(shape='component',     style='filled', fillcolor='palegreen',      color='forestgreen')),
    (r'^Task:',              dict(shape='parallelogram', style='filled', fillcolor='palegoldenrod',   color='saddlebrown')),
    (r'^if ',                dict(shape='diamond',       style='filled', fillcolor='lightcyan',      color='teal')),
    (r'^case',               dict(shape='hexagon',       style='filled', fillcolor='lightpink',      color='deeppink')),
    (r'^(for|while|repeat)', dict(shape='ellipse',       style='filled', fillcolor='khaki',          color='darkgoldenrod')),
    (r'LoopExit',            dict(shape='trapezium',     style='filled', fillcolor='gray90',         color='gray50')),
    (r'^EndIf',              dict(shape='circle',        style='filled', fillcolor='white',         color='black')),
    (r'^EndCase',            dict(shape='circle',        style='filled', fillcolor='white',         color='black')),
    (r'<=',                  dict(shape='box3d',         style='filled', fillcolor='lightcoral',     color='darkred')),
    (r'=',                   dict(shape='box3d',         style='filled', fillcolor='lightsalmon',    color='darkorange')),
    (r'^input ',             dict(shape='circle',        style='filled', fillcolor='greenyellow',    color='green')),
    (r'^output ',            dict(shape='doublecircle',  style='filled', fillcolor='khaki1',         color='orange')),
    (r'^inout ',             dict(shape='triangle',      style='filled', fillcolor='peachpuff',      color='orangered')),
    (r'^reg ',               dict(shape='oval',          style='filled', fillcolor='lavender',       color='rebeccapurple')),
    (r'^wire ',              dict(shape='egg',           style='filled', fillcolor='white',          color='gray')),
    (r'parameter',           dict(shape='note',          style='filled', fillcolor='honeydew',       color='darkolivegreen')),
]

# --- CFG & DFG storage ------------------------------------------------------
cfg_nodes       = []
cfg_edges       = []
clusters        = []
cluster_stack   = []
cfg_node_defs   = {}
cfg_node_uses   = {}
cfg_node_to_line_num = {}
node_to_cluster = {}
node_to_sourcetext  = {}
dfg_nodes       = []
dfg_edges       = []
dfg_node_map    = {}
verilog_code_lines = []

def add_cluster(name, color="lightgrey"):
    idx = len(clusters)
    clusters.append({"name": name, "color": color, "node_ids": []})
    return idx

def add_cfg_node(label, cluster=None, time=None):
    if time is not None:
        label = f"{label}@{time}"
    nid = len(cfg_nodes)
    cfg_nodes.append(label)
    if cluster is not None:
        clusters[cluster]["node_ids"].append(nid)
        node_to_cluster[nid] = cluster
    return nid

def add_cfg_edge(src, dst, label=""):
    cfg_edges.append((src, dst, label))

def add_dfg_edge(src, dst):
    if (src, dst) not in dfg_edges:
        dfg_edges.append((src, dst))

def get_dfg_node(var_name):
    if var_name in dfg_node_map:
        return dfg_node_map[var_name]
    nid = len(dfg_nodes)
    dfg_nodes.append(var_name)
    dfg_node_map[var_name] = nid
    return nid

def collect_var_names(expr_elem):
    names = set()
    if expr_elem is None:
        return []
    for v in expr_elem.findall('.//varref'):
        if v.get('name'):
            names.add(v.get('name'))
    tag = expr_elem.tag.lower()
    if tag in ('varref','var','signal') and expr_elem.get('name'):
        names.add(expr_elem.get('name'))
    return list(names)

def traverse_statement(elem):
    if elem is None:
        return None
    tag = elem.tag.lower()
    loc = elem.get('loc')
    line_num = None
    if loc:
        parts = loc.split(',')
        if len(parts) > 1:
            try:
                line_num = int(parts[1])
            except ValueError:
                pass

    def record(node_id):
        if node_id is not None and line_num is not None:
            cfg_node_to_line_num[node_id] = line_num
        return node_id

    # --- structural blocks ---------------------------------------------------
    if tag in ('initial','always','function','task'):
        if tag=='function':
            label, color = f"Function: {elem.get('name')}", 'palegreen'
        elif tag=='task':
            label, color = f"Task: {elem.get('name')}", 'palegoldenrod'
        else:
            sentree = elem.find('sentree')
            sens = []
            if sentree is not None:
                for item in sentree.findall('senitem'):
                    vr = item.find('.//varref')
                    if vr is not None and item.get('type'):
                        sens.append(f"{item.get('type')} {vr.get('name')}")
            label = f"{tag} @({', '.join(sens)})" if sens else tag
            color = 'lightblue' if tag=='always' else 'lightyellow'

        cid = add_cluster(label, color)
        cluster_stack.append(cid)

        entry = add_cfg_node(f"Enter {tag}", cluster=cid)
        if loc:
            try:
                _, s, _, e, _ = loc.split(',')
                start_i = int(s)-1
                end_i   = int(e)
                node_to_sourcetext[entry] = "".join(verilog_code_lines[start_i:end_i])
            except:
                pass

        last = entry
        # skip senitem, decl, param
        children = [c for c in elem if c.tag.lower() not in ('sentree','senitem','var','decl','param')]
        for c in children:
            n = traverse_statement(c)
            if n is None: continue
            add_cfg_edge(last, n)
            last = n

        cluster_stack.pop()
        return last

    # skip declarations
    if tag in ('var','decl','param','genvar'):
        return None

    # begin/end blocks
    if tag=='begin':
        last = None
        for c in elem:
            n = traverse_statement(c)
            if n is None: continue
            if last is not None:
                add_cfg_edge(last, n)
            last = n
        return last

    # --- if / ifstmt --------------------------------------------------------
    if tag in ('if','ifstmt'):
        cond = elem.find('cond')
        # fallback if no <cond>
        if cond is None:
            for c in elem:
                if c.tag.lower() in ('eq','neq','lts','lte','gte','gt','land','lor','varref','const'):
                    cond = c
                    break
        used = set(collect_var_names(cond))
        cond_str = expr_to_str(cond)
        lbl = f"if ({cond_str})\nUSE: {', '.join(used) if used else 'none'}"
        parent = cluster_stack[-1] if cluster_stack else None
        node_if = record(add_cfg_node(lbl, cluster=parent))
        cfg_node_uses[node_if] = used
        node_end = add_cfg_node('EndIf', cluster=parent)

        then_node = traverse_statement(elem.find('then'))
        if then_node is not None:
            add_cfg_edge(node_if, then_node, 'True')
            add_cfg_edge(then_node, node_end)
        else:
            add_cfg_edge(node_if, node_end, 'True')

        else_node = traverse_statement(elem.find('else'))
        if else_node is not None:
            add_cfg_edge(node_if, else_node, 'False')
            add_cfg_edge(else_node, node_end)
        else:
            add_cfg_edge(node_if, node_end, 'False')

        return node_end

    # --- case / casez / casex -----------------------------------------------
    if tag in ('case','casez','casex'):
        expr = elem.find('expr')
        # fallback if no <expr>
        if expr is None:
            for c in elem:
                if c.tag.lower() not in ('caseitem','item'):
                    expr = c
                    break
        used = set(collect_var_names(expr))
        expr_str = expr_to_str(expr)
        lbl = f"{tag}({expr_str})\nUSE: {', '.join(used) if used else 'none'}"
        parent = cluster_stack[-1] if cluster_stack else None
        node_case = record(add_cfg_node(lbl, cluster=parent))
        cfg_node_uses[node_case] = used
        node_end   = add_cfg_node('EndCase', cluster=parent)

        for itm in elem.findall('caseitem') + elem.findall('item'):
            vals = [c.get('name') for c in itm.findall('.//const') if c.get('name')]
            edge_lbl = ','.join(vals) if vals else 'default'
            stmt = next((c for c in itm if c.tag.lower() not in ('const','varref')), None)
            br = traverse_statement(stmt)
            if br is not None:
                add_cfg_edge(node_case, br, edge_lbl)
                add_cfg_edge(br, node_end)
            else:
                add_cfg_edge(node_case, node_end, edge_lbl)
        return node_end

    # --- loops --------------------------------------------------------------
    if tag in ('for','while','repeat'):
        cond = elem.find('cond')
        used = set(collect_var_names(cond))
        cond_str = expr_to_str(cond)
        lbl = f"{tag}({cond_str})\nUSE: {', '.join(used) if used else 'none'}"
        parent = cluster_stack[-1] if cluster_stack else None
        node_lp = record(add_cfg_node(lbl, cluster=parent))
        cfg_node_uses[node_lp] = used

        body = traverse_statement(elem.find('body') or elem)
        if body is not None:
            add_cfg_edge(node_lp, body, 'True')
            add_cfg_edge(body, node_lp)

        node_exit = add_cfg_node('LoopExit', cluster=parent)
        add_cfg_edge(node_lp, node_exit, 'False')
        return node_exit

    # --- assignments --------------------------------------------------------
    if tag in ('assign','blockingassign','nonblockingassign',
               'continuousassign','contassign','assigndly'):
        ch = list(elem)
        if len(ch) < 2:
            return None
        rhs, lhs = ch[0], ch[-1]
        lr = lhs.find('.//varref') or lhs
        name = lr.get('name','<unnamed>')
        srcs = set(collect_var_names(rhs))

        # DFG
        did = get_dfg_node(name)
        for v in srcs:
            add_dfg_edge(get_dfg_node(v), did)

        op = '<=' if 'nonblocking' in tag else '='
        lbl = f"{name} {op} ...\nDEF: {name}\nUSE: {', '.join(srcs) if srcs else 'none'}"
        nid = record(add_cfg_node(lbl, cluster=(cluster_stack[-1] if cluster_stack else None)))
        cfg_node_defs[nid] = name
        cfg_node_uses[nid] = srcs
        return nid

    # --- generic fallback: traverse children -------------------------------
    last = None
    for c in elem:
        nd = traverse_statement(c)
        if nd is None:
            continue
        if last is not None:
            add_cfg_edge(last, nd)
        last = nd
    return last

# --- DOT generation ---------------------------------------------------------
def generate_dot(graph_name, args):
    def get_node_attributes(nid):
        txt = cfg_nodes[nid].replace('"','\\"')
        attrs = {'label': f'"{txt}"'}
        # default
        attrs.update(shape='ellipse', style='filled', fillcolor='white', color='black')
        # apply STYLE_MAP
        for pat, style_kwargs in STYLE_MAP:
            if re.search(pat, txt):
                attrs.update(**style_kwargs)
                break
        # SVG tooltips
        if args.format=='svg':
            tips = []
            if nid in cfg_node_to_line_num:
                tips.append(f"Line: {cfg_node_to_line_num[nid]}")
            if nid in node_to_sourcetext:
                tips.append(html.escape(node_to_sourcetext[nid]))
            if tips:
                tips_text = "\\n".join(tips)
                attrs['tooltip'] = '"' + tips_text + '"'
        return ",".join(f"{k}={v}" for k,v in attrs.items())

    lines = [f"digraph {graph_name} {{", "  rankdir=LR; splines=ortho;"]
    if graph_name=='CFG':
        used = set()
        for i,cl in enumerate(clusters):
            lines.append(f"  subgraph cluster_{i} {{")
            lines.append(f"    label=\"{cl['name']}\"; style=filled; color=\"{cl['color']}\";")
            for nid in cl['node_ids']:
                used.add(nid)
                lines.append(f"    n{nid} [{get_node_attributes(nid)}];")
            lines.append("  }")
        for nid in range(len(cfg_nodes)):
            if nid in used: continue
            lines.append(f"  n{nid} [{get_node_attributes(nid)}];")

        lines.append("  # CFG Edges")
        for s,d,lbl in cfg_edges:
            attr = f' [xlabel="{lbl}"]' if lbl else ""
            lines.append(f"  n{s} -> n{d}{attr};")

        lines.append("  # DFG Edges")
        defs_by_var = {}
        for nid,var in cfg_node_defs.items():
            defs_by_var.setdefault(var,[]).append(nid)
        for uid,used_vars in cfg_node_uses.items():
            for v in used_vars:
                for did in defs_by_var.get(v,[]):
                    if args.no_inter_cluster_dfg:
                        cd = node_to_cluster.get(did)
                        cu = node_to_cluster.get(uid)
                        if cd is not None and cu is not None and cd!=cu:
                            continue
                    lines.append(f'  n{did} -> n{uid} [style=dashed,color=red,constraint=false,xlabel="{v}"];')
    else:
        for nid,txt in enumerate(dfg_nodes):
            esc = txt.replace('"','\\"')
            lines.append(f'  n{nid} [label="{esc}",shape=ellipse];')
        for s,d in dfg_edges:
            lines.append(f'  n{s} -> n{d};')

    lines.append("}")
    return "\n".join(lines)

# --- main driver ------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description="Generate linked CFG/DFG from Verilog via Verilator")
    p.add_argument('verilog_file', help="Verilog source file")
    p.add_argument('-t','--top', dest='top_module', help="Top-level module name")
    p.add_argument('-o','--output', dest='output_file',
                   help="Output name (e.g. mygraph.svg). Extension decides format.")
    p.add_argument('--format', choices=['svg','png','dot','pdf'],
                   help="Override output format. Use svg for tooltips.")
    p.add_argument('--layout-engine', choices=['dot','fdp','neato','circo','twopi'],
                   default='fdp', help="Graphviz layout engine")
    p.add_argument('--no-inter-cluster-dfg', action='store_true',
                   help="Hide DFG edges across procedural boundaries")
    args = p.parse_args()

    # default output
    if not args.output_file:
        base = os.path.splitext(os.path.basename(args.verilog_file))[0]
        args.output_file = base + "_cfg.svg"
        print(f"Warning: defaulting to {args.output_file}")
    fmt = args.format or os.path.splitext(args.output_file)[1][1:].lower()
    if not fmt:
        fmt = 'svg'
        args.output_file += '.svg'
    args.format = fmt

    # read source lines
    try:
        with open(args.verilog_file) as f:
            global verilog_code_lines
            verilog_code_lines = f.readlines()
    except FileNotFoundError:
        sys.exit(f"Error: cannot open {args.verilog_file}")

    # run Verilator → XML AST
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as tmp:
        ast_path = tmp.name
    cmd = ['verilator','--xml-only','--xml-output',ast_path,'-Wno-fatal']
    if args.top_module:
        cmd += ['--top-module',args.top_module]
    cmd.append(args.verilog_file)
    print("Invoking Verilator...")
    try:
        subprocess.run(cmd, check=True, text=True, capture_output=True)
    except FileNotFoundError:
        sys.exit("Error: 'verilator' not found in your PATH.")
    except subprocess.CalledProcessError as e:
        sys.exit(f"Verilator error:\n{e.stderr}")

    # parse and traverse
    tree = ET.parse(ast_path)
    os.remove(ast_path)
    nl = tree.find('netlist')
    if nl is not None:
        for mod in nl.findall('module'):
            for item in mod:
                traverse_statement(item)

    # generate DOT / image
    dot = generate_dot('CFG', args)
    if fmt=='dot':
        with open(args.output_file,'w') as f:
            f.write(dot)
        print(f"Wrote DOT → {args.output_file}")
    else:
        # write temp dot, then render
        with tempfile.NamedTemporaryFile(mode='w',suffix='.dot',delete=False) as td:
            td.write(dot)
            dot_path = td.name
        print(f"Rendering {fmt.upper()} via dot (engine={args.layout_engine})…")
        cmd2 = ['dot',f'-K{args.layout_engine}',f'-T{fmt}','-o',args.output_file,dot_path]
        try:
            res = subprocess.run(cmd2, check=True, text=True, capture_output=True)
            if res.stderr:
                print(f"dot warnings:\n{res.stderr}")
            print(f"Output → {args.output_file}")
        except FileNotFoundError:
            sys.exit("Error: 'dot' not found. Install Graphviz.")
        except subprocess.CalledProcessError as e:
            sys.exit(f"Graphviz error:\n{e.stderr}")
        finally:
            os.remove(dot_path)

if __name__=='__main__':
    main()
