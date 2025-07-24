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
        # Ensure parentheses for correct precedence if needed, though simple join is often fine for AST reconstruction
        return f"({op.join(expr_to_str(c) for c in elem)})"

    # arithmetic operations
    arith_ops = {
        "add": "+", "sub": "-", "mul": "*", "div": "/", "mod": "%",
        "shl": "<<", "shr": ">>", "ashr": ">>>" # Assuming ashr for sra
    }
    if tag in arith_ops:
        kids = list(elem)
        if len(kids) >= 2:
            left = expr_to_str(kids[0])
            right = expr_to_str(kids[1])
            return f"({left} {arith_ops[tag]} {right})"


    # unary operations (e.g., neg)
    if tag == "neg":
        kids = list(elem)
        if kids:
            return f"-({expr_to_str(kids[0])})"
    if tag == "not": # Bitwise NOT
        kids = list(elem)
        if kids:
            return f"~({expr_to_str(kids[0])})"
    if tag == "lnot": # Logical NOT
        kids = list(elem)
        if kids:
            return f"!({expr_to_str(kids[0])})"

    # ternary 
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
    (r'^always_comb',        dict(shape='box',           style='filled', fillcolor='lightcoral',     color='darkred')),
    (r'^always_ff',          dict(shape='box',           style='filled', fillcolor='darkseagreen1',  color='darkgreen')),
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
    (r'^OP:',                dict(shape='box',           style='filled', fillcolor='lightgreen',     color='darkgreen', fontcolor='black')), # Style for operation nodes
]

# --- SSA & Operation Nodes ----------------------------------------------
ssacounter = {}
latestversion = {}
operationmap = {
    'add': 'ADD', 'sub': 'SUB', 'and': 'AND', 'or': 'OR', 'xor': 'XOR',
    'mul': 'MUL', 'div': 'DIV', 'mod': 'MOD', 'sll': 'SLL', 'srl': 'SRL',
    'sra': 'SRA', 'lt': 'LT', 'lte': 'LTE', 'gt': 'GT', 'gte': 'GTE',
    'eq': 'EQ', 'neq': 'NEQ', 'land': 'LAND', 'lor': 'LOR',
    'neg': 'NEG', 'not': 'NOT', 'lnot': 'LNOT', # Add unary ops
    'concat': 'CONCAT', 'bitselect': 'BITSEL', 'partselect': 'PARTSEL' # Add common Verilog ops
}

def getssaname(var):
    """Generates a new SSA name for a variable and updates its latest version."""
    cnt = ssacounter.get(var, 0) + 1
    ssacounter[var] = cnt
    ssaname = f"{var}_{cnt}" # Using underscore for cleaner SSA names in Graphviz
    latestversion[var] = ssaname
    return ssaname

def getlatestversion(var):
    """Returns the current latest SSA version of a variable."""
    return latestversion.get(var, var) # If no SSA version, return original name

# --- CFG & DFG storage ------------------------------------------------------
cfg_nodes       = []
cfg_edges       = []
clusters        = []
cluster_stack   = []
cfg_node_defs   = {} # Maps CFG node ID to the SSA variable name it defines
cfg_node_uses   = {} # Maps CFG node ID to a set of SSA variable names it uses
cfg_node_to_line_num = {}
node_to_cluster = {}
node_to_sourcetext  = {}
dfg_nodes       = [] # Stores unique DFG node names (SSA variable names or operation IDs)
dfg_edges       = [] # Stores (source_dfg_node_id, dest_dfg_node_id)
dfg_node_map    = {} # Maps SSA variable/operation name to its DFG node ID
verilog_code_lines = []

def add_cluster(name, color="lightgrey"):
    """Adds a new cluster (subgraph) to the graph."""
    idx = len(clusters)
    clusters.append({"name": name, "color": color, "node_ids": []})
    return idx

def add_cfg_node(label, cluster=None, time=None):
    """Adds a new node to the CFG."""
    if time is not None:
        label = f"{label}@{time}"
    nid = len(cfg_nodes)
    cfg_nodes.append(label)
    if cluster is not None:
        clusters[cluster]["node_ids"].append(nid)
        node_to_cluster[nid] = cluster
    return nid

def add_cfg_edge(src, dst, label=""):
    """Adds an edge to the CFG."""
    cfg_edges.append((src, dst, label))

