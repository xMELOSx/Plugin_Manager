from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QPainter, QFont


class StarOverlay(QLabel):
    """Favorite star indicator overlay with cached rendering."""
    
    # Class-level pixmap cache
    _star_pixmap = None
    
    @classmethod
    def _get_star_pixmap(cls) -> QPixmap:
        """Get or create the cached star pixmap."""
        if cls._star_pixmap is None:
            size = 28
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            # Use explicit font for consistent rendering
            font = QFont("Segoe UI Symbol", 18)
            painter.setFont(font)
            painter.setPen(Qt.GlobalColor.yellow)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "★")
            painter.end()
            cls._star_pixmap = pixmap
        return cls._star_pixmap
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(28, 28)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setObjectName("overlay_star")
        self.setStyleSheet("background: transparent;")
        self.setPixmap(self._get_star_pixmap())
        self.hide()
    
    def setFavorite(self, is_favorite: bool):
        """Show or hide the star based on favorite status."""
        if is_favorite:
            self.show()
            self.raise_()
        else:
            self.hide()
