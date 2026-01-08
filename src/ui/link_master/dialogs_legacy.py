""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を介すること。
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QHBoxLayout, QFileDialog, QComboBox, QFormLayout, 
                             QGroupBox, QCheckBox, QWidget, QListWidget, QListWidgetItem,
                             QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
                             QTextEdit, QApplication, QMessageBox, QMenu, QSpinBox, QStyle,
                             QRadioButton, QButtonGroup, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QRect, QPoint, QRectF, QTimer
from PyQt6.QtGui import QMouseEvent, QAction, QIcon, QPainter, QPen, QColor, QPixmap, QPainterPath
from src.ui.flow_layout import FlowLayout
from src.ui.link_master.dialogs.library_usage_dialog import LibraryUsageDialog
from src.ui.toast import Toast
from src.ui.link_master.compact_dial import CompactDial
from src.core.link_master.utils import format_size
from src.ui.slide_button import SlideButton
from src.core.lang_manager import _
from src.ui.window_mixins import OptionsMixin
from src.ui.common_widgets import StyledLineEdit, StyledComboBox, StyledSpinBox
import os
import subprocess
import shutil
from src.ui.link_master.dialogs.executables_manager import ExecutablesManagerDialog
from src.ui.link_master.dialogs.library_dialogs import LibraryDependencyDialog, LibraryRegistrationDialog
from src.ui.link_master.dialogs.url_list_dialog import URLItemWidget, URLListDialog
from src.ui.link_master.dialogs.preview_dialogs import PreviewItemWidget, PreviewTableDialog, FullPreviewDialog

class TagIconLineEdit(StyledLineEdit):
    """QLineEdit that accepts image drag and drop."""
    file_dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setPlaceholderText(_("Icon Path (Optional) - Drag image here"))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile().lower().endswith(('.png', '.jpg', '.jpeg', '.ico', '.svg', '.webp')):
                event.acceptProposedAction()
    
    def dropEvent(self, event):
        path = event.mimeData().urls()[0].toLocalFile()
        self.file_dropped.emit(path)


