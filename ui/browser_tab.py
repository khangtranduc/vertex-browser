from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, pyqtSignal
from PyQt5.QtWidgets import QWidget, QVBoxLayout

class BrowserTab(QWidget):
    """Individual browser tab widget"""
    
    url_changed = pyqtSignal(str)
    title_changed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.node_id = None
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl('https://www.google.com'))
        layout.addWidget(self.browser)
        
        # Connect signals
        self.browser.urlChanged.connect(self._on_url_changed)
        self.browser.titleChanged.connect(self._on_title_changed)
        self.browser.loadFinished.connect(self._on_load_finished)
    
    def navigate_to_url(self, url):
        """Navigate to a URL"""
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        self.browser.setUrl(QUrl(url))
    
    def get_url(self):
        """Get current URL"""
        return self.browser.url().toString()
    
    def get_title(self):
        """Get current page title"""
        title = self.browser.title()
        return title if title else "New Tab"
    
    def back(self):
        self.browser.back()
    
    def forward(self):
        self.browser.forward()
    
    def reload(self):
        self.browser.reload()
    
    def _on_url_changed(self, url):
        self.url_changed.emit(url.toString())
    
    def _on_title_changed(self, title):
        self.title_changed.emit(title)
    
    def _on_load_finished(self, success):
        """Extract page content when load finishes"""
        if success and self.parent():
            # You can extract page content here for similarity analysis
            # self.browser.page().toHtml(self._on_html_ready)
            pass
    
    def _on_html_ready(self, html):
        """Called when HTML content is ready"""
        # Update node content in graph manager
        if self.parent() and hasattr(self.parent(), 'graph_manager'):
            self.parent().graph_manager.update_node(self.node_id, content=html)