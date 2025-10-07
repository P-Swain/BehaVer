# File: ast_utils.py

import xml.etree.ElementTree as ET

def expr_to_str(elem: ET.Element) -> str:
    """Recursively reconstructs a simple Verilog expression from an AST node."""
    if elem is None:
        return ""
    tag = elem.tag.lower()

    # Leaf nodes
    if tag == "varref":
        return elem.get("name", "")
    if tag == "const":
        return elem.get("name", "")

    # Binary comparison ops
    cmp_ops = {"lts": "<", "gt": ">", "eq": "==", "neq": "!=", "lte": "<=", "gte": ">="}
    if tag in cmp_ops:
        kids = list(elem)
        if len(kids) >= 2:
            left = expr_to_str(kids[0])
            right = expr_to_str(kids[1])
            return f"({left} {cmp_ops[tag]} {right})"

    # Logical AND/OR
    if tag in ("land", "lor"):
        op = "&&" if tag == "land" else "||"
        return f"({op.join(expr_to_str(c) for c in elem)})"

    # Arithmetic operations
    arith_ops = {
        "add": "+", "sub": "-", "mul": "*", "div": "/", "mod": "%",
        "shl": "<<", "shr": ">>", "ashr": ">>>"
    }
    if tag in arith_ops:
        kids = list(elem)
        if len(kids) >= 2:
            left = expr_to_str(kids[0])
            right = expr_to_str(kids[1])
            return f"({left} {arith_ops[tag]} {right})"

    # Unary operations
    if tag == "neg":
        return f"-({expr_to_str(list(elem)[0])})" if elem else ""
    if tag == "not":  # Bitwise NOT
        return f"~({expr_to_str(list(elem)[0])})" if elem else ""
    if tag == "lnot":  # Logical NOT
        return f"!({expr_to_str(list(elem)[0])})" if elem else ""

    # Ternary
    if tag == "cond":
        kids = list(elem)
        if len(kids) >= 3:
            return f"{expr_to_str(kids[0])} ? {expr_to_str(kids[1])} : {expr_to_str(kids[2])}"

    # Fallback: concat children
    return "".join(expr_to_str(c) for c in elem)

def collect_var_names(expr_elem: ET.Element) -> list[str]:
    """Collects all unique variable names (non-SSA) from an expression AST."""
    names = set()
    if expr_elem is None:
        return []
    for v in expr_elem.findall('.//varref'):
        if v.get('name'):
            names.add(v.get('name'))
    tag = expr_elem.tag.lower()
    if tag in ('varref', 'var', 'signal') and expr_elem.get('name'):
        names.add(expr_elem.get('name'))
    return list(names)