class ImageDropLabel(QLabel):
    """QLabel that accepts image drag and drop for preview."""
    image_dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: #222; border: 1px solid #444;")
        self.setText(_("Drop Image Here"))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile().lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp')):
                event.acceptProposedAction()
                self.setStyleSheet("background-color: #333; border: 2px solid #3498db;")
        elif event.mimeData().hasImage():
            event.acceptProposedAction()
            self.setStyleSheet("background-color: #333; border: 2px solid #3498db;")
    
    def dragLeaveEvent(self, event):
        self.setStyleSheet("background-color: #222; border: 1px solid #444;")
    
    def dropEvent(self, event):
        self.setStyleSheet("background-color: #222; border: 1px solid #444;")
        if event.mimeData().hasUrls():
            path = event.mimeData().urls()[0].toLocalFile()
            self.image_dropped.emit(path)
        elif event.mimeData().hasImage():
            # Handle direct image data from clipboard
            pixmap = QPixmap(event.mimeData().imageData())
            if not pixmap.isNull():
                self.setPixmap(pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                self.image_dropped.emit("")  # Empty path signals clipboard image


class AppRegistrationDialog(QDialog):
    def __init__(self, parent=None, app_data=None):
        super().__init__(parent)
        self.app_data = app_data
        self.pending_cover_pixmap = None  # For clipboard paste
        self.executables = []  # List of {name, path, args}
        
        mode = _("Edit") if app_data else _("Register New")
        self.setWindowTitle(_("{mode} Application").format(mode=mode))
        self.setMinimumSize(500, 550)
        self.setStyleSheet("""
            QDialog { background-color: #2b2b2b; color: #ffffff; }
            QLabel { color: #cccccc; }
            QPushButton {
                background-color: #444; color: #fff; border: none; padding: 6px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #555; }
        """)
        
        self._init_ui()
        if self.app_data:
            self._fill_data()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        # Name
        self.name_edit = StyledLineEdit()
        self.name_edit.setPlaceholderText(_("e.g. Minecraft"))
        form.addRow(_("App Name:"), self.name_edit)
        
        # Storage Root
        self.storage_edit = StyledLineEdit()
        self.storage_btn = QPushButton(_(" Browse "))
        self.storage_btn.clicked.connect(self._browse_storage)
        storage_layout = QHBoxLayout()
        storage_layout.addWidget(self.storage_edit)
        storage_layout.addWidget(self.storage_btn)
        form.addRow(_("Storage Path:"), storage_layout)
        
        # Helper to create target row with rule combo
        def create_target_row(label, edit_attr, btn_attr, rule_combo_attr, browse_slot, default_rule='folder'):
            layout = QHBoxLayout()
            edit = StyledLineEdit()
            setattr(self, edit_attr, edit)
            btn = QPushButton(_(" Browse "))
            setattr(self, btn_attr, btn)
            btn.clicked.connect(browse_slot)
            
            rule_combo = StyledComboBox()
            rule_combo.addItem(_("whole folder"), "folder")
            rule_combo.addItem(_("all files"), "files")
            rule_combo.addItem(_("tree"), "tree")
            setattr(self, rule_combo_attr, rule_combo)
            rule_combo.setFixedWidth(120)
            
            layout.addWidget(edit)
            layout.addWidget(btn)
            layout.addWidget(QLabel(_("Rule:")))
            layout.addWidget(rule_combo)
            form.addRow(label, layout)

        # Target A (Primary)
        create_target_row(_("Target A (Primary):"), "target_edit", "target_btn", "deploy_rule_combo", self._browse_target)
        
        # Target B (Optional)
        create_target_row(_("Target B (Optional):"), "target_edit_2", "target_btn_2", "deploy_rule_combo_b", self._browse_target_2)

        # Target C (Optional)
        create_target_row(_("Target C (Optional):"), "target_edit_3", "target_btn_3", "deploy_rule_combo_c", self._browse_target_3)

        # Default Folder Property Settings Group (Misc)
        defaults_group = QGroupBox(_("Other Default Settings"))
        defaults_group.setStyleSheet("QGroupBox { border: 1px solid #444; margin-top: 10px; padding-top: 10px; color: #aaa; }")
        defaults_form = QFormLayout()
        
        # Tree Skip (Redundant 'Default' removed from labels inside group)
        self.default_skip_levels_spin = StyledSpinBox()
        self.default_skip_levels_spin.setRange(0, 5)
        self.default_skip_levels_spin.setSuffix(_(" levels"))
        defaults_form.addRow(_("Tree Skip:"), self.default_skip_levels_spin)

        # Transfer Mode
        self.transfer_mode_combo = StyledComboBox()
        self.transfer_mode_combo.addItem(_("Symbolic Link"), "symlink")
        self.transfer_mode_combo.addItem(_("Physical Copy"), "copy")
        defaults_form.addRow(_("Transfer Mode:"), self.transfer_mode_combo)

        # Conflict Policy
        self.conflict_combo = StyledComboBox()
        self.conflict_combo.addItem(_("backup"), "backup")
        self.conflict_combo.addItem(_("skip"), "skip")
        self.conflict_combo.addItem(_("overwrite"), "overwrite")
        defaults_form.addRow(_("Conflict Policy:"), self.conflict_combo)

        # Style Settings
        self.cat_style_combo = StyledComboBox()
        self.cat_style_combo.addItem(_("image"), "image")
        self.cat_style_combo.addItem(_("text"), "text")
        self.cat_style_combo.addItem(_("image_text"), "image_text")
        defaults_form.addRow(_("Category Style:"), self.cat_style_combo)

        self.pkg_style_combo = StyledComboBox()
        self.pkg_style_combo.addItem(_("image"), "image")
        self.pkg_style_combo.addItem(_("text"), "text")
        self.pkg_style_combo.addItem(_("image_text"), "image_text")
        defaults_form.addRow(_("Package Style:"), self.pkg_style_combo)
        
        defaults_group.setLayout(defaults_form)
        form.addRow(defaults_group)

        
        # Cover Image with Edit Region support
        self.cover_edit = StyledLineEdit()
        self.cover_edit.setPlaceholderText(_("Optional: Select cover image for app"))
        self.cover_btn = QPushButton(_(" Browse "))
        self.cover_btn.clicked.connect(self._browse_cover)
        self.cover_crop_btn = QPushButton(_("✂ Edit Region"))
        self.cover_crop_btn.clicked.connect(self._crop_cover)
        self.cover_crop_btn.setToolTip(_("Select custom region from image"))
        cover_layout = QHBoxLayout()
        cover_layout.addWidget(self.cover_edit)
        cover_layout.addWidget(self.cover_btn)
        
        self.cover_paste_btn = QPushButton(_("📋 Paste"))
        self.cover_paste_btn.clicked.connect(self._paste_cover_from_clipboard)
        self.cover_paste_btn.setToolTip(_("Paste image from clipboard"))
        cover_layout.addWidget(self.cover_paste_btn)
        
        cover_layout.addWidget(self.cover_crop_btn)
        form.addRow(_("Cover Image:"), cover_layout)
        
        # Favorite System: ★ Toggle + Score
        fav_score_layout = QHBoxLayout()
        fav_score_layout.addStretch()
        
        self.favorite_btn = QPushButton(_("☆Favorite"))
        self.favorite_btn.setCheckable(True)
        self.favorite_btn.setFixedWidth(120)
        self.favorite_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.favorite_btn.setStyleSheet("""
            QPushButton { 
                background-color: transparent; color: #ccc; border: 1px solid #555; border-radius: 4px;
                text-align: center; padding: 4px 8px; min-width: 80px;
            }
            QPushButton:hover { background-color: #444; }
            QPushButton:checked { color: #f1c40f; font-weight: bold; border-color: #f1c40f; }
        """)
        self.favorite_btn.toggled.connect(lambda checked: self.favorite_btn.setText(_("★Favorite") if checked else _("☆Favorite")))
        fav_score_layout.addWidget(self.favorite_btn)
        
        fav_score_layout.addSpacing(15)
        score_label = QLabel(_("Score:"))
        fav_score_layout.addWidget(score_label)
        
        self.score_dial = CompactDial(self, digits=3, show_arrows=True)
        fav_score_layout.addWidget(self.score_dial)
        fav_score_layout.addStretch()
        form.addRow("", fav_score_layout)
        
        # App Preview Label with Image Drop support
        self.preview_label = ImageDropLabel(self)
        self.preview_label.setFixedSize(160, 120)
        self.preview_label.image_dropped.connect(self._on_preview_image_dropped)
        form.addRow(_("Preview:"), self.preview_label)

        # Executables Management (Phase 30)
        self.exe_btn = QPushButton(_("🚀 Manage Executables..."))
        self.exe_btn.clicked.connect(self._open_executables_manager)
        self.exe_btn.setStyleSheet("background-color: #d35400; color: white;")
        
        self.exe_count_label = QLabel("(0)")
        self.exe_count_label.setStyleSheet("color: #888;")
        
        exe_layout = QHBoxLayout()
        exe_layout.addWidget(self.exe_btn)
        exe_layout.addWidget(self.exe_count_label)
        exe_layout.addStretch()
        form.addRow(_("Executables:"), exe_layout)
        
        # URL Management (Phase 30)
        self.url_btn = QPushButton(_("🌐 Manage URLs..."))
        self.url_btn.clicked.connect(self._open_url_manager)
        self.url_btn.setStyleSheet("background-color: #2980b9; color: white;")
        
        self.url_count_label = QLabel("(0)")
        self.url_count_label.setStyleSheet("color: #888;")
        
        url_layout = QHBoxLayout()
        url_layout.addWidget(self.url_btn)
        url_layout.addWidget(self.url_count_label)
        url_layout.addStretch()
        form.addRow(_("URLs:"), url_layout)
        
        layout.addLayout(form)
        layout.addStretch()
        
        # Actions
        btn_layout = QHBoxLayout()
        
        # Unregister Button (Phase 32)
        if self.app_data:
            self.unregister_btn = QPushButton(_("Unregister App"))
            self.unregister_btn.clicked.connect(self._on_unregister_clicked)
            self.unregister_btn.setStyleSheet("background-color: #c0392b; color: white;")
            btn_layout.addWidget(self.unregister_btn)
            btn_layout.addSpacing(20)

        self.ok_btn = QPushButton(_("Save") if self.app_data else _("Register"))
        self.ok_btn.clicked.connect(self._on_save_clicked)
        self.ok_btn.setStyleSheet("background-color: #2980b9; font-weight: bold;")
        
        self.cancel_btn = QPushButton(_("Cancel"))
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(btn_layout)

    def _on_unregister_clicked(self):
        """Confirm and set flag for deletion."""
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(self, _("Confirm Unregister"),
                                   _("Are you sure you want to completely remove this application registration?\n"
                                     "This will NOT delete physical folders, but will delete all custom names, tags, and settings."),
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.is_unregister_request = True
            self.accept()

    def _fill_data(self):
        if not self.app_data: return
        self.name_edit.setText(self.app_data.get('name', ''))
        self.storage_edit.setText(self.app_data.get('storage_root', ''))
        self.target_edit.setText(self.app_data.get('target_root', ''))
        self.target_edit_2.setText(self.app_data.get('target_root_2', ''))
        self.target_edit_3.setText(self.app_data.get('target_root_3', ''))
        self.conflict_combo.setCurrentText(self.app_data.get('conflict_policy', 'backup'))
        
        # New Rule-based fields (with fallback to legacy types)
        def set_combo_rule(combo, key, fallback_key=None):
            rule = self.app_data.get(key)
            if not rule and fallback_key:
                old_val = self.app_data.get(fallback_key, 'folder')
                rule = 'files' if old_val == 'flatten' else 'folder'
            if not rule: rule = 'folder'
            idx = combo.findData(rule)
            if idx >= 0: combo.setCurrentIndex(idx)

        set_combo_rule(self.deploy_rule_combo, 'deployment_rule', 'deployment_type')
        set_combo_rule(self.deploy_rule_combo_b, 'deployment_rule_b')
        set_combo_rule(self.deploy_rule_combo_c, 'deployment_rule_c')
        
        t_mode = self.app_data.get('transfer_mode', 'symlink')
        idx = self.transfer_mode_combo.findData(t_mode)
        if idx >= 0: self.transfer_mode_combo.setCurrentIndex(idx)
        self.cat_style_combo.setCurrentText(self.app_data.get('default_category_style', 'image'))
        self.pkg_style_combo.setCurrentText(self.app_data.get('default_package_style', 'image'))
        self.default_skip_levels_spin.setValue(int(self.app_data.get('default_skip_levels', 0) or 0))

        # Cover image
        if self.app_data.get('cover_image'):
            img_path = self.app_data.get('cover_image', '')
            self.cover_edit.setText(img_path)
            self._update_preview(img_path)
        
        # Executables
        import json
        exe_json = self.app_data.get('executables', '[]')
        try:
            self.executables = json.loads(exe_json) if exe_json else []
        except:
            self.executables = []
        self._update_exe_count()
        
        # URLs
        self.url_list_json = self.app_data.get('url_list', '[]') or '[]'
        self._update_url_count()
        
        # Favorite and Score
        is_fav = bool(self.app_data.get('is_favorite', 0))
        self.favorite_btn.setChecked(is_fav)
        self.favorite_btn.setText(_("★Favorite") if is_fav else _("☆Favorite"))
        self.score_dial.setValue(int(self.app_data.get('score', 0) or 0))

    def _update_exe_count(self):
        count = len(self.executables)
        self.exe_count_label.setText(f"({count})")

    def _update_url_count(self):
        import json
        try:
            ud = json.loads(self.url_list_json)
            urls = ud if isinstance(ud, list) else ud.get('urls', [])
            self.url_count_label.setText(f"({len(urls)})")
        except:
            self.url_count_label.setText("(0)")

    def _open_url_manager(self):
        dialog = URLListDialog(self, url_list_json=getattr(self, 'url_list_json', '[]'))
        if dialog.exec():
            self.url_list_json = dialog.get_data()
            self._update_url_count()

    def _browse_storage(self):
        path = QFileDialog.getExistingDirectory(self, _("Select Storage Root"))
        if path: self.storage_edit.setText(path)

    def _browse_target(self):
        path = QFileDialog.getExistingDirectory(self, _("Select Target Install Root A"))
        if path: self.target_edit.setText(path)
        
    def _browse_target_2(self):
        path = QFileDialog.getExistingDirectory(self, _("Select Target Install Root B"))
        if path: self.target_edit_2.setText(path)

    def _browse_target_3(self):
        path = QFileDialog.getExistingDirectory(self, _("Select Target Install Root C"))
        if path: self.target_edit_3.setText(path)
    
    def _browse_cover(self):
        path, _filter = QFileDialog.getOpenFileName(self, _("Select Cover Image"), "", 
                                               _("Images (*.png *.jpg *.jpeg *.bmp *.webp)"))
        if path: 
            self.cover_edit.setText(path)
            self._update_preview(path)
            
    def _update_preview(self, path):
        import os  # Local import to ensure availability
        if not path or not os.path.exists(path):
            self.preview_label.clear()
            self.preview_label.setText(_("No Image"))
            return
            
        from PyQt6.QtGui import QPixmap
        pix = QPixmap(path)
        if not pix.isNull():
            self.preview_label.setPixmap(pix.scaled(160, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.preview_label.setText("Invalid Image")

    def _on_preview_image_dropped(self, path):
        """Handle image dropped onto preview area."""
        import os  # Local import to ensure availability
        if path and os.path.exists(path):
            self.cover_edit.setText(path)
            self._update_preview(path)
        elif not path:
            # Empty path means clipboard image was used - already displayed by ImageDropLabel
            self.cover_edit.setText(_("[Dropped from Clipboard]"))

    def _crop_cover(self):
        """Open crop dialog for cover image region selection."""
        import os  # Local import to ensure availability
        source_path = self.cover_edit.text().strip()
        if not source_path or not os.path.exists(source_path):
            QMessageBox.warning(self, _("Error"), _("Please select a valid cover image first."))
            return
        
        try:
            # Load source image and use IconCropDialog (which works with QPixmap)
            from PyQt6.QtGui import QPixmap
            source_pixmap = QPixmap(source_path)
            if source_pixmap.isNull():
                QMessageBox.warning(self, _("Error"), _("Could not load the image file."))
                return
                
            dialog = IconCropDialog(self, source_pixmap)
            if dialog.exec():
                cropped_pixmap = dialog.get_cropped_pixmap()
                if cropped_pixmap and not cropped_pixmap.isNull():
                    # Save cropped image to temp file
                    import tempfile
                    temp_path = tempfile.mktemp(suffix=".png")
                    cropped_pixmap.save(temp_path)
                    self.cover_edit.setText(temp_path)
                    self._update_preview(temp_path)
        except Exception as e:
            QMessageBox.warning(self, _("Error"), _("Failed to crop image: {error}").format(error=e))

    def _paste_cover_from_clipboard(self):
        """Paste cover image from clipboard."""
        from PyQt6.QtGui import QGuiApplication, QPixmap
        clipboard = QGuiApplication.clipboard()
        mime_data = clipboard.mimeData()
        
        if mime_data.hasImage():
            image = clipboard.image()
            pixmap = QPixmap.fromImage(image)
            if not pixmap.isNull():
                self.pending_cover_pixmap = pixmap
                self.cover_edit.setText(" [ Clipboard Image ] ")
                self.preview_label.setPixmap(pixmap.scaled(160, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                self.preview_label.setText("")
                
                # Ask to crop immediately
                reply = QMessageBox.question(self, _("Crop Image?"), _("Do you want to crop the pasted image?"), 
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    self._crop_clipboard_cover()
        else:
            QMessageBox.warning(self, _("No Image"), _("No image found in clipboard."))

    def _crop_clipboard_cover(self):
        """Crop the pending clipboard image."""
        if not self.pending_cover_pixmap:
            return
        
        dialog = IconCropDialog(self, self.pending_cover_pixmap)
        if dialog.exec():
            pixmap = dialog.get_cropped_pixmap()
            if pixmap:
                self.pending_cover_pixmap = pixmap
                self.cover_edit.setText("[Cropped from Clipboard]")
                self.preview_label.setPixmap(pixmap.scaled(160, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                self.preview_label.setText("")

    def _open_executables_manager(self):
        """Open dialog to manage executables."""
        dialog = ExecutablesManagerDialog(self, self.executables)
        if dialog.exec():
            self.executables = dialog.get_executables()
            self._update_exe_count()


    def _on_save_clicked(self):
        """Validate and accept."""
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, _("Validation Error"), _("Application name is required."))
            return
        if not self.storage_edit.text().strip():
            QMessageBox.warning(self, _("Validation Error"), _("Storage path is required."))
            return
        if not self.target_edit.text().strip():
            QMessageBox.warning(self, _("Validation Error"), _("Primary target install path is required."))
            return
        self.accept()

    def get_data(self):
        import json
        import uuid
        import os  # Local import to ensure availability
        
        if getattr(self, 'is_unregister_request', False):
            return {'is_unregister': True}

        # Save clipboard image if pending
        cover_path = self.cover_edit.text()
        if self.pending_cover_pixmap and cover_path in [" [ Clipboard Image ] ", "[Cropped from Clipboard]"]:
            # Save to a temp location within Project Root / resource / app
            # From src/ui/link_master/ -> root is 3 levels up
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            save_dir = os.path.join(project_root, "resource", "app", "_covers")
            os.makedirs(save_dir, exist_ok=True)
            filename = f"cover_{uuid.uuid4().hex[:8]}.png"
            full_path = os.path.join(save_dir, filename)
            if self.pending_cover_pixmap.save(full_path, "PNG"):
                cover_path = full_path
        
        return {
            "name": self.name_edit.text(),
            "storage_root": self.storage_edit.text(),
            "target_root": self.target_edit.text(),
            "target_root_2": self.target_edit_2.text(),
            "target_root_3": self.target_edit_3.text(),
            "default_subpath": "",
            "managed_folder_name": "_LinkMaster_Assets",
            "conflict_policy": self.conflict_combo.currentText(),
            "deployment_rule": self.deploy_rule_combo.currentData(),
            "deployment_rule_b": self.deploy_rule_combo_b.currentData(),
            "deployment_rule_c": self.deploy_rule_combo_c.currentData(),
            "transfer_mode": self.transfer_mode_combo.currentData(),
            "deployment_type": self.deploy_rule_combo.currentData(), # Backward compat
            "cover_image": cover_path if cover_path and cover_path not in [" [ Clipboard Image ] ", "[Cropped from Clipboard]"] else None,
            "is_favorite": 1 if self.favorite_btn.isChecked() else 0,
            "score": self.score_dial.value(),
            "default_category_style": self.cat_style_combo.currentText(),
            "default_package_style": self.pkg_style_combo.currentText(),
            "default_skip_levels": self.default_skip_levels_spin.value(),
            "executables": json.dumps(self.executables) if self.executables else "[]",
            "url_list": getattr(self, "url_list_json", "[]")
        }

class FolderPropertiesDialog(QDialog, OptionsMixin):
    """Dialog to configure folder-specific display properties."""
    
    # Phase 35: Signal for non-modal save
    config_saved = pyqtSignal(dict)

    def __init__(self, parent=None, folder_path: str = "", current_config: dict = None, 
                 batch_mode: bool = False, app_name: str = None, storage_root: str = None,
                 thumbnail_manager = None, app_deploy_default: str = "folder", 
                 app_conflict_default: str = "backup",
                 app_cat_style_default: str = "image",
                 app_pkg_style_default: str = "image",
                 app_skip_levels_default: int = 0):

        super().__init__(parent)
        self.folder_path = folder_path
        self.current_config = current_config or {}
        self.batch_mode = batch_mode  # For multi-folder editing
        self.app_name = app_name
        self.registry = getattr(parent, 'registry', None)
        self.storage_root = storage_root
        self.thumbnail_manager = thumbnail_manager
        self.app_deploy_default = app_deploy_default
        self.app_conflict_default = app_conflict_default
        self.app_cat_style_default = app_cat_style_default
        self.app_pkg_style_default = app_pkg_style_default
        self.app_skip_levels_default = app_skip_levels_default
        
        # Fetch App Target Roots
        self.target_roots = []
        self.current_app_data = {}
        if self.registry and self.app_name:
            for app in self.registry.get_apps():
                if app['name'] == self.app_name:
                    self.current_app_data = app
                    self.target_roots = [
                        app.get('target_root'),
                        app.get('target_root_2'),
                        app.get('target_root_3')
                    ]
                    break
        
        # Phase X: Library Dependencies state
        self.lib_deps = self.current_config.get('lib_deps', '[]') or '[]'


        self.pending_icon_pixmap = None  # To be saved on Accept
        self.pending_icon_path = None    # To be saved on Accept
        
        # Context-Aware Logic: Detection of "Deep Item" (Package Area)
        self.is_package_area = False
        if not self.batch_mode and self.storage_root:
            try:
                rel = os.path.relpath(self.folder_path, self.storage_root).replace('\\', '/')
                # Level 1 (sep=0), Level 2 (sep=1) -> Category area. Level 3+ (sep>=2) -> Package area.
                sep_count = rel.count('/')
                if rel != "." and sep_count >= 2:
                    self.is_package_area = True
            except: pass


        # Sizing / Constraints to fix "narrowing" bug
        self.setMinimumWidth(480)
        self.setMinimumHeight(550)
        self.resize(500, 600)
        
        # Improved folder name detection
        self.original_name = os.path.basename(folder_path.rstrip('\\/'))
        if not self.original_name:
            self.original_name = folder_path
            
        title = _("Batch Edit Properties") if batch_mode else _("Properties: {name}").format(name=self.original_name)
        self.setWindowTitle(title)

        # Style to match Link Master overall dark theme
        self.setStyleSheet("""
            QDialog { background-color: #2b2b2b; color: #ffffff; }
            QLineEdit, QComboBox, QSpinBox { background-color: #2b2b2b; color: #fff; border: 1px solid #555; border-radius: 4px; padding: 2px; }
            QComboBox { background: #333; }
            QPushButton { background-color: #3b3b3b; color: #fff; border: 1px solid #555; border-radius: 4px; padding: 4px 12px; }
            QPushButton:hover { background-color: #4a4a4a; }
            QLabel { color: #cccccc; }
            QCheckBox { color: #cccccc; }
            QGroupBox { 
                color: #ddd; 
                border: 1px solid #555; 
                border-radius: 4px; 
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; }
            QToolTip { background-color: #2d2d2d; color: #fff; border: 1px solid #555; padding: 4px; }
        """)
        
        # Auto-fill image_path from auto-detected thumbnail if empty (Phase 18.13)
        if not self.batch_mode and self.folder_path and not self.current_config.get('image_path'):
            auto_thumb = self._detect_auto_thumbnail()
            if auto_thumb:
                self.current_config['image_path'] = auto_thumb
        
        self.db = getattr(parent, 'db', None)
        self._init_ui()
        
        # Phase 32: Restore Size
        self.load_options("folder_properties")
    
    def closeEvent(self, event):
        """Save window geometry on close."""
        self.save_options("folder_properties")
        super().closeEvent(event)
        
    def done(self, r):
        """Overridden to ensure options are saved via accept/reject too."""
        self.save_options("folder_properties")
        super().done(r)
    
    def _detect_auto_thumbnail(self):
        """Detect first available image in folder for auto-thumbnail."""
        if not self.folder_path or not os.path.isdir(self.folder_path):
            return None
        
        image_exts = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')
        preview_names = ('preview', 'cover', 'thumb', 'icon', 'thumbnail')
        
        try:
            files = []
            for f in os.listdir(self.folder_path):
                if f.lower().endswith(image_exts):
                    files.append(f)
            
            if not files:
                return None
            
            # Prioritize files with preview-like names
            for f in files:
                name_lower = os.path.splitext(f)[0].lower()
                for pn in preview_names:
                    if pn in name_lower:
                        return os.path.join(self.folder_path, f)
            
            # Fallback to first image
            return os.path.join(self.folder_path, files[0])
        except:
            return None
        
    def _init_ui(self):
        # Phase 33: Split Layout (Left=Basic, Right=Advanced)
        self.root_layout = QVBoxLayout(self)
        
        content_split = QHBoxLayout()
        self.root_layout.addLayout(content_split)
        
        # Left Column (Reuse 'layout' variable name to minimize diffs for existing groups)
        layout = QVBoxLayout() 
        content_split.addLayout(layout, 55) # 55% width
        
        # Right Column
        right_layout = QVBoxLayout()
        content_split.addLayout(right_layout, 45) # 45% width
        
        # ===== Batch Mode Notice (New) =====
        if self.batch_mode:
            batch_notice = QLabel(_("💡 <b>If left empty, existing settings for each folder will be maintained.</b>"))
            batch_notice.setStyleSheet("color: #3498db; background-color: #1a2a3a; padding: 10px; border-radius: 4px; border: 1px solid #3498db;")
            batch_notice.setWordWrap(True)
            layout.addWidget(batch_notice)

        # ===== Display Settings Group =====
        display_group = QGroupBox(_("Display Settings"))
        display_group.setStyleSheet("""
            QGroupBox { color: #ddd; border: 1px solid #555; border-radius: 4px; margin-top: 10px; padding-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; }
            QPushButton { 
                background-color: #444; color: #fff; border: 1px solid #555; padding: 4px 8px; border-radius: 4px; 
                min-width: 60px;
            }
            QPushButton:hover { background-color: #555; border-color: #777; }
        """)
        display_form = QFormLayout(display_group)
        
        if not self.batch_mode:
            # Original Folder Name (Read-only) with folder open button
            folder_row = QHBoxLayout()
            folder_row.setContentsMargins(0, 0, 0, 0)
            folder_row.setSpacing(5)
            
            btn_open_folder = QPushButton()
            btn_open_folder.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
            btn_open_folder.setFixedSize(24, 24)
            btn_open_folder.setStyleSheet("border: 1px solid #555; border-radius: 3px; background-color: #444; min-width: 0px;") # Fix size override
            btn_open_folder.setToolTip(_("Open actual folder"))
            btn_open_folder.clicked.connect(self._open_actual_folder)
            folder_row.addWidget(btn_open_folder)
            
            orig_label = QLabel(self.original_name)
            orig_label.setStyleSheet("color: #888; font-style: italic;")
            folder_row.addWidget(orig_label)
            folder_row.addStretch()
            
            folder_widget = QWidget()
            folder_widget.setContentsMargins(0, 0, 0, 0)
            folder_widget.setLayout(folder_row)
            display_form.addRow(_("Folder Name:"), folder_widget)

            # Package Size Display (New)
            size_val = self.current_config.get('size_bytes', 0)
            scanned_at = self.current_config.get('scanned_at')
            size_text = format_size(size_val)
            if scanned_at:
                size_text += _(" (Scanned: {date})").format(date=scanned_at[:16].replace('T', ' '))
            
            size_label = QLabel(size_text)
            size_label.setStyleSheet("color: #aaa; font-size: 11px;")
            display_form.addRow(_("Package Size:"), size_label)
        
        # Display Name (Alias)
        self.name_edit = StyledLineEdit()
        self.name_edit.setPlaceholderText(_("Leave empty to use folder name"))
        
        # Phase 26: Batch mode display name controls
        self.batch_clear_name_toggle = None
        if self.batch_mode:
            name_row = QHBoxLayout()
            self.name_edit.setPlaceholderText(_("Enter name to apply to all"))
            self.name_edit.setEnabled(False)  # Disabled by default in batch mode
            name_row.addWidget(self.name_edit)
            
            clear_name_label = QLabel(_("Edit Name:"))
            clear_name_label.setStyleSheet("color: #aaa; font-size: 10px;")
            name_row.addWidget(clear_name_label)
            
            self.batch_clear_name_toggle = SlideButton()
            self.batch_clear_name_toggle.setChecked(False)
            self.batch_clear_name_toggle.toggled.connect(self._on_clear_name_toggle)
            name_row.addWidget(self.batch_clear_name_toggle)
            
            display_form.addRow(_("Display Name:"), name_row)
        else:
            self.name_edit.setText(self.current_config.get('display_name') or '')
            display_form.addRow(_("Display Name:"), self.name_edit)

        
        # Favorite System: ★ Toggle + Score (Phase 33: Left Aligned)
        fav_layout = QHBoxLayout()
        
        is_fav = self.current_config.get('is_favorite', False)
        self.favorite_btn = QPushButton(_("★Favorite") if is_fav else _("☆Favorite"), self)
        self.favorite_btn.setCheckable(True)
        self.favorite_btn.setChecked(is_fav)
        self.favorite_btn.setFixedWidth(120)
        self.favorite_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.favorite_btn.setStyleSheet("""
            QPushButton { 
                background-color: transparent; color: #ccc; border: 1px solid #555; border-radius: 4px; padding: 4px 8px; min-width: 80px;
                text-align: center;
            }
            QPushButton:hover { background-color: #444; }
            QPushButton:checked { color: #f1c40f; font-weight: bold; border-color: #f1c40f; }
        """)
        self.favorite_btn.toggled.connect(self._on_favorite_toggled_dialog)
        fav_layout.addWidget(self.favorite_btn)
        
        fav_layout.addSpacing(10)
        score_label = QLabel(_("Score:"))
        fav_layout.addWidget(score_label)
        self.score_dial = CompactDial(self, digits=3, show_arrows=True)
        self.score_dial.setValue(self.current_config.get('score', 0))  # Phase 26: Fix score loading bug
        fav_layout.addWidget(self.score_dial)
        
        # Phase 26: Batch mode score update toggle (default OFF to prevent unintended changes)
        self.batch_update_score_toggle = None
        if self.batch_mode:
            self.score_dial.setEnabled(False)  # Disabled by default in batch mode
            fav_layout.addSpacing(10)
            update_score_label = QLabel(_("Update Score:"))
            update_score_label.setStyleSheet("color: #aaa; font-size: 10px;")
            fav_layout.addWidget(update_score_label)
            self.batch_update_score_toggle = SlideButton()
            self.batch_update_score_toggle.setChecked(False)
            self.batch_update_score_toggle.toggled.connect(self._on_update_score_toggle)
            fav_layout.addWidget(self.batch_update_score_toggle)
        
        fav_layout.addStretch() # Align Left
        
        display_form.addRow("", fav_layout)
        
        # --- Multi-Preview Launcher (Phase 18) ---
        self.manage_previews_btn = QPushButton(_("📂 Manage Full Previews..."))
        self.manage_previews_btn.clicked.connect(self._open_multi_preview_browser)
        
        self.full_preview_edit = StyledLineEdit()
        self.full_preview_edit.setText(self.current_config.get('manual_preview_path', '') or '')
        display_form.addRow(_("Multi-Preview:"), self.manage_previews_btn)

        # Icon Path Widgets
        self.image_edit = StyledLineEdit()
        self.image_edit.setPlaceholderText(_("Path to icon image (200x200)"))
        self.image_edit.setText(self.current_config.get('image_path') or '')
        
        self.image_btn = QPushButton(_("Browse"))
        self.image_btn.clicked.connect(self._browse_image)
        
        self.crop_btn = QPushButton(_("✂ Edit Region"))
        self.crop_btn.clicked.connect(self._crop_image)
        
        self.paste_btn = QPushButton(_("📋 Paste"))
        self.paste_btn.clicked.connect(self._paste_from_clipboard)
        self.paste_btn.setToolTip(_("Paste image from clipboard"))
        
        self.clear_btn = QPushButton(_("Clear"))
        self.clear_btn.clicked.connect(self._clear_image)
        self.clear_btn.setStyleSheet("background-color: #8b0000; color: white; border: 1px solid #a00000; border-radius: 4px; padding: 4px 8px;")
        
        image_layout = QHBoxLayout()
        image_layout.addWidget(self.image_edit)
        image_layout.addWidget(self.image_btn)
        image_layout.addWidget(self.paste_btn)
        image_layout.addWidget(self.crop_btn)
        image_layout.addWidget(self.clear_btn)
        display_form.addRow(_("Icon Path (200x200):"), image_layout)

        self.preview_label = QLabel(_("No Image"))
        self.preview_label.setFixedSize(100, 100)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("background-color: #222; border: 1px solid #444; border-radius: 4px;")
        display_form.addRow(_("Effective Icon:"), self.preview_label)
        
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText(_("Folder description..."))
        self.description_edit.setText(self.current_config.get('description', '') or '')
        self.description_edit.setMaximumHeight(80)
        self.description_edit.setStyleSheet("""
            QTextEdit { 
                background-color: #3b3b3b; color: #ffffff; 
                border: 1px solid #555; padding: 4px; border-radius: 4px;
            }
        """)
        display_form.addRow(_("Description:"), self.description_edit)

        self.author_edit = StyledLineEdit()
        self.author_edit.setPlaceholderText(_("Author / Creator"))
        self.author_edit.setText(self.current_config.get('author', '') or '')
        display_form.addRow(_("Author:"), self.author_edit)

        # URL List Management (replaces single URL field)
        self.url_list = self.current_config.get('url_list', '[]') or '[]'  # JSON string
        # Migrate from old single 'url' field if exists
        old_url = self.current_config.get('url', '')
        if old_url and self.url_list == '[]':
            import json
            self.url_list = json.dumps([old_url])
        
        url_layout = QHBoxLayout()
        self.url_btn = QPushButton(_("🌐 Manage URLs..."))
        self.url_btn.clicked.connect(self._open_url_manager)
        self.url_btn.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold;")
        url_layout.addWidget(self.url_btn)
        
        # Hidden field to store structured JSON
        self.url_list_edit = StyledLineEdit()
        self.url_list_edit.setVisible(False)
        self.url_list_edit.setText(self.current_config.get('url_list') or '[]')
        
        # Count label
        self.url_count_label = QLabel()
        self._update_url_count()
        self.url_count_label.setStyleSheet("color: #888;")
        url_layout.addWidget(self.url_count_label)
        url_layout.addStretch()
        display_form.addRow(_("URLs:"), url_layout)
        
        # Phase 3.7: Button moved to Advanced section below to be near Deployment Rules

        layout.addWidget(display_group)
        
        # ===== Folder Attributes Group =====
        attr_group = QGroupBox(_("Folder Attributes"))
        attr_form = QFormLayout(attr_group)
        
        # Folder Type
        self.type_combo = StyledComboBox()
        if self.batch_mode:
            self.type_combo.addItem(_("--- No Change ---"), "KEEP")
            
        self.type_combo.addItem(_("Auto (Detect)"), "auto")
        self.type_combo.addItem(_("Category"), "category")
        self.type_combo.addItem(_("Package"), "package")
        
        # Default to Auto
        current_type = self.current_config.get('folder_type', 'auto')

        idx = self.type_combo.findData(current_type)
        if idx >= 0 and not self.batch_mode:
            self.type_combo.setCurrentIndex(idx)
        elif self.batch_mode:
            self.type_combo.setCurrentIndex(0) # No Change
            
        attr_form.addRow(_("Folder Type:"), self.type_combo)
        
        # Phase 19.x: Keep visible per user request to allow manual override
        # if self.is_package_area:
        #     self.type_combo.setVisible(False)
        #     attr_form.labelForField(self.type_combo).setVisible(False)

        
        # Display Style
        self.style_combo = StyledComboBox()
        if self.batch_mode:
            self.style_combo.addItem(_("--- No Change ---"), "KEEP")
            
        self.style_combo.addItem(_("App Default ({default})").format(default=self.app_cat_style_default), None)
        self.style_combo.addItem(_("Image Only"), "image")
        self.style_combo.addItem(_("Text Only"), "text")
        self.style_combo.addItem(_("Image + Text"), "image_text")
        
        current_style = self.current_config.get('display_style') # None = App Default

        idx = self.style_combo.findData(current_style)
        if idx >= 0 and not self.batch_mode:
            self.style_combo.setCurrentIndex(idx)
        elif self.batch_mode:
            self.style_combo.setCurrentIndex(0)

        attr_form.addRow(_("Category Style:"), self.style_combo)
        
        # Package Display Style (separate from category)
        self.style_combo_pkg = StyledComboBox()
        if self.batch_mode:
            self.style_combo_pkg.addItem(_("--- No Change ---"), "KEEP")
            
        self.style_combo_pkg.addItem(_("App Default ({default})").format(default=self.app_pkg_style_default), None)
        self.style_combo_pkg.addItem(_("Image Only"), "image")
        self.style_combo_pkg.addItem(_("Text Only"), "text")
        self.style_combo_pkg.addItem(_("Image + Text"), "image_text")
        
        current_style_pkg = self.current_config.get('display_style_package') # None = App Default

        idx_pkg = self.style_combo_pkg.findData(current_style_pkg)
        if idx_pkg >= 0 and not self.batch_mode:
            self.style_combo_pkg.setCurrentIndex(idx_pkg)
        elif self.batch_mode:
            self.style_combo_pkg.setCurrentIndex(0)

        attr_form.addRow(_("Package Style:"), self.style_combo_pkg)
        
        # Phase 19.x: Keep visible per user request
        # if self.is_package_area:
        #      self.style_combo.setVisible(False)
        #      attr_form.labelForField(self.style_combo).setVisible(False)
        #      self.style_combo_pkg.setVisible(False)
        #      attr_form.labelForField(self.style_combo_pkg).setVisible(False)

        
        # Terminal Flag Removed (Phase 12)
        
        # Phase 18.14: Hide Flag (is_visible)
        self.hide_checkbox = SlideButton()
        is_visible = self.current_config.get('is_visible', 1)
        self.hide_checkbox.setChecked(is_visible == 0)  # Checked = hidden
        attr_form.addRow(_("Hide from view:"), self.hide_checkbox)
        
        # Quick Tag Selector (Top Position - Phase 18 Swap)
        self.tag_panel = QWidget()
        self.tag_panel_layout = FlowLayout(self.tag_panel)
        self.tag_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.tag_panel_layout.setSpacing(5)
        
        self.tag_buttons = {} # name -> QPushButton
        
        try:
            # Find LinkMasterWindow to get frequent tags
            curr = self.parent()
            window = None
            while curr:
                if hasattr(curr, '_load_frequent_tags'):
                    window = curr
                    break
                curr = curr.parent()
            
            if window:
                frequent_tags = window._load_frequent_tags()
                for t in frequent_tags:
                    if t.get('is_sep'): continue
                    name = t.get('name')
                    mode = t.get('display_mode', 'text')
                    emoji = t.get('emoji', '')
                    
                    # 💡 RESPECT display_mode as requested by user
                    btn_text = ""
                    if mode == 'symbol' and emoji:
                        btn_text = emoji
                    elif mode == 'text_symbol' and emoji:
                        btn_text = f"{emoji} {name}"
                    elif mode == 'image':
                        btn_text = "" # Text hidden for image-only
                    elif mode == 'image_text':
                        btn_text = name # Icon + Text
                    else: # 'text' or fallback
                        btn_text = name
                        
                    btn = QPushButton(btn_text)
                    btn.setCheckable(True)
                    
                    # Add Icon if mode allows or as default
                    show_icon = (mode == 'image' or mode == 'image_text' or mode == 'text')
                    if show_icon and t.get('icon') and os.path.exists(t.get('icon')):
                         btn.setIcon(QIcon(t.get('icon')))
                    elif mode not in ['symbol', 'text_symbol'] and t.get('icon') and os.path.exists(t.get('icon')):
                         # Fallback for complex modes
                         btn.setIcon(QIcon(t.get('icon')))

                    current_tags = [p.strip().lower() for p in (self.current_config.get('tags', '') or '').split(',') if p.strip()]
                    if name.lower() in current_tags:
                        btn.setChecked(True)
                        btn.setStyleSheet("background-color: #2980b9; color: white; border: 1px solid #3498db; padding: 4px 8px;")
                    else:
                        btn.setStyleSheet("background-color: #444; color: #ccc; border: 1px solid #555; padding: 4px 8px;")
                        
                    # Use toggled signal for reliable checked state tracking
                    btn.toggled.connect(lambda checked, n=name: self._on_tag_toggled(n, checked))
                    self.tag_buttons[name.lower()] = btn
                    self.tag_panel_layout.addWidget(btn)

        except: pass
        
        attr_form.addRow(_("Quick Tags:"), self.tag_panel)

        # Tags (comma-separated) (Bottom Position) - Only MANUAL tags shown here
        # Quick Tags are stored in buttons and merged at save time
        self.tags_edit = StyledLineEdit()
        self.tags_edit.setPlaceholderText(_("Additional custom tags (e.g. my_custom, special)"))
        
        # Filter out quick tags from the text area on load
        all_tags_str = self.current_config.get('tags', '') or ''
        all_tags = [t.strip() for t in all_tags_str.split(',') if t.strip()]
        quick_tag_names = {t.lower() for t in self.tag_buttons.keys()}
        manual_only = [t for t in all_tags if t.lower() not in quick_tag_names]
        self.tags_edit.setText(", ".join(manual_only))
        
        attr_form.addRow(_("Additional Tags:"), self.tags_edit)
        
        # Inherit Tags Toggle (Phase 18.8)
        self.inherit_tags_chk = SlideButton()
        self.inherit_tags_chk.setChecked(bool(self.current_config.get('inherit_tags', 1)))
        self.inherit_tags_chk.setToolTip(_("If unchecked, tags from parent folders will NOT be applied to this item and its children."))
        attr_form.addRow(_("Inherit tags to subfolders:"), self.inherit_tags_chk)
        
        # No sync needed since Quick Tags are independent
        # self.tags_edit.textChanged.connect(self._sync_tag_buttons)

        layout.addWidget(attr_group)
        
        # Advanced Link Config (Merged into Folder Attributes or separate Group)
        adv_group = QGroupBox(_("Advanced Link Config"))
        adv_group.setStyleSheet("QGroupBox { font-weight: bold; color: #3498db; border: 1px solid #555; margin-top: 10px; padding-top: 10px; }")
        adv_form = QFormLayout(adv_group)

        # Phase 33 & Refinement: Target Override using Dropdown
        # Phase 33 & Refinement: Target Override using Dropdown
        # REPLACED QGroupBox with simple horizontal layout (No blue border)
        target_container = QWidget()
        target_layout = QHBoxLayout(target_container)
        target_layout.setContentsMargins(0, 0, 0, 0)
        target_layout.setSpacing(10)
        
        self.target_combo = StyledComboBox()
        self.target_combo.setMinimumWidth(200)
        
        if self.batch_mode:
            self.target_combo.addItem(_("--- No Change ---"), "KEEP")

        
        # 1. Inherit (App Default)
        last_target_key = self.current_app_data.get('last_target', 'target_root')
        root_map = {'target_root': 0, 'target_root_2': 1, 'target_root_3': 2}
        default_idx = root_map.get(last_target_key, 0)
        default_path = self.target_roots[default_idx] if len(self.target_roots) > default_idx else ""
        
        # Primary/Secondary/Tertiary Labels for Inheritance
        def_label = _("Primary") if default_idx == 0 else _("Secondary") if default_idx == 1 else _("Tertiary")
        self.target_combo.addItem(_("App Default (Inherit: {root})").format(root=def_label), 0)
        self.target_combo.setItemData(0, default_path, Qt.ItemDataRole.ToolTipRole)
        
        # 2. Roots (Primary, Secondary, Tertiary)
        labels = [_("Primary"), _("Secondary"), _("Tertiary")]
        for i, root_path in enumerate(self.target_roots):
            if root_path:
                self.target_combo.addItem(labels[i], i + 1)
                self.target_combo.setItemData(self.target_combo.count() - 1, root_path, Qt.ItemDataRole.ToolTipRole)
                
        # 3. Custom
        self.target_combo.addItem(_("Custom..."), 4)
        target_layout.addWidget(self.target_combo)
        
        # Manual Path Editor (Only visible if Custom is selected)
        self.manual_path_container = QWidget()
        manual_layout = QHBoxLayout(self.manual_path_container)
        manual_layout.setContentsMargins(0, 0, 0, 0)
        self.target_override_edit = StyledLineEdit()
        self.target_override_edit.setPlaceholderText(_("Override path..."))
        self.target_override_edit.setText(self.current_config.get('target_override') or '')
        self.target_override_btn = QPushButton(_("Browse"))
        self.target_override_btn.setFixedWidth(60)
        self.target_override_btn.clicked.connect(self._browse_target_override)
        manual_layout.addWidget(self.target_override_edit)
        manual_layout.addWidget(self.target_override_btn)
        target_layout.addWidget(self.manual_path_container)
        
        # Initial Selection Logic
        curr_override = self.current_config.get('target_override')
        if not curr_override:
            self.target_combo.setCurrentIndex(0)
        else:
            found = False
            for i, root_path in enumerate(self.target_roots):
                if root_path and os.path.normpath(curr_override) == os.path.normpath(root_path):
                    # Find index in combo with data == i+1
                    idx = self.target_combo.findData(i + 1)
                    if idx >= 0:
                        self.target_combo.setCurrentIndex(idx)
                        found = True
                        break
            if not found:
                idx = self.target_combo.findData(4)
                if idx >= 0:
                    self.target_combo.setCurrentIndex(idx)
        
        self.target_combo.currentIndexChanged.connect(self._on_target_choice_changed)
        self._on_target_choice_changed()
        
        adv_form.addRow(_("Target Destination:"), target_container)

        # Phase 2: Deploy/Conflict Overrides (Rule & Mode)
        self.deploy_rule_override_combo = StyledComboBox()
        if self.batch_mode:
            self.deploy_rule_override_combo.addItem(_("--- No Change ---"), "KEEP")
        
        # New Rule Options
        # Phase 36: Updated localized inheritance text
        self.deploy_rule_override_combo.addItem(_("Target Default (Inherit: 真上のターゲットに基く設定)"), "inherit")
        self.deploy_rule_override_combo.addItem(_("whole folder"), "folder")
        self.deploy_rule_override_combo.addItem(_("all files"), "files")
        self.deploy_rule_override_combo.addItem(_("tree"), "tree")
        self.deploy_rule_override_combo.addItem(_("Custom (Individual Settings)"), "custom")
        
        curr_rule = self.current_config.get('deploy_rule')
        if not curr_rule:
            # Fallback for old configs
            old_type = self.current_config.get('deploy_type')
            if old_type == 'flatten': curr_rule = 'files'
            elif old_type: curr_rule = old_type

        # Fix Phase 35: Use correct def_idx logic (index 0 is KEEP in batch mode)
        def_idx = 1 if self.batch_mode else 0
        if not curr_rule or curr_rule == 'inherit':
            # Phase 36: Simplified localized text for inheritance
            self.deploy_rule_override_combo.setItemText(def_idx, _("Target Default (Inherit: 真上のターゲットに基く設定)"))
            if not curr_rule: curr_rule = 'inherit'
        
        idx = self.deploy_rule_override_combo.findData(curr_rule)
        if idx >= 0 and not self.batch_mode:
            self.deploy_rule_override_combo.setCurrentIndex(idx)
        elif self.batch_mode:
            self.deploy_rule_override_combo.setCurrentIndex(0)
            
        # Help Button + Sticky Note (Phase 35) - Use text button "?" instead of emoji
        help_btn = QPushButton("?")
        help_btn.setFixedSize(24, 24)
        help_btn.setToolTip(_("Deployment Rule Help"))
        help_btn.setStyleSheet("""
            QPushButton { 
                background-color: transparent; border: 1px solid #555; color: #aaa; border-radius: 4px; font-weight: bold; 
            }
            QPushButton:hover { background-color: #444; color: #fff; border-color: #3498db; }
        """)
        
        rule_row = QHBoxLayout()
        rule_row.addWidget(self.deploy_rule_override_combo, 1)
        rule_row.addWidget(help_btn)
        adv_form.addRow(_("Deploy Rule:"), rule_row)

        # Help Note (The "Sticky Note")
        self.help_panel = QFrame()
        self.help_panel.setVisible(False)
        self.help_panel.setStyleSheet("""
            QFrame { 
                background-color: #2c3e50; border: 1px solid #3498db; border-radius: 6px; 
                margin: 5px 0px; padding: 8px;
            }
            QLabel { color: #ecf0f1; font-size: 11px; }
        """)
        help_layout = QVBoxLayout(self.help_panel)
        help_layout.setContentsMargins(5, 5, 5, 5)
        
        help_text = QLabel(
            _("<b>whole folder</b>: Keeps the folder structure as-is. Good for most mods.") + "<br><br>" +
            _("<b>all files</b>: Flattens the folder, placing all files directly into the target. Useful for 'resource pack' style folders.") + "<br><br>" +
            _("<b>tree</b>: Maintains partial structure starting from a specific depth. Advanced use only.") + "<br><br>" +
            _("<b>JSO (Joint Storage Organization)</b>: Advanced rule for shared storage structures. Controls how files are merged across targets.") + "<br><br>" +
            _("More detailed overrides (individual file redirections, excludes, etc.) can be managed via the <b>Edit Individual Redirections</b> button below.")
        )
        help_text.setWordWrap(True)
        help_layout.addWidget(help_text)
        adv_form.addRow("", self.help_panel)
        
        help_btn.clicked.connect(lambda: self.help_panel.setVisible(not self.help_panel.isVisible()))

        # Skip Levels for TREE mode (Moved below Deploy Rule)
        self.skip_levels_spin = StyledSpinBox()
        self.skip_levels_spin.setRange(0, 5)
        self.skip_levels_spin.setSuffix(_(" levels"))
        
        # Extract skip_levels from rules JSON if exists
        rules_json = self.current_config.get('deployment_rules', '') or ''
        try:
            import json
            current_rules = json.loads(rules_json) if rules_json else {}
            # Use rules value, or fallback to app default if it's a new config or specifically requested?
            # Actually, usually 0 is fine if not set.
            self.skip_levels_spin.setValue(int(current_rules.get('skip_levels', self.app_skip_levels_default)))
        except:
            self.skip_levels_spin.setValue(self.app_skip_levels_default)
            
        self.skip_levels_label = QLabel(_("Tree Skip Levels:"))
        adv_form.addRow(self.skip_levels_label, self.skip_levels_spin)
        
        # Visibility Logic
        self.deploy_rule_override_combo.currentIndexChanged.connect(self._update_tree_skip_visibility)
        QTimer.singleShot(0, self._update_tree_skip_visibility)

        # Transfer Mode Override
        self.transfer_mode_override_combo = StyledComboBox()
        if self.batch_mode:
            self.transfer_mode_override_combo.addItem(_("--- No Change ---"), "KEEP")
            
        app_default_mode = getattr(self, 'app_transfer_mode', 'symlink')
        self.transfer_mode_override_combo.addItem(_("App Default (Inherit)"), "inherit")
        self.transfer_mode_override_combo.addItem(_("Symbolic Link"), "symlink")
        self.transfer_mode_override_combo.addItem(_("Physical Copy"), "copy")
        
        curr_mode = self.current_config.get('transfer_mode')
        # Phase 34: Resolve Effective Mode for Display Label
        if not curr_mode or curr_mode == 'KEEP' or curr_mode == 'inherit':
            effective_mode = app_default_mode
            loc_mode = _("Symbolic Link") if effective_mode == 'symlink' else _("Physical Copy")
            # Item 1 is 'App Default' (index 0 is KEEP in batch, else Item 0 is App Default)
            def_idx = 1 if self.batch_mode else 0
            self.transfer_mode_override_combo.setItemText(def_idx, _("App Default (Inherit: {mode})").format(mode=loc_mode))
            if not curr_mode: curr_mode = 'inherit'

        idx = self.transfer_mode_override_combo.findData(curr_mode)
        if idx >= 0 and not self.batch_mode:
            self.transfer_mode_override_combo.setCurrentIndex(idx)
        elif self.batch_mode:
            self.transfer_mode_override_combo.setCurrentIndex(0)
        adv_form.addRow(_("Transfer Mode:"), self.transfer_mode_override_combo)

        # Tree Skip moved above

        self.conflict_override_combo = StyledComboBox()
        if self.batch_mode:
            self.conflict_override_combo.addItem(_("--- No Change ---"), "KEEP")
            
        self.conflict_override_combo.addItem(_("App Default (Inherit)"), "inherit")
        self.conflict_override_combo.addItem(_("backup"), "backup")
        self.conflict_override_combo.addItem(_("skip"), "skip")
        self.conflict_override_combo.addItem(_("overwrite"), "overwrite")
        
        curr_conflict = self.current_config.get('conflict_policy')
        # Phase 34: Resolve Effective Conflict Policy for Display Label
        if not curr_conflict or curr_conflict == 'KEEP' or curr_conflict == 'inherit':
            effective_conflict = self.app_conflict_default
            loc_policy = _(effective_conflict)
            def_idx = 1 if self.batch_mode else 0
            self.conflict_override_combo.setItemText(def_idx, _("App Default (Inherit: {policy})").format(policy=loc_policy))
            if not curr_conflict: curr_conflict = 'inherit'

        idx = self.conflict_override_combo.findData(curr_conflict)
        if idx >= 0 and not self.batch_mode:
            self.conflict_override_combo.setCurrentIndex(idx)
        elif self.batch_mode:
            self.conflict_override_combo.setCurrentIndex(0)
        adv_form.addRow(_("Conflict Policy:"), self.conflict_override_combo)

        # Deployment Rules (JSON) - Now BEFORE the redirections button
        self.rules_edit = QTextEdit()
        self.rules_edit.setPlaceholderText('{"exclude": ["*.txt", "docs/"], "rename": {"old.dll": "new.dll"}}')
        self.rules_edit.setMinimumHeight(80)
        self.rules_edit.setText(self.current_config.get('deployment_rules', '') or '')
        # Match QLineEdit style
        self.rules_edit.setStyleSheet("""
            QTextEdit { 
                background-color: #3b3b3b; color: #ffffff; 
                border: 1px solid #555; padding: 4px; border-radius: 4px;
            }
        """)
        adv_form.addRow(_("Deployment Rules (JSON):"), self.rules_edit)

        # Phase 3.7: Shortcut to File Management (Now AFTER Rules) - Full width
        if not self.batch_mode:
            self.manage_redirection_btn = QPushButton(_("Edit Individual Redirections..."))
            self.manage_redirection_btn.setStyleSheet("""
                QPushButton { background-color: #3b3b3b; color: #fff; border: 1px solid #555; border-radius: 4px; padding: 4px 10px; }
                QPushButton:hover { background-color: #4a4a4a; border-color: #777; }
                QPushButton:pressed { background-color: #222; padding-top: 5px; padding-left: 11px; }
            """)
            self.manage_redirection_btn.clicked.connect(self._open_file_management_shortcut)
            adv_form.addRow("", self.manage_redirection_btn)  # Empty label for full width
            
        # Phase 28/26: Conflict Tag Detection (Available in batch mode)
        conflict_tag_layout = QHBoxLayout()
        
        # Tag input field
        self.conflict_tag_edit = StyledLineEdit()
        self.conflict_tag_edit.setPlaceholderText(_("Tag to search..."))
        if self.batch_mode:
            self.conflict_tag_edit.setPlaceholderText(_("Leave empty to keep existing"))
        self.conflict_tag_edit.setText(self.current_config.get('conflict_tag', '') or '')
        conflict_tag_layout.addWidget(self.conflict_tag_edit, 2)  # stretch=2
        
        # Dropdown for scope selection
        self.conflict_scope_combo = StyledComboBox()
        if self.batch_mode:
            self.conflict_scope_combo.addItem(_("--- No Change ---"), "KEEP")
        self.conflict_scope_combo.addItem(_("Disabled"), "disabled")
        self.conflict_scope_combo.addItem(_("Category"), "category")
        self.conflict_scope_combo.addItem(_("Global"), "global")
        # Load initial scope value
        current_scope = self.current_config.get('conflict_scope', 'disabled')
        if self.batch_mode:
            self.conflict_scope_combo.setCurrentIndex(0)
        else:
            scope_idx = self.conflict_scope_combo.findData(current_scope)
            if scope_idx >= 0:
                self.conflict_scope_combo.setCurrentIndex(scope_idx)
        conflict_tag_layout.addWidget(self.conflict_scope_combo, 1)  # stretch=1
        
        adv_form.addRow(_("Conflict Tag:"), conflict_tag_layout)
        
        # Phase X/26: Library Usage Row (Available in batch mode)
        lib_row = QHBoxLayout()
        
        self.btn_lib_usage = QPushButton(_("📚 Library Settings"))
        self.btn_lib_usage.setFixedWidth(150)
        self.btn_lib_usage.setStyleSheet("""
            QPushButton { background-color: #2980b9; color: #fff; border: 1px solid #3498db; border-radius: 4px; padding: 4px 10px; }
            QPushButton:hover { background-color: #3498db; }
            QPushButton:pressed { background-color: #1a5276; }
        """)
        self.btn_lib_usage.clicked.connect(self._open_library_usage)
        lib_row.addWidget(self.btn_lib_usage)
        
        # Show configured libraries
        self.lib_display = QLabel()
        self.lib_display.setStyleSheet("color: #88c; font-style: italic; padding: 4px;")
        if self.batch_mode:
            self.lib_display.setText(_("(Batch: Overwrites All If Changed)"))
        else:
            self._update_lib_display()
        lib_row.addWidget(self.lib_display, 1)
        
        adv_form.addRow(_("Libraries:"), lib_row)

        
        right_layout.addWidget(adv_group)
        right_layout.addStretch() # Push Up
        
        # Phase 33: Ensure Left Column Stretches appropriately
        layout.addStretch()
        
        # Update preview if image exists, or try managed thumbnail, or first preview
        if self.current_config.get('image_path'):
            self._update_preview(self.current_config.get('image_path'))
        else:
            # Try managed thumbnail first
            self._try_load_managed_thumbnail()
            
            # If still no preview and manual_preview_path exists, auto-load first preview as icon
            if self.preview_label.text() in ["No Image", "No Cache", "Error", "No Preview"]:
                preview_paths = self.current_config.get('manual_preview_path', '') or ''
                first_preview = [p.strip() for p in preview_paths.split(';') if p.strip()]
                if first_preview and os.path.exists(first_preview[0]):
                    self.image_edit.setText(first_preview[0])
                    self._update_preview(first_preview[0])
            
        # Phase 35: Set non-modal to allow concurrent FM operation
        self.setModal(False)
        
        # Actions - Add to Root Layout (Phase 36: Restored missing buttons)
        btn_layout = QHBoxLayout()
        # Phase 28: Use Alt+Enter for save to prevent accidental submissions
        from PyQt6.QtGui import QKeySequence, QShortcut
        self.save_shortcut = QShortcut(QKeySequence("Alt+Return"), self)
        self.save_shortcut.activated.connect(self.accept)
        self.save_shortcut_win = QShortcut(QKeySequence("Alt+Enter"), self) # Support numpad
        self.save_shortcut_win.activated.connect(self.accept)

        self.ok_btn = QPushButton(_("変更を反映して閉じる (Alt+Enter)"))
        self.ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ok_btn.setStyleSheet("""
            QPushButton { 
                background-color: #2980b9; color: white; font-weight: bold; 
                border-radius: 4px; padding: 8px 16px; 
            }
            QPushButton:hover { background-color: #3498db; }
        """)
        self.ok_btn.clicked.connect(self.accept)
        
        self.cancel_btn = QPushButton(_("キャンセル"))
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setStyleSheet("""
            QPushButton { 
                background-color: #444; color: white; 
                border: 1px solid #555; border-radius: 4px; padding: 8px 16px; 
            }
            QPushButton:hover { background-color: #555; border-color: #777; }
        """)
        self.cancel_btn.clicked.connect(self.reject)

        
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.ok_btn)
        
        self.root_layout.addLayout(btn_layout)

    def accept(self):
        """Override accept to emit signal for non-modal use."""
        data = self.get_data()
        self.config_saved.emit(data)
        super().accept()
    
    def _open_actual_folder(self):
        """Open the folder in Explorer."""
        if self.folder_path and os.path.isdir(self.folder_path):
            os.startfile(os.path.normpath(self.folder_path))
    
    def _open_multi_preview_browser(self):
        """Open the table-based preview manager."""
        paths_str = self.full_preview_edit.text()
        paths = [p.strip() for p in paths_str.split(';') if p.strip()]
        
        dlg = PreviewTableDialog(self, paths=paths)
        if dlg.exec():
            # Update the hidden field
            final_paths = dlg.get_paths()
            self.full_preview_edit.setText("; ".join(final_paths))

    def _sync_icon_from_preview(self, path):
        """Called from PreviewTableDialog to set a path as the folder icon."""
        import os
        if path and os.path.exists(path):
            self.pending_icon_path = path
            self.image_edit.setText(path)
            self._update_preview(path)

    def _browse_image(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _filter = QFileDialog.getOpenFileName(self, _("Select Icon Image"), "", _("Images (*.png *.jpg *.jpeg *.gif *.webp)"))
        if path:
            self.pending_icon_path = path
            self.pending_icon_pixmap = None # Clear crop if any
            self.image_edit.setText(path)
            self._update_preview(path)

    def _paste_from_clipboard(self):
        """Get image from clipboard and stage it for saving."""
        from PyQt6.QtGui import QGuiApplication
        clipboard = QGuiApplication.clipboard()
        mime_data = clipboard.mimeData()
        
        if mime_data.hasImage():
            image = clipboard.image()
            pixmap = QPixmap.fromImage(image)
            if not pixmap.isNull():
                self.pending_icon_pixmap = pixmap
                self.pending_icon_path = "CLIPBOARD" # Sentinel
                
                # Update UI immediately
                self.image_edit.setText(" [ Clipboard Image ] ")
                self.preview_label.setPixmap(pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                self.preview_label.setText("")
                
                # Phase 28: Ask to crop immediately
                reply = QMessageBox.question(self, _("Crop Image?"), _("Do you want to crop the pasted image?"), 
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    self._crop_image()
        else:
            QMessageBox.warning(self, _("No Image"), _("No image found in clipboard."))

    def _get_thumbnail_root(self):
        """Get the app-specific thumbnail storage path."""
        # Check if thumbnail_manager can give us the base path
        if self.thumbnail_manager and hasattr(self.thumbnail_manager, 'resource_root'):
            base = self.thumbnail_manager.resource_root
        else:
            root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))) # src/ folder root
            base = os.path.join(root, "resource", "app")
            
        app_name = self.app_name or "default"
        thumb_dir = os.path.join(base, app_name, "thumbnail")
        os.makedirs(thumb_dir, exist_ok=True)
        return thumb_dir

    def get_data(self):
        """Gather all data from UI widgets into a directory for the database."""
        manual_tags = [t.strip() for t in self.tags_edit.text().split(',') if t.strip()]
        quick_tags = [n for n, btn in self.tag_buttons.items() if btn.isChecked()]
        all_tags = sorted(list(set(manual_tags + quick_tags)))

        data = {
            "display_name": self.name_edit.text(),
            "score": self.score_dial.value(),
            "image_path": self.image_edit.text() if self.image_edit.text() != " [ Clipboard Image ] " else self.pending_icon_path,
            "description": self.description_edit.toPlainText(),
            "author": self.author_edit.text(),
            "url_list": self.url_list_edit.text(),
            "folder_type": self.type_combo.currentData(),
            "display_style": self.style_combo.currentData(),
            "display_style_package": self.style_combo_pkg.currentData(),
            "is_visible": 0 if self.hide_checkbox.isChecked() else 1,
            "inherit_tags": 1 if self.inherit_tags_chk.isChecked() else 0,
            "conflict_tag": self.conflict_tag_edit.text(),
            "conflict_scope": self.conflict_scope_combo.currentData(),
            "transfer_mode": self.transfer_mode_override_combo.currentData(),
            "conflict_policy": self.conflict_override_combo.currentData(),
            "tags": ", ".join(all_tags)
        }

        # Target Override calculation
        t_data = self.target_combo.currentData()
        if t_data == "KEEP":
            pass # Handle KEEP logic if batch (caller should handle based on data being present)
        elif t_data == 0: # App Default
            data["target_override"] = None
        elif t_data == 4: # Custom
            data["target_override"] = self.target_override_edit.text()
        else: # Roots 1, 2, 3
            idx = t_data - 1
            if idx < len(self.target_roots):
                data["target_override"] = self.target_roots[idx]
        
        # Deploy Rule + Skip Levels
        data["deploy_rule"] = self.deploy_rule_override_combo.currentData()
        
        # Deployment Rules JSON
        import json
        rules_text = self.rules_edit.toPlainText() or '{}'
        try:
            current_rules = json.loads(rules_text)
        except:
            current_rules = {}
        current_rules['skip_levels'] = self.skip_levels_spin.value()
        data["deployment_rules"] = json.dumps(current_rules)

        return data

    def accept(self):
        """Override accept to save clipboard image and Stage/Finalize icon path."""
        import uuid
        if self.pending_icon_pixmap and self.pending_icon_path == "CLIPBOARD":
            save_dir = self._get_thumbnail_root()
            filename = f"thumb_{uuid.uuid4().hex[:8]}.png"
            full_path = os.path.abspath(os.path.join(save_dir, filename))
            
            if self.pending_icon_pixmap.save(full_path, "PNG"):
                self.pending_icon_path = full_path
                self.image_edit.setText(full_path)
            else:
                QMessageBox.warning(self, _("Error"), _("Failed to save clipboard image."))
                return

        super().accept()
        # Phase 29: Toast Notification on Success
        Toast(self.parent(), _("Settings Saved Successfully")).show_message()

    def reject(self):
        super().reject()
        # Phase 29: Toast Notification on Cancel (Yellowish/Warning)
        Toast(self.parent(), _("Changes Cancelled"), preset='warning').show_message()

    def keyPressEvent(self, event):
        """Phase 28: Handle global hotkeys for the dialog."""
        from PyQt6.QtCore import Qt
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.AltModifier:
                self.accept()
                return
            # Ignore plain Enter to prevent accidental submission from QLineEdit
            return
        super().keyPressEvent(event)

    def _browse_preview_file(self):
        from PyQt6.QtWidgets import QFileDialog
        paths, _filter = QFileDialog.getOpenFileNames(self, _("Select Preview Files"), "", _("All Files (*.*)"))
        if paths:
            existing = [p.strip() for p in self.full_preview_edit.text().split(';') if p.strip()]
            new_list = sorted(list(set(existing + paths)))
            self.full_preview_edit.setText("; ".join(new_list))

    def _clear_image(self):
        from PyQt6.QtGui import QPixmap
        self.image_edit.setText("")
        self.pending_icon_path = None
        self.pending_icon_pixmap = None
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText(_("No Image"))

    def _open_file_management_shortcut(self):
        """Shortcut to open FileManagementDialog from Properties."""
        # We need to reach the LinkMasterWindow instance to call _open_file_management
        curr = self.parent()
        window = None
        while curr:
            if hasattr(curr, '_open_file_management'):
                window = curr
                break
            curr = curr.parent()
        
        if window and self.storage_root:
            try:
                rel = os.path.relpath(self.folder_path, self.storage_root).replace('\\', '/')
                if rel == ".": rel = ""
                # Close this dialog and open file management? 
                # Better: Open management, and if it changes anything, we might need a refresh.
                window._open_file_management(rel)
                
                # Refresh rules in the current dialog's edit box
                config = window.db.get_folder_config(rel) or {}
                new_rules = config.get('deployment_rules', '')
                self.rules_edit.setText(new_rules)
            except Exception as e:
                print(f"Failed to open file management from properties: {e}")
    
    def _update_lib_display(self):
        """Update the library display label with configured libraries."""
        import json
        try:
            lib_deps = json.loads(self.lib_deps) if self.lib_deps else []
        except:
            lib_deps = []
        
        if not lib_deps:
            self.lib_display.setText(_("(None)"))
            return
        
        names = []
        for dep in lib_deps:
            if isinstance(dep, dict):
                name = dep.get('name', 'Unknown')
                ver = dep.get('version')
                if ver:
                    names.append(f"{name}@{ver}")
                else:
                    names.append(name)
            elif isinstance(dep, str):
                names.append(dep)
        
        self.lib_display.setText(", ".join(names) if names else _("(None)"))
    
    def _open_library_usage(self):
        """Open dialog to manage library dependencies for this package."""
        dialog = LibraryDependencyDialog(self, self.lib_deps)
        if dialog.exec():
            self.lib_deps = dialog.get_lib_deps_json()
            self._update_lib_display()

    def _update_tree_skip_visibility(self):
        """Show/Hide Tree Skip Levels based on Deploy Rule."""
        rule = self.deploy_rule_override_combo.currentData()
        is_tree = rule == "tree"
        self.skip_levels_spin.setVisible(is_tree)
        self.skip_levels_label.setVisible(is_tree)
        if is_tree:
            # Load app default every time it becomes visible
            self.skip_levels_spin.setValue(self.app_skip_levels_default)

    def _browse_target_override(self):
        """Browse for a custom target destination path."""
        from PyQt6.QtWidgets import QFileDialog
        path = QFileDialog.getExistingDirectory(self, _("Select Target Destination Override"))
        if path:
            self.target_override_edit.setText(os.path.normpath(path))

        if path:
            self.target_override_edit.setText(os.path.normpath(path))

    def _on_target_choice_changed(self, *args):
        choice = self.target_combo.currentData()
        self.manual_path_container.setVisible(choice == 4)
        
        # Phase 36: If Custom is chosen and current text is empty, pre-fill with primary target
        if choice == 4 and not self.target_override_edit.text():
            primary_root = self.target_roots[0] if self.target_roots else None
            if primary_root:
                self.target_override_edit.setText(primary_root)

    def _get_selected_target_path(self):
        choice = self.target_combo.currentData()
        if choice == "KEEP": # Phase 26: No Change
            return "KEEP"
        if choice == 0: # Inherit
            return None
        if choice >= 1 and choice <= 3: # Roots
            idx = choice - 1
            return self.target_roots[idx] if len(self.target_roots) > idx else None
        if choice == 4: # Manual
            return self.target_override_edit.text().strip() or None
        return None

    def _crop_image(self):
        """Open specialized cropper for the current image, thumbnail, or a new one."""
        from PyQt6.QtWidgets import QFileDialog
        from PyQt6.QtCore import Qt
        
        # Priority: 1. Pending icon pixmap (from clipboard), 2. Current icon path, 3. Pending crop source, 4. Managed thumbnail, 5. Preview, 6. Prompt
        source = self.image_edit.text()
        
        if source == " [ Clipboard Image ] " and self.pending_icon_pixmap:
            dialog = IconCropDialog(self, self.pending_icon_pixmap)
            if dialog.exec():
                pixmap = dialog.get_cropped_pixmap()
                if pixmap:
                    self.pending_icon_pixmap = pixmap
                    self.image_edit.setText("[Cropped from Clipboard]")
                    self.preview_label.setPixmap(pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                    self.preview_label.setText("")
            return

        if source in ["[Cropped Selection]", "[Cropped from Preview]", "[Cropped from Clipboard]"]:
            # If it's a pending crop, use the original source if available
            source = self.pending_icon_path
        
        if not source or not os.path.exists(source):
            # Try managed thumbnail (the effective icon shown in preview)
            source = self.managed_thumb_edit.text() if hasattr(self, 'managed_thumb_edit') else ""
        
        if not source or not os.path.exists(source) or os.path.isdir(source):
            path, _filter = QFileDialog.getOpenFileName(self, _("Select Image to Crop"), "", _("Images (*.png *.jpg *.jpeg *.webp)"))
            if not path: return
            source = path
            
        dialog = IconCropDialog(self, source)
        if dialog.exec():
            pixmap = dialog.get_cropped_pixmap()
            if pixmap:
                self.pending_icon_pixmap = pixmap
                self.pending_icon_path = source # Store original source for hashing
                self.image_edit.setText("[Cropped Selection]")
                # Scale preview to match label at 100x100 (1:1)
                self.preview_label.setPixmap(pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                self.preview_label.setText("")

    def _crop_preview_to_icon(self):
        """Open cropper using one of the preview files as source."""
        from PyQt6.QtWidgets import QFileDialog, QInputDialog
        from PyQt6.QtGui import QPixmap
        from PyQt6.QtCore import Qt
        import os
        
        # Get preview paths
        preview_str = self.full_preview_edit.text()
        previews = [p.strip() for p in preview_str.split(';') if p.strip() and os.path.exists(p.strip())]
        
        if not previews:
            # No previews, allow user to browse
            path, _filter = QFileDialog.getOpenFileName(self, _("Select Image to Crop"), "", _("Images (*.png *.jpg *.jpeg *.gif *.webp)"))
            if not path: return
            source = path
        elif len(previews) == 1:
            source = previews[0]
        else:
            # Multiple previews - let user choose
            items = [os.path.basename(p) for p in previews]
            choice, ok = QInputDialog.getItem(self, _("Select Preview"), _("Choose preview to crop:"), items, 0, False)
            if not ok: return
            idx = items.index(choice)
            source = previews[idx]
        
        dialog = IconCropDialog(self, source)
        if dialog.exec():
            pixmap = dialog.get_cropped_pixmap()
            if pixmap:
                self.pending_icon_pixmap = pixmap
                self.pending_icon_path = source
                self.image_edit.setText("[Cropped from Preview]")
                self.preview_label.setPixmap(pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                self.preview_label.setText("")

    def _save_pixmap_to_cache(self, pixmap, original_source):
        import hashlib
        import os
        import time
        
        # Cache directory is now relative to Project Root / resource / app / <app_name>
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        cache_dir = os.path.join(project_root, "resource", "app", self.app_name, ".icon_cache")
            
        os.makedirs(cache_dir, exist_ok=True)
        
        unique_key = f"{original_source}_{time.time()}"
        hash_name = hashlib.md5(unique_key.encode()).hexdigest()[:12]
        # Use PNG for cropped items to maintain quality/transparency
        cache_path = os.path.join(cache_dir, f"crop_{hash_name}.png")
        pixmap.save(cache_path, "PNG")
        return cache_path

    def _resize_and_cache_image(self, source_path):
        from PyQt6.QtGui import QPixmap
        from PyQt6.QtCore import Qt
        import os
        import hashlib
        import time
        
        # Cache directory is now relative to Project Root / resource / app / <app_name>
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        cache_dir = os.path.join(project_root, "resource", "app", self.app_name, ".icon_cache")
            
        os.makedirs(cache_dir, exist_ok=True)
        
        unique_key = f"{source_path}_{time.time()}"
        hash_name = hashlib.md5(unique_key.encode()).hexdigest()[:12]
        ext = os.path.splitext(source_path)[1]
        cache_path = os.path.join(cache_dir, f"thumb_{hash_name}{ext}")
        
        pixmap = QPixmap(source_path)
        if not pixmap.isNull() and (pixmap.width() > 256 or pixmap.height() > 256):
            scaled = pixmap.scaled(256, 256, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            scaled.save(cache_path)
            return cache_path
        
        return source_path
    
    def _update_preview(self, path):
        from PyQt6.QtGui import QPixmap
        from PyQt6.QtCore import Qt
        import os
        if path and os.path.exists(path):
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                # Scale preview to match label (1:1)
                scaled = pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.preview_label.setPixmap(scaled)
                return
        self.preview_label.setText(_("No Preview"))

    def _try_load_managed_thumbnail(self):
        """Attempt to find a managed thumbnail that matches the explorer's logic."""
        import os
        if not self.thumbnail_manager or not self.app_name or not self.storage_root:
            self.preview_label.setText("No Image")
            return
            
        try:
            rel_path = os.path.relpath(self.folder_path, self.storage_root)
            if rel_path == ".": rel_path = ""
            
            thumb_path = self.thumbnail_manager.get_thumbnail_path(self.app_name, rel_path)
            if os.path.exists(thumb_path):
                self._update_preview(thumb_path)
                self.preview_label.setToolTip(f"Managed Thumbnail: {os.path.basename(thumb_path)}")
                # Show path in readonly field
                if hasattr(self, 'managed_thumb_edit'):
                    self.managed_thumb_edit.setText(thumb_path)
            else:
                self.preview_label.setText(_("No Cache"))
        except Exception:
             self.preview_label.setText(_("Error"))

    def _on_tag_toggled(self, tag_name, checked):
        # Quick Tags are stored internally via button state.
        # They do NOT modify the manual tags_edit text area.
        # The get_data() method will merge both sources at save time.
        
        # Just update button visual state (color)
        # Note: tag_buttons keys are lowercase
        btn = self.tag_buttons.get(tag_name.lower())
        if btn:
            if checked:
                btn.setStyleSheet("background-color: #2980b9; color: white; border: 1px solid #3498db; padding: 4px 8px;")
            else:
                btn.setStyleSheet("background-color: #444; color: #ccc; border: 1px solid #555; padding: 4px 8px;")


    def _sync_tag_buttons(self):
        """
        Quick Tags are intentionally independent from the manual text area.
        This method now does nothing - Quick Tags only respond to button clicks.
        The merge happens in get_data() at save time.
        """
        pass

    def _on_favorite_toggled_dialog(self, checked):
        self.favorite_btn.setText(_("★Favorite") if checked else _("☆Favorite"))
        
    def _on_clear_name_toggle(self, checked):
        """Phase 26: Toggle display name field based on 'Edit Name' toggle."""
        self.name_edit.setEnabled(checked) # ON -> Enabled, OFF -> Disabled
        if checked:
            self.name_edit.setPlaceholderText(_("Leave empty to clear names"))
        else:
            self.name_edit.clear()
            self.name_edit.setPlaceholderText(_("Toggle ON to edit/clear"))

    def _on_update_score_toggle(self, checked):
        """Phase 26: Enable/Disable score dial based on 'Update Score' toggle."""
        self.score_dial.setEnabled(checked)

    def _open_url_manager(self):
        """Open specialized URL manager dialog."""
        # Use url_list_edit instead of old self.url_list
        dlg = URLListDialog(self, url_list_json=self.url_list_edit.text(), 
                            marked_url=self.current_config.get('marked_url'))
        if dlg.exec():
            json_data = dlg.get_data()
            self.url_list_edit.setText(json_data)
            self._update_url_count()

    def _update_url_count(self):
        """Update the URL count label."""
        import json
        try:
            raw = json.loads(self.url_list_edit.text())
            if isinstance(raw, dict):
                urls = raw.get('urls', [])
            else:
                urls = raw
            count = len(urls)
        except:
            count = 0
        self.url_count_label.setText(_("({count} registered)").format(count=count))

    def _open_library_usage(self):
        """Open the library usage dialog."""
        curr = self.parent()
        db = None
        while curr:
            if hasattr(curr, 'db'):
                db = curr.db
                break
            curr = curr.parent()
            
        if not db:
            QMessageBox.warning(self, _("Error"), _("Database access failed."))
            return
            
        dialog = LibraryUsageDialog(self, db, self.lib_deps)
        if dialog.exec():
            self.lib_deps = dialog.get_result_json()

            
    def get_data(self):
        # Finalize image path (Save pending if any)
        final_image_path = self.image_edit.text()
        
        if self.pending_icon_pixmap:
            # Use a dummy source or the full preview as original for hashing
            source = self.pending_icon_path or self.full_preview_edit.text() or "cropped_selection"
            final_image_path = self._save_pixmap_to_cache(self.pending_icon_pixmap, source)
        elif self.pending_icon_path:
            final_image_path = self._resize_and_cache_image(self.pending_icon_path)

        # Tags Logic (Phase 18 additive)
        manual_tags = {t.strip().lower() for t in self.tags_edit.text().split(',') if t.strip()}
        quick_tags = {name for name, btn in self.tag_buttons.items() if btn.isChecked()}
        
        # Merge manual tags with quick tag buttons
        quick_tags = [name for name, btn in self.tag_buttons.items() if btn.isChecked()]
        manual_tags = [t.strip() for t in self.tags_edit.text().split(',') if t.strip()]
        all_tags = sorted(list(set(quick_tags + manual_tags)))
        
        # Phase 26: Batch mode display name logic
        display_name = self.name_edit.text().strip() or None
        if self.batch_mode:
            if getattr(self, 'batch_clear_name_toggle', None) and not self.batch_clear_name_toggle.isChecked():
                display_name = "KEEP" # No change if toggle is OFF
            elif not display_name:
                display_name = "" # Explicitly clear if toggle is ON and field is empty
        
        data = {
            'display_name': display_name,
            'description': self.description_edit.toPlainText().strip() or None,
            'image_path': final_image_path.strip() or None, # Use the finalized image path
            'manual_preview_path': self.full_preview_edit.text().strip() or None,
            'author': self.author_edit.text().strip() or None,
            'url_list': self.url_list_edit.text() if self.url_list_edit.text() != '[]' else None,
            'is_favorite': 1 if self.favorite_btn.isChecked() else 0,
            'score': self.score_dial.value() if not self.batch_mode or (getattr(self, 'batch_update_score_toggle', None) and self.batch_update_score_toggle.isChecked()) else "KEEP",
            'folder_type': self.type_combo.currentData(),
            'display_style': self.style_combo.currentData(),
            'display_style_package': self.style_combo_pkg.currentData(),
            'tags': ", ".join(all_tags) if all_tags else None,
            'is_visible': 0 if self.hide_checkbox.isChecked() else 1,
            'deploy_rule': self.deploy_rule_override_combo.currentData(),
            'transfer_mode': self.transfer_mode_override_combo.currentData(),
            'deploy_type': None, # Supplant legacy
            'conflict_policy': self.conflict_override_combo.currentData(),
            'inherit_tags': 1 if self.inherit_tags_chk.isChecked() else 0,
            'target_override': self._get_selected_target_path(),
            'conflict_tag': self.conflict_tag_edit.text().strip() if self.conflict_tag_edit.text().strip() else (None if not self.batch_mode else "KEEP"),
            'conflict_scope': self.conflict_scope_combo.currentData(),
            'lib_deps': self.lib_deps if not self.batch_mode else (self.lib_deps if self.lib_deps != self.current_config.get('lib_deps', '[]') else "KEEP"),
        }
        
        # Inject skip_levels into rules JSON
        skip_val = self.skip_levels_spin.value()
        rules_str = self.rules_edit.toPlainText().strip()
        if skip_val > 0 or rules_str:
            try:
                import json
                rules_obj = json.loads(rules_str) if rules_str else {}
                if skip_val > 0:
                    rules_obj['skip_levels'] = skip_val
                elif 'skip_levels' in rules_obj:
                    del rules_obj['skip_levels']
                rules_str = json.dumps(rules_obj) if rules_obj else ""
            except:
                pass 
        data['deployment_rules'] = rules_str or None

        if self.batch_mode:
            # Only return fields that are NOT the "No Change" marker
            # For combos, KEEP is the marker. For text, empty might be marker.
            clean_data = {}
            for k, v in data.items():
                if v == "KEEP": continue
                
                # Special handling for empty strings (like clearing display_name)
                if v == "" and k == 'display_name':
                    clean_data[k] = None # Database expects None for empty
                    continue

                # Special handling for empty/None values in batch mode
                # If we specifically want to clear a field, it will be None or "" (not KEEP)
                if v is None and k not in [
                    'image_path', 'manual_preview_path', 'tags', 'deployment_rules', 
                    'description', 'author', 'url_list', 'conflict_tag', 'target_override'
                ]: 
                    continue 
                
                clean_data[k] = v
            return clean_data
            
        return data

class TagManagerDialog(QDialog):
    def __init__(self, parent=None, db=None, registry=None):
        super().__init__(parent)
        self.db = db
        # Fallback: Try to get registry from parent if not provided
        if registry is None and parent and hasattr(parent, 'registry'):
            registry = parent.registry
        # Final fallback: Get global registry singleton
        if registry is None:
            from src.core.link_master.database import get_lm_registry
            registry = get_lm_registry()
            import logging; logging.info(f"[TagManagerDialog] Using global registry singleton")
        self.registry = registry
        import logging; logging.info(f"[TagManagerDialog] __init__: registry={registry is not None}")
        self.setWindowTitle(_("Manage Frequent Tags"))
        self.resize(500, 400)
        self.tags = [] 
        self._dirty = False 
        self._loading = False 
        
        self._init_ui()
        self._load_tags()
        
        # Phase 32: Restore Size (use registry for global persistence)
        if self.registry:
            geom = self.registry.get_setting("geom_tag_manager", None)
            logging.info(f"[TagManagerDialog] Restoring geometry: geom={'found' if geom else 'None'}")
            if geom: 
                self.restoreGeometry(bytes.fromhex(geom))
                logging.info(f"[TagManagerDialog] Restored to: {self.width()}x{self.height()}")
        else:
            logging.warning("[TagManagerDialog] registry is None, cannot restore geometry")
        
        # Phase 32: Connect finished signal to ensure geometry is saved on close
        self.finished.connect(self._on_dialog_finished)

    def _save_geometry(self):
        """Save current geometry to registry."""
        import logging
        logging.info(f"[TagManagerDialog] _save_geometry called, registry={self.registry is not None}")
        if self.registry:
            try:
                geom_hex = self.saveGeometry().toHex().data().decode()
                self.registry.set_setting("geom_tag_manager", geom_hex)
                logging.info(f"[TagManagerDialog] Saved geometry: {self.width()}x{self.height()}")
            except Exception as e:
                logging.error(f"[TagManagerDialog] Failed to save geometry: {e}")
        else:
            logging.warning("[TagManagerDialog] registry is None, cannot save geometry")

    def _on_dialog_finished(self, result):
        """Called when dialog is finished (accept or reject)."""
        import logging
        logging.info(f"[TagManagerDialog] _on_dialog_finished called, result={result}")
        self._save_geometry()
        
        
    def _init_ui(self):
        from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView, QLabel, QVBoxLayout, QHBoxLayout, QWidget, QHeaderView, QFormLayout, QLineEdit, QComboBox, QCheckBox, QPushButton
        from PyQt6.QtGui import QIcon, QColor, QPixmap
        from PyQt6.QtCore import Qt, QRect
        
        layout = QHBoxLayout(self)
        
        # Left: Table
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        hint_label = QLabel(_("💡 Drag items to reorder"))
        hint_label.setStyleSheet("color: #888; font-style: italic;")
        left_layout.addWidget(hint_label)
        
        self.tag_table = QTableWidget()
        self.tag_table.setColumnCount(5)
        self.tag_table.setHorizontalHeaderLabels([
            _("Icon"), _("Symbol"), _("Tag Name"), _("Inherit"), _("Display Mode")
        ])
        
        self.tag_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tag_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tag_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tag_table.verticalHeader().setVisible(False)
        self.tag_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tag_table.horizontalHeader().setStretchLastSection(True)
        self.tag_table.setColumnWidth(0, 40)
        self.tag_table.setColumnWidth(1, 40)
        self.tag_table.setColumnWidth(3, 40)
        
        self.tag_table.itemClicked.connect(self._on_table_clicked)
        self.tag_table.setDragEnabled(True)
        self.tag_table.setAcceptDrops(True)
        self.tag_table.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.tag_table.setDefaultDropAction(Qt.DropAction.MoveAction)
        
        # Sync tags after manual reorder
        self.tag_table.model().rowsMoved.connect(self._on_rows_moved)
        
        left_layout.addWidget(self.tag_table)
        layout.addWidget(left_panel, 2)
        
        # Right: Edit Area
        self.right_panel = QWidget()
        self.right_panel.setObjectName("tagEditPanel")
        self.right_panel.setStyleSheet("#tagEditPanel { background-color: #252525; border-radius: 8px; }")
        right_layout = QVBoxLayout(self.right_panel)
        
        self.empty_placeholder = QLabel(_("👈 Select a tag or click 'Add New Tag' to start editing."))
        self.empty_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_placeholder.setStyleSheet("color: #888; font-style: italic; background: transparent; padding: 20px;")
        self.empty_placeholder.setWordWrap(True)
        right_layout.addWidget(self.empty_placeholder)

        self.edit_container = QWidget()
        self.edit_container.setStyleSheet("background: transparent;")
        edit_layout = QVBoxLayout(self.edit_container)
        edit_layout.setContentsMargins(10, 10, 10, 10)
        
        form = QFormLayout()
        form.setSpacing(10)
        
        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self._on_data_changed)
        form.addRow(_("Tag:"), self.name_edit)
        
        self.emoji_edit = QLineEdit()
        self.emoji_edit.setPlaceholderText(_("e.g. 🎨"))
        self.emoji_edit.setMaxLength(4) 
        self.emoji_edit.textChanged.connect(self._on_data_changed)
        
        self.display_mode_combo = QComboBox()
        from PyQt6.QtWidgets import QListView
        self.display_mode_combo.setView(QListView())
        self.display_mode_combo.setStyleSheet("QComboBox QAbstractItemView { background-color: #2b2b2b; color: #fff; selection-background-color: #3498db; }")
        self.display_mode_combo.addItem(_("Text"), "text")
        self.display_mode_combo.addItem(_("Symbol"), "symbol")
        self.display_mode_combo.addItem(_("Symbol + Text"), "text_symbol")
        self.display_mode_combo.addItem(_("Image"), "image")
        self.display_mode_combo.addItem(_("Image + Text"), "image_text")
        self.display_mode_combo.currentIndexChanged.connect(self._on_data_changed)
        form.addRow(_("Display Mode:"), self.display_mode_combo)

        emoji_h = QHBoxLayout()
        emoji_h.addWidget(self.emoji_edit)
        emoji_h.addStretch()
        form.addRow(_("Symbol (Display):"), emoji_h)

        self.inheritable_check = SlideButton()
        self.inheritable_check.setChecked(True)
        self.inheritable_check.toggled.connect(self._on_data_changed)
        form.addRow(_("Inherit to children:"), self.inheritable_check)
        
        self.icon_edit = TagIconLineEdit()
        self.icon_edit.file_dropped.connect(self._on_icon_dropped_to_edit)
        self.icon_edit.textChanged.connect(self._on_data_changed)
        self.icon_btn = QPushButton("...")
        self.icon_btn.setFixedWidth(30)
        self.icon_btn.clicked.connect(self._browse_icon)
        
        h = QHBoxLayout()
        h.addWidget(self.icon_edit)
        h.addWidget(self.icon_btn)
        form.addRow(_("Icon:"), h)
        
        edit_layout.addLayout(form)
        edit_layout.addStretch()
        
        self.edit_container.setVisible(False)
        right_layout.addWidget(self.edit_container)
        
        # Buttons
        btn_group = QWidget()
        btn_layout = QVBoxLayout(btn_group)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        
        self.overwrite_btn = QPushButton(_("Overwrite Current"))
        self.overwrite_btn.clicked.connect(self._save_current_item_data)
        self.overwrite_btn.setStyleSheet("background-color: #2980b9; color: white;")
        
        self.add_btn = QPushButton(_("Add New Tag"))
        self.add_btn.clicked.connect(self._add_tag_default)
        self.add_btn.setStyleSheet("background-color: #e67e22; color: white;")
        
        self.add_sep_btn = QPushButton(_("Add Separator"))
        self.add_sep_btn.clicked.connect(self._add_sep)
        self.add_sep_btn.setStyleSheet("background-color: #555; color: white;")
        
        self.remove_btn = QPushButton(_("Remove Selected"))
        self.remove_btn.clicked.connect(self._remove_tag)
        self.remove_btn.setStyleSheet("background-color: #c0392b; color: white;")
        
        self.save_btn = QPushButton(_("Confirm"))
        self.save_btn.clicked.connect(self._save_and_close)
        self.save_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; margin-top: 10px;")
        
        btn_layout.addWidget(self.overwrite_btn)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.add_sep_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addWidget(self.save_btn)
        
        right_layout.addWidget(btn_group)
        layout.addWidget(self.right_panel, 1)
        
        self.setStyleSheet("""
            QDialog { background-color: #2b2b2b; color: #ffffff; }
            QLineEdit { background-color: #3b3b3b; color: #ffffff; border: 1px solid #555; padding: 4px; }
            QLineEdit:disabled { background-color: #222; color: #777; }
            QTableWidget { background-color: #333; color: #ffffff; border: 1px solid #555; gridline-color: #444; }
            QTableWidget::item:selected { background-color: #2980b9; color: #ffffff; }
            QHeaderView::section { background-color: #252525; color: #fff; padding: 4px; border: 1px solid #444; }
            QPushButton { background-color: #444; color: #ffffff; padding: 6px; border-radius: 4px; border: none; }
            QPushButton:hover { background-color: #555; }
            QLabel { color: #ffffff; }
            QCheckBox { color: #ffffff; padding: 4px; }
            QCheckBox::indicator { border: 1px solid #555; background: #3b3b3b; width: 18px; height: 18px; border-radius: 3px; }
            QCheckBox::indicator:unchecked:hover { border-color: #3498db; }
            QCheckBox::indicator:checked { 
                background-color: #3498db; border-color: #3498db;
                image: url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0id2hpdGUiIGQ9Ik05IDE2LjE3TDQuODMgMTJsLTEuNDIgMS40MUw5IDE5IDIxIDdsLTEuNDEtMS40MXoiLz48L3N2Zz4=");
            }
            QComboBox { background-color: #3b3b3b; color: #ffffff; border: 1px solid #555; padding: 4px; }
            QComboBox QAbstractItemView, QListView { background-color: #2b2b2b; color: #ffffff; selection-background-color: #3498db; outline: none; border: 1px solid #555; }
        """)

    def _load_tags(self):
        if not self.db: return
        self._loading = True
        try:
            import json
            raw = self.db.get_setting('frequent_tags_config', '[]')
            try:
                self.tags = json.loads(raw)
                if not isinstance(self.tags, list): self.tags = []
            except:
                self.tags = []
            self._refresh_table()
        finally:
            self._loading = False
        
        if self.tag_table.rowCount() > 0:
            self.tag_table.selectRow(0)
            self._on_table_clicked(self.tag_table.item(0, 0))
        else:
            self.edit_container.setVisible(False)
            self.empty_placeholder.setVisible(True)
        
    def _refresh_list(self):
        self._refresh_table()

    def _refresh_table(self):
        self.tag_table.setRowCount(0)
        from PyQt6.QtGui import QIcon, QColor
        import os
        for idx, tag in enumerate(self.tags):
            self.tag_table.insertRow(idx)
            is_sep = tag.get('name') == '|' or tag.get('is_sep')
            if is_sep:
                # Store data in Column 0 even for separators to ensure sync/saving works
                sep_data_item = QTableWidgetItem()
                sep_data_item.setData(Qt.ItemDataRole.UserRole, tag)
                self.tag_table.setItem(idx, 0, sep_data_item)
                
                sep_item = QTableWidgetItem(_("|--- Separator ---|"))
                sep_item.setForeground(QColor("#888"))
                self.tag_table.setItem(idx, 2, sep_item)
                # Ensure other columns 1, 3, 4 are empty
                for col in [1, 3, 4]:
                    self.tag_table.setItem(idx, col, QTableWidgetItem(""))
            else:
                icon_path = tag.get('icon')
                icon_item = QTableWidgetItem()
                if icon_path and os.path.exists(icon_path):
                     icon_item.setIcon(QIcon(icon_path))
                icon_item.setData(Qt.ItemDataRole.UserRole, tag)
                self.tag_table.setItem(idx, 0, icon_item)
                self.tag_table.setItem(idx, 1, QTableWidgetItem(tag.get('emoji', '')))
                self.tag_table.setItem(idx, 2, QTableWidgetItem(tag.get('name', '???')))
                inherit = "Yes" if tag.get('is_inheritable', True) else "No"
                self.tag_table.setItem(idx, 3, QTableWidgetItem(_(inherit)))
                mode_map = {
                    'text': _("Text"),
                    'symbol': _("Symbol"),
                    'text_symbol': _("Symbol + Text"),
                    'image': _("Image"),
                    'image_text': _("Image + Text")
                }
                mode_label = mode_map.get(tag.get('display_mode', 'text'), tag.get('display_mode', 'text'))
                self.tag_table.setItem(idx, 4, QTableWidgetItem(mode_label))
            
            for col in range(5):
                item = self.tag_table.item(idx, col)
                if item:
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled)

        if self.tag_table.rowCount() == 0:
            self.edit_container.setVisible(False)
            self.empty_placeholder.setVisible(True)
            self.current_tag_ref = None
        else:
            self.empty_placeholder.setVisible(False)
            self.edit_container.setVisible(True)
            if self.tag_table.currentRow() == -1:
                self.tag_table.selectRow(0)
                item = self.tag_table.item(0, 0)
                if item: self._on_table_clicked(item)
            
    def _on_table_clicked(self, item):
        if not item: return
        row = self.tag_table.row(item)
        main_item = self.tag_table.item(row, 0)
        self._on_item_clicked(main_item)

    def _on_item_clicked(self, item):
        if not item:
            self.edit_container.setVisible(False)
            self.empty_placeholder.setVisible(True)
            self.current_tag_ref = None
            return
        tag = item.data(Qt.ItemDataRole.UserRole)
        if tag is None:
            self.edit_container.setVisible(False)
            self.empty_placeholder.setVisible(True)
            self.current_tag_ref = None
            return

        self.current_tag_ref = tag
        self._loading = True
        self.edit_container.setVisible(True)
        self.empty_placeholder.setVisible(False)
        self.name_edit.setText(tag.get('name', ''))
        self.emoji_edit.setText(tag.get('emoji', ''))
        mode = tag.get('display_mode', 'text')
        idx = self.display_mode_combo.findData(mode)
        if idx >= 0: self.display_mode_combo.setCurrentIndex(idx)
        else: self.display_mode_combo.setCurrentIndex(0)
        self.icon_edit.setText(tag.get('icon', ''))
        self.inheritable_check.setChecked(bool(tag.get('is_inheritable', True)))
        self._loading = False
        is_sep = tag.get('name') == '|' or tag.get('is_sep')
        self.name_edit.setEnabled(not is_sep)
        self.emoji_edit.setEnabled(not is_sep)
        self.display_mode_combo.setEnabled(not is_sep)
        self.icon_edit.setEnabled(not is_sep)
        self.inheritable_check.setEnabled(not is_sep)
            
    def _on_data_changed(self):
        pass

    def _on_rows_moved(self, parent, start, end, destination, row):
        """Handle synchronization after the row move is visually complete."""
        # Using a timer to ensure the move is finished in the model
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._sync_tags_from_table)
        self._dirty = True

    def _sync_tags_from_table(self):
        """Update self.tags list from the current order of the table."""
        if self._loading: return
        new_tags = []
        for i in range(self.tag_table.rowCount()):
            item = self.tag_table.item(i, 0)
            if item:
                tag_data = item.data(Qt.ItemDataRole.UserRole)
                if tag_data:
                    new_tags.append(tag_data)
        self.tags = new_tags
        print(f"[TagManager] tags synchronized from table ({len(self.tags)} items)")

    def _add_tag_default(self):
        name = "Tag"
        new_tag = {
            "name": name, "value": name, "emoji": "", "icon": "", 
            "display_mode": "text", "is_sep": False, "is_inheritable": True
        }
        self.tags.append(new_tag)
        self._refresh_list()
        self.tag_table.selectRow(self.tag_table.rowCount()-1)
        self._on_table_clicked(self.tag_table.item(self.tag_table.rowCount()-1, 0))
        self._dirty = True
    
    def _save_current_item_data(self):
        row = self.tag_table.currentRow()
        if row >= 0:
            # Get the actual tag dictionary stored in the item (robust to reordering)
            item0 = self.tag_table.item(row, 0)
            if not item0: return
            tag = item0.data(Qt.ItemDataRole.UserRole)
            if not tag: return
            
            if not tag.get('is_sep'):
                tag['name'] = self.name_edit.text().strip() or 'Unnamed'
                tag['value'] = tag['name'] 
                tag['emoji'] = self.emoji_edit.text().strip()
                tag['icon'] = self.icon_edit.text().strip()
                tag['display_mode'] = self.display_mode_combo.currentData()
                tag['is_inheritable'] = self.inheritable_check.isChecked()
                item0 = self.tag_table.item(row, 0)
                if item0:
                    item0.setData(Qt.ItemDataRole.UserRole, tag)
                    if tag['icon'] and os.path.exists(tag['icon']):
                        from PyQt6.QtGui import QIcon
                        item0.setIcon(QIcon(tag['icon']))
                    else:
                        item0.setIcon(QIcon())
                self.tag_table.setItem(row, 1, QTableWidgetItem(tag['emoji']))
                self.tag_table.setItem(row, 2, QTableWidgetItem(tag['name']))
                inherit = "Yes" if tag['is_inheritable'] else "No"
                self.tag_table.setItem(row, 3, QTableWidgetItem(_(inherit)))
                mode_map = {
                    'text': _("Text"), 'symbol': _("Symbol"), 'text_symbol': _("Symbol + Text"),
                    'image': _("Image"), 'image_text': _("Image + Text")
                }
                mode_label = mode_map.get(tag['display_mode'], tag['display_mode'])
                self.tag_table.setItem(row, 4, QTableWidgetItem(mode_label))
                for col in range(5):
                    it = self.tag_table.item(row, col)
                    if it: it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled)
            self._dirty = True
        
    def _add_sep(self):
        new_tag = {"name": "|", "value": "|", "emoji": "", "icon": "", "is_sep": True, "is_inheritable": True}
        self.tags.append(new_tag)
        self._refresh_table()
        self.tag_table.selectRow(self.tag_table.rowCount()-1)
        self._dirty = True

    def _remove_tag(self):
        row = self.tag_table.currentRow()
        if row >= 0:
            self._loading = True
            self.current_tag_ref = None
            self.tags.pop(row)
            self._refresh_list()
            self._loading = False
            self._dirty = True

    def _clear_icon(self):
        self.icon_edit.clear()

    def _on_icon_dropped_to_edit(self, path):
        self._process_and_set_icon(path)

    def _process_and_set_icon(self, path):
        try:
            from PyQt6.QtGui import QImage
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
            res_dir = os.path.join(project_root, "resource", "tags")
            os.makedirs(res_dir, exist_ok=True)
            dest_path = os.path.join(res_dir, os.path.basename(path))
            img = QImage(path)
            if not img.isNull():
                img = img.scaled(28, 28, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                img.save(dest_path)
            else:
                import shutil
                shutil.copy2(path, dest_path)
            self.icon_edit.setText(dest_path)
        except Exception as e:
            self.icon_edit.setText(path)

    def _browse_icon(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _filter = QFileDialog.getOpenFileName(self, _("Select Icon"), "", _("Images (*.png *.ico *.svg *.jpg)"))
        if path: self._process_and_set_icon(path)

    def _save_and_close(self):
        self._save_current_item_data()
        import json
        if self.db:
            new_tags = []
            for i in range(self.tag_table.rowCount()):
                item = self.tag_table.item(i, 0)
                tag_data = item.data(Qt.ItemDataRole.UserRole)
                if tag_data: new_tags.append(tag_data)
            try:
                self.db.set_setting('frequent_tags_config', json.dumps(new_tags))
                names = [t['name'] for t in new_tags if t.get('name') != '|']
                self.db.set_setting('frequent_tags', ",".join(names))
            except: pass
        self._dirty = False
        self.accept()

    def closeEvent(self, event):
        # Phase 32: Always save geometry before closing
        self._save_geometry()
        
        if self._dirty:
            from PyQt6.QtWidgets import QMessageBox
            reply = QMessageBox.question(self, _("Unsaved Changes"), _("You have unsaved changes. Do you want to save them?"), QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Save:
                self._save_and_close()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard: event.accept()
            else: event.ignore()
        else: event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape: self.close()
        else: super().keyPressEvent(event)


class TagCreationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Add Frequent Tag"))
        self.resize(300, 200)
        self.result_data = None
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(_("Tag Name"))
        form.addRow(_("Tag:"), self.name_edit)
        
        self.emoji_edit = QLineEdit()
        self.emoji_edit.setPlaceholderText(_("e.g. 🎨"))
        self.emoji_edit.setMaxLength(4) 
        
        # Display Mode Combo (Match TagManagerDialog)
        self.display_mode_combo = QComboBox()
        from PyQt6.QtWidgets import QListView
        self.display_mode_combo.setView(QListView()) # FORCE QSS on windows
        self.display_mode_combo.setStyleSheet("QComboBox QAbstractItemView { background-color: #2b2b2b; color: #fff; selection-background-color: #3498db; }")
        self.display_mode_combo.addItem(_("Text"), "text")
        self.display_mode_combo.addItem(_("Symbol"), "symbol")
        self.display_mode_combo.addItem(_("Symbol + Text"), "text_symbol")
        self.display_mode_combo.addItem(_("Image"), "image")
        self.display_mode_combo.addItem(_("Image + Text"), "image_text")
        
        emoji_h = QHBoxLayout()
        emoji_h.addWidget(self.emoji_edit)
        emoji_h.addStretch()
        
        form.addRow(_("Display Mode:"), self.display_mode_combo)
        form.addRow(_("Symbol (Display):"), emoji_h)
        
        # Icon Path (DnD Enabled)
        self.icon_edit = TagIconLineEdit()
        self.icon_edit.file_dropped.connect(self._on_icon_dropped_to_edit)
        self.icon_edit.setPlaceholderText(_("Icon Path (Optional)"))
        self.icon_btn = QPushButton("...")
        self.icon_btn.setFixedWidth(30)
        self.icon_btn.clicked.connect(self._browse_icon)
        
        h = QHBoxLayout()
        h.addWidget(self.icon_edit)
        h.addWidget(self.icon_btn)
        form.addRow(_("Icon:"), h)
        
        # Inheritance (Phase 18.9 compatibility)
        self.inheritable_check = SlideButton()
        self.inheritable_check.setChecked(True)
        form.addRow(_("Inherit to children:"), self.inheritable_check)
        
        self.is_sep_check = SlideButton()
        self.is_sep_check.toggled.connect(self._on_sep_toggled)
        form.addRow(_("Is Separator (|):"), self.is_sep_check)
        
        layout.addLayout(form)
        
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton(_("Add"))
        ok_btn.clicked.connect(self._on_ok)
        cancel_btn = QPushButton(_("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        self.setStyleSheet("""
            QDialog { background-color: #2b2b2b; color: #ffffff; }
            QLineEdit { background-color: #3b3b3b; color: #ffffff; border: 1px solid #555; padding: 4px; }
            QPushButton { background-color: #444; color: #ffffff; padding: 6px; border-radius: 4px; border: none; }
            QPushButton:hover { background-color: #555; }
            QLabel { color: #ffffff; }
            QCheckBox { color: #ffffff; padding: 4px; }
            QCheckBox::indicator { border: 1px solid #555; background: #3b3b3b; width: 18px; height: 18px; border-radius: 3px; }
            QCheckBox::indicator:unchecked:hover { border-color: #3498db; }
            QCheckBox::indicator:checked { 
                background-color: #3498db; border-color: #3498db;
                image: url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0id2hpdGUiIGQ9Ik05IDE2LjE3TDQuODMgMTJsLTEuNDIgMS40MUw5IDE5IDIxIDdsLTEuNDEtMS40MXoiLz48L3N2Zz4=");
            }
            QComboBox { background-color: #3b3b3b; color: #ffffff; border: 1px solid #555; padding: 4px; }
            QComboBox QAbstractItemView, QListView { background-color: #2b2b2b; color: #ffffff; selection-background-color: #3498db; outline: none; border: 1px solid #555; }
        """)

    def _on_sep_toggled(self, checked):
        self.name_edit.setEnabled(not checked)
        self.emoji_edit.setEnabled(not checked)
        self.display_mode_combo.setEnabled(not checked)
        self.icon_edit.setEnabled(not checked)
        self.icon_btn.setEnabled(not checked)
        
        if checked:
            self.name_edit.setText("|")
        else:
            if self.name_edit.text() == "|": self.name_edit.clear()

    def _on_icon_dropped_to_edit(self, path):
        """Handle image drop into the LineEdit."""
        self._process_and_set_icon(path)

    def _process_and_set_icon(self, path):
        """Resize and copy image to resource dir, then set value."""
        try:
            from PyQt6.QtGui import QImage
            from PyQt6.QtCore import Qt
            import shutil
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
            res_dir = os.path.join(project_root, "resource", "tags")
            os.makedirs(res_dir, exist_ok=True)
            
            dest_name = f"{os.path.basename(path)}"
            dest_path = os.path.join(res_dir, dest_name)
            
            img = QImage(path)
            if not img.isNull():
                img = img.scaled(28, 28, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                img.save(dest_path)
            else:
                shutil.copy2(path, dest_path)
            self.icon_edit.setText(dest_path)
        except Exception as e:
            print(f"Icon process error: {e}")
            self.icon_edit.setText(path)

    def _browse_icon(self):
        from PyQt6.QtWidgets import QFileDialog
        from src.core.lang_manager import _
        path, _filter = QFileDialog.getOpenFileName(self, _("Select Icon"), "", _("Images (*.png *.ico *.svg *.jpg)"))
        if path:
            self._process_and_set_icon(path)

    def _on_ok(self):
        if self.is_sep_check.isChecked():
            # 💡 Consistent identifier 'value' for separators
            self.result_data = {"name": "|", "value": "|", "emoji": "", "icon": "", "prefer_emoji": False, "is_inheritable": True, "is_sep": True}
            self.accept()
            return
        
        name = self.name_edit.text().strip()
        if not name:
            return
            
        self.result_data = {
            "name": name,
            "value": name, # 💡 Add identifier key for DB consistency
            "emoji": self.emoji_edit.text().strip(),
            "display_mode": self.display_mode_combo.currentData(),
            "prefer_emoji": (self.display_mode_combo.currentData() != "image"),
            "icon": self.icon_edit.text().strip(),
            "is_inheritable": self.inheritable_check.isChecked(),
            "is_sep": False
        }
        self.accept()

    def get_data(self):
        return self.result_data


class CropLabel(QLabel):
    """Custom label for interactive cropping with a translucent red selection square."""
    def __init__(self, pixmap, parent=None, allow_free=False):
        super().__init__(parent)
        self.setPixmap(pixmap)
        self.setFixedSize(pixmap.size())
        self.setMouseTracking(True)
        self.allow_free = allow_free
        self.aspect_ratio = 1.0 # W/H (Square)
        self.selection_rect = QRect(20, 20, 100, 100)
        self.dragging = False
        self.resizing = False
        self.drag_start = QPoint()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        
        # Draw translucent black background (scrim) outside the selection
        painter.setBrush(QColor(0, 0, 0, 100))
        painter.setPen(Qt.PenStyle.NoPen)
        
        path = QPainterPath()
        path.setFillRule(Qt.FillRule.OddEvenFill)
        path.addRect(QRectF(self.rect()))
        path.addRect(QRectF(self.selection_rect))
        painter.fillPath(path, painter.brush())

        # Draw Selection Border (Translucent Red as requested)
        painter.setBrush(QColor(255, 0, 0, 70)) # Slightly more opaque red fill
        painter.drawRect(self.selection_rect)
        
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(QColor(255, 0, 0, 255), 3) # Thicker 3px solid red border
        painter.setPen(pen)
        painter.drawRect(self.selection_rect)
        
        # Draw corner handle - larger and centered
        painter.setBrush(QColor(255, 255, 255)) # White handle for contrast
        h_size = 12
        painter.drawRect(self.selection_rect.right() - h_size//2, self.selection_rect.bottom() - h_size//2, h_size, h_size)

    def mousePressEvent(self, event):
        pos = event.pos()
        # Corner resize handle
        handle_rect = QRect(self.selection_rect.right() - 15, self.selection_rect.bottom() - 15, 30, 30)
        if handle_rect.contains(pos):
            self.resizing = True
        elif self.selection_rect.contains(pos):
            self.dragging = True
            self.drag_start = pos - self.selection_rect.topLeft()
        self.update()

    def mouseMoveEvent(self, event):
        pos = event.pos()
        # Update Cursor
        handle_rect = QRect(self.selection_rect.right() - 20, self.selection_rect.bottom() - 20, 40, 40)
        if handle_rect.contains(pos):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif self.selection_rect.contains(pos):
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

        if self.resizing:
            # Phase 4: Handle free cropping or maintain 1:1 aspect ratio
            diff_w = max(20, event.pos().x() - self.selection_rect.left())
            new_w = min(diff_w, self.pixmap().width() - self.selection_rect.left())
            
            if self.allow_free:
                new_h = max(20, event.pos().y() - self.selection_rect.top())
                new_h = min(new_h, self.pixmap().height() - self.selection_rect.top())
            else:
                new_h = int(new_w / self.aspect_ratio)
                # Second clamp for height
                if self.selection_rect.top() + new_h > self.pixmap().height():
                    new_h = self.pixmap().height() - self.selection_rect.top()
                    new_w = int(new_h * self.aspect_ratio)
            
            self.selection_rect.setWidth(new_w)
            self.selection_rect.setHeight(new_h)
            self.update()
        elif self.dragging:
            new_pos = pos - self.drag_start
            self.selection_rect.moveTo(new_pos)
            # Clamp
            if self.selection_rect.left() < 0: self.selection_rect.moveLeft(0)
            if self.selection_rect.top() < 0: self.selection_rect.moveTop(0)
            if self.selection_rect.right() > self.width():
                self.selection_rect.moveRight(self.width())
            if self.selection_rect.bottom() > self.height():
                self.selection_rect.moveBottom(self.height())
            self.update()

    def mouseReleaseEvent(self, event):
        self.dragging = False
        self.resizing = False
        self.update()

class IconCropDialog(QDialog):
    def __init__(self, parent=None, image_source=None, allow_free=False):
        super().__init__(parent)
        self.setWindowTitle(_("Select Region"))
        self.setModal(True)
        self.setMinimumSize(800, 600)
        self.setStyleSheet("background-color: #2b2b2b; color: #fff;")
        self.allow_free = allow_free
        
        # Load image
        if isinstance(image_source, str) and os.path.exists(image_source):
            self.pixmap = QPixmap(image_source)
        elif isinstance(image_source, QPixmap):
            self.pixmap = image_source
        else:
            self.pixmap = QPixmap()
            
        if self.pixmap.isNull():
             self.close()
             return
             
        # Scale for display
        self.max_display_w = 800
        self.max_display_h = 600
        
        self.display_pixmap = self.pixmap.scaled(self.max_display_w, self.max_display_h, 
                                               Qt.AspectRatioMode.KeepAspectRatio)
        self.scale_factor = self.pixmap.width() / self.display_pixmap.width()
        
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        self.hint_label = QLabel(_("Drag to move selection, use bottom-right corner to resize. Aspect ratio: 1:1 (Square)."))
        if self.allow_free:
            self.hint_label.setText(_("Drag to move, resize corner for free selection."))
            
        self.hint_label.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(self.hint_label)
        
        # Use Custom Label
        self.crop_label = CropLabel(self.display_pixmap, self, allow_free=self.allow_free)
        layout.addWidget(self.crop_label)
        
        btns = QHBoxLayout()
        
        # Toggle Mode Button
        self.mode_btn = QPushButton(_("Mode: Free") if self.allow_free else _("Mode: Square"))
        self.mode_btn.setCheckable(True)
        self.mode_btn.setChecked(self.allow_free)
        self.mode_btn.clicked.connect(self._toggle_mode)
        self.mode_btn.setStyleSheet("background-color: #34495e; color: white; border: 1px solid #555;")
        btns.addWidget(self.mode_btn)
        
        btns.addStretch()
        
        btn_ok = QPushButton(_("Crop && Apply"))
        btn_ok.clicked.connect(self.accept)
        btn_ok.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        
        btn_cancel = QPushButton(_("Cancel"))
        btn_cancel.clicked.connect(self.reject)
        
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

    def _toggle_mode(self):
        self.allow_free = self.mode_btn.isChecked()
        self.crop_label.allow_free = self.allow_free
        
        if self.allow_free:
            self.mode_btn.setText(_("Mode: Free"))
            self.hint_label.setText(_("Drag to move, resize corner for free selection."))
        else:
            self.mode_btn.setText(_("Mode: Square"))
            self.hint_label.setText(_("Drag to move selection, use bottom-right corner to resize. Aspect ratio: 1:1 (Square)."))
            
            # Forge aspect ratio
            w, h = self.crop_label.selection_rect.width(), self.crop_label.selection_rect.height()
            size = min(w, h)
            self.crop_label.selection_rect.setWidth(size)
            self.crop_label.selection_rect.setHeight(size)
            
        self.crop_label.update()

    def get_cropped_pixmap(self):
        # Convert display rect to source rect
        sel = self.crop_label.selection_rect
        source_x = int(sel.x() * self.scale_factor)
        source_y = int(sel.y() * self.scale_factor)
        source_w = int(sel.width() * self.scale_factor)
        source_h = int(sel.height() * self.scale_factor)
        
        source_rect = QRect(source_x, source_y, source_w, source_h)
        cropped = self.pixmap.copy(source_rect)
        
        if self.allow_free:
            return cropped # Don't scale to square
            
        # Scale to match standard icon size (256x256)
        return cropped.scaled(256, 256, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)

class ImportTypeDialog(QDialog):
    """Custom dark-themed dialog for selecting import type (Folder, Zip, or Open Explorer)."""
    def __init__(self, parent=None, target_type="item"):
        super().__init__(parent)
        self.target_type = target_type
        self.result_type = None
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._init_ui()

    def _init_ui(self):
        # Semi-transparent background container
        self.container = QWidget(self)
        self.container.setObjectName("DialogContainer")
        self.container.setStyleSheet("""
            #DialogContainer {
                background-color: rgba(30, 30, 30, 240);
                border: 1px solid #444;
                border-radius: 12px;
            }
            QLabel { color: #eee; font-size: 14px; }
            QPushButton {
                background-color: #444; color: #fff; border: 1px solid #555;
                padding: 10px; border-radius: 6px; font-size: 13px;
            }
            QPushButton:hover { background-color: #555; border-color: #666; }
            QPushButton#ActionBtn { background-color: #2980b9; font-weight: bold; border-color: #3498db; }
            QPushButton#ActionBtn:hover { background-color: #3498db; }
            QPushButton#CancelBtn { background-color: #2c3e50; font-size: 11px; padding: 6px; }
            QPushButton#CancelBtn:hover { background-color: #34495e; }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.container)
        
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Translating capitalized capitalized target_type name
        if self.target_type == "item":
            title_text = _("Import Item")
            type_name = _("Item")
        elif self.target_type == "category":
            title_text = _("Import Category")
            type_name = _("Category")
        else:
            title_text = _("Import Package")
            type_name = _("Package")
            
        title = QLabel(f"<b>{title_text}</b>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16px; color: #3498db; margin-bottom: 2px;")
        layout.addWidget(title)

        # Added Security Note (Phase 32)
        note = QLabel(_("Note: Target installation paths are NOT stored in dioco files for security."))
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setStyleSheet("color: #888; font-size: 10px; font-style: italic; margin-bottom: 8px;")
        note.setWordWrap(True)
        layout.addWidget(note)
        
        desc = QLabel(_("Select how to import this {type}:").format(type=type_name))
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True) # Fix clipping
        layout.addWidget(desc)
        
        # Buttons
        btn_folder = QPushButton(_("📁 Folder"))
        btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_folder.clicked.connect(lambda: self._set_result("folder"))
        layout.addWidget(btn_folder)
        
        btn_zip = QPushButton(_("📦 Zip File"))
        btn_zip.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_zip.clicked.connect(lambda: self._set_result("zip"))
        layout.addWidget(btn_zip)
        
        btn_explorer = QPushButton(_("🔍 Open Explorer"))
        btn_explorer.setObjectName("ActionBtn")
        btn_explorer.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_explorer.clicked.connect(lambda: self._set_result("explorer"))
        layout.addWidget(btn_explorer)
        
        layout.addSpacing(5)
        
        btn_cancel = QPushButton(_("Cancel"))
        btn_cancel.setObjectName("CancelBtn")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        layout.addWidget(btn_cancel)
        
        self.setFixedSize(300, 320)

    def _set_result(self, rtype):
        self.result_type = rtype
        self.accept()

    def get_result(self):
        return self.result_type

class PresetPropertiesDialog(QDialog):
    """Dialog to edit preset metadata like name and description."""
    def __init__(self, parent=None, name="", description=""):
        super().__init__(parent)
        self.setWindowTitle(_("Preset Properties"))
        self.setFixedWidth(400)
        self.setStyleSheet("""
            QDialog { background-color: #2b2b2b; color: #ffffff; }
            QLabel { color: #cccccc; }
            QLineEdit, QTextEdit { 
                background-color: #3b3b3b; color: #ffffff; 
                border: 1px solid #555; padding: 4px; border-radius: 4px;
            }
            QPushButton {
                background-color: #444; color: #fff; border: none; padding: 6px; border-radius: 4px;
            }
        """)
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.name_edit = QLineEdit(name)
        form.addRow(_("Preset Name:"), self.name_edit)
        
        from PyQt6.QtWidgets import QTextEdit
        self.desc_edit = QTextEdit()
        self.desc_edit.setPlainText(description or "")
        self.desc_edit.setPlaceholderText(_("Optional description..."))
        form.addRow(_("Description:"), self.desc_edit)
        
        layout.addLayout(form)
        
        btns = QHBoxLayout()
        ok_btn = QPushButton(_("Save"))
        ok_btn.clicked.connect(self.accept)
        ok_btn.setStyleSheet("background-color: #2980b9; font-weight: bold;")
        
        cancel_btn = QPushButton(_("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        
        btns.addStretch()
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)

    def get_data(self):
        return {
            "name": self.name_edit.text(),
            "description": self.desc_edit.toPlainText()
        }
