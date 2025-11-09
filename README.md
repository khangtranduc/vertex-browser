# Vertex Browser

A PyQt5 web browser with AI-powered graph visualization that shows semantic relationships between your open tabs.

## Features

- **Graph View**: Force-directed graph showing browser tabs as nodes with a minimum spanning tree visualization
- **AI-Powered Similarity**: Uses Claude AI (Haiku) to analyze page content and determine semantic similarity
- **Smart Clustering**: Automatically groups related tabs into clusters with color coding
- **Cluster Summaries**: AI-generated titles, descriptions, and tags for each cluster
- **Cluster Search**: Ctrl+F to search clusters with AI-powered fuzzy matching
- **Central Nodes**: MST-based centrality highlighting shows the most important pages in each cluster
- **Interactive**: Drag nodes, zoom, pan, single-click to select clusters, double-click to switch tabs
- **Physics Simulation**: Tabs with similar content cluster together through force-directed layout
- **Background Processing**: All AI operations run in background threads for smooth, responsive UI

## Installation

```bash
pip install -r requirements.txt
```

Or manually:
```bash
pip install PyQt5 PyQt5-WebEngine anthropic
```

## Setup

Set your Anthropic API key as an environment variable:

```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

## Running

```bash
python browser.py
```

## Usage

### Navigation
- **Ctrl+T**: New tab
- **Ctrl+G**: Go to graph view
- **Ctrl+Tab / Ctrl+Shift+Tab**: Switch between tabs
- **Ctrl+F** (in graph view): Open cluster search

### Graph Interactions
- **Single-click node**: Select cluster and view its summary panel
- **Double-click node**: Switch to that tab
- **Left-click + drag node**: Move node manually
- **Left-click + drag background**: Pan view
- **Mouse wheel**: Zoom in/out
- **Hover node**: Show full page title and URL tooltip
- **Hover node + click red X**: Close tab

### Cluster Information Panel
When you click a cluster, you'll see:
- **Cluster title**: AI-generated name describing the cluster's theme
- **Tags**: Key topics and concepts found in the cluster
- **Description**: Detailed summary of what the cluster contains
- **Color indicator**: Matches the node colors in the graph

### Search
Press **Ctrl+F** in graph view to search clusters:
- Initial results use keyword matching for instant feedback
- AI-powered fuzzy search runs in background for semantic matches
- Click a result to jump to that cluster in the graph

## How It Works

### Graph Visualization
- Each browser tab appears as a colored node in the graph
- Nodes are connected by a **minimum spanning tree** that shows the strongest relationships
- Edge thickness represents semantic similarity strength
- **Central nodes** (brighter/larger) are identified using MST-based centrality

### AI Processing
All AI operations run in **background threads** to keep the UI responsive:

1. **Content Extraction**: When a page loads, visible text is extracted via JavaScript
2. **Similarity Calculation**: Claude AI (Haiku) analyzes pairs of pages to determine semantic similarity
3. **Clustering**: Pages are grouped using union-find based on similarity threshold
4. **Summarization**: Each cluster gets AI-generated title, description, and tags

### Caching
- Similarity scores are cached in `./.vertex_browser_cache.json`
- Cluster summaries are cached in memory (keyed by URLs, not tab indices)
- Cache automatically updates when tabs navigate to new pages
