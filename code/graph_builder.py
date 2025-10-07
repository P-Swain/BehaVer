# File: graph_builder.py

import xml.etree.ElementTree as ET
from graph_model import Graph
from ast_utils import expr_to_str, collect_var_names

class GraphBuilder:
    """Traverses an XML AST to build a CFG and DFG in a Graph object."""
    def __init__(self, verilog_code_lines=None):
        self.graph = Graph()
        self.verilog_code_lines = verilog_code_lines if verilog_code_lines else []
        self.operationmap = {
            'add': 'ADD', 'sub': 'SUB', 'and': 'AND', 'or': 'OR', 'xor': 'XOR',
            'mul': 'MUL', 'div': 'DIV', 'mod': 'MOD', 'sll': 'SLL', 'srl': 'SRL',
            'sra': 'SRA', 'lt': 'LT', 'lte': 'LTE', 'gt': 'GT', 'gte': 'GTE',
            'eq': 'EQ', 'neq': 'NEQ', 'land': 'LAND', 'lor': 'LOR',
            'neg': 'NEG', 'not': 'NOT', 'lnot': 'LNOT',
            'concat': 'CONCAT', 'bitselect': 'BITSEL', 'partselect': 'PARTSEL'
        }

    def build_from_xml_root(self, root: ET.Element) -> Graph:
        """Starts the graph building process from the XML root."""
        netlist = root.find('netlist')
        if netlist is not None:
            for module in netlist.findall('module'):
                self.graph.reset_ssa_state()
                for item in module:
                    self._traverse_statement(item)
        return self.graph

    def _process_expression_for_dfg(self, expr_elem, current_cluster_id=None):
        if expr_elem is None:
            return []
        op_type = self.operationmap.get(expr_elem.tag.lower())
        if op_type:
            op_label = f"OP: {op_type}\n{expr_to_str(expr_elem)}"
            op_cfg_node_id = self.graph.add_cfg_node(op_label, cluster_id=current_cluster_id)
            op_result_ssa_name = f"op_result_{op_type}_{op_cfg_node_id}"
            op_dfg_node_id = self.graph.get_dfg_node_id(op_result_ssa_name)
            
            operands_dfg_node_ids = []
            for child in expr_elem:
                child_dfg_ids = self._process_expression_for_dfg(child, current_cluster_id)
                for child_dfg_id in child_dfg_ids:
                    self.graph.add_dfg_edge(child_dfg_id, op_dfg_node_id)
                operands_dfg_node_ids.extend(child_dfg_ids)
            
            self.graph.cfg_node_defs[op_cfg_node_id] = op_result_ssa_name
            self.graph.cfg_node_uses[op_cfg_node_id] = {self.graph.dfg_nodes[n] for n in operands_dfg_node_ids}
            return [op_dfg_node_id]
        else:
            var_names = collect_var_names(expr_elem)
            return [self.graph.get_dfg_node_id(self.graph.get_latest_version(v)) for v in var_names]

    def _process_assignment(self, elem):
        ch = list(elem)
        if len(ch) < 2: return []
        rhs_elem, lhs_elem = ch[0], ch[-1]
        lr = lhs_elem.find('.//varref') or lhs_elem
        lhs_var_name = lr.get('name', '<unnamed>')
        new_lhs_ssa_name = self.graph.get_ssa_name(lhs_var_name)
        new_lhs_dfg_node_id = self.graph.get_dfg_node_id(new_lhs_ssa_name)
        cluster = self.graph.cluster_stack[-1] if self.graph.cluster_stack else None
        rhs_outputs_dfg_ids = self._process_expression_for_dfg(rhs_elem, cluster)
        for rhs_output_dfg_id in rhs_outputs_dfg_ids:
            self.graph.add_dfg_edge(rhs_output_dfg_id, new_lhs_dfg_node_id)
        return [new_lhs_ssa_name]

    def _process_control(self, elem):
        cond_elem = elem.find('cond')
        if cond_elem is None:
            for c in elem:
                if c.tag.lower() in self.operationmap or c.tag.lower() in ('varref', 'const'):
                    cond_elem = c
                    break
        if cond_elem is not None:
            cluster = self.graph.cluster_stack[-1] if self.graph.cluster_stack else None
            self._process_expression_for_dfg(cond_elem, cluster)

    def _traverse_statement(self, elem):
        if elem is None: return None
        tag, loc = elem.tag.lower(), elem.get('loc')
        line_num = int(loc.split(',')[1]) if loc and ',' in loc else None
        def record(node_id):
            if node_id is not None and line_num is not None: self.graph.cfg_node_to_line_num[node_id] = line_num
            return node_id
        
        parent_cluster = self.graph.cluster_stack[-1] if self.graph.cluster_stack else None

        if tag in ('initial', 'always', 'function', 'task'):
            # ... structural block logic ...
            # (Full logic from original script, but using self.graph)
            # This is a simplified placeholder for the full logic.
            label, color = f"Block: {tag}", "lightblue" # Simplified
            cid = self.graph.add_cluster(label, color)
            self.graph.cluster_stack.append(cid)
            entry = self.graph.add_cfg_node(f"Enter {tag}", cluster_id=cid)
            last = entry
            children = [c for c in elem if c.tag.lower() not in ('sentree','senitem','var','decl','param')]
            for c in children:
                n = self._traverse_statement(c)
                if n is not None:
                    self.graph.add_cfg_edge(last, n)
                    last = n
            self.graph.cluster_stack.pop()
            return last

        if tag in ('var','decl','param','genvar'): return None
        if tag == 'begin':
            last = None
            for c in elem:
                n = self._traverse_statement(c)
                if n is not None:
                    if last is not None: self.graph.add_cfg_edge(last, n)
                    last = n
            return last

        if tag in ('if','ifstmt'):
            self._process_control(elem)
            cond = elem.find('cond') or next((c for c in elem if c.tag.lower() in self.operationmap or c.tag.lower() in ('varref','const')), None)
            used = {self.graph.get_latest_version(v) for v in collect_var_names(cond)}
            lbl = f"if ({expr_to_str(cond)})\nUSE: {', '.join(used) if used else 'none'}"
            node_if = record(self.graph.add_cfg_node(lbl, cluster_id=parent_cluster))
            self.graph.cfg_node_uses[node_if] = used
            node_end = self.graph.add_cfg_node('EndIf', cluster_id=parent_cluster)
            
            then_node = self._traverse_statement(elem.find('then'))
            if then_node: self.graph.add_cfg_edge(node_if, then_node, 'True'); self.graph.add_cfg_edge(then_node, node_end)
            else: self.graph.add_cfg_edge(node_if, node_end, 'True')
            
            else_node = self._traverse_statement(elem.find('else'))
            if else_node: self.graph.add_cfg_edge(node_if, else_node, 'False'); self.graph.add_cfg_edge(else_node, node_end)
            else: self.graph.add_cfg_edge(node_if, node_end, 'False')
            return node_end
        
        if tag in ('assign','blockingassign','nonblockingassign', 'continuousassign','contassign','assigndly'):
            defined = self._process_assignment(elem)
            rhs, lhs = list(elem)[0], list(elem)[-1]
            lhs_var = (lhs.find('.//varref') or lhs).get('name', '<unnamed>')
            rhs_used = {self.graph.get_latest_version(v) for v in collect_var_names(rhs)}
            op = '<=' if 'nonblocking' in tag else '='
            lbl = f"{lhs_var} {op} {expr_to_str(rhs)}\nDEF: {defined[0] if defined else 'N/A'}\nUSE: {', '.join(rhs_used) if rhs_used else 'none'}"
            nid = record(self.graph.add_cfg_node(lbl, cluster_id=parent_cluster))
            if defined: self.graph.cfg_node_defs[nid] = defined[0]
            self.graph.cfg_node_uses[nid] = rhs_used
            return nid

        # Fallback for other unhandled tags
        last = None
        for c in elem:
            nd = self._traverse_statement(c)
            if nd is not None:
                if last is not None: self.graph.add_cfg_edge(last, nd)
                last = nd
        return last