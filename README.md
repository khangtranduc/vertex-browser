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
# Normal mode - starts with one empty tab
python browser.py

# Test/Demo mode - loads preset tabs for testing
python browser.py --test              # Loads default preset
python browser.py --test python       # Loads Python programming preset
python browser.py --test ml           # Loads Machine Learning preset
python browser.py --test web          # Loads Web Development preset
python browser.py --test news         # Loads Tech News preset

# Alias: --demo works the same as --test
python browser.py --demo
```

## How It Works

- Open multiple tabs and browse different websites
- Switch to the "Graph View" tab to see your tabs visualized
- Tabs are connected by edges whose thickness represents similarity (based on Claude AI analysis)
- Similar content clusters together through physics simulation
- Results are cached in `~/.vertex_browser_cache.json` to avoid redundant API calls

## Testing & Demo Mode

The browser includes a testing feature that loads preset tabs for quick demonstrations:

### Using Presets
```bash
python browser.py --test [preset_name]
```

Available presets (defined in `test_tabs.json`):
- **default** - Mixed topics demo (Python, ML, Web Dev, News)
- **python** - Python programming resources
- **ml** - Machine Learning tutorials
- **web** - Web development documentation
- **news** - Tech news sites

### Custom Presets
Edit `test_tabs.json` to add your own presets:

```json
{
  "presets": {
    "my_preset": {
      "name": "My Custom Preset",
      "tabs": [
        "https://example.com/page1",
        "https://example.com/page2"
      ]
    }
  }
}
```

### Programmatic Usage
You can also load test tabs programmatically:

```python
# Load a preset
browser.load_test_tabs('python')

# Load custom URLs
browser.load_test_tabs(['https://example.com', 'https://another.com'])
```
