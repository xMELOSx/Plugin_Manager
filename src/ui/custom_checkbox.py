from PyQt6.QtWidgets import QCheckBox

class CustomCheckBox(QCheckBox):
    """
    Standard dark-themed QCheckBox for use throughout the application.
    Inherits from QCheckBox and applies consistent styling.
    """
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("""
            QCheckBox {
                color: #ddd;
                font-size: 11px;
                spacing: 8px;
                padding: 4px;
            }
            QCheckBox:hover {
                color: #fff;
                background-color: rgba(255, 255, 255, 0.05);
                border-radius: 4px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #555;
                background: #3b3b3b;
                border-radius: 3px;
            }
            QCheckBox::indicator:unchecked:hover {
                border-color: #3498db;
            }
            QCheckBox::indicator:checked {
                background: #3498db;
                border: 2px solid #3498db;
            }
        """)
