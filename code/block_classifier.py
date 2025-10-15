# File: block_classifier.py
import xml.etree.ElementTree as ET

def is_sequential(elem: ET.Element) -> bool:
    """Checks if an always block is sequential (clocked)."""
    sentree = elem.find('sentree')
    if sentree is None: return False
    return any(item.get('type') == 'posedge' or item.get('type') == 'negedge' for item in sentree.findall('senitem'))

def classify_block(elem: ET.Element) -> str:
    """
    Classifies an always block based on heuristics.
    Returns a string label like 'FSM', 'Datapath', etc.
    """
    if elem.tag.lower() not in ('always', 'initial'):
        return "Unknown"

    # Heuristic 1: FSM Detection
    # FSMs are sequential, have a case statement, and the case variable
    # is often a state register that gets updated.
    if is_sequential(elem):
        case_stmt = elem.find('.//casestmt')
        if case_stmt is not None:
            # A strong indicator of an FSM.
            return "FSM Controller"

    # Heuristic 2: Counter Detection
    if is_sequential(elem):
        for assign in elem.findall('.//nonblockingassign'):
            lhs = assign.find('.//varref')
            rhs_add = assign.find('.//add')
            if lhs is not None and rhs_add is not None:
                lhs_name = lhs.get('name')
                # Check for `count <= count + 1` pattern
                if any(v.get('name') == lhs_name for v in rhs_add.findall('.//varref')):
                    return "Counter"

    # Heuristic 3: Datapath/ALU Detection
    if not is_sequential(elem): # Combinational logic
        case_stmt = elem.find('.//casestmt')
        op_count = len(elem.findall('.//add')) + len(elem.findall('.//sub')) + \
                   len(elem.findall('.//mul')) + len(elem.findall('.//and')) + \
                   len(elem.findall('.//or')) + len(elem.findall('.//xor'))
        # Combinational block with a case statement or many operations is likely a datapath
        if case_stmt is not None or op_count > 3:
            return "Combinational Datapath"

    # Fallback Classification
    if is_sequential(elem):
        return "Sequential Logic"
    else:
        return "Combinational Logic"
