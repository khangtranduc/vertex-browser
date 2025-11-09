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

### Basic Usage

```bash
python browser.py
```

### Load URLs from File (for Testing/Demos)

```bash
# Load URLs from a custom file
python browser.py --urls my_urls.txt

# Load demo URLs (uses demo_urls.txt)
python browser.py --demo
```

**URL File Format:**
- One URL per line
- Lines starting with `#` are treated as comments
- Blank lines are ignored

**Example file:**
```
# Python resources
https://docs.python.org/3/tutorial/
https://realpython.com/

# Machine Learning
https://pytorch.org/tutorials/
https://tensorflow.org/tutorials
```

## How It Works

- Open multiple tabs and browse different websites
- Switch to the "Graph View" tab to see your tabs visualized
- Tabs are connected by edges whose thickness represents similarity (based on Claude AI analysis)
- Similar content clusters together through physics simulation
- Results are cached in `~/.vertex_browser_cache.json` to avoid redundant API calls
