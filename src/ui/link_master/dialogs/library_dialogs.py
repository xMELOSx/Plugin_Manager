import os
import json
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
                             QPushButton, QTreeWidget, QTreeWidgetItem, QFormLayout, 
                             QLineEdit, QMessageBox)
from PyQt6.QtCore import pyqtSignal, Qt, QSize, QByteArray
from src.core.lang_manager import _

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
            QTreeWidget::item { padding: 4px; }
            QHeaderView::section { background-color: #333; color: #eee; border: 1px solid #444; padding: 4px; }
            QPushButton { background-color: #3d3d3d; color: #e0e0e0; padding: 5px 10px; min-height: 24px; }
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
        
        self.name_edit = QLineEdit(self.lib_name)
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
        
        self.author_edit = QLineEdit(first_cfg.get('author', ''))
        form.addRow(_("Author:"), self.author_edit)
        
        layout.addLayout(form)
        
        layout.addWidget(QLabel(_("Registered Versions:")))
        
        self.ver_tree = QTreeWidget()
        self.ver_tree.setEditTriggers(QTreeWidget.EditTrigger.DoubleClicked | QTreeWidget.EditTrigger.SelectedClicked)
        self.ver_tree.setHeaderLabels([_("Version (Editable)"), _("Package Name"), _("URL"), _("View"), _("Edit"), _("Unreg")])
        self.ver_tree.setColumnWidth(0, 80)
        self.ver_tree.setColumnWidth(1, 150)
        self.ver_tree.setColumnWidth(2, 120)
        self.ver_tree.setColumnWidth(3, 50)
        self.ver_tree.setColumnWidth(4, 50)
        self.ver_tree.setColumnWidth(5, 50)
        
        for v in self.versions:
            item = QTreeWidgetItem(self.ver_tree)
            item.setText(0, v.get('lib_version', 'Unknown'))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            rel_path = v.get('_rel_path') or v.get('rel_path', '')
            item.setText(1, os.path.basename(rel_path))
            
            # URL Button
            url_btn = QPushButton("🌐")
            url_btn.setFixedSize(30, 24)
            url_btn.setToolTip(_("URL Management"))
            url_btn.clicked.connect(lambda _, p=rel_path, c=v.get('url_list', '[]'): self._open_version_url_manager(p, c))
            self.ver_tree.setItemWidget(item, 2, url_btn)
            
            # Column 3 (View)
            view_btn = QPushButton("📋")
            view_btn.setFixedSize(30, 24)
            view_btn.setToolTip(_("View Properties"))
            view_btn.clicked.connect(lambda _, p=rel_path: self.request_view_properties.emit(p))
            self.ver_tree.setItemWidget(item, 3, view_btn)
            
            # Column 4 (Edit)
            edit_btn = QPushButton("✏")
            edit_btn.setFixedSize(30, 24)
            edit_btn.setToolTip(_("Edit Properties"))
            edit_btn.clicked.connect(lambda _, p=rel_path: self.request_edit_properties.emit(p))
            self.ver_tree.setItemWidget(item, 4, edit_btn)
            
            # Column 5 (Unregister)
            unreg_btn = QPushButton("🗑")
            unreg_btn.setFixedSize(30, 24)
            unreg_btn.setStyleSheet("background-color: #c0392b; color: white; padding: 0;")
            unreg_btn.clicked.connect(lambda _, p=rel_path, it=item: self._unregister_version(p, it))
            self.ver_tree.setItemWidget(item, 5, unreg_btn)
            
            item.setData(0, Qt.ItemDataRole.UserRole, rel_path)
        
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
        from src.ui.link_master.dialogs_legacy import URLListDialog
        dialog = URLListDialog(self, url_list_json=self.url_list_json)
        if dialog.exec():
            self.url_list_json = dialog.get_data()
            self._update_url_count_preview()

    def _open_version_url_manager(self, path, current_json):
        from src.ui.link_master.dialogs_legacy import URLListDialog
        dialog = URLListDialog(self, url_list_json=current_json)
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
        self.setWindowTitle(f"依存パッケージ: {lib_name}")
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
        layout.addWidget(QLabel(f"「{self.lib_name}」を使用しているパッケージ:"))
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["パッケージ", "状態", "使用", "🔗", "表示", "編集", "解除"])
        self.tree.setColumnWidth(0, 180)
        self.tree.setColumnWidth(1, 40)
        self.tree.setColumnWidth(2, 80)
        self.tree.setColumnWidth(3, 40)
        self.tree.setColumnWidth(4, 40)
        self.tree.setColumnWidth(5, 40)
        self.tree.setColumnWidth(6, 40)
        layout.addWidget(self.tree)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("閉じる")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
    
    def _load_deps(self):
        self.tree.clear()
        all_configs = self.db.get_all_folder_configs()
        ver_options = ["最新版"]
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
                
                combo = QComboBox()
                combo.addItems(ver_options)
                ver_mode = dep.get('version_mode', 'latest') if isinstance(dep, dict) else 'latest'
                spec_ver = dep.get('version') if isinstance(dep, dict) else None
                if ver_mode == 'latest': combo.setCurrentText("最新版")
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
    
    def _deploy_pkg(self, rel_path: str):
        self.request_deploy.emit(rel_path)
        self._load_deps()
    def _unlink_pkg(self, rel_path: str):
        self.request_unlink.emit(rel_path)
        self._load_deps()
    def _on_version_changed(self, rel_path: str, version_text: str):
        cfg = self.db.get_folder_config(rel_path) or {}
        lib_deps_json = cfg.get('lib_deps', '[]')
        try: lib_deps = json.loads(lib_deps_json) if lib_deps_json else []
        except: lib_deps = []
        new_deps = []
        for dep in lib_deps:
            if (isinstance(dep, dict) and dep.get('name') == self.lib_name) or (isinstance(dep, str) and dep == self.lib_name):
                if version_text == "最新版": new_deps.append({'name': self.lib_name, 'version_mode': 'latest'})
                else: new_deps.append({'name': self.lib_name, 'version_mode': 'specific', 'version': version_text})
            else: new_deps.append(dep)
        self.db.update_folder_display_config(rel_path, lib_deps=json.dumps(new_deps))
    def _remove_dependency(self, rel_path: str):
        confirm = QMessageBox.question(self, "依存関係を解除", f"このパッケージから「{self.lib_name}」への依存関係を解除しますか？", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm != QMessageBox.StandardButton.Yes: return
        cfg = self.db.get_folder_config(rel_path) or {}
        lib_deps_json = cfg.get('lib_deps', '[]')
        try: lib_deps = json.loads(lib_deps_json) if lib_deps_json else []
        except: lib_deps = []
        new_deps = [d for d in lib_deps if not (isinstance(d, dict) and d.get('name') == self.lib_name) and not (isinstance(d, str) and d == self.lib_name)]
        self.db.update_folder_display_config(rel_path, lib_deps=json.dumps(new_deps))
        self._load_deps()
