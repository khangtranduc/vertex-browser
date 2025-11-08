from abc import ABC, abstractmethod

class BaseAnalyzer(ABC):
    """Abstract base class for similarity analyzers"""
    
    @abstractmethod
    def calculate_similarity(self, node1_data, node2_data):
        """
        Calculate similarity between two nodes.
        
        Args:
            node1_data: Dictionary with node attributes (url, title, content, etc.)
            node2_data: Dictionary with node attributes
            
        Returns:
            float: Similarity score between 0 and 1
        """
        pass