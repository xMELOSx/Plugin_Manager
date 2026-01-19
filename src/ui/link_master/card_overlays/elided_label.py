from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontMetrics, QAction
from src.ui.common_widgets import StandardEditMenu


class ElidedLabel(QLabel):
    """Label that automatically elides text with '...' when it doesn't fit."""
    
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._full_text = text
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
    
    def setText(self, text: str):
        """Set the full text and update display."""
        self._full_text = text
        self._updateElidedText()
    
    def text(self) -> str:
        """Return the full (non-elided) text."""
        return self._full_text
    
    def resizeEvent(self, event):
        """Re-elide text when widget is resized."""
        super().resizeEvent(event)
        self._updateElidedText()
    
    def setWrapMode(self, wrap: bool):
        """Enable or disable text wrapping."""
        self._wrap = wrap
        self.setWordWrap(wrap)
        if wrap:
            # When wrapping is on, show full text and let Qt handle wrapping
            super().setText(self._full_text)
        else:
            # When wrapping is off, enforce single line elision
            self._updateElidedText()

    def _updateElidedText(self):
        """Calculate and set the elided text based on current width."""
        if getattr(self, '_wrap', False):
            # If wrapping is enabled, do nothing (Qt handles it)
            super().setText(self._full_text)
            return

        if not self._full_text:
            super().setText("")
            return
        
        metrics = QFontMetrics(self.font())
        available_width = self.width() - 4  # Small margin
        
        if available_width <= 0:
            super().setText(self._full_text)
            return
        
        elided = metrics.elidedText(
            self._full_text, 
            Qt.TextElideMode.ElideMiddle, 
            available_width
        )
        super().setText(elided)
    
    def fullText(self) -> str:
        """Return the full (non-elided) text."""
        return self._full_text
    def contextMenuEvent(self, event):
        """Show context menu with copy option."""
        menu = StandardEditMenu(self)
        menu.exec(event.globalPos())
