"""
Preview Dialog Classes for Link Master

Contains:
- PreviewItemWidget: Custom widget for each preview item in the list
- PreviewTableDialog: Dialog to manage multiple preview files with drag-and-drop reordering
- FullPreviewDialog: Gallery-style dialog to display large previews of selected images
"""

import os
import time
import subprocess
from PyQt6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, 
                              QLabel, QPushButton, QListWidget, QListWidgetItem,
                              QAbstractItemView, QMenu, QMessageBox, QFileDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap
from src.core.lang_manager import _


class PreviewItemWidget(QWidget):
    """Custom widget for each preview item in the list."""
    removed = pyqtSignal(str)  # Emitted when item is removed, passes path
    
    def __init__(self, path: str, parent_dialog=None):
        super().__init__()
        self.path = path
        self.parent_dialog = parent_dialog
        self._init_ui()
    
    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 3, 5, 3)
        layout.setSpacing(5)
        
        # Drag Handle (☰)
        drag_label = QLabel("☰")
        drag_label.setFixedWidth(20)
        drag_label.setStyleSheet("color: #888; font-size: 14px;")
        drag_label.setCursor(Qt.CursorShape.SizeAllCursor)
        drag_label.setToolTip(_("Drag to reorder"))
        layout.addWidget(drag_label)
        
        # Path Label (stretch)
        self.path_label = QLabel(self.path)
        self.path_label.setToolTip(self.path)
        self.path_label.setStyleSheet("color: #e0e0e0;")
        layout.addWidget(self.path_label, 1)
        
        # Detect if file is an image for conditional button visibility
        ext = os.path.splitext(self.path)[1].lower()
        is_image = ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp']
        
        # Button Order: Icon → Crop → Launch → Explorer → Delete
        btn_style = "QPushButton { padding: 2px 5px; } QPushButton:hover { background-color: #5d5d5d; }"
        
        # Icon Sync (✨) - Images only
        if is_image:
            sync_btn = QPushButton("✨")
            sync_btn.setToolTip(_("Set as folder icon"))
            sync_btn.setFixedWidth(28)
            sync_btn.setStyleSheet(btn_style)
            sync_btn.clicked.connect(self._sync_to_icon)
            layout.addWidget(sync_btn)
            
            # Crop (✂️) - Images only
            crop_btn = QPushButton("✂")
            crop_btn.setToolTip(_("Free crop image"))
            crop_btn.setFixedWidth(28)
            crop_btn.setStyleSheet(btn_style)
            crop_btn.clicked.connect(self._crop_image)
            layout.addWidget(crop_btn)
        else:
            # Spacers for alignment
            for i in range(2): # 💡 FIX: Use 'i' instead of '_' to avoid shadowing translation function
                spacer = QWidget()
                spacer.setFixedWidth(28)
                layout.addWidget(spacer)
        
        # Open File (🚀)
        open_btn = QPushButton("🚀")
        open_btn.setToolTip(_("Open in external app"))
        open_btn.setFixedWidth(28)
        open_btn.setStyleSheet(btn_style)
        open_btn.clicked.connect(self._open_file)
        layout.addWidget(open_btn)
        
        # Open in Explorer (📁)
        explorer_btn = QPushButton("📁")
        explorer_btn.setToolTip(_("Open folder in Explorer"))
        explorer_btn.setFixedWidth(28)
        explorer_btn.setStyleSheet(btn_style)
        explorer_btn.clicked.connect(self._open_in_explorer)
        layout.addWidget(explorer_btn)
        
        # Delete (❌)
        del_btn = QPushButton("❌")
        del_btn.setFixedWidth(28)
        del_btn.setStyleSheet(btn_style)
        del_btn.clicked.connect(self._remove)
        layout.addWidget(del_btn)
    
    def _sync_to_icon(self):
        if self.parent_dialog and hasattr(self.parent_dialog, '_sync_to_icon'):
            self.parent_dialog._sync_to_icon(self.path)
    
    def _crop_image(self):
        if self.parent_dialog and hasattr(self.parent_dialog, '_crop_image'):
            self.parent_dialog._crop_image(self.path)
    
    def _open_file(self):
        if os.path.exists(self.path):
            os.startfile(self.path)
    
    def _open_in_explorer(self):
        norm_path = os.path.normpath(self.path)
        if os.path.exists(norm_path):
            subprocess.Popen(['explorer', '/select,', norm_path])
    
    def _remove(self):
        self.removed.emit(self.path)


