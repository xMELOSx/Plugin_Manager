from PyQt6.QtWidgets import QMainWindow, QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox
from PyQt6.QtCore import Qt, QPoint, QSize, QEvent, QTimer
from PyQt6.QtGui import QColor, QPixmap, QImage, QIcon, QPalette, QPainter, QBrush
from src.ui.title_bar_button import TitleBarButton
from src.ui.window_mixins import Win32Mixin, DraggableMixin, ResizableMixin
import os
import ctypes

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

class FramelessWindow(QMainWindow, Win32Mixin, DraggableMixin, ResizableMixin):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 0. Preparation for "No White Flash"
        self.setWindowOpacity(0.0) # Hide immediately
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        # self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent) # Remove: may cause alpha accumulation on some systems
        
        
        # 1. Base UI Props
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        # Enable transparency - this is the ONLY attribute we need for semi-transparent background
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 2. Force DWM Dark mode (for window border color)
        force_dark_mode(self)
        
        # Mixin Inits
        self.init_drag()
        self.init_resize()
        
        # State
        self.border_radius = 8
        self._bg_opacity = 0.9 # Default Background 90%
        self._content_opacity = 1.0 # Default Content 100%
        
        self._init_frameless_ui()
        
        # 4. Show with short delay to ensure first paint is done
        QTimer.singleShot(30, lambda: self.setWindowOpacity(1.0))

    def _init_frameless_ui(self):
        # Ensure the Window itself is transparent so only our painted background/container is seen
        self.setStyleSheet("background: transparent;")
        
        # Main container - uses parent's paintEvent for background
        self.container = QWidget(self)
        self.container.setObjectName("FramelessContainer")
        self.container.setMouseTracking(True)
        self.container.installEventFilter(self)
        self.container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.container.setAttribute(Qt.WidgetAttribute.WA_Hover)
        
        self._update_stylesheet()
        self.setCentralWidget(self.container) # Assuming set_content_widget is a typo and it should be setCentralWidget
        
        # Debug window should be opaque for better readability
        # Now that FramelessDialog (via LinkMasterDebugWindow inheritance) has paintEvent, this will work.
        # But wait, LinkMasterDebugWindow inherits FramelessWindow, which ALREADY has paintEvent!
        # The user's issue with DebugWindow "half transparency" was due to default 0.9 opacity.
        self.set_background_opacity(0.95)

        
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Title Bar
        self.title_bar = QWidget(self.container)
        self.title_bar.setObjectName("TitleBar")
        self.title_bar.setStyleSheet("background-color: transparent;")
        self.title_bar.setFixedHeight(40)
        self.title_bar.setMouseTracking(True)
        # self.title_bar.installEventFilter(self) # Redundant
        
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
        
        # Center Container for Executable Links (Phase 28)
        self.title_bar_center = QWidget(self.title_bar)
        self.title_bar_center_layout = QHBoxLayout(self.title_bar_center)
        self.title_bar_center_layout.setContentsMargins(0, 0, 0, 0)
        self.title_bar_center_layout.setSpacing(5)
        self.title_bar_layout.addWidget(self.title_bar_center)
        
        self.title_bar_layout.addStretch()
        
        # Gap between handle area and buttons
        self.title_bar_layout.addSpacing(10) 
        
        # Custom Buttons Area
        self.control_layout = QHBoxLayout()
        self.control_layout.setSpacing(1)
        self.title_bar_layout.addLayout(self.control_layout)

        # Default Controls (Min/Max/Close)
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
        # Background is handled by paintEvent, no need to re-apply global stylesheet
        self.update()

    def set_content_opacity(self, opacity: float):
        """Sets the text/content opacity (0.0 to 1.0).
        
        Optimization: Uses a short timer to debounce stylesheet updates during slider movement.
        """
        self._content_opacity = max(0.0, min(1.0, opacity))
        
        if not hasattr(self, '_opacity_timer'):
            self._opacity_timer = QTimer(self)
            self._opacity_timer.setSingleShot(True)
            self._opacity_timer.timeout.connect(self._update_stylesheet)
        
        self._opacity_timer.start(30) # 30ms debounce

    def _update_stylesheet(self):
        radius = f"{self.border_radius}px" if not self.isMaximized() and not self.isFullScreen() else "0px"
        check_icon_path = "src/assets/checkmark.svg"
        
        # Calculate RGBA for background
        bg_alpha = int(self._bg_opacity * 255)
        bg_color = f"rgba(43, 43, 43, {bg_alpha})" # #2b2b2b
        
        # Calculate RGBA for text
        text_alpha = self._content_opacity # 0.0 - 1.0
        text_color_rgba = f"rgba(221, 221, 221, {text_alpha})" # #ddd
        
        self.container.setStyleSheet(f"""
            #FramelessContainer {{
                /* Background is painted by paintEvent - keep transparent here */
                background: transparent;
                border-radius: {radius};
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
                image: url({check_icon_path});
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
        
        # Use Source to REPLACE pixels to exact opacity. 
        # Prevents both accumulation (darker) and flicker (clearing).
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        
        # Calculate color with opacity
        bg_alpha = int(self._bg_opacity * 255)
        # Ensure we clamp alpha
        bg_alpha = max(0, min(255, bg_alpha))
        bg_color = QColor(43, 43, 43, bg_alpha)
        
        # DEBUG: Log opacity (Removed)
        
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        
        radius = self.border_radius if not self.isMaximized() and not self.isFullScreen() else 0
        
        if self.isMaximized():
             painter.drawRect(self.rect())
        else:
             painter.drawRoundedRect(self.rect(), radius, radius)
        
        # Draw border (SourceOver to blend ON TOP of background)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        border_alpha = int(self._bg_opacity * 255)
        if radius > 0:
            from PyQt6.QtGui import QPen
            painter.setPen(QPen(QColor(68, 68, 68, border_alpha), 1))
            painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), radius, radius)
            
        painter.end()
        # Debug: Log paint event occasionally or on specific state
        # print(f"DEBUG: Painted {self.objectName()} with bg_opacity={self._bg_opacity}, alpha={bg_alpha}")

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
        """Hide minimize and maximize buttons (for dialogs like About)."""
        if hasattr(self, 'min_btn'):
            self.min_btn.hide()
        if hasattr(self, 'max_btn'):
            self.max_btn.hide()

    def toggle_maximize(self):
        # Freeze updates to hide the "jump" (move then resize) behavior
        self.setUpdatesEnabled(False) 
        
        if self.isMaximized():
            self.showNormal()
            self.max_btn.setText("□")
        else:
            self.showMaximized()
            self.max_btn.setText("❐")
            
        self._update_stylesheet()
        self.setUpdatesEnabled(True)

    def toggle_fullscreen(self):
        self.setUpdatesEnabled(False)
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
        self._update_stylesheet()
        self.setUpdatesEnabled(True)

    def add_title_bar_button(self, btn: TitleBarButton, index: int = 0):
        self.control_layout.insertWidget(index, btn)

    def add_title_bar_widget(self, widget: QWidget, index: int = 0):
        """Add a custom widget (e.g., QLabel) to the control area of the title bar."""
        self.control_layout.insertWidget(index, widget)

    def set_content_widget(self, widget: QWidget):
        # Clear old layout properly without creating orphan widgets
        old_layout = self.content_area.layout()
        if old_layout:
            # Delete all widgets in old layout
            while old_layout.count():
                item = old_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            # Delete the old layout itself
            old_layout.deleteLater()
        
        layout = QVBoxLayout(self.content_area)
        layout.setContentsMargins(10, 10, 10, 10)
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
            self._update_stylesheet()
            if self.isMaximized():
                self.max_btn.setText("❐")
                self.main_layout.setContentsMargins(0, 0, 0, 0)
            elif self.isFullScreen():
                self.main_layout.setContentsMargins(0, 0, 0, 0)
            else:
                self.max_btn.setText("□")
                self.main_layout.setContentsMargins(0, 0, 5, 5)
        super().changeEvent(event)

    def eventFilter(self, obj, event):
        # Resize Cursor Hover Handling (Even over child widgets via HoverMove)
        if event.type() in [QEvent.Type.MouseMove, QEvent.Type.HoverMove]:
            if self.resizable and not self.isMaximized() and not self.isFullScreen() and not getattr(self, '_resizing', False) and not getattr(self, 'draggable', False):
                # For HoverMove, the position is in event.position()
                pos = event.position().toPoint() if event.type() == QEvent.Type.HoverMove else event.pos()
                
                # Use mapFromGlobal if obj is a child widget filtering events
                if obj != self:
                    pos = self.mapFromGlobal(obj.mapToGlobal(pos))
                
                edges = self._get_resize_edges(pos)
                self._update_cursor(edges)
        
        elif event.type() == QEvent.Type.HoverLeave:
             # Reset cursor when leaving the window or moving deep into content if needed
             self.setCursor(Qt.CursorShape.ArrowCursor)

        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # 1. Resize
            if not self.isMaximized() and not self.isFullScreen():
                if self.handle_resize_press(event):
                    return
            
            # 2. Drag
            # Check ignored widgets
            child = self.childAt(event.pos())
            if isinstance(child, (QPushButton, QCheckBox)): 
                 pass # Ignored
            
            self.handle_drag_press(event)
        
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # Resize
        if not self.isMaximized() and not self.isFullScreen():
            self.handle_resize_move(event)
            if self._resizing: return

        # Drag
        if not self.isMaximized() and not self.isFullScreen():
            self.handle_drag_move(event)
            
        # Cursor update handled by eventFilter mostly, but ensure:
        if not self._resizing and not self.draggable:
             edges = self._get_resize_edges(event.pos())
             self._update_cursor(edges)
             
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.handle_drag_release(event)
            self.handle_resize_release(event)
            self.setCursor(Qt.CursorShape.ArrowCursor) 
            edges = self._get_resize_edges(event.pos())
            self._update_cursor(edges)
            
        super().mouseReleaseEvent(event)

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

class FramelessDialog(QDialog, Win32Mixin, DraggableMixin, ResizableMixin):
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
        
        # Mixin Inits
        self.init_drag()
        self.init_resize()
        
        # State
        self.border_radius = 8
        self._bg_opacity = 0.95 # Dialogs usually more opaque
        self._content_opacity = 1.0
        
        # Initialize Mixin States securely
        self._is_resizing = False
        self._is_dragging = False
        self._resize_edge = None
        self._drag_pos = None

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
        """Paint background directly using CompositionMode_Source to prevent transparency accumulation."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Use Source to REPLACE pixels to exact opacity. 
        # Prevents both accumulation (darker) and flicker (clearing).
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        
        # Calculate color with opacity
        bg_alpha = int(self._bg_opacity * 255)
        bg_alpha = max(0, min(255, bg_alpha))
        bg_color = QColor(43, 43, 43, bg_alpha)
        
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        
        rect = self.rect()
        radius = self.border_radius if not self.isMaximized() else 0
        
        if self.isMaximized():
            painter.drawRect(rect)
        else:
            painter.drawRoundedRect(rect, radius, radius)
        
        # Draw border (SourceOver to blend ON TOP of background)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        border_alpha = int(self._bg_opacity * 255)
        if radius > 0:
            from PyQt6.QtGui import QPen
            painter.setPen(QPen(QColor(68, 68, 68, border_alpha), 1))
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
        widget.installEventFilter(self)
        widget.setAttribute(Qt.WidgetAttribute.WA_Hover)

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

    def set_default_icon(self):
        """Set a default system icon if no specific icon is provided."""
        from PyQt6.QtWidgets import QStyle, QApplication
        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon)
        if not icon.isNull():
             self.icon_label.setPixmap(icon.pixmap(24, 24))
             self.icon_label.setVisible(True)
             self.setWindowIcon(icon)

    def eventFilter(self, obj, event):
        # Resize Cursor Hover Handling
        if event.type() in [QEvent.Type.MouseMove, QEvent.Type.HoverMove]:
            if getattr(self, 'resizable', False) and not self.isMaximized() and not getattr(self, '_is_resizing', False) and not getattr(self, '_is_dragging', False):
                pos = event.position().toPoint() if event.type() == QEvent.Type.HoverMove else event.pos()
                if obj != self:
                    pos = self.mapFromGlobal(obj.mapToGlobal(pos))
                
                edges = self._get_resize_edges(pos)
                self._update_cursor(edges)
        
        elif event.type() == QEvent.Type.HoverLeave:
             self.setCursor(Qt.CursorShape.ArrowCursor)

        # Dragging logic - Check if title_bar exists first to avoid AttributeError during init
        if hasattr(self, 'title_bar') and obj == self.title_bar:
            if event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self._is_dragging = True
                    self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                    return True
            elif event.type() == QEvent.Type.MouseMove:
                if self._is_dragging:
                    self.move(event.globalPosition().toPoint() - self._drag_pos)
                    return True
            elif event.type() == QEvent.Type.MouseButtonRelease:
                self._is_dragging = False
                return True
            elif event.type() == QEvent.Type.MouseButtonDblClick:
                 self.toggle_maximize()
                 return True

        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # 1. Resize (Delegated to ResizableMixin)
            if not self.isMaximized() and not self.isFullScreen():
                if self.handle_resize_press(event):
                    return
            
            # 2. Drag (Delegated to DraggableMixin)
            child = self.childAt(event.pos())
            if isinstance(child, (QPushButton, QCheckBox)): 
                 pass # Ignored
            else:
                self.handle_drag_press(event)
        
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # Resize (Delegated to ResizableMixin)
        if not self.isMaximized() and not self.isFullScreen():
            self.handle_resize_move(event)
            # ResizableMixin handles _resizing state internally
            if getattr(self, '_resizing', False): return

        # Drag (Delegated to DraggableMixin)
        if not self.isMaximized() and not self.isFullScreen():
            self.handle_drag_move(event)
            
        # Cursor update handled by ResizableMixin logic mostly, but explicit update for hover
        if not getattr(self, '_resizing', False) and not getattr(self, 'draggable', False):
             edges = self._get_resize_edges(event.pos())
             self._update_cursor(edges)
             
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.handle_drag_release(event)
            self.handle_resize_release(event)
            
            # Cursor reset
            self.setCursor(Qt.CursorShape.ArrowCursor) 
            edges = self._get_resize_edges(event.pos())
            self._update_cursor(edges)
            
        super().mouseReleaseEvent(event)

    def center_on_screen(self):
        """Center the dialog on its current screen."""
        screen = self.screen()
        if not screen: return
        geo = self.geometry()
        screen_geo = screen.availableGeometry()
        x = screen_geo.x() + (screen_geo.width() - geo.width()) // 2
        y = screen_geo.y() + (screen_geo.height() - geo.height()) // 2
        self.move(x, y)
