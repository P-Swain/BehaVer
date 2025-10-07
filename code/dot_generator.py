# File: dot_generator.py

import re
import html
from graph_model import Graph # Import the data model

# Visual-style map for Verilog constructs and data types
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
    (r'^OP:',                dict(shape='box',           style='filled', fillcolor='lightgreen',     color='darkgreen', fontcolor='black')),
]

def generate_dot(graph: Graph, graph_name: str, args) -> str:
    """Generates the DOT graph description from a Graph object."""
    def get_node_attributes(nid):
        """Determines DOT attributes for a CFG node based on its label and type."""
        txt = graph.cfg_nodes[nid].replace('"', '\\"')
        attrs = {'label': f'"{txt}"'}
        # Default attributes
        attrs.update(shape='ellipse', style='filled', fillcolor='white', color='black')
        # Apply STYLE_MAP
        for pat, style_kwargs in STYLE_MAP:
            if re.search(pat, txt):
                attrs.update(**style_kwargs)
                break
        # SVG tooltips for source code and line number
        if args.format == 'svg':
            tips = []
            if nid in graph.cfg_node_to_line_num:
                tips.append(f"Line: {graph.cfg_node_to_line_num[nid]}")
            if nid in graph.node_to_sourcetext:
                tips.append(html.escape(graph.node_to_sourcetext[nid]))
            if tips:
                attrs['tooltip'] = '"' + "\\n".join(tips) + '"'
        return ",".join(f"{k}={v}" for k, v in attrs.items())

    lines = ["digraph {} {{".format(graph_name), "  rankdir=LR; splines=ortho;"]

    if graph_name == 'CFG':
        # Add clusters (modules, always blocks, etc.)
        used_cfg_nodes = set()
        for i, cl in enumerate(graph.clusters):
            lines.append("  subgraph cluster_{} {{".format(i))
            lines.append(f'    label="{cl["name"]}"; style=filled; color="{cl["color"]}";')
            for nid in cl['node_ids']:
                used_cfg_nodes.add(nid)
                lines.append(f"    n{nid} [{get_node_attributes(nid)}];")
            lines.append("  }")

        # Add CFG nodes not part of any explicit cluster
        for nid in range(len(graph.cfg_nodes)):
            if nid in used_cfg_nodes: continue
            lines.append(f"  n{nid} [{get_node_attributes(nid)}];")

        lines.append("  # CFG Edges")
        for s, d, lbl in graph.cfg_edges:
            attr = f' [xlabel="{lbl}"]' if lbl else ""
            lines.append(f"  n{s} -> n{d}{attr};")

        lines.append("  # DFG Edges (overlayed on CFG)")
        defs_by_var_ssa = {}
        for nid, var_ssa_name in graph.cfg_node_defs.items():
            defs_by_var_ssa.setdefault(var_ssa_name, []).append(nid)

        for uid, used_vars_ssa_set in graph.cfg_node_uses.items():
            for v_ssa_name in used_vars_ssa_set:
                for did in defs_by_var_ssa.get(v_ssa_name, []):
                    if args.no_inter_cluster_dfg:
                        cd = graph.node_to_cluster.get(did)
                        cu = graph.node_to_cluster.get(uid)
                        if cd is not None and cu is not None and cd != cu:
                            continue
                    lines.append(f'  n{did} -> n{uid} [style=dashed,color=red,constraint=false,xlabel="{v_ssa_name}"];')
    else:  # DFG-only graph
        for nid, txt in enumerate(graph.dfg_nodes):
            sanitized_txt = txt.replace('"', '\\"')
            # Then, use this new, clean variable inside the f-string.
            lines.append(f'  dfg_n{nid} [label="{sanitized_txt}",shape=ellipse];')
        for s, d in graph.dfg_edges:
            lines.append(f'  dfg_n{s} -> dfg_n{d};')

    lines.append("}")
    return "\n".join(lines)