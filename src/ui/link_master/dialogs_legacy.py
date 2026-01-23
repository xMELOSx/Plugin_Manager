""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を介すること。
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QHBoxLayout, QGridLayout, QFileDialog, QComboBox, QFormLayout, 
                             QGroupBox, QCheckBox, QWidget, QListWidget, QListWidgetItem,
                             QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
                             QTextEdit, QApplication, QMessageBox, QMenu, QSpinBox, QStyle,
                              QRadioButton, QButtonGroup, QFrame, QSplitter)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QRect, QPoint, QRectF, QTimer, QEvent
from PyQt6.QtGui import QMouseEvent, QAction, QIcon, QPainter, QPen, QColor, QPixmap, QPainterPath
from src.ui.flow_layout import FlowLayout
from src.ui.link_master.dialogs.library_usage_dialog import LibraryUsageDialog
from src.ui.link_master.compact_dial import CompactDial
from src.core.link_master.utils import format_size
from src.ui.slide_button import SlideButton
from src.core.lang_manager import _
from src.ui.window_mixins import OptionsMixin
from src.ui.common_widgets import ProtectedLineEdit, ProtectedTextEdit, StyledComboBox, StyledSpinBox, StyledButton
from src.core.file_handler import FileHandler
import os
import subprocess
import shutil
from src.utils.path_utils import get_user_data_path, ensure_dir
from src.ui.link_master.dialogs.executables_manager import ExecutablesManagerDialog
from src.ui.link_master.dialogs.library_dialogs import LibraryDependencyDialog, LibraryRegistrationDialog
from src.ui.link_master.dialogs.url_list_dialog import URLListDialog
from src.ui.link_master.dialogs.preview_dialogs import PreviewItemWidget, PreviewTableDialog, FullPreviewDialog

from src.ui.styles import apply_common_dialog_style
from src.ui.frameless_window import FramelessDialog
from src.ui.toast import Toast
from src.ui.link_master.tag_chip_input import TagChipInput

class TagIconLineEdit(ProtectedLineEdit):
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


class AppRegistrationDialog(FramelessDialog):
    def __init__(self, parent=None, app_data=None):
        super().__init__(parent)
        self.app_data = app_data
        self.pending_cover_pixmap = None  # For clipboard paste
        self.executables = []  # List of {name, path, args}
        
        mode = _("Edit") if app_data else _("Register New")
        self.setWindowTitle(_("{mode} Application").format(mode=mode))
        self.setMinimumSize(500, 550)
        self.set_default_icon()
        
        self._init_ui()
        if self.app_data:
            self._fill_data()
        
    def _init_ui(self):
        from PyQt6.QtWidgets import QScrollArea
        
        # Main layout is managed by FramelessDialog
        # dialog_layout = QVBoxLayout(self) # Removed redundant layout creation
        # dialog_layout.setContentsMargins(0, 0, 0, 0)
        
        # Scroll Area Setup
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        
        content_widget = QWidget()
        content_widget.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 10)
        content_layout.setSpacing(15)
        
        form = QFormLayout()
        form.setSpacing(12)
        
        # Name
        self.name_edit = ProtectedLineEdit()
        self.name_edit.setPlaceholderText(_("e.g. Minecraft"))
        form.addRow(_("App Name:"), self.name_edit)
        
        # Storage Root
        self.storage_edit = ProtectedLineEdit()
        self.storage_btn = QPushButton(_(" Browse "))
        self.storage_btn.clicked.connect(self._browse_storage)
        storage_layout = QHBoxLayout()
        storage_layout.addWidget(self.storage_edit)
        storage_layout.addWidget(self.storage_btn)
        form.addRow(_("Storage Path:"), storage_layout)
        
        # Helper to create target row with rule combo
        def create_target_row(label, edit_attr, btn_attr, rule_combo_attr, browse_slot, default_rule='folder'):
            layout = QHBoxLayout()
            edit = ProtectedLineEdit()
            setattr(self, edit_attr, edit)
            btn = QPushButton(_(" Browse "))
            setattr(self, btn_attr, btn)
            btn.clicked.connect(browse_slot)
            
            rule_combo = StyledComboBox()
            rule_combo.addItem(_("Folder"), "folder")
            rule_combo.addItem(_("Flat"), "files")
            rule_combo.addItem(_("Tree"), "tree")
            setattr(self, rule_combo_attr, rule_combo)
            rule_combo.setFixedWidth(120)
            
            layout.addWidget(edit)
            layout.addWidget(btn)
            layout.addWidget(QLabel(_("Rule:")))
            layout.addWidget(rule_combo)
            form.addRow(label, layout)

        # Target Configs
        create_target_row(_("Primary"), "target_edit", "target_btn", "deploy_rule_combo", self._browse_target)
        create_target_row(_("Secondary (Optional)"), "target_edit_2", "target_btn_2", "deploy_rule_combo_b", self._browse_target_2)
        create_target_row(_("Tertiary (Optional)"), "target_edit_3", "target_btn_3", "deploy_rule_combo_c", self._browse_target_3)

        # Default Folder Property Settings Group (Misc)
        defaults_group = QGroupBox(_("Other Default Settings"))
        defaults_form = QFormLayout()
        defaults_form.setSpacing(10)
        
        # Tree Skip
        self.default_skip_levels_spin = StyledSpinBox()
        self.default_skip_levels_spin.setRange(0, 5)
        self.default_skip_levels_spin.setSuffix(_(" levels"))
        defaults_form.addRow(_("Tree Skip:"), self.default_skip_levels_spin)

        # Transfer Mode
        self.transfer_mode_combo = StyledComboBox()
        self.transfer_mode_combo.addItem(_("Symbolic Link (recommended)"), "symlink")
        self.transfer_mode_combo.addItem(_("Physical Copy (slower)"), "copy")
        defaults_form.addRow(_("Transfer Mode:"), self.transfer_mode_combo)

        # Conflict Policy
        self.conflict_combo = StyledComboBox()
        for p, label in [("backup", _("Backup")), ("skip", _("Skip")), ("overwrite", _("Overwrite"))]:
            self.conflict_combo.addItem(label, p)
        defaults_form.addRow(_("Conflict Policy:"), self.conflict_combo)

        # Style Settings
        self.cat_style_combo = StyledComboBox()
        # Phase 33: "Global Default" removed from App Settings as it creates a null reference for children.
        # App Settings must define the concrete default for the hierarchy.
        for s, label in [("image", _("Image")), ("text", _("Text")), ("image_text", _("Image + Text"))]:
            self.cat_style_combo.addItem(label, s)
        defaults_form.addRow(_("Category Style:"), self.cat_style_combo)

        self.pkg_style_combo = StyledComboBox()
        # "Global Default" removed here too.
        for s, label in [("image", _("Image")), ("text", _("Text")), ("image_text", _("Image + Text"))]:
            self.pkg_style_combo.addItem(label, s)
        defaults_form.addRow(_("Package Style:"), self.pkg_style_combo)
        
        defaults_group.setLayout(defaults_form)
        form.addRow(defaults_group)

        # Cover Image
        self.cover_edit = ProtectedLineEdit()
        self.cover_edit.setPlaceholderText(_("Optional: Select cover image for app"))
        self.cover_btn = QPushButton(_(" Browse "))
        self.cover_btn.clicked.connect(self._browse_cover)
        self.cover_crop_btn = QPushButton(_("✂ Edit Region"))
        self.cover_crop_btn.clicked.connect(self._crop_cover)
        self.cover_crop_btn.setToolTip(_("Select custom region from image"))
        self.cover_paste_btn = QPushButton(_("📋 Paste"))
        self.cover_paste_btn.clicked.connect(self._paste_cover_from_clipboard)
        self.cover_paste_btn.setToolTip(_("Paste image from clipboard"))
        
        cover_layout = QHBoxLayout()
        cover_layout.addWidget(self.cover_edit)
        cover_layout.addWidget(self.cover_btn)
        cover_layout.addWidget(self.cover_paste_btn)
        cover_layout.addWidget(self.cover_crop_btn)
        form.addRow(_("Cover Image:"), cover_layout)
        
        # Favorite & Score
        fav_score_layout = QHBoxLayout()
        self.favorite_btn = QPushButton(_("☆Favorite"))
        self.favorite_btn.setCheckable(True)
        self.favorite_btn.setFixedWidth(120)
        self.favorite_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.favorite_btn.setStyleSheet("""
            QPushButton { 
                background-color: transparent; color: #ccc; border: 1px solid #555; border-radius: 4px; padding: 4px 8px; min-width: 80px;
            }
            QPushButton:hover { background-color: #444; }
            QPushButton:checked { color: #f1c40f; font-weight: bold; border-color: #f1c40f; }
        """)
        self.favorite_btn.toggled.connect(lambda checked: self.favorite_btn.setText(_("★Favorite") if checked else _("☆Favorite")))
        
        score_label = QLabel(_("Score:"))
        self.score_dial = CompactDial(self, digits=3, show_arrows=True)
        
        fav_score_layout.addWidget(self.favorite_btn)
        fav_score_layout.addSpacing(15)
        fav_score_layout.addWidget(score_label)
        fav_score_layout.addWidget(self.score_dial)
        fav_score_layout.addStretch()
        form.addRow("", fav_score_layout)
        
        # Preview Label
        self.preview_label = ImageDropLabel(self)
        self.preview_label.setFixedSize(160, 120)
        self.preview_label.image_dropped.connect(self._on_preview_image_dropped)
        form.addRow(_("Preview:"), self.preview_label)

        # Managers
        def create_manager_row(label_text, btn_text, color, count_attr, slot):
            layout = QHBoxLayout()
            btn = QPushButton(btn_text)
            btn.clicked.connect(slot)
            btn.setStyleSheet(f"background-color: {color}; color: white; min-width: 150px;")
            count_lbl = QLabel("(0)")
            count_lbl.setStyleSheet("color: #888;")
            setattr(self, count_attr, count_lbl)
            layout.addWidget(btn)
            layout.addWidget(count_lbl)
            layout.addStretch()
            form.addRow(label_text, layout)

        create_manager_row(_("Executables:"), _("🚀 Manage Executables..."), "#d35400", "exe_count_label", self._open_executables_manager)
        create_manager_row(_("URLs:"), _("🌐 Manage URLs..."), "#2980b9", "url_count_label", self._open_url_manager)
        create_manager_row(_("Passwords:"), _("🔑 Manage Passwords..."), "#8e44ad", "pwd_count_label", self._open_password_manager)
        
        # Hidden password field
        self.password_list_json = self.app_data.get('password_list', '[]') if self.app_data else '[]'
        self.pwd_list_edit = ProtectedLineEdit()
        self.pwd_list_edit.setVisible(False)
        self.pwd_list_edit.setText(self.password_list_json)
        self._update_pwd_count()
        
        content_layout.addLayout(form)
        content_layout.addStretch()
        
        scroll.setWidget(content_widget)
        # Use FramelessDialog's helper to set content
        self.set_content_widget(scroll)
        # dialog_layout.addWidget(scroll) # Removed

        # Footer Actions (Static Bottom)
        footer_widget = QWidget()
        footer_widget.setStyleSheet("background-color: #2b2b2b; border-top: 1px solid #444;")
        btn_layout = QHBoxLayout(footer_widget)
        btn_layout.setContentsMargins(20, 10, 20, 10)
        
        if self.app_data:
            self.unregister_btn = QPushButton(_("Unregister App"))
            self.unregister_btn.clicked.connect(self._on_unregister_clicked)
            self.unregister_btn.setStyleSheet("background-color: #c0392b; color: white;")
            btn_layout.addWidget(self.unregister_btn)
            btn_layout.addSpacing(20)

        self.ok_btn = QPushButton(_("Save") if self.app_data else _("Register"))
        self.ok_btn.clicked.connect(self._on_save_clicked)
        self.ok_btn.setStyleSheet("background-color: #2980b9; font-weight: bold; min-width: 100px;")
        
        self.cancel_btn = QPushButton(_("Cancel"))
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        
        # Add to inherited content layout
        self.content_layout.addWidget(footer_widget)

    def _on_unregister_clicked(self):
        """Confirm and set flag for deletion."""
        from src.ui.common_widgets import FramelessMessageBox
        dlg = FramelessMessageBox(self)
        dlg.setWindowTitle(_("Confirm Unregister"))
        dlg.setText(_("Are you sure you want to completely remove this application registration?\n"
                      "This will NOT delete physical folders, but will delete all custom names, tags, and settings."))
        dlg.setIcon(FramelessMessageBox.Icon.Question)
        dlg.setStandardButtons(FramelessMessageBox.StandardButton.Yes | FramelessMessageBox.StandardButton.No)
        if dlg.exec() == FramelessMessageBox.StandardButton.Yes:
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
        
        # Style combos - use findData for correct matching
        cat_style = self.app_data.get('default_category_style', 'image')
        idx = self.cat_style_combo.findData(cat_style)
        if idx >= 0: self.cat_style_combo.setCurrentIndex(idx)
        
        pkg_style = self.app_data.get('default_package_style', 'image')
        idx = self.pkg_style_combo.findData(pkg_style)
        if idx >= 0: self.pkg_style_combo.setCurrentIndex(idx)
        
        # Conflict policy - use findData
        conflict = self.app_data.get('conflict_policy', 'backup')
        idx = self.conflict_combo.findData(conflict)
        if idx >= 0: self.conflict_combo.setCurrentIndex(idx)
        
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
            self.url_count_label.setText(_("({count} registered)").format(count=len(urls)))
        except:
            self.url_count_label.setText(_("(0 registered)"))

    def _open_url_manager(self):
        dialog = URLListDialog(self, url_list_json=getattr(self, 'url_list_json', '[]'), caller_id="app_registration")
        if dialog.exec():
            self.url_list_json = dialog.get_data()
            self._update_url_count()

    def _open_password_manager(self):
        from src.ui.link_master.dialogs.password_list_dialog import PasswordListDialog
        dialog = PasswordListDialog(self, password_list_json=self.password_list_json)
        if dialog.exec():
            self.password_list_json = dialog.get_data()
            self.pwd_list_edit.setText(self.password_list_json) # Sync hidden field
            self._update_pwd_count()

    def _update_pwd_count(self):
        try:
            import json
            pwds = json.loads(self.password_list_json)
            count = len(pwds)
            self.pwd_count_label.setText(f"({count})")
        except:
            self.pwd_count_label.setText("(0)")

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
        from src.ui.common_widgets import FramelessMessageBox
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
                msg = FramelessMessageBox(self)
                msg.setWindowTitle(_("Crop Image?"))
                msg.setText(_("Do you want to crop the pasted image?"))
                msg.setStandardButtons(FramelessMessageBox.StandardButton.Yes | FramelessMessageBox.StandardButton.No)
                msg.setIcon(FramelessMessageBox.Icon.Question)
                
                if msg.exec() == FramelessMessageBox.StandardButton.Yes:
                    self._crop_clipboard_cover()
        else:
            msg = FramelessMessageBox(self)
            msg.setWindowTitle(_("No Image"))
            msg.setText(_("No image found in clipboard."))
            msg.setIcon(FramelessMessageBox.Icon.Warning)
            msg.exec()

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
        import os
        from src.ui.common_widgets import FramelessMessageBox
        
        # Validate all fields
        errors = []
        
        # Required field checks
        if not self.name_edit.text().strip():
            errors.append(_("Application name is required."))

        storage_path = self.storage_edit.text().strip()
        if not storage_path:
            errors.append(_("Storage path is required."))
        elif not os.path.exists(storage_path):
            errors.append(_("Storage path does not exist:\n{path}").format(path=storage_path))
            
        target_path = self.target_edit.text().strip()
        if not target_path:
            errors.append(_("Primary target install path is required."))
        elif not os.path.exists(target_path):
            errors.append(_("Primary target path does not exist:\n{path}").format(path=target_path))
        
        # Optional target paths
        target_path_2 = self.target_edit_2.text().strip()
        if target_path_2 and not os.path.exists(target_path_2):
            errors.append(_("Secondary target path does not exist:\n{path}").format(path=target_path_2))
            
        target_path_3 = self.target_edit_3.text().strip()
        if target_path_3 and not os.path.exists(target_path_3):
            errors.append(_("Tertiary target path does not exist:\n{path}").format(path=target_path_3))
            
        if errors:
            msg = FramelessMessageBox(self)
            msg.setIcon(FramelessMessageBox.Icon.Warning)
            msg.setWindowTitle(_("Validation Error"))
            msg.setText("\n".join(errors))
            msg.exec()
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
            # Phase 63: Use APPDATA for app covers in EXE mode
            save_dir = get_user_data_path(os.path.join("resource", "app", "_covers"))
            ensure_dir(save_dir)
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
            "conflict_policy": self.conflict_combo.currentData(),
            "deployment_rule": self.deploy_rule_combo.currentData(),
            "deployment_rule_b": self.deploy_rule_combo_b.currentData(),
            "deployment_rule_c": self.deploy_rule_combo_c.currentData(),
            "transfer_mode": self.transfer_mode_combo.currentData(),
            "deployment_type": self.deploy_rule_combo.currentData(), # Backward compat
            "cover_image": cover_path if cover_path and cover_path not in [" [ Clipboard Image ] ", "[Cropped from Clipboard]"] else None,
            "is_favorite": 1 if self.favorite_btn.isChecked() else 0,
            "score": self.score_dial.value(),
            "default_category_style": self.cat_style_combo.currentData(),
            "default_package_style": self.pkg_style_combo.currentData(),
            "default_skip_levels": self.default_skip_levels_spin.value(),
            "executables": json.dumps(self.executables) if self.executables else "[]",
            "url_list": getattr(self, "url_list_json", "[]"),
            "password_list": getattr(self, "password_list_json", "[]")
        }

