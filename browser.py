import sys
import os
import json
from PyQt5.QtCore import QUrl, Qt, QPointF, QTimer
from PyQt5.QtGui import QPainter, QPen, QColor, QFont, QBrush, QRadialGradient, QPainterPath
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QVBoxLayout,
                             QHBoxLayout, QWidget, QLineEdit, QPushButton, QLabel)
from PyQt5.QtWebEngineWidgets import QWebEngineView
import math
import random
from anthropic import Anthropic

class GraphView(QWidget):
    """Widget that displays a graph visualization of browser tabs"""
    
    def __init__(self, browser):
        super().__init__()
        self.browser = browser
        self.node_positions = {}
        self.velocities = {}
        self.dragging_node = None
        self.drag_offset = (0, 0)
        self.panning = False
        self.pan_start = None
        self.offset_x = 0
        self.offset_y = 0
        self.zoom = 1.0
        self.hovered_node = None
        self.setMinimumSize(800, 600)
        self.setMouseTracking(True)
        # Physics parameters
        self.physics_enabled = True
        self.physics_interval_ms = 33  # ~30 FPS for smoother animation
        self.attraction_threshold = 0.15
        self.attraction_strength = 0.5  # Gentler attraction
        self.repulsion_strength = 1500.0  # Less aggressive repulsion
        # Separation to keep comfortable distances (pixels)
        self.min_separation = 100.0  # More breathing room
        self.separation_strength = 6.0
        self.damping = 0.90  # Higher damping for smoother settling

        # Start physics timer
        self._physics_timer = QTimer(self)
        self._physics_timer.timeout.connect(self._physics_tick)
        self._physics_timer.start(self.physics_interval_ms)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Draw Obsidian-inspired dark background
        bg_color = QColor(30, 30, 35)  # Dark gray-blue
        painter.fillRect(self.rect(), bg_color)

        # Draw subtle grid pattern
        painter.setPen(QPen(QColor(50, 50, 60, 40), 1))
        grid_size = 50
        for x in range(0, self.width(), grid_size):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), grid_size):
            painter.drawLine(0, y, self.width(), y)

        # Get all non-graph tabs
        tabs = self.browser.get_web_tabs()

        if not tabs:
            painter.setPen(QPen(QColor(150, 150, 160)))
            painter.setFont(QFont('Arial', 14))
            painter.drawText(self.rect(), Qt.AlignCenter,
                           "No tabs to display\nOpen some web pages to see the graph")
            return
        
        # Calculate node positions in a circle if not already set
        center_x = self.width() / 2
        center_y = self.height() / 2
        radius = min(self.width(), self.height()) / 3
        
        tab_indices = list(tabs.keys())
        for i, idx in enumerate(tab_indices):
            if idx not in self.node_positions:
                angle = 2 * math.pi * i / len(tab_indices)
                x = center_x + radius * math.cos(angle)
                y = center_y + radius * math.sin(angle)
                self.node_positions[idx] = (x, y)
        
        # Remove positions for closed tabs
        for idx in list(self.node_positions.keys()):
            if idx not in tabs:
                del self.node_positions[idx]
        
        # Save the transform state
        painter.save()
        
        # Apply zoom and pan transformations
        painter.translate(self.offset_x, self.offset_y)
        painter.scale(self.zoom, self.zoom)
        
        # Draw edges (connections between tabs)
        # Draw edges (connections between tabs)
        self.draw_edges(painter, tabs, tab_indices)
        
        # Draw nodes
        for idx, (x, y) in self.node_positions.items():
            tab_data = tabs[idx]

            # Node appearance based on state
            if idx == self.hovered_node:
                radius = 35
                # Gradient from purple to blue (hovered)
                gradient = QRadialGradient(x, y, radius)
                gradient.setColorAt(0, QColor(160, 100, 255))
                gradient.setColorAt(0.7, QColor(120, 80, 220))
                gradient.setColorAt(1, QColor(90, 60, 180))
                node_brush = QBrush(gradient)
                border_color = QColor(180, 120, 255)
                border_width = 2.5
            else:
                radius = 32
                # Gradient from lighter to darker purple (normal)
                gradient = QRadialGradient(x, y, radius)
                gradient.setColorAt(0, QColor(110, 80, 160))
                gradient.setColorAt(0.7, QColor(85, 65, 130))
                gradient.setColorAt(1, QColor(65, 50, 100))
                node_brush = QBrush(gradient)
                border_color = QColor(100, 75, 150, 180)
                border_width = 2

            # Soft outer glow
            glow_radius = radius + 8
            glow = QRadialGradient(x, y, glow_radius)
            glow.setColorAt(0, QColor(120, 90, 180, 60))
            glow.setColorAt(0.5, QColor(80, 60, 120, 30))
            glow.setColorAt(1, QColor(0, 0, 0, 0))
            painter.setBrush(QBrush(glow))
            painter.setPen(QPen(Qt.NoPen))
            painter.drawEllipse(QPointF(x, y), glow_radius, glow_radius)

            # Shadow
            painter.setBrush(QBrush(QColor(0, 0, 0, 80)))
            painter.drawEllipse(QPointF(x + 3, y + 3), radius, radius)

            # Node circle
            painter.setBrush(node_brush)
            painter.setPen(QPen(border_color, border_width))
            painter.drawEllipse(QPointF(x, y), radius, radius)

            # Tab title
            painter.setFont(QFont('Segoe UI', 10, QFont.Normal))
            title = tab_data['title'][:25] + '...' if len(tab_data['title']) > 25 else tab_data['title']

            # Draw title below node
            text_rect = painter.boundingRect(0, 0, 250, 50, Qt.AlignCenter, title)
            text_rect.moveCenter(QPointF(x, y + radius + 20).toPoint())

            # Dark semi-transparent background for text
            painter.setBrush(QBrush(QColor(25, 25, 30, 200)))
            painter.setPen(QPen(QColor(80, 70, 120, 100), 1))
            painter.drawRoundedRect(text_rect.adjusted(-8, -3, 8, 3), 5, 5)

            # Text with light purple color
            painter.setPen(QPen(QColor(220, 200, 255)))
            painter.drawText(text_rect, Qt.AlignCenter, title)
        
        # Restore painter state
        painter.restore()
    
    def get_node_at_pos(self, screen_x, screen_y):
        """Get node index at screen position, accounting for zoom and pan"""
        # Transform screen coordinates to graph coordinates
        graph_x = (screen_x - self.offset_x) / self.zoom
        graph_y = (screen_y - self.offset_y) / self.zoom
        
        for idx, (x, y) in self.node_positions.items():
            distance = math.sqrt((graph_x - x)**2 + (graph_y - y)**2)
            if distance <= 35:  # Max node radius
                return idx
        return None

    def draw_edges(self, painter, tabs, tab_indices, threshold=0.20):
        """Draw edges between nodes when similarity exceeds threshold.

        painter: QPainter already transformed for pan/zoom
        tabs: dict mapping tab index -> {'title', 'url', 'widget'}
        tab_indices: list of tab indices in display order
        threshold: similarity cutoff (0..1)
        """
        if not tab_indices or len(tab_indices) < 2:
            return

        for i, idx1 in enumerate(tab_indices):
            for idx2 in tab_indices[i+1:]:
                try:
                    similarity = self.browser.calculate_similarity(
                        tabs[idx1]['url'], tabs[idx2]['url']
                    )
                except Exception as e:
                    print(f"[DEBUG] Error calculating similarity: {e}")
                    similarity = 0.0

                # Draw edge if similarity exceeds threshold
                if similarity > threshold:
                    x1, y1 = self.node_positions[idx1]
                    x2, y2 = self.node_positions[idx2]

                    # Weight derived from similarity (0..1)
                    weight = float(similarity)

                    # Smoother thickness scaling - less variation
                    min_width = 1.5
                    max_width = 4
                    thickness = min_width + (max_width - min_width) * weight

                    # More subtle alpha for less clutter
                    alpha = int(80 + weight * 120)  # 80-200 range

                    # Obsidian-inspired purple/blue gradient colors
                    if self.hovered_node in (idx1, idx2):
                        # Bright purple when hovered
                        color = QColor(150, 100, 255, alpha)
                    else:
                        # Muted purple-blue for normal edges
                        color = QColor(120, 90, 180, alpha)

                    # Create curved path instead of straight line
                    path = QPainterPath()
                    path.moveTo(x1, y1)

                    # Calculate control point for bezier curve
                    # Offset perpendicular to the line for a gentle curve
                    mid_x = (x1 + x2) / 2
                    mid_y = (y1 + y2) / 2
                    dx = x2 - x1
                    dy = y2 - y1
                    dist = math.sqrt(dx*dx + dy*dy)

                    # Curve amount based on distance (less curve for short distances)
                    curve_amount = min(50, dist * 0.15)

                    # Perpendicular offset
                    if dist > 0:
                        ctrl_x = mid_x - dy / dist * curve_amount
                        ctrl_y = mid_y + dx / dist * curve_amount
                    else:
                        ctrl_x = mid_x
                        ctrl_y = mid_y

                    # Draw smooth quadratic bezier curve
                    path.quadTo(ctrl_x, ctrl_y, x2, y2)

                    pen = QPen(color, thickness, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                    painter.setPen(pen)
                    painter.drawPath(path)

                    # Only show similarity score on hover
                    if self.hovered_node in (idx1, idx2):
                        painter.setFont(QFont('Arial', 9, QFont.Bold))
                        painter.setPen(QPen(QColor(200, 180, 255)))
                        painter.drawText(int(mid_x), int(mid_y - 5), f"{similarity:.2f}")

    def _physics_tick(self):
        """Timer tick: apply a small physics step and request repaint."""
        if not self.physics_enabled:
            return
        # dt in seconds
        dt = max(0.001, self.physics_interval_ms / 1000.0)
        self.apply_physics(dt)
        # repaint will be triggered by update in apply_physics

    def apply_physics(self, dt):
        """Apply a simple force-directed layout step.

        - Attractive force between nodes is proportional to similarity (weight).
        - Repulsive force between all nodes prevents overlap.
        - Velocities are damped each step to settle the system.

        Positions are updated in-place in self.node_positions.
        """
        tabs = self.browser.get_web_tabs()
        node_ids = list(self.node_positions.keys())
        n = len(node_ids)
        if n < 2:
            return

        # Ensure velocity entries exist
        for nid in node_ids:
            if nid not in self.velocities:
                self.velocities[nid] = (0.0, 0.0)

        # Prepare force accumulator
        forces = {nid: [0.0, 0.0] for nid in node_ids}

        # Pairwise interactions
        for i, id1 in enumerate(node_ids):
            x1, y1 = self.node_positions[id1]
            for id2 in node_ids[i+1:]:
                x2, y2 = self.node_positions[id2]
                dx = x2 - x1
                dy = y2 - y1
                dist_sq = dx*dx + dy*dy
                dist = math.sqrt(dist_sq) if dist_sq > 0 else 0.001

                # repulsive force (to avoid overlap), inverse-square
                repulse_mag = self.repulsion_strength / (dist_sq + 1.0)
                fx = (dx / dist) * repulse_mag
                fy = (dy / dist) * repulse_mag

                # apply equal and opposite repulsion
                forces[id1][0] -= fx
                forces[id1][1] -= fy
                forces[id2][0] += fx
                forces[id2][1] += fy

                # attractive force based on similarity (only if above threshold)
                try:
                    sim = float(self.browser.calculate_similarity(
                        tabs[id1]['url'], tabs[id2]['url']
                    ))
                except Exception:
                    sim = 0.0

                if sim > self.attraction_threshold:
                    # desired distance decreases with higher similarity
                    desired = 100.0 * (1.0 - min(0.9, sim)) + 30.0
                    # spring-like attraction: F = k * (dist - desired)
                    k = self.attraction_strength * sim
                    spring_mag = k * (dist - desired)
                    sfx = (dx / dist) * spring_mag
                    sfy = (dy / dist) * spring_mag
                    # attraction pulls nodes together (opposite sign)
                    forces[id1][0] += sfx
                    forces[id1][1] += sfy
                    forces[id2][0] -= sfx
                    forces[id2][1] -= sfy

                # Additional separation when nodes are too close to prevent overlap
                try:
                    min_sep = float(self.min_separation)
                except Exception:
                    min_sep = 80.0

                if dist < min_sep:
                    # overlap amount
                    overlap = max(0.0, min_sep - dist)
                    sep_mag = self.separation_strength * overlap
                    # push nodes apart along the line connecting them
                    sfx2 = (dx / dist) * sep_mag
                    sfy2 = (dy / dist) * sep_mag
                    forces[id1][0] -= sfx2
                    forces[id1][1] -= sfy2
                    forces[id2][0] += sfx2
                    forces[id2][1] += sfy2

        # Integrate velocities and update positions
        max_disp = 200.0 * dt  # clamp per-step displacement for stability
        for nid in node_ids:
            fx, fy = forces[nid]
            vx, vy = self.velocities.get(nid, (0.0, 0.0))

            # acceleration = force (mass=1)
            ax = fx
            ay = fy

            # integrate
            vx = (vx + ax * dt) * self.damping
            vy = (vy + ay * dt) * self.damping

            # clamp velocity to max_disp/dt
            vmax = max_disp / max(1e-6, dt)
            vmag = math.sqrt(vx*vx + vy*vy)
            if vmag > vmax:
                scale = vmax / vmag
                vx *= scale
                vy *= scale

            # update position
            x, y = self.node_positions[nid]
            nx = x + vx * dt
            ny = y + vy * dt

            self.node_positions[nid] = (nx, ny)
            self.velocities[nid] = (vx, vy)

        # Request repaint
        self.update()
    
    def mousePressEvent(self, event):
        """Handle mouse press for dragging nodes or panning"""
        pos = event.pos()
        node_idx = self.get_node_at_pos(pos.x(), pos.y())
        
        if event.button() == Qt.LeftButton:
            if node_idx is not None:
                # Start dragging node
                self.dragging_node = node_idx
                node_x, node_y = self.node_positions[node_idx]
                graph_x = (pos.x() - self.offset_x) / self.zoom
                graph_y = (pos.y() - self.offset_y) / self.zoom
                self.drag_offset = (graph_x - node_x, graph_y - node_y)
            else:
                # Start panning
                self.panning = True
                self.pan_start = (pos.x(), pos.y())
                self.setCursor(Qt.ClosedHandCursor)
        
        elif event.button() == Qt.RightButton:
            if node_idx is not None:
                # Right-click to switch to tab
                self.browser.tabs.setCurrentIndex(node_idx)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging or panning"""
        pos = event.pos()
        
        if self.dragging_node is not None:
            # Drag node
            graph_x = (pos.x() - self.offset_x) / self.zoom
            graph_y = (pos.y() - self.offset_y) / self.zoom
            
            new_x = graph_x - self.drag_offset[0]
            new_y = graph_y - self.drag_offset[1]
            
            self.node_positions[self.dragging_node] = (new_x, new_y)
            self.update()
            
        elif self.panning:
            # Pan view
            dx = pos.x() - self.pan_start[0]
            dy = pos.y() - self.pan_start[1]
            
            self.offset_x += dx
            self.offset_y += dy
            
            self.pan_start = (pos.x(), pos.y())
            self.update()
            
        else:
            # Update hover state
            old_hover = self.hovered_node
            self.hovered_node = self.get_node_at_pos(pos.x(), pos.y())
            
            if self.hovered_node != old_hover:
                self.update()
            
            # Update cursor
            if self.hovered_node is not None:
                self.setCursor(Qt.PointingHandCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        if event.button() == Qt.LeftButton:
            self.dragging_node = None
            self.panning = False
            self.setCursor(Qt.ArrowCursor)
    
    def mouseDoubleClickEvent(self, event):
        """Double-click to switch to tab"""
        pos = event.pos()
        node_idx = self.get_node_at_pos(pos.x(), pos.y())
        
        if node_idx is not None:
            self.browser.tabs.setCurrentIndex(node_idx)
    
    def wheelEvent(self, event):
        """Handle mouse wheel for zooming"""
        delta = event.angleDelta().y()
        zoom_factor = 1.1 if delta > 0 else 0.9
        
        # Get mouse position
        mouse_x = event.x()
        mouse_y = event.y()
        
        # Zoom relative to mouse position
        old_zoom = self.zoom
        self.zoom *= zoom_factor
        self.zoom = max(0.3, min(3.0, self.zoom))
        
        # Adjust offset to zoom towards mouse
        zoom_change = self.zoom / old_zoom
        self.offset_x = mouse_x - (mouse_x - self.offset_x) * zoom_change
        self.offset_y = mouse_y - (mouse_y - self.offset_y) * zoom_change
        
        self.update()


class BrowserTab(QWidget):
    """Individual browser tab with address bar and web view"""

    def __init__(self):
        super().__init__()
        self.web_view = QWebEngineView()
        self.page_content = ""  # Store extracted page content
        self.content_extraction_pending = False

        # Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Navigation bar
        nav_bar = QHBoxLayout()

        self.back_btn = QPushButton('←')
        self.forward_btn = QPushButton('→')
        self.reload_btn = QPushButton('⟳')

        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.navigate_to_url)

        self.go_btn = QPushButton('Go')
        self.go_btn.clicked.connect(self.navigate_to_url)

        nav_bar.addWidget(self.back_btn)
        nav_bar.addWidget(self.forward_btn)
        nav_bar.addWidget(self.reload_btn)
        nav_bar.addWidget(self.url_bar)
        nav_bar.addWidget(self.go_btn)

        layout.addLayout(nav_bar)
        layout.addWidget(self.web_view)

        self.setLayout(layout)

        # Connect signals
        self.back_btn.clicked.connect(self.web_view.back)
        self.forward_btn.clicked.connect(self.web_view.forward)
        self.reload_btn.clicked.connect(self.web_view.reload)
        self.web_view.urlChanged.connect(self.update_url_bar)
        self.web_view.loadFinished.connect(self.on_load_finished)
        
    def navigate_to_url(self):
        url = self.url_bar.text()
        if not url.startswith('http'):
            url = 'https://' + url
        self.web_view.setUrl(QUrl(url))
    
    def update_url_bar(self, url):
        self.url_bar.setText(url.toString())
    
    def extract_page_content(self):
        """Extract text content from the current page"""
        if self.content_extraction_pending:
            return

        self.content_extraction_pending = True

        # JavaScript to extract visible text from the page
        js_code = """
        (function() {
            // Get text from body, excluding script and style tags
            let clone = document.body.cloneNode(true);
            let scripts = clone.getElementsByTagName('script');
            let styles = clone.getElementsByTagName('style');

            for (let i = scripts.length - 1; i >= 0; i--) {
                scripts[i].remove();
            }
            for (let i = styles.length - 1; i >= 0; i--) {
                styles[i].remove();
            }

            let text = clone.innerText || clone.textContent || '';
            // Limit to first 10000 characters to avoid huge API calls
            return text.substring(0, 10000);
        })();
        """

        def handle_content(result):
            if result:
                self.page_content = result
                print(f"✓ Extracted content from {self.web_view.url().toString()[:60]}")
            else:
                self.page_content = ""
            self.content_extraction_pending = False
            # Trigger graph update after content is extracted
            if hasattr(self, 'browser_parent') and self.browser_parent:
                self.browser_parent.update_graph()

        self.web_view.page().runJavaScript(js_code, handle_content)

    def on_load_finished(self, success):
        # Extract page content when page loads
        if success:
            self.extract_page_content()


class Browser(QMainWindow):
    """Main browser window with tabbed interface and graph view"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle('PyQt Web Browser with Graph View')
        self.setGeometry(100, 100, 1200, 800)

        # Initialize graph_tab_index early
        self.graph_tab_index = 0

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)

        # Create graph view tab first
        self.graph_view = GraphView(self)
        self.graph_tab_index = self.tabs.addTab(self.graph_view, 'Graph View')

        # Connect tab changed signal after graph_tab_index is set
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # Add new tab button and refresh button
        corner_widget = QWidget()
        corner_layout = QHBoxLayout()
        corner_layout.setContentsMargins(0, 0, 0, 0)

        refresh_btn = QPushButton('⟳ Extract Content')
        refresh_btn.clicked.connect(self.refresh_all_content)
        refresh_btn.setToolTip('Re-extract content from all tabs')

        new_tab_btn = QPushButton('+')
        new_tab_btn.clicked.connect(self.add_new_tab)

        corner_layout.addWidget(refresh_btn)
        corner_layout.addWidget(new_tab_btn)
        corner_widget.setLayout(corner_layout)
        self.tabs.setCornerWidget(corner_widget)

        self.setCentralWidget(self.tabs)

        # Add first browser tab
        self.add_new_tab()

        # Initialize Anthropic client
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if api_key:
            self.anthropic_client = Anthropic(api_key=api_key)
            print("✓ Anthropic API initialized")
        else:
            self.anthropic_client = None
            print("⚠ ANTHROPIC_API_KEY not set - using random similarity")

        # Cache for similarity scores (url1-url2 -> score)
        self.similarity_cache = {}
        # Cache file for persistent storage
        self.cache_file = os.path.expanduser('~/.vertex_browser_cache.json')
        self._load_similarity_cache()
    
    def add_new_tab(self, url='https://www.google.com'):
        """Add a new browser tab"""
        browser_tab = BrowserTab()
        browser_tab.browser_parent = self  # Store reference to browser
        browser_tab.tab_id = id(browser_tab)  # Unique ID for debugging

        idx = self.tabs.addTab(browser_tab, 'New Tab')
        self.tabs.setCurrentIndex(idx)

        # Load URL - handle both string URLs and boolean from button clicks
        if isinstance(url, bool):
            url = 'https://www.google.com'
        elif not url.startswith('http'):
            url = 'https://' + url
        browser_tab.web_view.setUrl(QUrl(url))

        # Update tab title when page loads
        browser_tab.web_view.titleChanged.connect(
            lambda title, i=idx: self.update_tab_title(i, title)
        )

        return browser_tab
    
    def close_tab(self, idx):
        """Close a tab (but not the graph view)"""
        if idx != self.graph_tab_index and self.tabs.count() > 2:
            self.tabs.removeTab(idx)
            self.update_graph()
    
    def update_tab_title(self, idx, title):
        """Update tab title"""
        if idx < self.tabs.count():
            short_title = title[:20] + '...' if len(title) > 20 else title
            self.tabs.setTabText(idx, short_title)
            self.update_graph()

    def refresh_all_content(self):
        """Re-extract content from all tabs"""
        print("⟳ Refreshing content for all tabs...")
        tabs = self.get_web_tabs()
        for idx, tab_data in tabs.items():
            widget = tab_data['widget']
            if isinstance(widget, BrowserTab):
                widget.extract_page_content()
    
    def _load_similarity_cache(self):
        """Load cached similarity scores from disk"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    self.similarity_cache = json.load(f)
                print(f"✓ Loaded {len(self.similarity_cache)} cached similarities")
        except Exception as e:
            print(f"⚠ Could not load cache: {e}")
            self.similarity_cache = {}

    def _save_similarity_cache(self):
        """Save similarity scores to disk"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.similarity_cache, f)
        except Exception as e:
            print(f"⚠ Could not save cache: {e}")

    def get_web_tabs(self):
        """Get all web tabs (excluding graph view)"""
        tabs = {}
        for i in range(self.tabs.count()):
            if i == self.graph_tab_index:
                continue

            widget = self.tabs.widget(i)
            if isinstance(widget, BrowserTab):
                content = widget.page_content if hasattr(widget, 'page_content') else ""
                tabs[i] = {
                    'title': self.tabs.tabText(i),
                    'url': widget.web_view.url().toString(),
                    'content': content,
                    'widget': widget
                }
        return tabs
    
    def calculate_similarity(self, url1, url2):
        """
        Calculate similarity between two tabs using Claude AI to analyze
        page content. Returns a float between 0.0 and 1.0.
        """
        # Create a cache key (ensure consistent ordering)
        cache_key = f"{min(url1, url2)}||{max(url1, url2)}"

        # Check cache first
        if cache_key in self.similarity_cache:
            return self.similarity_cache[cache_key]

        # If no API client, fall back to random similarity
        if not self.anthropic_client:
            score = random.random()
            self.similarity_cache[cache_key] = score
            return score

        # Get tab content for both URLs
        tabs = self.get_web_tabs()
        content1 = None
        content2 = None

        for tab_data in tabs.values():
            if tab_data['url'] == url1:
                content1 = tab_data['content']
            if tab_data['url'] == url2:
                content2 = tab_data['content']

        # If either page has no content yet, cache and return low similarity
        if not content1 or not content2:
            # Cache the low result to prevent repeated checks
            self.similarity_cache[cache_key] = 0.0
            return 0.0

        try:
            # Use Claude to analyze similarity
            prompt = f"""You are analyzing the semantic similarity between two web pages. Provide a precise similarity score.

Page 1 URL: {url1}
Page 1 Content:
{content1[:3000]}

Page 2 URL: {url2}
Page 2 Content:
{content2[:3000]}

Analyze how similar these pages are based on:
- Topic and subject matter (most important)
- Content type (article, documentation, shopping, social media, etc.)
- Domain/category (news, tech, sports, finance, etc.)

Respond with ONLY a decimal number between 0.00 and 1.00 (use 2 decimal places for precision):
- 0.00-0.10 = completely unrelated topics
- 0.20-0.35 = tangentially related (same broad category)
- 0.40-0.60 = moderately related (overlapping themes)
- 0.65-0.80 = closely related (similar topics)
- 0.85-0.95 = very similar (same specific topic)
- 0.98-1.00 = nearly identical content

Be precise and use the full range. Respond with ONLY the number (e.g., 0.73)."""

            message = self.anthropic_client.messages.create(
                model="claude-3-5-haiku-20241022",  # Fast and cost-effective
                max_tokens=10,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse the response - extract just the number
            response_text = message.content[0].text.strip()
            # Take only the first line and extract the number
            first_line = response_text.split('\n')[0].strip()
            similarity = float(first_line)
            similarity = max(0.0, min(1.0, similarity))  # Clamp to [0, 1]

            # Cache the result
            self.similarity_cache[cache_key] = similarity
            self._save_similarity_cache()

            print(f"✓ Similarity: {similarity:.2f} - {url1[:40]}... ↔ {url2[:40]}...")
            return similarity

        except Exception as e:
            print(f"⚠ Error calculating similarity: {e}")
            # Fall back to basic domain comparison
            try:
                domain1 = QUrl(url1).host()
                domain2 = QUrl(url2).host()
                if domain1 == domain2:
                    return 0.7
                return 0.1
            except:
                return 0.1
    
    def update_graph(self):
        """Update the graph view"""
        self.graph_view.update()
    
    def on_tab_changed(self, idx):
        """Handle tab changes"""
        if idx == self.graph_tab_index:
            self.update_graph()


def main():
    app = QApplication(sys.argv)
    browser = Browser()
    browser.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()