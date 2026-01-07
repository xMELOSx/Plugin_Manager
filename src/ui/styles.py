"""
Shared UI Styles - Reusable button styles, colors, and effects.

Usage:
    from src.ui.styles import ButtonStyles
    btn.setStyleSheet(ButtonStyles.PRIMARY)
"""

class ButtonStyles:
    """Reusable button stylesheet templates."""
    
    # Default button style (gray)
    DEFAULT = """
        QPushButton {
            background-color: #3b3b3b;
            color: #fff;
            border: 1px solid #555;
            border-radius: 4px;
            padding: 2px 6px;
        }
        QPushButton:hover {
            background-color: #4a4a4a;
            border-color: #777;
        }
        QPushButton:pressed {
            background-color: #222;
            padding-top: 4px;
            padding-left: 8px;
        }
        QPushButton:disabled {
            background-color: #222;
            color: #555;
            border-color: #333;
        }
    """
    
    # Primary action button (blue)
    PRIMARY = """
        QPushButton {
            background-color: #2980b9;
            color: #fff;
            border: 1px solid #3498db;
            border-radius: 4px;
            padding: 2px 6px;
        }
        QPushButton:hover {
            background-color: #3498db;
            border-color: #fff;
        }
        QPushButton:pressed {
            background-color: #1a5276;
            padding-top: 4px;
            padding-left: 8px;
        }
    """
    
    # Success/Selected button (green)
    SUCCESS = """
        QPushButton {
            background-color: #27ae60;
            color: #fff;
            border: 1px solid #2ecc71;
            border-radius: 4px;
            padding: 2px 6px;
        }
        QPushButton:hover {
            background-color: #2ecc71;
            border-color: #fff;
        }
        QPushButton:pressed {
            background-color: #1e8449;
            padding-top: 4px;
            padding-left: 8px;
        }
    """
    
    # Danger button (red)
    DANGER = """
        QPushButton {
            background-color: #c0392b;
            color: #fff;
            border: 1px solid #e74c3c;
            border-radius: 4px;
            padding: 2px 6px;
        }
        QPushButton:hover {
            background-color: #e74c3c;
            border-color: #fff;
        }
        QPushButton:pressed {
            background-color: #922b21;
        }
    """
    
    # Warning button (orange)
    WARNING = """
        QPushButton {
            background-color: #e67e22;
            color: #fff;
            border: 1px solid #d35400;
            border-radius: 4px;
            padding: 2px 6px;
        }
        QPushButton:hover {
            background-color: #d35400;
        }
        QPushButton:pressed {
            background-color: #a04000;
        }
    """
    
    # Icon button (small, transparent background)
    ICON = """
        QPushButton {
            font-size: 14px;
            padding: 2px;
            border: none;
            background: transparent;
        }
        QPushButton:hover {
            background: #555;
            border-radius: 4px;
        }
        QPushButton:pressed {
            background: #333;
        }
    """
    
    # Checkable icon button with custom checked color
    @staticmethod
    def icon_checkable(checked_color: str = "#27ae60") -> str:
        return f"""
            QPushButton {{
                font-size: 14px;
                padding: 2px;
                border: none;
                background: transparent;
            }}
            QPushButton:hover {{
                background: #555;
                border-radius: 4px;
            }}
            QPushButton:checked {{
                background: {checked_color};
                border-radius: 4px;
            }}
        """


class Colors:
    """Common color constants."""
    
    # Backgrounds
    BG_DARK = "#2b2b2b"
    BG_MEDIUM = "#3b3b3b"
    BG_LIGHT = "#4a4a4a"
    
    # Accents
    PRIMARY = "#3498db"
    SUCCESS = "#27ae60"
    WARNING = "#e67e22"
    DANGER = "#e74c3c"
    INFO = "#9b59b6"
    
    # Text
    TEXT_PRIMARY = "#ffffff"
    TEXT_SECONDARY = "#aaaaaa"
    TEXT_MUTED = "#666666"
    
    # Borders
    BORDER_DEFAULT = "#555555"
    BORDER_HOVER = "#777777"


class MenuStyles:
    """Reusable context menu stylesheet templates."""
    
    # Standard dark context menu
    CONTEXT = """
        QMenu { background-color: #2b2b2b; border: 1px solid #555; }
        QMenu::item { padding: 5px 20px; color: #ddd; }
        QMenu::item:selected { background-color: #3498db; color: white; }
        QMenu::item:disabled { color: #555; }
        QMenu::separator { height: 1px; background: #555; margin: 4px 8px; }
    """


class TooltipStyles:
    """Reusable QToolTip stylesheet templates for consistent tooltips."""
    
    # Standard dark tooltip (use with setStyleSheet)
    DARK = """
        QToolTip {
            color: #ffffff;
            background-color: #2b2b2b;
            border: 1px solid #76797C;
            padding: 4px;
        }
    """
    
    @staticmethod
    def apply_to_widget(widget):
        """Apply the dark tooltip style to a widget."""
        current = widget.styleSheet() or ""
        if "QToolTip" not in current:
            widget.setStyleSheet(current + TooltipStyles.DARK)


class DialogStyles:
    """Reusable dialog stylesheet templates."""
    
    # Enhanced dark QMessageBox style with wider buttons
    ENHANCED_MSG_BOX = """
        QMessageBox { background-color: #1e1e1e; border: 1px solid #444; color: white; }
        QLabel { color: white; font-size: 13px; background: transparent; }
        QPushButton { 
            background-color: #3b3b3b; color: white; border: 1px solid #555; 
            padding: 6px 16px; min-width: 100px; border-radius: 4px; font-weight: bold;
        }
        QPushButton:hover { background-color: #4a4a4a; border-color: #3498db; }
        QPushButton:pressed { background-color: #2980b9; }
    """
