import xml.etree.ElementTree as ET
import subprocess
import sys
import os
import argparse
import tempfile

# Graph data structures for CFG and DFG
cfg_nodes = []
cfg_edges = []  # list of (src_id, dst_id, label) for CFG edges
dfg_nodes = []
dfg_edges = []  # list of (src_id, dst_id) for DFG edges
dfg_node_map = {}  # map variable key to DFG node id

# Current context for naming
current_module = None
current_function = None
current_task = None
current_func_locals = set()
modules_count = 0

def collect_var_names(expr_elem):
    """Recursively collect variable names from an expression subtree (for DFG)."""
    vars = []
    if expr_elem is None:
        return vars
    tag = expr_elem.tag
    if tag in ("varref", "var", "signal"):
        name = expr_elem.get("name")
        if name:
            vars.append(name)
    for child in list(expr_elem):
        vars.extend(collect_var_names(child))
    return vars

def get_dfg_node(var_name):
    """Get or create a DFG node for the given variable (with module/function context)."""
    key = var_name
    # Prefix module name if multiple modules exist
    if modules_count > 1 and current_module:
        key = f"{current_module}::{key}"
    # Prefix function/task name if variable is local to a function/task
    if current_function and var_name in current_func_locals:
        if modules_count > 1:
            key = f"{current_module}.{current_function}::{var_name}"
        else:
            key = f"{current_function}::{var_name}"
    if current_task and var_name in current_func_locals:
        if modules_count > 1:
            key = f"{current_module}.{current_task}::{var_name}"
        else:
            key = f"{current_task}::{var_name}"
    # Get or create node
    if key in dfg_node_map:
        return dfg_node_map[key]
    node_id = len(dfg_nodes)
    dfg_nodes.append(key)
    dfg_node_map[key] = node_id
    return node_id

def add_cfg_node(label):
    node_id = len(cfg_nodes)
    cfg_nodes.append(label)
    return node_id

def add_cfg_edge(src, dst, label=""):
    cfg_edges.append((src, dst, label))

def add_dfg_edge(src, dst):
    edge = (src, dst)
    if edge not in dfg_edges:
        dfg_edges.append(edge)

