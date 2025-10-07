# File: graph_model.py

class Graph:
    """A class to store and manage CFG and DFG data, avoiding global state."""
    def __init__(self):
        # SSA State
        self.ssacounter = {}
        self.latestversion = {}

        # Cluster State
        self.clusters = []
        self.cluster_stack = []

        # CFG Data
        self.cfg_nodes = []
        self.cfg_edges = []
        self.cfg_node_defs = {}
        self.cfg_node_uses = {}
        self.cfg_node_to_line_num = {}
        self.node_to_cluster = {}
        self.node_to_sourcetext = {}

        # DFG Data
        self.dfg_nodes = []
        self.dfg_edges = []
        self.dfg_node_map = {}

    def reset_ssa_state(self):
        """Resets SSA counters for a new module."""
        self.ssacounter = {}
        self.latestversion = {}

    def get_ssa_name(self, var):
        """Generates a new SSA name for a variable."""
        count = self.ssacounter.get(var, 0) + 1
        self.ssacounter[var] = count
        ssa_name = f"{var}_{count}"
        self.latestversion[var] = ssa_name
        return ssa_name

    def get_latest_version(self, var):
        """Returns the current latest SSA version of a variable."""
        return self.latestversion.get(var, var)

    def add_cluster(self, name, color="lightgrey"):
        """Adds a new cluster (subgraph) to the graph."""
        idx = len(self.clusters)
        self.clusters.append({"name": name, "color": color, "node_ids": []})
        return idx

    def add_cfg_node(self, label, cluster_id=None):
        """Adds a new node to the CFG."""
        node_id = len(self.cfg_nodes)
        self.cfg_nodes.append(label)
        if cluster_id is not None:
            self.clusters[cluster_id]["node_ids"].append(node_id)
            self.node_to_cluster[node_id] = cluster_id
        return node_id

    def add_cfg_edge(self, src, dst, label=""):
        """Adds an edge to the CFG."""
        self.cfg_edges.append((src, dst, label))

    def add_dfg_edge(self, src_dfg_id, dst_dfg_id):
        """Adds an edge to the DFG."""
        if (src_dfg_id, dst_dfg_id) not in self.dfg_edges:
            self.dfg_edges.append((src_dfg_id, dst_dfg_id))

    def get_dfg_node_id(self, ssa_name):
        """Gets or creates a DFG node ID for a given SSA name."""
        if ssa_name in self.dfg_node_map:
            return self.dfg_node_map[ssa_name]
        node_id = len(self.dfg_nodes)
        self.dfg_nodes.append(ssa_name)
        self.dfg_node_map[ssa_name] = node_id
        return node_id