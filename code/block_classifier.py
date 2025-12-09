# File: block_classifier.py
import xml.etree.ElementTree as ET

def is_sequential(elem: ET.Element) -> bool:
    """Checks if an always block is sequential (clocked)."""
    sentree = elem.find('sentree')
    if sentree is None: return False
    
    # Check for explicit edge triggers
    if any(item.get('type') in ('posedge', 'negedge') for item in sentree.findall('senitem')):
        return True

    # Fallback: Check for common clock names in the sensitivity list
    # This helps if Verilator's XML output simplifies the edge type
    for item in sentree.findall('senitem'):
        varref = item.find('varref')
        if varref is not None:
            name = varref.get('name', '').lower()
            if 'clk' in name or 'clock' in name or 'reset' in name or 'rst' in name:
                return True
                
    return False

def classify_block(elem: ET.Element) -> str:
    """
    Classifies an always block based on heuristics.
    Returns a string label like 'FSM', 'Datapath', etc.
    """
    tag = elem.tag.lower()
    
    # Explicitly label continuous assignments
    if tag in ('assign', 'contassign'):
        return "Continuous Assignment"

    if tag not in ('always', 'initial', 'always_comb', 'always_ff'):
        return f"Block: {tag}"

    # Heuristic 1: FSM Detection
    if is_sequential(elem):
        case_stmt = elem.find('.//casestmt')
        if case_stmt is not None:
            return "FSM Controller"

    # Heuristic 2: Counter Detection
    if is_sequential(elem):
        for assign in elem.findall('.//nonblockingassign'):
            lhs = assign.find('.//varref')
            rhs_add = assign.find('.//add')
            if lhs is not None and rhs_add is not None:
                lhs_name = lhs.get('name')
                if any(v.get('name') == lhs_name for v in rhs_add.findall('.//varref')):
                    return "Counter"

    # Heuristic 3: Datapath/ALU Detection
    if not is_sequential(elem): 
        case_stmt = elem.find('.//casestmt')
        op_count = len(elem.findall('.//add')) + len(elem.findall('.//sub')) + \
                   len(elem.findall('.//mul')) + len(elem.findall('.//and')) + \
                   len(elem.findall('.//or')) + len(elem.findall('.//xor'))
        if case_stmt is not None or op_count > 3:
            return "Combinational Datapath"

    # Fallback Classification
    if is_sequential(elem):
        return "Sequential Logic"
    else:
        return "Combinational Logic"