class FolderPropertiesDialog(FramelessDialog, OptionsMixin):
    """Dialog to configure folder-specific display properties."""
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
        
        self.set_default_icon()
        
        # Heuristic detection of folder type for Auto mode display
        self.detected_folder_type = 'category'  # Default
        if not self.batch_mode and self.folder_path and os.path.isdir(self.folder_path):
            self.detected_folder_type = self._detect_folder_type_internal(self.folder_path)


        # Sizing / Constraints - use saved size or reasonable default
        self.setMinimumWidth(480)
        self.setMinimumHeight(550)
        self.resize(560, 720)  # Default size matching typical usage
        
        # Improved folder name detection
        self.original_name = os.path.basename(folder_path.rstrip('\\/'))
        if not self.original_name:
            self.original_name = folder_path
            
        title = _("Batch Edit Properties") if batch_mode else _("Properties: {name}").format(name=self.original_name)
        self.setWindowTitle(title)

        # Auto-fill image_path from auto-detected thumbnail if empty (Phase 18.13)
        if not self.batch_mode and self.folder_path and not self.current_config.get('image_path'):
            auto_thumb = self._detect_auto_thumbnail()
            if auto_thumb:
                self.current_config['image_path'] = auto_thumb
        
        self.db = getattr(parent, 'db', None)
        
        # Phase 40: Target-Specific Deploy Rules State
        self.deploy_rules = {
            1: self.current_config.get('deploy_rule', 'inherit'),
            2: self.current_config.get('deploy_rule_b', 'inherit'),
            3: self.current_config.get('deploy_rule_c', 'inherit'),
            4: 'custom'
        }
        self.prev_target_data = 1 # Start with Primary
        
        self._init_ui()
        
        # Phase 32: Restore Size
        self.load_options("folder_properties")

    def reject(self):
        from src.ui.toast import Toast
        if self.parent():
             Toast.show_toast(self.parent(), _("Edit Cancelled"), preset="warning")
        super().reject()

    def closeEvent(self, event):
        """Save window geometry on close."""
        self.save_options("folder_properties")
        super().closeEvent(event)
        
    def done(self, r):
        """Overridden to ensure options are saved via accept/reject too."""
        self.save_options("folder_properties")
        super().done(r)
    
    def _detect_folder_type_internal(self, path):
        """Heuristic detection of folder type (package or category)."""
        if not path or not os.path.exists(path) or not os.path.isdir(path):
            return 'category'
        
        # 1. Manifest Check
        manifests = ["manifest.json", "plugin.json", "config.yml", "__init__.py", "package.json"]
        for m in manifests:
            if os.path.exists(os.path.join(path, m)):
                return 'package'
        
        # 2. Naming Convention
        pkg_exts = (".pkg", ".bundle", ".plugin", ".addon")
        if path.lower().endswith(pkg_exts):
            return 'package'
        
        # 3. Content Density - If it contains any files at top level, likely a package
        try:
            with os.scandir(path) as it:
                for entry in it:
                    if entry.is_file():
                        return 'package'
        except:
            pass
        
        return 'category'
    
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
        content_widget = QWidget()
        self.root_layout = QVBoxLayout(content_widget)
        
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
            btn_open_folder.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_open_folder.setStyleSheet("""
                QPushButton { border: 1px solid #555; border-radius: 3px; background-color: #444; min-width: 0px; }
                QPushButton:hover { background-color: #555; border-color: #777; }
                QPushButton:pressed { background-color: #333; }
            """) # Fix size override and add feedback
            btn_open_folder.setToolTip(_("Open actual folder"))
            btn_open_folder.clicked.connect(self._open_actual_folder)
            folder_row.addWidget(btn_open_folder)
            
            self.orig_edit = ProtectedLineEdit()
            self.orig_edit.setText(self.original_name)
            self.orig_edit.setReadOnly(True)
            self.orig_edit.setFrame(False) # Make it look like a label
            self.orig_edit.setStyleSheet("color: #888; font-style: italic; background: transparent;")
            folder_row.addWidget(self.orig_edit)
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
            
            self.size_edit = ProtectedLineEdit()
            self.size_edit.setText(size_text)
            self.size_edit.setReadOnly(True)
            self.size_edit.setFrame(False)
            self.size_edit.setStyleSheet("color: #aaa; font-size: 11px; background: transparent;")
            display_form.addRow(_("Package Size:"), self.size_edit)
        
        # Display Name (Alias)
        self.name_edit = ProtectedLineEdit()
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
        self.favorite_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.favorite_btn.setStyleSheet("""
            QPushButton { 
                background-color: #3b3b3b; color: #fff; border: 1px solid #555; border-radius: 4px; padding: 4px; 
            }
            QPushButton:hover { background-color: #4a4a4a; border-color: #3498db; }
            QPushButton:checked { background-color: #3d5a80; border-color: #3498db; color: #fff; }
            QPushButton:pressed { background-color: #2c3e50; }
        """)
        self.favorite_btn.toggled.connect(self._on_favorite_toggled_dialog)
        
        # Phase 26/58: Batch mode favorite toggle
        self.batch_favorite_toggle = None
        if self.batch_mode:
            self.favorite_btn.setEnabled(False) # Disabled by default in batch mode
            self.batch_favorite_toggle = SlideButton()
            self.batch_favorite_toggle.setChecked(False)
            self.batch_favorite_toggle.toggled.connect(self.favorite_btn.setEnabled)
            fav_layout.addWidget(self.batch_favorite_toggle)
            fav_layout.addSpacing(5)

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
        self.manage_previews_btn = StyledButton(_("📂 Manage Previews..."), style_type="Gray")
        self.manage_previews_btn.clicked.connect(self._open_multi_preview_browser)
        
        self.full_preview_edit = ProtectedLineEdit()
        self.full_preview_edit.setText(self.current_config.get('manual_preview_path', '') or '')
        display_form.addRow(_("Multi-Preview:"), self.manage_previews_btn)

        # Icon Path Widgets
        self.image_edit = ProtectedLineEdit()
        self.image_edit.setPlaceholderText(_("Path to icon image (200x200)"))
        self.image_edit.setText(self.current_config.get('image_path') or '')
        
        # utility buttons
        image_btn_h = QHBoxLayout()
        image_btn_h.setSpacing(5)
        
        self.image_btn = StyledButton(_(" Browse "), style_type="Gray")
        self.image_btn.clicked.connect(self._browse_image)
        
        self.paste_btn = StyledButton(_("📋 Paste"), style_type="Gray")
        self.paste_btn.clicked.connect(self._paste_from_clipboard)
        self.paste_btn.setToolTip(_("Paste image from clipboard"))
        
        self.crop_btn = StyledButton(_("✂ Edit Region"), style_type="Gray")
        self.crop_btn.clicked.connect(self._crop_image)
        
        self.clear_btn = StyledButton(_("Clear"), style_type="Red")
        self.clear_btn.clicked.connect(self._clear_image)
        
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
        
        self.description_edit = ProtectedTextEdit()
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

        self.author_edit = ProtectedLineEdit()
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
        self.url_btn = StyledButton(_("🌐 Manage URLs..."), style_type="Blue")
        self.url_btn.clicked.connect(self._open_url_manager)
        url_layout.addWidget(self.url_btn)
        
        # Hidden field to store structured JSON
        self.url_list_edit = ProtectedLineEdit()
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
        attr_group.setStyleSheet("""
            QGroupBox { color: #ddd; border: 1px solid #555; border-radius: 4px; margin-top: 10px; padding-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; }
        """)
        attr_form = QFormLayout(attr_group)
        
        # Folder Type
        self.type_combo = StyledComboBox()
        if self.batch_mode:
            self.type_combo.addItem(_("--- No Change ---"), "KEEP")
            # In batch mode, don't show detection result (could be mixed)
            self.type_combo.addItem(_("Auto (Detect)"), "auto")
        else:
            # Show detected type in Auto option for user clarity (single item only)
            detected_label = _("Category") if self.detected_folder_type == 'category' else _("Package")
            self.type_combo.addItem(_("Auto (→ {detected})").format(detected=detected_label), "auto")
        self.type_combo.addItem(_("Category"), "category")
        self.type_combo.addItem(_("Package"), "package")
        
        # Default to Auto - use explicit string check since 'auto' is the expected value
        current_type = self.current_config.get('folder_type') or 'auto'

        # Ensure Auto is selected when type is not set or explicitly 'auto'
        if current_type and current_type != 'auto':
            idx = self.type_combo.findData(current_type)
            if idx >= 0 and not self.batch_mode:
                self.type_combo.setCurrentIndex(idx)
        elif not self.batch_mode:
            # Select Auto (index 0 in non-batch mode)
            self.type_combo.setCurrentIndex(0)
        
        if self.batch_mode:
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
            
        self.style_combo.addItem(_("App Default ({default})").format(default=_(self.app_cat_style_default)), None)
        self.style_combo.addItem(_("Image Only"), "image")
        self.style_combo.addItem(_("Text Only"), "text")
        self.style_combo.addItem(_("Image + Text"), "image_text")
        
        current_style = self.current_config.get('display_style') # None = App Default

        # Ensure App Default is selected when style is not set
        if current_style is not None:
            idx = self.style_combo.findData(current_style)
            if idx >= 0 and not self.batch_mode:
                self.style_combo.setCurrentIndex(idx)
        elif not self.batch_mode:
            # Select App Default (index 0 in non-batch mode) - don't use findData(None) as Qt may not match None correctly
            self.style_combo.setCurrentIndex(0)
        
        if self.batch_mode:
            self.style_combo.setCurrentIndex(0)

        attr_form.addRow(_("Category Style:"), self.style_combo)
        
        # Package Display Style (separate from category)
        self.style_combo_pkg = StyledComboBox()
        if self.batch_mode:
            self.style_combo_pkg.addItem(_("--- No Change ---"), "KEEP")
            
        self.style_combo_pkg.addItem(_("App Default ({default})").format(default=_(self.app_pkg_style_default)), None)
        self.style_combo_pkg.addItem(_("Image Only"), "image")
        self.style_combo_pkg.addItem(_("Text Only"), "text")
        self.style_combo_pkg.addItem(_("Image + Text"), "image_text")
        
        current_style_pkg = self.current_config.get('display_style_package') # None = App Default

        # Ensure App Default is selected when style is not set
        if current_style_pkg is not None:
            idx_pkg = self.style_combo_pkg.findData(current_style_pkg)
            if idx_pkg >= 0 and not self.batch_mode:
                self.style_combo_pkg.setCurrentIndex(idx_pkg)
        elif not self.batch_mode:
            # Select App Default (index 0 in non-batch mode) - don't use findData(None) as Qt may not match None correctly
            self.style_combo_pkg.setCurrentIndex(0)
        
        if self.batch_mode:
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
        # Phase 61: Use ComboBox for visibility in Batch Mode to avoid confusion with double-toggles
        if self.batch_mode:
            self.hide_combo = StyledComboBox()
            self.hide_combo.addItem(_("--- No Change ---"), "KEEP")
            self.hide_combo.addItem(_("Visible (Show)"), 1)
            self.hide_combo.addItem(_("Hidden (Hide)"), 0)
            self.hide_combo.setCurrentIndex(0)
            attr_form.addRow(_("Visibility:"), self.hide_combo)
            self.hide_checkbox = None
        else:
            hide_container = QHBoxLayout()
            self.hide_checkbox = SlideButton()
            is_visible = self.current_config.get('is_visible', 1)
            self.hide_checkbox.setChecked(is_visible == 0)  # Checked = hidden
            
            hide_container.addWidget(self.hide_checkbox)
            hide_container.addStretch()
            attr_form.addRow(_("Hide from View:"), hide_container)
        
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
                if hasattr(curr, '_load_quick_tags'):
                    window = curr
                    break
                curr = curr.parent()
            
            if window:
                frequent_tags = window._load_quick_tags()
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
                    btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    
                    # Compact stable size: Icon size for symbols, fit-content for text
                    btn.setFixedHeight(24)
                    if mode in ['symbol', 'text_symbol'] and emoji:
                        btn.setFixedWidth(28)
                    else:
                        btn.setMinimumWidth(28)
                        btn.setMaximumWidth(80)
                    
                    # Style with consistent padding/font to prevent size changes on toggle
                    base_style = """
                        QPushButton { 
                            background-color: #3b3b3b; color: #fff; border: 1px solid #555; 
                            padding: 2px 4px; font-size: 10px; font-weight: normal;
                            border-radius: 3px; min-width: 0px;
                        }
                        QPushButton:hover { background-color: #4a4a4a; border-color: #777; }
                        QPushButton:checked { background-color: #3498db; color: #fff; border-color: #fff; }
                        QPushButton:pressed { background-color: #222; }
                    """
                    btn.setStyleSheet(base_style)
                    
                    # Add Icon if mode allows
                    show_icon = (mode == 'image' or mode == 'image_text' or mode == 'text')
                    if show_icon and t.get('icon') and os.path.exists(t.get('icon')):
                         btn.setIcon(QIcon(t.get('icon')))
                    elif mode not in ['symbol', 'text_symbol'] and t.get('icon') and os.path.exists(t.get('icon')):
                         btn.setIcon(QIcon(t.get('icon')))

                    current_tags = [p.strip().lower() for p in (self.current_config.get('tags', '') or '').split(',') if p.strip()]
                    if name.lower() in current_tags:
                        btn.setChecked(True)
                        
                    # Use toggled signal for reliable checked state tracking
                    btn.toggled.connect(lambda checked, n=name: self._on_tag_toggled(n, checked))
                    self.tag_buttons[name.lower()] = btn
                    self.tag_panel_layout.addWidget(btn)

        except: pass
        
        attr_form.addRow(_("Quick Tags:"), self.tag_panel)

        # Tags (comma-separated) (Bottom Position) - Only MANUAL tags shown here
        # Quick Tags are stored in buttons and merged at save time
        all_known_tags = []
        if hasattr(self, 'db'):
            all_known_tags = self.db.get_all_tags()
            
        quick_tag_names = {t.lower() for t in self.tag_buttons.keys()}
        
        ph = _("Additional custom tags (e.g. my_custom, special)")
        if self.batch_mode:
            ph = _("Leave empty to keep existing")
            
        self.tags_edit = TagChipInput(
            placeholder=ph,
            suggestions=all_known_tags,
            quick_tags=list(quick_tag_names)
        )
        
        # Filter out quick tags from the text area on load
        all_tags_str = self.current_config.get('tags', '') or ''
        all_tags = [t.strip() for t in all_tags_str.split(',') if t.strip()]
        manual_only = [t for t in all_tags if t.lower() not in quick_tag_names]
        self.tags_edit.set_tags(manual_only)
        
        # Tag Section Container (Tags + Inherit toggle below)
        tag_section_container = QWidget()
        tag_section_v = QVBoxLayout(tag_section_container)
        tag_section_v.setContentsMargins(0, 0, 0, 0)
        tag_section_v.setSpacing(4)
        tag_section_v.addWidget(self.tags_edit)
        
        # Inherit Tags Toggle (Phase 18.8) - NOW INSIDE tag section
        self.inherit_tags_chk = SlideButton()
        self.inherit_tags_chk.setChecked(bool(self.current_config.get('inherit_tags', 1)))
        self.inherit_tags_chk.setToolTip(_("Inherit Tags: If unchecked, parent tags will NOT be applied."))
        
        inherit_box = QHBoxLayout()
        inherit_box.setContentsMargins(2, 0, 0, 0)
        inherit_box.setSpacing(5)
        inherit_label = QLabel(_("Inherit:")) # PO translation handles "子パッケージに継承:"
        inherit_label.setStyleSheet("color: #aaa; font-size: 11px;")
        inherit_box.addWidget(inherit_label)
        inherit_box.addWidget(self.inherit_tags_chk)
        inherit_box.addStretch()
        tag_section_v.addLayout(inherit_box)
        
        attr_form.addRow(_("Additional Tags:"), tag_section_container)
        
        # No sync needed since Quick Tags are independent
        # self.tags_edit.textChanged.connect(self._sync_tag_buttons)

        layout.addWidget(attr_group)
        
        # Advanced Link Config (Merged into Folder Attributes or separate Group)
        adv_group = QGroupBox(_("Advanced Link Settings"))
        adv_group.setStyleSheet("QGroupBox { font-weight: bold; color: #3498db; border: 1px solid #555; margin-top: 10px; padding-top: 10px; }")
        adv_form = QFormLayout(adv_group)

        # Phase 33 & Refinement: Target Override using Dropdown
        # Phase 33 & Refinement: Target Override using Dropdown
        # REPLACED QGroupBox with simple horizontal layout (No blue border)
        target_container = QWidget()
        target_v_layout = QVBoxLayout(target_container)
        target_v_layout.setContentsMargins(0, 0, 0, 0)
        target_v_layout.setSpacing(0)
        
        target_row = QHBoxLayout()
        target_row.setContentsMargins(0, 0, 0, 0)
        target_row.setSpacing(5)
        target_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        target_v_layout.addLayout(target_row)

        self.target_combo = StyledComboBox()
        self.target_combo.setFixedWidth(240)
        if self.batch_mode:
            self.target_combo.addItem(_("--- No Change ---"), "KEEP")

        # Phase 40: Unified Target Labels
        labels = [_("Primary"), _("Secondary"), _("Tertiary")]
        for i, root_path in enumerate(self.target_roots):
            if root_path:
                self.target_combo.addItem(labels[i], i + 1)
                self.target_combo.setItemData(self.target_combo.count() - 1, root_path, Qt.ItemDataRole.ToolTipRole)
                
        # 3. Custom
        self.target_combo.addItem(_("Custom..."), 4)
        target_row.addWidget(self.target_combo)
        target_row.addStretch() # Push to left

        # [RE-MOVED] Manual Path Editor restored to "Right Below" the selection
        self.manual_path_container = QWidget()
        manual_v = QVBoxLayout(self.manual_path_container)
        manual_v.setContentsMargins(10, 5, 0, 5) # Indent a bit
        
        manual_edit_h = QHBoxLayout()
        self.target_override_edit = ProtectedLineEdit()
        self.target_override_edit.setPlaceholderText(_("Override path (Absolute)..."))
        self.target_override_edit.setText(self.current_config.get('target_override') or '')
        manual_edit_h.addWidget(self.target_override_edit)
        
        self.target_override_btn = StyledButton(_("Browse"), style_type="Gray")
        self.target_override_btn.setFixedWidth(70)
        self.target_override_btn.clicked.connect(self._browse_target_override)
        manual_edit_h.addWidget(self.target_override_btn)
        manual_v.addLayout(manual_edit_h)
        
        target_v_layout.addWidget(self.manual_path_container)
        
        # Initial Selection Logic (Standardized to Primary by default to avoid 'latesttarget' noise)
        # Initial Selection Logic
        # Priority: 1. target_selection (New), 2. target_override (Legacy inference)
        curr_selection = self.current_config.get('target_selection')
        curr_override = self.current_config.get('target_override')
        
        target_set = False
        if curr_selection:
            # New Logic: Map selection string to combo data
            sel_map = {'primary': 1, 'secondary': 2, 'tertiary': 3, 'custom': 4}
            val = sel_map.get(curr_selection)
            if val:
                idx = self.target_combo.findData(val)
                if idx >= 0:
                    self.target_combo.setCurrentIndex(idx)
                    target_set = True
                    
        if not target_set and curr_override:
            # Legacy Logic: Try to infer from path
            found = False
            for i, root_path in enumerate(self.target_roots):
                if root_path and os.path.normpath(curr_override) == os.path.normpath(root_path):
                    target_idx = self.target_combo.findData(i + 1)
                    if target_idx >= 0:
                        self.target_combo.setCurrentIndex(target_idx)
                        target_set = True
                        break
            if not target_set:
                custom_idx = self.target_combo.findData(4)
                if custom_idx >= 0:
                    self.target_combo.setCurrentIndex(custom_idx)
                    target_set = True

        if not target_set:
            # Default to Primary (or KEEP in batch mode)
            if self.batch_mode:
                idx = self.target_combo.findData("KEEP")
            else:
                idx = self.target_combo.findData(1)
            
            if idx >= 0: self.target_combo.setCurrentIndex(idx)
            else: self.target_combo.setCurrentIndex(0)
        
        # [CRITICAL] Defer signal connection to end of init to prevent loops during setup
        # self.target_combo.currentIndexChanged.connect(self._on_target_choice_changed)
        
        # Phase 40: Target-Specific Deploy Rules State (REVERTED to Simple Model)
        self.target_row = target_row # Keep for layout reference
        adv_form.addRow(_("Target Destination:"), target_container)

        # Phase 40 & Correction: In-place help layout
        deploy_rule_container = QWidget()
        deploy_rule_v_layout = QVBoxLayout(deploy_rule_container)
        deploy_rule_v_layout.setContentsMargins(0, 0, 0, 0)
        deploy_rule_v_layout.setSpacing(2)
        
        deploy_rule_row = QHBoxLayout()
        deploy_rule_row.setContentsMargins(0, 0, 0, 0)
        deploy_rule_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        deploy_rule_row.setSpacing(5)
        deploy_rule_v_layout.addLayout(deploy_rule_row)

        self.deploy_rule_override_combo = StyledComboBox()
        self.deploy_rule_override_combo.setFixedWidth(240) # Fix width to prevent "shaking" when text changes
        if self.batch_mode:
            self.deploy_rule_override_combo.addItem(_("--- No Change ---"), "KEEP")
        
        # Options
        self.deploy_rule_override_combo.addItem(_("Default"), "inherit")
        self.deploy_rule_override_combo.addItem(_("Folder"), "folder")
        self.deploy_rule_override_combo.addItem(_("Flat"), "files")
        self.deploy_rule_override_combo.addItem(_("Tree"), "tree")
        self.deploy_rule_override_combo.addItem(_("Custom"), "custom")
        
        # Initial Rule for current target
        if self.batch_mode:
            initial_rule = "KEEP"
        else:
            initial_rule = self.deploy_rules.get(self.prev_target_data, "inherit")
        
        idx = self.deploy_rule_override_combo.findData(initial_rule)
        if idx >= 0:
            self.deploy_rule_override_combo.setCurrentIndex(idx)
            
        deploy_rule_row.addWidget(self.deploy_rule_override_combo)
        
        # Help Button - Now toggles In-place label with checked visual
        self.rule_help_btn = QPushButton("?")
        self.rule_help_btn.setFixedSize(22, 22)
        self.rule_help_btn.setCheckable(True)
        self.rule_help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rule_help_btn.clicked.connect(self._toggle_deploy_help)
        self.rule_help_btn.setStyleSheet("""
            QPushButton { 
                background-color: #555; color: #fff; border-radius: 11px; font-weight: bold; font-size: 14px;
                min-width: 22px; max-width: 22px; min-height: 22px; max-height: 22px;
                padding: 0px; margin: 0px; border: none;
            }
            QPushButton:hover { background-color: #777; }
            QPushButton:checked { background-color: #3498db; }
        """)
        deploy_rule_row.addWidget(self.rule_help_btn)
        deploy_rule_row.addStretch()

        # [NEW] In-place Help Label
        self.deploy_help_panel = QLabel()
        self.deploy_help_panel.setWordWrap(True)
        self.deploy_help_panel.setStyleSheet("""
            background-color: #333; color: #aaa; border-left: 3px solid #555; 
            padding: 8px; margin: 5px 0 10px 0; border-radius: 4px;
        """)
        msg = _(
            "<b>[Default]</b>: Use app settings<br>"
            "<b>[Folder]</b>: Maintain folder structure<br>"
            "<b>[Flat]</b>: Ignore subfolders (flat file list)<br>"
            "<b>[Tree]</b>: Recursively replicate hierarchy<br>"
            "<b>[Custom]</b>: Apply JSON rules"
        )
        self.deploy_help_panel.setText(msg)
        self.deploy_help_panel.setVisible(False)
        deploy_rule_v_layout.addWidget(self.deploy_help_panel)
        
        adv_form.addRow(_("Deploy Rule:"), deploy_rule_container)
        
        # [CRITICAL] Defer initial update until the end of constructor to avoid signal loops
        
        # Skip Levels for TREE mode (Moved below Deploy Rule)
        self.skip_levels_spin = StyledSpinBox()
        self.skip_levels_spin.setRange(-1, 5) # -1 = Default
        self.skip_levels_spin.setSpecialValueText(_("Default ({val})").format(val=self.app_skip_levels_default))
        self.skip_levels_spin.setSuffix(_(" levels"))
        
        # Extract skip_levels from rules JSON if exists, otherwise Default (-1)
        rules_json = self.current_config.get('deployment_rules', '') or ''
        try:
            import json
            current_rules = json.loads(rules_json) if rules_json else {}
            # Use rules value, or fallback to -1 (Default)
            val = int(current_rules.get('skip_levels', -1))
            self.skip_levels_spin.setValue(val)
        except:
            self.skip_levels_spin.setValue(-1)
            
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
        self.transfer_mode_override_combo.addItem(_("App Default ({default})").format(default=_(app_default_mode)), None)
        self.transfer_mode_override_combo.addItem(_("Symbolic Link"), "symlink")
        self.transfer_mode_override_combo.addItem(_("Physical Copy"), "copy")
        
        curr_mode = self.current_config.get('transfer_mode')
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
            
        self.conflict_override_combo.addItem(_("App Default ({default})").format(default=_(self.app_conflict_default)), None)
        self.conflict_override_combo.addItem(_("Backup"), "backup")
        self.conflict_override_combo.addItem(_("Skip"), "skip")
        self.conflict_override_combo.addItem(_("Overwrite"), "overwrite")
        
        curr_conflict = self.current_config.get('conflict_policy')

        idx = self.conflict_override_combo.findData(curr_conflict)
        if idx >= 0 and not self.batch_mode:
            self.conflict_override_combo.setCurrentIndex(idx)
        elif self.batch_mode:
            self.conflict_override_combo.setCurrentIndex(0)
        adv_form.addRow(_("Conflict Policy:"), self.conflict_override_combo)

        # [NEW] Deployment Rules (JSON) with In-place Help
        json_container = QWidget()
        json_v_layout = QVBoxLayout(json_container)
        json_v_layout.setContentsMargins(0, 0, 0, 0)
        json_v_layout.setSpacing(2)
        
        json_label_row = QHBoxLayout()
        json_label_row.setSpacing(5)
        json_label_row.addWidget(QLabel(_("Deployment Rules (JSON):")))
        
        self.json_help_btn = QPushButton("?")
        self.json_help_btn.setFixedSize(22, 22)
        self.json_help_btn.setCheckable(True)
        self.json_help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.json_help_btn.clicked.connect(self._toggle_json_help)
        self.json_help_btn.setStyleSheet("""
            QPushButton { 
                background-color: #555; color: #fff; border-radius: 11px; font-weight: bold; font-size: 14px;
                min-width: 22px; max-width: 22px; min-height: 22px; max-height: 22px;
                padding: 0px; margin: 0px; border: none;
            }
            QPushButton:hover { background-color: #777; }
            QPushButton:checked { background-color: #3498db; }
        """)
        json_label_row.addWidget(self.json_help_btn)
        json_label_row.addStretch()
        json_v_layout.addLayout(json_label_row)

        # [NEW] In-place JSON Help - Selectable for copying with IBeam cursor
        self.json_help_panel = QLabel()
        self.json_help_panel.setWordWrap(True)
        self.json_help_panel.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.json_help_panel.setCursor(Qt.CursorShape.IBeamCursor)
        self.json_help_panel.setStyleSheet("""
            background-color: #333; color: #aaa; border-left: 3px solid #3498db; 
            padding: 8px; margin: 3px 0 10px 0; border-radius: 4px; font-size: 11px;
        """)
        json_msg = _(
            "<b>JSON Example:</b><br>"
            "<code>{\"exclude\": [\"*.txt\"], \"rename\": {\"a\": \"b\"}}</code><br><br>"
            "• <b>exclude</b>: List of glob patterns to exclude<br>"
            "• <b>rename</b>: Map for internal file renaming"
        )
        self.json_help_panel.setText(json_msg)
        self.json_help_panel.setVisible(False)
        json_v_layout.addWidget(self.json_help_panel)

        self.rules_edit = ProtectedTextEdit()
        self.rules_edit.setPlaceholderText('{"exclude": ["*.txt"], "rename": {"old": "new"}}')
        self.rules_edit.setMinimumHeight(100)
        self.rules_edit.setText(self.current_config.get('deployment_rules', '') or '')
        self.rules_edit.setStyleSheet("""
            QTextEdit { background-color: #3b3b3b; color: #ffffff; border: 1px solid #555; padding: 4px; border-radius: 4px; }
            QTextEdit:disabled { background-color: #222; color: #666; }
        """)
        json_v_layout.addWidget(self.rules_edit)
        adv_form.addRow(json_container)


        # Phase 3.7: Shortcut to File Management (Now AFTER Rules) - Full width
        if not self.batch_mode:
            self.manage_redirection_btn = StyledButton(_("Edit Individual Redirections..."), style_type="Gray")
            self.manage_redirection_btn.clicked.connect(self._open_file_management_shortcut)
            adv_form.addRow("", self.manage_redirection_btn)  # Empty label for full width
            
        # Phase 28: Conflict Tag Detection (Available in batch mode)
        # Revert Scope Selection to the RIGHT side as requested, aligned with text box
        self.conflict_scope_combo = StyledComboBox()
        self.conflict_scope_combo.setFixedWidth(80)
        if self.batch_mode:
            self.conflict_scope_combo.addItem(_("KEEP"), "KEEP")
        self.conflict_scope_combo.addItem(_("Off"), "disabled")
        self.conflict_scope_combo.addItem(_("Cat"), "category")
        self.conflict_scope_combo.addItem(_("Global"), "global")
        
        current_scope = self.current_config.get('conflict_scope', 'disabled')
        if self.batch_mode:
            self.conflict_scope_combo.setCurrentIndex(0)
        else:
            scope_idx = self.conflict_scope_combo.findData(current_scope)
            if scope_idx >= 0:
                self.conflict_scope_combo.setCurrentIndex(scope_idx)

        # Tag input field
        ph_ct = _("Tag to search...")
        if self.batch_mode:
            ph_ct = _("Leave empty to keep existing")

        self.conflict_tag_edit = TagChipInput(
            placeholder=ph_ct,
            suggestions=all_known_tags,
            quick_tags=list(quick_tag_names)
        )
        self.conflict_tag_edit.set_tags(self.current_config.get('conflict_tag', '') or '')
        
        # ADD SCOPE COMBO AS EXTENSION to the line_edit row
        scope_h = QHBoxLayout()
        scope_h.setContentsMargins(0, 0, 0, 0)
        scope_h.setSpacing(4)
        scope_label = QLabel(_("Scope:"))
        scope_label.setStyleSheet("color: #aaa; font-size: 11px;")
        scope_h.addWidget(scope_label)
        scope_h.addWidget(self.conflict_scope_combo)
        
        scope_container = QWidget()
        scope_container.setLayout(scope_h)
        self.conflict_tag_edit.add_input_extension(scope_container)
        
        adv_form.addRow(_("Conflict Tag:"), self.conflict_tag_edit)
        
        # Phase X/26: Library Usage Row (Available in batch mode)
        lib_row = QHBoxLayout()
        
        self.btn_lib_usage = StyledButton(_("📚 Library Settings"), style_type="Blue")
        self.btn_lib_usage.setFixedWidth(150)
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
        
        # Set content widget (moved outside batch_mode check to fix batch dialog display)
        self.set_content_widget(content_widget)
        
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
            
        # Actions - Add to Root Layout
        btn_layout = QHBoxLayout()
        self.ok_btn = QPushButton(_("Save (Alt + Enter)"))
        self.ok_btn.setObjectName("save_btn")
        # Removed setDefault(True) - Use Alt+Enter instead
        self.ok_btn.clicked.connect(self.accept)
        
        # Phase 28: Use Alt+Enter for save to prevent accidental submissions
        from PyQt6.QtGui import QKeySequence, QShortcut
        self.save_shortcut = QShortcut(QKeySequence("Alt+Return"), self)
        self.save_shortcut.activated.connect(self.accept)
        self.save_shortcut_win = QShortcut(QKeySequence("Alt+Enter"), self) # Support numpad
        self.save_shortcut_win.activated.connect(self.accept)
        
        # Button Styling & Layout (Unified)
        self.ok_btn.setStyleSheet("background-color: #2980b9; font-weight: bold;")
        self.ok_btn.setFixedWidth(160)
        
        self.cancel_btn = QPushButton(_("Cancel"))
        self.cancel_btn.setFixedWidth(160)
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.ok_btn)
        
        self.root_layout.addLayout(btn_layout)
        
        self.target_combo.currentIndexChanged.connect(self._on_target_choice_changed)
        self.deploy_rule_override_combo.currentIndexChanged.connect(self._on_deploy_rule_changed)
        
        # Initialize display values immediately
        self._on_target_choice_changed()
        
    def _on_target_choice_changed(self):
        """Handle target selection changes - update custom path visibility and deployment defaults."""
        # FIX: Removed automatic state caching/restoration as per user request.
        # The dropdown should NOT change automatically when switching targets.
        
        data = self.target_combo.currentData()
        
        # Show/hide custom path editor
        is_custom = (data == 4)
        if hasattr(self, 'manual_path_container'):
            self.manual_path_container.setVisible(is_custom)
            
        # [CRITICAL FIX] Ensure target_override field is sync'd when switching to Primary/Secondary/Tertiary
        if not is_custom and data in [1, 2, 3]:
            idx = data - 1
            if 0 <= idx < len(self.target_roots) and self.target_roots[idx]:
                self.target_override_edit.setText(os.path.normpath(self.target_roots[idx]))
            else:
                self.target_override_edit.clear()

        if hasattr(self, 'deploy_rule_override_combo'):
            # Determine effective target for inheritance display
            effective_target = data
            if data == 4 or data == "KEEP":
                 effective_target = 1
            
            # Re-fetch default rules (Simplified: no per-target caching)
            actual_default_rule = self.app_deploy_default
            if effective_target == 2:
                actual_default_rule = self.current_app_data.get('deployment_rule_b') or self.app_deploy_default
            elif effective_target == 3:
                actual_default_rule = self.current_app_data.get('deployment_rule_c') or self.app_deploy_default
            
            rule_display_map = {'folder': _('Folder'), 'files': _('Flat'), 'tree': _('Tree'), 'custom': _('Custom')}
            default_display = rule_display_map.get(actual_default_rule, str(actual_default_rule).capitalize())
            
            # Update the label for "Default" (inherit) option
            inherit_idx = self.deploy_rule_override_combo.findData("inherit")
            if inherit_idx >= 0:
                self.deploy_rule_override_combo.setItemText(inherit_idx, _("Default ({rule})").format(rule=default_display))
            
            # Enable JSON editor ONLY if current rule is custom
            # (Simplified logic, not stateful per target)
            current_rule = self.deploy_rule_override_combo.currentData()
            enable_json = (current_rule == 'custom')
            if hasattr(self, 'rules_edit'):
                self.rules_edit.setEnabled(enable_json)

            # Update tree skip visibility
            if hasattr(self, '_update_tree_skip_visibility'):
                self._update_tree_skip_visibility()

        # Force a repaint for help buttons
        if hasattr(self, 'rule_help_btn'):
            self.rule_help_btn.raise_()

    def _on_deploy_rule_changed(self):
        """Update JSON editor enablement and update cache for current target."""
        if hasattr(self, 'deploy_rule_override_combo'):
            rule = self.deploy_rule_override_combo.currentData()
            data = self.target_combo.currentData()
            is_custom_target = (data == 4)
            enable_json = (is_custom_target or rule == 'custom')
            if hasattr(self, 'rules_edit'):
                self.rules_edit.setEnabled(enable_json)
            
            # Update cache for current target
            if hasattr(self, 'prev_target_data'):
                self.deploy_rules[self.prev_target_data] = rule

    def _get_selected_target_path(self):
        """Helper to get current effective target path."""
        data = self.target_combo.currentData()
        if data == 4:
            return self.target_override_edit.text()
        elif data == "KEEP":
             return "KEEP"
        
        # Primary, Secondary, Tertiary
        idx_val = 0
        try:
            idx_val = int(data) - 1
        except: return None

        if 0 <= idx_val < len(self.target_roots):
            return self.target_roots[idx_val]
        return None

    def _toggle_deploy_help(self):
        """Toggle in-place deployment rule guide."""
        if hasattr(self, 'deploy_help_panel'):
            self.deploy_help_panel.setVisible(not self.deploy_help_panel.isVisible())

    def _toggle_json_help(self):
        """Toggle in-place JSON rules guide."""
        if hasattr(self, 'json_help_panel'):
            self.json_help_panel.setVisible(not self.json_help_panel.isVisible())

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
                msg = FramelessMessageBox(self)
                msg.setWindowTitle(_("Crop Image?"))
                msg.setText(_("Do you want to crop the pasted image?"))
                msg.setStandardButtons(FramelessMessageBox.StandardButton.Yes | FramelessMessageBox.StandardButton.No)
                msg.setIcon(FramelessMessageBox.Icon.Question)
                
                if msg.exec() == FramelessMessageBox.StandardButton.Yes:
                    self._crop_image()
        else:
            msg = FramelessMessageBox(self)
            msg.setWindowTitle(_("No Image"))
            msg.setText(_("No image found in clipboard."))
            msg.setIcon(FramelessMessageBox.Icon.Warning)
            msg.exec()

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
                msg = FramelessMessageBox(self)
                msg.setIcon(FramelessMessageBox.Icon.Warning)
                msg.setWindowTitle(_("Error"))
                msg.setText(_("Failed to save clipboard image."))
                msg.exec()
                return

        super().accept()

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
                
                # Phase 5: Pass the current rule in the property dialog to the file management dialog
                # We need to make sure _open_file_management can handle an optional override rule
                current_rule = self.deploy_rule_override_combo.currentData()
                if current_rule == "inherit":
                    # Determine app default
                    current_target = self.target_combo.currentData()
                    if current_target == 2:
                        current_rule = self.current_app_data.get('deployment_rule_b') or self.app_deploy_default
                    elif current_target == 3:
                        current_rule = self.current_app_data.get('deployment_rule_c') or self.app_deploy_default
                    else:
                        current_rule = self.app_deploy_default
                
                # Check if window._open_file_management supports the override
                import inspect
                sig = inspect.signature(window._open_file_management)
                if 'override_rule' in sig.parameters:
                    window._open_file_management(rel, override_rule=current_rule)
                else:
                    window._open_file_management(rel)
                
                # [CRITICAL] Since _open_file_management in lm_file_management is non-modal (show()),
                # we need to connect to its finished signal to refresh OUR rules_edit.
                if hasattr(window, '_current_file_mgmt_dialog') and window._current_file_mgmt_dialog:
                    def on_mgmt_finished():
                        # Refresh rules in the current dialog's edit box
                        if window.db:
                            config = window.db.get_folder_config(rel) or {}
                            new_rules = config.get('deployment_rules', '')
                            self.rules_edit.setText(new_rules)
                    window._current_file_mgmt_dialog.finished.connect(on_mgmt_finished)
                    
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
        """Show/Hide Tree Skip Levels based on Deploy Rule. Also handles Transfer Mode state."""
        from PyQt6 import sip
        # Guard against accessing deleted widgets
        if sip.isdeleted(self) or not hasattr(self, 'deploy_rule_override_combo') or sip.isdeleted(self.deploy_rule_override_combo):
            return
        rule = self.deploy_rule_override_combo.currentData()
        is_tree = rule == "tree"
        self.skip_levels_spin.setVisible(is_tree)
        self.skip_levels_label.setVisible(is_tree)
        
        # New Logic: Disable Transfer Mode for 'custom' rule
        is_custom = rule == "custom"
        # If custom, we disable the manual transfer mode override because the JSON rules should dictate it (mixed mode)
        self.transfer_mode_override_combo.setEnabled(not is_custom)
        if is_custom:
            from src.core.lang_manager import _ # Ensure localization
            self.transfer_mode_override_combo.setToolTip(_("Transfer mode is determined by JSON rules in Custom mode."))
        else:
             self.transfer_mode_override_combo.setToolTip("")

    def _browse_target_override(self):
        """Browse for a custom target destination path."""
        from PyQt6.QtWidgets import QFileDialog
        path = QFileDialog.getExistingDirectory(self, _("Select Target Destination Override"))
        if path:
            self.target_override_edit.setText(os.path.normpath(path))

        if path:
            self.target_override_edit.setText(os.path.normpath(path))

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
        
        # Phase 63: Use APPDATA for icon cache in EXE mode
        cache_dir = get_user_data_path(os.path.join("resource", "app", self.app_name, ".icon_cache"))
        ensure_dir(cache_dir)
        
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
        
        # Phase 63: Use APPDATA for icon cache in EXE mode
        cache_dir = get_user_data_path(os.path.join("resource", "app", self.app_name, ".icon_cache"))
        ensure_dir(cache_dir)
        
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
        """Internal button state updated."""
        pass


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
                            marked_url=self.current_config.get('marked_url'), caller_id="folder_properties")
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
        manual_tags = self.tags_edit.get_tags()
        quick_tags = [name for name, btn in self.tag_buttons.items() if btn.isChecked()]
        all_tags = sorted(list(set([t.lower() for t in quick_tags] + [t.lower() for t in manual_tags])))
        
        # Phase 26: Batch mode display name logic
        display_name = self.name_edit.text().strip() or None
        if self.batch_mode:
            if getattr(self, 'batch_clear_name_toggle', None) and not self.batch_clear_name_toggle.isChecked():
                display_name = "KEEP" # No change if toggle is OFF
            elif not display_name:
                display_name = "" # Explicitly clear if toggle is ON and field is empty
        # Non-batch mode: if empty, it's already None due to 'or None' above.
        # This will trigger ItemCard.update_data's fallback to sanitized folder name.
        
        # Phase 40: Target-Specific Rule Switching (Restored logic)
        # Update current selected target's rule in cache before collecting everything
        current_rule = self.deploy_rule_override_combo.currentData()
        current_target = self.target_combo.currentData()
        if hasattr(self, 'prev_target_data') and self.prev_target_data is not None:
             self.deploy_rules[self.prev_target_data] = current_rule
        
        # Phase 42: Separate Target Selection from Physical Path
        current_target_code = self.target_combo.currentData()
        target_selection = None
        target_override = None
        
        if current_target_code == 4: # Custom
            target_selection = 'custom'
            target_override = self.target_override_edit.text().strip() or None
        elif current_target_code == "KEEP":
            target_selection = "KEEP"
            target_override = "KEEP"
        elif current_target_code == 1:
            target_selection = 'primary'
            target_override = None # Clear override logic to enforce dynamic lookups
        elif current_target_code == 2:
            target_selection = 'secondary'
            target_override = None
        elif current_target_code == 3:
            target_selection = 'tertiary'
            target_override = None


        data = {
            'display_name': display_name,
            'description': self.description_edit.toPlainText().strip() or None,
            'image_path': final_image_path.strip() or None, 
            'manual_preview_path': self.full_preview_edit.text().strip() or None,
            'author': self.author_edit.text().strip() or None,
            'url_list': self.url_list_edit.text() if self.url_list_edit.text() != '[]' else None,
            'is_favorite': (1 if self.favorite_btn.isChecked() else 0) if not self.batch_mode or (self.batch_favorite_toggle and self.batch_favorite_toggle.isChecked()) else "KEEP",
            'score': self.score_dial.value() if not self.batch_mode or (getattr(self, 'batch_update_score_toggle', None) and self.batch_update_score_toggle.isChecked()) else "KEEP",
            'folder_type': self.type_combo.currentData(),
            'display_style': self.style_combo.currentData(),
            'display_style_package': self.style_combo_pkg.currentData(),
            'tags': ", ".join(all_tags) if all_tags else None,
            'is_visible': self.hide_combo.currentData() if self.batch_mode else (0 if self.hide_checkbox.isChecked() else 1),
            
            # Use cached values for all targets
            # Phase 42 Fix: Do NOT save per-target rules automatically to prevent unintended overwrites
            # Only saving the Primary rule which is standard.
            'deploy_rule': self.deploy_rules.get(1, 'KEEP' if self.batch_mode else 'inherit'),
            
            # REMOVED: Saving deploy_rule_b/c. User must edit DB manually for these or use a dedicated tool
            # to avoid switching targets in dialog accidentally saving "inherit" over custom rules.
            # 'deploy_rule_b': ...,
            # 'deploy_rule_c': ...,
            
            'transfer_mode': self.transfer_mode_override_combo.currentData(),
            'conflict_policy': self.conflict_override_combo.currentData(),
            'inherit_tags': 1 if self.inherit_tags_chk.isChecked() else 0,
            'target_selection': target_selection,
            'target_override': target_override, 
            'conflict_tag': ", ".join(self.conflict_tag_edit.get_tags()) if self.conflict_tag_edit.get_tags() else (None if not self.batch_mode else "KEEP"),
            'conflict_scope': self.conflict_scope_combo.currentData(),
            'lib_deps': self.lib_deps if not self.batch_mode else (self.lib_deps if self.lib_deps != self.current_config.get('lib_deps', '[]') else "KEEP"),
        }
        
        # Keep legacy deploy_type if it exists and we're not explicitly supplanting it?
        # Actually, it's safer to just NOT include it in the update dict to prevent clearing fallback data.
        if 'deploy_type' in self.current_config:
            data['deploy_type'] = self.current_config['deploy_type']
        
        # Inject skip_levels into rules JSON
        skip_val = self.skip_levels_spin.value()
        rules_str = self.rules_edit.toPlainText().strip()
        if skip_val >= 0 or rules_str:
            try:
                import json
                rules_obj = json.loads(rules_str) if rules_str else {}
                if skip_val >= 0:
                    rules_obj['skip_levels'] = skip_val
                elif skip_val == -1 and 'skip_levels' in rules_obj:
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
                    'description', 'author', 'url_list', 'conflict_tag', 'target_override',
                    'display_style', 'display_style_package'
                ]: 
                    continue 
                
                clean_data[k] = v
            return clean_data
            
        return data