def add_dfg_edge(src_dfg_id, dst_dfg_id):
    """Adds an edge to the DFG. DFG node IDs are used here."""
    if (src_dfg_id, dst_dfg_id) not in dfg_edges:
        dfg_edges.append((src_dfg_id, dst_dfg_id))

def get_dfg_node_id_from_ssa_name(ssa_name):
    """Gets or creates a DFG node ID for a given SSA name (variable or operation)."""
    if ssa_name in dfg_node_map:
        return dfg_node_map[ssa_name]
    nid = len(dfg_nodes)
    dfg_nodes.append(ssa_name) # Store the SSA name itself
    dfg_node_map[ssa_name] = nid
    return nid

def collect_var_names(expr_elem):
    """Collects all variable names (non-SSA) from an expression AST."""
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

def process_expression_for_dfg(expr_elem, current_cluster_id=None):
    """
    Recursively processes an expression to create DFG nodes for operations
    and connect them to their operands (variables or other operation results).
    Returns a list of DFG node IDs that represent the output(s) of this expression.
    """
    if expr_elem is None:
        return []

    op_type = operationmap.get(expr_elem.tag.lower())
    if op_type:
        # This is an operation node
        op_label = f"OP: {op_type}\n{expr_to_str(expr_elem)}" # Add expression string to label
        
        # Create a CFG node for the operation (optional, but good for visualization)
        op_cfg_node_id = add_cfg_node(op_label, cluster=current_cluster_id)
        
        # Create a unique SSA name for the *result* of this operation
        op_result_ssa_name = f"op_result_{op_type}_{op_cfg_node_id}"
        op_dfg_node_id = get_dfg_node_id_from_ssa_name(op_result_ssa_name)

        # Recursively process children (operands)
        operands_dfg_node_ids = []
        for child in expr_elem:
            child_results_dfg_ids = process_expression_for_dfg(child, current_cluster_id)
            for child_dfg_id in child_results_dfg_ids:
                add_dfg_edge(child_dfg_id, op_dfg_node_id) # Data flow from operand to operation
            operands_dfg_node_ids.extend(child_results_dfg_ids)
        
        # Record this CFG node's definition (the operation's result) and uses (its operands)
        cfg_node_defs[op_cfg_node_id] = op_result_ssa_name
        # Convert DFG node IDs back to their SSA names for cfg_node_uses
        cfg_node_uses[op_cfg_node_id] = set(dfg_nodes[n] for n in operands_dfg_node_ids if n < len(dfg_nodes))
        
        return [op_dfg_node_id] # Return the DFG node ID representing the operation's result
    else:
        # Not an operation, could be a varref or const.
        # For constants, we don't usually add them to DFG unless explicitly requested.
        # For varrefs, get their latest SSA version.
        var_names = collect_var_names(expr_elem)
        dfg_node_ids = []
        for vname in var_names:
            dfg_node_ids.append(get_dfg_node_id_from_ssa_name(getlatestversion(vname)))
        return dfg_node_ids

def processassignment(tag, elem):
    """Processes an assignment statement for DFG and SSA."""
    ch = list(elem)
    if len(ch) < 2:
        return [] # Return empty list if invalid structure

    rhs_elem, lhs_elem = ch[0], ch[-1]
    lr = lhs_elem.find('.//varref') or lhs_elem
    lhs_var_name = lr.get('name','<unnamed>')

    # Get the new SSA name for the LHS variable (this is a definition)
    new_lhs_ssa_name = getssaname(lhs_var_name)
    new_lhs_dfg_node_id = get_dfg_node_id_from_ssa_name(new_lhs_ssa_name)

    # Process the RHS expression. This will create operation nodes and link their inputs.
    # The return value is a list of DFG node IDs that are the "outputs" of the RHS.
    rhs_outputs_dfg_ids = process_expression_for_dfg(rhs_elem, cluster_stack[-1] if cluster_stack else None)
    
    # Create DFG edges from the outputs of the RHS expression to the new LHS SSA variable
    for rhs_output_dfg_id in rhs_outputs_dfg_ids:
        add_dfg_edge(rhs_output_dfg_id, new_lhs_dfg_node_id)
    
    return [new_lhs_ssa_name] # Return the SSA name of the defined variable

