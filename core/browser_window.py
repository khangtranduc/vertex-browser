from PyQt5.QtWidgets import (QMainWindow, QSplitter, QWidget, QVBoxLayout)
from PyQt5.QtCore import Qt
from ui.toolbar import NavigationToolbar
from ui.browser_tab import BrowserTab
from graph.graph_manager import GraphManager
from graph.graph_view import GraphView

class BrowserWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Graph Browser')
        self.setGeometry(100, 100, 1600, 900)
        
        # Initialize graph manager
        self.graph_manager = GraphManager()
        
        # Create main layout with splitter
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Toolbar
        self.toolbar = NavigationToolbar(self)
        layout.addWidget(self.toolbar)
        
        # Splitter for browser and graph view
        self.splitter = QSplitter(Qt.Horizontal)
        
        # Browser container
        self.browser_container = QWidget()
        self.browser_layout = QVBoxLayout(self.browser_container)
        self.browser_layout.setContentsMargins(0, 0, 0, 0)
        
        # Graph view
        self.graph_view = GraphView(self.graph_manager)
        self.graph_view.node_clicked.connect(self.on_graph_node_clicked)
        
        self.splitter.addWidget(self.browser_container)
        self.splitter.addWidget(self.graph_view)
        self.splitter.setSizes([1000, 600])
        
        layout.addWidget(self.splitter)
        
        # Current tab tracking
        self.current_tab = None
        self.tabs = {}  # node_id -> BrowserTab mapping
        
        # Create initial tab
        self.add_new_tab()
        
    def add_new_tab(self, url=None):
        """Create a new browser tab and add it to the graph"""
        tab = BrowserTab(self)
        
        if url:
            tab.navigate_to_url(url)
        
        # Add to graph
        node_id = self.graph_manager.add_node(
            tab=tab,
            url=tab.get_url(),
            title=tab.get_title()
        )
        
        # Store reference
        self.tabs[node_id] = tab
        tab.node_id = node_id
        
        # Connect signals
        tab.url_changed.connect(lambda url: self.on_tab_url_changed(node_id, url))
        tab.title_changed.connect(lambda title: self.on_tab_title_changed(node_id, title))
        
        # Switch to new tab
        self.switch_to_tab(node_id)
        
        return node_id
    
    def switch_to_tab(self, node_id):
        """Switch to a specific tab"""
        if node_id not in self.tabs:
            return
        
        # Hide current tab
        if self.current_tab and self.current_tab in self.tabs:
            self.tabs[self.current_tab].hide()
        
        # Show new tab
        tab = self.tabs[node_id]
        if tab.parent() is None:
            self.browser_layout.addWidget(tab)
        tab.show()
        
        self.current_tab = node_id
        
        # Update toolbar
        self.toolbar.url_bar.setText(tab.get_url())
        self.setWindowTitle(f'{tab.get_title()} - Graph Browser')
        
        # Highlight in graph
        self.graph_view.highlight_node(node_id)
    
    def close_tab(self, node_id):
        """Close a tab and remove from graph"""
        if node_id not in self.tabs:
            return
        
        # Remove from graph
        self.graph_manager.remove_node(node_id)
        
        # Remove widget
        tab = self.tabs[node_id]
        tab.deleteLater()
        del self.tabs[node_id]
        
        # Switch to another tab or create new one
        if len(self.tabs) == 0:
            self.add_new_tab()
        elif self.current_tab == node_id:
            next_id = next(iter(self.tabs.keys()))
            self.switch_to_tab(next_id)
    
    def on_tab_url_changed(self, node_id, url):
        """Handle URL change in tab"""
        self.graph_manager.update_node(node_id, url=url)
        if node_id == self.current_tab:
            self.toolbar.url_bar.setText(url)
    
    def on_tab_title_changed(self, node_id, title):
        """Handle title change in tab"""
        self.graph_manager.update_node(node_id, title=title)
        if node_id == self.current_tab:
            self.setWindowTitle(f'{title} - Graph Browser')
    
    def on_graph_node_clicked(self, node_id):
        """Handle click on graph node"""
        self.switch_to_tab(node_id)
    
    def navigate_to_url(self, url):
        """Navigate current tab to URL"""
        if self.current_tab and self.current_tab in self.tabs:
            self.tabs[self.current_tab].navigate_to_url(url)
