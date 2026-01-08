from PyQt6.QtWidgets import QMainWindow, QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QGraphicsOpacityEffect, QLineEdit, QTextEdit, QComboBox, QSlider, QScrollArea, QAbstractButton
from PyQt6.QtCore import Qt, QPoint, QSize, QEvent, QTimer
from PyQt6.QtGui import QColor, QPixmap, QImage, QIcon, QPalette, QPainter, QBrush
from src.ui.title_bar_button import TitleBarButton
from src.ui.window_mixins import Win32Mixin, DraggableMixin, ResizableMixin
import os
import ctypes
from ctypes import wintypes
from PyQt6.QtWidgets import QApplication

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
        # FramelessWindowHint removes standard frame, but we re-add native behavior via WinAPI style
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowMinMaxButtonsHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 2. Force DWM Dark mode
        force_dark_mode(self)
        
        # 3. Apply WinAPI Styles (Moved to showEvent for stability)
        self._native_styles_applied = False
        
        # State
        self.border_radius = 8
        self._bg_opacity = 0.9
        self._content_opacity = 1.0
        
        self._init_frameless_ui()
        
        # 4. Show with short delay to ensure first paint is done
        QTimer.singleShot(30, lambda: self.setWindowOpacity(1.0))


    def _init_frameless_ui(self):
        # Ensure the Window itself is transparent so only our painted background/container is seen
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
        
        self.set_background_opacity(0.95)
        
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
        self._update_stylesheet()

    def set_content_opacity(self, opacity: float):
        """Sets the text/content opacity (0.0 to 1.0) using QGraphicsOpacityEffect."""
        self._content_opacity = max(0.0, min(1.0, opacity))
        if hasattr(self, '_content_opacity_effect'):
            self._content_opacity_effect.setOpacity(self._content_opacity)

    def _update_stylesheet(self):
        # Simple stylesheet update for border radius
        # The main frame is hidden by WM_NCCALCSIZE, so we just style the container
        radius = 0 if self.isMaximized() else self.border_radius
        border = "" if self.isMaximized() else "border: 1px solid #444;"
        
        # Calculate RGBA for text
        text_alpha = self._content_opacity # 0.0 - 1.0
        text_color_rgba = f"rgba(221, 221, 221, {text_alpha})" # #ddd
        
        self.container.setStyleSheet(f"""
            #FramelessContainer {{
                background-color: transparent;
                border-radius: {radius}px;
                {border}
            }}
            /* Generic Widget Styling for Dark Mode */
            QLabel {{ color: {text_color_rgba}; background: transparent; }}
            
            QLineEdit, QComboBox, QAbstractItemView {{
                color: #e0e0e0; /* Fixed bright text */
                background-color: #252525; /* OPAQUE dark background */
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px;
                selection-background-color: #3498db;
                selection-color: white;
            }}
            
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            
            QScrollArea {{
                border: 1px solid #555;
                background-color: transparent;
            }}
            /* Make scroll area viewport and contents transparent */
            QScrollArea > QWidget > QWidget {{
                background: transparent;
            }}
            QAbstractScrollArea::viewport {{
                background: transparent;
            }}
            
            QTreeView {{
                /* Opaque background - window paintEvent handles transparency */
                background-color: #1e1e1e;
                border: 1px solid #444;
                color: #e0e0e0;
            }}
            
            QHeaderView::section {{
                background-color: #333;
                color: #e0e0e0;
                border: 1px solid #555;
                padding: 4px;
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
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}

            QCheckBox {{ 
                color: {text_color_rgba}; 
                spacing: 8px;
                padding: 4px;
                background: transparent;
            }}
            QCheckBox:hover {{
                background-color: rgba(255, 255, 255, 0.05); 
                border-radius: 4px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 2px solid #666;
                background: #444;
                border-radius: 3px;
            }}
            QCheckBox::indicator:hover {{
                border-color: #888;
                background: #555;
            }}
            QCheckBox::indicator:checked, QCheckBox::indicator:checked:!active {{
                background: #3498db;
                border: 2px solid #3498db;
                image: url(src/assets/checkmark.svg);
            }}

            /* Fix QSpinBox visibility in dark mode */
            QSpinBox, QDoubleSpinBox {{
                color: #e0e0e0;
                background-color: #252525;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px;
                padding-right: 20px; /* Space for buttons */
            }}
            QSpinBox::up-button, QSpinBox::down-button, 
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
                background: #333;
                border-left: 1px solid #555;
                width: 16px;
            }}
            QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ border-left: 4px solid transparent; border-right: 4px solid transparent; border-bottom: 4px solid #aaa; }}
            QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 4px solid #aaa; }}

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
        
        # 1. Calculate geometry properties early
        radius = self.border_radius if not self.isMaximized() and not self.isFullScreen() else 0
        rect = self.rect()
        
        # 2. Draw Background
        # Use Source to REPLACE pixels to exact opacity. Prevents accumulation.
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        bg_alpha = int(self._bg_opacity * 255)
        # Base Color: Neutral Dark #1e1e1e (30,30,30)
        bg_color = QColor(30, 30, 30, bg_alpha)
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
        # Debug: Log paint event occasionally or on specific state
        # print(f"DEBUG: Painted {self.objectName()} with bg_opacity={self._bg_opacity}, alpha={bg_alpha}")

    def _add_default_controls(self):
        self.min_btn = TitleBarButton("_")
        self.min_btn.setObjectName("titlebar_minimize")
        self.min_btn.clicked.connect(self.showMinimized) # showMinimized is fine as it triggers WM_SYSCOMMAND internally
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
        """Hide minimize and maximize buttons (for dialogs like About)."""
        if hasattr(self, 'min_btn'):
            self.min_btn.hide()
        if hasattr(self, 'max_btn'):
            self.max_btn.hide()

    def toggle_maximize(self):
        """Toggle maximization using native WinAPI commands for better integration."""
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
            except:
                pass
        
        # Fallback for non-Windows or if API fails
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
        self._update_stylesheet()

    def add_title_bar_button(self, btn: TitleBarButton, index: int = 0):
        self.control_layout.insertWidget(index, btn)

    def add_title_bar_widget(self, widget: QWidget, index: int = 0):
        """Add a custom widget (e.g., QLabel) to the control area of the title bar."""
        self.control_layout.insertWidget(index, widget)

    def set_content_widget(self, widget: QWidget):
        layout = self.content_area.layout()
        if not layout:
            layout = QVBoxLayout(self.content_area)
            layout.setContentsMargins(10, 10, 10, 10)
        else:
            # Clear existing items if any
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                    
        layout.addWidget(widget)
        widget.installEventFilter(self) # Ensure top-level content handles resize cursor reset
        widget.setAttribute(Qt.WidgetAttribute.WA_Hover)

    def set_resizable(self, resizable: bool):
        self.resizable = resizable
    
    def set_title_bar_icon_visible(self, visible: bool):
        self.icon_label.setVisible(visible)

    # -- Event Overrides with Mixins delegation --
    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            # Sync Maximize Button Icon
            if hasattr(self, 'max_btn'):
                self.max_btn.setText("❐" if self.isMaximized() else "□")
            self._update_stylesheet()
            if self.isMaximized():
                self.main_layout.setContentsMargins(0, 0, 0, 0)
            elif self.isFullScreen():
                self.main_layout.setContentsMargins(0, 0, 0, 0)
            else:
                self.max_btn.setText("□")
                self.main_layout.setContentsMargins(0, 0, 5, 5)
        super().changeEvent(event)

    def eventFilter(self, obj, event):
        # Allow child widgets to process their own hover/mouse events without interference
        return super().eventFilter(obj, event)

    def showEvent(self, event):
        """Apply native styles once the window is shown and winId is valid."""
        super().showEvent(event)
        if not self._native_styles_applied:
            self._apply_native_styles()
            self._native_styles_applied = True

    def _apply_native_styles(self):
        """Apply Windows styles to enable native features like Snap and Shadows."""
        if os.name == 'nt':
            try:
                # Ensure window handle is created
                if not self.winId():
                    return
                    
                hwnd = int(self.winId())
                GWL_STYLE = -16
                WS_CAPTION = 0x00C00000
                WS_THICKFRAME = 0x00040000
                
                style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style | WS_CAPTION | WS_THICKFRAME)
                
                # Trigger frame recalc
                SWP_NOMOVE = 0x0002
                SWP_NOSIZE = 0x0001
                SWP_NOZORDER = 0x0004
                SWP_FRAMECHANGED = 0x0020
                user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
            except Exception as e:
                print(f"Failed to apply native styles: {e}")

    def nativeEvent(self, eventType, message):
        """Handle native Windows events for true frameless behavior."""
        try:
            if eventType == b"windows_generic_MSG":
                msg = ctypes.wintypes.MSG.from_address(int(message))
            else:
                return False, 0
        except:
            return False, 0
            
        WM_GETMINMAXINFO = 0x0024
        WM_NCCALCSIZE = 0x0083
        WM_NCHITTEST = 0x0084

        if msg.message == WM_GETMINMAXINFO:
            # Prevent 8px overhang when maximized
            try:
                info = ctypes.cast(msg.lParam, ctypes.POINTER(MINMAXINFO)).contents
                r = self.devicePixelRatioF()
                screen = self.screen().availableGeometry()
                # WinAPI expects physical pixels, Qt provides logical
                info.ptMaxTrackSize.x = int(screen.width() * r)
                info.ptMaxTrackSize.y = int(screen.height() * r)
                info.ptMaxSize.x = int(screen.width() * r)
                info.ptMaxSize.y = int(screen.height() * r)
                info.ptMaxPosition.x = 0
                info.ptMaxPosition.y = 0
                return True, 0
            except:
                pass
            
        if msg.message == WM_NCCALCSIZE:
            # Return True (1) to indicate valid client area (hides standard title bar)
            return True, 0
            
        if msg.message == WM_NCHITTEST:
            # Physical screen coordinates (High DPI Aware)
            x_phys = ctypes.c_short(msg.lParam & 0xffff).value
            y_phys = ctypes.c_short((msg.lParam >> 16) & 0xffff).value
            
            # Convert physical to Qt logical
            r = self.devicePixelRatioF()
            pt_logical = QPoint(int(x_phys / r), int(y_phys / r))
            local_pos = self.mapFromGlobal(pt_logical)
            lx, ly = local_pos.x(), local_pos.y()
            w, h = self.width(), self.height()
            
            # 1. Resize Handles (Skip if maximized)
            if not self.isMaximized() and not self.isFullScreen():
                margin = 8
                if lx < margin and ly < margin: return True, 13 # HTTOPLEFT
                if lx > w - margin and ly < margin: return True, 14 # HTTOPRIGHT
                if lx < margin and ly > h - margin: return True, 16 # HTBOTTOMLEFT
                if lx > w - margin and ly > h - margin: return True, 17 # HTBOTTOMRIGHT
                if lx < margin: return True, 10 # HTLEFT
                if lx > w - margin: return True, 11 # HTRIGHT
                if ly < margin: return True, 12 # HTTOP
                if ly > h - margin: return True, 15 # HTBOTTOM
            
            # 2. Universal Drag vs Interactive detection
            child = self.childAt(local_pos)
            
            # Whitelist: Components that SHOULD handle clicks (HTCLIENT)
            from PyQt6.QtWidgets import QAbstractButton, QAbstractScrollArea, QAbstractItemView, QLineEdit, QTextEdit, QComboBox, QSlider
            interactive_types = (QAbstractButton, QLineEdit, QTextEdit, QComboBox, QSlider, QAbstractScrollArea, QAbstractItemView)
            interactive_names = ["Sidebar", "ItemCard", "QuickTagPanel", "title_bar_controls"]
            
            # Check the widget under the mouse or its parents
            curr = child
            while curr:
                # If we hit an interactive class or a specifically named panel, return HTCLIENT
                if isinstance(curr, interactive_types) or curr.objectName() in interactive_names:
                    return False, 1 # HTCLIENT: Interaction required
                curr = curr.parentWidget()
            
            # Everything else (Labels, Background gaps, TitleBar empty area, root container) is DRAGGABLE
            return True, 2 # HTCAPTION
            
        return False, 0 


    # Manual mouse events are handled by the OS via nativeEvent (WM_NCHITTEST)
    # We do NOT override them unless we need specific child-interaction logic.
    # Standard child interaction works because we return HTCLIENT (1) for non-caption/non-border areas.

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen()
        super().keyPressEvent(event)

    def set_window_icon_from_path(self, path: str):
        try:
            image = QImage(path)
            if image.isNull():
                return
            
            # Optimization: Scale down BEFORE pixel-by-pixel processing to avoid millions of iterations.
            # 256x256 is more than enough for a window icon and title bar icon.
            if image.width() > 256 or image.height() > 256:
                image = image.scaled(256, 256, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                
            image = image.convertToFormat(QImage.Format.Format_ARGB32)
            # Simple threshold for "white" corners (to make them transparent for JPG icons)
            w, h = image.width(), image.height()
            threshold = 240
            
            # Process corners only for transparency (25% of edges for deeper coverage)
            cw, ch = int(w * 0.25), int(h * 0.25)
            
            # Helper to check and set transparency
            def process_pixel(px, py):
                p = image.pixelColor(px, py)
                if p.red() > threshold and p.green() > threshold and p.blue() > threshold:
                    image.setPixelColor(px, py, QColor(0, 0, 0, 0))

            # Top-left
            for y in range(ch):
                for x in range(cw):
                    process_pixel(x, y)
            # Top-right
            for y in range(ch):
                for x in range(w - cw, w):
                    process_pixel(x, y)
            # Bottom-left
            for y in range(h - ch, h):
                for x in range(cw):
                    process_pixel(x, y)
            # Bottom-right
            for y in range(h - ch, h):
                for x in range(w - cw, w):
                    process_pixel(x, y)
            
            pixmap = QPixmap.fromImage(image)
            self.icon_label.setPixmap(pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            self.icon_label.setVisible(True)
            self.setWindowIcon(QIcon(pixmap)) 
        except Exception as e:
            print(f"Failed to load icon: {e}")
            
    def set_default_icon(self):
        """Set a default system icon if no specific icon is provided."""
        from PyQt6.QtWidgets import QStyle, QApplication
        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon)
        if not icon.isNull():
             self.icon_label.setPixmap(icon.pixmap(24, 24))
             self.icon_label.setVisible(True)
             self.setWindowIcon(icon)

    def center_on_screen(self):
        """Center the window on its current screen."""
        screen = self.screen()
        if not screen: return
        geo = self.geometry()
        screen_geo = screen.availableGeometry()
        x = screen_geo.x() + (screen_geo.width() - geo.width()) // 2
        y = screen_geo.y() + (screen_geo.height() - geo.height()) // 2
        self.move(x, y)

class FramelessDialog(QDialog, Win32Mixin):
    """
    Common base class for all Link Master dialogs.
    Provides borderless, translucent, and 'flash-free' dark UI matching the main window.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 0. Preparation for "No White Flash"
        self.setWindowOpacity(0.0) # Hide immediately
        # WA_NoSystemBackground removed - causes transparency issues on some systems
        
        # 1. Base UI Props - Use Window instead of Dialog to prevent layering transparency bugs
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)  # Auto-delete on close to prevent ghost windows
        
        # 2. Force Dark Palette immediately
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#1e1e1e"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#1e1e1e"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#dddddd"))
        self.setPalette(palette)
        
        # 3. Force DWM Dark mode
        force_dark_mode(self)
        
        # 3. Apply WinAPI Styles (same stability as FramelessWindow)
        self._native_styles_applied = False
        
        # State
        self.border_radius = 8
        self._bg_opacity = 0.95
        self._content_opacity = 1.0

        self._init_frameless_ui()
        
        # 4. Show with short delay to ensure first paint is done
        self._auto_fade_in = True
        QTimer.singleShot(30, self._check_auto_fade)
        
    def _check_auto_fade(self):
        if self._auto_fade_in:
            self.setWindowOpacity(1.0)
            
    def _init_frameless_ui(self):
        # QDialog doesn't have setCentralWidget, so we use a main layout on self.
        
        # Main container
        self.container = QWidget(self)
        # self.container.setWindowFlags(Qt.WindowType.Widget) 
        # WA_NoSystemBackground removed - causes transparency issues on some systems
        self.container.setObjectName("FramelessContainer")
        self.container.installEventFilter(self)
        
        # Apply Base Styling
        self._update_stylesheet()
        
        # Set main layout for QDialog
        self.window_layout = QVBoxLayout(self)
        self.window_layout.setContentsMargins(0, 0, 0, 0)
        self.window_layout.addWidget(self.container)
        
        # Layout for Title Bar + Content
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # 1. Custom Title Bar
        self.title_bar = QWidget(self.container)
        self.title_bar.setObjectName("TitleBar")
        self.title_bar.setFixedHeight(32)
        self.title_bar.setStyleSheet("background-color: transparent;")
        
        tb_layout = QHBoxLayout(self.title_bar)
        tb_layout.setContentsMargins(10, 0, 5, 0)
        
        # Icon
        self.icon_label = QLabel(self.title_bar)
        self.icon_label.setFixedSize(24, 24)
        self.icon_label.setVisible(False)
        tb_layout.addWidget(self.icon_label)
        
        # Title
        self.title_label = QLabel("Dialog", self.title_bar)
        self.title_label.setStyleSheet("color: #cccccc; font-weight: bold; font-family: 'Segoe UI', sans-serif;")
        tb_layout.addWidget(self.title_label)
        
        tb_layout.addStretch()
        
        # Buttons
        # Buttons
        self.min_btn = TitleBarButton("_")
        self.min_btn.clicked.connect(self.showMinimized)
        self.min_btn.setVisible(False) # Hidden by default for dialogs
        tb_layout.addWidget(self.min_btn)
        
        self.max_btn = TitleBarButton("□")
        self.max_btn.clicked.connect(self.toggle_maximize)
        self.max_btn.setVisible(False) # Hidden by default for dialogs
        tb_layout.addWidget(self.max_btn)
        
        self.close_btn = TitleBarButton("✕")
        self.close_btn.set_colors(hover="#c42b1c", text="#cccccc")
        self.close_btn.clicked.connect(self.reject) # QDialog uses reject()
        tb_layout.addWidget(self.close_btn)
        
        self.main_layout.addWidget(self.title_bar)
        
        # 2. Content Area
        self.content_area = QWidget(self.container)
        self.content_area.setMouseTracking(True)
        self.content_area.installEventFilter(self)
        self.content_area.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.content_area)

    def set_background_opacity(self, opacity: float):
        self._bg_opacity = max(0.0, min(1.0, opacity))
        self.update()

    def paintEvent(self, event):
        """Paint background directly to prevent OS/Qt state interference."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 1. Geometry properties
        radius = self.border_radius if not self.isMaximized() else 0
        rect = self.rect()
        
        # 2. Draw Background
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        bg_alpha = int(self._bg_opacity * 255)
        # Consistent Dark Color
        bg_color = QColor(30, 30, 30, bg_alpha)
        
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        
        if self.isMaximized():
            painter.drawRect(rect)
        else:
            painter.drawRoundedRect(rect, radius, radius)
        
        # 3. Draw Border
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        if radius > 0:
            from PyQt6.QtGui import QPen
            painter.setPen(QPen(QColor(80, 80, 80, 100), 1))
            painter.drawRoundedRect(rect.adjusted(0, 0, -1, -1), radius, radius)
            
        painter.end()

    def _update_stylesheet(self):
        # Ensure the Main Window (Dialog) is fully transparent so only our container is seen
        self.setStyleSheet("background: transparent;")
        
        self.container.setStyleSheet(f"""
            QWidget#FramelessContainer {{
                background-color: transparent; /* Fixed: Prevents double-opacity */
                border: 1px solid #444;
                border-radius: {self.border_radius}px;
            }}
        """)
        
    def set_content_widget(self, widget):
        if self.content_layout.count() > 0:
            old = self.content_layout.takeAt(0).widget()
            if old: old.deleteLater()
        self.content_layout.addWidget(widget)

    def setWindowTitle(self, title: str):
        super().setWindowTitle(title)
        if hasattr(self, 'title_label'):
            self.title_label.setText(title)

    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    # Event Overrides (MUST be explicit for super() to work correctly in this class context)
    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMaximized():
                self.main_layout.setContentsMargins(0, 0, 0, 0)
                self.max_btn.setText("❐")
                self.container.setStyleSheet(f"""
                    QWidget#FramelessContainer {{
                        background-color: rgba(30, 30, 30, 1.0);
                        border: none;
                        border-radius: 0px;
                    }}
                """)
            else:
                self.max_btn.setText("□")
                self.main_layout.setContentsMargins(0, 0, 0, 0) # Base container margins
                self._update_stylesheet()
        super().changeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._native_styles_applied:
            self._apply_native_styles()
            self._native_styles_applied = True

    def _apply_native_styles(self):
        """Apply Windows styles for snap/shadows."""
        if os.name == 'nt':
            try:
                hwnd = int(self.winId())
                GWL_STYLE = -16
                WS_CAPTION = 0x00C00000
                WS_THICKFRAME = 0x00040000
                
                style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style | WS_CAPTION | WS_THICKFRAME)
                
                user32 = ctypes.windll.user32
                user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0020)
            except: pass

    def nativeEvent(self, eventType, message):
        """Standard NCHITTEST for Dialogs."""
        try:
            if eventType == b"windows_generic_MSG":
                msg = ctypes.wintypes.MSG.from_address(int(message))
            else: return False, 0
        except: return False, 0
        
        if msg.message == 0x0112: # WM_SYSCOMMAND
            if (msg.wParam & 0xFFF0) == 0xF030: # SC_MAXIMIZE
                self.toggle_maximize()
                return True, 0

        if msg.message == 0x0083: # WM_NCCALCSIZE
            return True, 0
            
        if msg.message == 0x0084: # WM_NCHITTEST
            x_phys = ctypes.c_short(msg.lParam & 0xffff).value
            y_phys = ctypes.c_short((msg.lParam >> 16) & 0xffff).value
            r = self.devicePixelRatioF()
            pt_logical = QPoint(int(x_phys / r), int(y_phys / r))
            pt = self.mapFromGlobal(pt_logical)
            lx, ly = pt.x(), pt.y()
            w, h = self.width(), self.height()
            
            # Resize
            margin = 8
            if lx < margin and ly < margin: return True, 13
            if lx > w - margin and ly < margin: return True, 14
            if lx < margin and ly > h - margin: return True, 16
            if lx > w - margin and ly > h - margin: return True, 17
            if lx < margin: return True, 10
            if lx > w - margin: return True, 11
            if ly < margin: return True, 12
            if ly > h - margin: return True, 15
            
            # Refined Drag Hit-Test (Dialog)
            child = self.childAt(pt)
            from PyQt6.QtWidgets import QAbstractButton, QAbstractScrollArea, QAbstractItemView, QLineEdit, QTextEdit, QComboBox, QSlider
            interactive_types = (QAbstractButton, QLineEdit, QTextEdit, QComboBox, QSlider, QAbstractScrollArea, QAbstractItemView)
            interactive_names = ["Sidebar", "MainContent", "ItemCard", "QuickTagPanel"]
            
            curr = child
            while curr:
                if isinstance(curr, interactive_types) or curr.objectName() in interactive_names:
                    return False, 1 # HTCLIENT
                curr = curr.parentWidget()
                
            return True, 2 # HTCAPTION
            
        return False, 0

    # Legacy mouse events removed in favor of nativeEvent

    def center_on_screen(self):
        """Center the dialog on its current screen."""
        screen = self.screen()
        if not screen: return
        geo = self.geometry()
        screen_geo = screen.availableGeometry()
        x = screen_geo.x() + (screen_geo.width() - geo.width()) // 2
        y = screen_geo.y() + (screen_geo.height() - geo.height()) // 2
        self.move(x, y)
