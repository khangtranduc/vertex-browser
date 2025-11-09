"""
Multi-document summarization for browser tab clusters.

Uses a map-reduce approach with Claude to handle large numbers of documents:
1. Map: Summarize each document individually
2. Reduce: Hierarchically combine summaries
3. Extract: Generate a concise topic-based title
"""

import time
from typing import List, Dict, Optional
from anthropic import Anthropic


class ClusterSummary:
    """Represents a summarized cluster of documents"""

    def __init__(self, title: str, summary: str, doc_count: int, urls: List[str]):
        self.title = title
        self.summary = summary  # 2-3 sentence paragraph
        self.doc_count = doc_count
        self.urls = urls

    def __repr__(self):
        return f"ClusterSummary(title='{self.title}', docs={self.doc_count})"

    def __str__(self):
        return f"{self.title}: {self.summary}"


class ClusterSummarizer:
    """Handles multi-document summarization using map-reduce approach"""

    def __init__(self, anthropic_client: Anthropic):
        self.client = anthropic_client
        self.max_content_chars = 3000  # Max chars per doc to send
        self.batch_size = 5  # Number of summaries to combine at once
        self.max_retries = 3
        self.retry_delay = 1.0  # seconds

    def summarize_cluster(self, documents: List[Dict[str, str]]) -> ClusterSummary:
        """
        Summarize a cluster of documents.

        Args:
            documents: List of dicts with 'url', 'content', 'title' keys

        Returns:
            ClusterSummary object with title and paragraph-length summary
        """
        if not documents:
            return ClusterSummary("Empty Cluster", "No documents in this cluster.", 0, [])

        urls = [doc['url'] for doc in documents]

        # Map phase: Summarize each document
        print(f"📝 Summarizing {len(documents)} documents...")
        individual_summaries = self._map_phase(documents)

        # Reduce phase: Hierarchically combine summaries
        print(f"🔄 Combining summaries...")
        final_summary = self._reduce_phase(individual_summaries)

        # Generate title
        print(f"🏷️  Generating title...")
        title = self._extract_title(final_summary, documents)

        return ClusterSummary(
            title=title,
            summary=final_summary,
            doc_count=len(documents),
            urls=urls
        )

    def _map_phase(self, documents: List[Dict[str, str]]) -> List[str]:
        """Summarize each document individually"""
        summaries = []

        for i, doc in enumerate(documents):
            print(f"  [{i+1}/{len(documents)}] Summarizing: {doc['title'][:40]}...")

            # Truncate content if too long
            content = doc['content'][:self.max_content_chars]

            prompt = f"""Summarize this web page in one concise sentence. Focus on the main topic or purpose.

URL: {doc['url']}
Title: {doc['title']}
Content: {content}

Respond with ONLY one sentence summarizing the main topic."""

            summary = self._call_claude_with_retry(prompt, max_tokens=100)
            summaries.append(summary)

        return summaries

    def _reduce_phase(self, summaries: List[str]) -> str:
        """Hierarchically combine summaries into one final sentence"""

        # If only one summary, return it
        if len(summaries) == 1:
            return summaries[0]

        # Iteratively combine summaries in batches
        current_summaries = summaries[:]

        while len(current_summaries) > 1:
            next_level = []

            # Process in batches
            for i in range(0, len(current_summaries), self.batch_size):
                batch = current_summaries[i:i + self.batch_size]

                if len(batch) == 1:
                    next_level.append(batch[0])
                else:
                    combined = self._combine_summaries(batch)
                    next_level.append(combined)

            current_summaries = next_level

        return current_summaries[0]

    def _combine_summaries(self, summaries: List[str]) -> str:
        """Combine a batch of summaries into one"""
        summaries_text = "\n".join(f"- {s}" for s in summaries)

        prompt = f"""These are summaries of related web pages. Combine them into a brief paragraph (2-3 sentences) that captures the common theme or topic.

Summaries:
{summaries_text}

Respond with a 2-3 sentence paragraph describing the overall theme."""

        return self._call_claude_with_retry(prompt, max_tokens=150)

    def _extract_title(self, final_summary: str, documents: List[Dict[str, str]]) -> str:
        """Generate a concise topic-based title"""

        # Get a sample of URLs for context
        sample_urls = [doc['url'] for doc in documents[:5]]
        urls_text = "\n".join(sample_urls)

        prompt = f"""Based on this summary and sample URLs, create a short title (2-4 words) for this cluster of web pages.

Summary: {final_summary}

Sample URLs:
{urls_text}

The title should be:
- Topic-based (e.g., "Python Programming", "Machine Learning")
- Or descriptive of content type (e.g., "News Articles", "Documentation")
- Concise (2-4 words maximum)

Respond with ONLY the title, nothing else."""

        title = self._call_claude_with_retry(prompt, max_tokens=20)

        # Clean up title (remove quotes, periods, etc.)
        title = title.strip().strip('"\'.,')

        return title

    def _call_claude_with_retry(self, prompt: str, max_tokens: int = 100) -> str:
        """Call Claude API with retry logic"""

        for attempt in range(self.max_retries):
            try:
                message = self.client.messages.create(
                    model="claude-3-5-haiku-20241022",  # Fast and cheap
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}]
                )

                return message.content[0].text.strip()

            except Exception as e:
                if attempt < self.max_retries - 1:
                    print(f"  ⚠ API error (attempt {attempt+1}/{self.max_retries}): {e}")
                    time.sleep(self.retry_delay)
                else:
                    print(f"  ❌ API failed after {self.max_retries} attempts: {e}")
                    raise

        return ""


# Example usage
if __name__ == "__main__":
    import os

    # Initialize
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set")
        exit(1)

    client = Anthropic(api_key=api_key)
    summarizer = ClusterSummarizer(client)

    # Example documents
    documents = [
        {
            'url': 'https://docs.python.org/3/tutorial/',
            'title': 'Python Tutorial',
            'content': 'This tutorial introduces the reader informally to the basic concepts and features of the Python language...'
        },
        {
            'url': 'https://realpython.com/python-basics/',
            'title': 'Python Basics',
            'content': 'Learn the basics of Python programming language including variables, data types, functions...'
        },
        {
            'url': 'https://www.learnpython.org/',
            'title': 'Learn Python',
            'content': 'Interactive Python tutorial for beginners. Learn Python programming with examples...'
        }
    ]

    # Summarize
    summary = summarizer.summarize_cluster(documents)

    print("\n" + "="*50)
    print(f"Title: {summary.title}")
    print(f"Summary: {summary.summary}")
    print(f"Documents: {summary.doc_count}")
    print("="*50)
