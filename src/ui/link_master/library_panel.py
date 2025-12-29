"""
ライブラリ管理パネル - UI 調整版 v4

機能:
- 優先バージョンの状態を表示（緑/黄/赤）
- デプロイ/アンリンクボタンは状態に応じて切り替え
- 同ライブラリは一つだけデプロイ
- 非表示機能（名前灰色表示）
- 表示/編集ボタン正しく分離
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, 
                             QPushButton, QHBoxLayout, QMessageBox, QLabel, QMenu,
                             QInputDialog, QFrame, QComboBox, QCheckBox, QHeaderView,
                             QDialog, QFormLayout, QLineEdit, QListWidget, QListWidgetItem,
                             QTextEdit, QSplitter, QSizePolicy, QRadioButton, QButtonGroup,
                             QStyledItemDelegate)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor, QDesktopServices, QBrush, QPalette
from src.core.lang_manager import _
import json
import os
import webbrowser
import urllib.request
import urllib.error
from PyQt6.QtCore import pyqtSignal, Qt, QUrl, QTimer


class LibraryItemDelegate(QStyledItemDelegate):
    """Custom delegate to handle text colors for hidden/visible items even when selected."""
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        # Get is_hidden from item's UserRole data
        # Note: LibraryPanel sets a dict in UserRole
        item_data = index.data(Qt.ItemDataRole.UserRole)
        is_hidden = False
        if isinstance(item_data, dict):
            is_hidden = item_data.get('is_hidden', False)
            
        color = QColor("#bbbbbb") if is_hidden else QColor("#ffffff")
        # Set colors for both normal and selected states in the palette
        option.palette.setColor(QPalette.ColorRole.Text, color)
        option.palette.setColor(QPalette.ColorRole.HighlightedText, color)
        # Ensure the foreground role also matches to be triple-sure
        option.palette.setColor(QPalette.ColorRole.WindowText, color)


class LibraryPanel(QWidget):
    """ライブラリとバージョンを管理するパネル。"""
    request_register_library = pyqtSignal()
    request_deploy_library = pyqtSignal(str)
    request_unlink_library = pyqtSignal(str)
    request_edit_properties = pyqtSignal(str)
    request_view_properties = pyqtSignal(str)  # View only (no edit)
    library_changed = pyqtSignal()

    def __init__(self, parent=None, db=None):
        super().__init__(parent)
        self.db = db
        self.app_id = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Header
        self.header_lbl = QLabel(_("📚 Library Management"))
        self.header_lbl.setStyleSheet("font-weight: bold; color: #ccc; font-size: 14px;")
        layout.addWidget(self.header_lbl)
        
        # Library TreeWidget
        self.lib_tree = QTreeWidget()
        self.lib_tree.setHeaderLabels([_("Library Name"), _("Status"), _("Latest"), _("Priority"), _("Deps")])
        self.lib_tree.setColumnWidth(0, 150)
        self.lib_tree.setColumnWidth(1, 40)
        self.lib_tree.setColumnWidth(2, 60)
        self.lib_tree.setColumnWidth(3, 100)  # For 最新 text
        self.lib_tree.setColumnWidth(4, 40)
        self.lib_tree.setMinimumHeight(150)
        self.lib_tree.setRootIsDecorated(False)
        self.lib_tree.setStyleSheet("""
            QTreeWidget { background-color: #2b2b2b; border: 1px solid #444; color: #ddd; }
            QTreeWidget::item { padding: 5px; min-height: 36px; }
            QTreeWidget::item:selected { background-color: #3498db; }
            QHeaderView::section { background-color: #333; color: #eee; border: 1px solid #444; padding: 4px; }
        """)
        # Set custom delegate for consistent colors
        self.lib_tree.setItemDelegate(LibraryItemDelegate(self.lib_tree))
        self.lib_tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.lib_tree.header().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.lib_tree, 1)
        
        # Row 1: Deploy/Unlink + URL + Settings
        row1 = QHBoxLayout()
        row1.setSpacing(5)
        
        self.btn_deploy_unlink = QPushButton(_("🚀 Deploy"))
        self.btn_deploy_unlink.setStyleSheet("""
            QPushButton { background-color: #27ae60; color: white; }
            QPushButton:hover { background-color: #2ecc71; }
        """)
        self.btn_deploy_unlink.clicked.connect(self._toggle_deploy)
        row1.addWidget(self.btn_deploy_unlink)
        
        self.btn_url = QPushButton(_("🌐 URL"))
        self.btn_url.setToolTip(_("Open URL in Browser"))
        self.btn_url.setStyleSheet("""
            QPushButton { background-color: #3d3d3d; color: #e0e0e0; }
            QPushButton:hover { background-color: #5d5d5d; }
        """)
        self.btn_url.clicked.connect(self._open_url)
        row1.addWidget(self.btn_url)
        
        self.btn_settings = QPushButton(_("⚙ Settings"))
        self.btn_settings.setStyleSheet("""
            QPushButton { background-color: #3d3d3d; color: #e0e0e0; }
            QPushButton:hover { background-color: #5d5d5d; }
        """)
        self.btn_settings.clicked.connect(self._open_lib_settings)
        row1.addWidget(self.btn_settings)
        
        layout.addLayout(row1)
        
        # Row 2: Properties + Deps + Unregister
        row2 = QHBoxLayout()
        row2.setSpacing(5)
        
        self.btn_props = QPushButton(_("📋 Properties"))
        self.btn_props.setToolTip(_("Open properties of priority version"))
        self.btn_props.setStyleSheet("""
            QPushButton { background-color: #3d3d3d; color: #e0e0e0; }
            QPushButton:hover { background-color: #5d5d5d; }
        """)
        self.btn_props.clicked.connect(self._open_priority_props)
        row2.addWidget(self.btn_props)
        
        self.btn_deps = QPushButton(_("📦 Check Deps"))
        self.btn_deps.setStyleSheet("""
            QPushButton { background-color: #3d3d3d; color: #e0e0e0; }
            QPushButton:hover { background-color: #5d5d5d; }
        """)
        self.btn_deps.clicked.connect(self._open_dep_packages)
        row2.addWidget(self.btn_deps)
        
        self.btn_unregister = QPushButton(_("🗑 Unregister"))
        self.btn_unregister.setToolTip(_("Unregister selected version from library"))
        self.btn_unregister.clicked.connect(self._unregister_selected)
        row2.addWidget(self.btn_unregister)
        
        layout.addLayout(row2)
        
        # Row 3: Hide/Show + Register
        row3 = QHBoxLayout()
        row3.setSpacing(5)
        
        self.btn_hide = QPushButton(_("👁 Hide"))
        self.btn_hide.setToolTip(_("Hide from library list"))
        self.btn_hide.setStyleSheet("""
            QPushButton { background-color: #3d3d3d; color: #e0e0e0; }
            QPushButton:hover { background-color: #5d5d5d; }
        """)
        self.btn_hide.clicked.connect(self._toggle_visibility)
        row3.addWidget(self.btn_hide)
        
        self.btn_reg = QPushButton(_("🏷 Register Selected Package"))
        self.btn_reg.setToolTip(_("Register the selected folder as a library."))
        self.btn_reg.setStyleSheet("""
            QPushButton { background-color: #2980b9; color: white; padding: 5px; }
            QPushButton:hover { background-color: #3498db; }
        """)
        self.btn_reg.clicked.connect(self.request_register_library.emit)
        row3.addWidget(self.btn_reg)
        
        self.btn_refresh = QPushButton("🔄")
        self.btn_refresh.setFixedWidth(30)
        self.btn_refresh.setStyleSheet("""
            QPushButton { background-color: #3d3d3d; color: #e0e0e0; }
            QPushButton:hover { background-color: #5d5d5d; }
        """)
        self.btn_refresh.clicked.connect(self.refresh)
        row3.addWidget(self.btn_refresh)
        
        layout.addLayout(row3)

    def retranslate_ui(self):
        """Update strings for current language."""
        from src.core.lang_manager import _
        self.header_lbl.setText(_("📚 Library Management"))
        self.lib_tree.setHeaderLabels([_("Library Name"), _("Status"), _("Latest"), _("Priority"), _("Deps")])
        self.btn_deploy_unlink.setText(_("🚀 Deploy"))
        self.btn_url.setText(_("🌐 URL"))
        self.btn_url.setToolTip(_("Open URL in Browser"))
        self.btn_settings.setText(_("⚙ Settings"))
        self.btn_props.setText(_("📋 Properties"))
        self.btn_props.setToolTip(_("Open properties of priority version"))
        self.btn_deps.setText(_("📦 Check Deps"))
        self.btn_unregister.setText(_("🗑 Unregister"))
        self.btn_unregister.setToolTip(_("Unregister selected version from library"))
        self.btn_hide.setText(_("👁 Hide"))
        self.btn_hide.setToolTip(_("Hide from library list"))
        self.btn_reg.setText(_("🏷 Register Selected Package"))
        self.btn_reg.setToolTip(_("Register the selected folder as a library."))

    def set_app(self, app_id, db):
        self.app_id = app_id
        self.db = db
        self.refresh()

    def refresh(self):
        if not self.db: return
        
        all_configs = self.db.get_all_folder_configs()
        libraries = {}
        
        for rel_path, cfg in all_configs.items():
            if cfg.get('is_library', 0):
                lib_name = cfg.get('lib_name') or "Unnamed Library"
                if lib_name not in libraries: 
                    libraries[lib_name] = {'versions': [], 'any_linked': False}
                cfg['_rel_path'] = rel_path
                libraries[lib_name]['versions'].append(cfg)
                if cfg.get('last_known_status') == 'linked':
                    libraries[lib_name]['any_linked'] = True
                if cfg.get('has_logical_conflict', 0) == 1 or cfg.get('last_known_status') == 'conflict':
                    # Only mark as 'any_conflict' if ANY version has it, but used for summary?
                    # The user wants specific detection for the selected version.
                    cfg['_has_local_conflict'] = True
                    libraries[lib_name].setdefault('any_conflict', True)
                else:
                    cfg['_has_local_conflict'] = False
        
        dep_counts = self._count_dependent_packages(libraries.keys(), all_configs)
        
        # In-place update to maintain focus/expansion
        existing_items = {}
        for i in range(self.lib_tree.topLevelItemCount()):
            item = self.lib_tree.topLevelItem(i)
            item_data = item.data(0, Qt.ItemDataRole.UserRole)
            if item_data and item_data.get('name'):
                existing_items[item_data['name']] = item
        
        current_names = set(libraries.keys())
        
        for lib_name, lib_data in sorted(libraries.items()):
            versions = lib_data['versions']
            versions.sort(key=lambda x: x.get('lib_version', ''), reverse=True)
            latest_ver = versions[0].get('lib_version', 'Unknown') if versions else 'N/A'
            
            # Find priority version
            priority_ver = None
            priority_path = None
            priority_mode = 'fixed'
            
            for v in versions:
                if v.get('lib_priority', 0) > 0:
                    priority_ver = v.get('lib_version', 'Unknown')
                    priority_path = v['_rel_path']
                    priority_mode = v.get('lib_priority_mode', 'fixed')
                    break
            
            if not priority_path and versions:
                for v in versions:
                    if v.get('lib_priority_mode') == 'latest':
                        priority_mode = 'latest'
                        priority_path = versions[0]['_rel_path']
                        priority_ver = latest_ver
                        break
                if not priority_path:
                    priority_path = versions[0]['_rel_path']
                    priority_ver = latest_ver
            
            priority_cfg = next((v for v in versions if v['_rel_path'] == priority_path), None)
            priority_status = priority_cfg.get('last_known_status', 'unlinked') if priority_cfg else 'unlinked'
            # Correctly detect conflict ONLY for the selected (priority) version
            has_conflict = priority_cfg.get('_has_local_conflict', False) if priority_cfg else False
            is_hidden = bool(priority_cfg.get('lib_hidden', 0)) if priority_cfg else False
            
            # Reuse or create
            item = existing_items.get(lib_name)
            if not item:
                item = QTreeWidgetItem(self.lib_tree)
            
            # Sync Data
            item.setData(0, Qt.ItemDataRole.UserRole, {
                'type': 'library',
                'name': lib_name,
                'versions': versions,
                'priority_path': priority_path,
                'priority_status': priority_status,
                'has_conflict': has_conflict,
                'is_hidden': is_hidden
            })
            
            # Columns
            item.setText(0, f"📚 {lib_name}")
            if is_hidden:
                item.setForeground(0, QBrush(QColor("#888")))
            else:
                item.setForeground(0, QBrush(QColor("#ffffff")))
            
            if has_conflict or priority_status == 'conflict':
                item.setText(1, "🔴")
                item.setToolTip(1, _("Conflict (Occupied by another package)"))
            elif priority_status == 'linked':
                item.setText(1, "🟢")
                item.setToolTip(1, _("Deployed (Link normal)"))
            else:
                item.setText(1, "🟡")
                item.setToolTip(1, _("Not Deployed (Inactive)"))
            item.setTextAlignment(1, Qt.AlignmentFlag.AlignCenter)
            
            item.setText(2, latest_ver)
            
            # Version Dropdown
            old_combo = self.lib_tree.itemWidget(item, 3)
            if old_combo:
                # Reuse if same versions and path? Actually recreating is safer for Qt internal sync.
                # However, lets try to block signals to avoid triggering re-deploy logic if possible.
                old_combo.blockSignals(True)
            
            priority_combo = QComboBox()
            priority_combo.setStyleSheet("background: #333; color: #eee; border: 1px solid #555;")
            priority_combo.addItem(_("🔄 Latest"), "__LATEST__")
            for v in versions:
                priority_combo.addItem(v.get('lib_version', 'Unknown'), v['_rel_path'])
            
            if priority_mode == 'latest':
                priority_combo.setCurrentIndex(0)
            elif priority_path:
                idx = priority_combo.findData(priority_path)
                if idx >= 0: priority_combo.setCurrentIndex(idx)
            
            priority_combo.currentIndexChanged.connect(
                lambda idx, name=lib_name, combo=priority_combo: self._on_priority_changed(name, combo)
            )
            self.lib_tree.setItemWidget(item, 3, priority_combo)
            
            # Dep count
            item.setText(4, str(dep_counts.get(lib_name, 0)))
            item.setTextAlignment(4, Qt.AlignmentFlag.AlignCenter)
            
        # Cleanup
        for name, item in existing_items.items():
            if name not in current_names:
                root = self.lib_tree.invisibleRootItem()
                root.removeChild(item)
        
        self._update_buttons()

    def _count_dependent_packages(self, lib_names: list, all_configs: dict) -> dict:
        counts = {name: 0 for name in lib_names}
        for rel_path, cfg in all_configs.items():
            if cfg.get('is_library', 0):
                continue
            lib_deps_json = cfg.get('lib_deps', '[]')
            try:
                lib_deps = json.loads(lib_deps_json) if lib_deps_json else []
            except:
                lib_deps = []
            for dep in lib_deps:
                if isinstance(dep, dict):
                    name = dep.get('name')
                elif isinstance(dep, str):
                    name = dep
                else:
                    continue
                if name in counts:
                    counts[name] += 1
        return counts

    def _get_selected_lib_data(self):
        selected = self.lib_tree.selectedItems()
        if not selected:
            return None
        return selected[0].data(0, Qt.ItemDataRole.UserRole)

    def _on_selection_changed(self):
        self._update_buttons()

    def _update_buttons(self):
        data = self._get_selected_lib_data()
        if not data:
            self.btn_deploy_unlink.setEnabled(False)
            self.btn_deploy_unlink.setText("🚀 デプロイ")
            self.btn_deploy_unlink.setStyleSheet("""
                QPushButton { background-color: #555; color: #888; }
            """)
            self.btn_hide.setText("👁 非表示")
            return
        
        self.btn_deploy_unlink.setEnabled(True)
        
        if data.get('priority_status') == 'linked':
            self.btn_deploy_unlink.setText("🔗 アンリンク")
            self.btn_deploy_unlink.setStyleSheet("""
                QPushButton { background-color: #e67e22; color: white; }
                QPushButton:hover { background-color: #f39c12; }
            """)
        else:
            self.btn_deploy_unlink.setText("🚀 デプロイ")
            self.btn_deploy_unlink.setStyleSheet("""
                QPushButton { background-color: #27ae60; color: white; }
                QPushButton:hover { background-color: #2ecc71; }
            """)
        
        if data.get('is_hidden'):
            self.btn_hide.setText("👁 表示")
        else:
            self.btn_hide.setText("👁 非表示")

    def _on_priority_changed(self, lib_name: str, combo: QComboBox):
        selected_data = combo.currentData()
        if not selected_data or not self.db:
            return
        
        all_configs = self.db.get_all_folder_configs()
        
        if selected_data == "__LATEST__":
            for rp, cfg in all_configs.items():
                if cfg.get('lib_name') == lib_name and cfg.get('is_library', 0):
                    self.db.update_folder_display_config(rp, lib_priority=0, lib_priority_mode='latest')
        else:
            for rp, cfg in all_configs.items():
                if cfg.get('lib_name') == lib_name and cfg.get('is_library', 0):
                    if rp == selected_data:
                        self.db.update_folder_display_config(rp, lib_priority=1, lib_priority_mode='fixed')
                    else:
                        self.db.update_folder_display_config(rp, lib_priority=0, lib_priority_mode=None)
        
        self.refresh()
        for i in range(self.lib_tree.topLevelItemCount()):
            item = self.lib_tree.topLevelItem(i)
            item_data = item.data(0, Qt.ItemDataRole.UserRole)
            if item_data and item_data.get('name') == lib_name:
                self.lib_tree.setCurrentItem(item)
                break
        
        self.library_changed.emit()

    def _toggle_deploy(self):
        data = self._get_selected_lib_data()
        if not data:
            return
        
        path = data.get('priority_path')
        if not path:
            return
        
        lib_name = data.get('name')
        
        if data.get('priority_status') == 'linked':
            self.request_unlink_library.emit(path)
        else:
            all_configs = self.db.get_all_folder_configs()
            for rp, cfg in all_configs.items():
                if cfg.get('lib_name') == lib_name and cfg.get('is_library', 0):
                    if cfg.get('last_known_status') == 'linked' and rp != path:
                        self.request_unlink_library.emit(rp)
            
            self.request_deploy_library.emit(path)
        
        self.refresh()
        
        if lib_name:
            for i in range(self.lib_tree.topLevelItemCount()):
                item = self.lib_tree.topLevelItem(i)
                item_data = item.data(0, Qt.ItemDataRole.UserRole)
                if item_data and item_data.get('name') == lib_name:
                    self.lib_tree.setCurrentItem(item)
                    break

    def _open_url(self):
        """Open URL for selected library using shared utility with fallback dialog."""
        data = self._get_selected_lib_data()
        if not data or not data.get('versions'):
            return
        
        # Combine all URLs from all versions into a single URL list format
        import json
        all_url_data = []
        legacy_urls = []
        
        for v in data['versions']:
            url_list_json = v.get('url_list', '[]')
            try:
                ud = json.loads(url_list_json)
                if isinstance(ud, list):
                    all_url_data.extend(ud)
                elif isinstance(ud, dict):
                    all_url_data.extend(ud.get('urls', []))
            except: pass
            
            url = (v.get('url') or '').strip()
            if url:
                legacy_urls.append(url)
        
        # Deduplicate
        unique_urls = []
        seen = set()
        for d in all_url_data:
            u = (d.get('url') or '').strip()
            if u and u not in seen:
                unique_urls.append({'url': u, 'active': True})
                seen.add(u)
        
        for u in legacy_urls:
            if u not in seen:
                unique_urls.append({'url': u, 'active': True})
                seen.add(u)
        
        # Convert to JSON for shared utility
        combined_json = json.dumps({'urls': unique_urls, 'auto_mark': False})
        
        from src.utils.url_utils import open_first_working_url, URL_OPEN_MANAGER, URL_NO_URLS
        result = open_first_working_url(combined_json, parent=self)
        
        if result in (URL_OPEN_MANAGER, URL_NO_URLS):
            # Open library settings dialog
            self._open_lib_settings()

    def _open_priority_props(self):
        data = self._get_selected_lib_data()
        if not data:
            return
        path = data.get('priority_path')
        if path:
            self.request_edit_properties.emit(path)

    def _open_lib_settings(self):
        data = self._get_selected_lib_data()
        if not data:
            return
        # Make non-modal and keep reference to prevent garbage collection
        self._settings_dialog = LibrarySettingsDialog(self, self.db, data['name'], data['versions'])
        self._settings_dialog.setModal(False)
        self._settings_dialog.request_view_properties.connect(self.request_view_properties.emit)
        self._settings_dialog.request_edit_properties.connect(self.request_edit_properties.emit)
        self._settings_dialog.accepted.connect(self.refresh)
        self._settings_dialog.accepted.connect(self.library_changed.emit)
        self._settings_dialog.show()

    def _open_dep_packages(self):
        data = self._get_selected_lib_data()
        if not data:
            return
        # Make non-modal and keep reference to prevent garbage collection
        self._dep_dialog = DependentPackagesDialog(self, self.db, data['name'], data['versions'])
        self._dep_dialog.setModal(False)
        self._dep_dialog.request_view_properties.connect(self.request_view_properties.emit)
        self._dep_dialog.request_edit_properties.connect(self.request_edit_properties.emit)
        self._dep_dialog.request_deploy.connect(self.request_deploy_library.emit)
        self._dep_dialog.request_unlink.connect(self.request_unlink_library.emit)
        self._dep_dialog.accepted.connect(self.refresh)
        self._dep_dialog.accepted.connect(self.library_changed.emit)
        self._dep_dialog.show()

    def _unregister_selected(self):
        data = self._get_selected_lib_data()
        if not data:
            return
        path = data.get('priority_path')
        if not path:
            return
        confirm = QMessageBox.question(
            self, "ライブラリ解除", 
            f"選択中のバージョンをライブラリから解除しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.db.update_folder_display_config(path, is_library=0, lib_name=None, lib_version=None)
            self.refresh()
            self.library_changed.emit()

    def _toggle_visibility(self):
        data = self._get_selected_lib_data()
        if not data:
            return
        
        lib_name = data.get('name')
        is_hidden = data.get('is_hidden', False)
        
        all_configs = self.db.get_all_folder_configs()
        for rp, cfg in all_configs.items():
            if cfg.get('lib_name') == lib_name and cfg.get('is_library', 0):
                self.db.update_folder_display_config(rp, lib_hidden=0 if is_hidden else 1)
        
        self.refresh()
        
        for i in range(self.lib_tree.topLevelItemCount()):
            item = self.lib_tree.topLevelItem(i)
            item_data = item.data(0, Qt.ItemDataRole.UserRole)
            if item_data and item_data.get('name') == lib_name:
                self.lib_tree.setCurrentItem(item)
                break


class LibrarySettingsDialog(QDialog):
    """ライブラリの詳細設定ダイアログ"""
    request_view_properties = pyqtSignal(str)
    request_edit_properties = pyqtSignal(str)
    
    def __init__(self, parent, db, lib_name: str, versions: list):
        super().__init__(parent)
        self.db = db
        self.lib_name = lib_name
        self.versions = versions
        self.setWindowTitle(f"ライブラリ設定: {lib_name}")
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
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        
        self.name_edit = QLineEdit(self.lib_name)
        form.addRow("ライブラリ名:", self.name_edit)
        
        first_cfg = self.versions[0] if self.versions else {}
        self.url_list_json = first_cfg.get('url_list', '[]') or '[]'
        
        url_manage_layout = QHBoxLayout()
        self.url_btn = QPushButton("🌐 Manage URLs...")
        self.url_btn.clicked.connect(self._open_url_manager)
        self.url_btn.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; min-height: 24px;")
        url_manage_layout.addWidget(self.url_btn)
        
        self.url_count_label = QLabel("(0)")
        self.url_count_label.setStyleSheet("color: #888;")
        url_manage_layout.addWidget(self.url_count_label)
        url_manage_layout.addStretch()
        form.addRow("URLs:", url_manage_layout)
        self._update_url_count_preview()
        
        self.author_edit = QLineEdit(first_cfg.get('author', ''))
        form.addRow("作者:", self.author_edit)
        
        layout.addLayout(form)
        
        layout.addWidget(QLabel("登録済みバージョン:"))
        
        self.ver_tree = QTreeWidget()
        self.ver_tree.setEditTriggers(QTreeWidget.EditTrigger.DoubleClicked | QTreeWidget.EditTrigger.SelectedClicked)
        self.ver_tree.setHeaderLabels(["バージョン (編集可)", "パッケージ名", "URL", "表示", "編集", "解除"])
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
            item.setText(1, os.path.basename(v['_rel_path']))
            # Column 1 (Package Name) is explicitly not editable
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable if 1==1 else item.flags()) # Column flags apply to whole item usually, but we manage via triggers or check
            
            # URL Button
            url_btn = QPushButton("🌐")
            url_btn.setFixedSize(30, 24)
            url_btn.setToolTip("URL管理")
            url_btn.clicked.connect(lambda _, p=v['_rel_path'], c=v.get('url_list', '[]'): self._open_version_url_manager(p, c))
            self.ver_tree.setItemWidget(item, 2, url_btn)
            
            # Column 3 (View)
            view_btn = QPushButton("📋")
            view_btn.setFixedSize(30, 24)
            view_btn.setToolTip("プロパティ表示")
            view_btn.clicked.connect(lambda _, p=v['_rel_path']: self.request_view_properties.emit(p))
            self.ver_tree.setItemWidget(item, 3, view_btn)
            
            # Column 4 (Edit)
            edit_btn = QPushButton("✏")
            edit_btn.setFixedSize(30, 24)
            edit_btn.setToolTip("プロパティ編集")
            edit_btn.clicked.connect(lambda _, p=v['_rel_path']: self.request_edit_properties.emit(p))
            self.ver_tree.setItemWidget(item, 4, edit_btn)
            
            # Column 5 (Unregister)
            unreg_btn = QPushButton("🗑")
            unreg_btn.setFixedSize(30, 24)
            unreg_btn.setStyleSheet("background-color: #c0392b; color: white; padding: 0;")
            unreg_btn.clicked.connect(lambda _, p=v['_rel_path'], it=item: self._unregister_version(p, it))
            self.ver_tree.setItemWidget(item, 5, unreg_btn)
            
            # Use fixed sizes for view/edit too
            view_btn.setFixedSize(30, 24)
            view_btn.setStyleSheet("padding: 0;")
            edit_btn.setFixedSize(30, 24)
            edit_btn.setStyleSheet("padding: 0;")
            
            item.setData(0, Qt.ItemDataRole.UserRole, v['_rel_path'])
        
        layout.addWidget(self.ver_tree)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        save_btn = QPushButton("保存")
        save_btn.setStyleSheet("background-color: #27ae60; color: white;")
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("キャンセル")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
    
    def _unregister_version(self, path: str, item: QTreeWidgetItem):
        confirm = QMessageBox.question(
            self, "ライブラリ解除", 
            "このバージョンをライブラリから解除しますか？",
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
            # Update legacy url as well
            try:
                import json
                ud = json.loads(new_json)
                urls = ud if isinstance(ud, list) else ud.get('urls', [])
                if urls:
                    self.db.update_folder_display_config(path, url=urls[0].get('url'))
            except: pass

    def _save(self):
        new_lib_name = self.name_edit.text().strip()
        common_url_list = self.url_list_json
        # Also extract a single URL for legacy 'url' field
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
            
            # Update each version
            self.db.update_folder_display_config(
                path,
                lib_name=new_lib_name or self.lib_name,
                lib_version=new_ver,
                url=legacy_url, # Legacy field
                url_list=common_url_list, # Modern field
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
            if cfg.get('is_library', 0):
                continue
            
            lib_deps_json = cfg.get('lib_deps', '[]')
            try:
                lib_deps = json.loads(lib_deps_json) if lib_deps_json else []
            except:
                lib_deps = []
            
            for dep in lib_deps:
                dep_name = dep.get('name') if isinstance(dep, dict) else dep
                if dep_name != self.lib_name:
                    continue
                
                item = QTreeWidgetItem(self.tree)
                display_name = cfg.get('display_name') or os.path.basename(rel_path)
                item.setText(0, display_name)
                
                status = cfg.get('last_known_status', 'unlinked')
                item.setText(1, "🟢" if status == 'linked' else "⚪")
                item.setTextAlignment(1, Qt.AlignmentFlag.AlignCenter)
                
                # Version dropdown
                combo = QComboBox()
                combo.addItems(ver_options)
                ver_mode = dep.get('version_mode', 'latest') if isinstance(dep, dict) else 'latest'
                spec_ver = dep.get('version') if isinstance(dep, dict) else None
                if ver_mode == 'latest':
                    combo.setCurrentText("最新版")
                elif spec_ver:
                    combo.setCurrentText(spec_ver)
                combo.currentTextChanged.connect(lambda t, rp=rel_path: self._on_version_changed(rp, t))
                self.tree.setItemWidget(item, 2, combo)
                
                # Deploy/Unlink button
                if status == 'linked':
                    deploy_btn = QPushButton("🔗")
                    deploy_btn.setStyleSheet("background-color: #e67e22;")
                    deploy_btn.setToolTip("アンリンク")
                    deploy_btn.clicked.connect(lambda _, rp=rel_path: self._unlink_pkg(rp))
                else:
                    deploy_btn = QPushButton("🚀")
                    deploy_btn.setStyleSheet("background-color: #27ae60;")
                    deploy_btn.setToolTip("デプロイ")
                    deploy_btn.clicked.connect(lambda _, rp=rel_path: self._deploy_pkg(rp))
                deploy_btn.setFixedWidth(35)
                self.tree.setItemWidget(item, 3, deploy_btn)
                
                # View button - property view
                view_btn = QPushButton("📋")
                view_btn.setFixedWidth(35)
                view_btn.setToolTip("プロパティ表示")
                view_btn.clicked.connect(lambda _, rp=rel_path: self.request_view_properties.emit(rp))
                self.tree.setItemWidget(item, 4, view_btn)
                
                # Edit button - property edit
                edit_btn = QPushButton("✏")
                edit_btn.setFixedWidth(35)
                edit_btn.setToolTip("プロパティ編集")
                edit_btn.clicked.connect(lambda _, rp=rel_path: self.request_edit_properties.emit(rp))
                self.tree.setItemWidget(item, 5, edit_btn)
                
                # Remove dependency button
                remove_btn = QPushButton("🗑")
                remove_btn.setFixedWidth(35)
                remove_btn.setStyleSheet("background-color: #c0392b;")
                remove_btn.setToolTip("依存関係を解除")
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
        try:
            lib_deps = json.loads(lib_deps_json) if lib_deps_json else []
        except:
            lib_deps = []
        
        new_deps = []
        for dep in lib_deps:
            if isinstance(dep, dict) and dep.get('name') == self.lib_name:
                if version_text == "最新版":
                    new_deps.append({'name': self.lib_name, 'version_mode': 'latest'})
                else:
                    new_deps.append({'name': self.lib_name, 'version_mode': 'specific', 'version': version_text})
            elif isinstance(dep, str) and dep == self.lib_name:
                if version_text == "最新版":
                    new_deps.append({'name': self.lib_name, 'version_mode': 'latest'})
                else:
                    new_deps.append({'name': self.lib_name, 'version_mode': 'specific', 'version': version_text})
            else:
                new_deps.append(dep)
        
        self.db.update_folder_display_config(rel_path, lib_deps=json.dumps(new_deps))
    
    def _remove_dependency(self, rel_path: str):
        confirm = QMessageBox.question(
            self, "依存関係を解除", 
            f"このパッケージから「{self.lib_name}」への依存関係を解除しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        
        cfg = self.db.get_folder_config(rel_path) or {}
        lib_deps_json = cfg.get('lib_deps', '[]')
        try:
            lib_deps = json.loads(lib_deps_json) if lib_deps_json else []
        except:
            lib_deps = []
        
        new_deps = [d for d in lib_deps 
                    if not (isinstance(d, dict) and d.get('name') == self.lib_name)
                    and not (isinstance(d, str) and d == self.lib_name)]
        
        self.db.update_folder_display_config(rel_path, lib_deps=json.dumps(new_deps))
        self._load_deps()
