# Vertex Browser

A PyQt5 web browser with AI-powered graph visualization that shows semantic relationships between your open tabs.

## Features

- **Graph View**: Force-directed graph showing browser tabs as nodes
- **AI Similarity**: Uses Claude AI to analyze page content and determine semantic similarity
- **Interactive**: Drag nodes, zoom, pan, and click to navigate
- **Physics Simulation**: Tabs with similar content cluster together

## Installation

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

## How It Works

- Open multiple tabs and browse different websites
- Switch to the "Graph View" tab to see your tabs visualized
- Tabs are connected by edges whose thickness represents similarity (based on Claude AI analysis)
- Similar content clusters together through physics simulation
- Results are cached in `~/.vertex_browser_cache.json` to avoid redundant API calls
