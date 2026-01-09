from PyQt6.QtWidgets import QLineEdit, QComboBox, QSpinBox, QPushButton
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

class StyledButton(QPushButton):
    """
    Standardized QPushButton with premium hover effects and pointing hand cursor.
    Supports 'Gray', 'Blue', 'Green' style presets.
    """
    def __init__(self, text, parent=None, style_type="Gray"):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.style_type = style_type
        self._apply_style()

    def _apply_style(self):
        # Color Map
        colors = {
            "Gray":  {"bg": "#3b3b3b", "hover": "#4a4a4a", "border": "#555", "hover_border": "#777"},
            "Blue":  {"bg": "#2980b9", "hover": "#3498db", "border": "#3498db", "hover_border": "#fff"},
            "Green": {"bg": "#27ae60", "hover": "#2ecc71", "border": "#2ecc71", "hover_border": "#fff"},
            "Red":   {"bg": "#c0392b", "hover": "#e74c3c", "border": "#e74c3c", "hover_border": "#fff"}
        }
        
        c = colors.get(self.style_type, colors["Gray"])
        
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['bg']};
                color: #ffffff;
                border: 1px solid {c['border']};
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {c['hover']};
                border-color: {c['hover_border']};
            }}
            QPushButton:pressed {{
                background-color: #222;
                padding-top: 7px;
                padding-left: 13px;
            }}
            QPushButton:disabled {{
                background-color: #2c2c2c;
                color: #555;
                border-color: #333;
            }}
        """)

    def set_style_type(self, style_type: str):
        self.style_type = style_type
        self._apply_style()
