"""
Shared UI Styles - Reusable button styles, colors, and effects.

Usage:
    from src.ui.styles import ButtonStyles, apply_common_dialog_style
    btn.setStyleSheet(ButtonStyles.PRIMARY)
    apply_common_dialog_style(self)
"""

from PyQt6.QtWidgets import QDialog, QMessageBox, QPushButton, QLabel

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
    

class DialogStyles:
    """Reusable dialog stylesheet templates."""
    
    # Common dark dialog style
    COMMON = """
        /* Force white/light-gray text on dialogs and common child widgets */
        QDialog, QMessageBox {
            background-color: #2b2b2b;
            color: #e0e0e0;
        }
        
        /* Specific overrides for common form elements to ensure visibility */
        QLabel, QRadioButton, QCheckBox, QGroupBox {
            color: #e0e0e0;
            background-color: transparent;
            border: none;
        }
        
        QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QAbstractItemView {
            color: #eeeeee;
            background-color: #1e1e1e;
            border: 1px solid #555;
            border-radius: 4px;
            padding: 4px;
        }

        /* Lists and Tables */
        QTableWidget, QListWidget, QTreeWidget {
            background-color: #252525;
            color: #e0e0e0;
            gridline-color: #3d3d3d;
        }
        QHeaderView::section {
            background-color: #333;
            color: #ddd;
            padding: 4px;
            border: none;
        }

        QPushButton {
            background-color: #444;
            color: #ffffff;
            border: 1px solid #555;
            padding: 6px 12px;
            border-radius: 4px;
            min-width: 80px;
        }
        QPushButton:hover {
            background-color: #555;
            border-color: #777;
        }
        QPushButton:pressed {
            background-color: #2a2a2a;
        }
        QPushButton:disabled {
            color: #666;
            background-color: #2a2a2a;
        }
    """

def apply_common_dialog_style(dialog):
    """
    Apply a consistent dark theme to a QDialog or QMessageBox.
    Includes dark title bar support for Windows.
    """
    # Windows dark titlebar support
    try:
        import ctypes
        from ctypes import wintypes
        hwnd = int(dialog.winId())
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        dwmapi = ctypes.windll.dwmapi
        value = ctypes.c_int(1)  # 1 = dark mode
        dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 
                                      ctypes.byref(value), ctypes.sizeof(value))
    except Exception:
        pass  # Ignore on non-Windows or if API fails
    
    # Strong override for all labels within the dialog to ensure visibility
    common_label_style = """
        QLabel {
            color: #ffffff;
            background-color: transparent;
            border: none;
        }
    """
    
    if isinstance(dialog, QMessageBox):
        # QMessageBox specific internal styling
        dialog.setStyleSheet(DialogStyles.COMMON + common_label_style + """
            QMessageBox QLabel {
                font-size: 13px;
            }
        """)
    else:
        dialog.setStyleSheet(DialogStyles.COMMON + common_label_style)
