""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を介すること。
"""

from PyQt6.QtWidgets import QPushButton
from PyQt6.QtGui import QColor, QCursor
from PyQt6.QtCore import Qt, QSize

class TitleBarButton(QPushButton):
    """
    Custom button for the title bar with hover effects and state management.
    """
    def __init__(self, text="", parent=None, is_toggle=False):
        super().__init__(text, parent)
        self.setFixedSize(30, 30)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.is_toggle = is_toggle
        self.toggled_state = False
        
        # Default colors
        self.hover_color = "#3a3a3a" # Dark Grey
        self.active_color = "#3498db" # Blue (for toggled state)
        self.text_color = "#cccccc"
        
        self.update_style()

    def set_colors(self, hover=None, active=None, text=None):
        if hover: self.hover_color = hover
        if active: self.active_color = active
        if text: self.text_color = text
        self.update_style()

    def update_style(self):
        bg_color = self.active_color if self.toggled_state else "transparent"
        border_radius = "4px" if self.toggled_state else "0px"
        
        # Logic: Distinct hover color for toggled vs untoggled
        if self.toggled_state:
            # Lighter blue to show interaction on top of active state
            hover_bg = "#4aa3df" 
            pressed_bg = "#2980b9"
        else:
            hover_bg = self.hover_color
            pressed_bg = "#2c3e50"

        style = f"""
            QPushButton {{
                background-color: {bg_color};
                border: none;
                border-radius: {border_radius};
                color: {self.text_color};
                font-weight: bold;
                font-family: "Segoe UI Emoji", "Segoe UI", sans-serif;
                font-size: 16px;
                padding: 0px;
                margin: 0px;
            }}
            QPushButton:hover {{
                background-color: {hover_bg}; 
                border: 1px solid rgba(255,255,255,0.2); 
            }}
            QPushButton:pressed {{
                background-color: {pressed_bg};
            }}
        """
        self.setStyleSheet(style)

    def toggle(self):
        if self.is_toggle:
            self.toggled_state = not self.toggled_state
            self.update_style()
            return self.toggled_state
        return False

    def _force_state(self, state: bool):
        """Sets the state without returning anything or triggering logic (Helper for restorations)."""
        if self.is_toggle:
            self.toggled_state = state
            self.update_style()
