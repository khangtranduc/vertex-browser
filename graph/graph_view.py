from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QSlider, QLabel, QHBoxLayout
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPointF
from PyQt5.QtGui import QPainter, QColor, QPen, QFont
import networkx as nx
import math

class GraphView(QWidget):
    """Interactive graph visualization widget"""
    
    node_clicked = pyqtSignal(str)  # Emitted when a node is clicked
    
    def __init__(self, graph_manager):
        super().__init__()
        self.graph_manager = graph_manager
        self.graph_manager.graph_changed.connect(self.update_layout)
        
        # Layout
        layout = QVBoxLayout(self)
        
        # Controls
        controls = QHBoxLayout()
        
        self.threshold_label = QLabel("Edge Threshold: 0.3")
        controls.addWidget(self.threshold_label)
        
        self.threshold_slider = QSlider(Qt.Horizontal)
        self.threshold_slider.setMinimum(0)
        self.threshold_slider.setMaximum(100)
        self.threshold_slider.setValue(30)
        self.threshold_slider.valueChanged.connect(self.on_threshold_changed)
        controls.addWidget(self.threshold_slider)
        
        self.reset_btn = QPushButton("Reset Layout")
        self.reset_btn.clicked.connect(self.reset_layout)
        controls.addWidget(self.reset_btn)
        
        layout.addLayout(controls)
        
        # Graph positions
        self.positions = {}  # node_id -> QPointF
        self.velocities = {}  # node_id -> QPointF
        self.highlighted_node = None
        
        # Physics simulation
        self.simulation_timer = QTimer()
        self.simulation_timer.timeout.connect(self.step_simulation)
        self.simulation_timer.start(16)  # ~60 FPS
        
        # Interaction
        self.dragging_node = None
        self.offset = QPointF()
        
        self.setMinimumSize(400, 400)
        self.update_layout()
    
    def on_threshold_changed(self, value):
        """Handle threshold slider change"""
        threshold = value / 100.0
        self.threshold_label.setText(f"Edge Threshold: {threshold:.2f}")
        self.graph_manager.set_edge_threshold(threshold)
    
    def reset_layout(self):
        """Reset node positions"""
        self.positions.clear()
        self.velocities.clear()
        self.update_layout()
    
    def update_layout(self):
        """Update graph layout"""
        graph = self.graph_manager.get_graph()
        
        # Initialize positions for new nodes
        for node_id in graph.nodes():
            if node_id not in self.positions:
                # Random initial position
                import random
                x = random.uniform(50, self.width() - 50)
                y = random.uniform(50, self.height() - 50)
                self.positions[node_id] = QPointF(x, y)
                self.velocities[node_id] = QPointF(0, 0)
        
        # Remove positions for deleted nodes
        to_remove = [nid for nid in self.positions if nid not in graph.nodes()]
        for nid in to_remove:
            del self.positions[nid]
            del self.velocities[nid]
        
        self.update()
    
    def step_simulation(self):
        """Physics-based force-directed layout step"""
        graph = self.graph_manager.get_graph()
        if len(graph.nodes()) == 0:
            return
        
        # Parameters
        repulsion = 5000
        attraction = 0.01
        damping = 0.8
        
        center = QPointF(self.width() / 2, self.height() / 2)
        
        # Calculate forces
        forces = {node_id: QPointF(0, 0) for node_id in graph.nodes()}
        
        # Repulsion between all nodes
        nodes = list(graph.nodes())
        for i, node1 in enumerate(nodes):
            for node2 in nodes[i+1:]:
                pos1 = self.positions[node1]
                pos2 = self.positions[node2]
                
                delta = pos1 - pos2
                distance = math.sqrt(delta.x()**2 + delta.y()**2) + 0.1
                
                force_magnitude = repulsion / (distance * distance)
                force = QPointF(delta.x() / distance * force_magnitude,
                              delta.y() / distance * force_magnitude)
                
                forces[node1] += force
                forces[node2] -= force
        
        # Attraction along edges
        for edge in graph.edges(data=True):
            node1, node2, data = edge
            pos1 = self.positions[node1]
            pos2 = self.positions[node2]
            
            delta = pos2 - pos1
            distance = math.sqrt(delta.x()**2 + delta.y()**2) + 0.1
            
            weight = data.get('weight', 0.5)
            force_magnitude = distance * attraction * weight
            force = QPointF(delta.x() / distance * force_magnitude,
                          delta.y() / distance * force_magnitude)
            
            forces[node1] += force
            forces[node2] -= force
        
        # Center gravity
        for node_id in graph.nodes():
            delta = center - self.positions[node_id]
            forces[node_id] += delta * 0.001
        
        # Update positions
        for node_id in graph.nodes():
            if node_id == self.dragging_node:
                continue
            
            self.velocities[node_id] += forces[node_id]
            self.velocities[node_id] *= damping
            
            self.positions[node_id] += self.velocities[node_id]
            
            # Keep within bounds
            pos = self.positions[node_id]
            margin = 30
            pos.setX(max(margin, min(self.width() - margin, pos.x())))
            pos.setY(max(margin, min(self.height() - margin, pos.y())))
        
        self.update()
    
    def highlight_node(self, node_id):
        """Highlight a specific node"""
        self.highlighted_node = node_id
        self.update()
    
    def paintEvent(self, event):
        """Draw the graph"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Background
        painter.fillRect(self.rect(), QColor(30, 30, 30))
        
        graph = self.graph_manager.get_graph()
        
        # Draw edges
        for edge in graph.edges(data=True):
            node1, node2, data = edge
            if node1 not in self.positions or node2 not in self.positions:
                continue
            
            pos1 = self.positions[node1]
            pos2 = self.positions[node2]
            
            weight = data.get('weight', 0.5)
            
            # Edge appearance based on weight
            pen = QPen(QColor(100, 100, 200, int(100 + weight * 155)))
            pen.setWidth(int(1 + weight * 3))
            painter.setPen(pen)
            
            painter.drawLine(pos1.toPoint(), pos2.toPoint())
        
        # Draw nodes
        font = QFont("Arial", 9)
        painter.setFont(font)
        
        for node_id in graph.nodes():
            if node_id not in self.positions:
                continue
            
            pos = self.positions[node_id]
            node_data = self.graph_manager.get_node_data(node_id)
            
            # Node size based on connections
            degree = graph.degree(node_id)
            radius = 15 + degree * 3
            
            # Node color
            if node_id == self.highlighted_node:
                color = QColor(100, 200, 100)
            else:
                color = QColor(80, 120, 200)
            
            # Draw node
            painter.setBrush(color)
            painter.setPen(QPen(QColor(200, 200, 200), 2))
            painter.drawEllipse(pos.toPoint(), radius, radius)
            
            # Draw title
            title = node_data.get('title', 'New Tab')[:20]
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(int(pos.x() - 40), int(pos.y() + radius + 15), title)
    
    def mousePressEvent(self, event):
        """Handle mouse press"""
        graph = self.graph_manager.get_graph()
        
        for node_id in graph.nodes():
            if node_id not in self.positions:
                continue
            
            pos = self.positions[node_id]
            distance = math.sqrt((event.pos().x() - pos.x())**2 + 
                               (event.pos().y() - pos.y())**2)
            
            if distance < 20:
                if event.button() == Qt.LeftButton:
                    self.dragging_node = node_id
                    self.offset = event.pos() - pos.toPoint()
                    self.node_clicked.emit(node_id)
                return
    
    def mouseMoveEvent(self, event):
        """Handle mouse move"""
        if self.dragging_node:
            self.positions[self.dragging_node] = QPointF(event.pos() - self.offset)
            self.velocities[self.dragging_node] = QPointF(0, 0)
            self.update()
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        self.dragging_node = None