from src.ui.frameless_window import FramelessDialog

class TagManagerDialog(FramelessDialog):
    def __init__(self, parent=None, db=None, registry=None):
        super().__init__(parent)
        # FramelessDialog handles its own background styling
        
        # Fallback: Try to get db from parent if not provided
        if db is None and parent and hasattr(parent, 'db'):
            db = parent.db
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
        import logging; logging.info(f"[TagManagerDialog] __init__: db={db is not None}, registry={registry is not None}")
        self.setWindowTitle(_("Manage Quick Tags"))
        self.resize(500, 400)
        self.tags = [] 
        self.current_tag_ref = None  # Reference to currently-selected tag's data object
        self._dirty = False 
        self._loading = False
        self._is_dragging = False  # Flag to track D&D operations for sync logic
        
        # FramelessDialog setup
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
        from PyQt6.QtWidgets import (QTableWidget, QTableWidgetItem, QAbstractItemView, QLabel, 
                                     QVBoxLayout, QHBoxLayout, QWidget, QHeaderView, QFormLayout, 
                                     QLineEdit, QComboBox, QCheckBox, QPushButton, QListView)
        from PyQt6.QtGui import QIcon, QColor, QPixmap
        from PyQt6.QtCore import Qt, QRect
        
        content_widget = QWidget()
        main_layout = QVBoxLayout(content_widget)
        main_layout.setContentsMargins(10, 5, 10, 10) # Reduced top margin
        main_layout.setSpacing(5)
        
        # Explicit Title Bar Styling via container styling to prevent white bleed
        self.title_bar.setStyleSheet("background-color: #2b2b2b; border-bottom: 1px solid #3d3d3d;")
        self.title_label.setStyleSheet("color: #ffffff; background-color: transparent; font-weight: bold; padding-left: 5px;")
        self.set_default_icon()
        
        # Consistent Button/Input styles for this dialog (Local to container)
        content_widget.setStyleSheet("""
            QLineEdit, QComboBox { background-color: #1e1e1e; color: #eee; border: 1px solid #444; border-radius: 4px; padding: 4px; }
            QPushButton { background-color: #3b3b3b; color: white; border-radius: 4px; padding: 6px; }
            QPushButton:hover { background-color: #4a4a4a; }
            QPushButton:pressed { background-color: #222222; margin-top: 1px; margin-left: 1px; }
            QLabel { color: #ddd; }
        """)
        
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter)
        
        # Left: Table
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        hint_label = QLabel(_("💡 Drag items to reorder"))
        hint_label.setStyleSheet("color: #888; font-style: italic;")
        left_layout.addWidget(hint_label)
        
        self.tag_table = QTableWidget()
        self.tag_table.setFrameShape(QFrame.Shape.NoFrame if hasattr(QFrame, "Shape") else QFrame.NoFrame)
        self.tag_table.setColumnCount(5)
        self.tag_table.setHorizontalHeaderLabels([
            _("Icon"), _("Sym"), _("Tag Name"), _("Inherit"), _("Display")
        ])
        
        self.tag_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tag_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tag_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        # Standard Header Style (Premium Frameless look)
        hh = self.tag_table.horizontalHeader()
        hh.setVisible(True)
        hh.setStretchLastSection(False) # Turn off last-stretch to manually stretch column 2
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch) # Tag Name stretches
        hh.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        
        vh = self.tag_table.verticalHeader()
        vh.setVisible(False)
        vh.setDefaultSectionSize(26) # Consistent 26px height
        
        self.tag_table.setCornerButtonEnabled(False)
        self.tag_table.setShowGrid(False) # Clean look
        # Refined style: brighter selection, no dotted outline, consistent grid, dark header
        self.tag_table.setStyleSheet("""
            QTableWidget { 
                gridline-color: #3d3d3d; 
                border: 1px solid #3d3d3d; 
                outline: none; 
                background-color: #1e1e1e;
                color: #eeeeee;
                padding-left: 0px;
                margin-left: 0px;
            }
            QHeaderView::section {
                background-color: #333;
                color: #ffffff;
                padding: 0px;
                border: none;
                border-right: 1px solid #444;
                border-bottom: 1px solid #444;
                font-weight: bold;
            }
            QTableWidget::item:selected { 
                background-color: #3498db; 
                color: white; 
            }
            QTableWidget::item:focus {
                background-color: #3498db;
            }
        """)
        
        # Column resizing still works on hidden header
        self.tag_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tag_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tag_table.setColumnWidth(0, 40)  # Icon
        self.tag_table.setColumnWidth(1, 60)  # Symbol
        self.tag_table.setColumnWidth(3, 60)  # Inherit
        # Display (表示) will stretch or be minimal
        
        # Drag and Drop settings
        self.tag_table.itemClicked.connect(self._on_table_clicked)
        self.tag_table.setDragEnabled(True)
        self.tag_table.setAcceptDrops(True)
        self.tag_table.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.tag_table.setDragDropOverwriteMode(False)
        self.tag_table.setDropIndicatorShown(True)
        self.tag_table.setDefaultDropAction(Qt.DropAction.MoveAction)
        
        # Sync tags after manual reorder - Signal is good, but EventFilter is MORE certain for drops
        self.tag_table.model().rowsMoved.connect(self._on_rows_moved)
        self.tag_table.viewport().installEventFilter(self)
        
        left_layout.addWidget(self.tag_table)
        self.splitter.addWidget(left_panel)
        
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
        edit_layout.setContentsMargins(5, 5, 5, 5)
        edit_layout.setSpacing(5)
        
        form = QFormLayout()
        form.setSpacing(6)
        
        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self._on_data_changed)
        form.addRow(_("Tag Name:"), self.name_edit)
        
        self.emoji_edit = QLineEdit()
        self.emoji_edit.setPlaceholderText(_("e.g. 🎨"))
        self.emoji_edit.setMaxLength(4) 
        self.emoji_edit.textChanged.connect(self._on_data_changed)
        
        self.display_mode_combo = QComboBox()
        self.display_mode_combo.setView(QListView())
        # Fix transparency: explicit opaque background for both combo and its view
        self.display_mode_combo.setStyleSheet("""
            QComboBox { background-color: #2b2b2b; color: #eee; border: 1px solid #555; padding: 2px; }
            QComboBox QAbstractItemView { background-color: #2b2b2b; color: #eee; selection-background-color: #3498db; outline: none; }
        """)
        self.display_mode_combo.addItem(_("Text"), "text")
        self.display_mode_combo.addItem(_("Symbol"), "symbol")
        self.display_mode_combo.addItem(_("Sym+Text"), "text_symbol")
        self.display_mode_combo.addItem(_("Img"), "image")
        self.display_mode_combo.addItem(_("Img+Text"), "image_text")
        self.display_mode_combo.currentIndexChanged.connect(self._on_data_changed)
        form.addRow(_("Display:"), self.display_mode_combo)

        emoji_h = QHBoxLayout()
        emoji_h.addWidget(self.emoji_edit)
        emoji_h.addStretch()
        form.addRow(_("Symbol:"), emoji_h)

        self.inheritable_check = SlideButton()
        self.inheritable_check.setChecked(True)
        self.inheritable_check.toggled.connect(self._on_data_changed)
        form.addRow(_("子供に継承:"), self.inheritable_check)
        
        self.icon_edit = TagIconLineEdit()
        self.icon_edit.textChanged.connect(self._on_data_changed)
        self.icon_edit.file_dropped.connect(self._on_icon_dropped)
        form.addRow(_("Icon (Path):"), self.icon_edit)
        
        self.icon_btn = QPushButton(_(" Browse "))
        self.icon_btn.clicked.connect(self._browse_icon)
        
        icon_btn_row = QHBoxLayout()
        icon_btn_row.addWidget(self.icon_btn)
        icon_btn_row.addStretch()
        form.addRow("", icon_btn_row)
        
        edit_layout.addLayout(form)
        edit_layout.addStretch()
        
        self.edit_container.setVisible(False)
        right_layout.addWidget(self.edit_container)
        self.splitter.addWidget(self.right_panel)
        self.splitter.setStretchFactor(0, 3) # Left Table
        self.splitter.setStretchFactor(1, 2) # Right Edit
        
        # Buttons
        btn_group = QWidget()
        btn_layout = QVBoxLayout(btn_group)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        
        self.overwrite_btn = QPushButton(_("Overwrite Current"))
        self.overwrite_btn.clicked.connect(self._save_current_item_data)
        self.overwrite_btn.setStyleSheet("""
            QPushButton { background-color: #2980b9; color: white; border: none; padding: 6px; border-radius: 4px; }
            QPushButton:hover { background-color: #3498db; }
            QPushButton:pressed { background-color: #1a5276; margin-top: 1px; margin-left: 1px; }
            QPushButton:disabled { background-color: #444; color: #888; }
        """)
        
        self.add_btn = QPushButton(_("Add New Tag"))
        self.add_btn.clicked.connect(self._add_tag_default)
        self.add_btn.setStyleSheet("""
            QPushButton { background-color: #e67e22; color: white; border: none; padding: 6px; border-radius: 4px; }
            QPushButton:hover { background-color: #f39c12; }
            QPushButton:pressed { background-color: #d35400; margin-top: 1px; margin-left: 1px; }
        """)
        
        self.add_sep_btn = QPushButton(_("Add Separator"))
        self.add_sep_btn.clicked.connect(self._add_sep)
        self.add_sep_btn.setStyleSheet("""
            QPushButton { background-color: #555555; color: white; border: none; padding: 6px; border-radius: 4px; }
            QPushButton:hover { background-color: #666666; }
            QPushButton:pressed { background-color: #333333; margin-top: 1px; margin-left: 1px; }
        """)
        
        self.remove_btn = QPushButton(_("Remove Selected"))
        self.remove_btn.clicked.connect(self._remove_tag)
        self.remove_btn.setStyleSheet("""
            QPushButton { background-color: #c0392b; color: white; border: none; padding: 6px; border-radius: 4px; }
            QPushButton:hover { background-color: #e74c3c; }
            QPushButton:pressed { background-color: #922b21; margin-top: 1px; margin-left: 1px; }
        """)
        
        self.save_btn = QPushButton(_("Confirm"))
        self.save_btn.clicked.connect(self._save_and_close)
        self.save_btn.setStyleSheet("""
            QPushButton { background-color: #27ae60; color: white; font-weight: bold; margin-top: 10px; border: none; padding: 6px; border-radius: 4px; }
            QPushButton:hover { background-color: #2ecc71; }
            QPushButton:pressed { background-color: #1e8449; margin-top: 11px; margin-left: 1px; }
        """)
        
        btn_layout.addWidget(self.overwrite_btn)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.add_sep_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addWidget(self.save_btn)
        
        right_layout.addWidget(btn_group)
        
        # Finish layout
        self.set_content_widget(content_widget)

    def _load_tags(self):
        self._loading = True
        try:
            import json
            # Use App-Specific DB (self.db) to match Main Window logic
            if not self.db: return
            
            raw = self.db.get_setting('frequent_tags_config', '[]')
            try:
                self.tags = json.loads(raw)
                if not isinstance(self.tags, list): self.tags = []
            except:
                self.tags = []
            self._refresh_table()
        finally:
            self._loading = False
        
        self.tag_table.clearSelection()
        self._on_table_clicked(None)
        
    def _refresh_list(self):
        self._refresh_table()

    def _refresh_table(self):
        self.tag_table.setRowCount(0)
        
        for idx, tag in enumerate(self.tags):
            row = idx
            self.tag_table.insertRow(row)
            self.tag_table.setRowHeight(row, 26) # Consistent with user preference
            is_sep = tag.get('name') == '|' or tag.get('is_sep')
            if is_sep:
                # Store data in Column 0 even for separators to ensure sync/saving works
                sep_data_item = QTableWidgetItem()
                sep_data_item.setData(Qt.ItemDataRole.UserRole, tag)
                self.tag_table.setItem(row, 0, sep_data_item)
                
                sep_item = QTableWidgetItem(_("|--- Separator ---|"))
                sep_item.setForeground(QColor("#888"))
                self.tag_table.setItem(row, 2, sep_item)
                # Ensure other columns 1, 3, 4 are empty
                for col in [1, 3, 4]:
                    self.tag_table.setItem(row, col, QTableWidgetItem(""))
            else:
                # Icon
                icon_path = tag.get('icon', '')
                if icon_path and os.path.exists(icon_path):
                    pix = QPixmap(icon_path).scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    icon_item = QTableWidgetItem(QIcon(pix), "")
                else:
                    icon_item = QTableWidgetItem("❓")
                icon_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                icon_item.setData(Qt.ItemDataRole.UserRole, tag) # Store full data in col 0
                self.tag_table.setItem(row, 0, icon_item)
                
                # Symbol
                sym_item = QTableWidgetItem(tag.get('emoji', ''))
                sym_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tag_table.setItem(row, 1, sym_item)
                
                # Tag Name (Inherits default alignment but force it to be safe)
                name_item = QTableWidgetItem(tag.get('name', ''))
                name_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter) # Name is better left-aligned
                name_item.setForeground(QColor("#eeeeee"))
                self.tag_table.setItem(row, 2, name_item)
                
                # Inherit
                inherit = tag.get('is_inheritable', True)
                inh_text = _("Yes") if inherit else _("No")
                inh_item = QTableWidgetItem(inh_text)
                inh_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                inh_item.setForeground(QColor("#eeeeee"))
                self.tag_table.setItem(row, 3, inh_item)
                
                # Display Mode
                mode = tag.get('display_mode', 'text')
                mode_labels = {
                    'text': _("Text"),
                    'symbol': _("Sym"),
                    'text_symbol': _("Sym+Text"),
                    'image': _("Img"),
                    'image_text': _("Img+Text")
                }
                mode_item = QTableWidgetItem(mode_labels.get(mode, mode))
                mode_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                mode_item.setForeground(QColor("#eeeeee"))
                self.tag_table.setItem(row, 4, mode_item)

            for col in range(5):
                item = self.tag_table.item(row, col)
                if item:
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled)

        if self.tag_table.rowCount() == 0:
            self.edit_container.setVisible(False)
            self.empty_placeholder.setVisible(True)
            self.current_tag_ref = None
        else:
            # Rebranded requirement: Don't select any item on startup
            self.tag_table.clearSelection()
            self.tag_table.setCurrentCell(-1, -1)
            self.edit_container.setVisible(False)
            self.empty_placeholder.setVisible(True)
            self.current_tag_ref = None
            self.overwrite_btn.setEnabled(False)
            self.overwrite_btn.setStyleSheet("background-color: #444; color: #888;")
            
    def _on_table_clicked(self, item):
        if not item: return
        row = self.tag_table.row(item)
        main_item = self.tag_table.item(row, 0)
        self._on_item_clicked(main_item)


    def _on_item_clicked(self, item):
        # NOTE: Auto-save on selection change was removed due to unstable reference tracking.
        # Users must explicitly use the "Overwrite Save" button to save changes.

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
        
        # Separator Guard: if name is "|", disable most inputs
        is_sep = tag.get('is_sep', False) or tag.get('name') == "|"
        
        self.edit_container.setVisible(True)
        self.empty_placeholder.setVisible(False)
        
        # Apply Separator Styles
        bg_color = "#3d3d3d" if is_sep else "#1e1e1e"
        edit_style = f"background-color: {bg_color}; color: #eee; border: 1px solid #555; padding: 4px;"
        
        self.name_edit.setEnabled(not is_sep)
        self.name_edit.setStyleSheet(edit_style)
        self.emoji_edit.setEnabled(not is_sep)
        self.emoji_edit.setStyleSheet(edit_style)
        self.display_mode_combo.setEnabled(not is_sep)
        self.inheritable_check.setEnabled(not is_sep)
        self.icon_edit.setEnabled(not is_sep)
        self.icon_edit.setStyleSheet(edit_style)
        self.icon_btn.setEnabled(not is_sep)
        
        # Button dimming
        if is_sep:
            self.overwrite_btn.setEnabled(False)
            self.overwrite_btn.setStyleSheet("background-color: #444; color: #888;")
        else:
            self.overwrite_btn.setEnabled(True)
            self.overwrite_btn.setStyleSheet("background-color: #2980b9; color: white;")
        self.name_edit.setText(tag.get('name', ''))
        self.emoji_edit.setText(tag.get('emoji', ''))
        mode = tag.get('display_mode', 'text')
        idx = self.display_mode_combo.findData(mode)
        if idx >= 0: self.display_mode_combo.setCurrentIndex(idx)
        else: self.display_mode_combo.setCurrentIndex(0)
        self.icon_edit.setText(tag.get('icon', ''))
        self.inheritable_check.setChecked(bool(tag.get('is_inheritable', True)))
        self._loading = False

    def _on_icon_dropped(self, path):
        """Handle image drop onto icon path field."""
        if not path: return
        self._process_and_set_icon(path)
        # Auto-switch display mode to Image if an image is dropped
        idx = self.display_mode_combo.findData("image")
        if idx >= 0:
            self.display_mode_combo.setCurrentIndex(idx)
            
    def _on_data_changed(self):
        pass

    def _on_rows_moved(self, parent, start, end, destination, row):
        """Handle synchronization after the row move is visually complete."""
        # Using a timer to ensure the move is finished in the model
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._sync_tags_from_table)
        self._dirty = True

    def eventFilter(self, source, event):
        """Catch Drag/Drop events on the table viewport for validation without blocking normal interaction."""
        if source is self.tag_table.viewport():
            if event.type() == QEvent.Type.DragEnter:
                self._is_dragging = True  # Mark that a D&D operation is in progress
            if event.type() == QEvent.Type.DragMove:
                # Proactively ignore drops on 'nothing' (far below last row)
                pos = event.position().toPoint()
                index = self.tag_table.indexAt(pos)
                if not index.isValid():
                    last_row = self.tag_table.rowCount() - 1
                    if last_row >= 0:
                        last_row_bottom = self.tag_table.rowViewportPosition(last_row) + self.tag_table.rowHeight(last_row)
                        if pos.y() > last_row_bottom + 10:
                            event.ignore()
                            return True
                return False
            elif event.type() == QEvent.Type.Drop:
                self.tag_table.setUpdatesEnabled(False)
                QTimer.singleShot(30, self._sync_tags_from_table)
                self._dirty = True
                return False
        return super().eventFilter(source, event)

    def _sync_tags_from_table(self):
        """Update self.tags list from the current order of the table. Only triggers rollback if a D&D was in progress."""
        try:
            if self._loading: 
                self.tag_table.setUpdatesEnabled(True)
                return
            
            new_tags = []
            rowCount = self.tag_table.rowCount()
            expected = len(self.tags)
            
            for i in range(rowCount):
                item = self.tag_table.item(i, 0)
                if item:
                    tag_data = item.data(Qt.ItemDataRole.UserRole)
                    if isinstance(tag_data, dict):
                        new_tags.append(tag_data)
            
            if len(new_tags) == expected:
                self.tags = new_tags
                import logging; logging.debug(f"[TagManager] SUCCESS: tags synchronized ({len(self.tags)} items)")
            else:
                import logging; logging.debug(f"[TagManager] FAILURE: Table state inconsistent (found {len(new_tags)} items, expected {expected})")
                # Only trigger rollback if this was caused by a D&D operation
                if self._is_dragging:
                    logging.debug(f"[TagManager] Auto-rollback triggered (D&D detected).")
                    self._loading = True
                    self._refresh_table()
                    self._loading = False
        except Exception as e:
            import logging; logging.debug(f"[TagManager] Sync error: {e}")
        finally:
            self._is_dragging = False  # Clear the D&D flag
            self.tag_table.setUpdatesEnabled(True)
            self.tag_table.repaint()

    def _find_row_for_tag(self, tag_ref):
        """Find the row index containing the given tag data object."""
        for i in range(self.tag_table.rowCount()):
            it = self.tag_table.item(i, 0)
            if it and it.data(Qt.ItemDataRole.UserRole) is tag_ref:
                return i
        return -1

    def _save_tag_data_from_ui(self, tag):
        """Standardized logic to save current UI input fields into a tag record and update its table row."""
        import logging
        if not tag: 
            logging.debug(f"[TagManager] _save_tag_data_from_ui: tag is None, skipping")
            return
        
        if not tag.get('is_sep'):
            # Update data object
            old_name = tag.get('name', '')
            tag['name'] = self.name_edit.text().strip() or 'Unnamed'
            tag['value'] = tag['name'] 
            tag['emoji'] = self.emoji_edit.text().strip()
            tag['icon'] = self.icon_edit.text().strip()
            tag['display_mode'] = self.display_mode_combo.currentData()
            tag['is_inheritable'] = self.inheritable_check.isChecked()
            
            logging.debug(f"[TagManager] Saving: '{old_name}' -> '{tag['name']}' (id={id(tag)})")
            
            # Find row and update UI
            row = self._find_row_for_tag(tag)
            logging.debug(f"[TagManager] _find_row_for_tag returned: {row}")
            if row >= 0:
                item0 = self.tag_table.item(row, 0)
                if item0:

                    if tag['icon'] and os.path.exists(tag['icon']):
                        from PyQt6.QtGui import QPixmap
                        pix = QPixmap(tag['icon']).scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        item0.setIcon(QIcon(pix))
                        item0.setText("")
                    else:
                        item0.setIcon(QIcon())
                        item0.setText("❓")
                    
                    # CRITICAL: Explicitly update the UserRole data in the item to ensure it's not stale
                    item0.setData(Qt.ItemDataRole.UserRole, tag)
                
                # Update other columns
                # Symbol (Col 1)
                self.tag_table.setItem(row, 1, QTableWidgetItem(tag['emoji']))
                self.tag_table.item(row, 1).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                
                # Tag Name (Col 2)
                name_item = QTableWidgetItem(tag['name'])
                name_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                name_item.setForeground(QColor("#eeeeee"))
                self.tag_table.setItem(row, 2, name_item)
                
                # Inherit (Col 3)
                inherit_text = _("Yes") if tag['is_inheritable'] else _("No")
                inh_item = QTableWidgetItem(inherit_text)
                inh_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                inh_item.setForeground(QColor("#eeeeee"))
                self.tag_table.setItem(row, 3, inh_item)
                
                # Mode labels (consistent with refresh_table)
                mode_labels = {
                    'text': _("Text"), 'symbol': _("Sym"), 'text_symbol': _("Sym+Text"),
                    'image': _("Img"), 'image_text': _("Img+Text")
                }
                mode_item = QTableWidgetItem(mode_labels.get(tag['display_mode'], tag['display_mode']))
                mode_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                mode_item.setForeground(QColor("#eeeeee"))
                self.tag_table.setItem(row, 4, mode_item)
                
                # Re-apply flags if item was reset
                for col in range(5):
                    it = self.tag_table.item(row, col)
                    if it: it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled)
                
                print(f"[TagManager] Saved changes to row {row}: {tag['name']}")
        self._dirty = True

    def _add_tag_default(self):
        # Auto-save previous selection before adding new (uses direct row access)
        if not self._loading:
            self._save_current_item_data()

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
        """Manual overwrite of the CURRENTLY SELECTED row - uses current selection directly."""
        import logging
        
        row = self.tag_table.currentRow()
        if row < 0:
            logging.debug("[TagManager] _save_current_item_data: No row selected")
            return
        
        item = self.tag_table.item(row, 0)
        if not item:
            logging.debug(f"[TagManager] _save_current_item_data: Row {row} has no item")
            return
            
        tag = item.data(Qt.ItemDataRole.UserRole)
        if not tag:
            logging.debug(f"[TagManager] _save_current_item_data: Row {row} item has no UserRole data")
            return
            
        if tag.get('is_sep'):
            logging.debug("[TagManager] _save_current_item_data: Cannot save separator")
            return
        
        # Update the data object directly
        old_name = tag.get('name', '')
        tag['name'] = self.name_edit.text().strip() or 'Unnamed'
        tag['value'] = tag['name']
        tag['emoji'] = self.emoji_edit.text().strip()
        tag['icon'] = self.icon_edit.text().strip()
        tag['display_mode'] = self.display_mode_combo.currentData()
        tag['is_inheritable'] = self.inheritable_check.isChecked()
        
        # CRITICAL: Ensure self.tags is also updated (explicit copy if identity mismatch)
        # Find the matching tag in self.tags by identity or position
        if row < len(self.tags) and self.tags[row] is tag:
            logging.debug(f"[TagManager] Identity OK: self.tags[{row}] is same object")
        else:
            # Object mismatch - explicitly update self.tags
            logging.debug(f"[TagManager] Identity MISMATCH: updating self.tags[{row}] explicitly")
            if row < len(self.tags):
                self.tags[row] = tag
            else:
                logging.debug(f"[TagManager] ERROR: row {row} out of bounds for self.tags (len={len(self.tags)})")
        
        logging.debug(f"[TagManager] Saved row {row}: '{old_name}' -> '{tag['name']}' | Verification: self.tags[{row}]['name'] = '{self.tags[row].get('name', '?') if row < len(self.tags) else 'OOB'}'")
        

        # Update the visual table cells
        # Update the visual table cells
        if tag['icon'] and os.path.exists(tag['icon']):
            from PyQt6.QtGui import QPixmap
            pix = QPixmap(tag['icon']).scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            item.setIcon(QIcon(pix))
            item.setText("")
        else:
            item.setIcon(QIcon())
            item.setText("❓")

        # CRITICAL: Explicitly update the UserRole data in the item to ensure it's not stale
        item.setData(Qt.ItemDataRole.UserRole, tag)
        
        # Symbol
        self.tag_table.setItem(row, 1, QTableWidgetItem(tag['emoji']))
        self.tag_table.item(row, 1).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Name
        name_item = QTableWidgetItem(tag['name'])
        name_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        name_item.setForeground(QColor("#eeeeee"))
        self.tag_table.setItem(row, 2, name_item)
        
        # Inherit
        inherit_text = _("Yes") if tag['is_inheritable'] else _("No")
        inh_item = QTableWidgetItem(inherit_text)
        inh_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        inh_item.setForeground(QColor("#eeeeee"))
        self.tag_table.setItem(row, 3, inh_item)
        
        # Mode
        mode_labels = {
            'text': _("Text"), 'symbol': _("Sym"), 'text_symbol': _("Sym+Text"),
            'image': _("Img"), 'image_text': _("Img+Text")
        }
        mode_item = QTableWidgetItem(mode_labels.get(tag['display_mode'], tag['display_mode']))
        mode_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        mode_item.setForeground(QColor("#eeeeee"))
        self.tag_table.setItem(row, 4, mode_item)
        
        # Re-apply flags
        for col in range(5):
            it = self.tag_table.item(row, col)
            if it: 
                it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled)
        
        self._dirty = True
        

    def _add_sep(self):
        # Auto-save previous selection before adding new (uses direct row access)
        if not self._loading:
            self._save_current_item_data()
        
        new_tag = {"name": "|", "value": "|", "emoji": "", "icon": "", "is_sep": True, "is_inheritable": True}
        self.tags.append(new_tag)
        self._refresh_table()
        self.tag_table.selectRow(self.tag_table.rowCount()-1)
        self._dirty = True


    def _remove_tag(self):
        import logging
        row = self.tag_table.currentRow()
        logging.debug(f"[TagManager] _remove_tag called: currentRow={row}, self.tags length={len(self.tags)}")
        
        if row < 0:
            logging.debug("[TagManager] _remove_tag: No row selected")
            return
            
        item = self.tag_table.item(row, 0)
        if not item: 
            logging.debug(f"[TagManager] _remove_tag: Row {row} has no item")
            return
        tag_to_remove = item.data(Qt.ItemDataRole.UserRole)
        if not tag_to_remove: 
            logging.debug(f"[TagManager] _remove_tag: Row {row} has no UserRole data")
            return

        self._loading = True
        self.current_tag_ref = None
        
        # Try identity-based removal first
        found = False
        for i, tag in enumerate(self.tags):
            if tag is tag_to_remove:
                logging.debug(f"[TagManager] Removing by identity: index {i}")
                del self.tags[i]
                found = True
                break
        
        # Fallback: if identity match failed, remove by position
        if not found:
            logging.debug(f"[TagManager] Identity match failed, removing by position: row {row}")
            if row < len(self.tags):
                del self.tags[row]
            else:
                logging.debug(f"[TagManager] ERROR: row {row} out of bounds")
        
        logging.debug(f"[TagManager] After removal: self.tags length={len(self.tags)}")
        
        self._refresh_table()
        self._loading = False
        self._dirty = True



    def _clear_icon(self):
        self.icon_edit.clear()

    def _on_icon_dropped_to_edit(self, path):
        self._process_and_set_icon(path)

    def _process_and_set_icon(self, path):
        try:
            from PyQt6.QtGui import QImage
            # Phase 63: Use APPDATA for tag icons in EXE mode
            res_dir = get_user_data_path(os.path.join("resource", "tags"))
            ensure_dir(res_dir)
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
        # テーブルのUserRoleデータをself.tagsに同期（位置変更なしでも編集内容を反映）
        self._sync_tags_from_table()
        import json
        
        if self.db:
             self.db.set_setting('frequent_tags_config', json.dumps(self.tags))
        else:
             import logging
             logging.error("[TagManager] Cannot save tags: No db available")
        # Close dialog first
        self.accept()
        # Use main window for toast so it persists
        app_window = self.window().parent() or self.window()
        import logging
        logging.debug(f"[FrequentTagEdit] Save success, showing toast on window={app_window}")
        if hasattr(app_window, '_toast_instance'):
            app_window._toast_instance.show_message(_("Tags saved successfully"), preset="success")
        else:
            Toast.show_toast(app_window, _("Tags saved successfully"), preset="success")
        self._dirty = False

    def closeEvent(self, event):
        # Phase 32: Always save geometry before closing
        self._save_geometry()
        
        if self._dirty:
            from src.ui.common_widgets import FramelessMessageBox
            msg_box = FramelessMessageBox(self)
            msg_box.setIcon(FramelessMessageBox.Icon.Question)
            msg_box.setWindowTitle(_("Unsaved Changes"))
            msg_box.setText(_("You have unsaved changes. Do you want to save them?"))
            
            save_btn = msg_box.addButton(_("Save"), QMessageBox.ButtonRole.AcceptRole)
            discard_btn = msg_box.addButton(_("Discard"), QMessageBox.ButtonRole.DestructiveRole)
            cancel_btn = msg_box.addButton(_("Cancel"), QMessageBox.ButtonRole.RejectRole)
            
            msg_box.exec()
            clicked = msg_box.clickedButton()
            
            if clicked == save_btn:
                self._save_and_close()
                event.accept()
            elif clicked == discard_btn:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape: self.close()
        else: super().keyPressEvent(event)


