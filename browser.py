import sys
import os
import json
from PyQt5.QtCore import QUrl, Qt, QPointF, QTimer, QSize, QRect, QEvent, QMetaObject, Q_ARG
from PyQt5.QtGui import QPainter, QPen, QColor, QFont, QBrush, QRadialGradient, QPainterPath, QPixmap, QIcon, QFontMetrics, QKeySequence
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QVBoxLayout,
                             QHBoxLayout, QWidget, QLineEdit, QPushButton, QLabel, QShortcut, QListWidget, QListWidgetItem)
from PyQt5.QtWebEngineWidgets import QWebEngineView
import math
import random
from anthropic import Anthropic
import concurrent.futures
import threading
from cluster_summarizer import ClusterSummarizer
from cluster_search import ClusterSearcher
from types import SimpleNamespace
from spanning_tree import SpanningTreeCalculator, Edge

class GraphView(QWidget):
    """Widget that displays a graph visualization of browser tabs"""
    
    def __init__(self, browser):
        super().__init__()
        self.browser = browser
        self.node_positions = {}
        self.velocities = {}
        self.dragging_node = None
        self.drag_offset = (0, 0)
        self.drag_start_pos = None
        self.has_dragged = False
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
        self.min_separation = 220.0  # More breathing room for larger nodes
        self.separation_strength = 6.0
        self.damping = 0.90  # Higher damping for smoother settling

        # Start physics timer
        self._physics_timer = QTimer(self)
        self._physics_timer.timeout.connect(self._physics_tick)
        self._physics_timer.start(self.physics_interval_ms)
        # Clustering
        self.cluster_threshold = 0.30
        self.cluster_map = {}
        self.cluster_colors = {}
        # Selection state for clusters
        self.selected_cluster = None
        self._panel_rect = None
        self._close_btn_rect = None
        # Gesture state for pinch-to-zoom
        try:
            # enable pinch gesture if supported
            self.grabGesture(Qt.PinchGesture)
        except Exception:
            pass
        self.pinch_center = None
        # MST visualization
        self.show_mst_only = True
        self.mst_result = None
        self.mst_calculator = SpanningTreeCalculator(min_edge_weight=0.2)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Clean modern background (light gray, like modern browsers)
        bg_color = QColor(248, 249, 250)  # Very light gray
        painter.fillRect(self.rect(), bg_color)

        # Subtle dot grid pattern
        painter.setPen(QPen(QColor(220, 222, 225, 100), 1))
        grid_size = 40
        for x in range(0, self.width(), grid_size):
            for y in range(0, self.height(), grid_size):
                painter.drawPoint(x, y)

        # Get all non-graph tabs
        tabs = self.browser.get_web_tabs()

        if not tabs:
            painter.setPen(QPen(QColor(120, 125, 130)))
            painter.setFont(QFont('SF Pro Display', 14))
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
        
        # Clear close button positions from previous frame
        self.close_button_positions = {}

        # Draw nodes
        # Compute clustering based on current similarities
        try:
            self.cluster_map = self.compute_clusters(tabs, tab_indices, threshold=self.cluster_threshold)
        except Exception:
            self.cluster_map = {}

        # Identify central nodes using MST
        central_nodes = set()
        if self.mst_result and self.cluster_map:
            cluster_central = self.mst_calculator.get_cluster_central_nodes(
                self.mst_result, self.cluster_map, top_n_per_cluster=10  # Get all nodes
            )
            for cluster_id, nodes_scores in cluster_central.items():
                if not nodes_scores or len(nodes_scores) < 2:
                    continue
                # Only highlight as central if there's a clear difference in centrality
                # Check if top node has significantly higher score than second node
                top_score = nodes_scores[0][1]
                second_score = nodes_scores[1][1] if len(nodes_scores) > 1 else 0.0

                # Only highlight if the top score is at least 2% higher than second
                # This avoids highlighting in cases where all nodes are equal
                if top_score > second_score * 1.02:
                    central_nodes.add(nodes_scores[0][0])

        # Track hovered node for drawing full title on top later
        hovered_node_data = None

        for idx, (x, y) in self.node_positions.items():
            tab_data = tabs[idx]

            # Check if this is a central node
            is_central = idx in central_nodes

            # Node appearance based on state
            if idx == self.hovered_node:
                # Slightly smaller hovered radius while still fitting the title
                radius = 75;
                # Clean blue gradient (hovered) - Chrome-like
                gradient = QRadialGradient(x, y, radius)
                gradient.setColorAt(0, QColor(100, 160, 255))
                gradient.setColorAt(0.7, QColor(66, 133, 244))
                gradient.setColorAt(1, QColor(50, 110, 200))
                node_brush = QBrush(gradient)
                border_color = QColor(66, 133, 244)
                border_width = 2.5
            else:
                # Central nodes are larger
                radius = 85 if is_central else 70
                # Color by cluster if available
                cluster_id = self.cluster_map.get(idx, None)
                if cluster_id is not None:
                    if cluster_id not in self.cluster_colors:
                        hue = (cluster_id * 47) % 360
                        self.cluster_colors[cluster_id] = QColor.fromHsv(hue, 180, 245)
                    base_color = self.cluster_colors[cluster_id]
                else:
                    base_color = QColor(245, 247, 250)

                # Brighter gradient for central nodes
                if is_central:
                    gradient = QRadialGradient(x, y, radius)
                    gradient.setColorAt(0, base_color.lighter(135))
                    gradient.setColorAt(0.7, base_color.lighter(115))
                    gradient.setColorAt(1, base_color.darker(105))
                    node_brush = QBrush(gradient)
                    border_color = base_color.darker(130)
                    border_width = 3.5
                else:
                    # Subtle radial gradient tinted by cluster color
                    gradient = QRadialGradient(x, y, radius)
                    gradient.setColorAt(0, base_color.lighter(120))
                    gradient.setColorAt(0.8, base_color.lighter(105))
                    gradient.setColorAt(1, base_color.darker(110))
                    node_brush = QBrush(gradient)
                    border_color = base_color.darker(120)
                    border_width = 2

            # Soft shadow (not glow)
            painter.setBrush(QBrush(QColor(0, 0, 0, 20)))
            painter.setPen(QPen(Qt.NoPen))
            painter.drawEllipse(QPointF(x + 2, y + 3), radius + 2, radius + 2)

            # Node circle
            painter.setBrush(node_brush)
            painter.setPen(QPen(border_color, border_width))
            painter.drawEllipse(QPointF(x, y), radius, radius)

            # Draw favicon in center of node (shift up a bit to leave room for label)
            if 'icon' in tab_data and not tab_data['icon'].isNull():
                # Scale favicon sizes down to match slightly smaller nodes
                icon_size = 48 if idx == self.hovered_node else 44
                pixmap = tab_data['icon'].pixmap(QSize(icon_size, icon_size))
                # Move favicon up more so the inline label can sit lower inside the node
                painter.drawPixmap(
                    int(x - icon_size / 2),
                    int(y - icon_size / 2 - 16),  # Move up to make room for label below
                    pixmap
                )

            # Small truncated label inside the node
            try:
                label = tab_data.get('title', '')
                # Prefer web view's title if available (full title fetched for hover)
                widget = tab_data.get('widget')
                if widget is not None and hasattr(widget, 'web_view'):
                    wtitle = widget.web_view.title()
                    if wtitle:
                        label = wtitle
            except Exception:
                label = tab_data.get('title', '')

            # Truncate to a short inline label (12 chars) for compact display
            short_label = label[:12] + '…' if len(label) > 12 else label
            painter.setFont(QFont('SF Pro Display', 9, QFont.Normal))
            painter.setPen(QPen(QColor(60, 64, 67)))
            txt_rect = painter.boundingRect(0, 0, int(radius * 1.4), 18, Qt.AlignCenter, short_label)
            # Position the inline label inside the node (lower than center but still contained)
            txt_rect.moveCenter(QPointF(x, y + radius * 0.35).toPoint())
            painter.drawText(txt_rect, Qt.AlignCenter, short_label)

            # Save full title from web view (for hover overlay)
            full_title = tab_data.get('title', '')
            try:
                if widget is not None and hasattr(widget, 'web_view'):
                    wtitle = widget.web_view.title()
                    if wtitle:
                        full_title = wtitle
            except Exception:
                pass

            if idx == self.hovered_node:
                hovered_node_data = {
                    'x': x,
                    'y': y,
                    'radius': radius,
                    'title': full_title
                }

            # Draw close button when hovered
            if idx == self.hovered_node:
                # Place the close button slightly outside the node at the top-right
                # so it visually sits just outside the circle with a small overlap.
                # offset factor > 1 would place it further out; 0.75 keeps it near
                # the edge but slightly outside along the diagonal.
                # Keep the close button slightly outside the node at the top-right
                close_btn_offset_factor = 0.75
                close_btn_x = x + radius * close_btn_offset_factor
                close_btn_y = y - radius * close_btn_offset_factor
                # Slightly smaller close button to match reduced node size
                close_btn_radius = 14

                # Close button background
                painter.setBrush(QBrush(QColor(220, 53, 69)))
                painter.setPen(QPen(QColor(200, 40, 55), 1))
                painter.drawEllipse(QPointF(close_btn_x, close_btn_y), close_btn_radius, close_btn_radius)

                # X symbol (centered in the close button)
                painter.setPen(QPen(QColor(255, 255, 255), 2))
                offset = max(4, int(close_btn_radius * 0.45))
                painter.drawLine(
                    int(close_btn_x - offset), int(close_btn_y - offset),
                    int(close_btn_x + offset), int(close_btn_y + offset)
                )
                painter.drawLine(
                    int(close_btn_x + offset), int(close_btn_y - offset),
                    int(close_btn_x - offset), int(close_btn_y + offset)
                )

                # Store close button position for click detection
                self.close_button_positions[idx] = (close_btn_x, close_btn_y, close_btn_radius)

                # Show URL tooltip on hover
                url = tab_data['url']
                if len(url) > 60:
                    url = url[:60] + '...'

                # Draw tooltip
                tooltip_font = QFont('SF Pro Display', 9)
                painter.setFont(tooltip_font)
                tooltip_rect = painter.boundingRect(0, 0, 400, 30, Qt.AlignLeft, url)
                tooltip_rect.moveCenter(QPointF(x, y - radius - 35).toPoint())

                # Tooltip background
                painter.setBrush(QBrush(QColor(50, 55, 60, 240)))
                painter.setPen(QPen(Qt.NoPen))
                painter.drawRoundedRect(tooltip_rect.adjusted(-10, -5, 10, 5), 5, 5)

                # Tooltip text
                painter.setPen(QPen(QColor(240, 245, 250)))
                painter.drawText(tooltip_rect, Qt.AlignCenter, url)

        # Hover overlay will be drawn in screen coordinates after restore

        # Restore painter state (end of transformed drawing)
        painter.restore()

        # Draw hovered node's full title in screen coordinates so sizing
        # and wrapping are measured against widget pixels (avoids issues
        # when zoom/pan transforms are active).
        if hovered_node_data:
            from PyQt5.QtCore import QRectF
            from PyQt5.QtGui import QTextDocument

            # Convert graph coordinates to screen coordinates (apply zoom & pan)
            gx = hovered_node_data['x']
            gy = hovered_node_data['y']
            radius = hovered_node_data['radius']
            full_title = hovered_node_data['title']

            sx = gx * self.zoom + self.offset_x
            sy = gy * self.zoom + self.offset_y

            font = QFont('SF Pro Display', 14, QFont.Bold)

            # Use QTextDocument for proper text layout with word wrapping
            max_chars = 200
            display_title = full_title if len(full_title) <= max_chars else full_title[:max_chars] + "…"

            doc = QTextDocument()
            doc.setDefaultFont(font)
            html_text = f'<div style="color: rgb(60, 64, 67); text-align: center;">{display_title}</div>'
            doc.setHtml(html_text)

            # Measure natural width (no constraint) using font metrics for accuracy
            fm = QFontMetrics(font)
            natural_width = fm.horizontalAdvance(display_title)

            # Safe maximum (60% of widget width, cap at 800px)
            safe_max = min(800, int(self.width() * 0.6))

            if natural_width > safe_max:
                # Constrain document to safe_max so it wraps
                doc.setTextWidth(safe_max)
                text_size = doc.size()
                text_width = text_size.width()
                text_height = text_size.height()
            else:
                # Use measured natural width; set doc width to that to get height
                doc.setTextWidth(natural_width)
                text_size = doc.size()
                text_width = text_size.width()
                text_height = text_size.height()

            # Position the popup centered below the node in screen coords
            text_rect = QRectF(
                sx - text_width / 2,
                sy + radius + 12,
                text_width,
                text_height
            )

            # Ensure popup stays within widget bounds horizontally
            if text_rect.left() < 8:
                text_rect.moveLeft(8)
            if text_rect.right() > self.width() - 8:
                text_rect.moveRight(self.width() - 8)

            # Draw shadow + background + border
            painter.setBrush(QBrush(QColor(0, 0, 0, 40)))
            painter.setPen(QPen(Qt.NoPen))
            painter.drawRoundedRect(text_rect.adjusted(-8, -3, 14, 9), 8, 8)

            painter.setBrush(QBrush(QColor(255, 255, 255, 250)))
            painter.setPen(QPen(QColor(66, 133, 244), 2))
            painter.drawRoundedRect(text_rect.adjusted(-10, -5, 10, 5), 8, 8)

            # Draw the text
            painter.setPen(QPen(QColor(60, 64, 67)))
            painter.save()
            painter.translate(text_rect.topLeft())
            doc.drawContents(painter)
            painter.restore()
        # Draw overlay panel for selected cluster (no transform)
        if self.selected_cluster is not None:
            panel_width = min(360, max(260, int(self.width() * 0.28)))
            panel_margin = 16
            panel_x = self.width() - panel_width - panel_margin
            panel_y = panel_margin
            panel_h = self.height() - panel_margin * 2
            panel_w = panel_width

            # Panel background
            panel_rect = QRect(panel_x, panel_y, panel_w, panel_h)
            self._panel_rect = panel_rect

            painter.setPen(QPen(QColor(200, 205, 210), 1))
            painter.setBrush(QBrush(QColor(255, 255, 255, 250)))
            painter.drawRoundedRect(panel_rect, 8, 8)

            # Close button at top-right of panel
            close_r = 12
            close_x = panel_x + panel_w - close_r - 10
            close_y = panel_y + 10
            self._close_btn_rect = QRect(close_x - close_r, close_y - close_r, close_r*2, close_r*2)

            painter.setBrush(QBrush(QColor(230, 80, 80)))
            painter.setPen(QPen(QColor(200, 40, 40)))
            painter.drawEllipse(self._close_btn_rect)
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawLine(close_x - 5, close_y - 5, close_x + 5, close_y + 5)
            painter.drawLine(close_x + 5, close_y - 5, close_x - 5, close_y + 5)

            # Title and description from external callbacks if provided
            title = self.get_cluster_title(self.selected_cluster)
            desc = self.get_cluster_description(self.selected_cluster)

            # Draw cluster color indicator (circle next to title)
            cluster_color = self.cluster_colors.get(self.selected_cluster, QColor(180, 180, 180))
            indicator_size = 14
            indicator_x = panel_x + 16
            indicator_y = panel_y + 26

            # Draw color indicator with border
            painter.setPen(QPen(cluster_color.darker(120), 2))
            painter.setBrush(QBrush(cluster_color))
            painter.drawEllipse(indicator_x, indicator_y, indicator_size, indicator_size)

            # Draw title (shifted right to make room for indicator)
            painter.setPen(QPen(QColor(34, 40, 49)))
            painter.setFont(QFont('SF Pro Display', 12, QFont.Bold))
            title_rect = QRect(panel_x + 16 + indicator_size + 8, panel_y + 20, panel_w - 40 - indicator_size - 8, 30)
            painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignVCenter, title)

            # Draw tags (chips) below the title if available
            tags = []
            try:
                tags = self.get_cluster_tags(self.selected_cluster) or []
            except Exception:
                tags = []

            tags_height = 0
            if tags:
                painter.setFont(QFont('SF Pro Display', 9))
                fm = painter.fontMetrics()
                chip_x = panel_x + 16
                chip_y = panel_y + 52
                max_x = panel_x + panel_w - 16
                line_height = fm.height() + 6

                for t in tags[:12]:
                    text_w = fm.width(t)
                    chip_w = text_w + 12
                    if chip_x + chip_w > max_x:
                        # wrap to next line
                        chip_x = panel_x + 16
                        chip_y += line_height + 6

                    chip_rect = QRect(int(chip_x), int(chip_y), int(chip_w), fm.height() + 6)
                    painter.setBrush(QBrush(QColor(245, 246, 248)))
                    painter.setPen(QPen(QColor(210, 215, 220)))
                    painter.drawRoundedRect(chip_rect, 6, 6)
                    painter.setPen(QPen(QColor(60, 64, 67)))
                    painter.drawText(chip_rect, Qt.AlignCenter, t)

                    chip_x += chip_w + 8

                tags_height = (chip_y - (panel_y + 52)) + line_height

            # Draw description (positioned below tags area)
            painter.setFont(QFont('SF Pro Display', 10))
            painter.setPen(QPen(QColor(70, 76, 82)))
            desc_y = panel_y + 60 + max(0, tags_height)
            desc_rect = QRect(panel_x + 16, desc_y, panel_w - 40, panel_h - (desc_y - panel_y) - 20)
            painter.drawText(desc_rect, Qt.TextWordWrap, desc)
    
    def get_node_at_pos(self, screen_x, screen_y):
        """Get node index at screen position, accounting for zoom and pan"""
        # Transform screen coordinates to graph coordinates
        graph_x = (screen_x - self.offset_x) / self.zoom
        graph_y = (screen_y - self.offset_y) / self.zoom
        
        for idx, (x, y) in self.node_positions.items():
            distance = math.sqrt((graph_x - x)**2 + (graph_y - y)**2)
            if distance <= 116:  # Max node radius (updated to match larger nodes)
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

        if self.show_mst_only:
            # Build edges for MST calculation
            edges = []
            for i, idx1 in enumerate(tab_indices):
                for idx2 in tab_indices[i+1:]:
                    try:
                        similarity = self.browser.calculate_similarity(
                            tabs[idx1]['url'], tabs[idx2]['url']
                        )
                    except Exception as e:
                        similarity = 0.0

                    if similarity > threshold:
                        edges.append(Edge(idx1, idx2, similarity))

            # Calculate MST (but use full graph for centrality)
            self.mst_result = self.mst_calculator.calculate_mst(
                tab_indices, edges, self.cluster_map
            )

            # Calculate centrality based on full graph, not just MST
            full_graph_centrality = self.mst_calculator._calculate_centrality(
                tab_indices, edges  # Use ALL edges, not just MST
            )
            # Override the MST-based centrality with full graph centrality
            self.mst_result.node_centrality = full_graph_centrality

            # Draw only MST edges
            for edge in self.mst_result.edges:
                self._draw_edge(painter, edge.node1, edge.node2, edge.weight)
        else:
            # Draw all edges above threshold
            for i, idx1 in enumerate(tab_indices):
                for idx2 in tab_indices[i+1:]:
                    try:
                        similarity = self.browser.calculate_similarity(
                            tabs[idx1]['url'], tabs[idx2]['url']
                        )
                    except Exception as e:
                        similarity = 0.0

                    if similarity > threshold:
                        self._draw_edge(painter, idx1, idx2, similarity)

    def _draw_edge(self, painter, idx1, idx2, weight):
        """Helper method to draw a single edge between two nodes.

        painter: QPainter already transformed for pan/zoom
        idx1, idx2: node indices
        weight: edge weight (similarity score 0..1)
        """
        x1, y1 = self.node_positions[idx1]
        x2, y2 = self.node_positions[idx2]

        # Smoother thickness scaling - less variation
        min_width = 1.5
        max_width = 4
        thickness = min_width + (max_width - min_width) * weight

        # More subtle alpha for less clutter
        alpha = int(60 + weight * 100)  # 60-160 range

        # Modern browser-inspired blue colors
        if self.hovered_node in (idx1, idx2):
            # Bright blue when hovered (Chrome blue)
            color = QColor(66, 133, 244, alpha + 60)
        else:
            # Subtle gray-blue for normal edges
            color = QColor(128, 134, 139, alpha)

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
            painter.setFont(QFont('SF Pro Display', 9, QFont.Bold))
            painter.setPen(QPen(QColor(66, 133, 244)))
            painter.drawText(int(mid_x), int(mid_y - 5), f"{weight:.2f}")

    def compute_clusters(self, tabs, tab_indices, threshold=None):
        """Compute clusters as connected components where edge weight >= threshold.

        Returns a dict mapping node id -> small integer cluster id.
        This is a simple, fast approach that groups strongly-connected nodes.
        """
        if threshold is None:
            threshold = self.cluster_threshold

        # Initialize union-find parents
        parents = {nid: nid for nid in tab_indices}

        def find(a):
            # path compression
            while parents[a] != a:
                parents[a] = parents[parents[a]]
                a = parents[a]
            return a

        def union(a, b):
            ra = find(a)
            rb = find(b)
            if ra != rb:
                parents[rb] = ra

        # Union pairs with similarity >= threshold
        for i, id1 in enumerate(tab_indices):
            for id2 in tab_indices[i+1:]:
                try:
                    sim = float(self.browser.calculate_similarity(
                        tabs[id1]['url'], tabs[id2]['url']
                    ))
                except Exception:
                    sim = 0.0

                if sim >= threshold:
                    union(id1, id2)

        # Assign compact cluster ids
        cluster_roots = {}
        cluster_map = {}
        next_id = 0
        for nid in tab_indices:
            root = find(nid)
            if root not in cluster_roots:
                cluster_roots[root] = next_id
                next_id += 1
            cluster_map[nid] = cluster_roots[root]

        return cluster_map

    def get_cluster_title(self, cluster_id):
        """Return cluster title by delegating to Browser if available.

        The Browser may implement a `get_cluster_title(cluster_id)` method
        to provide custom titles. If not present, return a simple fallback.
        """
        if cluster_id is None:
            return ""
        if hasattr(self.browser, 'get_cluster_title') and callable(self.browser.get_cluster_title):
            try:
                return self.browser.get_cluster_title(cluster_id)
            except Exception:
                pass
        return f"Cluster {cluster_id}"

    def get_cluster_description(self, cluster_id):
        """Return cluster description by delegating to Browser if available.

        Browser can implement `get_cluster_description(cluster_id)` to return
        a string description. Fallback is an empty placeholder.
        """
        if cluster_id is None:
            return ""
        if hasattr(self.browser, 'get_cluster_description') and callable(self.browser.get_cluster_description):
            try:
                return self.browser.get_cluster_description(cluster_id)
            except Exception:
                pass
        return "(No description available)"

    def get_cluster_tags(self, cluster_id):
        """Return cluster tags by delegating to Browser if available.

        Returns a list of tag strings. If unavailable, returns an empty list.
        """
        if cluster_id is None:
            return []
        if hasattr(self.browser, 'get_cluster_tags') and callable(self.browser.get_cluster_tags):
            try:
                return self.browser.get_cluster_tags(cluster_id)
            except Exception:
                pass
        return []

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
    
    def is_on_close_button(self, screen_x, screen_y):
        """Check if click is on a close button"""
        if not hasattr(self, 'close_button_positions'):
            return None

        graph_x = (screen_x - self.offset_x) / self.zoom
        graph_y = (screen_y - self.offset_y) / self.zoom

        for idx, (btn_x, btn_y, btn_radius) in self.close_button_positions.items():
            dist = math.sqrt((graph_x - btn_x)**2 + (graph_y - btn_y)**2)
            if dist <= btn_radius:
                return idx
        return None

    def mousePressEvent(self, event):
        """Handle mouse press for dragging nodes or panning"""
        pos = event.pos()

        # Check if clicking close button first
        close_idx = self.is_on_close_button(pos.x(), pos.y())
        if close_idx is not None and event.button() == Qt.LeftButton:
            self.browser.close_tab(close_idx)
            return

        node_idx = self.get_node_at_pos(pos.x(), pos.y())

        if event.button() == Qt.LeftButton:
            if node_idx is not None:
                # Track potential drag vs click
                self.dragging_node = node_idx
                self.drag_start_pos = pos
                self.has_dragged = False
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
            # Check if we've moved enough to count as a drag
            if hasattr(self, 'drag_start_pos'):
                dx = pos.x() - self.drag_start_pos.x()
                dy = pos.y() - self.drag_start_pos.y()
                if abs(dx) > 5 or abs(dy) > 5:
                    self.has_dragged = True

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
            pos = event.pos()

            # If click on panel close button, clear selection
            try:
                if self._close_btn_rect is not None and self._close_btn_rect.contains(pos):
                    self.selected_cluster = None
                    self.update()
                    return
            except Exception:
                pass

            # If we were on a node and didn't drag, select its cluster (do NOT switch tabs on single click)
            if self.dragging_node is not None and not self.has_dragged:
                node_idx = self.dragging_node
                # select cluster
                self.selected_cluster = self.cluster_map.get(node_idx, None)
                self.update()

            # If we weren't dragging but clicked (quick click on node), select cluster
            if self.dragging_node is None and not self.has_dragged:
                node_idx = self.get_node_at_pos(pos.x(), pos.y())
                if node_idx is not None:
                    # single click now only selects the cluster; double-click opens the tab
                    self.selected_cluster = self.cluster_map.get(node_idx, None)
                    self.update()

            self.dragging_node = None
            self.panning = False
            self.has_dragged = False
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

    def event(self, event):
        """Handle gesture events for pinch-to-zoom"""
        if event.type() == QEvent.Gesture:
            return self.gestureEvent(event)
        return super().event(event)

    def gestureEvent(self, event):
        """Handle pinch gesture for zooming"""
        gesture = event.gesture(Qt.PinchGesture)
        if gesture:
            return self.pinchGesture(gesture)
        return False

    def pinchGesture(self, gesture):
        """Handle pinch-to-zoom gesture"""
        if gesture.state() == Qt.GestureStarted:
            # Store the center point when pinch starts
            self.pinch_center = gesture.centerPoint()

        elif gesture.state() == Qt.GestureUpdated:
            # Get the scale factor from the gesture
            scale_factor = gesture.scaleFactor()

            # Get center point of the pinch
            center = gesture.centerPoint()
            center_x = center.x()
            center_y = center.y()

            # Apply zoom
            old_zoom = self.zoom
            self.zoom *= scale_factor
            self.zoom = max(0.3, min(3.0, self.zoom))

            # Adjust offset to zoom towards pinch center
            zoom_change = self.zoom / old_zoom
            self.offset_x = center_x - (center_x - self.offset_x) * zoom_change
            self.offset_y = center_y - (center_y - self.offset_y) * zoom_change

            self.update()

        elif gesture.state() == Qt.GestureFinished:
            self.pinch_center = None

        return True


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
                # Pre-calculate similarities in background (with delay to avoid blocking)
                QTimer.singleShot(500, lambda: self.browser_parent.precalculate_similarities())
                # Pre-generate cluster summaries in background (with delay)
                QTimer.singleShot(1000, lambda: self.browser_parent.precalculate_cluster_summaries())

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

        # Prepare cluster summarizer when API available
        if self.anthropic_client:
            try:
                # Enable tag extraction so cluster summaries include tags
                self.cluster_summarizer = ClusterSummarizer(self.anthropic_client, enable_tags=True)
            except Exception as e:
                print(f"⚠ Could not initialize ClusterSummarizer: {e}")
                self.cluster_summarizer = None
        else:
            self.cluster_summarizer = None

        # Cache for similarity scores (url1-url2 -> score)
        self.similarity_cache = {}
        # Cache file for persistent storage
        self.cache_file = os.path.expanduser('./.vertex_browser_cache.json')
        self._load_similarity_cache()

        # Cache for cluster summaries: frozenset(node ids) -> ClusterSummary
        self._cluster_summary_cache = {}
        # Thread pool for background summarization
        self._summary_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self._summary_futures = {}  # key -> Future
        self._summary_lock = threading.Lock()

        # Keyboard shortcuts
        try:
            # Next/previous tab (Ctrl+Tab, Ctrl+Shift+Tab)
            self._sc_next = QShortcut(QKeySequence('Ctrl+Tab'), self)
            self._sc_next.activated.connect(self._shortcut_next_tab)

            self._sc_prev = QShortcut(QKeySequence('Ctrl+Shift+Tab'), self)
            self._sc_prev.activated.connect(self._shortcut_prev_tab)

            self._sc_find = QShortcut(QKeySequence('Ctrl+F'), self)
            self._sc_find.activated.connect(self._shortcut_find)

            # Go to graph view (Ctrl+G)
            self._sc_graph = QShortcut(QKeySequence('Ctrl+G'), self)
            self._sc_graph.activated.connect(self._shortcut_go_graph)

            # New tab (Ctrl+T)
            self._sc_new_tab = QShortcut(QKeySequence('Ctrl+T'), self)
            self._sc_new_tab.activated.connect(self._shortcut_new_tab)
        except Exception:
            # If QShortcut/QKeySequence isn't available for some reason, ignore
            pass

        # Cluster search panel (created on-demand)
        self._cluster_search_panel = None

    # --- Keyboard shortcut handlers ---------------------------------
    def _shortcut_next_tab(self):
        try:
            count = self.tabs.count()
            if count <= 1:
                return
            new_index = (self.tabs.currentIndex() + 1) % count
            self.tabs.setCurrentIndex(new_index)
        except Exception:
            pass

    def _shortcut_prev_tab(self):
        try:
            count = self.tabs.count()
            if count <= 1:
                return
            new_index = (self.tabs.currentIndex() - 1) % count
            self.tabs.setCurrentIndex(new_index)
        except Exception:
            pass

    def _shortcut_go_graph(self):
        try:
            if hasattr(self, 'graph_tab_index') and 0 <= self.graph_tab_index < self.tabs.count():
                self.tabs.setCurrentIndex(self.graph_tab_index)
                # Give focus to the graph view widget
                try:
                    self.graph_view.setFocus()
                except Exception:
                    pass
        except Exception:
            pass

    def _shortcut_find(self):
        # Only open search when currently viewing the graph
        try:
            if self.tabs.currentIndex() == self.graph_tab_index:
                self._open_cluster_search()
        except Exception:
            pass

    def _shortcut_new_tab(self):
        try:
            self.add_new_tab()
        except Exception:
            pass

    def _open_cluster_search(self):
        """Create (if needed) and show the cluster search panel anchored to the Graph View."""
        # Create panel lazily
        try:
            if self._cluster_search_panel is None:
                panel = QWidget(self.graph_view)
                panel.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
                panel.setAttribute(Qt.WA_ShowWithoutActivating)
                layout = QVBoxLayout()
                layout.setContentsMargins(8, 8, 8, 8)

                # Search input
                search_edit = QLineEdit()
                if self.anthropic_client:
                    search_edit.setPlaceholderText('🔍 AI-powered search... (press Enter)')
                else:
                    search_edit.setPlaceholderText('Search clusters... (press Enter)')
                layout.addWidget(search_edit)

                # Results list
                results_list = QListWidget()
                layout.addWidget(results_list)

                panel.setLayout(layout)

                # Add event handler for fuzzy search updates
                def panel_event_filter(obj, event):
                    if event.type() == QEvent.User and hasattr(panel, '_pending_fuzzy_results'):
                        # Process fuzzy results on main thread
                        fuzzy_results = panel._pending_fuzzy_results
                        delattr(panel, '_pending_fuzzy_results')
                        if hasattr(panel, '_update_fuzzy'):
                            panel._update_fuzzy(fuzzy_results)
                        return True
                    return False

                panel.eventFilter = panel_event_filter
                panel.installEventFilter(panel)

                # Close on Esc
                esc_short = QShortcut(QKeySequence('Esc'), panel)
                esc_short.activated.connect(panel.hide)

                # Store widgets for reuse
                panel._search_edit = search_edit
                panel._results_list = results_list
                panel._current_query = None
                panel._current_clusters = None

                # Perform search when user presses Enter
                def do_search():
                    q = search_edit.text().strip()
                    results_list.clear()
                    if not q:
                        return

                    # Build clusters from current graph
                    tabs = self.get_web_tabs()
                    tab_indices = list(tabs.keys())
                    cluster_map = {}
                    try:
                        cluster_map = self.graph_view.compute_clusters(tabs, tab_indices, threshold=self.graph_view.cluster_threshold)
                    except Exception:
                        cluster_map = {}

                    groups = {}
                    for nid, cid in cluster_map.items():
                        groups.setdefault(cid, []).append(nid)

                    clusters = []
                    for cid, members in groups.items():
                        title = self.get_cluster_title(cid)
                        summary = self.get_cluster_description(cid)
                        tags = self.get_cluster_tags(cid) or []
                        urls = [tabs.get(nid, {}).get('url', '') for nid in members]
                        doc_count = len(members)
                        clusters.append(SimpleNamespace(title=title, summary=summary, tags=tags, urls=urls, doc_count=doc_count, cluster_id=cid))

                    # Store current search context for re-running when descriptions update
                    panel._current_query = q
                    panel._current_clusters = clusters

                    # STEP 1: Show keyword-based results immediately
                    keyword_searcher = ClusterSearcher()  # No fuzzy search
                    try:
                        keyword_results = keyword_searcher.search(clusters, q, min_score=0.0, max_results=50)
                    except Exception:
                        keyword_results = []

                    # Display keyword results immediately
                    for res in keyword_results:
                        item = QListWidgetItem(f"{res.cluster.title} — score {res.score:.2f}")
                        item.setData(Qt.UserRole, getattr(res.cluster, 'cluster_id', None))
                        item.setToolTip((res.cluster.summary or '')[:400])
                        results_list.addItem(item)

                    # STEP 2: If API available, update with fuzzy results in background
                    if self.anthropic_client:
                        # Create helper method that can be invoked from background thread
                        def update_with_fuzzy_results(fuzzy_results):
                            try:
                                print(f"📊 Updating UI with fuzzy results for: '{q}'")
                                results_list.clear()
                                for res in fuzzy_results:
                                    item = QListWidgetItem(f"{res.cluster.title} — score {res.score:.2f} 🔍")
                                    item.setData(Qt.UserRole, getattr(res.cluster, 'cluster_id', None))
                                    item.setToolTip((res.cluster.summary or '')[:400])
                                    results_list.addItem(item)
                                print(f"✓ UI updated with {results_list.count()} fuzzy results")
                            except Exception as e:
                                import traceback
                                print(f"⚠ UI update error: {e}")
                                print(traceback.format_exc())

                        # Store reference to update function
                        panel._update_fuzzy = update_with_fuzzy_results

                        def run_fuzzy_search():
                            try:
                                print(f"🔍 Starting fuzzy search for: '{q}' (in background thread)")
                                fuzzy_searcher = ClusterSearcher(anthropic_client=self.anthropic_client, enable_fuzzy=True)
                                fuzzy_results = fuzzy_searcher.search(clusters, q, min_score=0.0, max_results=50)
                                print(f"✓ Fuzzy search completed for: '{q}' ({len(fuzzy_results)} results)")

                                # Update UI using the app's event loop from background thread
                                print(f"⏰ Invoking UI update on main thread")
                                QApplication.instance().postEvent(
                                    panel,
                                    QEvent(QEvent.User)
                                )
                                # Store results for the event handler
                                panel._pending_fuzzy_results = fuzzy_results
                                print(f"⏰ UI update event posted")
                            except Exception as e:
                                import traceback
                                print(f"⚠ Fuzzy search error: {e}")
                                print(traceback.format_exc())

                        # Run fuzzy search in background
                        print(f"📤 Submitting fuzzy search task to executor")
                        future = self._summary_executor.submit(run_fuzzy_search)
                        print(f"📤 Fuzzy search task submitted: {future}")

                search_edit.returnPressed.connect(do_search)

                # Click result -> switch to graph tab and select cluster
                def on_result_clicked(item):
                    cid = item.data(Qt.UserRole)
                    if cid is None:
                        return
                    # Switch to graph tab and select cluster
                    try:
                        self.tabs.setCurrentIndex(self.graph_tab_index)
                        self.graph_view.selected_cluster = cid
                        self.graph_view.update()
                    except Exception:
                        pass
                    panel.hide()

                results_list.itemClicked.connect(on_result_clicked)

                self._cluster_search_panel = panel

            # Position and show panel
            panel = self._cluster_search_panel
            # Place near top-left of graph view with a small margin
            panel.resize(420, 360)
            panel.move(20, 20)
            panel.show()
            panel.raise_()
            panel._search_edit.setFocus()

        except Exception as e:
            print(f"⚠ Failed to open cluster search panel: {e}")


    def get_cluster_title(self, cluster_id):
        """Return a title for the given cluster id by summarizing member pages.

        This method collects pages in the cluster, calls the ClusterSummarizer
        (if available) and returns a short title. Falls back to a simple label
        when summarization is unavailable or fails.
        """
        if cluster_id is None:
            return ""

        # Find node ids in this cluster from the graph view
        try:
            cluster_map = getattr(self.graph_view, 'cluster_map', {})
            node_ids = [nid for nid, cid in cluster_map.items() if cid == cluster_id]
        except Exception:
            node_ids = []

        if not node_ids:
            return f"Cluster {cluster_id}"

        # Build documents for summarizer and create cache key from URLs
        docs = []
        tabs = self.get_web_tabs()
        urls_for_key = []
        for nid in node_ids:
            td = tabs.get(nid)
            if not td:
                continue
            widget = td.get('widget')
            content = getattr(widget, 'page_content', '') if widget is not None else ''
            url = td.get('url', '')
            urls_for_key.append(url)
            docs.append({'url': url, 'title': td.get('title', ''), 'content': content})

        # Cache key includes URLs so it changes when tabs navigate
        key = tuple(sorted(urls_for_key))
        if key in self._cluster_summary_cache:
            return self._cluster_summary_cache[key].title

        if not docs or not self.cluster_summarizer:
            return f"Cluster {cluster_id}"
        # If a summary is already being computed, return placeholder
        with self._summary_lock:
            if key in self._summary_futures:
                return "Loading..."

            # Submit background job
            try:
                future = self._summary_executor.submit(self.cluster_summarizer.summarize_cluster, docs)
            except Exception as e:
                print(f"⚠ Failed to submit summarization task: {e}")
                return f"Cluster {cluster_id}"

            self._summary_futures[key] = future

            # Attach done callback
            def _done(fut, k=key):
                try:
                    summary = fut.result()
                except Exception as ex:
                    print(f"⚠ Cluster summarization task failed: {ex}")
                    with self._summary_lock:
                        self._summary_futures.pop(k, None)
                    return

                with self._summary_lock:
                    self._cluster_summary_cache[k] = summary
                    self._summary_futures.pop(k, None)

                # Schedule UI update on main thread using thread-safe method
                try:
                    app = QApplication.instance()
                    if app:
                        # Use invokeMethod to safely call from background thread
                        QMetaObject.invokeMethod(self.graph_view, "update", Qt.QueuedConnection)
                        # Also refresh search panel if open
                        QMetaObject.invokeMethod(self, "_refresh_search_panel", Qt.QueuedConnection)
                except Exception as e:
                    print(f"⚠ Error scheduling UI update: {e}")

            future.add_done_callback(_done)

        return "Loading..."

    def _refresh_search_panel(self):
        """Refresh search panel with updated cluster descriptions"""
        try:
            if self._cluster_search_panel is None or not self._cluster_search_panel.isVisible():
                return

            panel = self._cluster_search_panel
            if not hasattr(panel, '_current_query') or panel._current_query is None:
                return

            q = panel._current_query

            # Re-build clusters with updated descriptions
            tabs = self.get_web_tabs()
            tab_indices = list(tabs.keys())
            cluster_map = {}
            try:
                cluster_map = self.graph_view.compute_clusters(tabs, tab_indices, threshold=self.graph_view.cluster_threshold)
            except Exception:
                return

            groups = {}
            for nid, cid in cluster_map.items():
                groups.setdefault(cid, []).append(nid)

            clusters = []
            for cid, members in groups.items():
                title = self.get_cluster_title(cid)
                summary = self.get_cluster_description(cid)
                tags = self.get_cluster_tags(cid) or []
                urls = [tabs.get(nid, {}).get('url', '') for nid in members]
                doc_count = len(members)
                clusters.append(SimpleNamespace(title=title, summary=summary, tags=tags, urls=urls, doc_count=doc_count, cluster_id=cid))

            # Only update if descriptions have changed (not still "Loading...")
            if any(c.summary != "Loading..." for c in clusters):
                # Re-run keyword search with updated descriptions
                keyword_searcher = ClusterSearcher()
                try:
                    keyword_results = keyword_searcher.search(clusters, q, min_score=0.0, max_results=50)

                    # Update list if we have results
                    if keyword_results:
                        panel._results_list.clear()
                        for res in keyword_results:
                            item = QListWidgetItem(f"{res.cluster.title} — score {res.score:.2f}")
                            item.setData(Qt.UserRole, getattr(res.cluster, 'cluster_id', None))
                            item.setToolTip((res.cluster.summary or '')[:400])
                            panel._results_list.addItem(item)
                except Exception as e:
                    print(f"⚠ Search panel refresh error: {e}")
        except Exception as e:
            print(f"⚠ _refresh_search_panel error: {e}")

    def get_cluster_tags(self, cluster_id):
        """Return a list of tags for the given cluster id.

        Uses the same asynchronous summarization/caching strategy as the
        title/description methods. Returns a list when available or an
        empty list while loading / unavailable.
        """
        if cluster_id is None:
            return []

        try:
            cluster_map = getattr(self.graph_view, 'cluster_map', {})
            node_ids = [nid for nid, cid in cluster_map.items() if cid == cluster_id]
        except Exception:
            node_ids = []

        if not node_ids:
            return []

        # Build documents for summarizer and create cache key from URLs
        docs = []
        tabs = self.get_web_tabs()
        urls_for_key = []
        for nid in node_ids:
            td = tabs.get(nid)
            if not td:
                continue
            widget = td.get('widget')
            content = getattr(widget, 'page_content', '') if widget is not None else ''
            url = td.get('url', '')
            urls_for_key.append(url)
            docs.append({'url': url, 'title': td.get('title', ''), 'content': content})

        # Cache key includes URLs so it changes when tabs navigate
        key = tuple(sorted(urls_for_key))
        if key in self._cluster_summary_cache:
            return list(self._cluster_summary_cache[key].tags or [])

        if not docs or not self.cluster_summarizer:
            return []

        with self._summary_lock:
            if key in self._summary_futures:
                return []

            try:
                future = self._summary_executor.submit(self.cluster_summarizer.summarize_cluster, docs)
            except Exception as e:
                print(f"⚠ Failed to submit summarization task (tags): {e}")
                return []

            self._summary_futures[key] = future

            def _done(fut, k=key):
                try:
                    summary = fut.result()
                except Exception as ex:
                    print(f"⚠ Cluster summarization task failed: {ex}")
                    with self._summary_lock:
                        self._summary_futures.pop(k, None)
                    return

                with self._summary_lock:
                    self._cluster_summary_cache[k] = summary
                    self._summary_futures.pop(k, None)

                # Schedule UI update on main thread
                try:
                    QTimer.singleShot(0, lambda: self.graph_view.update())
                except Exception:
                    pass

            future.add_done_callback(_done)

        return []

    def get_cluster_description(self, cluster_id):
        """Return a paragraph description for the given cluster id.

        Delegates to the cluster summarizer and caches results.
        """
        if cluster_id is None:
            return ""

        try:
            cluster_map = getattr(self.graph_view, 'cluster_map', {})
            node_ids = [nid for nid, cid in cluster_map.items() if cid == cluster_id]
        except Exception:
            node_ids = []

        if not node_ids:
            return ""

        # Build documents for summarizer and create cache key from URLs
        docs = []
        tabs = self.get_web_tabs()
        urls_for_key = []
        for nid in node_ids:
            td = tabs.get(nid)
            if not td:
                continue
            widget = td.get('widget')
            content = getattr(widget, 'page_content', '') if widget is not None else ''
            url = td.get('url', '')
            urls_for_key.append(url)
            docs.append({'url': url, 'title': td.get('title', ''), 'content': content})

        # Cache key includes URLs so it changes when tabs navigate
        key = tuple(sorted(urls_for_key))
        if key in self._cluster_summary_cache:
            return self._cluster_summary_cache[key].summary

        if not docs or not self.cluster_summarizer:
            return "(No description available)"
        # If a summary is already being computed, return placeholder
        with self._summary_lock:
            if key in self._summary_futures:
                return "Loading..."

            # Submit background job
            try:
                future = self._summary_executor.submit(self.cluster_summarizer.summarize_cluster, docs)
            except Exception as e:
                print(f"⚠ Failed to submit summarization task: {e}")
                return "(No description available)"

            self._summary_futures[key] = future

            def _done(fut, k=key):
                try:
                    summary = fut.result()
                except Exception as ex:
                    print(f"⚠ Cluster summarization task failed: {ex}")
                    with self._summary_lock:
                        self._summary_futures.pop(k, None)
                    return

                with self._summary_lock:
                    self._cluster_summary_cache[k] = summary
                    self._summary_futures.pop(k, None)

                try:
                    QTimer.singleShot(0, lambda: self.graph_view.update())
                except Exception:
                    pass

            future.add_done_callback(_done)

        return "Loading..."
    
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
                # Get favicon from the web page
                icon = widget.web_view.icon()
                tabs[i] = {
                    'title': self.tabs.tabText(i),
                    'url': widget.web_view.url().toString(),
                    'content': content,
                    'widget': widget,
                    'icon': icon
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

    def precalculate_similarities(self):
        """Pre-calculate all similarities in background to populate cache"""
        if not self.anthropic_client:
            return  # No API, can't precalculate

        tabs = self.get_web_tabs()
        tab_indices = list(tabs.keys())

        if len(tab_indices) < 2:
            return

        # Submit background jobs to calculate all pairwise similarities
        def calculate_pair(idx1, idx2):
            try:
                url1 = tabs[idx1]['url']
                url2 = tabs[idx2]['url']
                # This will cache the result
                self.calculate_similarity(url1, url2)
            except Exception as e:
                print(f"⚠ Background similarity calculation error: {e}")

        # Use existing thread pool executor to calculate similarities
        for i, idx1 in enumerate(tab_indices):
            for idx2 in tab_indices[i+1:]:
                # Check if already cached
                url1 = tabs[idx1]['url']
                url2 = tabs[idx2]['url']
                cache_key = f"{min(url1, url2)}||{max(url1, url2)}"

                if cache_key not in self.similarity_cache:
                    # Submit background calculation
                    try:
                        self._summary_executor.submit(calculate_pair, idx1, idx2)
                    except Exception:
                        pass  # Executor might be full, that's OK

    def precalculate_cluster_summaries(self):
        """Pre-generate cluster summaries in background"""
        if not self.cluster_summarizer:
            return  # No summarizer available

        # Run clustering and summarization entirely in background thread
        def background_task():
            try:
                tabs = self.get_web_tabs()
                tab_indices = list(tabs.keys())

                if len(tab_indices) < 2:
                    return

                # Compute clusters (this may call calculate_similarity which can block)
                cluster_map = {}
                try:
                    cluster_map = self.graph_view.compute_clusters(tabs, tab_indices, threshold=self.graph_view.cluster_threshold)
                    # Store the cluster map on main thread
                    QTimer.singleShot(0, lambda cm=cluster_map: setattr(self.graph_view, 'cluster_map', cm))
                except Exception as e:
                    print(f"⚠ Error computing clusters: {e}")
                    return

                # Group nodes by cluster
                groups = {}
                for nid, cid in cluster_map.items():
                    groups.setdefault(cid, []).append(nid)

                # For each cluster, directly submit summarization tasks
                for cid, members in groups.items():
                    node_ids = sorted(members)

                    # Build documents for this cluster and create cache key from URLs
                    docs = []
                    urls_for_key = []
                    for nid in node_ids:
                        td = tabs.get(nid)
                        if not td:
                            continue
                        widget = td.get('widget')
                        content = getattr(widget, 'page_content', '') if widget is not None else ''
                        url = td.get('url', '')
                        urls_for_key.append(url)
                        docs.append({'url': url, 'title': td.get('title', ''), 'content': content})

                    # Cache key includes URLs so it changes when tabs navigate
                    key = tuple(sorted(urls_for_key))

                    # Skip if already cached or being computed
                    with self._summary_lock:
                        if key in self._cluster_summary_cache or key in self._summary_futures:
                            continue

                    if not docs:
                        continue

                    # Submit background summarization job
                    with self._summary_lock:
                        try:
                            print(f"📝 Starting summarization for cluster {cid} ({len(docs)} pages)")
                            future = self._summary_executor.submit(self.cluster_summarizer.summarize_cluster, docs)
                            self._summary_futures[key] = future

                            # Attach done callback
                            def _done(fut, k=key):
                                try:
                                    summary = fut.result()
                                except Exception as ex:
                                    print(f"⚠ Cluster summarization task failed: {ex}")
                                    with self._summary_lock:
                                        self._summary_futures.pop(k, None)
                                    return

                                with self._summary_lock:
                                    self._cluster_summary_cache[k] = summary
                                    self._summary_futures.pop(k, None)

                                print(f"✓ Cluster summary completed for {len(k)} pages")

                                # Schedule UI update on main thread using the application instance
                                # This ensures it runs on the main thread's event loop
                                try:
                                    app = QApplication.instance()
                                    if app:
                                        # Use invokeMethod to safely call from background thread
                                        from PyQt5.QtCore import QMetaObject, Q_ARG
                                        QMetaObject.invokeMethod(self.graph_view, "update", Qt.QueuedConnection)
                                        # Also refresh search panel if open
                                        QMetaObject.invokeMethod(self, "_refresh_search_panel", Qt.QueuedConnection)
                                except Exception as e:
                                    print(f"⚠ Error scheduling UI update: {e}")

                            future.add_done_callback(_done)
                        except Exception as e:
                            print(f"⚠ Failed to submit summarization task: {e}")

                print(f"🔄 Started background summarization for {len(groups)} clusters")
            except Exception as e:
                print(f"⚠ Error in background_task: {e}")

        # Submit the entire clustering+summarization task to background thread
        try:
            self._summary_executor.submit(background_task)
        except Exception as e:
            print(f"⚠ Failed to submit background clustering task: {e}")

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