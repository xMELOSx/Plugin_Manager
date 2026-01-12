from PyQt6.QtWidgets import (QMainWindow, QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QGraphicsOpacityEffect, QLineEdit, QTextEdit, QComboBox, QSlider, QScrollArea, 
                             QApplication, QAbstractItemView, QAbstractScrollArea, QAbstractSpinBox, QStyle,
                             QTabWidget, QSplitter, QStackedWidget, QToolBox)
from PyQt6.QtCore import Qt, QPoint, QSize, QEvent, QTimer
from PyQt6.QtGui import QColor, QPixmap, QImage, QIcon, QPalette, QPainter, QBrush, QPen, QPainterPath
from src.ui.title_bar_button import TitleBarButton
from src.ui.window_mixins import Win32Mixin
from src.ui.toast import Toast
import os
import ctypes
from ctypes import wintypes

class MINMAXINFO(ctypes.Structure):
    class POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]
    _fields_ = [
        ("ptReserved", POINT),
        ("ptMaxSize", POINT),
        ("ptMaxPosition", POINT),
        ("ptMinTrackSize", POINT),
        ("ptMaxTrackSize", POINT),
    ]

def force_dark_mode(window):
    """Force immersive dark mode via DWM API to prevent white borders/flashes."""
    if os.name == 'nt':
        try:
            hwnd = int(window.winId())
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            state = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(state), ctypes.sizeof(state)
            )
        except: pass

# Standardized Layout Constants
TITLEBAR_HEIGHT = 40     # Unified height for all windows
TITLEBAR_ICON_SIZE = 24  # Standard icon size
TITLEBAR_SPACING = 8     # Layout spacing
ICON_CONTENT_SIZE = 24   # Use full area

def get_icon_path() -> str:
    """Robustly resolve the application icon path across dev and bundle."""
    import sys
    import os
    # Priority 1: PyInstaller bundle internal path
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    # Priority 2: Frozen EXE directory
    elif getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    # Priority 3: Development source tree
    else:
        # Expected: src/ui/frameless_window.py -> ProjectRoot/src/ui/frameless_window.py
        # Project Root is 3 levels up from this file
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # Check common locations
    candidates = [
        os.path.join(base_path, "src", "resource", "icon", "icon.ico"),
        os.path.join(base_path, "resource", "icon", "icon.ico"),
        os.path.join(base_path, "src", "resource", "icon", "icon.jpg"),
        os.path.join(base_path, "resource", "icon", "icon.jpg")
    ]
    for c in candidates:
        if os.path.exists(c): return c
    return ""

