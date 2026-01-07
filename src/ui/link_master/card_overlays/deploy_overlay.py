from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QPainter, QFont, QIcon
from src.core.lang_manager import _


class DeployOverlay(QPushButton):
    """Deploy status button overlay with cached emoji rendering."""
    
    # Class-level pixmap cache to avoid re-rendering emojis
    _emoji_cache = {}
    
    @classmethod
    def _get_emoji_pixmap(cls, emoji: str, size: int = 16) -> QPixmap:
        """Get or create a cached pixmap for an emoji."""
        key = (emoji, size)
        if key not in cls._emoji_cache:
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            # Use a font known to support emojis
            font = QFont("Segoe UI Emoji", size - 4)
            painter.setFont(font)
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, emoji)
            painter.end()
            cls._emoji_cache[key] = pixmap
        return cls._emoji_cache[key]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(24, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("overlay_deploy")
        self._current_status = 'none'
        self.hide()
    
    def setStatus(self, link_status: str, opacity: float = 0.8):
        """Update button appearance based on link status."""
        self._current_status = link_status
        
        if link_status in ('linked', 'partial'):
            icon_pixmap = self._get_emoji_pixmap("🔗", 16)
            base_color = f"rgba(39, 174, 96, {opacity})"
            hover_color = "rgba(46, 204, 113, 0.95)"
            border_color = "#1e8449"
            self.setToolTip(_("Linked (Unlink)") if link_status == 'linked' else _("Partially Linked (Unlink)"))
        elif link_status == 'conflict':
            icon_pixmap = self._get_emoji_pixmap("⚠", 16)
            base_color = f"rgba(231, 76, 60, {opacity})"
            hover_color = "rgba(241, 100, 85, 0.95)"
            border_color = "#943126"
            self.setToolTip(_("Conflict (Occupy)"))
        else:
            icon_pixmap = self._get_emoji_pixmap("🚀", 16)
            base_color = f"rgba(52, 152, 219, {opacity})"
            hover_color = "rgba(93, 173, 226, 0.95)"
            border_color = "#2471a3"
            self.setToolTip(_("Not Linked (Deploy)"))

        self.setIcon(QIcon(icon_pixmap))
        self.setIconSize(QSize(16, 16))
        self.setText("")

        style = f"""
            QPushButton {{ 
                background-color: {base_color}; 
                color: white; 
                border-radius: 12px; 
                border: 1px solid {border_color}; 
            }}
            QPushButton:hover {{ 
                background-color: {hover_color}; 
            }}
        """
        self.setStyleSheet(style)
