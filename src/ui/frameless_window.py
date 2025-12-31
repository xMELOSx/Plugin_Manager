""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を介すること。
"""

from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox
from PyQt6.QtCore import Qt, QPoint, QSize, QEvent
from PyQt6.QtGui import QColor, QPixmap, QImage, QIcon
from src.ui.title_bar_button import TitleBarButton
from src.ui.window_mixins import Win32Mixin, DraggableMixin, ResizableMixin

class FramelessWindow(QMainWindow, Win32Mixin, DraggableMixin, ResizableMixin):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Mixin Inits
        self.init_drag()
        self.init_resize()
        
        # State
        self.border_radius = 8
        self._bg_opacity = 0.9 # Default Background 90%
        self._content_opacity = 1.0 # Default Content 100%
        
        self._init_frameless_ui()

    def _init_frameless_ui(self):
        # Main container
        self.container = QWidget()
        self.container.setObjectName("FramelessContainer")
        self.container.setMouseTracking(True)
        self.container.installEventFilter(self)
        
        self._update_stylesheet()
        self.setCentralWidget(self.container)
        
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Title Bar
        self.title_bar = QWidget()
        self.title_bar.setObjectName("TitleBar")
        self.title_bar.setStyleSheet("background-color: transparent;")
        self.title_bar.setFixedHeight(40)
        self.title_bar.setMouseTracking(True)
        # self.title_bar.installEventFilter(self) # Redundant
        
        self.title_bar_layout = QHBoxLayout(self.title_bar)
        self.title_bar_layout.setContentsMargins(10, 5, 10, 5)
        self.title_bar_layout.setSpacing(2)

        # Icon Label
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(24, 24)
        self.icon_label.setVisible(False)
        self.title_bar_layout.addWidget(self.icon_label)
        
        # Title Label
        self.title_label = QLabel("Application")
        self.title_label.setStyleSheet("padding-left: 5px;")
        self.title_bar_layout.addWidget(self.title_label)
        
        self.title_bar_layout.addStretch()
        
        # Center Container for Executable Links (Phase 28)
        self.title_bar_center = QWidget()
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
        self.content_area = QWidget()
        self.main_layout.addWidget(self.content_area)
        self.content_area.setMouseTracking(True)
        # self.content_area.installEventFilter(self) # Redundant

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
        """Sets the text/content opacity (0.0 to 1.0)."""
        self._content_opacity = max(0.0, min(1.0, opacity))
        self._update_stylesheet()

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
                background-color: {bg_color};
                border: 1px solid rgba(68, 68, 68, {bg_alpha});
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
                background-color: transparent; /* Keep transparent to show window blur if needed, but border is key */
            }}
            
            QTreeView {{
                background-color: rgba(30, 30, 30, {bg_alpha}); /* Tree can remain semi-transparent or opaque? User said Dropdown specifically. Let's keep tree semi for now, but ensure text is bright. */
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
            QCheckBox::indicator:checked {{
                background: #3498db;
                border: 2px solid #3498db;
                image: url({check_icon_path});
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

    def set_content_widget(self, widget: QWidget):
        if self.content_area.layout():
            QWidget().setLayout(self.content_area.layout())
        layout = QVBoxLayout(self.content_area)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(widget)

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
        if event.type() == QEvent.Type.MouseMove:
            if self.resizable and not self.isMaximized() and not self.isFullScreen() and not self._resizing and not self.draggable:
                global_pos = event.globalPosition().toPoint()
                local_pos = self.mapFromGlobal(global_pos)
                
                # IMPORTANT: Only call _update_cursor if we are actually over a region 
                # that might need a cursor change (near edges).
                edges = self._get_resize_edges(local_pos)
                if edges or self.cursor().shape() != Qt.CursorShape.ArrowCursor:
                    self._update_cursor(edges)
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
            
            # Process corners only for transparency (20% of edges)
            cw, ch = int(w * 0.2), int(h * 0.2)
            
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
