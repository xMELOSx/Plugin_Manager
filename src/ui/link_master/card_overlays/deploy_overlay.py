from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QPainter, QFont, QIcon, QColor, QPen
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
        self._current_pixmap = None
        self.hide()
    
    def setStatus(self, link_status: str, opacity: float = 0.8, is_category: bool = False, has_conflict: bool = False):
        """Update button appearance based on link status."""
        self._current_status = link_status
        
        if link_status == 'linked':
            icon_pixmap = self._get_emoji_pixmap("🔗", 16)
            self._base_color = QColor(39, 174, 96, int(255 * opacity))
            self._hover_color = QColor(46, 204, 113, 242) # 0.95 * 255
            self._border_color = QColor("#1e8449")
            self.setToolTip(_("Linked (Unlink)"))
        elif link_status == 'partial':
            icon_pixmap = self._get_emoji_pixmap("⚠", 16)
            self._base_color = QColor("#f39c12")
            self._base_color.setAlpha(int(255 * opacity))
            self._hover_color = QColor("#f1c40f")
            self._hover_color.setAlpha(242)
            self._border_color = QColor("#d68910")
            self.setToolTip(_("Partial Deployment (Repair)"))
        elif link_status == 'conflict':
            icon_pixmap = self._get_emoji_pixmap("⚠", 16)
            self._base_color = QColor(231, 76, 60, int(255 * opacity))
            self._hover_color = QColor(241, 100, 85, 242)
            self._border_color = QColor("#943126")
            self.setToolTip(_("Conflict (Occupy)"))
        else:
            icon_char = "📁" if is_category else "🚀"
            if is_category and has_conflict:
                icon_char = "⚠"
            
            icon_pixmap = self._get_emoji_pixmap(icon_char, 16)
            self._base_color = QColor(52, 152, 219, int(255 * opacity))
            self._hover_color = QColor(93, 173, 226, 242)
            self._border_color = QColor("#2471a3")
            if is_category and has_conflict:
                self.setToolTip(_("Deployment Blocked (Tag/Library Conflict)"))
            else:
                self.setToolTip(_("Not Linked (Deploy)"))

        self._current_pixmap = icon_pixmap
        # still set icon for standard button features (accessibility etc)
        self.setIcon(QIcon(icon_pixmap))
        self.setIconSize(QSize(16, 16))
        self.setText("")
        
        # Remove stylesheet to prevent interference
        self.setStyleSheet("")
        self.update()

    def paintEvent(self, event):
        """Custom painting for high performance opacity updates."""
        painter = QPainter(self)
        if not painter.isActive():
            return
            
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Determine background color
        bg = getattr(self, '_base_color', QColor(52, 152, 219, 200))
        if self.underMouse():
             bg = getattr(self, '_hover_color', QColor(93, 173, 226, 242))
             
        border = getattr(self, '_border_color', QColor("#2471a3"))
        
        # Draw Circle Background
        painter.setBrush(bg)
        painter.setPen(QPen(border, 1))
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.drawEllipse(rect)
        
        # Draw Icon (Directly from pixmap to avoid QIcon.paint re-entry/instability)
        pixmap = getattr(self, '_current_pixmap', None)
        if pixmap and not pixmap.isNull():
             icon_x = (self.width() - pixmap.width()) // 2
             icon_y = (self.height() - pixmap.height()) // 2
             painter.drawPixmap(icon_x, icon_y, pixmap)
        
        painter.end()

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)
