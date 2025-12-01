# File: dot_generator.py

import re
from graph_model import DesignHierarchy, Graph

STYLE_MAP = [
    (r'FSM Controller',      dict(shape='Mdiamond',      style='filled', fillcolor='skyblue')),
    (r'Counter',             dict(shape='doubleoctagon', style='filled', fillcolor='lightgreen')),
    (r'Datapath',            dict(shape='octagon',       style='filled', fillcolor='lightcoral')),
    (r'Sequential Logic',    dict(shape='box',           style='filled,rounded', fillcolor='darkseagreen1')),
    (r'Combinational Logic', dict(shape='box',           style='filled,rounded', fillcolor='lightgoldenrod')),
    (r'^if ',                dict(shape='diamond',       style='filled', fillcolor='lightcyan',      color='teal')),
    (r'<=',                  dict(shape='box3d',         style='filled', fillcolor='lightcoral',     color='darkred')),
    (r'=',                   dict(shape='box3d',         style='filled', fillcolor='lightsalmon',    color='darkorange')),
]

def _generate_single_dot(graph: Graph, output_basename: str, link_prefix: str, args, is_arch=False) -> str:
    def quote_attr(val):
        if isinstance(val, str) and val.startswith('"') and val.endswith('"'):
            return val
        return f'"{val}"'

    def get_node_attributes(nid, link_map=None):
        txt = graph.cfg_nodes[nid].replace('"', '\\"').replace('\n', '\\n')
        attrs = {'label': f'"{txt}"'}

        for pat, style_kwargs in STYLE_MAP:
            if re.search(pat, txt):
                attrs.update(**style_kwargs)
                break
        
        if is_arch and link_map and nid in link_map:
            link_key = link_map[nid]['link']
            target_svg = f"{output_basename}_{link_key}.{args.format}"
            attrs['URL'] = f'"viewer.html?file={target_svg}"'
            attrs['target'] = '"_top"'
            attrs['tooltip'] = '"Click to see details"'
        
        meta = graph.node_metadata.get(nid, {})
        if 'module_link' in meta:
            target_mod = meta['module_link']
            target_svg = f"{link_prefix}_{target_mod}_arch.{args.format}"
            attrs['URL'] = f'"viewer.html?file={target_svg}"'
            attrs['target'] = '"_top"'
            attrs['style'] = '"filled,bold"'
            attrs['fillcolor'] = '"#e6f3ff"'
            attrs['tooltip'] = f'"Go to module: {target_mod}"'

        return ",".join(f"{k}={quote_attr(v)}" for k, v in attrs.items())

    # Uses ortho for block-diagram look
    lines = [f"digraph {graph.name} {{", 
             "  rankdir=TB; splines=ortho;", 
             "  graph [ranksep=2.0, nodesep=1.5];", 
             "  node [shape=box, style=filled, fillcolor=white, fontsize=12, fontname=\"Arial\"];",
             "  edge [fontname=\"Arial\", fontsize=10, color=\"#555555\"];"
            ]

    for i, cl in enumerate(graph.clusters):
        lines.append(f"  subgraph cluster_{i} {{")
        lines.append(f'    label="{cl["name"]}"; style=filled; color="{cl["color"]}";')
        node_link_map = cl.get('metadata', {})
        for nid in cl['node_ids']:
            lines.append(f"    n{nid} [{get_node_attributes(nid, link_map=node_link_map if is_arch else None)}];")
        lines.append("  }")

    for s, d, lbl_data in graph.cfg_edges:
        if not lbl_data:
             lines.append(f"  n{s} -> n{d};")
             continue

        # Handle Bus (List of signals)
        if isinstance(lbl_data, list):
            count = len(lbl_data)
            full_list_str = "\\n".join(lbl_data) # Use literal \n for DOT strings
            safe_tooltip = full_list_str.replace('"', '\\"')
            
            if count > 3:
                hitbox_text = f"Bus: {count} signals"
            else:
                hitbox_text = full_list_str

            safe_xlabel = hitbox_text.replace('"', '\\"').replace('\n', '\\n')
            
            # Thick line for Bus, transparent xlabel for hit area
            attr = (f' [xlabel="{safe_xlabel}", fontcolor="#00000000", '
                    f'tooltip="{safe_tooltip}", penwidth=4.0, arrowsize=1.5, color="#333333"]')
        
        # Handle Single Wire
        else:
            safe_lbl = str(lbl_data).replace('"', '\\"')
            attr = (f' [xlabel="{safe_lbl}", fontcolor="#00000000", '
                    f'tooltip="{safe_lbl}", penwidth=2.0, arrowsize=1.0]')
            
        lines.append(f"  n{s} -> n{d}{attr};")

    lines.append("}")
    return "\n".join(lines)

def generate_all_dots(hierarchy: DesignHierarchy, output_basename: str, link_prefix: str, args) -> dict:
    dot_files = {}
    arch_graph = hierarchy.architectural_graph

    arch_filename = f"{output_basename}_arch.dot"
    dot_files[arch_filename] = _generate_single_dot(arch_graph, output_basename, link_prefix, args, is_arch=True)

    for key, sub_graph in hierarchy.sub_graphs.items():
        sub_graph_filename = f"{output_basename}_{key}.dot"
        dot_files[sub_graph_filename] = _generate_single_dot(sub_graph, output_basename, link_prefix, args)

    return dot_files