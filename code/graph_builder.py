# File: graph_builder.py

import xml.etree.ElementTree as ET
from graph_model import Graph, DesignHierarchy
from ast_utils import expr_to_str, collect_var_names
from block_classifier import classify_block # Import the new classifier

class GraphBuilder:
    """Traverses an XML AST to build a hierarchical, multi-level graph."""
    def __init__(self, verilog_code_lines=None):
        self.verilog_code_lines = verilog_code_lines if verilog_code_lines else []
        self.hierarchy = None
        self.current_graph = None # The graph we are currently building on
        self.operationmap = {
            'add': 'ADD', 'sub': 'SUB', 'and': 'AND', 'or': 'OR', 'xor': 'XOR',
            'mul': 'MUL', 'div': 'DIV', 'mod': 'MOD', 'sll': 'SLL', 'srl': 'SRL',
            'sra': 'SRA', 'lt': 'LT', 'lte': 'LTE', 'gt': 'GT', 'gte': 'GTE',
            'eq': 'EQ', 'neq': 'NEQ', 'land': 'LAND', 'lor': 'LOR',
            'neg': 'NEG', 'not': 'NOT', 'lnot': 'LNOT',
            'concat': 'CONCAT', 'bitselect': 'BITSEL', 'partselect': 'PARTSEL'
        }

    def build_from_xml_root(self, root: ET.Element) -> DesignHierarchy:
        """Starts the graph building process from the XML root."""
        netlist = root.find('netlist')
        if netlist is not None:
            for module in netlist.findall('module'):
                module_name = module.get("name", "top")
                self.hierarchy = DesignHierarchy(module_name)
                self.current_graph = self.hierarchy.architectural_graph
                self.current_graph.reset_ssa_state()
                
                # Add a top-level cluster for the module itself in the architectural view
                arch_cluster_id = self.current_graph.add_cluster(f"Module: {module_name}", color="lightblue")
                self.current_graph.cluster_stack.append(arch_cluster_id)
                
                for item in module:
                    # We only create high-level nodes in the architectural graph
                    self._traverse_architectural_view(item)
        return self.hierarchy

    def _traverse_architectural_view(self, elem):
        """
        Traverses the AST to build the high-level architectural view.
        When it finds a procedural block, it creates a detailed sub-graph.
        """
        if elem is None: return
        tag = elem.tag.lower()

        if tag in ('always', 'initial'):
            classification = classify_block(elem)
            arch_graph = self.hierarchy.architectural_graph
            parent_cluster = arch_graph.cluster_stack[-1] if arch_graph.cluster_stack else None

            # Add a single node to the architectural graph for this block
            arch_node_label = f"{classification}\\n({tag})"
            arch_node_id = arch_graph.add_cfg_node(arch_node_label, cluster_id=parent_cluster)
            
            # Create a unique key for the sub-graph
            sub_graph_key = f"cluster_{len(self.hierarchy.sub_graphs)}"
            arch_graph.clusters[parent_cluster]['metadata'][arch_node_id] = {'link': sub_graph_key}

            # Now, create and build the detailed graph for this block
            detailed_graph = Graph(name=sub_graph_key)
            self.hierarchy.add_sub_graph(sub_graph_key, detailed_graph)
            
            # Temporarily switch context to build the detailed graph
            original_graph = self.current_graph
            self.current_graph = detailed_graph
            
            # Create a cluster in the detailed graph
            detail_cluster_id = self.current_graph.add_cluster(f"Details: {classification}", color="lightgoldenrodyellow")
            self.current_graph.cluster_stack.append(detail_cluster_id)
            
            # Use the original detailed traversal logic for the block's children
            entry_node = self.current_graph.add_cfg_node(f"Enter {tag}", cluster_id=detail_cluster_id)
            last_node = entry_node
            for child in elem:
                child_node = self._traverse_detailed_view(child)
                if child_node is not None:
                    self.current_graph.add_cfg_edge(last_node, child_node)
                    last_node = child_node
            
            self.current_graph.cluster_stack.pop()
            
            # Restore context to the architectural graph
            self.current_graph = original_graph

        # We can add logic here to find module instances for the architectural graph too
        # For now, we only abstract away procedural blocks.

    def _traverse_detailed_view(self, elem):
        """
        This is the original traversal logic, now used to build the
        detailed sub-graphs for each procedural block.
        """
        if elem is None: return None
        graph = self.current_graph
        tag, loc = elem.tag.lower(), elem.get('loc')
        line_num = int(loc.split(',')[1]) if loc and ',' in loc else None
        
        def record(node_id):
            if node_id is not None and line_num is not None: graph.cfg_node_to_line_num[node_id] = line_num
            return node_id
        
        parent_cluster = graph.cluster_stack[-1] if graph.cluster_stack else None

        if tag in ('var','decl','param','genvar'): return None
        if tag == 'begin':
            last = None
            for c in elem:
                n = self._traverse_detailed_view(c)
                if n is not None:
                    if last is not None: graph.add_cfg_edge(last, n)
                    last = n
            return last

        if tag in ('if','ifstmt'):
            cond = elem.find('cond') or next((c for c in elem if c.tag.lower() in self.operationmap or c.tag.lower() in ('varref','const')), None)
            used = {graph.get_latest_version(v) for v in collect_var_names(cond)}
            lbl = f"if ({expr_to_str(cond)})"
            node_if = record(graph.add_cfg_node(lbl, cluster_id=parent_cluster))
            graph.cfg_node_uses[node_if] = used
            node_end = graph.add_cfg_node('EndIf', cluster_id=parent_cluster)
            
            then_node = self._traverse_detailed_view(elem.find('then'))
            if then_node: graph.add_cfg_edge(node_if, then_node, 'True'); graph.add_cfg_edge(then_node, node_end)
            else: graph.add_cfg_edge(node_if, node_end, 'True')
            
            else_node = self._traverse_detailed_view(elem.find('else'))
            if else_node: graph.add_cfg_edge(node_if, else_node, 'False'); graph.add_cfg_edge(else_node, node_end)
            else: graph.add_cfg_edge(node_if, node_end, 'False')
            return node_end
        
        if tag in ('assign','blockingassign','nonblockingassign'):
            rhs, lhs = list(elem)[0], list(elem)[-1]
            op = '<=' if 'nonblocking' in tag else '='
            lbl = f"{expr_to_str(lhs)} {op} {expr_to_str(rhs)}"
            nid = record(graph.add_cfg_node(lbl, cluster_id=parent_cluster))
            # DFG logic can be added here if needed for the detailed view
            return nid
        
        # Fallback for other unhandled tags
        last = None
        for c in elem:
            nd = self._traverse_detailed_view(c)
            if nd is not None:
                if last is not None: graph.add_cfg_edge(last, nd)
                last = nd
        return last