def traverse_statement(elem):
    """Recursively traverse an AST statement element to build CFG and DFG."""
    global current_function, current_task, current_func_locals
    if elem is None:
        return None
    tag = elem.tag
    # Skip declarations or parameters (not part of control flow)
    if tag in ("var", "decl", "param", "genvar"):
        return None
    if tag == "begin":
        # Sequential block
        last_node = None
        for child in list(elem):
            node = traverse_statement(child)
            if node is None:
                continue
            if last_node is not None:
                add_cfg_edge(last_node, node)
            last_node = node
        return last_node
    if tag in ("function", "task"):
        # Enter function/task context
        prev_function = current_function
        prev_task = current_task
        prev_locals = current_func_locals
        if tag == "function":
            current_function = elem.get("name", "<function>")
            current_task = None
        else:
            current_task = elem.get("name", "<task>")
            current_function = None
        # Collect local variables declared in this function/task
        current_func_locals = set(child.get("name") for child in elem if child.tag == "var" and child.get("name"))
        # Create entry and exit nodes
        entry_label = f"{tag.capitalize()} {elem.get('name','')}".strip()
        entry_node = add_cfg_node(entry_label)
        end_label = f"End{tag.capitalize()} {elem.get('name','')}".strip()
        end_node = add_cfg_node(end_label if end_label != f"End{tag.capitalize()}" else f"End{tag.capitalize()}")
        # Traverse the function/task body
        body_start = None
        last_body_node = None
        for child in list(elem):
            if child.tag in ("var", "param", "decl"):
                continue  # skip declarations
            node = traverse_statement(child)
            if node is None:
                continue
            if body_start is None:
                body_start = node
            if last_body_node is not None:
                add_cfg_edge(last_body_node, node)
            last_body_node = node
        # Connect entry to body and body to exit
        if body_start:
            add_cfg_edge(entry_node, body_start)
            if last_body_node:
                add_cfg_edge(last_body_node, end_node)
            else:
                add_cfg_edge(body_start, end_node)
        else:
            # no statements in body
            add_cfg_edge(entry_node, end_node)
        # Restore previous context
        current_function = prev_function
        current_task = prev_task
        current_func_locals = prev_locals if prev_locals is not None else set()
        # Definitions are not part of execution flow linking
        return None
    if tag in ("if", "ifStmt"):
        # If statement
        # Determine condition
        cond_elem = None
        cond_container = elem.find("cond")
        if cond_container is not None:
            cond_elem = list(cond_container)[0] if len(list(cond_container)) > 0 else None
        else:
            children = list(elem)
            cond_elem = children[0] if children else None
        # Create condition node
        cond_label = "if"
        if cond_elem is not None:
            if cond_elem.get("name"):
                cond_label += f" ({cond_elem.get('name')})"
            else:
                first_sub = list(cond_elem)[0] if len(list(cond_elem)) > 0 else None
                cond_label += f" ({first_sub.get('name')})" if (first_sub is not None and first_sub.get("name")) else " (cond)"
        else:
            cond_label += " (cond)"
        cond_node = add_cfg_node(cond_label)
        # Traverse then and else branches
        then_start = None
        end_then = None
        else_start = None
        end_else = None
        children = list(elem)
        # Locate else element
        idx_else = next((i for i, c in enumerate(children) if c.tag == "else"), None)
        # Then branch children (skip first child which is cond expr if no 'cond' tag)
        start_idx = 1
        then_children = children[start_idx:idx_else] if idx_else is not None else children[start_idx:]
        if then_children and then_children[0].tag == "then":
            then_children = list(then_children[0])
        last_then = None
        for ch in then_children:
            node = traverse_statement(ch)
            if node is None:
                continue
            if then_start is None:
                then_start = node
            if last_then is not None:
                add_cfg_edge(last_then, node)
            last_then = node
        end_then = last_then
        if idx_else is not None:
            else_elem = children[idx_else]
            last_else = None
            for ch in list(else_elem):
                node = traverse_statement(ch)
                if node is None:
                    continue
                if else_start is None:
                    else_start = node
                if last_else is not None:
                    add_cfg_edge(last_else, node)
                last_else = node
            end_else = last_else
        # Connect condition to branch starts
        if then_start is not None:
            add_cfg_edge(cond_node, then_start, "True")
        if else_start is not None:
            add_cfg_edge(cond_node, else_start, "False")
        # Create merge node
        merge_node = add_cfg_node("EndIf")
        if end_then is not None:
            add_cfg_edge(end_then, merge_node)
        if end_else is not None:
            add_cfg_edge(end_else, merge_node)
        else:
            # No else: connect False directly to merge
            add_cfg_edge(cond_node, merge_node, "False")
        return merge_node
    if tag in ("case", "casez", "casex"):
        # Case statement
        expr_elem = elem.find("expr")
        expr_child = None
        if expr_elem is not None and len(list(expr_elem)) > 0:
            expr_child = list(expr_elem)[0]
        else:
            children = list(elem)
            if children and not (children[0].tag.startswith("case") or children[0].tag in ("caseitem", "item")):
                expr_child = children[0]
        case_label = tag
        if expr_child is not None:
            if expr_child.get("name"):
                case_label += f" ({expr_child.get('name')})"
            else:
                first_sub = list(expr_child)[0] if len(list(expr_child)) > 0 else None
                case_label += f" ({first_sub.get('name')})" if (first_sub is not None and first_sub.get("name")) else " (expr)"
        case_node = add_cfg_node(case_label)
        # Create merge node
        merge_label = "EndCase"
        if tag == "casez":
            merge_label = "EndCaseZ"
        elif tag == "casex":
            merge_label = "EndCaseX"
        merge_node = add_cfg_node(merge_label)
        # Traverse each case item
        for item in elem:
            if item.tag not in ("caseitem", "item"):
                continue
            # Determine edge label (case value or default)
            const_elems = [c for c in list(item) if c.tag == "const"]
            if const_elems:
                values = [c.get("name") for c in const_elems if c.get("name")]
                edge_label = ", ".join(values) if values else ""
            else:
                edge_label = "default"
            # Statements in this case branch (after any const values)
            branch_children = [c for c in list(item) if c.tag != "const"]
            branch_start = None
            last_branch = None
            for stmt in branch_children:
                node = traverse_statement(stmt)
                if node is None:
                    continue
                if branch_start is None:
                    branch_start = node
                if last_branch is not None:
                    add_cfg_edge(last_branch, node)
                last_branch = node
            if branch_start is not None:
                add_cfg_edge(case_node, branch_start, edge_label)
                add_cfg_edge(last_branch if last_branch else branch_start, merge_node)
            else:
                # Empty branch
                add_cfg_edge(case_node, merge_node, edge_label)
        return merge_node
    if tag in ("for", "while", "repeat"):
        # Loop
        cond_elem = elem.find("cond")
        loop_label = f"{tag} (...)"
        if cond_elem is not None and len(list(cond_elem)) > 0:
            cond_child = list(cond_elem)[0]
            if cond_child.get("name"):
                loop_label = f"{tag} ({cond_child.get('name')})"
        loop_node = add_cfg_node(loop_label)
        body_elem = elem.find("body")
        body_start = None
        last_body = None
        if body_elem is not None:
            for child in list(body_elem):
                node = traverse_statement(child)
                if node is None:
                    continue
                if body_start is None:
                    body_start = node
                if last_body is not None:
                    add_cfg_edge(last_body, node)
                last_body = node
        if body_start is not None:
            add_cfg_edge(loop_node, body_start, "True")
            if last_body is not None:
                add_cfg_edge(last_body, loop_node, "Next")
        loop_exit = add_cfg_node("LoopExit")
        add_cfg_edge(loop_node, loop_exit, "False")
        return loop_exit
    if tag in ("assign", "blockingAssign", "nonBlockingAssign", "continuousAssign", "contassign", "assigndly"):
        # Assignment (procedural or continuous)
        children = list(elem)
        if len(children) < 2:
            return None
        rhs_elem = children[0]
        lhs_elem = children[-1]
        # Determine LHS variable name
        lhs_name = lhs_elem.get("name")
        if not lhs_name:
            var_child = lhs_elem.find(".//*[@name]")
            lhs_name = var_child.get("name") if var_child is not None else "<unnamed>"
        if rhs_elem.tag == "cond":
            # Ternary expression on RHS
            cond_expr = list(rhs_elem)[0] if len(list(rhs_elem)) > 0 else None
            cond_label = "?:"
            if cond_expr is not None:
                if cond_expr.get("name"):
                    cond_label += f" ({cond_expr.get('name')})"
                else:
                    first_sub = list(cond_expr)[0] if len(list(cond_expr)) > 0 else None
                    cond_label += f" ({first_sub.get('name')})" if (first_sub is not None and first_sub.get("name")) else " (cond)"
            else:
                cond_label += " (cond)"
            cond_node = add_cfg_node(cond_label)
            true_expr = list(rhs_elem)[1] if len(list(rhs_elem)) > 1 else None
            false_expr = list(rhs_elem)[2] if len(list(rhs_elem)) > 2 else None
            # Create assignment nodes for each branch
            def expr_to_str(expr):
                if expr is None:
                    return "?"
                if expr.get("name"):
                    return expr.get("name")
                if expr.tag == "const" and expr.get("name"):
                    return expr.get("name")
                return "(expr)"
            true_label = f"{lhs_name} = {expr_to_str(true_expr)}"
            false_label = f"{lhs_name} = {expr_to_str(false_expr)}"
            true_node = add_cfg_node(true_label)
            false_node = add_cfg_node(false_label)
            add_cfg_edge(cond_node, true_node, "True")
            add_cfg_edge(cond_node, false_node, "False")
            end_node = add_cfg_node("EndIf")
            add_cfg_edge(true_node, end_node)
            add_cfg_edge(false_node, end_node)
            # DFG: add data dependencies for both branches
            dest_id = get_dfg_node(lhs_name)
            src_vars = []
            if true_expr is not None:
                src_vars += collect_var_names(true_expr)
            if false_expr is not None:
                src_vars += collect_var_names(false_expr)
            for var in set(src_vars):
                src_id = get_dfg_node(var)
                add_dfg_edge(src_id, dest_id)
            return end_node
        else:
            # Simple assignment
            rhs_str = None
            if rhs_elem.get("name"):
                rhs_str = rhs_elem.get("name")
            elif rhs_elem.tag == "const" and rhs_elem.get("name"):
                rhs_str = rhs_elem.get("name")
            else:
                var_in_rhs = rhs_elem.find(".//*[@name]")
                rhs_str = var_in_rhs.get("name") if var_in_rhs is not None else "..."
            assign_label = f"{lhs_name} = {rhs_str}"
            node_id = add_cfg_node(assign_label)
            dest_id = get_dfg_node(lhs_name)
            src_vars = set(collect_var_names(rhs_elem))
            for var in src_vars:
                src_id = get_dfg_node(var)
                add_dfg_edge(src_id, dest_id)
            return node_id
    if tag == "initial":
        last_node = None
        for child in list(elem):
            node = traverse_statement(child)
            if node is None:
                continue
            if last_node is not None:
                add_cfg_edge(last_node, node)
            last_node = node
        return last_node
    if tag == "always":
        last_node = None
        start_node = None
        for child in list(elem):
            if child.tag in ("sentree", "senitem"):
                continue  # skip sensitivity list details
            node = traverse_statement(child)
            if node is None:
                continue
            if start_node is None:
                start_node = node
            if last_node is not None:
                add_cfg_edge(last_node, node)
            last_node = node
        return start_node
    if tag == "generate":
        # Flatten generate block by traversing children
        last_node = None
        for child in list(elem):
            node = traverse_statement(child)
            if node is None:
                continue
            if last_node is not None:
                add_cfg_edge(last_node, node)
            last_node = node
        return last_node
    # Fallback: descend into any remaining wrapper/unknown tags
    last_node = None
    for child in list(elem):
        node = traverse_statement(child)
        if node is None:
            continue
        if last_node is not None:
            add_cfg_edge(last_node, node)
        last_node = node
    return last_node