def processcontrol(tag, elem):
    """Processes control flow conditions for DFG."""
    cond_elem = elem.find('cond')
    # fallback if no <cond>
    if cond_elem is None:
        for c in elem:
            # Look for common expression tags directly under the control element
            if c.tag.lower() in operationmap or c.tag.lower() in ('varref','const'):
                cond_elem = c
                break
    
    if cond_elem is not None:
        # Process the condition expression. This will create operation nodes and link their inputs.
        # The result of the condition is not assigned to a variable, but it uses other variables.
        process_expression_for_dfg(cond_elem, cluster_stack[-1] if cluster_stack else None)


def traverse_statement(elem):
    """Recursively traverses the Verilog AST to build CFG and DFG."""
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
        """Helper to record CFG node to source line number mapping."""
        if node_id is not None and line_num is not None:
            cfg_node_to_line_num[node_id] = line_num
        return node_id

    # --- structural blocks ---------------------------------------------------
    if tag in ('initial','always','function','task'):
        graphtype = None
        if tag=='function':
            label, color = f"Function: {elem.get('name')}", 'palegreen'
        elif tag=='task':
            label, color = f"Task: {elem.get('name')}", 'palegoldenrod'
        else: # initial or always
            sentree = elem.find('sentree')
            sens = []
            if sentree is not None:
                for item in sentree.findall('senitem'):
                    vr = item.find('.//varref')
                    if vr is not None and item.get('type'):
                        sens.append(f"{item.get('type')} {vr.get('name')}")
            
            # Determine process type and set label/color
            if tag == 'always':
                if any(x in sens for x in ('posedge','negedge')):
                    graphtype = 'alwaysff'
                    label = f"always_ff @({', '.join(sens)})"
                    color = 'darkseagreen1'
                else:
                    graphtype = 'alwayscomb'
                    label = f"always_comb @({', '.join(sens)})"
                    color = 'lightcoral'
            elif tag == 'initial':
                graphtype = 'initial'
                label = f"initial block"
                color = 'lightgoldenrod'
            else: # Fallback for unknown always/initial types
                label = f"{tag} @({', '.join(sens)})" if sens else tag
                color = 'lightblue' if tag=='always' else 'lightyellow'

        cid = add_cluster(label, color)
        cluster_stack.append(cid)

        entry = add_cfg_node(f"Enter {tag}", cluster=cid)
        if loc:
            try:
                # Extracting source text for the entire block
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
        processcontrol(tag, elem) # Process condition for DFG operations

        cond = elem.find('cond')
        if cond is None: # Fallback if no explicit <cond> tag
            for c in elem:
                if c.tag.lower() in operationmap or c.tag.lower() in ('varref','const'):
                    cond = c
                    break
        
        used = set(getlatestversion(v) for v in collect_var_names(cond)) # Use latest SSA version for uses
        cond_str = expr_to_str(cond)
        lbl = f"if ({cond_str})\nUSE: {', '.join(used) if used else 'none'}"
        parent = cluster_stack[-1] if cluster_stack else None
        node_if = record(add_cfg_node(lbl, cluster=parent))
        cfg_node_uses[node_if] = used # Record CFG node's uses
        node_end = add_cfg_node('EndIf', cluster=parent)

        then_node = traverse_statement(elem.find('then'))
        if then_node is not None:
            add_cfg_edge(node_if, then_node, 'True')
            add_cfg_edge(then_node, node_end)
        else:
            add_cfg_edge(node_if, node_end, 'True') # Direct edge if no 'then' block

        else_node = traverse_statement(elem.find('else'))
        if else_node is not None:
            add_cfg_edge(node_if, else_node, 'False')
            add_cfg_edge(else_node, node_end)
        else:
            add_cfg_edge(node_if, node_end, 'False') # Direct edge if no 'else' block

        return node_end

    # --- case / casez / casex -----------------------------------------------
    if tag in ('case','casez','casex'):
        processcontrol(tag, elem) # Process expression for DFG operations

        expr = elem.find('expr')
        if expr is None: # Fallback if no explicit <expr> tag
            for c in elem:
                if c.tag.lower() not in ('caseitem','item'):
                    expr = c
                    break
        
        used = set(getlatestversion(v) for v in collect_var_names(expr)) # Use latest SSA version for uses
        expr_str = expr_to_str(expr)
        lbl = f"{tag}({expr_str})\nUSE: {', '.join(used) if used else 'none'}"
        parent = cluster_stack[-1] if cluster_stack else None
        node_case = record(add_cfg_node(lbl, cluster=parent))
        cfg_node_uses[node_case] = used # Record CFG node's uses
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
                add_cfg_edge(node_case, node_end, edge_lbl) # Direct edge if no branch body
        return node_end

    # --- loops --------------------------------------------------------------
    if tag in ('for','while','repeat'):
        cond = elem.find('cond')
        # Process condition for DFG operations
        process_expression_for_dfg(cond, cluster_stack[-1] if cluster_stack else None)

        used = set(getlatestversion(v) for v in collect_var_names(cond)) # Use latest SSA version for uses
        cond_str = expr_to_str(cond)
        lbl = f"{tag}({cond_str})\nUSE: {', '.join(used) if used else 'none'}"
        parent = cluster_stack[-1] if cluster_stack else None
        node_lp = record(add_cfg_node(lbl, cluster=parent))
        cfg_node_uses[node_lp] = used # Record CFG node's uses

        body = traverse_statement(elem.find('body') or elem)
        if body is not None:
            add_cfg_edge(node_lp, body, 'True')
            add_cfg_edge(body, node_lp) # Loop back edge

        node_exit = add_cfg_node('LoopExit', cluster=parent)
        add_cfg_edge(node_lp, node_exit, 'False') # Exit edge
        return node_exit

    # --- assignments --------------------------------------------------------
    if tag in ('assign','blockingassign','nonblockingassign',
               'continuousassign','contassign','assigndly'):
        
        # This call handles SSA for LHS and DFG connections for RHS operations
        defined_ssa_names = processassignment(tag, elem) 

        ch = list(elem)
        rhs_elem, lhs_elem = ch[0], ch[-1]
        lr = lhs_elem.find('.//varref') or lhs_elem
        lhs_var_name = lr.get('name','<unnamed>')
        
        # Collect uses for the CFG node label (these are the inputs to the assignment)
        # Use getlatestversion for variables that are *read* on the RHS
        rhs_used_vars = set(getlatestversion(v) for v in collect_var_names(rhs_elem))

        op = '<=' if 'nonblocking' in tag else '='
        # Use the newly defined SSA name for the DEF part of the label
        lbl = f"{lhs_var_name} {op} {expr_to_str(rhs_elem)}\nDEF: {defined_ssa_names[0] if defined_ssa_names else 'none'}\nUSE: {', '.join(rhs_used_vars) if rhs_used_vars else 'none'}"
        
        nid = record(add_cfg_node(lbl, cluster=(cluster_stack[-1] if cluster_stack else None)))
        
        # Record the CFG node's definition and uses using SSA names
        if defined_ssa_names:
            cfg_node_defs[nid] = defined_ssa_names[0]
        cfg_node_uses[nid] = rhs_used_vars
        
        return nid
    
    # --- generic fallback: traverse children -------------------------------
    # This ensures that any unhandled statements are still traversed to find nested structures.
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
    """Generates the DOT graph description."""
    def get_node_attributes(nid):
        """Determines DOT attributes for a CFG node based on its label and type."""
        txt = cfg_nodes[nid].replace('"','\\"')
        attrs = {'label': f'"{txt}"'}
        # default attributes
        attrs.update(shape='ellipse', style='filled', fillcolor='white', color='black')
        # apply STYLE_MAP
        for pat, style_kwargs in STYLE_MAP:
            if re.search(pat, txt):
                attrs.update(**style_kwargs)
                break
        # SVG tooltips for source code and line number
        if args.format=='svg':
            tips = []
            if nid in cfg_node_to_line_num:
                tips.append(f"Line: {cfg_node_to_line_num[nid]}")
            if nid in node_to_sourcetext:
                # Escape HTML for tooltips
                tips.append(html.escape(node_to_sourcetext[nid]))
            if tips:
                tips_text = "\\n".join(tips)
                attrs['tooltip'] = '"' + tips_text + '"'
        return ",".join(f"{k}={v}" for k,v in attrs.items())

    lines = [f"digraph {graph_name} {{", "  rankdir=LR; splines=ortho;"]
    
    if graph_name=='CFG':
        # Add clusters (modules, always blocks, etc.)
        used_cfg_nodes = set()
        for i,cl in enumerate(clusters):
            lines.append(f"  subgraph cluster_{i} {{")
            lines.append(f"    label=\"{cl['name']}\"; style=filled; color=\"{cl['color']}\";")
            for nid in cl['node_ids']:
                used_cfg_nodes.add(nid)
                lines.append(f"    n{nid} [{get_node_attributes(nid)}];")
            lines.append("  }")
        
        # Add CFG nodes not part of any explicit cluster (e.g., top-level module)
        for nid in range(len(cfg_nodes)):
            if nid in used_cfg_nodes: continue
            lines.append(f"  n{nid} [{get_node_attributes(nid)}];")

        lines.append("  # CFG Edges")
        for s,d,lbl in cfg_edges:
            attr = f' [xlabel="{lbl}"]' if lbl else ""
            lines.append(f"  n{s} -> n{d}{attr};")

        lines.append("  # DFG Edges (overlayed on CFG)")
        # Map SSA variable names to the CFG nodes that define them
        defs_by_var_ssa = {}
        for nid,var_ssa_name in cfg_node_defs.items():
            defs_by_var_ssa.setdefault(var_ssa_name,[]).append(nid)
        
        # Create DFG edges from definitions to uses within the CFG
        for uid,used_vars_ssa_set in cfg_node_uses.items():
            for v_ssa_name in used_vars_ssa_set:
                for did in defs_by_var_ssa.get(v_ssa_name,[]):
                    # Optionally hide inter-cluster DFG edges
                    if args.no_inter_cluster_dfg:
                        cd = node_to_cluster.get(did)
                        cu = node_to_cluster.get(uid)
                        if cd is not None and cu is not None and cd!=cu:
                            continue
                    lines.append(f'  n{did} -> n{uid} [style=dashed,color=red,constraint=false,xlabel="{v_ssa_name}"];')
    else: # DFG graph (if generated separately, currently not used in main)
        for nid,txt in enumerate(dfg_nodes):
            esc = txt.replace('"','\\"')
            lines.append(f'  dfg_n{nid} [label="{esc}",shape=ellipse];') # Use a different prefix for DFG nodes if separate
        for s,d in dfg_edges:
            lines.append(f'  dfg_n{s} -> dfg_n{d};')

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

    # default output file name if not provided
    if not args.output_file:
        base = os.path.splitext(os.path.basename(args.verilog_file))[0]
        args.output_file = base + "_cfg.svg"
        print(f"Warning: defaulting to {args.output_file}")
    
    # Determine output format from extension or override
    fmt = args.format or os.path.splitext(args.output_file)[1][1:].lower()
    if not fmt: # If no extension and no format specified
        fmt = 'svg'
        args.output_file += '.svg'
    args.format = fmt

    # Read Verilog source lines for source text display in tooltips
    try:
        with open(args.verilog_file) as f:
            global verilog_code_lines
            verilog_code_lines = f.readlines()
    except FileNotFoundError:
        sys.exit(f"Error: cannot open {args.verilog_file}")

    # Run Verilator to generate XML AST
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
        sys.exit("Error: 'verilator' not found in your PATH. Please install Verilator.")
    except subprocess.CalledProcessError as e:
        sys.exit(f"Verilator error:\n{e.stderr}\n{e.stdout}")

    # Parse XML AST and traverse to build CFG and DFG
    tree = ET.parse(ast_path)
    os.remove(ast_path) # Clean up temporary AST file
    nl = tree.find('netlist')
    if nl is not None:
        for mod in nl.findall('module'):
            # Reset SSA counters for each module to ensure independent SSA for each module
            global ssacounter, latestversion
            ssacounter = {}
            latestversion = {}
            # Traverse statements within the module
            for item in mod:
                traverse_statement(item)

    # Generate DOT graph description
    dot = generate_dot('CFG', args) # The 'CFG' graph now includes DFG edges

    # Output DOT or render image using Graphviz
    if fmt=='dot':
        with open(args.output_file,'w') as f:
            f.write(dot)
        print(f"Wrote DOT → {args.output_file}")
    else:
        # Write to a temporary .dot file, then call Graphviz 'dot' command
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
            sys.exit("Error: 'dot' (Graphviz) not found. Please install Graphviz (e.g., `sudo apt-get install graphviz`).")
        except subprocess.CalledProcessError as e:
            sys.exit(f"Graphviz error:\n{e.stderr}\n{e.stdout}")
        finally:
            os.remove(dot_path) # Clean up temporary DOT file

if __name__=='__main__':
    main()
