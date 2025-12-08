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
        self.signal_registry = {} 
        self.collected_ports = {'input': [], 'output': [], 'inout': []}
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
                
                self.signal_registry = {}
                self.collected_ports = {'input': [], 'output': [], 'inout': []}
                
                arch_cluster_id = self.current_graph.add_cluster(f"Module: {module_name}", color="lightblue")
                self.current_graph.cluster_stack.append(arch_cluster_id)
                
                for item in module:
                    self._traverse_architectural_view(item)
                
                self._create_aggregated_port_nodes()
                self._resolve_connections()
                
                self.current_graph.cluster_stack.pop()
                hierarchies.append(self.hierarchy)
        return hierarchies

    def _create_aggregated_port_nodes(self):
        arch_graph = self.hierarchy.architectural_graph
        parent_cluster = arch_graph.cluster_stack[-1] if arch_graph.cluster_stack else None

        for direction, ports in self.collected_ports.items():
            if not ports: continue
            
            label = f"{direction.capitalize()}s"
            node_id = arch_graph.add_cfg_node(label, cluster_id=parent_cluster)
            
            full_list_str = "\n".join(ports)
            arch_graph.add_node_metadata(node_id, "type", "port_group")
            arch_graph.add_node_metadata(node_id, "content", full_list_str)

            reg_dir = 'out' if direction == 'input' else 'in'
            if direction == 'inout': reg_dir = 'inout'

            for p_name in ports:
                if p_name not in self.signal_registry:
                    self.signal_registry[p_name] = []
                self.signal_registry[p_name].append({'id': node_id, 'dir': reg_dir})

    def _traverse_architectural_view(self, elem):
        if elem is None: return
        tag = elem.tag.lower()

        # --- 1. Handle Procedural Blocks ---
        if tag in ('always', 'initial', 'always_comb', 'always_ff', 'always_latch', 'assign', 'contassign'):
            classification = classify_block(elem)
            
            # --- SMART LABELING START ---
            # Extract logic summary to display on the node (e.g. "a = b & c")
            label_extra = ""
            
            # Helper to safely get name/value
            def get_name(e):
                if e.tag == 'varref': return e.get('name')
                if e.tag == 'const': return e.get('name') # e.g. "1'h1"
                if e.tag in self.operationmap: return self.operationmap[e.tag]
                return "?"

            if tag in ('assign', 'contassign'):
                # In Verilator XML, contassign usually has RHS elements then LHS last.
                if len(elem) >= 2:
                    lhs = elem[-1]
                    rhs = elem[0] # Simplified: grabbing first RHS operand
                    lhs_str = get_name(lhs)
                    rhs_str = get_name(rhs)
                    
                    if len(elem) > 2: rhs_str += "..." # Indicate complex logic
                    label_extra = f"\\n{lhs_str} <= {rhs_str}"
            
            elif tag == 'initial':
                # Detect simple parameter inits: initial -> assign -> (const, varref)
                if len(elem) == 1 and elem[0].tag == 'assign':
                    assign_block = elem[0]
                    if len(assign_block) >= 2:
                        rhs = assign_block[0]
                        lhs = assign_block[-1]
                        if rhs.tag == 'const':
                             classification = "Init"
                             label_extra = f"\\n{get_name(lhs)} = {get_name(rhs)}"
            # --- SMART LABELING END ---

            arch_graph = self.hierarchy.architectural_graph
            parent_cluster = arch_graph.cluster_stack[-1] if arch_graph.cluster_stack else None

            arch_node_label = f"{classification}{label_extra}"
            arch_node_id = arch_graph.add_cfg_node(arch_node_label, cluster_id=parent_cluster)
            
            self._scan_block_for_signals(elem, arch_node_id)

            sub_graph_key = f"cluster_{len(self.hierarchy.sub_graphs)}"
            if parent_cluster is not None and arch_graph.clusters:
                 arch_graph.clusters[parent_cluster].setdefault('metadata', {})[arch_node_id] = {'link': sub_graph_key}

            detailed_graph = Graph(name=sub_graph_key)
            self.hierarchy.add_sub_graph(sub_graph_key, detailed_graph)
            
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

        # --- 2. Handle Module Instances ---
        elif tag in ('inst', 'instance'):
            inst_name = elem.get('name')
            mod_type = elem.get('defName')
            
            arch_graph = self.hierarchy.architectural_graph
            parent_cluster = arch_graph.cluster_stack[-1] if arch_graph.cluster_stack else None
            
            label = f"{inst_name}\n({mod_type})"
            node_id = arch_graph.add_cfg_node(label, cluster_id=parent_cluster)
            
            arch_graph.add_node_metadata(node_id, "module_link", mod_type)
            
            for port in elem.findall('port'):
                raw_dir = port.get('direction', 'inout')
                direction = 'inout'
                if raw_dir in ('input', 'in'): direction = 'in'
                elif raw_dir in ('output', 'out'): direction = 'out'

                for conn in port.findall('.//varref'):
                    signal_name = conn.get('name')
                    if signal_name:
                        if signal_name not in self.signal_registry:
                            self.signal_registry[signal_name] = []
                        self.signal_registry[signal_name].append({'id': node_id, 'dir': direction})

        # --- 3. Handle Module Ports ---
        elif tag == 'var':
            direction = elem.get('dir')
            if direction: 
                name = elem.get('name')
                norm_dir = 'inout'
                if direction in ('input', 'in'): norm_dir = 'input'
                elif direction in ('output', 'out'): norm_dir = 'output'
                self.collected_ports[norm_dir].append(name)

    def _scan_block_for_signals(self, block_elem, node_id):
        ASSIGN_TAGS = ('assign', 'contassign', 'blockingassign', 'nonblockingassign')
        
        def recursive_scan(elem, current_mode='read'):
            if elem is None: return
            tag = elem.tag.lower()

            if tag in ASSIGN_TAGS:
                children = list(elem)
                if children:
                    recursive_scan(children[0], current_mode='write')
                    for child in children[1:]:
                        recursive_scan(child, current_mode='read')
                return

            if tag == 'varref':
                name = elem.get('name')
                if name:
                    direction = 'out' if current_mode == 'write' else 'in'
                    if name not in self.signal_registry:
                        self.signal_registry[name] = []
                    entry = {'id': node_id, 'dir': direction}
                    if entry not in self.signal_registry[name]:
                        self.signal_registry[name].append(entry)
                return

            for child in elem:
                recursive_scan(child, current_mode)

        recursive_scan(block_elem)

    def _resolve_connections(self):
        graph = self.hierarchy.architectural_graph
        IGNORED = {'clk', 'rst', 'clk_i', 'rst_i', 'clock', 'reset'}
        connections = {}

        for signal, ports in self.signal_registry.items():
            if len(ports) < 2 or signal in IGNORED:
                continue 
            
            drivers = [p['id'] for p in ports if p['dir'] == 'out']
            receivers = [p['id'] for p in ports if p['dir'] == 'in']
            
            def add_conn(s, d, sig):
                if s == d: return
                if (s, d) not in connections: connections[(s, d)] = []
                if sig not in connections[(s, d)]: connections[(s, d)].append(sig)

            if drivers and receivers:
                for src in drivers:
                    for dst in receivers:
                        add_conn(src, dst, signal)
            elif not drivers and len(ports) > 1:
                 nodes = sorted(list({p['id'] for p in ports}))
                 for i in range(len(nodes) - 1):
                     add_conn(nodes[i], nodes[i+1], signal)
        
        for (src, dst), signal_list in connections.items():
            graph.add_cfg_edge(src, dst, label=signal_list)

    def _traverse_detailed_view(self, elem):
        if elem is None: return None
        graph = self.current_graph
        tag = elem.tag.lower()
        loc = elem.get('loc')
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