def generate_dot(graph_name):
    """Generate Graphviz DOT format string for CFG or DFG graph."""
    lines = [f"digraph {graph_name} {{"]

    if graph_name == "CFG":
        nodes = cfg_nodes
        edges = cfg_edges
    else:
        nodes = dfg_nodes
        edges = dfg_edges

    # Output nodes with appropriate labels and shapes
    for i, label in enumerate(nodes):
        shape = ""
        # Decide shape based on node label
        if label.startswith("End") or label.startswith("LoopExit"):
            shape = "circle"
        elif "=" in label:
            shape = "box"
        elif (label.startswith("if") or label.startswith("case") or label.startswith("for") or 
              label.startswith("while") or label.startswith("repeat") or label.startswith("?:")):
            shape = "diamond"
        lbl = label.replace('"', '\\"')
        if shape:
            lines.append(f'    n{i} [label="{lbl}", shape={shape}];')
        else:
            lines.append(f'    n{i} [label="{lbl}"];')
    # Output edges
    if graph_name == "CFG":
        for src, dst, elabel in edges:
            if elabel:
                lbl = elabel.replace('"', '\\"')
                lines.append(f'    n{src} -> n{dst} [label="{lbl}"];')
            else:
                lines.append(f'    n{src} -> n{dst};')
    else:
        for src, dst in edges:
            lines.append(f'    n{src} -> n{dst};')
    lines.append("}")
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="Generate PDG (CFG and DFG) from Verilog using Verilator AST")
    parser.add_argument("verilog_file", help="Verilog source file")
    parser.add_argument("-t", "--top", dest="top_module", help="Top module name (if needed)")
    parser.add_argument("-o", "--output", dest="output_prefix", help="Output file name prefix (optional)")
    args = parser.parse_args()

    verilog_file = args.verilog_file
    top_module = args.top_module
    prefix = args.output_prefix
    if prefix is None:
        prefix = os.path.splitext(os.path.basename(verilog_file))[0]

    # Create temporary file for AST XML
    fd, ast_path = tempfile.mkstemp(suffix=".xml", prefix="ast_")
    os.close(fd)
    # Construct Verilator command
    cmd = ["verilator", "--xml-only", "--flatten", "--xml-output", ast_path, "-Wno-fatal"]
    if top_module:
        cmd += ["--top-module", top_module]
    cmd.append(verilog_file)
    try:
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False)
    except FileNotFoundError:
        sys.stderr.write("Error: Verilator executable not found. Ensure Verilator is installed and in PATH.\n")
        sys.exit(1)
    if result.returncode != 0:
        sys.stderr.write(f"Error: Verilator failed with exit code {result.returncode}\n")
        if result.stderr:
            sys.stderr.write(result.stderr.decode())
        sys.exit(1)
     # Parse the generated AST XML
    tree = ET.parse(ast_path)
    root = tree.getroot()
    os.remove(ast_path)  # cleanup

    # Find exactly the modules in the netlist
    netlist = root.find("netlist")
    modules = netlist.findall("module") if netlist is not None else []
    modules_count = len(modules)

    for module in modules:
        current_module = module.get("name", "")
        # hand the whole module to traverse_statement so it can recurse into topscope/begin/always/etc.
        traverse_statement(module)
        current_module = None

    # Write DOT files for CFG and DFG
    cfg_dot = generate_dot("CFG")
    dfg_dot = generate_dot("DFG")
    cfg_file = f"{prefix}_cfg.dot"
    dfg_file = f"{prefix}_dfg.dot"
    try:
        with open(cfg_file, "w") as f:
            f.write(cfg_dot)
        with open(dfg_file, "w") as f:
            f.write(dfg_dot)
    except Exception as e:
        sys.stderr.write(f"Error: Failed to write output files: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
