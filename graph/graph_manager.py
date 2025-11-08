import networkx as nx
from PyQt5.QtCore import QObject, pyqtSignal

class GraphManager(QObject):
    """Manages the graph structure of browser tabs"""
    
    graph_changed = pyqtSignal()  # Emitted when graph structure changes
    
    def __init__(self):
        super().__init__()
        self.graph = nx.Graph()
        self.node_counter = 0
        self.analyzers = []  # List of similarity analyzer functions
        self.edge_threshold = 0.3  # Minimum similarity to create edge
        
    def add_node(self, tab, url, title):
        """Add a new node to the graph"""
        node_id = f"node_{self.node_counter}"
        self.node_counter += 1
        
        self.graph.add_node(node_id, 
                           tab=tab,
                           url=url, 
                           title=title,
                           content="")  # Will be populated later
        
        # Update edges with existing nodes
        self._update_edges_for_node(node_id)
        
        self.graph_changed.emit()
        return node_id
    
    def remove_node(self, node_id):
        """Remove a node from the graph"""
        if node_id in self.graph:
            self.graph.remove_node(node_id)
            self.graph_changed.emit()
    
    def update_node(self, node_id, **kwargs):
        """Update node attributes"""
        if node_id in self.graph:
            for key, value in kwargs.items():
                self.graph.nodes[node_id][key] = value
            
            # Recalculate edges if content changed
            if 'content' in kwargs or 'url' in kwargs:
                self._update_edges_for_node(node_id)
            
            self.graph_changed.emit()
    
    def add_analyzer(self, analyzer_func):
        """
        Add a similarity analyzer function.
        
        Args:
            analyzer_func: Function that takes (node1_data, node2_data) 
                          and returns similarity score (0-1)
        """
        self.analyzers.append(analyzer_func)
        self.update_all_edges()
    
    def set_edge_threshold(self, threshold):
        """Set minimum similarity threshold for creating edges"""
        self.edge_threshold = threshold
        self.update_all_edges()
    
    def _calculate_similarity(self, node1_id, node2_id):
        """Calculate similarity between two nodes using all analyzers"""
        if not self.analyzers:
            return 0.0
        
        node1_data = self.graph.nodes[node1_id]
        node2_data = self.graph.nodes[node2_id]
        
        # Average similarity across all analyzers
        scores = []
        for analyzer in self.analyzers:
            try:
                score = analyzer(node1_data, node2_data)
                scores.append(score)
            except Exception as e:
                print(f"Analyzer error: {e}")
        
        return sum(scores) / len(scores) if scores else 0.0
    
    def _update_edges_for_node(self, node_id):
        """Update edges for a specific node"""
        if node_id not in self.graph:
            return
        
        # Remove existing edges for this node
        edges_to_remove = list(self.graph.edges(node_id))
        self.graph.remove_edges_from(edges_to_remove)
        
        # Calculate similarity with all other nodes
        for other_id in self.graph.nodes():
            if other_id == node_id:
                continue
            
            similarity = self._calculate_similarity(node_id, other_id)
            
            if similarity >= self.edge_threshold:
                self.graph.add_edge(node_id, other_id, weight=similarity)
    
    def update_all_edges(self):
        """Recalculate all edges in the graph"""
        # Clear all edges
        self.graph.remove_edges_from(list(self.graph.edges()))
        
        # Recalculate
        nodes = list(self.graph.nodes())
        for i, node1 in enumerate(nodes):
            for node2 in nodes[i+1:]:
                similarity = self._calculate_similarity(node1, node2)
                
                if similarity >= self.edge_threshold:
                    self.graph.add_edge(node1, node2, weight=similarity)
        
        self.graph_changed.emit()
    
    def get_graph(self):
        """Get the NetworkX graph object"""
        return self.graph
    
    def get_node_data(self, node_id):
        """Get data for a specific node"""
        return self.graph.nodes[node_id] if node_id in self.graph else None