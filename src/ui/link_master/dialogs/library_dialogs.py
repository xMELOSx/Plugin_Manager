import os
import json
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
                             QPushButton, QTreeWidget, QTreeWidgetItem, QFormLayout, 
                             QLineEdit, QMessageBox, QListWidget, QListWidgetItem, QMenu, QWidget)
from PyQt6.QtCore import pyqtSignal, Qt, QSize, QByteArray
from src.core.lang_manager import _
from src.ui.common_widgets import StyledComboBox, ProtectedLineEdit

class LibrarySettingsDialog(QDialog):
    """ライブラリの詳細設定ダイアログ"""
    request_view_properties = pyqtSignal(str)
    request_edit_properties = pyqtSignal(str)
    
    def __init__(self, parent, db, lib_name: str, versions: list, app_id=None):
        super().__init__(parent)
        self.db = db
        self.lib_name = lib_name
        self.versions = versions
        self.app_id = app_id
        self.setWindowTitle(_("Library Settings: {name}").format(name=lib_name))
        self.setMinimumSize(550, 400)
        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; color: #e0e0e0; }
            QLineEdit, QTextEdit { background-color: #2d2d2d; color: #e0e0e0; border: 1px solid #3d3d3d; padding: 4px; }
            QTreeWidget { background-color: #2d2d2d; color: #e0e0e0; border: 1px solid #3d3d3d; }
            QTreeWidget::item { padding: 0px; margin: 0px; min-height: 32px; }
            QHeaderView::section { background-color: #333; color: white; border: none; padding: 6px; font-weight: bold; }
            QPushButton { background-color: #3d3d3d; color: #e0e0e0; padding: 2px 4px; margin: 0px; min-height: 20px; }
            QPushButton:hover { background-color: #5d5d5d; }
        """)
        self._init_ui()

    def save_state(self, tree_header):
        """Save UI state like column widths."""
        if not self.db: return
        try:
            state = tree_header.saveState().data().hex()
            self.db.set_setting(f'lib_panel_state_{self.app_id or "default"}', state)
        except Exception as e:
            print(f"Error saving lib state: {e}")

    def restore_state(self, tree_header):
        """Restore UI state."""
        if not self.db: return
        try:
             state_hex = self.db.get_setting(f'lib_panel_state_{self.app_id or "default"}')
             if state_hex:
                 tree_header.restoreState(QByteArray.fromHex(state_hex.encode()))
        except Exception as e:
            print(f"Error restoring lib state: {e}")

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        
        self.name_edit = ProtectedLineEdit(self.lib_name)
        form.addRow(_("Library Name:"), self.name_edit)
        
        first_cfg = self.versions[0] if self.versions else {}
        self.url_list_json = first_cfg.get('url_list', '[]') or '[]'
        
        url_manage_layout = QHBoxLayout()
        self.url_btn = QPushButton(_("🌐 Manage URLs..."))
        self.url_btn.clicked.connect(self._open_url_manager)
        self.url_btn.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; min-height: 24px;")
        url_manage_layout.addWidget(self.url_btn)
        
        self.url_count_label = QLabel("(0)")
        self.url_count_label.setStyleSheet("color: #888;")
        url_manage_layout.addWidget(self.url_count_label)
        url_manage_layout.addStretch()
        form.addRow(_("URLs:"), url_manage_layout)
        self._update_url_count_preview()
        
        self.author_edit = ProtectedLineEdit(first_cfg.get('author', ''))
        form.addRow(_("Author:"), self.author_edit)
        
        layout.addLayout(form)
        
        layout.addWidget(QLabel(_("Registered Versions:")))
        
        self.ver_tree = QTreeWidget()
        self.ver_tree.setUniformRowHeights(True)  # Ensure consistent row heights
        self.ver_tree.setEditTriggers(QTreeWidget.EditTrigger.DoubleClicked | QTreeWidget.EditTrigger.SelectedClicked)
        self.ver_tree.setHeaderLabels([_("Version (Editable)"), _("Package Name"), _("URL"), _("View"), _("Edit"), _("Unreg")])
        
        # Column widths: Version fixed, Package Name stretches, button columns fixed
        header = self.ver_tree.header()
        header.setSectionResizeMode(0, header.ResizeMode.Fixed)
        header.setSectionResizeMode(1, header.ResizeMode.Stretch)  # Package Name stretches
        header.setSectionResizeMode(2, header.ResizeMode.Fixed)
        header.setSectionResizeMode(3, header.ResizeMode.Fixed)
        header.setSectionResizeMode(4, header.ResizeMode.Fixed)
        header.setSectionResizeMode(5, header.ResizeMode.Fixed)
        self.ver_tree.setColumnWidth(0, 100)
        self.ver_tree.setColumnWidth(2, 45)  # URL button
        self.ver_tree.setColumnWidth(3, 45)  # View button
        self.ver_tree.setColumnWidth(4, 45)  # Edit button
        self.ver_tree.setColumnWidth(5, 45)  # Unreg button
        
        # Common button style - shared by all buttons
        btn_style = """
            QPushButton {
                padding: 0; margin: 0; font-size: 14px;
                background-color: #3d3d3d; color: #e0e0e0; 
                border: none; border-radius: 3px;
            }
            QPushButton:hover { background-color: #5d5d5d; }
            QPushButton:pressed { background-color: #2d2d2d; }
        """
        delete_btn_style = """
            QPushButton {
                background-color: #c0392b; color: white; 
                padding: 0; margin: 0; font-size: 14px;
                border: none; border-radius: 3px;
            }
            QPushButton:hover { background-color: #e74c3c; }
            QPushButton:pressed { background-color: #922b21; }
        """
        
        # Helper to create centered button container
        def create_centered_btn(btn):
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
            return container
        
        for v in self.versions:
            item = QTreeWidgetItem(self.ver_tree)
            item.setText(0, v.get('lib_version', 'Unknown'))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            rel_path = v.get('_rel_path') or v.get('rel_path', '')
            item.setText(1, os.path.basename(rel_path))
            
            # Set row height - smaller at 26px
            item.setSizeHint(0, QSize(0, 26))
            
            # URL Button
            url_btn = QPushButton("🌐")
            url_btn.setFixedSize(32, 22)
            url_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            url_btn.setStyleSheet(btn_style)
            url_btn.setToolTip(_("URL Management"))
            url_btn.clicked.connect(lambda _, p=rel_path, c=v.get('url_list', '[]'): self._open_version_url_manager(p, c))
            self.ver_tree.setItemWidget(item, 2, create_centered_btn(url_btn))
            
            # Column 3 (View)
            view_btn = QPushButton("📋")
            view_btn.setFixedSize(32, 22)
            view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            view_btn.setStyleSheet(btn_style)
            view_btn.setToolTip(_("View Properties"))
            view_btn.clicked.connect(lambda _, p=rel_path: self.request_view_properties.emit(p))
            self.ver_tree.setItemWidget(item, 3, create_centered_btn(view_btn))
            
            # Column 4 (Edit)
            edit_btn = QPushButton("✏")
            edit_btn.setFixedSize(32, 22)
            edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            edit_btn.setStyleSheet(btn_style)
            edit_btn.setToolTip(_("Edit Properties"))
            edit_btn.clicked.connect(lambda _, p=rel_path: self.request_edit_properties.emit(p))
            self.ver_tree.setItemWidget(item, 4, create_centered_btn(edit_btn))
            
            # Column 5 (Unregister) - red with hover
            unreg_btn = QPushButton("🗑")
            unreg_btn.setFixedSize(32, 22)
            unreg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            unreg_btn.setStyleSheet(delete_btn_style)
            unreg_btn.setToolTip(_("Unregister"))
            unreg_btn.clicked.connect(lambda _, p=rel_path, it=item: self._unregister_version(p, it))
            self.ver_tree.setItemWidget(item, 5, create_centered_btn(unreg_btn))
            
            item.setData(0, Qt.ItemDataRole.UserRole, rel_path)
        
        self.ver_tree.header().setSortIndicatorClearable(True)
        self.ver_tree.setSortingEnabled(True)
        self.ver_tree.header().setSortIndicator(0, Qt.SortOrder.AscendingOrder)
        self.ver_tree.header().sectionClicked.connect(self._on_ver_header_clicked)
        
        layout.addWidget(self.ver_tree)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        save_btn = QPushButton(_("Save"))
        save_btn.setStyleSheet("background-color: #27ae60; color: white;")
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton(_("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
    
    def _on_ver_header_clicked(self, logicalIndex):
        """Ensure sorting defaults to Ascending when a new column is clicked."""
        if self.ver_tree.header().sortIndicatorSection() != logicalIndex:
            self.ver_tree.header().setSortIndicator(logicalIndex, Qt.SortOrder.AscendingOrder)

    def _unregister_version(self, path: str, item: QTreeWidgetItem):
        confirm = QMessageBox.question(
            self, _("Unregister Library"), 
            _("Unregister this version from the library?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.db.update_folder_display_config(path, is_library=0, lib_name=None, lib_version=None)
            idx = self.ver_tree.indexOfTopLevelItem(item)
            if idx >= 0:
                self.ver_tree.takeTopLevelItem(idx)
    
    def _update_url_count_preview(self):
        try:
            ud = json.loads(self.url_list_json)
            urls = []
            if isinstance(ud, list): urls = ud
            elif isinstance(ud, dict): urls = ud.get('urls', [])
            self.url_count_label.setText(f"({len(urls)})")
        except:
            self.url_count_label.setText("(0)")

    def _open_url_manager(self):
        from src.ui.link_master.dialogs.url_list_dialog import URLListDialog
        dialog = URLListDialog(self, url_list_json=self.url_list_json, caller_id="library_settings")
        if dialog.exec():
            self.url_list_json = dialog.get_data()
            self._update_url_count_preview()

    def _open_version_url_manager(self, path, current_json):
        from src.ui.link_master.dialogs.url_list_dialog import URLListDialog
        dialog = URLListDialog(self, url_list_json=current_json, caller_id="library_version")
        if dialog.exec():
            new_json = dialog.get_data()
            self.db.update_folder_display_config(path, url_list=new_json)
            try:
                ud = json.loads(new_json)
                urls = ud if isinstance(ud, list) else ud.get('urls', [])
                if urls:
                    self.db.update_folder_display_config(path, url=urls[0].get('url'))
            except: pass

    def _save(self):
        new_lib_name = self.name_edit.text().strip()
        common_url_list = self.url_list_json
        legacy_url = None
        try:
            ud = json.loads(common_url_list)
            urls = ud if isinstance(ud, list) else ud.get('urls', [])
            if urls:
                legacy_url = urls[0].get('url')
        except: pass
        
        common_author = self.author_edit.text().strip()
        
        for i in range(self.ver_tree.topLevelItemCount()):
            item = self.ver_tree.topLevelItem(i)
            path = item.data(0, Qt.ItemDataRole.UserRole)
            new_ver = item.text(0).strip()
            
            self.db.update_folder_display_config(
                path,
                lib_name=new_lib_name or self.lib_name,
                lib_version=new_ver,
                url=legacy_url,
                url_list=common_url_list,
                author=common_author or None
            )
        self.accept()

class DependentPackagesDialog(QDialog):
    """依存パッケージ確認ダイアログ"""
    request_view_properties = pyqtSignal(str)
    request_edit_properties = pyqtSignal(str)
    request_deploy = pyqtSignal(str)
    request_unlink = pyqtSignal(str)
    
    def __init__(self, parent, db, lib_name: str, versions: list):
        super().__init__(parent)
        self.db = db
        self.lib_name = lib_name
        self.versions = versions
        self.setWindowTitle(_("Dependent Packages: {name}").format(name=lib_name))
        self.setMinimumSize(650, 400)
        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; color: #e0e0e0; }
            QTreeWidget { background-color: #2d2d2d; color: #e0e0e0; border: 1px solid #3d3d3d; }
            QTreeWidget::item { padding: 4px; }
            QHeaderView::section { background-color: #333; color: #eee; border: 1px solid #444; padding: 4px; }
            QPushButton { background-color: #3d3d3d; color: #e0e0e0; padding: 5px 10px; }
            QPushButton:hover { background-color: #5d5d5d; }
            QComboBox { background-color: #333; color: #eee; border: 1px solid #555; }
        """)
        self._init_ui()
        self._load_deps()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(_("Packages using '{name}':").format(name=self.lib_name)))
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([_("Package"), _("Status"), _("Usage"), _("Link"), _("View"), _("Edit"), _("Remove")])
        self.tree.setColumnWidth(0, 180)
        self.tree.setColumnWidth(1, 40)
        self.tree.setColumnWidth(2, 80)
        self.tree.setColumnWidth(3, 40)
        self.tree.setColumnWidth(4, 40)
        self.tree.setColumnWidth(5, 40)
        self.tree.setColumnWidth(6, 40)
        self.tree.header().setSortIndicatorClearable(True)
        self.tree.setSortingEnabled(True)
        self.tree.header().setSortIndicator(0, Qt.SortOrder.AscendingOrder)
        self.tree.header().sectionClicked.connect(self._on_header_clicked)

        layout.addWidget(self.tree)
        
        btn_layout = QHBoxLayout()
        
        # Batch Buttons
        batch_deploy_btn = QPushButton(_("Batch Deploy"))
        batch_deploy_btn.setStyleSheet("background-color: #27ae60; color: white; border-radius: 4px;")
        batch_deploy_btn.clicked.connect(self._batch_deploy_all)
        btn_layout.addWidget(batch_deploy_btn)
        
        batch_unlink_btn = QPushButton(_("Batch Unlink"))
        batch_unlink_btn.setStyleSheet("background-color: #e67e22; color: white; border-radius: 4px;")
        batch_unlink_btn.clicked.connect(self._batch_unlink_all)
        btn_layout.addWidget(batch_unlink_btn)
        
        btn_layout.addStretch()
        
        close_btn = QPushButton(_("Close"))
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
    
    def _on_header_clicked(self, logicalIndex):
        """Ensure sorting defaults to Ascending when a new column is clicked."""
        if self.tree.header().sortIndicatorSection() != logicalIndex:
            self.tree.header().setSortIndicator(logicalIndex, Qt.SortOrder.AscendingOrder)

    def _load_deps(self):
        # Save selection
        selected_rel = None
        curr = self.tree.currentItem()
        if curr:
            selected_rel = curr.data(0, Qt.ItemDataRole.UserRole)

        self.tree.clear()
        all_configs = self.db.get_all_folder_configs()
        ver_options = [_("Latest Version")]
        for v in self.versions:
            ver_options.append(v.get('lib_version', 'Unknown'))
        
        for rel_path, cfg in all_configs.items():
            if cfg.get('is_library', 0): continue
            lib_deps_json = cfg.get('lib_deps', '[]')
            try:
                lib_deps = json.loads(lib_deps_json) if lib_deps_json else []
            except: lib_deps = []
            
            for dep in lib_deps:
                dep_name = dep.get('name') if isinstance(dep, dict) else dep
                if dep_name != self.lib_name: continue
                
                item = QTreeWidgetItem(self.tree)
                display_name = cfg.get('display_name') or os.path.basename(rel_path)
                item.setText(0, display_name)
                status = cfg.get('last_known_status', 'unlinked')
                item.setText(1, "🟢" if status == 'linked' else "⚪")
                item.setTextAlignment(1, Qt.AlignmentFlag.AlignCenter)
                
                combo = StyledComboBox()
                combo.addItems(ver_options)
                ver_mode = dep.get('version_mode', 'latest') if isinstance(dep, dict) else 'latest'
                spec_ver = dep.get('version') if isinstance(dep, dict) else None
                if ver_mode == 'latest': combo.setCurrentText(_("Latest Version"))
                elif spec_ver: combo.setCurrentText(spec_ver)
                combo.currentTextChanged.connect(lambda t, rp=rel_path: self._on_version_changed(rp, t))
                self.tree.setItemWidget(item, 2, combo)
                
                if status == 'linked':
                    deploy_btn = QPushButton("🔗")
                    deploy_btn.setStyleSheet("background-color: #e67e22;")
                    deploy_btn.clicked.connect(lambda _, rp=rel_path: self._unlink_pkg(rp))
                else:
                    deploy_btn = QPushButton("🚀")
                    deploy_btn.setStyleSheet("background-color: #27ae60;")
                    deploy_btn.clicked.connect(lambda _, rp=rel_path: self._deploy_pkg(rp))
                deploy_btn.setFixedWidth(35)
                self.tree.setItemWidget(item, 3, deploy_btn)
                
                view_btn = QPushButton("📋")
                view_btn.setFixedWidth(35)
                view_btn.clicked.connect(lambda _, rp=rel_path: self.request_view_properties.emit(rp))
                self.tree.setItemWidget(item, 4, view_btn)
                
                edit_btn = QPushButton("✏")
                edit_btn.setFixedWidth(35)
                edit_btn.clicked.connect(lambda _, rp=rel_path: self.request_edit_properties.emit(rp))
                self.tree.setItemWidget(item, 5, edit_btn)
                
                remove_btn = QPushButton("🗑")
                remove_btn.setFixedWidth(35)
                remove_btn.setStyleSheet("background-color: #c0392b;")
                remove_btn.clicked.connect(lambda _, rp=rel_path: self._remove_dependency(rp))
                self.tree.setItemWidget(item, 6, remove_btn)
                
                item.setData(0, Qt.ItemDataRole.UserRole, rel_path)
                
                # Restore selection
                if selected_rel and rel_path == selected_rel:
                    self.tree.setCurrentItem(item)

        # Force focus back to list or maintain dialog focus
        self.setFocus()
    
    def _get_app_data(self):
        """Find the main window and get current app data."""
        curr = self.parent()
        while curr:
            if hasattr(curr, 'app_combo'):
                return curr.app_combo.currentData()
            curr = curr.parent()
        return None

    def _update_item_status(self, item):
        rel_path = item.data(0, Qt.ItemDataRole.UserRole)
        app_data = self._get_app_data()
        target_root = app_data.get('target_root') if app_data else None
        
        is_linked = False
        if target_root:
            folder_name = os.path.basename(rel_path)
            config = self.db.get_folder_config(rel_path) or {}
            target_link = config.get('target_override') or os.path.join(target_root, folder_name)
            if os.path.islink(target_link) or os.path.exists(target_link):
                is_linked = True
        
        # Update text
        status_text = "🟢 " + _("Linked") if is_linked else "⚪ " + _("Unlinked")
        item.setText(1, status_text)
        
        # Update buttons (column 3 is the toggle button)
        toggle_btn = self.tree.itemWidget(item, 3)
        if toggle_btn:
            # Check if this button currently has focus
            was_focused = toggle_btn.hasFocus()
            
            if is_linked:
                toggle_btn.setText("🔗")
                toggle_btn.setStyleSheet("background-color: #27ae60; color: white;")
                try: toggle_btn.clicked.disconnect()
                except: pass
                toggle_btn.clicked.connect(lambda _, rp=rel_path: self._unlink_pkg(rp))
            else:
                toggle_btn.setText("🚀")
                toggle_btn.setStyleSheet("background-color: #2980b9; color: white;")
                try: toggle_btn.clicked.disconnect()
                except: pass
                toggle_btn.clicked.connect(lambda _, rp=rel_path: self._deploy_pkg(rp))
            
            if was_focused:
                toggle_btn.setFocus()
        
        # Phase 32 Fix: Ensure focus is not lost from the dialog itself or the last interaction
        # if no button was focused, keep the tree focused.
        else:
            if not self.hasFocus():
                self.tree.setFocus()

    def _deploy_pkg(self, rel_path: str):
        self.request_deploy.emit(rel_path)
        # Find item and update
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item.data(0, Qt.ItemDataRole.UserRole) == rel_path:
                self._update_item_status(item)
                break
        
    def _batch_deploy_all(self):
        """Deploy all currently unlinked packages in the list."""
        count = 0
        items_to_update = []
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            rel_path = item.data(0, Qt.ItemDataRole.UserRole)
            if "⚪" in item.text(1):
                self.request_deploy.emit(rel_path)
                items_to_update.append(item)
                count += 1
        
        for item in items_to_update:
            self._update_item_status(item)

    def _unlink_pkg(self, rel_path: str):
        self.request_unlink.emit(rel_path)
        # Find item and update
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item.data(0, Qt.ItemDataRole.UserRole) == rel_path:
                self._update_item_status(item)
                break

    def _batch_unlink_all(self):
        """Unlink all currently linked packages in the list."""
        count = 0
        items_to_update = []
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            rel_path = item.data(0, Qt.ItemDataRole.UserRole)
            if "🟢" in item.text(1):
                self.request_unlink.emit(rel_path)
                items_to_update.append(item)
                count += 1
        
        for item in items_to_update:
            self._update_item_status(item)
    def _on_version_changed(self, rel_path: str, version_text: str):
        cfg = self.db.get_folder_config(rel_path) or {}
        lib_deps_json = cfg.get('lib_deps', '[]')
        try: lib_deps = json.loads(lib_deps_json) if lib_deps_json else []
        except: lib_deps = []
        new_deps = []
        for dep in lib_deps:
            if (isinstance(dep, dict) and dep.get('name') == self.lib_name) or (isinstance(dep, str) and dep == self.lib_name):
                if version_text == _("Latest Version"): new_deps.append({'name': self.lib_name, 'version_mode': 'latest'})
                else: new_deps.append({'name': self.lib_name, 'version_mode': 'specific', 'version': version_text})
            else: new_deps.append(dep)
        self.db.update_folder_display_config(rel_path, lib_deps=json.dumps(new_deps))
    def _remove_dependency(self, rel_path: str):
        confirm = QMessageBox.question(self, _("Remove Dependency"), _("Do you want to remove the dependency on '{name}' from this package?").format(name=self.lib_name), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm != QMessageBox.StandardButton.Yes: return
        cfg = self.db.get_folder_config(rel_path) or {}
        lib_deps_json = cfg.get('lib_deps', '[]')
        try: lib_deps = json.loads(lib_deps_json) if lib_deps_json else []
        except: lib_deps = []
        new_deps = [d for d in lib_deps if not (isinstance(d, dict) and d.get('name') == self.lib_name) and not (isinstance(d, str) and d == self.lib_name)]
        self.db.update_folder_display_config(rel_path, lib_deps=json.dumps(new_deps))
        self._load_deps()


class LibraryDependencyDialog(QDialog):
    """Dialog to manage library dependencies for a package."""
    def __init__(self, parent=None, lib_deps_json: str = "[]"):
        super().__init__(parent)
        self.setWindowTitle(_("Library Dependency Settings"))
        self.setMinimumSize(450, 350)
        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; color: #e0e0e0; }
            QListWidget { background-color: #2d2d2d; color: #e0e0e0; border: 1px solid #3d3d3d; }
            QListWidget::item { padding: 4px; }
            QListWidget::item:selected { background-color: #3d5a80; }
            QPushButton { background-color: #3d3d3d; color: #e0e0e0; padding: 5px 10px; }
            QPushButton:hover { background-color: #5d5d5d; }
        """)
        
        try:
            self.lib_deps = json.loads(lib_deps_json) if lib_deps_json else []
        except:
            self.lib_deps = []
        
        self._init_ui()
        self._load_list()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(_("Add or remove libraries to use.")))
        
        add_form = QHBoxLayout()
        self.lib_combo = StyledComboBox()
        self.lib_combo.setMinimumWidth(150)
        self._load_available_libraries()
        add_form.addWidget(self.lib_combo)
        
        self.ver_combo = StyledComboBox()
        self.ver_combo.addItem(_("Preferred"), None)
        self.ver_combo.setMinimumWidth(100)
        add_form.addWidget(self.ver_combo)
        
        self.lib_combo.currentIndexChanged.connect(self._on_lib_selected)
        
        add_btn = QPushButton(_("Add"))
        add_btn.clicked.connect(self._add_dep)
        add_form.addWidget(add_btn)
        layout.addLayout(add_form)
        
        layout.addWidget(QLabel(_("Current Dependencies:")))
        self.dep_list = QListWidget()
        self.dep_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.dep_list.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.dep_list)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton(_("OK"))
        ok_btn.setStyleSheet("background-color: #27ae60; color: white;")
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        cancel_btn = QPushButton(_("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
    
    def _load_available_libraries(self):
        self.lib_combo.clear()
        self.lib_combo.addItem(_("-- Select Library --"), None)
        try:
            curr = self.parent()
            while curr:
                if hasattr(curr, 'db') and curr.db:
                    all_configs = curr.db.get_all_folder_configs()
                    lib_names = set()
                    for rel_path, cfg in all_configs.items():
                        if cfg.get('is_library', 0):
                            lib_names.add(cfg.get('lib_name', 'Unknown'))
                    for name in sorted(lib_names):
                        self.lib_combo.addItem(f"📚 {name}", name)
                    break
                curr = curr.parent()
        except: pass
    
    def _on_lib_selected(self, index):
        self.ver_combo.clear()
        self.ver_combo.addItem(_("Preferred"), None)
        lib_name = self.lib_combo.currentData()
        if not lib_name: return
        try:
            curr = self.parent()
            while curr:
                if hasattr(curr, 'db') and curr.db:
                    all_configs = curr.db.get_all_folder_configs()
                    for rel_path, cfg in all_configs.items():
                        if cfg.get('is_library', 0) and cfg.get('lib_name') == lib_name:
                            ver = cfg.get('lib_version', 'Unknown')
                            self.ver_combo.addItem(f"📦 {ver}", ver)
                    break
                curr = curr.parent()
        except: pass
    
    def _add_dep(self):
        lib_name = self.lib_combo.currentData()
        if not lib_name: return
        version = self.ver_combo.currentData()
        for dep in self.lib_deps:
            if isinstance(dep, dict) and dep.get('name') == lib_name: return
            elif isinstance(dep, str) and dep == lib_name: return
        if version:
            self.lib_deps.append({'name': lib_name, 'version': version})
        else:
            self.lib_deps.append({'name': lib_name})
        self._load_list()
    
    def _load_list(self):
        self.dep_list.clear()
        for dep in self.lib_deps:
            if isinstance(dep, dict):
                name = dep.get('name', 'Unknown')
                ver = dep.get('version')
                text = f"📚 {name}" + (f" @ {ver}" if ver else _(" (Preferred)"))
            else:
                text = f"📚 {dep}" + _(" (Preferred)")
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, dep)
            self.dep_list.addItem(item)
    
    def _show_context_menu(self, pos):
        item = self.dep_list.itemAt(pos)
        if not item: return
        menu = QMenu(self)
        remove_action = menu.addAction(_("🗑 Delete"))
        action = menu.exec(self.dep_list.mapToGlobal(pos))
        if action == remove_action:
            dep = item.data(Qt.ItemDataRole.UserRole)
            if dep in self.lib_deps:
                self.lib_deps.remove(dep)
            self._load_list()
    
    def get_lib_deps_json(self) -> str:
        return json.dumps(self.lib_deps)


class LibraryRegistrationDialog(QDialog):
    """Library Registration Dialog - Select existing library or register version."""
    def __init__(self, parent=None, db=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle(_("Library Registration"))
        self.setMinimumSize(400, 200)
        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; color: #ffffff; }
            QLabel { color: #ffffff; }
            QLineEdit, QComboBox { background-color: #444444; color: #ffffff; border: 1px solid #555555; padding: 6px; }
            QComboBox QAbstractItemView { background-color: #444444; color: #ffffff; selection-background-color: #3498db; }
            QPushButton { background-color: #3d3d3d; color: #ffffff; padding: 6px 12px; }
            QPushButton:hover { background-color: #5d5d5d; }
        """)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(_("Register selected package as a library")))
        form = QFormLayout()
        
        self.lib_combo = StyledComboBox()
        self.lib_combo.setEditable(True)
        self.lib_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.lib_combo.lineEdit().setPlaceholderText(_("Enter new library name"))
        self.lib_combo.setStyleSheet("color: white;")
        self._load_existing_libraries()
        self.lib_combo.setCurrentIndex(-1)
        self.lib_combo.lineEdit().setText("")
        self.lib_combo.currentTextChanged.connect(self._on_lib_changed)
        form.addRow(_("Library Name:"), self.lib_combo)
        
        self.existing_versions_label = QLabel("")
        self.existing_versions_label.setStyleSheet("color: #888; font-size: 11px;")
        form.addRow("", self.existing_versions_label)
        
        self.version_edit = ProtectedLineEdit()
        self.version_edit.setPlaceholderText(_("1.0"))
        form.addRow(_("Version:"), self.version_edit)
        layout.addLayout(form)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton(_("Register"))
        ok_btn.setStyleSheet("background-color: #27ae60; color: white;")
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        cancel_btn = QPushButton(_("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
    
    def _load_existing_libraries(self):
        self.lib_combo.clear()
        if not self.db: return
        all_configs = self.db.get_all_folder_configs()
        lib_names = set()
        self.lib_versions = {}
        for rel_path, cfg in all_configs.items():
            if cfg.get('is_library', 0):
                name = cfg.get('lib_name', 'Unknown')
                lib_names.add(name)
                if name not in self.lib_versions:
                    self.lib_versions[name] = []
                ver = cfg.get('lib_version', 'Unknown')
                if ver not in self.lib_versions[name]:
                    self.lib_versions[name].append(ver)
        for name in sorted(lib_names):
            clean_name = name.replace("📚 ", "").replace("📚", "").strip()
            self.lib_combo.addItem(f"📚 {clean_name}", clean_name)
    
    def _on_lib_changed(self, text):
        clean_name = text.replace("📚 ", "")
        if hasattr(self, 'lib_versions') and clean_name in self.lib_versions:
            vers = ", ".join(sorted(self.lib_versions[clean_name], reverse=True))
            self.existing_versions_label.setText(_("Existing Versions: {vers}").format(vers=vers))
        else:
            self.existing_versions_label.setText("")
    
    def get_library_name(self) -> str:
        idx = self.lib_combo.currentIndex()
        if idx >= 0 and self.lib_combo.currentText() == self.lib_combo.itemText(idx):
            data = self.lib_combo.itemData(idx)
            if data: return str(data).strip()
        text = self.lib_combo.currentText().strip()
        return text.replace("📚", "").strip()
    
    def get_version(self) -> str:
        return self.version_edit.text().strip() or "1.0"
