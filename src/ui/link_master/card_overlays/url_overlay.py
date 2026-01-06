from PyQt6.QtWidgets import QPushButton, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QPainter, QFont, QIcon
from src.core.lang_manager import _
from .overlay_position_mixin import OverlayPositionMixin


class UrlOverlay(OverlayPositionMixin, QPushButton):
    """URL button overlay for opening related URLs. Auto-positions to top-right."""
    
    # Class-level pixmap cache
    _url_pixmap = None
    
    @classmethod
    def _get_url_pixmap(cls) -> QPixmap:
        """Get or create the cached URL emoji pixmap."""
        if cls._url_pixmap is None:
            size = 18
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            font = QFont("Segoe UI Emoji", 12)
            painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "🌐")
            painter.end()
            cls._url_pixmap = pixmap
        return cls._url_pixmap
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(24, 24)
        self.setObjectName("overlay_url")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(_("Open related URL"))
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.7)
        self.setGraphicsEffect(self._opacity_effect)
        self.setPositionMode('top_right', margin=6)
        self.setIcon(QIcon(self._get_url_pixmap()))
        self.setIconSize(QSize(18, 18))
        self._applyStyle()
        self.hide()
    
    def setOpacity(self, opacity: float):
        """Set the button opacity (0.0 to 1.0)."""
        self._opacity_effect.setOpacity(opacity)
    
    def _applyStyle(self):
        self.setStyleSheet("""
            QPushButton { 
                background-color: rgba(40, 40, 40, 0.85); 
                border-radius: 4px; 
                border: 1px solid rgba(255,255,255,0.1);
                padding: 0px;
                margin: 0px;
            }
            QPushButton:hover { 
                background-color: rgba(60, 60, 60, 0.95); 
                border: 1px solid rgba(255,255,255,0.3);
            }
        """)

