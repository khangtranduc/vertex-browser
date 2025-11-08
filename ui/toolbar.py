from PyQt5.QtWidgets import QToolBar, QLineEdit, QAction
from PyQt5.QtCore import Qt

class NavigationToolbar(QToolBar):
    """Navigation toolbar with URL bar and controls"""
    
    def __init__(self, browser_window):
        super().__init__()
        self.browser_window = browser_window
        
        # Back button
        back_btn = QAction('←', self)
        back_btn.triggered.connect(self.navigate_back)
        self.addAction(back_btn)
        
        # Forward button
        forward_btn = QAction('→', self)
        forward_btn.triggered.connect(self.navigate_forward)
        self.addAction(forward_btn)
        
        # Reload button
        reload_btn = QAction('⟳', self)
        reload_btn.triggered.connect(self.reload_page)
        self.addAction(reload_btn)
        
        # URL bar
        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        self.addWidget(self.url_bar)
        
        # New tab button
        new_tab_btn = QAction('+', self)
        new_tab_btn.triggered.connect(self.browser_window.add_new_tab)
        self.addAction(new_tab_btn)
    
    def navigate_back(self):
        if self.browser_window.current_tab:
            tab = self.browser_window.tabs.get(self.browser_window.current_tab)
            if tab:
                tab.back()
    
    def navigate_forward(self):
        if self.browser_window.current_tab:
            tab = self.browser_window.tabs.get(self.browser_window.current_tab)
            if tab:
                tab.forward()
    
    def reload_page(self):
        if self.browser_window.current_tab:
            tab = self.browser_window.tabs.get(self.browser_window.current_tab)
            if tab:
                tab.reload()
    
    def navigate_to_url(self):
        url = self.url_bar.text()
        self.browser_window.navigate_to_url(url)