class FramelessWindow(QMainWindow, Win32Mixin):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowMinMaxButtonsHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._native_styles_applied = False
        self.border_radius = 8
        self._bg_opacity = 0.95
        self._content_opacity = 1.0
        self.resizable = True
        self._init_frameless_ui()

    def show_toast(self, message: str, level: str = "info"):
        Toast.show_toast(self, message, level)

    def _init_frameless_ui(self):
        self.setStyleSheet("background: transparent;")
        self.container = QWidget(self)
        self.container.setObjectName("FramelessContainer")
        self.container.installEventFilter(self)
        self.container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Maximize Alpha Boost (0-255)
        self.max_alpha_boost = 60
        
        self._update_stylesheet()
        self.setCentralWidget(self.container)
        self._content_opacity_effect = QGraphicsOpacityEffect(self.container)
        self._content_opacity_effect.setOpacity(self._content_opacity)
        self.container.setGraphicsEffect(self._content_opacity_effect)
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.title_bar = QWidget(self.container)
        self.title_bar.setObjectName("TitleBar")
        self.title_bar.setFixedHeight(TITLEBAR_HEIGHT)
        self.title_bar.setMouseTracking(True)
        self.title_bar_layout = QHBoxLayout(self.title_bar)
        self.title_bar_layout.setContentsMargins(10, 0, 10, 0) # 10px safe margin on right too
        self.title_bar_layout.setSpacing(TITLEBAR_SPACING)
        self.title_bar_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.icon_label = QLabel(self.title_bar)
        self.icon_label.setFixedSize(TITLEBAR_ICON_SIZE, TITLEBAR_ICON_SIZE)
        self.icon_label.setObjectName("titlebar_icon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter) 
        self.icon_label.setVisible(False)
        self.title_bar_layout.addWidget(self.icon_label)
        from src.core.version import VERSION_STRING
        self.title_label = QLabel(VERSION_STRING, self.title_bar)
        self.title_label.setObjectName("titlebar_title")
        self.title_label.setStyleSheet("padding-left: 0px;") # Spacing handled by layout
        self.title_bar_layout.addWidget(self.title_label)
        self.title_bar_layout.addStretch()
        self.title_bar_center = QWidget(self.title_bar)
        self.title_bar_center_layout = QHBoxLayout(self.title_bar_center)
        self.title_bar_center_layout.setContentsMargins(0, 0, 0, 0)
        self.title_bar_layout.addWidget(self.title_bar_center)
        self.title_bar_layout.addStretch()
        self.control_layout = QHBoxLayout()
        self.control_layout.setSpacing(1)
        self.title_bar_layout.addLayout(self.control_layout)
        self._add_default_controls()
        self.main_layout.addWidget(self.title_bar)
        self.content_area = QWidget(self.container)
        self.main_layout.addWidget(self.content_area)
        self.main_layout.setContentsMargins(0, 0, 5, 5)
        self.set_default_icon()

    def setWindowTitle(self, title: str):
        super().setWindowTitle(title)
        if hasattr(self, 'title_label'): self.title_label.setText(title)

    def set_background_opacity(self, opacity: float):
        self._bg_opacity = max(0.0, min(1.0, opacity))
        self.update()

    def set_content_opacity(self, opacity: float):
        self._content_opacity = max(0.0, min(1.0, opacity))
        if hasattr(self, '_content_opacity_effect'):
            self._content_opacity_effect.setOpacity(self._content_opacity)

    def _update_stylesheet(self):
        radius = 0 if self.isMaximized() else self.border_radius
        border = "" if self.isMaximized() else "border: 1px solid #444;"
        text_alpha = self._content_opacity
        text_color_rgba = "rgba(255, 255, 255, {})".format(text_alpha)
        
        from src.ui.styles import TooltipStyles
        self.container.setStyleSheet("""
            #FramelessContainer {{
                background-color: transparent;
                border-radius: {radius}px;
                {border}
            }}
            {tooltip_style}
            QLabel, QCheckBox, QRadioButton, QGroupBox {{ color: {text_color}; background: transparent; }}
            QGroupBox {{ font-weight: bold; border: 1px solid #444; margin-top: 10px; padding-top: 10px; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 10px; color: #aaa; }}
            
            QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
                color: #ffffff;
                background-color: #252525;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px;
            }}
            QSpinBox::up-button, QDoubleSpinBox::up-button,
            QSpinBox::down-button, QDoubleSpinBox::down-button {{
                background-color: #333;
                border-left: 1px solid #555;
                width: 16px;
            }}
            QSpinBox::up-button {{ border-top-right-radius: 4px; }}
            QSpinBox::down-button {{ border-bottom-right-radius: 4px; border-top: 1px solid #555; }}
            QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
            QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{ background-color: #444; }}
            
            QScrollBar:vertical {{ background: #2b2b2b; width: 12px; margin: 0px; }}
            QScrollBar::handle:vertical {{ background: #555; min-height: 20px; border-radius: 6px; }}
            
            QTableWidget, QListWidget, QTreeWidget {{
                background-color: #252525;
                color: #ffffff;
                gridline-color: #3d3d3d;
                border: 1px solid #444;
                border-radius: 4px;
                outline: none;
            }}
            QHeaderView::section {{
                background-color: #333;
                color: #ffffff;
                padding: 4px;
                border: none;
                border-bottom: 1px solid #444;
            }}
            QTableWidget QTableCornerButton::section {{ background: #333; border: none; }}
            
            QPushButton {{ color: {text_color}; background-color: #444; border: 1px solid #555; padding: 6px 12px; border-radius: 4px; }}
            QPushButton:hover {{ background-color: #555; }}
            QPushButton:pressed {{ background-color: #333; }}
        """.format(radius=radius, border=border, text_color=text_color_rgba, tooltip_style=TooltipStyles.DARK))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        radius = self.border_radius if not self.isMaximized() and not self.isFullScreen() else 0
        rect = self.rect()
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        alpha_val = self._bg_opacity
        if self.isMaximized(): 
            boost = self.max_alpha_boost / 255.0
            alpha_val = min(1.0, alpha_val + boost)
        bg_alpha = int(alpha_val * 255)
        bg_color = QColor(56, 56, 56, bg_alpha)
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        if radius > 0: painter.drawRoundedRect(rect, radius, radius)
        else: painter.drawRect(rect)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        if radius > 0:
            painter.setPen(QPen(QColor(80, 80, 80, 100), 1))
            painter.drawRoundedRect(rect.adjusted(0, 0, -1, -1), radius, radius)
        painter.end()

    def _add_default_controls(self):
        self.min_btn = TitleBarButton("_")
        self.min_btn.clicked.connect(self.showMinimized)
        self.control_layout.addWidget(self.min_btn)
        self.max_btn = TitleBarButton("□")
        self.max_btn.clicked.connect(self.toggle_maximize)
        self.control_layout.addWidget(self.max_btn)
        self.close_btn = TitleBarButton("✕")
        self.close_btn.set_colors(hover="#c42b1c", text="#cccccc")
        self.close_btn.clicked.connect(self.close)
        self.control_layout.addWidget(self.close_btn)

    def hide_min_max_buttons(self):
        if hasattr(self, 'min_btn'): self.min_btn.hide()
        if hasattr(self, 'max_btn'): self.max_btn.hide()

    def set_resizable(self, resizable: bool): self.resizable = resizable
    def set_title_bar_icon_visible(self, visible: bool):
        if hasattr(self, 'icon_label'): self.icon_label.setVisible(visible)

    def add_title_bar_button(self, btn, index=0):
        self.control_layout.insertWidget(index, btn)

    def add_title_bar_widget(self, widget, index=0):
        self.control_layout.insertWidget(index, widget)

    def toggle_maximize(self):
        if os.name == 'nt':
            try:
                hwnd = int(self.winId())
                WM_SYSCOMMAND, SC_MAXIMIZE, SC_RESTORE = 0x0112, 0xF030, 0xF120
                if self.isMaximized(): ctypes.windll.user32.PostMessageW(hwnd, WM_SYSCOMMAND, SC_RESTORE, 0)
                else: ctypes.windll.user32.PostMessageW(hwnd, WM_SYSCOMMAND, SC_MAXIMIZE, 0)
                return
            except: pass
        if self.isMaximized(): self.showNormal()
        else: self.showMaximized()

    def set_content_widget(self, widget):
        layout = self.content_area.layout() or QVBoxLayout(self.content_area)
        if not self.content_area.layout(): self.content_area.setLayout(layout)
        layout.setContentsMargins(10, 10, 10, 10)
        while layout.count():
            item = layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        layout.addWidget(widget)

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            if hasattr(self, 'max_btn'): self.max_btn.setText("❐" if self.isMaximized() else "□")
            self._update_stylesheet()
            self.update()
        super().changeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._native_styles_applied:
            self._apply_native_styles()
            self._native_styles_applied = True

    def _apply_native_styles(self):
        if os.name == 'nt':
            try:
                hwnd = int(self.winId())
                GWL_STYLE = -16
                WS_CAPTION, WS_THICKFRAME = 0x00C00000, 0x00040000
                style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style | WS_CAPTION | WS_THICKFRAME)
                ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0020)
            except: pass

    def nativeEvent(self, eventType, message):
        try:
            if eventType == b"windows_generic_MSG": msg = ctypes.wintypes.MSG.from_address(int(message))
            else: return False, 0
        except: return False, 0
        
        if msg.message == 0x0024:
            try:
                info = ctypes.cast(msg.lParam, ctypes.POINTER(MINMAXINFO)).contents
                r = self.devicePixelRatioF()
                
                if self.isFullScreen():
                    screen = self.screen().geometry()
                else:
                    screen = self.screen().availableGeometry()
                
                info.ptMaxTrackSize.x = int(screen.width() * r)
                info.ptMaxTrackSize.y = int(screen.height() * r)
                info.ptMaxSize.x = int(screen.width() * r)
                info.ptMaxSize.y = int(screen.height() * r)
                return True, 0
            except: pass
        if msg.message == 0x0083: return True, 0 
        if msg.message == 0x0084: # WM_NCHITTEST
            x_phys = ctypes.c_short(msg.lParam & 0xffff).value
            y_phys = ctypes.c_short((msg.lParam >> 16) & 0xffff).value
            r = self.devicePixelRatioF()
            pt_logical = QPoint(int(x_phys / r), int(y_phys / r))
            local_pos = self.mapFromGlobal(pt_logical)
            lx, ly = local_pos.x(), local_pos.y()
            w, h = self.width(), self.height()
            
            if self.resizable and not self.isMaximized() and not self.isFullScreen():
                margin = 8
                if lx < margin and ly < margin: return True, 13
                if lx > w - margin and ly < margin: return True, 14
                if lx < margin and ly > h - margin: return True, 16
                if lx > w - margin and ly > h - margin: return True, 17
                if lx < margin: return True, 10
                if lx > w - margin: return True, 11
                if ly < margin: return True, 12
                if ly > h - margin: return True, 15
            
            child = self.childAt(local_pos)
            if not child: return True, 2 # Dragging background
            
            curr = child
            while curr and curr != self:
                cname = curr.metaObject().className()
                oname = curr.objectName()
                
                # SPECIFIC INTERACTIVE ELEMENTS (Highest Priority)
                # Indicators/Buttons that must be clickable even if small
                if oname in ["deploy_mode_indicator", "titlebar_pin_btn", "titlebar_help_btn", "titlebar_options_btn", "titlebar_icon", "titlebar_max", "titlebar_min", "titlebar_close"]:
                    return False, 1 # HTCLIENT
                
                # Check for Selectable Text Labels
                if isinstance(curr, QLabel) and (curr.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse):
                    return False, 1 # HTCLIENT
                
                # COMPREHENSIVE INTERACTIVE WHITELIST (Strict inputs only)
                # Avoid "Box" or "Group" to prevent blocking containers.
                if any(t in cname for t in [
                    "Button", "Btn", "Edit", "Combo", "Spin", "Slider", "Dial", 
                    "Table", "Tree", "List", "View", "Header", "TabWidget", "TabBar", 
                    "Splitter", "Browser", "Web", "Stacked", 
                    "Check", "Radio", "Menu", "Indicator", "Icon", "Status",
                    "ScrollBar", "ItemCard", "ClickableLabel",
                    "TagBar", "TagWidget", "TagFlowPreview", "TagChipInput"
                ]):
                    return False, 1 # HTCLIENT
                
                # DRAGGABLE CONTAINER WHITELIST
                # Explicitly list containers that should allow dragging from gaps
                if oname in [
                    "MainContent", "ItemCardPool", 
                    "cat_container", "pkg_container", 
                    "TitleBar", "BreadcrumbContainer", 
                    "fav_switcher_container",
                    "CategoryHeaderContainer", "PackageHeaderContainer",
                    "MainContentWrapper", "LayoutContentWrapper"
                ]:
                    return True, 2 # HTCAPTION
                
                curr = curr.parentWidget()
            
            # If nothing matched (e.g. generic QWidget background), assume Caption (Window Background)
            return True, 2 
            
        return False, 0 

    def set_window_icon_from_path(self, path: str):
        """High-resolution, DPI-aware icon loader (Shared logic)."""
        if not path or not os.path.exists(path):
            return False
            
        try:
            # 1. Load Icon for Taskbar
            multi_icon = QIcon(path)
            if multi_icon.isNull():
                return False
            self.setWindowIcon(multi_icon)
            
            # 2. Render optimized title bar pixmap (Sharp, Square, DPI aware)
            dpr = self.devicePixelRatioF()
            base_size = ICON_CONTENT_SIZE 
            physical_size = int(base_size * dpr)
            
            # Create a high-quality transparent pixmap
            pixmap = QPixmap(physical_size, physical_size)
            pixmap.fill(Qt.GlobalColor.transparent)
            
            painter = QPainter(pixmap)
            try:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                
                # Apply a rounded mask (4px logical radius)
                path_obj = QPainterPath()
                path_obj.addRoundedRect(0, 0, physical_size, physical_size, 4 * dpr, 4 * dpr)
                painter.setClipPath(path_obj)
                
                multi_icon.paint(painter, 0, 0, physical_size, physical_size)
            finally:
                painter.end()
            
            pixmap.setDevicePixelRatio(dpr)
            
            if hasattr(self, 'icon_label'):
                self.icon_label.setPixmap(pixmap)
                self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.icon_label.setVisible(True)
            return True
        except Exception as e:
            print(f"Icon Load Fail: {e}")
            return False

    def set_default_icon(self):
        """Unified default icon loader."""
        path = get_icon_path()
        if path:
            self.set_window_icon_from_path(path)
        else:
            icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon)
            if hasattr(self, 'icon_label'):
                self.icon_label.setPixmap(icon.pixmap(24, 24))
                self.icon_label.setVisible(True)
            self.setWindowIcon(icon)

    def center_on_screen(self):
        screen = self.screen() or QApplication.primaryScreen()
        geo = self.geometry()
        screen_geo = screen.availableGeometry()
        self.move(screen_geo.x() + (screen_geo.width() - geo.width()) // 2, screen_geo.y() + (screen_geo.height() - geo.height()) // 2)

class FramelessDialog(QDialog, Win32Mixin):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Revert to Window flag as requested by user's preference for taskbar independence
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._native_styles_applied = False
        self.border_radius = 8
        self._bg_opacity = 0.95
        self._content_opacity = 1.0
        self.resizable = True # Correctly initialized
        self._init_frameless_ui()

    def show_toast(self, message: str, level: str = "info"):
        Toast.show_toast(self, message, level)
            
    def _init_frameless_ui(self):
        self.container = QWidget(self)
        self.container.setObjectName("FramelessContainer")
        self._update_stylesheet()
        self.window_layout = QVBoxLayout(self)
        self.window_layout.setContentsMargins(0, 0, 0, 0)
        self.window_layout.addWidget(self.container)
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.title_bar = QWidget(self.container)
        self.title_bar.setObjectName("TitleBar")
        self.title_bar.setFixedHeight(TITLEBAR_HEIGHT) 
        tb_layout = QHBoxLayout(self.title_bar)
        tb_layout.setContentsMargins(10, 0, 10, 0)
        tb_layout.setSpacing(TITLEBAR_SPACING)
        tb_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.icon_label = QLabel(self.title_bar)
        self.icon_label.setFixedSize(TITLEBAR_ICON_SIZE, TITLEBAR_ICON_SIZE)
        self.icon_label.setObjectName("titlebar_icon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setVisible(False)
        tb_layout.addWidget(self.icon_label)
        self.title_label = QLabel("Dialog", self.title_bar)
        self.title_label.setObjectName("titlebar_title")
        self.title_label.setStyleSheet("color: #cccccc; font-weight: bold; padding-left: 0px;")
        tb_layout.addWidget(self.title_label)
        tb_layout.addStretch()
        self.close_btn = TitleBarButton("✕")
        self.close_btn.setObjectName("titlebar_close")
        self.close_btn.clicked.connect(self.reject)
        tb_layout.addWidget(self.close_btn)
        self.main_layout.addWidget(self.title_bar)
        self.content_area = QWidget(self.container)
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.content_area, 1) # Give content area stretch factor 1
        self.set_default_icon()

    def set_resizable(self, resizable: bool): self.resizable = resizable 
    
    def set_title_bar_icon_visible(self, visible: bool):
        if hasattr(self, 'icon_label'): self.icon_label.setVisible(visible)

    def set_background_opacity(self, opacity: float):
        self._bg_opacity = max(0.0, min(1.0, opacity))
        self.update()

    def set_content_opacity(self, opacity: float):
        self._content_opacity = max(0.0, min(1.0, opacity))

    def set_window_icon_from_path(self, path: str):
        """Delegate to simplified high-quality logic (matching FramelessWindow)."""
        return FramelessWindow.set_window_icon_from_path(self, path)

    def set_default_icon(self):
        """Delegate to unified logic."""
        return FramelessWindow.set_default_icon(self)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        radius = self.border_radius if not self.isMaximized() else 0
        rect = self.rect()
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        alpha_val = self._bg_opacity
        if self.isMaximized(): alpha_val = min(1.0, alpha_val + 0.15)
        bg_alpha = int(alpha_val * 255)
        bg_color = QColor(35, 35, 35, bg_alpha)
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        if self.isMaximized(): painter.drawRect(rect)
        else: painter.drawRoundedRect(rect, radius, radius)
        painter.end()

    def _update_stylesheet(self):
        self.setStyleSheet("background: transparent;")
        text_color_rgba = "rgba(255, 255, 255, {})".format(self._content_opacity)
        from src.ui.styles import TooltipStyles
        self.container.setStyleSheet("""
            QWidget#FramelessContainer {{ background-color: transparent; border: none; border-radius: {radius}px; }}
            {tooltip_style}
            QLabel, QCheckBox, QRadioButton, QGroupBox {{ color: {text_color}; background: transparent; }}
            QGroupBox {{ font-weight: bold; border: 1px solid #444; margin-top: 10px; padding-top: 12px; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 10px; color: #aaa; }}
            
            QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
                color: #ffffff; background-color: #252525; border: 1px solid #555; border-radius: 4px; padding: 4px;
            }}
            QSpinBox::up-button, QDoubleSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::down-button {{
                background-color: #333; border-left: 1px solid #555; width: 16px;
            }}
            QSpinBox::up-button {{ border-top-right-radius: 4px; }}
            QSpinBox::down-button {{ border-bottom-right-radius: 4px; border-top: 1px solid #555; }}
            QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover, QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{ background-color: #444; }}
            
            QTableWidget, QListWidget, QTreeWidget {{
                background-color: #252525;
                color: #ffffff;
                gridline-color: #3d3d3d;
                border: 1px solid #444;
                border-radius: 4px;
                outline: none;
            }}
            QHeaderView::section {{
                background-color: #333;
                color: #ffffff;
                padding: 4px;
                border: none;
                border-bottom: 1px solid #444;
            }}
            QTableWidget QTableCornerButton::section {{ background: #333; border: none; }}
            
            QPushButton {{ color: {text_color}; background-color: #444; border: 1px solid #555; padding: 6px 12px; border-radius: 4px; }}
            QPushButton:hover {{ background-color: #555; }}
            QPushButton:pressed {{ background-color: #333; }}
        """.format(radius=self.border_radius, text_color=text_color_rgba, tooltip_style=TooltipStyles.DARK))

    def set_content_widget(self, widget):
        if self.content_layout.count() > 0:
            old = self.content_layout.takeAt(0).widget()
            if old: old.deleteLater()
        self.content_layout.addWidget(widget)

    def setWindowTitle(self, title: str):
        super().setWindowTitle(title)
        if hasattr(self, 'title_label'): self.title_label.setText(title)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._native_styles_applied:
            self._apply_native_styles()
            self._native_styles_applied = True

    def _apply_native_styles(self):
        if os.name == 'nt':
            try:
                hwnd = int(self.winId())
                GWL_STYLE = -16
                WS_THICKFRAME, WS_SYSMENU = 0x00040000, 0x00080000
                style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
                # DO NOT use WS_CAPTION for Dialogs/Small Windows to avoid native title bar leak
                # Just keep ThickFrame for resize handles if needed
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style | WS_THICKFRAME | WS_SYSMENU)
                ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0020)
            except: pass

    def nativeEvent(self, eventType, message):
        try:
            if eventType == b"windows_generic_MSG": msg = ctypes.wintypes.MSG.from_address(int(message))
            else: return False, 0
        except: return False, 0
        if msg.message == 0x0024:
            try:
                info = ctypes.cast(msg.lParam, ctypes.POINTER(MINMAXINFO)).contents
                r = self.devicePixelRatioF()
                screen = self.screen().availableGeometry()
                info.ptMaxTrackSize.x = int(screen.width() * r)
                info.ptMaxTrackSize.y = int(screen.height() * r)
                info.ptMaxSize.x = int(screen.width() * r)
                info.ptMaxSize.y = int(screen.height() * r)
                return True, 0
            except: pass
        if msg.message == 0x0083: return True, 0
        if msg.message == 0x0084: # WM_NCHITTEST
            x_phys = ctypes.c_short(msg.lParam & 0xffff).value
            y_phys = ctypes.c_short((msg.lParam >> 16) & 0xffff).value
            r = self.devicePixelRatioF()
            pt_logical = QPoint(int(x_phys / r), int(y_phys / r))
            local_pos = self.mapFromGlobal(pt_logical)
            lx, ly = local_pos.x(), local_pos.y()
            w, h = self.width(), self.height()
            
            if self.resizable and not self.isMaximized() and not self.isFullScreen():
                margin = 8
                if lx < margin and ly < margin: return True, 13
                if lx > w - margin and ly < margin: return True, 14
                if lx < margin and ly > h - margin: return True, 16
                if lx > w - margin and ly > h - margin: return True, 17
                if lx < margin: return True, 10
                if lx > w - margin: return True, 11
                if ly < margin: return True, 12
                if ly > h - margin: return True, 15
            
            child = self.childAt(local_pos)
            if not child: return True, 2 # Dragging
            
            curr = child
            while curr and curr != self:
                cname = curr.metaObject().className()
                oname = curr.objectName()
                
                # Check for Selectable Text Labels (Fix for cursor/selection)
                if isinstance(curr, QLabel) and (curr.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse):
                    return False, 1 # HTCLIENT
                
                # DIALOG WHITELIST
                if any(t in cname for t in [
                    "Button", "Btn", "Edit", "Combo", "Spin", "Slider", "Dial", 
                    "Table", "Tree", "List", "View", "Header", "Tab", "Splitter", 
                    "Browser", "Web", "Stacked", "ToolBox", 
                    "Check", "Radio", "Group", "Menu", "Indicator", "Icon",
                    "ScrollBar", "ItemCard", "TagBar", "TagWidget", "TagFlowPreview", "TagChipInput"
                ]) or "Clickable" in cname or oname in ["titlebar_icon", "titlebar_close", "titlebar_maximize", "titlebar_minimize"]:
                     return False, 1 # HTCLIENT
                
                if oname in ["MainContent", "ItemCardPool", "cat_container", "pkg_container"]:
                    return True, 2
                
                curr = curr.parentWidget()
            
            return True, 2 
        return False, 0

    def set_window_icon_from_path(self, path: str):
        try:
            if not os.path.exists(path): return False
            
            from PyQt6.QtGui import QPainter, QBrush, QImage
            
            # 1. Prepare/Set QIcon - ICO files already have multiple sizes
            if path.lower().endswith('.ico'):
                multi_icon = QIcon(path)
            else:
                original_image = QImage(path)
                if original_image.isNull(): return False
                multi_icon = QIcon()
                # Standard Windows icon sizes
                for size in [256, 128, 64, 48, 32, 16]:
                    scaled_pix = QPixmap.fromImage(original_image).scaled(
                        size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                    )
                    multi_icon.addPixmap(scaled_pix)
            
            self.setWindowIcon(multi_icon)
            
            # 2. Set Title Bar Label (Rounded, DPI aware)
            dpr = self.devicePixelRatioF()
            base_size = 24
            target_size = int(base_size * dpr)
            
            # For our generated ICO, it should already be rounded and multi-size
            if path.lower().endswith('.ico'):
                scaled = multi_icon.pixmap(target_size, target_size)
                # Set DPR so it displays at logical size (e.g. 24x24) instead of physical size (e.g. 48x48)
                scaled.setDevicePixelRatio(dpr)
                if hasattr(self, 'icon_label'):
                    self.icon_label.setPixmap(scaled)
                    self.icon_label.setVisible(True)
                return True

            # For other formats (like JPG), apply rounding manually
            original_image = QImage(path)
            scaled = QPixmap.fromImage(original_image).scaled(
                target_size, target_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            
            if scaled.isNull():
                return False

            # 1. Create Mask (White rounded rect on transparent)
            mask = QPixmap(target_size, target_size)
            mask.fill(Qt.GlobalColor.transparent)
            mask_painter = QPainter(mask)
            mask_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            mask_painter.setBrush(QBrush(Qt.GlobalColor.white))
            mask_painter.setPen(Qt.PenStyle.NoPen)
            
            # Scale radius properly
            radius = 6 * dpr
            mask_painter.drawRoundedRect(0, 0, target_size, target_size, radius, radius)
            mask_painter.end()
            
            # 2. Draw Image into Mask using SourceIn
            rounded = QPixmap(target_size, target_size)
            rounded.fill(Qt.GlobalColor.transparent)
            p = QPainter(rounded)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.drawPixmap(0, 0, mask)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            p.drawPixmap(0, 0, scaled)
            p.end()
            
            # Set DPR on the final pixmap so Qt knows how to display it
            rounded.setDevicePixelRatio(dpr)
            
            if hasattr(self, 'icon_label'):
                self.icon_label.setPixmap(rounded)
                self.icon_label.setVisible(True)
            return True
        except: return False
            


    def center_on_screen(self):
        screen = self.screen() or QApplication.primaryScreen()
        geo = self.geometry()
        screen_geo = screen.availableGeometry()
        self.move(screen_geo.x() + (screen_geo.width() - geo.width()) // 2, screen_geo.y() + (screen_geo.height() - geo.height()) // 2)
