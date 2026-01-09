from PyQt6.QtWidgets import QMainWindow, QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QGraphicsOpacityEffect, QLineEdit, QTextEdit, QComboBox, QSlider, QScrollArea, QAbstractButton
from PyQt6.QtCore import Qt, QPoint, QSize, QEvent, QTimer
from PyQt6.QtGui import QColor, QPixmap, QImage, QIcon, QPalette, QPainter, QBrush
from src.ui.title_bar_button import TitleBarButton
from src.ui.window_mixins import Win32Mixin, DraggableMixin, ResizableMixin
import os
import ctypes
from ctypes import wintypes
from PyQt6.QtWidgets import QApplication
from src.ui.toast import Toast

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
            # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 (Windows 11) or 19 (Windows 10)
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            state = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(state), ctypes.sizeof(state)
            )
        except: pass

class FramelessWindow(QMainWindow, Win32Mixin):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 0. Preparation for "No White Flash"
        self.setWindowOpacity(0.0) # Hide immediately
        
        # 1. Base UI Props - User recommended flags
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowMinMaxButtonsHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 2. Force DWM Dark mode
        force_dark_mode(self)
        
        # 3. Apply WinAPI Styles (Moved to showEvent for stability)
        self._native_styles_applied = False
        
        # State
        self.border_radius = 8
        self._bg_opacity = 0.95
        self._content_opacity = 1.0
        
        self._init_frameless_ui()
        
        # 4. Show with short delay to ensure first paint is done
        QTimer.singleShot(30, lambda: self.setWindowOpacity(1.0))

    def show_toast(self, message: str, level: str = "info"):
        """Show toast on active window."""
        Toast.show_toast(self, message, level)


    def _init_frameless_ui(self):
        # Ensure the Window itself is transparent
        self.setStyleSheet("background: transparent;")
        
        # Main container
        self.container = QWidget(self)
        self.container.setObjectName("FramelessContainer")
        self.container.setMouseTracking(False)
        self.container.installEventFilter(self)
        self.container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.container.setAttribute(Qt.WidgetAttribute.WA_Hover, False)
        
        self._update_stylesheet()
        self.setCentralWidget(self.container)
        
        # Initialize Opacity Effect
        self._content_opacity_effect = QGraphicsOpacityEffect(self.container)
        self._content_opacity_effect.setOpacity(self._content_opacity)
        self.container.setGraphicsEffect(self._content_opacity_effect)
        
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Title Bar
        self.title_bar = QWidget(self.container)
        self.title_bar.setObjectName("TitleBar")
        self.title_bar.setStyleSheet("background-color: transparent;")
        self.title_bar.setFixedHeight(40)
        self.title_bar.setMouseTracking(True)
        
        self.title_bar_layout = QHBoxLayout(self.title_bar)
        self.title_bar_layout.setContentsMargins(10, 5, 10, 5)
        self.title_bar_layout.setSpacing(2)

        # Icon Label
        self.icon_label = QLabel(self.title_bar)
        self.icon_label.setObjectName("titlebar_icon")
        self.icon_label.setFixedSize(24, 24)
        self.icon_label.setVisible(False)
        self.title_bar_layout.addWidget(self.icon_label)
        
        # Title Label
        from src.core.version import VERSION_STRING
        self.title_label = QLabel(VERSION_STRING, self.title_bar)
        self.title_label.setObjectName("titlebar_title")
        self.title_label.setStyleSheet("padding-left: 5px;")
        self.title_bar_layout.addWidget(self.title_label)
        
        self.title_bar_layout.addStretch()
        
        # Center Container
        self.title_bar_center = QWidget(self.title_bar)
        self.title_bar_center_layout = QHBoxLayout(self.title_bar_center)
        self.title_bar_center_layout.setContentsMargins(0, 0, 0, 0)
        self.title_bar_center_layout.setSpacing(5)
        self.title_bar_layout.addWidget(self.title_bar_center)
        
        self.title_bar_layout.addStretch()
        
        # Gap
        self.title_bar_layout.addSpacing(10) 
        
        # Custom Buttons Area
        self.control_layout = QHBoxLayout()
        self.control_layout.setSpacing(1)
        self.title_bar_layout.addLayout(self.control_layout)

        # Default Controls
        self._add_default_controls()

        self.main_layout.addWidget(self.title_bar)
        
        # Content Area
        self.content_area = QWidget(self.container)
        self.main_layout.addWidget(self.content_area)
        self.content_area.setMouseTracking(True)
        self.content_area.installEventFilter(self)
        self.content_area.setAttribute(Qt.WidgetAttribute.WA_Hover)

        self.main_layout.setContentsMargins(0, 0, 5, 5)
    
    def setWindowTitle(self, title: str):
        """Override to sync title_label with window title."""
        super().setWindowTitle(title)
        if hasattr(self, 'title_label'):
            self.title_label.setText(title)

    def set_background_opacity(self, opacity: float):
        """Sets the background opacity (0.0 to 1.0) separate from content."""
        self._bg_opacity = max(0.0, min(1.0, opacity))
        self.update() # Trigger paintEvent for background transparency

    def set_content_opacity(self, opacity: float):
        """Sets the text/content opacity (0.0 to 1.0) using QGraphicsOpacityEffect."""
        self._content_opacity = max(0.0, min(1.0, opacity))
        if hasattr(self, '_content_opacity_effect'):
            self._content_opacity_effect.setOpacity(self._content_opacity)

    def _update_stylesheet(self):
        # Simple stylesheet update for border radius
        radius = 0 if self.isMaximized() else self.border_radius
        border = "" if self.isMaximized() else "border: 1px solid #444;"
        
        # Calculate RGBA for text
        text_alpha = self._content_opacity
        text_color_rgba = f"rgba(221, 221, 221, {text_alpha})"
        
        self.container.setStyleSheet(f"""
            #FramelessContainer {{
                background-color: transparent;
                border-radius: {radius}px;
                {border}
            }}
            QLabel {{ color: {text_color_rgba}; background: transparent; }}
            
            QLineEdit, QComboBox, QAbstractItemView, QSpinBox, QDoubleSpinBox {{
                color: #e0e0e0;
                background-color: #252525;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px;
            }}
            
            QSpinBox::up-button, QDoubleSpinBox::up-button,
            QSpinBox::down-button, QDoubleSpinBox::down-button {{
                background-color: #333;
                border-left: 1px solid #555;
                width: 20px;
                border-radius: 0px;
            }}
            QSpinBox::up-button {{ border-top-right-radius: 4px; }}
            QSpinBox::down-button {{ border-bottom-right-radius: 4px; border-top: 1px solid #555; }}
            
            QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
            QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
                background-color: #444;
            }}
            QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 4px solid #eee;
                width: 0; height: 0;
                margin-bottom: 1px;
            }}
            QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid #eee;
                width: 0; height: 0;
                margin-top: 1px;
            }}

            QScrollBar:vertical {{
                background: #2b2b2b;
                width: 12px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: #555;
                min-height: 20px;
                border-radius: 6px;
            }}

            QPushButton {{
                color: {text_color_rgba};
                background-color: #444;
                border: 1px solid #555;
                padding: 6px 12px;
                border-radius: 4px;
            }}
            QPushButton:hover {{ background-color: #555; }}
            QPushButton:pressed {{ background-color: #333; }}
        """)

    def paintEvent(self, event):
        """Paint background directly to prevent OS/Qt state interference."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 1. Calculate geometry
        radius = self.border_radius if not self.isMaximized() and not self.isFullScreen() else 0
        rect = self.rect()
        
        # 2. Draw Background
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        # Maximized Alpha Boost: Compensate for missing OS shadow by darkening background (+0.15 alpha)
        alpha_val = self._bg_opacity
        if self.isMaximized():
            alpha_val = min(1.0, alpha_val + 0.15)
        bg_alpha = int(alpha_val * 255)
        # Base Color: (35, 35, 35) as preferred by user
        bg_color = QColor(35, 35, 35, bg_alpha)
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        
        if radius > 0:
            painter.drawRoundedRect(rect, radius, radius)
        else:
            painter.drawRect(rect)
        
        # 3. Draw Border
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        if radius > 0:
            from PyQt6.QtGui import QPen
            painter.setPen(QPen(QColor(80, 80, 80, 100), 1))
            painter.drawRoundedRect(rect.adjusted(0, 0, -1, -1), radius, radius)
        
        painter.end()

    def _add_default_controls(self):
        self.min_btn = TitleBarButton("_")
        self.min_btn.setObjectName("titlebar_minimize")
        self.min_btn.clicked.connect(self.showMinimized)
        self.control_layout.addWidget(self.min_btn)

        self.max_btn = TitleBarButton("□")
        self.max_btn.setObjectName("titlebar_maximize")
        self.max_btn.clicked.connect(self.toggle_maximize)
        self.control_layout.addWidget(self.max_btn)

        self.close_btn = TitleBarButton("✕")
        self.close_btn.setObjectName("titlebar_close")
        self.close_btn.set_colors(hover="#c42b1c", text="#cccccc")
        self.close_btn.clicked.connect(self.close)
        self.control_layout.addWidget(self.close_btn)

    def hide_min_max_buttons(self):
        """Hide minimize and maximize buttons."""
        if hasattr(self, 'min_btn'): self.min_btn.hide()
        if hasattr(self, 'max_btn'): self.max_btn.hide()

    def set_resizable(self, resizable: bool):
        self.resizable = resizable
    
    def set_title_bar_icon_visible(self, visible: bool):
        if hasattr(self, 'icon_label'):
            self.icon_label.setVisible(visible)

    def add_title_bar_button(self, btn: TitleBarButton, index: int = 0):
        self.control_layout.insertWidget(index, btn)

    def add_title_bar_widget(self, widget: QWidget, index: int = 0):
        self.control_layout.insertWidget(index, widget)

    def toggle_maximize(self):
        """Toggle maximization using native WinAPI commands."""
        if os.name == 'nt':
            try:
                hwnd = int(self.winId())
                WM_SYSCOMMAND = 0x0112
                SC_MAXIMIZE = 0xF030
                SC_RESTORE = 0xF120
                if self.isMaximized():
                    ctypes.windll.user32.PostMessageW(hwnd, WM_SYSCOMMAND, SC_RESTORE, 0)
                else:
                    ctypes.windll.user32.PostMessageW(hwnd, WM_SYSCOMMAND, SC_MAXIMIZE, 0)
                return
            except: pass
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def set_content_widget(self, widget: QWidget):
        layout = self.content_area.layout()
        if not layout:
            layout = QVBoxLayout(self.content_area)
            layout.setContentsMargins(10, 10, 10, 10)
        else:
            while layout.count():
                item = layout.takeAt(0)
                if item.widget(): item.widget().deleteLater()
        layout.addWidget(widget)
        widget.installEventFilter(self)
        widget.setAttribute(Qt.WidgetAttribute.WA_Hover)

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            if hasattr(self, 'max_btn'):
                self.max_btn.setText("❐" if self.isMaximized() else "□")
            self.main_layout.setContentsMargins(0, 0, 0, 0)
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
                WS_CAPTION = 0x00C00000
                WS_THICKFRAME = 0x00040000
                style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style | WS_CAPTION | WS_THICKFRAME)
                ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0020)
            except: pass

    def nativeEvent(self, eventType, message):
        try:
            if eventType == b"windows_generic_MSG":
                msg = ctypes.wintypes.MSG.from_address(int(message))
            else: return False, 0
        except: return False, 0
            
        WM_GETMINMAXINFO = 0x0024
        WM_NCCALCSIZE = 0x0083
        WM_NCHITTEST = 0x0084

        if msg.message == WM_GETMINMAXINFO:
            try:
                info = ctypes.cast(msg.lParam, ctypes.POINTER(MINMAXINFO)).contents
                r = self.devicePixelRatioF()
                screen = self.screen().availableGeometry()
                info.ptMaxTrackSize.x = int(screen.width() * r) - 2
                info.ptMaxTrackSize.y = int(screen.height() * r) - 2
                info.ptMaxSize.x = int(screen.width() * r) - 2
                info.ptMaxSize.y = int(screen.height() * r) - 2
                return True, 0
            except: pass
            
        if msg.message == WM_NCCALCSIZE:
            return True, 0
            
        if msg.message == WM_NCHITTEST:
            x_phys = ctypes.c_short(msg.lParam & 0xffff).value
            y_phys = ctypes.c_short((msg.lParam >> 16) & 0xffff).value
            r = self.devicePixelRatioF()
            pt_logical = QPoint(int(x_phys / r), int(y_phys / r))
            local_pos = self.mapFromGlobal(pt_logical)
            lx, ly = local_pos.x(), local_pos.y()
            w, h = self.width(), self.height()
            
            if not self.isMaximized() and not self.isFullScreen():
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
            from PyQt6.QtWidgets import QAbstractButton, QAbstractScrollArea, QAbstractItemView, QLineEdit, QTextEdit, QComboBox, QSlider, QAbstractSpinBox
            interactive_types = (QAbstractButton, QLineEdit, QTextEdit, QComboBox, QSlider, QAbstractScrollArea, QAbstractItemView, QAbstractSpinBox)
            interactive_names = ["Sidebar", "ItemCard", "QuickTagPanel", "title_bar_controls", "BreadcrumbContainer", "SearchBar", "deploy_mode_indicator", "titlebar_icon"]
            
            curr = child
            while curr:
                if isinstance(curr, interactive_types) or curr.objectName() in interactive_names or curr.__class__.__name__ == "ClickableLabel":
                    return False, 1 # HTCLIENT
                curr = curr.parentWidget()
            
            return True, 2 # HTCAPTION
            
        return False, 0 

    def set_window_icon_from_path(self, path: str):
        try:
            image = QImage(path)
            if image.isNull(): return
            if image.width() > 256 or image.height() > 256:
                image = image.scaled(256, 256, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            image = image.convertToFormat(QImage.Format.Format_ARGB32)
            # Threshold transparency logic for JPG icons
            w, h = image.width(), image.height()
            threshold = 240
            cw, ch = int(w * 0.25), int(h * 0.25)
            def process_pixel(px, py):
                p = image.pixelColor(px, py)
                if p.red() > threshold and p.green() > threshold and p.blue() > threshold:
                    image.setPixelColor(px, py, QColor(0, 0, 0, 0))
            for y in range(ch):
                for x in range(cw): process_pixel(x, y)
            for y in range(ch):
                for x in range(w - cw, w): process_pixel(x, y)
            for y in range(h - ch, h):
                for x in range(cw): process_pixel(x, y)
            for y in range(h - ch, h):
                for x in range(w - cw, w): process_pixel(x, y)
            pixmap = QPixmap.fromImage(image)
            if hasattr(self, 'icon_label'):
                self.icon_label.setPixmap(pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                self.icon_label.setVisible(True)
            self.setWindowIcon(QIcon(pixmap)) 
        except Exception as e:
            print(f"Failed to load icon: {e}")
            
    def set_default_icon(self):
        """Set a default system icon if no specific icon is provided."""
        from PyQt6.QtWidgets import QStyle
        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon)
        if not icon.isNull():
             if hasattr(self, 'icon_label'):
                 self.icon_label.setPixmap(icon.pixmap(24, 24))
                 self.icon_label.setVisible(True)
             self.setWindowIcon(icon)

    def center_on_screen(self):
        screen = self.screen()
        if not screen: return
        geo = self.geometry()
        screen_geo = screen.availableGeometry()
        x = screen_geo.x() + (screen_geo.width() - geo.width()) // 2
        y = screen_geo.y() + (screen_geo.height() - geo.height()) // 2
        self.move(x, y)

class FramelessDialog(QDialog, Win32Mixin):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowOpacity(0.0)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        force_dark_mode(self)
        self._native_styles_applied = False
        self.border_radius = 8
        self._bg_opacity = 0.95
        self._content_opacity = 1.0
        self._init_frameless_ui()
        QTimer.singleShot(30, lambda: self.setWindowOpacity(1.0))

    def show_toast(self, message: str, level: str = "info"):
        """Show toast on active window."""
        Toast.show_toast(self, message, level)
            
    def _init_frameless_ui(self):
        self.container = QWidget(self)
        self.container.setObjectName("FramelessContainer")
        self.container.installEventFilter(self)
        self._update_stylesheet()
        self.window_layout = QVBoxLayout(self)
        self.window_layout.setContentsMargins(0, 0, 0, 0)
        self.window_layout.addWidget(self.container)
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.title_bar = QWidget(self.container)
        self.title_bar.setObjectName("TitleBar")
        self.title_bar.setFixedHeight(32)
        tb_layout = QHBoxLayout(self.title_bar)
        tb_layout.setContentsMargins(10, 0, 5, 0)
        
        # Icon Label
        self.icon_label = QLabel(self.title_bar)
        self.icon_label.setFixedSize(24, 24)
        self.icon_label.setVisible(False)
        tb_layout.addWidget(self.icon_label)
        
        self.title_label = QLabel("Dialog", self.title_bar)
        self.title_label.setStyleSheet("color: #cccccc; font-weight: bold; padding-left: 5px;")
        tb_layout.addWidget(self.title_label)
        tb_layout.addStretch()
        self.close_btn = TitleBarButton("✕")
        self.close_btn.clicked.connect(self.reject)
        tb_layout.addWidget(self.close_btn)
        self.main_layout.addWidget(self.title_bar)
        self.content_area = QWidget(self.container)
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.content_area)

    def set_background_opacity(self, opacity: float):
        self._bg_opacity = max(0.0, min(1.0, opacity))
        self.update()

    def set_default_icon(self):
        """Set a default system icon if no specific icon is provided."""
        from PyQt6.QtWidgets import QStyle
        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon)
        if not icon.isNull():
             if hasattr(self, 'icon_label'):
                 self.icon_label.setPixmap(icon.pixmap(24, 24))
                 self.icon_label.setVisible(True)
             self.setWindowIcon(icon)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        radius = self.border_radius if not self.isMaximized() else 0
        rect = self.rect()
        # 2. Draw Background
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        # Maximized Alpha Boost: Compensate for missing OS shadow by darkening background (+0.15 alpha)
        alpha_val = self._bg_opacity
        if self.isMaximized():
            alpha_val = min(1.0, alpha_val + 0.15)
        bg_alpha = int(alpha_val * 255)
        bg_color = QColor(35, 35, 35, bg_alpha)
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        if self.isMaximized(): painter.drawRect(rect)
        else: painter.drawRoundedRect(rect, radius, radius)
        painter.end()

    def _update_stylesheet(self):
        # Ensure the Dialog is transparent
        self.setStyleSheet("background: transparent;")
        
        # Calculate RGBA for text (Dialogs default to 1.0 opacity for now)
        text_color_rgba = "rgba(221, 221, 221, 1.0)"
        
        self.container.setStyleSheet(f"""
            QWidget#FramelessContainer {{
                background-color: transparent;
                border: 1px solid #444;
                border-radius: {self.border_radius}px;
            }}
            QLabel {{ color: {text_color_rgba}; background: transparent; }}
            
            QLineEdit, QComboBox, QAbstractItemView, QSpinBox, QDoubleSpinBox {{
                color: #e0e0e0;
                background-color: #252525;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px;
            }}
            
            QSpinBox::up-button, QDoubleSpinBox::up-button,
            QSpinBox::down-button, QDoubleSpinBox::down-button {{
                background-color: #333;
                border-left: 1px solid #555;
                width: 20px;
                border-radius: 0px;
            }}
            QSpinBox::up-button {{ border-top-right-radius: 4px; }}
            QSpinBox::down-button {{ border-bottom-right-radius: 4px; border-top: 1px solid #555; }}
            
            QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
            QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
                background-color: #444;
            }}
            QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 4px solid #eee;
                width: 0; height: 0;
                margin-bottom: 1px;
            }}
            QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid #eee;
                width: 0; height: 0;
                margin-top: 1px;
            }}

            QPushButton {{
                color: {text_color_rgba};
                background-color: #444;
                border: 1px solid #555;
                padding: 6px 12px;
                border-radius: 4px;
            }}
            QPushButton:hover {{ background-color: #555; }}
            QPushButton:pressed {{ background-color: #333; }}
        """)

    def set_content_widget(self, widget):
        if self.content_layout.count() > 0:
            old = self.content_layout.takeAt(0).widget()
            if old: old.deleteLater()
        self.content_layout.addWidget(widget)

    def setWindowTitle(self, title: str):
        super().setWindowTitle(title)
        if hasattr(self, 'title_label'): self.title_label.setText(title)

    def toggle_maximize(self):
        if self.isMaximized(): self.showNormal()
        else: self.showMaximized()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
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
                WS_CAPTION = 0x00C00000
                WS_THICKFRAME = 0x00040000
                style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style | WS_CAPTION | WS_THICKFRAME)
                ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0020)
            except: pass

    def nativeEvent(self, eventType, message):
        try:
            if eventType == b"windows_generic_MSG":
                msg = ctypes.wintypes.MSG.from_address(int(message))
            else: return False, 0
        except: return False, 0
        if msg.message == 0x0083: return True, 0
        if msg.message == 0x0084:
            x_phys = ctypes.c_short(msg.lParam & 0xffff).value
            y_phys = ctypes.c_short((msg.lParam >> 16) & 0xffff).value
            r = self.devicePixelRatioF()
            pt = self.mapFromGlobal(QPoint(int(x_phys / r), int(y_phys / r)))
            child = self.childAt(pt)
            from PyQt6.QtWidgets import QAbstractButton, QAbstractScrollArea, QAbstractItemView, QLineEdit, QTextEdit, QComboBox, QSlider, QAbstractSpinBox
            interactive_types = (QAbstractButton, QLineEdit, QTextEdit, QComboBox, QSlider, QAbstractScrollArea, QAbstractItemView, QAbstractSpinBox)
            interactive_names = ["Sidebar", "MainContent", "ItemCard", "QuickTagPanel", "deploy_mode_indicator", "titlebar_icon"]
            curr = child
            while curr:
                if isinstance(curr, interactive_types) or curr.objectName() in interactive_names or curr.__class__.__name__ == "ClickableLabel":
                    return False, 1 # HTCLIENT
                curr = curr.parentWidget()
            return True, 2 # HTCAPTION
        return False, 0

    def set_window_icon_from_path(self, path: str):
        try:
            image = QImage(path)
            if image.isNull(): return
            if image.width() > 256 or image.height() > 256:
                image = image.scaled(256, 256, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            image = image.convertToFormat(QImage.Format.Format_ARGB32)
            pixmap = QPixmap.fromImage(image)
            if hasattr(self, 'icon_label'):
                self.icon_label.setPixmap(pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                self.icon_label.setVisible(True)
            self.setWindowIcon(QIcon(pixmap)) 
        except: pass
            
    def set_default_icon(self):
        """Set a default system icon if no specific icon is provided."""
        from PyQt6.QtWidgets import QStyle
        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon)
        if not icon.isNull():
             if hasattr(self, 'icon_label'):
                 self.icon_label.setPixmap(icon.pixmap(24, 24))
                 self.icon_label.setVisible(True)
             self.setWindowIcon(icon)

    def hide_min_max_buttons(self):
        """Hide minimize and maximize buttons."""
        if hasattr(self, 'min_btn'): self.min_btn.hide()
        if hasattr(self, 'max_btn'): self.max_btn.hide()

    def center_on_screen(self):
        screen = self.screen()
        if not screen: return
        geo = self.geometry()
        screen_geo = screen.availableGeometry()
        x = screen_geo.x() + (screen_geo.width() - geo.width()) // 2
        y = screen_geo.y() + (screen_geo.height() - geo.height()) // 2
        self.move(x, y)
