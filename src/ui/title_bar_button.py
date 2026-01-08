""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を介すること。
"""

from PyQt6.QtWidgets import QPushButton
from PyQt6.QtGui import QColor, QCursor
from PyQt6.QtCore import Qt, QSize

class TitleBarButton(QPushButton):
    """
    Custom button for the title bar with hover effects and state management.
    Supports two active states: override (green) and default (blue).
    """
    def __init__(self, text="", parent=None, is_toggle=False):
        super().__init__(text, parent)
        self.setFixedSize(30, 30)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.is_toggle = is_toggle
        self.toggled_state = False
        self._is_override = False  # True=green(override), False=blue(default)
        
        # Default colors
        self.hover_color = "#3a3a3a" # Dark Grey
        self.active_color = "#3498db" # Blue (for default active state)
        self.override_color = "#27ae60" # Green (for override active state)
        self.text_color = "#cccccc"
        
        self.update_style()

    def set_colors(self, hover=None, active=None, override=None, text=None):
        if hover: self.hover_color = hover
        if active: self.active_color = active
        if override: self.override_color = override
        if text: self.text_color = text
        self.update_style()

    def update_style(self):
        if self.toggled_state:
            bg_color = self.override_color if self._is_override else self.active_color
        else:
            bg_color = "transparent"
        border_radius = "4px"
        
        # Logic: Distinct hover color for toggled vs untoggled
        if self.toggled_state:
            if self._is_override:
                hover_bg = "#2ecc71"  # Lighter green
                pressed_bg = "#1e8449"
            else:
                hover_bg = "#4aa3df"  # Lighter blue
                pressed_bg = "#2980b9"
            border_color = "transparent"
        else:
            hover_bg = self.hover_color
            pressed_bg = "#2c3e50"
            border_color = "#555"  # Dark grey border for inactive state

        style = f"""
            QPushButton {{
                background-color: {bg_color};
                border: 1px solid {border_color};
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
            QToolTip {{
                color: #ffffff;
                background-color: #2b2b2b;
                border: 1px solid #76797C;
            }}
        """
        self.setStyleSheet(style)

    def toggle(self):
        if self.is_toggle:
            self.toggled_state = not self.toggled_state
            self.update_style()
            return self.toggled_state
        return False

    def _force_state(self, state: bool, is_override: bool = False):
        """Sets the state. is_override=True for green, False for blue."""
        if self.is_toggle:
            self.toggled_state = state
            self._is_override = is_override
            self.update_style()

