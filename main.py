import sys
from PyQt5.QtWidgets import QApplication
from core.browser_window import BrowserWindow

def main():
    app = QApplication(sys.argv)
    app.setApplicationName('Graph Browser')
    
    window = BrowserWindow()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()