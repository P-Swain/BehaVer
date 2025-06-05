import xml.etree.ElementTree as ET
import networkx as nx
import matplotlib.pyplot as plt

# Parse the Verilator XML (replace 'AST.xml' with your actual filename)
tree = ET.parse('../samples/exampleASTs/trafficLightAST.xml')
root = tree.getroot()

G = nx.DiGraph()

# 1) Handle blocking assignments (“<assign>”): LHS is the first direct <varref>;
#    any other <varref> in the subtree are RHS sources.
for assign in root.findall(".//assign"):
    # Find all direct-child <varref> elements
    direct_varrefs = assign.findall("varref")
    if not direct_varrefs:
        continue

    # The first direct <varref> is the LHS
    lhs_elem = direct_varrefs[0]
    lhs = lhs_elem.attrib["name"]

    # Collect every <varref> in the entire subtree, then skip the LHS element
    for varref in assign.findall(".//varref"):
        if varref is lhs_elem:
            continue
        rhs = varref.attrib["name"]
        if rhs != lhs:
            G.add_edge(rhs, lhs)

# 2) Handle non-blocking/sequential assignments (“<assigndly>”): 
#    LHS is the last direct <varref>; any other <varref> in the subtree are RHS.
for adly in root.findall(".//assigndly"):
    # Find all direct-child <varref> elements
    direct_varrefs = adly.findall("varref")
    if not direct_varrefs:
        continue

    # The last direct <varref> is the LHS
    lhs_elem = direct_varrefs[-1]
    lhs = lhs_elem.attrib["name"]

    # Collect every <varref> in the subtree, then skip the LHS element
    for varref in adly.findall(".//varref"):
        if varref is lhs_elem:
            continue
        rhs = varref.attrib["name"]
        if rhs != lhs:
            G.add_edge(rhs, lhs)

# 3) Draw the resulting dependency graph
plt.figure(figsize=(8, 6))
pos = nx.spring_layout(G, seed=42)  # fixed seed for reproducible layout
nx.draw(
    G,
    pos,
    with_labels=True,
    node_color="lightgreen",
    node_size=1000,
    font_size=10,
    edge_color="gray",
)
plt.title("Signal/Data-Dependency Graph from Verilator XML")
plt.show()
