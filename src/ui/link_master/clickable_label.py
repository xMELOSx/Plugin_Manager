from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import pyqtSignal, Qt

class ClickableLabel(QLabel):
    """A QLabel that emits a clicked signal when clicked with the left mouse button."""
    clicked = pyqtSignal()

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