class FrequentTagEditDialog(FramelessDialog):
    """
    Restored class to fix 'Quick Tag Edit' stack trace.
    Allows editing multiple frequent tags in a simple list.
    """
    def __init__(self, parent=None, db=None):
        super().__init__(parent)
        self.setWindowTitle(_("Quick Tag Edit"))
        self.setMinimumSize(400, 500)
        self.set_default_icon()
        self.db = db
        self._init_ui()
        self._load_data()

    def _init_ui(self):
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        
        self.label = QLabel(_("Edit quick tags (one per line):"))
        self.label.setStyleSheet("background: transparent; color: #ffffff; border: none;")
        layout.addWidget(self.label)
        
        self.text_edit = ProtectedTextEdit()
        self.text_edit.setPlaceholderText(_("Tag1,Symbol1\nTag2,Symbol2..."))
        self.text_edit.setStyleSheet("background-color: #1e1e1e; color: #ffffff; font-family: Consolas, monospace;")
        layout.addWidget(self.text_edit)
        
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton(_("Save"))
        self.save_btn.clicked.connect(self.accept)
        self.save_btn.setStyleSheet("background-color: #27ae60; color: white; padding: 8px;")
        
        self.cancel_btn = QPushButton(_("Cancel"))
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setStyleSheet("background-color: #c0392b; color: white; padding: 8px;")
        
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)
        self.set_content_widget(content_widget)
        self.set_content_widget(content_widget)

    def _load_data(self):
        if not self.db: return
        # User requested: "Empty on launch" (or maybe they meant the first line?)
        # Let's keep data loading but if they want it empty we could clear it.
        # But usually 'Edit' means loading current state.
        # Rereading: "クイックタグ編集起動時 1番目のデータが入っているが空にする"
        # This usually means the input fields in the Manager. 
        # I already cleared selection in TagManagerDialog.
        raw = self.db.get_setting('frequent_tags', '') 
        self.text_edit.setPlainText(raw)

    def get_data(self):
        return self.text_edit.toPlainText().strip()


