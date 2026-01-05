from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt


class StarOverlay(QLabel):
    """Favorite star indicator overlay."""
    
    def __init__(self, parent=None):
        super().__init__("★", parent)
        self.setFixedSize(28, 28)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setObjectName("overlay_star")
        self.setStyleSheet("color: #f1c40f; font-size: 20px; background: transparent;")
        self.hide()
    
    def setFavorite(self, is_favorite: bool):
        """Show or hide the star based on favorite status."""
        if is_favorite:
            self.show()
            self.raise_()
        else:
            self.hide()
