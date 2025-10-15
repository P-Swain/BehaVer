# File: dot_generator.py

import re
import html
from graph_model import DesignHierarchy, Graph

STYLE_MAP = [
    # Architectural Styles
    (r'FSM Controller',      dict(shape='Mdiamond',      style='filled', fillcolor='skyblue')),
    (r'Counter',             dict(shape='doubleoctagon', style='filled', fillcolor='lightgreen')),
    (r'Datapath',            dict(shape='octagon',       style='filled', fillcolor='lightcoral')),
    (r'Sequential Logic',    dict(shape='box',           style='filled,rounded', fillcolor='darkseagreen1')),
    (r'Combinational Logic', dict(shape='box',           style='filled,rounded', fillcolor='lightgoldenrod')),
    # Detailed Styles
    (r'^if ',                dict(shape='diamond',       style='filled', fillcolor='lightcyan',      color='teal')),
    (r'<=',                  dict(shape='box3d',         style='filled', fillcolor='lightcoral',     color='darkred')),
    (r'=',                   dict(shape='box3d',         style='filled', fillcolor='lightsalmon',    color='darkorange')),
]

def _generate_single_dot(graph: Graph, output_basename: str, args, is_arch=False) -> str:
    """Generates the DOT graph description for a single Graph object."""
    def quote_attr(val):
        """Helper to ensure DOT attribute values are properly quoted."""
        if isinstance(val, str) and val.startswith('"') and val.endswith('"'):
            return val
        return f'"{val}"'

    def get_node_attributes(nid, link_map=None):
        """
        Determines DOT attributes for a CFG node.
        Accepts an optional link_map for adding URLs.
        """
        txt = graph.cfg_nodes[nid].replace('"', '\\"').replace('\n', '\\n')
        # The label value is already quoted here
        attrs = {'label': f'"{txt}"'}

        # Apply styles from the map
        for pat, style_kwargs in STYLE_MAP:
            if re.search(pat, txt):
                attrs.update(**style_kwargs)
                break
        
        # Add URL for drill-down if it's an architectural node and a link exists
        if is_arch and link_map and nid in link_map:
            link_key = link_map[nid]['link']
            # The URL and tooltip values are also explicitly quoted here
            attrs['URL'] = f'"{output_basename}_{link_key}.{args.format}"'
            attrs['tooltip'] = '"Click to see details"'

        # Join all attributes, ensuring every value is quoted
        return ",".join(f"{k}={quote_attr(v)}" for k, v in attrs.items())

    lines = [f"digraph {graph.name} {{", "  rankdir=TB; splines=ortho;"]

    # Add clusters
    for i, cl in enumerate(graph.clusters):
        lines.append(f"  subgraph cluster_{i} {{")
        lines.append(f'    label="{cl["name"]}"; style=filled; color="{cl["color"]}";')
        node_link_map = cl.get('metadata', {})
        for nid in cl['node_ids']:
            lines.append(f"    n{nid} [{get_node_attributes(nid, link_map=node_link_map if is_arch else None)}];")
        lines.append("  }")

    # Add CFG Edges
    for s, d, lbl in graph.cfg_edges:
        attr = f' [xlabel="{lbl}"]' if lbl else ""
        lines.append(f"  n{s} -> n{d}{attr};")

    lines.append("}")
    return "\n".join(lines)

def generate_all_dots(hierarchy: DesignHierarchy, output_basename: str, args) -> dict:
    """
    Generates all DOT files for the entire hierarchy.
    Returns a dictionary of {filename: dot_content}.
    """
    dot_files = {}
    arch_graph = hierarchy.architectural_graph

    # Generate the main architectural graph with links
    arch_filename = f"{output_basename}_arch.dot"
    dot_files[arch_filename] = _generate_single_dot(arch_graph, output_basename, args, is_arch=True)

    # Generate dot files for all sub-graphs
    for key, sub_graph in hierarchy.sub_graphs.items():
        sub_graph_filename = f"{output_basename}_{key}.dot"
        dot_files[sub_graph_filename] = _generate_single_dot(sub_graph, output_basename, args)

    return dot_files

