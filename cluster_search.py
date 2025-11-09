"""
Search and ranking functionality for cluster summaries.

Provides flexible search across cluster titles, summaries, tags, and URLs
with configurable weighting and ranking algorithms.
"""

from typing import List, Dict, Optional, Tuple
from cluster_summarizer import ClusterSummary
import re


class SearchResult:
    """Represents a search result with ranking information"""

    def __init__(self, cluster: ClusterSummary, score: float, match_details: Dict[str, any]):
        self.cluster = cluster
        self.score = score  # Higher score = better match
        self.match_details = match_details  # Details about what matched

    def __repr__(self):
        return f"SearchResult(title='{self.cluster.title}', score={self.score:.3f})"

    def __str__(self):
        return f"{self.cluster.title} (score: {self.score:.3f})"


class ClusterSearcher:
    """Handles searching and ranking of cluster summaries"""

    def __init__(
        self,
        title_weight: float = 3.0,
        tag_weight: float = 2.5,
        summary_weight: float = 1.5,
        url_weight: float = 1.0,
        case_sensitive: bool = False
    ):
        """
        Initialize the cluster searcher with configurable weights.

        Args:
            title_weight: Weight for matches in cluster title (default: 3.0)
            tag_weight: Weight for matches in tags (default: 2.5)
            summary_weight: Weight for matches in summary text (default: 1.5)
            url_weight: Weight for matches in URLs (default: 1.0)
            case_sensitive: Whether search should be case-sensitive (default: False)
        """
        self.title_weight = title_weight
        self.tag_weight = tag_weight
        self.summary_weight = summary_weight
        self.url_weight = url_weight
        self.case_sensitive = case_sensitive

    def search(
        self,
        clusters: List[ClusterSummary],
        query: str,
        min_score: float = 0.0,
        max_results: Optional[int] = None
    ) -> List[SearchResult]:
        """
        Search clusters and return ranked results.

        Args:
            clusters: List of ClusterSummary objects to search
            query: Search query string
            min_score: Minimum score threshold (default: 0.0)
            max_results: Maximum number of results to return (default: None = all)

        Returns:
            List of SearchResult objects, sorted by score (highest first)
        """
        if not query or not clusters:
            return []

        # Prepare query
        search_query = query if self.case_sensitive else query.lower()
        query_terms = self._tokenize(search_query)

        # Score each cluster
        results = []
        for cluster in clusters:
            score, details = self._score_cluster(cluster, search_query, query_terms)

            if score >= min_score:
                results.append(SearchResult(cluster, score, details))

        # Sort by score (descending)
        results.sort(key=lambda r: r.score, reverse=True)

        # Limit results if requested
        if max_results is not None:
            results = results[:max_results]

        return results

    def _score_cluster(
        self,
        cluster: ClusterSummary,
        query: str,
        query_terms: List[str]
    ) -> Tuple[float, Dict[str, any]]:
        """
        Calculate relevance score for a cluster.

        Returns:
            Tuple of (score, match_details)
        """
        total_score = 0.0
        details = {
            'title_matches': 0,
            'tag_matches': 0,
            'summary_matches': 0,
            'url_matches': 0,
            'exact_matches': 0,
            'partial_matches': 0
        }

        # Prepare cluster text
        title = cluster.title if self.case_sensitive else cluster.title.lower()
        summary = cluster.summary if self.case_sensitive else cluster.summary.lower()
        tags = [tag if self.case_sensitive else tag.lower() for tag in cluster.tags]
        urls = [url if self.case_sensitive else url.lower() for url in cluster.urls]

        # 1. Title matching
        title_score, title_exact, title_partial = self._match_text(title, query, query_terms)
        total_score += title_score * self.title_weight
        details['title_matches'] = title_exact + title_partial
        details['exact_matches'] += title_exact
        details['partial_matches'] += title_partial

        # 2. Tag matching (exact and partial matches in tags)
        tag_score = 0.0
        for tag in tags:
            # Exact tag match gets bonus
            if query == tag:
                tag_score += 2.0
                details['tag_matches'] += 1
                details['exact_matches'] += 1
            # Query term appears in tag
            elif query in tag:
                tag_score += 1.5
                details['tag_matches'] += 1
                details['partial_matches'] += 1
            else:
                # Partial term matches
                for term in query_terms:
                    if term in tag:
                        tag_score += 0.5
                        details['tag_matches'] += 1
                        details['partial_matches'] += 1
        total_score += tag_score * self.tag_weight

        # 3. Summary matching
        summary_score, summary_exact, summary_partial = self._match_text(summary, query, query_terms)
        total_score += summary_score * self.summary_weight
        details['summary_matches'] = summary_exact + summary_partial
        details['exact_matches'] += summary_exact
        details['partial_matches'] += summary_partial

        # 4. URL matching
        url_score = 0.0
        for url in urls:
            url_match_score, url_exact, url_partial = self._match_text(url, query, query_terms)
            url_score += url_match_score
            details['url_matches'] += url_exact + url_partial
            details['exact_matches'] += url_exact
            details['partial_matches'] += url_partial
        # Average URL score (don't over-weight clusters with many URLs)
        if urls:
            url_score = url_score / len(urls)
        total_score += url_score * self.url_weight

        return total_score, details

    def _match_text(
        self,
        text: str,
        query: str,
        query_terms: List[str]
    ) -> Tuple[float, int, int]:
        """
        Calculate match score for a text field.

        Returns:
            Tuple of (score, exact_matches, partial_matches)
        """
        score = 0.0
        exact_matches = 0
        partial_matches = 0

        # Exact phrase match
        if query in text:
            # Count occurrences
            count = text.count(query)
            score += count * 2.0  # 2 points per exact match
            exact_matches += count

        # Individual term matches
        for term in query_terms:
            if term in text:
                count = text.count(term)
                score += count * 0.5  # 0.5 points per term match
                partial_matches += count

        return score, exact_matches, partial_matches

    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into search terms.

        Splits on whitespace and removes short tokens.
        """
        # Split on whitespace and punctuation
        tokens = re.findall(r'\w+', text)

        # Filter out very short tokens (single characters)
        tokens = [t for t in tokens if len(t) > 1]

        return tokens

    def search_with_filters(
        self,
        clusters: List[ClusterSummary],
        query: str,
        required_tags: Optional[List[str]] = None,
        excluded_tags: Optional[List[str]] = None,
        min_doc_count: Optional[int] = None,
        max_doc_count: Optional[int] = None,
        min_score: float = 0.0,
        max_results: Optional[int] = None
    ) -> List[SearchResult]:
        """
        Search with additional filtering options.

        Args:
            clusters: List of ClusterSummary objects to search
            query: Search query string
            required_tags: Tags that must be present (default: None)
            excluded_tags: Tags that must not be present (default: None)
            min_doc_count: Minimum number of documents in cluster (default: None)
            max_doc_count: Maximum number of documents in cluster (default: None)
            min_score: Minimum score threshold (default: 0.0)
            max_results: Maximum number of results to return (default: None)

        Returns:
            List of SearchResult objects, sorted by score (highest first)
        """
        # Pre-filter clusters based on criteria
        filtered_clusters = []

        for cluster in clusters:
            # Check document count
            if min_doc_count is not None and cluster.doc_count < min_doc_count:
                continue
            if max_doc_count is not None and cluster.doc_count > max_doc_count:
                continue

            # Check required tags
            if required_tags:
                cluster_tags_lower = [tag.lower() for tag in cluster.tags]
                required_tags_lower = [tag.lower() for tag in required_tags]
                if not all(req_tag in cluster_tags_lower for req_tag in required_tags_lower):
                    continue

            # Check excluded tags
            if excluded_tags:
                cluster_tags_lower = [tag.lower() for tag in cluster.tags]
                excluded_tags_lower = [tag.lower() for tag in excluded_tags]
                if any(exc_tag in cluster_tags_lower for exc_tag in excluded_tags_lower):
                    continue

            filtered_clusters.append(cluster)

        # Perform search on filtered clusters
        return self.search(filtered_clusters, query, min_score, max_results)


# Example usage
if __name__ == "__main__":
    from cluster_summarizer import ClusterSummary

    # Create example clusters
    clusters = [
        ClusterSummary(
            title="Python Programming",
            summary="A collection of Python tutorials covering basic syntax, data structures, and object-oriented programming concepts for beginners.",
            doc_count=5,
            urls=[
                "https://docs.python.org/3/tutorial/",
                "https://realpython.com/python-basics/",
                "https://www.learnpython.org/"
            ],
            tags=["python", "tutorial", "programming", "beginner"]
        ),
        ClusterSummary(
            title="Machine Learning",
            summary="Research papers and tutorials on neural networks, deep learning frameworks, and practical applications of machine learning in Python.",
            doc_count=8,
            urls=[
                "https://pytorch.org/tutorials/",
                "https://tensorflow.org/tutorials",
                "https://scikit-learn.org/stable/tutorial/"
            ],
            tags=["machine learning", "AI", "python", "neural networks", "deep learning"]
        ),
        ClusterSummary(
            title="Web Development",
            summary="Modern web development guides covering JavaScript frameworks, responsive design, and full-stack development practices.",
            doc_count=12,
            urls=[
                "https://developer.mozilla.org/en-US/docs/Learn",
                "https://reactjs.org/tutorial/",
                "https://nodejs.org/en/docs/guides/"
            ],
            tags=["web development", "javascript", "frontend", "backend", "tutorial"]
        ),
        ClusterSummary(
            title="Data Science",
            summary="Comprehensive resources on data analysis, visualization, and statistical methods using Python libraries like pandas and matplotlib.",
            doc_count=6,
            urls=[
                "https://pandas.pydata.org/docs/getting_started/tutorials.html",
                "https://matplotlib.org/stable/tutorials/index.html"
            ],
            tags=["data science", "python", "analytics", "visualization"]
        )
    ]

    # Create searcher
    searcher = ClusterSearcher()

    # Example 1: Basic search
    print("\n" + "="*60)
    print("Example 1: Search for 'python'")
    print("="*60)
    results = searcher.search(clusters, "python", min_score=0.5)
    for i, result in enumerate(results, 1):
        print(f"\n{i}. {result.cluster.title} (Score: {result.score:.3f})")
        print(f"   Summary: {result.cluster.summary[:80]}...")
        print(f"   Tags: {', '.join(result.cluster.tags)}")
        print(f"   Matches: {result.match_details}")

    # Example 2: Search with filters
    print("\n" + "="*60)
    print("Example 2: Search for 'tutorial' with 'python' tag required")
    print("="*60)
    results = searcher.search_with_filters(
        clusters,
        "tutorial",
        required_tags=["python"],
        min_score=0.5
    )
    for i, result in enumerate(results, 1):
        print(f"\n{i}. {result.cluster.title} (Score: {result.score:.3f})")
        print(f"   Tags: {', '.join(result.cluster.tags)}")

    # Example 3: Phrase search
    print("\n" + "="*60)
    print("Example 3: Search for 'machine learning'")
    print("="*60)
    results = searcher.search(clusters, "machine learning", max_results=3)
    for i, result in enumerate(results, 1):
        print(f"\n{i}. {result.cluster.title} (Score: {result.score:.3f})")
        print(f"   Exact matches: {result.match_details['exact_matches']}")
        print(f"   Partial matches: {result.match_details['partial_matches']}")

    # Example 4: Custom weights (prioritize tags)
    print("\n" + "="*60)
    print("Example 4: Tag-focused search (higher tag weight)")
    print("="*60)
    tag_focused_searcher = ClusterSearcher(
        title_weight=2.0,
        tag_weight=5.0,  # Much higher weight on tags
        summary_weight=1.0,
        url_weight=0.5
    )
    results = tag_focused_searcher.search(clusters, "python")
    for i, result in enumerate(results, 1):
        print(f"{i}. {result.cluster.title} (Score: {result.score:.3f}) - Tags: {', '.join(result.cluster.tags)}")
