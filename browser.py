import sys
from PyQt5.QtCore import QUrl, Qt, QPointF
from PyQt5.QtGui import QPainter, QPen, QColor, QFont, QBrush
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QVBoxLayout, 
                             QHBoxLayout, QWidget, QLineEdit, QPushButton, QLabel)
from PyQt5.QtWebEngineWidgets import QWebEngineView
import math

class GraphView(QWidget):
    """Widget that displays a graph visualization of browser tabs"""
    
    def __init__(self, browser):
        super().__init__()
        self.browser = browser
        self.node_positions = {}
        self.setMinimumSize(800, 600)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Get all non-graph tabs
        tabs = self.browser.get_web_tabs()
        
        if not tabs:
            painter.setPen(QPen(Qt.black))
            painter.setFont(QFont('Arial', 12))
            painter.drawText(self.rect(), Qt.AlignCenter, 
                           "No tabs to display\nOpen some web pages to see the graph")
            return
        
        # Calculate node positions in a circle
        center_x = self.width() / 2
        center_y = self.height() / 2
        radius = min(self.width(), self.height()) / 3
        
        for i, (idx, tab_data) in enumerate(tabs.items()):
            angle = 2 * math.pi * i / len(tabs)
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            self.node_positions[idx] = (x, y)
        
        # Draw edges (connections between tabs)
        painter.setPen(QPen(QColor(150, 150, 150), 2))
        for i, idx1 in enumerate(tabs.keys()):
            for idx2 in list(tabs.keys())[i+1:]:
                similarity = self.browser.calculate_similarity(
                    tabs[idx1]['url'], tabs[idx2]['url']
                )
                
                # Draw edge if similarity exceeds threshold
                if similarity > 0.3:
                    x1, y1 = self.node_positions[idx1]
                    x2, y2 = self.node_positions[idx2]
                    
                    # Line thickness based on similarity
                    thickness = int(1 + similarity * 5)
                    alpha = int(50 + similarity * 200)
                    painter.setPen(QPen(QColor(100, 100, 200, alpha), thickness))
                    painter.drawLine(int(x1), int(y1), int(x2), int(y2))
                    
                    # Draw similarity score at midpoint
                    mid_x = (x1 + x2) / 2
                    mid_y = (y1 + y2) / 2
                    painter.setFont(QFont('Arial', 8))
                    painter.setPen(QPen(QColor(100, 100, 200)))
                    painter.drawText(int(mid_x), int(mid_y), f"{similarity:.2f}")
        
        # Draw nodes
        for idx, (x, y) in self.node_positions.items():
            tab_data = tabs[idx]
            
            # Node circle
            painter.setBrush(QBrush(QColor(70, 130, 180)))
            painter.setPen(QPen(QColor(50, 80, 130), 3))
            painter.drawEllipse(QPointF(x, y), 30, 30)
            
            # Tab title
            painter.setPen(QPen(Qt.black))
            painter.setFont(QFont('Arial', 10, QFont.Bold))
            title = tab_data['title'][:20] + '...' if len(tab_data['title']) > 20 else tab_data['title']
            
            # Draw title below node
            text_rect = painter.boundingRect(0, 0, 200, 50, Qt.AlignCenter, title)
            text_rect.moveCenter(QPointF(x, y + 50).toPoint())
            
            # Background for text
            painter.setBrush(QBrush(QColor(255, 255, 255, 200)))
            painter.setPen(QPen(Qt.NoPen))
            painter.drawRect(text_rect.adjusted(-5, -2, 5, 2))
            
            # Text
            painter.setPen(QPen(Qt.black))
            painter.drawText(text_rect, Qt.AlignCenter, title)
    
    def mousePressEvent(self, event):
        """Handle clicks on nodes to switch to that tab"""
        pos = event.pos()
        for idx, (x, y) in self.node_positions.items():
            distance = math.sqrt((pos.x() - x)**2 + (pos.y() - y)**2)
            if distance <= 30:
                self.browser.tabs.setCurrentIndex(idx)
                break


class BrowserTab(QWidget):
    """Individual browser tab with address bar and web view"""
    
    def __init__(self):
        super().__init__()
        self.web_view = QWebEngineView()
        
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
    
    def on_load_finished(self):
        # Trigger graph update when page loads
        if hasattr(self.parent(), 'update_graph'):
            self.parent().update_graph()


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
        self.graph_tab_index = self.tabs.addTab(self.graph_view, '📊 Graph View')
        
        # Connect tab changed signal after graph_tab_index is set
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        # Add new tab button
        new_tab_btn = QPushButton('+')
        new_tab_btn.clicked.connect(self.add_new_tab)
        self.tabs.setCornerWidget(new_tab_btn)
        
        self.setCentralWidget(self.tabs)
        
        # Add first browser tab
        self.add_new_tab()
    
    def add_new_tab(self, url='https://www.google.com'):
        """Add a new browser tab"""
        browser_tab = BrowserTab()
        browser_tab.parent = lambda: self  # Allow tab to access browser
        
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
    
    def get_web_tabs(self):
        """Get all web tabs (excluding graph view)"""
        tabs = {}
        for i in range(self.tabs.count()):
            if i == self.graph_tab_index:
                continue
            
            widget = self.tabs.widget(i)
            if isinstance(widget, BrowserTab):
                tabs[i] = {
                    'title': self.tabs.tabText(i),
                    'url': widget.web_view.url().toString(),
                    'widget': widget
                }
        return tabs
    
    def calculate_similarity(self, url1, url2):
        """
        Calculate similarity between two tabs based on their URLs.
        This is a placeholder implementation - users can replace this with
        more sophisticated similarity metrics like:
        - Content-based similarity (TF-IDF, embeddings)
        - Domain similarity
        - Topic modeling
        - User browsing patterns
        """
        # Simple domain-based similarity
        try:
            domain1 = QUrl(url1).host()
            domain2 = QUrl(url2).host()
            
            # Same domain = high similarity
            if domain1 == domain2:
                return 0.9
            
            # Same top-level domain = medium similarity
            tld1 = '.'.join(domain1.split('.')[-2:]) if '.' in domain1 else domain1
            tld2 = '.'.join(domain2.split('.')[-2:]) if '.' in domain2 else domain2
            
            if tld1 == tld2:
                return 0.5
            
            # Check for common keywords
            keywords1 = set(domain1.lower().split('.'))
            keywords2 = set(domain2.lower().split('.'))
            common = keywords1.intersection(keywords2)
            
            if common:
                return 0.4
            
            return 0.1  # Low default similarity
            
        except:
            return 0.0
    
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