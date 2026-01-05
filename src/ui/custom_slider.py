from PyQt6.QtWidgets import QSlider
from PyQt6.QtCore import Qt

class CustomSlider(QSlider):
    """
    Standard dark-themed QSlider for use throughout the application.
    Features a consistent blue handle and track that persists even when the window loses focus.
    """
    def __init__(self, orientation=Qt.Orientation.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: #333;
                border: 1px solid #444;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #3498db;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal:!active {
                background: #3498db;
            }
            QSlider::add-page:horizontal {
                background: #2b2b2b;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 1px solid #bbb;
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 3px;
            }
            QSlider::handle:horizontal:hover {
                background: #f8f8f8;
                border-color: #fff;
            }
            QSlider::handle:horizontal:!active {
                background: #ffffff;
            }
            
            QSlider::sub-page:horizontal:disabled {
                background: #555;
            }
            QSlider::handle:horizontal:disabled {
                background: #777;
                border-color: #555;
            }
        """)
