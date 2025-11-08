from .base_analyzer import BaseAnalyzer
from urllib.parse import urlparse

class URLAnalyzer(BaseAnalyzer):
    """Similarity based on URL structure"""
    
    def calculate_similarity(self, node1_data, node2_data):
        url1 = node1_data.get('url', '')
        url2 = node2_data.get('url', '')
        
        if not url1 or not url2:
            return 0.0
        
        parsed1 = urlparse(url1)
        parsed2 = urlparse(url2)
        
        # Same domain = high similarity
        if parsed1.netloc == parsed2.netloc:
            # Same path = very high similarity
            if parsed1.path == parsed2.path:
                return 0.9
            return 0.6
        
        return 0.0
