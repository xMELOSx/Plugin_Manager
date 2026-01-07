from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor

class ActionButton(QPushButton):
    """
    Unified action button component that inherits the Trash button's style,
    cursor, and feel, with built-in support for toggling.
    """
    def __init__(self, text, parent=None, is_toggle=True, trigger_on_release=False):
        super().__init__(text, parent)
        self.setCheckable(is_toggle)
        self.trigger_on_release = trigger_on_release
        self.is_danger = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_base_style()

    def _apply_base_style(self):
        # Base style inherited from the project's 'filter_btn_style' logic
        bg_color = "#c0392b" if self.is_danger else "#3b3b3b"
        hover_color = "#d9534f" if self.is_danger else "#4a4a4a"
        border_color = "#e74c3c" if self.is_danger else "#555"
        
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_color};
                color: #fff;
                font-size: 14px;
                border: 1px solid {border_color};
                border-radius: 4px;
                padding: 2px 6px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
                border-color: {"#fff" if self.is_danger else "#999"};
            }}
            QPushButton:pressed {{
                background-color: #1a1a1a;
                padding-top: 6px;
                padding-left: 10px;
                border-style: inset;
            }}
            QPushButton:checked {{
                background-color: #27ae60;
                border-color: #2ecc71;
            }}
            QPushButton:checked:hover {{
                background-color: #2ecc71;
                border-color: #fff;
            }}
        """)

    def set_danger(self, danger: bool):
        """Set the button to a red danger style."""
        self.is_danger = danger
        self._apply_base_style()

    def mouseReleaseEvent(self, event):
        """Override to ensure activation only on release if trigger_on_release is set."""
        # Use childAt check to be sure we are still on the button
        was_inside = self.rect().contains(event.pos())
        super().mouseReleaseEvent(event)
        
        # Note: released signal is already emitted by super().mouseReleaseEvent(event)
        # We don't need extra logic here unless we want to block it, 
        # but we already removed the press-trigger in the window.

    def set_active(self, active: bool):
        """Programmatically set the toggle state."""
        if self.isCheckable():
            self.setChecked(active)
