import sys
from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import (QApplication, QMainWindow, QToolBar, 
                             QLineEdit, QAction, QTabWidget, QWidget, QVBoxLayout)
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtGui import QIcon

class BrowserTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl('https://www.google.com'))
        
        # Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.browser)
        self.setLayout(layout)
        
        # Connect signals
        self.browser.urlChanged.connect(self.update_url)
        self.browser.loadFinished.connect(self.on_load_finished)
        
    def update_url(self, url):
        if self.parent() and hasattr(self.parent().parent(), 'url_bar'):
            if self.parent().parent().tabs.currentWidget() == self:
                self.parent().parent().url_bar.setText(url.toString())
                self.parent().parent().url_bar.setCursorPosition(0)
    
    def on_load_finished(self, success):
        if self.parent() and hasattr(self.parent().parent(), 'update_title'):
            if self.parent().parent().tabs.currentWidget() == self:
                self.parent().parent().update_title()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('PyQt Web Browser')
        self.setGeometry(100, 100, 1200, 800)
        
        # Create tab widget
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.current_tab_changed)
        self.setCentralWidget(self.tabs)
        
        # Create navigation toolbar
        navbar = QToolBar()
        self.addToolBar(navbar)
        
        # Back button
        back_btn = QAction('←', self)
        back_btn.triggered.connect(self.navigate_back)
        navbar.addAction(back_btn)
        
        # Forward button
        forward_btn = QAction('→', self)
        forward_btn.triggered.connect(self.navigate_forward)
        navbar.addAction(forward_btn)
        
        # Reload button
        reload_btn = QAction('⟳', self)
        reload_btn.triggered.connect(self.reload_page)
        navbar.addAction(reload_btn)
        
        # Home button
        home_btn = QAction('⌂', self)
        home_btn.triggered.connect(self.navigate_home)
        navbar.addAction(home_btn)
        
        # URL bar
        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        navbar.addWidget(self.url_bar)
        
        # New tab button
        new_tab_btn = QAction('+', self)
        new_tab_btn.triggered.connect(self.add_new_tab)
        navbar.addAction(new_tab_btn)
        
        # Add initial tab
        self.add_new_tab()
        
    def add_new_tab(self, url=None):
        tab = BrowserTab(self.tabs)
        
        if url:
            tab.browser.setUrl(QUrl(url))
        
        index = self.tabs.addTab(tab, 'New Tab')
        self.tabs.setCurrentIndex(index)
        
        # Update title when page title changes
        tab.browser.titleChanged.connect(lambda title: self.update_tab_title(tab, title))
        
    def close_tab(self, index):
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)
        else:
            self.close()
    
    def current_tab_changed(self, index):
        if index >= 0:
            current_tab = self.tabs.currentWidget()
            if current_tab:
                url = current_tab.browser.url()
                self.url_bar.setText(url.toString())
                self.url_bar.setCursorPosition(0)
                self.update_title()
    
    def update_tab_title(self, tab, title):
        index = self.tabs.indexOf(tab)
        if index >= 0:
            # Truncate long titles
            display_title = title[:20] + '...' if len(title) > 20 else title
            self.tabs.setTabText(index, display_title)
            if self.tabs.currentWidget() == tab:
                self.update_title()
    
    def update_title(self):
        current_tab = self.tabs.currentWidget()
        if current_tab:
            title = current_tab.browser.page().title()
            self.setWindowTitle(f'{title} - PyQt Browser')
    
    def navigate_back(self):
        current_tab = self.tabs.currentWidget()
        if current_tab:
            current_tab.browser.back()
    
    def navigate_forward(self):
        current_tab = self.tabs.currentWidget()
        if current_tab:
            current_tab.browser.forward()
    
    def reload_page(self):
        current_tab = self.tabs.currentWidget()
        if current_tab:
            current_tab.browser.reload()
    
    def navigate_home(self):
        current_tab = self.tabs.currentWidget()
        if current_tab:
            current_tab.browser.setUrl(QUrl('https://www.google.com'))
    
    def navigate_to_url(self):
        url = self.url_bar.text()
        current_tab = self.tabs.currentWidget()
        
        if current_tab:
            # Add http:// if no protocol specified
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            current_tab.browser.setUrl(QUrl(url))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setApplicationName('PyQt Web Browser')
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())