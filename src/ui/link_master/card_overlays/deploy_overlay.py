from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import Qt
from src.core.lang_manager import _


class DeployOverlay(QPushButton):
    """Deploy status button overlay."""
    
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
        
        if link_status == 'linked':
            icon_char = "🔗"
            base_color = f"rgba(39, 174, 96, {opacity})"
            hover_color = "rgba(46, 204, 113, 0.95)"
            border_color = "#1e8449"
            self.setToolTip(_("Linked (Unlink)"))
        elif link_status == 'conflict':
            icon_char = "⚠"
            base_color = f"rgba(231, 76, 60, {opacity})"
            hover_color = "rgba(241, 100, 85, 0.95)"
            border_color = "#943126"
            self.setToolTip(_("Conflict (Occupy)"))
        else:
            icon_char = "🚀"
            base_color = f"rgba(52, 152, 219, {opacity})"
            hover_color = "rgba(93, 173, 226, 0.95)"
            border_color = "#2471a3"
            self.setToolTip(_("Not Linked (Deploy)"))

        style = f"""
            QPushButton {{ 
                background-color: {base_color}; 
                color: white; 
                border-radius: 12px; 
                font-size: 11px; 
                border: 1px solid {border_color}; 
            }}
            QPushButton:hover {{ 
                background-color: {hover_color}; 
            }}
        """
        self.setText(icon_char)
        self.setStyleSheet(style)
