from PyQt6.QtWidgets import QWidget, QLabel, QScrollArea, QHBoxLayout, QPushButton, QSizePolicy, QFrame
from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QMimeData
from PyQt6.QtGui import QMouseEvent, QWheelEvent, QDragEnterEvent, QDropEvent, QPixmap
import os

class TagWidget(QLabel):
    clicked = pyqtSignal(str, bool) # tag_value, is_right_click
    icon_dropped = pyqtSignal(str, str)  # tag_value, image_path

    def __init__(self, tag_data, parent=None, is_special_btn=False):
        super().__init__(parent)
        self.is_special_btn = is_special_btn
        
        if is_special_btn:
            self.tag_data = {'name': tag_data, 'value': tag_data}
            self.setText(tag_data)
        else:
            self.tag_data = tag_data 
            prefer_emoji = tag_data.get('prefer_emoji', False)
            emoji = tag_data.get('emoji', '')
            icon_path = tag_data.get('icon', '')
            
            if not prefer_emoji and icon_path and os.path.exists(icon_path):
                self.setText("")
            else:
                self.setText(emoji or tag_data.get('name', ''))
            
        self.selected = False
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setProperty("is_tag", True)
        
        if not is_special_btn and not self.tag_data.get('prefer_emoji') and self.tag_data.get('icon'):
            icon_path = self.tag_data.get('icon')
            if os.path.exists(icon_path):
                 self._set_icon(icon_path)

        # Phase 1.1.8: Set unique objectName based on tag value
        tag_val = self.tag_data.get('value', 'unnamed')
        self.setObjectName(f"tag_btn_{tag_val}")

        if not is_special_btn:
             # display_mode can be: 'text', 'text_symbol', 'symbol', 'image'
             self.display_mode = tag_data.get('display_mode', 'text')
             # Backward compatibility: prefer_emoji=False used to mean 'image' if icon exists
             if 'display_mode' not in tag_data and not tag_data.get('prefer_emoji', True) and self.tag_data.get('icon'):
                 self.display_mode = 'image'
             
             self._update_display()
             self.update_style()
             
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Enable DnD for image icon setting
        if not is_special_btn:
            self.setAcceptDrops(True)

    def _update_display(self):
        """Update label content based on display_mode."""
        if self.is_special_btn: return
        
        mode = self.display_mode
        name = self.tag_data.get('name', '')
        emoji = self.tag_data.get('emoji', '')
        icon_path = self.tag_data.get('icon', '')
        
        self.setPixmap(QPixmap()) # Clear icon first
        
        if mode == 'image' and icon_path and os.path.exists(icon_path):
            self.setText("")
            self._set_icon(icon_path)
        elif mode == 'symbol' and emoji:
            self.setText(emoji)
        elif mode == 'text_symbol' and emoji:
            self.setText(f"{emoji} {name}")
        else: # 'text' or fallback
            self.setText(name)
            
    def _set_icon(self, path):
        pix = QPixmap(path)
        if not pix.isNull():
            # Resize icon for better visibility (22x22)
            pix = pix.scaled(22, 22, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.setPixmap(pix)
            self.setToolTip(self.tag_data.get('name'))
            self.setMinimumWidth(28)

    def set_selected(self, selected):
        self.selected = selected
        self.update_style()

    def update_style(self):
        if self.is_special_btn: return
        
        if self.tag_data.get('is_sep'):
            self.setStyleSheet("color: #666; font-weight: bold; padding: 0 5px; background: transparent;")
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.setText("|")
            return

        if self.selected:
            self.setStyleSheet("""
                QLabel {
                    background-color: #2980b9; color: white; border: 1px solid #3498db;
                    border-radius: 4px; padding: 2px 6px; font-weight: bold; font-size: 11px;
                }
            """)
        else:
            self.setStyleSheet("""
                QLabel {
                    background-color: #333; color: #ddd; border: 1px solid #555;
                    border-radius: 4px; padding: 2px 6px; font-size: 11px;
                }
                QLabel:hover { background-color: #444; border-color: #777; }
            """)

    def mousePressEvent(self, event: QMouseEvent):
        if self.tag_data.get('is_sep'): return
        is_right = event.button() == Qt.MouseButton.RightButton
        # User requested: "Right-click is for exclusive selection (one method)"
        # We restore the original clicked emission where is_right determines behavioral branch in TagBar
        self.clicked.emit(self.tag_data.get('value'), is_right)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if self.is_special_btn or self.tag_data.get('is_sep'):
            event.ignore()
            return
        mime = event.mimeData()
        if mime.hasUrls():
            for url in mime.urls():
                path = url.toLocalFile()
                if path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.ico', '.svg')):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        if self.is_special_btn or self.tag_data.get('is_sep'):
            event.ignore()
            return
        mime = event.mimeData()
        if mime.hasUrls():
            for url in mime.urls():
                path = url.toLocalFile()
                if path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.ico', '.svg')):
                    # User requested: "Videos/Images accepted and resized to icon"
                    # Replacing PIL with PyQt6 QImage for environment stability
                    try:
                        from PyQt6.QtGui import QImage
                        import os
                        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                        res_dir = os.path.join(project_root, "resource", "tags")
                        if not os.path.exists(res_dir): os.makedirs(res_dir)
                        
                        tag_val = self.tag_data.get('value', 'unknown')
                        dest_name = f"tag_{tag_val}_{os.path.basename(path)}"
                        dest_path = os.path.join(res_dir, dest_name)
                        
                        # Use QImage instead of PIL
                        img = QImage(path)
                        if not img.isNull():
                            img = img.scaled(28, 28, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                            img.save(dest_path)
                        else:
                            # Fallback to copy if QImage failed but path exists
                            import shutil
                            shutil.copy2(path, dest_path)
                        
                        # Update tag data and visuals
                        self.tag_data['icon'] = dest_path
                        self.tag_data['prefer_emoji'] = False # This is for backward compatibility
                        self.tag_data['display_mode'] = 'image' # Set new display mode
                        self.display_mode = 'image'
                        self.icon_dropped.emit(self.tag_data.get('value'), dest_path)
                        self._update_display() # Use the new update display method
                        self.update_style()
                        event.acceptProposedAction()
                        return
                    except Exception as e:
                        print(f"Tag DnD Drop processing error: {e}")
        event.ignore()
        
    def toggle_display_mode(self):
        """Cycle through 5 display modes."""
        if self.is_special_btn or self.tag_data.get('is_sep'): return
        
        modes = ['text', 'text_symbol', 'symbol', 'image', 'image_text']
        idx = modes.index(self.display_mode) if self.display_mode in modes else 0
        self.display_mode = modes[(idx + 1) % len(modes)]
        
        # Ensure 'image' / 'image_text' is skipped if no icon exists
        if (self.display_mode == 'image' or self.display_mode == 'image_text') and (not self.tag_data.get('icon') or not os.path.exists(self.tag_data.get('icon'))):
            self.display_mode = 'text'

        self.tag_data['display_mode'] = self.display_mode
        # Maintain prefer_emoji for backward compatibility
        self.tag_data['prefer_emoji'] = (self.display_mode != 'image')
        
        self._update_display()
        self.update_style()
        self.icon_dropped.emit(self.tag_data.get('value'), self.tag_data.get('icon') or '')
            
class TagBar(QWidget):
    tags_changed = pyqtSignal(list)
    request_add_tag = pyqtSignal()
    request_edit_tags = pyqtSignal()
    tag_icon_updated = pyqtSignal(str, str)  # tag_value, image_path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(34)
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(5)
        
        # Scroll Area for Tags
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("background: transparent;")
        # Prevent scroll area from being treated as a separate window
        self.scroll.setWindowFlags(Qt.WindowType.Widget)
        
        self.container = QWidget(self.scroll)
        self.container.setStyleSheet("background: transparent;")
        self.tags_layout = QHBoxLayout(self.container)
        self.tags_layout.setContentsMargins(0, 0, 0, 0)
        self.tags_layout.setSpacing(5)
        self.tags_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        self.scroll.setWidget(self.container)
        main_layout.addWidget(self.scroll, 1)
        
        from src.core.lang_manager import _
        # Integrated Edit Button
        self.edit_btn = QPushButton("E", self)
        self.edit_btn.setObjectName("tagbar_edit_btn")
        self.edit_btn.setFixedSize(24, 24)
        self.edit_btn.setToolTip(_("Edit Frequent Tags"))
        self.edit_btn.clicked.connect(self.request_edit_tags.emit)
        self.edit_btn.setStyleSheet("""
            QPushButton { 
                background-color: #e67e22; color: white; border-radius: 12px; 
                border: 1px solid #d35400; font-weight: bold; font-size: 10px;
            }
            QPushButton:hover { background-color: #d35400; }
        """)
        main_layout.addWidget(self.edit_btn)
        
        self.tags = []
        self.selected_tags = set()
        self.widget_map = {}
        self.tag_widgets = []
        
        # Enable wheel scrolling
        self.scroll.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj == self.scroll.viewport() and event.type() == QEvent.Type.Wheel:
            # Shift mouse wheel for horizontal scroll
            delta = event.angleDelta().y()
            self.scroll.horizontalScrollBar().setValue(
                self.scroll.horizontalScrollBar().value() - delta
            )
            return True
        return super().eventFilter(obj, event)
        
    def refresh_tags(self):
        """Refresh visuals for current tags."""
        self.set_tags(self.tags)

    def set_tags(self, tags: list):
        # Clear
        while self.tags_layout.count():
            item = self.tags_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        self.tags = tags
        self.tag_widgets = []
        self.widget_map = {}
        
        # Hide scroll area if no tags to "close up" space
        self.scroll.setVisible(len(tags) > 0)
        
        for t in tags:
            w = TagWidget(t, parent=self.container)
            w.clicked.connect(self._on_tag_clicked)
            w.icon_dropped.connect(self._on_icon_dropped)
            self.tags_layout.addWidget(w)
            self.tag_widgets.append(w)
            if not t.get('is_sep'):
                self.widget_map[t.get('value')] = w

    def _on_icon_dropped(self, tag_value, image_path):
        """Relay tag icon change to parent for persistence."""
        self.tag_icon_updated.emit(tag_value, image_path)

    def _on_tag_clicked(self, tag_value, is_right):
        if is_right:
            idx = -1
            for i, w in enumerate(self.tag_widgets):
                if w.tag_data.get('value') == tag_value:
                    idx = i
                    break
            if idx == -1: return

            start = 0
            end = len(self.tag_widgets)
            for i in range(idx, -1, -1):
                if self.tag_widgets[i].tag_data.get('is_sep'):
                    start = i + 1
                    break
            for i in range(idx, len(self.tag_widgets)):
                if self.tag_widgets[i].tag_data.get('is_sep'):
                    end = i
                    break
            
            for i in range(start, end):
                t = self.tag_widgets[i].tag_data.get('value')
                if t in self.selected_tags: self.selected_tags.remove(t)
            
            self.selected_tags.add(tag_value)
        else:
            if tag_value in self.selected_tags:
                self.selected_tags.remove(tag_value)
            else:
                self.selected_tags.add(tag_value)
        
        self._refresh_visuals()
        self.tags_changed.emit(list(self.selected_tags))

    def _refresh_visuals(self):
        for w in self.tag_widgets:
            val = w.tag_data.get('value')
            w.set_selected(val in self.selected_tags)

    def get_selected_tags(self):
        return list(self.selected_tags)

    def get_selected_segments(self):
        """
        Return selected tags grouped by separators.
        Example: [[TagA, TagB], [TagC]] means (TagA OR TagB) AND (TagC)
        """
        segments = []
        current_segment = []
        
        for w in self.tag_widgets:
            if w.tag_data.get('is_sep'):
                if current_segment:
                    segments.append(current_segment)
                    current_segment = []
            else:
                val = w.tag_data.get('value')
                if val in self.selected_tags:
                    current_segment.append(val.lower())
                    
        if current_segment:
            segments.append(current_segment)
            
        return segments

    def clear_selection(self):
        self.selected_tags.clear()
        self._refresh_visuals()
        self.tags_changed.emit([])