class PreviewTableDialog(QDialog):
    """Dialog to manage multiple preview files with drag-and-drop reordering."""
    def __init__(self, parent=None, paths: list = None):
        super().__init__(parent)
        self.setWindowTitle(_("Manage Full Previews"))
        self.resize(700, 400)
        self.paths = paths or []
        self._init_ui()
        self._load_paths()
        
        # Phase 32: Restore Size
        self.db = getattr(parent, 'db', None)
        if self.db:
            geom = self.db.get_setting("geom_preview_table", None)
            if geom: self.restoreGeometry(bytes.fromhex(geom))
    
    def closeEvent(self, event):
        if self.db:
            self.db.set_setting("geom_preview_table", self.saveGeometry().toHex().data().decode())
        super().closeEvent(event)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # Dark theme
        self.setStyleSheet("""
            QDialog { background-color: #2b2b2b; color: #e0e0e0; }
            QListWidget { background-color: #333333; color: #e0e0e0; border: 1px solid #444444; }
            QListWidget::item { padding: 2px; }
            QListWidget::item:selected { background-color: #3d5a80; }
            QPushButton { background-color: #3d3d3d; color: #e0e0e0; padding: 5px 10px; }
            QPushButton:hover { background-color: #5d5d5d; }
            QToolTip { background-color: #2d2d2d; color: #fff; border: 1px solid #555; padding: 4px; }
        """)
        
        # List Widget with Drag-Drop
        self.list_widget = QListWidget()
        self.list_widget.setDragEnabled(True)
        self.list_widget.setAcceptDrops(True)
        self.list_widget.setDropIndicatorShown(True)
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        # Sync paths after drag-drop
        self.list_widget.model().rowsMoved.connect(self._on_rows_moved)
        layout.addWidget(self.list_widget)
        
        # Toolbar
        btns = QHBoxLayout()
        add_btn = QPushButton(_("➕ Add File"))
        add_btn.clicked.connect(self._add_file)
        clear_btn = QPushButton(_("🗑 Clear All"))
        clear_btn.clicked.connect(self._clear_all)
        
        paste_btn = QPushButton(_("📋 Paste from Clipboard"))
        paste_btn.clicked.connect(self._add_from_clipboard)
        
        btns.addWidget(add_btn)
        btns.addWidget(paste_btn)
        btns.addWidget(clear_btn)
        btns.addStretch()
        
        ok_btn = QPushButton(_("OK"))
        ok_btn.clicked.connect(self.accept)
        btns.addWidget(ok_btn)
        
        layout.addLayout(btns)

    def _load_paths(self):
        self.list_widget.clear()
        for path in self.paths:
            self._add_item(path)

    def _add_item(self, path):
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 36))
        item.setData(Qt.ItemDataRole.UserRole, path)  # Store path in item data
        
        widget = PreviewItemWidget(path, self)
        widget.removed.connect(self._on_item_removed)
        
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, widget)

    def _on_item_removed(self, path):
        if path in self.paths:
            self.paths.remove(path)
        self._load_paths()

    def _on_rows_moved(self, parent, start, end, destination, row):
        """Sync self.paths after drag-drop reorder."""
        self._sync_paths_from_list()

    def _sync_paths_from_list(self):
        """Rebuild self.paths from current list order."""
        self.paths = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            path = item.data(Qt.ItemDataRole.UserRole)
            if path:
                self.paths.append(path)

    def _show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item: return
        
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #333333; color: #e0e0e0; } QMenu::item:selected { background-color: #3d5a80; }")
        
        move_top = menu.addAction(_("⬆ Move to Top"))
        move_bottom = menu.addAction(_("⬇ Move to Bottom"))
        menu.addSeparator()
        delete_action = menu.addAction(_("❌ Remove"))
        
        action = menu.exec(self.list_widget.mapToGlobal(pos))
        path = item.data(Qt.ItemDataRole.UserRole)
        
        if action == move_top:
            self._move_to_top(item)
        elif action == move_bottom:
            self._move_to_bottom(item)
        elif action == delete_action:
            if path in self.paths:
                self.paths.remove(path)
            self._load_paths()

    def _move_to_top(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path in self.paths:
            self.paths.remove(path)
            self.paths.insert(0, path)
        self._load_paths()
        self.list_widget.setCurrentRow(0)

    def _move_to_bottom(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path in self.paths:
            self.paths.remove(path)
            self.paths.append(path)
        self._load_paths()
        self.list_widget.setCurrentRow(self.list_widget.count() - 1)

    def _add_file(self):
        file, _ = QFileDialog.getOpenFileName(
            self, _("Select File"), "",
            _("All Files (*)")
        )
        if file:
            self.paths.append(file)
            self._add_item(file)

    def _clear_all(self):
        self.paths.clear()
        self.list_widget.clear()

    def _sync_to_icon(self, path):
        if self.parent() and hasattr(self.parent(), "_sync_icon_from_preview"):
            self.parent()._sync_icon_from_preview(path)

    def _crop_image(self, path):
        """Open the image in IconCropDialog for free cropping (arbitrary rectangles)."""
        if not os.path.exists(path):
            QMessageBox.warning(self, _("Error"), _("File not found."))
            return
        
        # Import IconCropDialog from dialogs_legacy to avoid circular import
        from src.ui.link_master.dialogs_legacy import IconCropDialog
        
        dialog = IconCropDialog(self, path, allow_free=True)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            cropped_pixmap = dialog.get_cropped_pixmap()
            if cropped_pixmap and not cropped_pixmap.isNull():
                crop_dir = os.path.join(os.environ.get('APPDATA', ''), 'LinkMaster', 'Cache', 'Cropped')
                os.makedirs(crop_dir, exist_ok=True)
                
                base_name = os.path.splitext(os.path.basename(path))[0]
                cropped_filename = f"{base_name}_cropped_{int(time.time())}.png"
                cropped_path = os.path.join(crop_dir, cropped_filename)
                
                if cropped_pixmap.save(cropped_path, "PNG"):
                    idx = self.paths.index(path) if path in self.paths else -1
                    if idx >= 0:
                        self.paths[idx] = cropped_path
                    self._load_paths()
                else:
                    QMessageBox.warning(self, _("Error"), _("Failed to save cropped image."))

    def get_paths(self):
        """Return paths in the current visual order."""
        self._sync_paths_from_list()
        return self.paths

    def _add_from_clipboard(self):
        """Add image data or file paths directly from clipboard."""
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QPixmap
        
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()
        
        if mime.hasImage():
            pixmap = QPixmap(clipboard.image())
            if not pixmap.isNull():
                # Save to temp
                crop_dir = os.path.join(os.environ.get('APPDATA', ''), 'LinkMaster', 'Cache', 'Clipboard')
                os.makedirs(crop_dir, exist_ok=True)
                
                filename = f"clipboard_{int(time.time())}.png"
                save_path = os.path.join(crop_dir, filename)
                
                if pixmap.save(save_path, "PNG"):
                    self.paths.append(save_path)
                    self._add_item(save_path)
                else:
                    QMessageBox.warning(self, _("Clip Error"), _("Failed to save image from clipboard."))
            return
            
        QMessageBox.information(self, _("Empty Clipboard"), _("No image or file found in clipboard."))


class FullPreviewDialog(QDialog):
    """Gallery-style dialog to display large previews of selected images."""
    def __init__(self, parent=None, paths: list = None, name: str = "Preview"):
        super().__init__(parent)
        self.setWindowTitle(_("Preview: {name}").format(name=name))
        self.resize(800, 600)
        self.paths = paths or []
        self.current_index = 0
        self._init_ui()
        self._update_display()
        
        # Phase 32: Restore Size
        self.db = getattr(parent, 'db', None)
        if self.db:
            geom = self.db.get_setting("geom_full_preview", None)
            if geom: self.restoreGeometry(bytes.fromhex(geom))

    def closeEvent(self, event):
        if self.db:
            self.db.set_setting("geom_full_preview", self.saveGeometry().toHex().data().decode())
        super().closeEvent(event)

    def _init_ui(self):
        self.setStyleSheet("QDialog { background-color: #2b2b2b; }")
        layout = QVBoxLayout(self)
        
        # Image Display Area
        self.image_label = QLabel(_("Loading..."))
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #1a1a1a; border-radius: 8px;")
        self.image_label.setMinimumSize(600, 400)
        layout.addWidget(self.image_label, 1)
        
        # Navigation Area
        nav_layout = QHBoxLayout()
        
        self.prev_btn = QPushButton(_("◀ Previous"))
        self.prev_btn.clicked.connect(self._prev_image)
        self.prev_btn.setStyleSheet("background-color: #444; color: white;")
        
        self.counter_label = QLabel("1 / 1")
        self.counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.counter_label.setStyleSheet("color: #888;")
        
        self.next_btn = QPushButton(_("Next ▶"))
        self.next_btn.clicked.connect(self._next_image)
        self.next_btn.setStyleSheet("background-color: #444; color: white;")
        
        # Phase 4 Enhancements
        self.crop_btn = QPushButton(_("🎨 Crop"))
        self.crop_btn.clicked.connect(self._crop_current)
        self.crop_btn.setStyleSheet("background-color: #444; color: white;")
        
        self.set_icon_btn = QPushButton(_("🖼 Set as Icon"))
        self.set_icon_btn.clicked.connect(self._set_as_icon_current)
        self.set_icon_btn.setStyleSheet("background-color: #444; color: white;")
        
        self.open_btn = QPushButton(_("🔗 Open File"))
        self.open_btn.clicked.connect(self._open_current)
        self.open_btn.setStyleSheet("background-color: #2980b9; color: white;")
        
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(self.counter_label)
        nav_layout.addWidget(self.next_btn)
        nav_layout.addStretch()
        nav_layout.addWidget(self.crop_btn)
        nav_layout.addWidget(self.set_icon_btn)
        nav_layout.addWidget(self.open_btn)
        
        layout.addLayout(nav_layout)

    def _update_display(self):
        if not self.paths:
            self.image_label.setText(_("No images available."))
            self.counter_label.setText("0 / 0")
            return
        
        path = self.paths[self.current_index]
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)
        else:
            self.image_label.setText(_("Cannot load: {path}").format(path=path))
        
        self.counter_label.setText(f"{self.current_index + 1} / {len(self.paths)}")
        self.prev_btn.setEnabled(self.current_index > 0)
        self.next_btn.setEnabled(self.current_index < len(self.paths) - 1)
        
        # Toggle Icon controls visibility based on extension
        is_image = path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'))
        self.crop_btn.setVisible(is_image)
        self.set_icon_btn.setVisible(is_image)

    def _crop_current(self):
        """Open cropping dialog for current image."""
        if not self.paths: return
        path = self.paths[self.current_index]
        # free_crop = True means any aspect ratio
        from src.ui.link_master.dialogs_legacy import IconCropDialog
        dlg = IconCropDialog(self, path, allow_free=True)
        if dlg.exec():
            # What to do with the cropped image? 
            # Prompt user to save as icon? Or just add to previews?
            # User requirement: "free-cropping feature for images within the full preview gallery"
            # Let's say it saves it as a new preview file.
            pixmap = dlg.get_cropped_pixmap()
            if pixmap:
                # Save to cache
                curr = self.parent()
                app_name = "Unknown"
                while curr:
                    if hasattr(curr, 'app_name'):
                        app_name = curr.app_name
                        break
                    curr = curr.parent()
                
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
                cache_dir = os.path.join(project_root, "src", "resource", "app", app_name, ".icon_cache")
                os.makedirs(cache_dir, exist_ok=True)
                
                save_path = os.path.join(cache_dir, f"crop_{int(time.time())}.png")
                pixmap.save(save_path, "PNG")
                
                # Add to paths and update
                self.paths.append(save_path)
                self.current_index = len(self.paths) - 1
                self._update_display()
                
                # If parent is PreviewTableDialog, update its table too
                if hasattr(self.parent(), '_add_row'):
                    self.parent()._add_row(save_path)

    def _set_as_icon_current(self):
        """Set the current image as folder icon via parent."""
        if not self.paths: return
        path = self.paths[self.current_index]
        
        # Traverse to FolderPropertiesDialog
        curr = self.parent()
        fprop_dlg = None
        while curr:
            if hasattr(curr, '_sync_icon_from_preview'):
                fprop_dlg = curr
                break
            curr = curr.parent()
        
        if fprop_dlg:
            fprop_dlg._sync_icon_from_preview(path)
            QMessageBox.information(self, _("Success"), _("Set as Icon."))
        else:
             QMessageBox.warning(self, _("Error"), _("Could not access properties dialog."))

    def _prev_image(self):
        if self.current_index > 0:
            self.current_index -= 1
            self._update_display()

    def _next_image(self):
        if self.current_index < len(self.paths) - 1:
            self.current_index += 1
            self._update_display()

    def _open_current(self):
        if self.paths and 0 <= self.current_index < len(self.paths):
            os.startfile(self.paths[self.current_index])