class TestStyleDialog(FramelessDialog):
    """Simple verification dialog to check base styles."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("UI Style Verification")
        self.set_default_icon()
        self.resize(300, 150)
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.addWidget(QLabel("UI Style Verification - Dialog Base Style"))
        
        btn = QPushButton("OK")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
        self.set_content_widget(content)


class TagCreationDialog(FramelessDialog):
    def __init__(self, parent=None, db=None):
        super().__init__(parent)
        self.setWindowTitle(_("Create New Tag"))
        self.setMinimumSize(400, 300)
        self.set_default_icon()
        self.db = db
        self._init_ui()

    def _init_ui(self):
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        form = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(_("e.g. Work"))
        form.addRow(_("Tag Name:"), self.name_edit)
        
        self.emoji_edit = QLineEdit()
        self.emoji_edit.setPlaceholderText(_("e.g. 🎨"))
        self.emoji_edit.setMaxLength(4)
        
        # Display Mode Combo (Match TagManagerDialog)
        self.display_mode_combo = QComboBox()
        from PyQt6.QtWidgets import QListView
        self.display_mode_combo.setView(QListView()) # FORCE QSS on windows
        # Explicitly set opaque background to avoid transparency issues
        self.display_mode_combo.setStyleSheet("""
            QComboBox { background-color: #2b2b2b; color: #eee; border: 1px solid #555; padding: 2px; }
            QComboBox QAbstractItemView { background-color: #2b2b2b; color: #eee; selection-background-color: #3498db; outline: none; }
        """)
        self.display_mode_combo.addItem(_("Text"), "text")
        self.display_mode_combo.addItem(_("Symbol"), "symbol")
        self.display_mode_combo.addItem(_("Sym+Text"), "text_symbol")
        self.display_mode_combo.addItem(_("Img"), "image")
        self.display_mode_combo.addItem(_("Img+Text"), "image_text")
        
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
        form.addRow(_("子供に継承:"), self.inheritable_check)
        
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
        self.set_content_widget(content_widget)
        
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

class IconCropDialog(FramelessDialog):
    def __init__(self, parent=None, image_source=None, allow_free=False):
        super().__init__(parent)
        self.setWindowTitle(_("Select Region"))
        self.setModal(True)
        self.setMinimumSize(800, 600)
        self.set_default_icon()
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
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(0, 0, 0, 10)  # No top margin, text sits right under title
        layout.setSpacing(5)
        
        # Help Text Banner - sits directly under title bar
        self.hint_label = QLabel(_("Drag to move selection, use bottom-right corner to resize. Aspect ratio: 1:1 (Square)."))
        if self.allow_free:
            self.hint_label.setText(_("Drag to move, resize corner for free selection."))
            
        self.hint_label.setStyleSheet("background-color: #1a1a1a; color: #aaa; font-style: italic; padding: 8px 10px; border-bottom: 1px solid #444;")
        layout.addWidget(self.hint_label)
        
        # Use Custom Label
        self.crop_label = CropLabel(self.display_pixmap, self, allow_free=self.allow_free)
        layout.addWidget(self.crop_label)
        
        btns = QHBoxLayout()
        
        # Toggle Mode Button (Localized)
        mode_text = _("Mode: Free") if self.allow_free else _("Mode: Square")
        self.mode_btn = StyledButton(mode_text)
        self.mode_btn.setCheckable(True)
        self.mode_btn.setChecked(self.allow_free)
        self.mode_btn.clicked.connect(self._toggle_mode)
        self.mode_btn.setFixedWidth(140)
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
        self.set_content_widget(content_widget)

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

class ImportTypeDialog(FramelessDialog):
    def __init__(self, parent=None, target_type="item"):
        super().__init__(parent)
        self.setWindowTitle(_("Select Import Type"))
        self.set_default_icon()
        self.target_type = target_type
        self.result_type = None
        self._init_ui()

    def _init_ui(self):
        from src.ui.common_widgets import StyledButton
        from src.ui.styles import ButtonStyles, TooltipStyles
        
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Translating target_type name
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
        title.setStyleSheet("font-size: 16px; margin-bottom: 2px;") 
        layout.addWidget(title)

        # Security Note
        note = QLabel(_("Note: Target installation paths are NOT stored in dioco files for security."))
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setStyleSheet("color: #888; font-size: 10px; font-style: italic; margin-bottom: 8px;")
        note.setWordWrap(True)
        layout.addWidget(note)
        
        desc = QLabel(_("Select how to import this {type}:").format(type=type_name))
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # Buttons using standard styles
        btn_folder = QPushButton(_("📁 Folder"))
        btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_folder.clicked.connect(lambda: self._set_result("folder"))
        layout.addWidget(btn_folder)
        
        btn_zip = QPushButton(_("📦 Archive File"))
        btn_zip.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_zip.clicked.connect(lambda: self._set_result("archive"))
        layout.addWidget(btn_zip)
        
        btn_explorer = QPushButton(_("🔍 Open Explorer"))
        btn_explorer.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_explorer.clicked.connect(lambda: self._set_result("explorer"))
        layout.addWidget(btn_explorer)
        
        layout.addSpacing(5)
        
        btn_cancel = QPushButton(_("Cancel"))
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        layout.addWidget(btn_cancel)
        
        self.setFixedSize(320, 360)
        self.set_content_widget(content_widget)

    def _set_result(self, rtype):
        self.result_type = rtype
        self.accept()

    def get_result(self):
        return self.result_type

class PresetPropertiesDialog(FramelessDialog):
    def __init__(self, parent=None, name="", description=""):
        super().__init__(parent)
        self.setWindowTitle(_("Preset Properties"))
        self.setFixedWidth(400)
        self.set_default_icon()
        
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        form = QFormLayout()
        
        self.name_edit = QLineEdit(name)
        form.addRow(_("Preset Name:"), self.name_edit)
        
        from PyQt6.QtWidgets import QTextEdit
        self.desc_edit = ProtectedTextEdit()
        self.desc_edit.setPlainText(description or "")
        self.desc_edit.setPlaceholderText(_("Optional description..."))
        form.addRow(_("Description:"), self.desc_edit)
        
        layout.addLayout(form)
        
        btns = QHBoxLayout()
        ok_btn = QPushButton(_("Save"))
        ok_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton(_("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        
        btns.addStretch()
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)
        self.set_content_widget(content_widget)

    def get_data(self):
        return {
            "name": self.name_edit.text(),
            "description": self.desc_edit.toPlainText()
        }
