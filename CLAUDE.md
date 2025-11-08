# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Vertex Browser is a PyQt5-based web browser with a unique graph visualization feature that displays browser tabs as nodes in a force-directed graph. Tabs are connected by edges whose thickness represents the similarity between pages, creating a visual representation of browsing relationships.

## Running the Application

```bash
python browser.py
```

**Requirements:** PyQt5, PyQt5-WebEngine

## Architecture

### Core Components

The application consists of three main classes that work together:

1. **Browser (QMainWindow)** - browser.py:483
   - Main application window managing the tab interface
   - Orchestrates communication between browser tabs and graph view
   - Maintains similarity weights cache in `self.weights` dictionary
   - `get_web_tabs()` returns dict of all browser tabs (excluding graph view)
   - `calculate_similarity(url1, url2)` computes edge weights between tabs

2. **BrowserTab (QWidget)** - browser.py:426
   - Individual browser tab with navigation controls
   - Contains QWebEngineView for rendering web content
   - Includes address bar and back/forward/reload buttons
   - Notifies parent browser when pages load to trigger graph updates

3. **GraphView (QWidget)** - browser.py:10
   - Custom widget rendering the force-directed graph
   - Manages node positions, velocities, and physics simulation
   - Implements interactive features: dragging, panning, zooming, hover effects

### Graph Visualization System

**Node Representation:**
- Each browser tab appears as a colored circle node
- Node positions stored in `self.node_positions` dict mapping tab index to (x, y)
- Initially arranged in circle layout, then physics takes over

**Edge System:**
- Edges drawn between tabs based on URL similarity (browser.py:144)
- `draw_edges()` only renders edges when similarity exceeds threshold (default 0.3)
- Edge thickness maps to similarity strength (1-12 pixels)
- Similarity scores displayed at edge midpoints

**Similarity Calculation:**
- Currently uses random weights cached in `Browser.weights` dict (browser.py:569)
- Placeholder implementation designed to be replaced with:
  - Content-based similarity (TF-IDF, embeddings)
  - Domain/topic analysis
  - User browsing patterns

### Physics Engine

The graph uses a force-directed layout with three force types:

1. **Repulsion** (browser.py:241-250)
   - Inverse-square repulsion between all node pairs
   - Prevents nodes from overlapping
   - Strength controlled by `self.repulsion_strength` (default: 2000.0)

2. **Attraction** (browser.py:252-272)
   - Spring-like force proportional to similarity
   - Only active when similarity > `self.attraction_threshold` (default: 0.15)
   - Desired distance inversely proportional to similarity
   - Strength: `self.attraction_strength` (default: 0.8)

3. **Separation** (browser.py:274-290)
   - Additional repulsion when nodes closer than `self.min_separation` (default: 80px)
   - Prevents visual overlap even with high similarity
   - Strength controlled by `self.separation_strength` (default: 8.0)

**Physics Update Loop:**
- Timer-based simulation at 20 FPS (`self.physics_interval_ms` = 50ms)
- `_physics_tick()` calls `apply_physics(dt)` every frame
- Velocities damped by `self.damping` (default: 0.85) for stability
- Displacement clamped to prevent instability

### Interaction Model

**Mouse Events:**
- **Left-click + drag on node:** Move node manually (resets velocity)
- **Left-click + drag on background:** Pan view
- **Right-click on node:** Switch to that tab
- **Double-click on node:** Switch to that tab
- **Mouse wheel:** Zoom in/out centered on cursor
- **Hover:** Highlights node and connected edges

**Coordinate Transformations:**
- `get_node_at_pos()` transforms screen → graph coordinates accounting for pan/zoom
- Painter uses save/restore around pan/zoom transforms

## Development Notes

### Tab Management
- Graph view tab always exists at `self.graph_tab_index` (usually 0)
- `get_web_tabs()` filters out graph view when iterating tabs
- Minimum 2 tabs required (graph view + at least one browser tab)

### Extending Similarity
The placeholder `calculate_similarity()` function is designed to be replaced. When implementing:
- Return float in range [0, 1]
- Cache results if computation is expensive
- Handle exceptions gracefully (return 0.0 on error)
- Consider both url1→url2 and url2→url1 symmetry

### Physics Tuning
Adjust these GraphView parameters for different graph behaviors:
- `attraction_threshold`: Minimum similarity to create attraction force
- `attraction_strength`: How strongly similar tabs pull together
- `repulsion_strength`: How strongly all nodes push apart
- `min_separation`: Minimum visual distance between nodes
- `damping`: Velocity decay factor (higher = faster settling)
