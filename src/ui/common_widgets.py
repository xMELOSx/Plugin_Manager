from PyQt6.QtWidgets import QLineEdit, QComboBox, QSpinBox
from PyQt6.QtCore import Qt

class StyledLineEdit(QLineEdit):
    """Standardized QLineEdit with project dark theme."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QLineEdit {
                background-color: #3b3b3b;
                color: #ffffff;
                border: 1px solid #555;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QLineEdit:hover {
                border-color: #3498db;
            }
            QLineEdit:focus {
                border-color: #3498db;
                background-color: #444;
            }
        """)

class StyledComboBox(QComboBox):
    """Premium QComboBox with a dedicated dropdown indicator area."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QComboBox {
                background-color: #3b3b3b;
                color: #ffffff;
                border: 1px solid #555;
                padding: 3px 25px 3px 6px;
                border-radius: 4px;
            }
            QComboBox:hover {
                border-color: #3498db;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 18px;
                background-color: #333;
                border: none;
                border-left: 1px solid #555;
            }
            QComboBox::down-arrow {
                image: none;
                border: none; /* Clear global CSS triangle */
                background: none;
            }
            /* Styling the internal list view */
            QComboBox QAbstractItemView {
                background-color: #3b3b3b;
                color: #ffffff;
                selection-background-color: #2980b9;
                selection-color: #ffffff;
                border: 1px solid #555;
                outline: none;
            }
        """)
    
    def paintEvent(self, event):
        """Override paintEvent to draw a custom triangle manually since QSS image is tricky."""
        super().paintEvent(event)
        from PyQt6.QtGui import QPainter, QPolygon, QBrush, QColor
        from PyQt6.QtCore import QPoint
        
        painter = QPainter(self)
        # Avoid drawing arrow if widget is too small
        if self.width() < 30:
            painter.end()
            return
            
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Calculate triangle position
        rect = self.rect()
        arrow_x = rect.width() - 9
        arrow_y = rect.height() // 2 + 1
        
        # Draw small triangle
        points = [
            QPoint(arrow_x - 4, arrow_y - 2),
            QPoint(arrow_x + 4, arrow_y - 2),
            QPoint(arrow_x, arrow_y + 3)
        ]
        
        painter.setPen(Qt.GlobalColor.transparent)
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawPolygon(QPolygon(points))
        painter.end()

class StyledSpinBox(QSpinBox):
    """Standardized QSpinBox with project dark theme."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QSpinBox {
                background-color: #3b3b3b;
                color: #ffffff;
                border: 1px solid #555;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QSpinBox:hover {
                border-color: #3498db;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #333;
                border-left: 1px solid #555;
                width: 20px;
            }
            QSpinBox::up-button { border-top-right-radius: 4px; }
            QSpinBox::down-button { border-bottom-right-radius: 4px; }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #444;
            }
            QSpinBox::up-arrow, QSpinBox::down-arrow {
                width: 7px;
                height: 7px;
            }
        """)
