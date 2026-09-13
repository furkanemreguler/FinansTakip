"""
Finans Takip - Uygulama giriş noktası.
Çalıştırmak için: python main.py
"""
import sys
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtGui import QFont

from db import init_db
from ui.app_shell import AppShell
from ui.theme import LIGHT, DARK, build_stylesheet


class MainWindow(QMainWindow):
    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.setWindowTitle("Finans Takip")
        self.resize(1200, 800)

        self.shell = AppShell()
        self.shell.theme_changed.connect(self._apply_theme)
        self.setCentralWidget(self.shell)

        self._apply_theme("light")

    def _apply_theme(self, mode: str):
        theme = DARK if mode == "dark" else LIGHT
        self.app.setStyleSheet(build_stylesheet(theme))


def main():
    init_db()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Geist"))  # sistemde yoksa Qt otomatik sans-serif'e düşer

    window = MainWindow(app)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()