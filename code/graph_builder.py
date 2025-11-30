# File: graph_builder.py

import xml.etree.ElementTree as ET
from graph_model import Graph, DesignHierarchy
from ast_utils import expr_to_str, collect_var_names
from block_classifier import classify_block

class GraphBuilder:
    """Traverses an XML AST to build a hierarchical, multi-level graph."""
    def __init__(self, verilog_code_lines=None):
        self.verilog_code_lines = verilog_code_lines if verilog_code_lines else []
        self.hierarchy = None
        self.current_graph = None 
        self.signal_registry = {} # Maps signal_name -> list of node_ids
        self.operationmap = {
            'add': 'ADD', 'sub': 'SUB', 'and': 'AND', 'or': 'OR', 'xor': 'XOR',
            'mul': 'MUL', 'div': 'DIV', 'mod': 'MOD', 'sll': 'SLL', 'srl': 'SRL',
            'sra': 'SRA', 'lt': 'LT', 'lte': 'LTE', 'gt': 'GT', 'gte': 'GTE',
            'eq': 'EQ', 'neq': 'NEQ', 'land': 'LAND', 'lor': 'LOR',
            'neg': 'NEG', 'not': 'NOT', 'lnot': 'LNOT',
            'concat': 'CONCAT', 'bitselect': 'BITSEL', 'partselect': 'PARTSEL'
        }

    def build_from_xml_root(self, root: ET.Element) -> list[DesignHierarchy]:
        """Starts the graph building process from the XML root."""
        hierarchies = []
        netlist = root.find('netlist')
        if netlist is not None:
            for module in netlist.findall('module'):
                module_name = module.get("name", "top")
                self.hierarchy = DesignHierarchy(module_name)
                self.current_graph = self.hierarchy.architectural_graph
                self.current_graph.reset_ssa_state()
                
                # Reset signal registry for each new module
                self.signal_registry = {}
                
                # Add a top-level cluster for the module itself
                arch_cluster_id = self.current_graph.add_cluster(f"Module: {module_name}", color="lightblue")
                self.current_graph.cluster_stack.append(arch_cluster_id)
                
                for item in module:
                    self._traverse_architectural_view(item)
                
                # Connect the instances based on shared signals
                self._resolve_connections()
                
                self.current_graph.cluster_stack.pop()
                hierarchies.append(self.hierarchy)
        return hierarchies

    def _traverse_architectural_view(self, elem):
        """
        Traverses the AST to build the high-level architectural view.
        """
        if elem is None: return
        tag = elem.tag.lower()

        # --- 1. Handle Behavioral Blocks (always, initial) ---
        if tag in ('always', 'initial', 'always_comb', 'always_ff', 'always_latch'):
            classification = classify_block(elem)
            arch_graph = self.hierarchy.architectural_graph
            parent_cluster = arch_graph.cluster_stack[-1] if arch_graph.cluster_stack else None

            # Add Node
            arch_node_label = f"{classification}\\n({tag})"
            arch_node_id = arch_graph.add_cfg_node(arch_node_label, cluster_id=parent_cluster)
            
            # Create Sub-graph Link
            sub_graph_key = f"cluster_{len(self.hierarchy.sub_graphs)}"
            if parent_cluster is not None and arch_graph.clusters:
                 arch_graph.clusters[parent_cluster].setdefault('metadata', {})[arch_node_id] = {'link': sub_graph_key}

            # Build Detailed Graph
            detailed_graph = Graph(name=sub_graph_key)
            self.hierarchy.add_sub_graph(sub_graph_key, detailed_graph)
            
            # Switch Context
            original_graph = self.current_graph
            self.current_graph = detailed_graph
            
            detail_cluster_id = self.current_graph.add_cluster(f"Details: {classification}", color="lightgoldenrodyellow")
            self.current_graph.cluster_stack.append(detail_cluster_id)
            
            entry_node = self.current_graph.add_cfg_node(f"Enter {tag}", cluster_id=detail_cluster_id)
            last_node = entry_node
            for child in elem:
                child_node = self._traverse_detailed_view(child)
                if child_node is not None:
                    self.current_graph.add_cfg_edge(last_node, child_node)
                    last_node = child_node
            
            self.current_graph.cluster_stack.pop()
            self.current_graph = original_graph

        # --- 2. Handle Structural Instances (Modules) ---
        # FIXED: Your XML uses 'instance', not 'inst'. I check for both now.
        elif tag in ('inst', 'instance'):
            inst_name = elem.get('name')
            mod_type = elem.get('defName')
            
            # Add Node
            arch_graph = self.hierarchy.architectural_graph
            parent_cluster = arch_graph.cluster_stack[-1] if arch_graph.cluster_stack else None
            
            label = f"{inst_name}\n({mod_type})"
            # Use a box shape for instances to distinguish them from logic blocks
            # (Note: dot_generator styles might need updates if you want specific colors, but this works)
            node_id = arch_graph.add_cfg_node(label, cluster_id=parent_cluster)
            
            # Map Ports to Signals for Wiring
            for port in elem.findall('port'):
                conn = port.find('varref')
                if conn is not None:
                    signal_name = conn.get('name')
                    
                    if signal_name not in self.signal_registry:
                        self.signal_registry[signal_name] = []
                    self.signal_registry[signal_name].append(node_id)

    def _resolve_connections(self):
        """Draws lines between nodes that share the same wire."""
        graph = self.hierarchy.architectural_graph
        
        # Filter out common global signals to prevent "hairballs"
        IGNORED_SIGNALS = {'clk', 'rst', 'clk_i', 'rst_i', 'clock', 'reset'}

        for signal, nodes in self.signal_registry.items():
            if len(nodes) < 2:
                continue 
            if signal in IGNORED_SIGNALS:
                continue

            # Connect nodes in a chain
            for i in range(len(nodes) - 1):
                src = nodes[i]
                dst = nodes[i+1]
                # Label the edge with the wire name so you see what connects them
                graph.add_cfg_edge(src, dst, label=signal)

    def _traverse_detailed_view(self, elem):
        """Standard traversal for detailed behavioral graphs."""
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
            nodes = [self._traverse_detailed_view(c) for c in elem]
            nodes = [n for n in nodes if n is not None]
            if not nodes: return None
            for i in range(len(nodes) - 1):
                graph.add_cfg_edge(nodes[i], nodes[i+1])
            return nodes[0]

        if tag in ('if','ifstmt'):
            cond = elem.find('cond') or next((c for c in elem if c.tag.lower() in self.operationmap or c.tag.lower() in ('varref','const')), None)
            used = {graph.get_latest_version(v) for v in collect_var_names(cond)}
            lbl = f"if ({expr_to_str(cond)})"
            node_if = record(graph.add_cfg_node(lbl, cluster_id=parent_cluster))
            graph.cfg_node_uses[node_if] = used
            
            node_end = graph.add_cfg_node('EndIf', cluster_id=parent_cluster)
            
            then_elem = elem.find('then')
            if then_elem is not None:
                then_node = self._traverse_detailed_view(then_elem)
                if then_node:
                    graph.add_cfg_edge(node_if, then_node, 'True')
                    graph.add_cfg_edge(then_node, node_end)
            else:
                graph.add_cfg_edge(node_if, node_end, 'True')
            
            else_elem = elem.find('else')
            if else_elem is not None:
                else_node = self._traverse_detailed_view(else_elem)
                if else_node:
                    graph.add_cfg_edge(node_if, else_node, 'False')
                    graph.add_cfg_edge(else_node, node_end)
            else:
                graph.add_cfg_edge(node_if, node_end, 'False')
            return node_if
        
        if tag in ('assign','blockingassign','nonblockingassign'):
            lhs_elem = elem.find('.//varref')
            rhs_elems = [c for c in elem if c is not lhs_elem]
            lhs_str = expr_to_str(lhs_elem)
            rhs_str = expr_to_str(rhs_elems[0]) if rhs_elems else ""
            op = '<=' if 'nonblocking' in tag else '='
            lbl = f"{lhs_str} {op} {rhs_str}"
            return record(graph.add_cfg_node(lbl, cluster_id=parent_cluster))
        
        nid = record(graph.add_cfg_node(f"Node: {tag}", cluster_id=parent_cluster))
        last = nid
        for c in elem:
            nd = self._traverse_detailed_view(c)
            if nd is not None:
                graph.add_cfg_edge(last, nd)
                last = nd
        return nid