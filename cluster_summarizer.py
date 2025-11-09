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

    def __init__(self, title: str, summary: str, doc_count: int, urls: List[str], tags: Optional[List[str]] = None):
        self.title = title
        self.summary = summary  # 2-3 sentence paragraph
        self.doc_count = doc_count
        self.urls = urls
        self.tags = tags if tags is not None else []  # Backwards compatible - defaults to empty list

    def __repr__(self):
        tag_str = f", tags={len(self.tags)}" if self.tags else ""
        return f"ClusterSummary(title='{self.title}', docs={self.doc_count}{tag_str})"

    def __str__(self):
        tag_str = f" [{', '.join(self.tags)}]" if self.tags else ""
        return f"{self.title}{tag_str}: {self.summary}"


class ClusterSummarizer:
    """Handles multi-document summarization using map-reduce approach"""

    def __init__(self, anthropic_client: Anthropic, enable_tags: bool = False):
        self.client = anthropic_client
        self.max_content_chars = 3000  # Max chars per doc to send
        self.batch_size = 5  # Number of summaries to combine at once
        self.max_retries = 3
        self.retry_delay = 1.0  # seconds
        self.enable_tags = enable_tags  # Backwards compatible - tags disabled by default

    def summarize_cluster(self, documents: List[Dict[str, str]]) -> ClusterSummary:
        """
        Summarize a cluster of documents.

        Args:
            documents: List of dicts with 'url', 'content', 'title' keys

        Returns:
            ClusterSummary object with title and paragraph-length summary (and tags if enabled)
        """
        if not documents:
            return ClusterSummary("Empty Cluster", "No documents in this cluster.", 0, [], [])

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

        # Extract tags if enabled
        tags = []
        if self.enable_tags:
            print(f"🏷️  Extracting tags...")
            tags = self._extract_tags(final_summary, documents)

        return ClusterSummary(
            title=title,
            summary=final_summary,
            doc_count=len(documents),
            urls=urls,
            tags=tags
        )

    def _map_phase(self, documents: List[Dict[str, str]]) -> List[str]:
        """Summarize each document individually"""
        summaries = []

        for i, doc in enumerate(documents):
            print(f"  [{i+1}/{len(documents)}] Summarizing: {doc['title'][:40]}...")

            # Truncate content if too long
            content = doc['content'][:self.max_content_chars]

            # Skip if content is empty or too short
            if not content or len(content.strip()) < 20:
                print(f"    ⚠ Skipping - insufficient content")
                summaries.append(f"Page about {doc['title']}")
                continue

            prompt = f"""Summarize this web page in one clear, complete sentence that describes what the page is about.

URL: {doc['url']}
Title: {doc['title']}
Content: {content}

Write a natural sentence describing the page's main topic or purpose. Do not write placeholder text or error messages.

Example format: "This page covers [topic] and explains [key points]."

Your summary:"""

            summary = self._call_claude_with_retry(prompt, max_tokens=100)

            # Validate summary - check for placeholder/error patterns
            summary_lower = summary.lower()
            if any(phrase in summary_lower for phrase in ['placeholder', 'error', 'cannot', 'unable to', 'i apologize', 'i cannot']):
                print(f"    ⚠ Got placeholder/error response, using fallback")
                summary = f"Web page about {doc['title']}"

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

        prompt = f"""These are summaries of related web pages. Combine them into a brief paragraph (2-3 sentences) that describes what this collection of pages covers.

Summaries:
{summaries_text}

Write a cohesive summary that:
- Describes the main topic and themes across all pages
- Sounds natural to a user browsing their tabs
- Avoids meta-references like "these summaries" or "the documents"

Respond with a 2-3 sentence paragraph describing the overall content."""

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

    def _extract_tags(self, final_summary: str, documents: List[Dict[str, str]]) -> List[str]:
        """Extract relevant tags/keywords for the cluster"""

        # Get a sample of titles and URLs for context
        sample_titles = [doc['title'] for doc in documents[:5]]
        sample_urls = [doc['url'] for doc in documents[:5]]

        titles_text = "\n".join(f"- {title}" for title in sample_titles)
        urls_text = "\n".join(f"- {url}" for url in sample_urls)

        prompt = f"""Based on this summary and sample documents, extract 3-7 relevant tags/keywords that categorize this cluster of web pages.

Summary: {final_summary}

Sample Titles:
{titles_text}

Sample URLs:
{urls_text}

Tags should be:
- Single words or short phrases (1-3 words max each)
- Descriptive of the topic, domain, or content type
- Useful for categorization and filtering
- Examples: "python", "machine learning", "tutorial", "documentation", "news", "AI research", "web development"

Respond with ONLY the tags separated by commas (e.g., "python, tutorial, programming, beginner-friendly")."""

        response = self._call_claude_with_retry(prompt, max_tokens=50)

        # Parse tags from comma-separated response
        tags = [tag.strip().strip('"\'.,') for tag in response.split(',')]

        # Filter out empty tags and limit to 7 tags
        tags = [tag for tag in tags if tag][:7]

        return tags

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

    # Example 1: Without tags (backwards compatible)
    print("\n" + "="*60)
    print("Example 1: Basic summarization (no tags)")
    print("="*60)
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

    # Summarize without tags
    summary = summarizer.summarize_cluster(documents)

    print("\n" + "="*50)
    print(f"Title: {summary.title}")
    print(f"Summary: {summary.summary}")
    print(f"Documents: {summary.doc_count}")
    print(f"Tags: {summary.tags}")
    print("="*50)

    # Example 2: With tags enabled
    print("\n" + "="*60)
    print("Example 2: Summarization with tags enabled")
    print("="*60)
    summarizer_with_tags = ClusterSummarizer(client, enable_tags=True)

    # Summarize with tags
    summary_with_tags = summarizer_with_tags.summarize_cluster(documents)

    print("\n" + "="*50)
    print(f"Title: {summary_with_tags.title}")
    print(f"Summary: {summary_with_tags.summary}")
    print(f"Documents: {summary_with_tags.doc_count}")
    print(f"Tags: {summary_with_tags.tags}")
    print("="*50)
