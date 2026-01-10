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
                             QStyledItemDelegate, QTreeWidgetItemIterator)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor, QDesktopServices, QBrush, QPalette
from src.core.lang_manager import _
import json
import os
import webbrowser
import urllib.request
import urllib.error
from PyQt6.QtCore import pyqtSignal, Qt, QUrl, QTimer
from src.ui.link_master.dialogs.library_dialogs import LibrarySettingsDialog, DependentPackagesDialog
from src.ui.common_widgets import StyledComboBox


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
        self.header_lbl = QLabel(_("📚 Library Management"), self)
        self.header_lbl.setStyleSheet("font-weight: bold; color: #ccc; font-size: 14px;")
        layout.addWidget(self.header_lbl)
        
        # Library TreeWidget
        class LibraryTreeWidget(QTreeWidget):
            dropped = pyqtSignal()
            def dropEvent(self, event):
                super().dropEvent(event)
                self.dropped.emit()
                
        self.lib_tree = LibraryTreeWidget(self)
        self.lib_tree.dropped.connect(self._sync_tree_to_db)
        self.lib_tree.setHeaderLabels([_("Library Name"), _("Status"), _("Latest"), _("Priority"), _("Deps")])
        self.lib_tree.setColumnWidth(0, 150)
        self.lib_tree.setColumnWidth(1, 40)
        self.lib_tree.setColumnWidth(2, 60)
        self.lib_tree.setColumnWidth(3, 100)  # For 最新 text
        self.lib_tree.setColumnWidth(4, 40)
        self.lib_tree.setMinimumHeight(150)
        self.lib_tree.setRootIsDecorated(True)  # Show folder expand/collapse arrows
        self.lib_tree.setIndentation(20)  # Slightly larger indentation
        self.lib_tree.setEditTriggers(QTreeWidget.EditTrigger.NoEditTriggers)  # Disable text editing
        self.lib_tree.setStyleSheet("""
            QTreeWidget { background-color: #2b2b2b; border: 1px solid #444; color: #ddd; outline: none; }
            QTreeWidget::item { padding: 4px 0px; min-height: 28px; }
            QTreeWidget::item:selected { background-color: #3498db; }
            QHeaderView::section { background-color: #333; color: #eee; border: none; padding: 2px 5px; min-height: 32px; font-weight: bold; }
            QComboBox { background: #333; color: #eee; border: 1px solid #555; height: 24px; font-size: 11px; margin: 2px 0px 0px 0px; }
        """)
        # Set custom delegate for consistent colors
        self.lib_tree.setItemDelegate(LibraryItemDelegate(self.lib_tree))
        self.lib_tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.lib_tree.itemDoubleClicked.connect(self._on_item_double_clicked)  # Double-click to toggle folders
        self.lib_tree.header().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lib_tree.header().setSortIndicatorClearable(True)
        self.lib_tree.setSortingEnabled(True)
        self.lib_tree.header().setSortIndicator(0, Qt.SortOrder.AscendingOrder)
        self.lib_tree.header().sectionClicked.connect(self._on_header_clicked)
        
        # Enable Drag & Drop
        self.lib_tree.setDragEnabled(True)
        self.lib_tree.setAcceptDrops(True)
        self.lib_tree.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        self.lib_tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.lib_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lib_tree.customContextMenuRequested.connect(self._show_context_menu)
        
        # Connect expansion to save state
        self.lib_tree.itemExpanded.connect(self._on_item_expanded_collapsed)
        self.lib_tree.itemCollapsed.connect(self._on_item_expanded_collapsed)
        
        layout.addWidget(self.lib_tree, 1)
        
        # Row 1: Deploy/Unlink + URL + Settings
        row1 = QHBoxLayout()
        row1.setSpacing(5)
        
        self.btn_deploy_unlink = QPushButton(_("🚀 Deploy"), self)
        self.btn_deploy_unlink.setStyleSheet("""
            QPushButton { background-color: #27ae60; color: white; }
            QPushButton:hover { background-color: #2ecc71; }
        """)
        self.btn_deploy_unlink.clicked.connect(self._toggle_deploy)
        self.btn_deploy_unlink.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        row1.addWidget(self.btn_deploy_unlink)
        
        self.btn_url = QPushButton(_("🌐 URL"), self)
        self.btn_url.setToolTip(_("Open URL in Browser"))
        self.btn_url.setStyleSheet("""
            QPushButton { background-color: #3d3d3d; color: #e0e0e0; }
            QPushButton:hover { background-color: #5d5d5d; }
        """)
        self.btn_url.clicked.connect(self._open_url)
        self.btn_url.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        row1.addWidget(self.btn_url)
        
        self.btn_settings = QPushButton(_("⚙ Settings"), self)
        self.btn_settings.setStyleSheet("""
            QPushButton { background-color: #3d3d3d; color: #e0e0e0; }
            QPushButton:hover { background-color: #5d5d5d; }
        """)
        self.btn_settings.clicked.connect(self._open_lib_settings)
        self.btn_settings.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        row1.addWidget(self.btn_settings)
        
        layout.addLayout(row1)
        
        # Row 2: Properties + Deps + Unregister
        row2 = QHBoxLayout()
        row2.setSpacing(5)
        
        self.btn_props = QPushButton(_("📋 Properties"), self)
        self.btn_props.setToolTip(_("Open properties of priority version"))
        self.btn_props.setStyleSheet("""
            QPushButton { background-color: #3d3d3d; color: #e0e0e0; }
            QPushButton:hover { background-color: #5d5d5d; }
        """)
        self.btn_props.clicked.connect(self._open_priority_props)
        self.btn_props.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        row2.addWidget(self.btn_props)
        
        self.btn_deps = QPushButton(_("📦 Check Deps"), self)
        self.btn_deps.setStyleSheet("""
            QPushButton { background-color: #3d3d3d; color: #e0e0e0; }
            QPushButton:hover { background-color: #5d5d5d; }
        """)
        self.btn_deps.clicked.connect(self._open_dep_packages)
        self.btn_deps.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        row2.addWidget(self.btn_deps)
        
        self.btn_unregister = QPushButton(_("🗑 Unregister"), self)
        self.btn_unregister.setToolTip(_("Unregister selected version from library"))
        self.btn_unregister.clicked.connect(self._unregister_selected)
        self.btn_unregister.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        row2.addWidget(self.btn_unregister)
        
        layout.addLayout(row2)
        
        # Row 3: Hide/Show + Register
        row3 = QHBoxLayout()
        row3.setSpacing(5)
        
        self.btn_hide = QPushButton(_("👁 Hide"), self)
        self.btn_hide.setToolTip(_("Hide from library list"))
        self.btn_hide.setStyleSheet("""
            QPushButton { background-color: #3d3d3d; color: #e0e0e0; }
            QPushButton:hover { background-color: #5d5d5d; }
        """)
        self.btn_hide.clicked.connect(self._toggle_visibility)
        self.btn_hide.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        row3.addWidget(self.btn_hide)

        self.btn_new_folder = QPushButton(_("📁 New Folder"), self)
        self.btn_new_folder.setToolTip(_("Create a new library folder"))
        self.btn_new_folder.setStyleSheet("""
            QPushButton { background-color: #3d3d3d; color: #e0e0e0; }
            QPushButton:hover { background-color: #5d5d5d; }
        """)
        self.btn_new_folder.clicked.connect(lambda: self._create_new_folder())
        self.btn_new_folder.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        row3.addWidget(self.btn_new_folder)
        
        self.btn_reg = QPushButton(_("🏷 Register Selected Package"), self)
        self.btn_reg.setToolTip(_("Register the selected folder as a library."))
        self.btn_reg.setStyleSheet("""
            QPushButton { background-color: #2980b9; color: white; padding: 5px; }
            QPushButton:hover { background-color: #3498db; }
        """)
        self.btn_reg.clicked.connect(self.request_register_library.emit)
        self.btn_reg.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        row3.addWidget(self.btn_reg)
        
        self.btn_refresh = QPushButton("🔄", self)
        self.btn_refresh.setFixedWidth(30)
        self.btn_refresh.setStyleSheet("""
            QPushButton { background-color: #3d3d3d; color: #e0e0e0; }
            QPushButton:hover { background-color: #5d5d5d; }
        """)
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_refresh.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        row3.addWidget(self.btn_refresh)
        self.btn_refresh.hide()  # Hidden: unclear purpose
        
        layout.addLayout(row3)

    def _on_header_clicked(self, logicalIndex):
        """Ensure sorting defaults to Ascending when a new column is clicked."""
        if self.lib_tree.header().sortIndicatorSection() != logicalIndex:
            self.lib_tree.header().setSortIndicator(logicalIndex, Qt.SortOrder.AscendingOrder)
        else:
            # Toggle logic is handled by QTreeWidget, but we can enforce Ascending as priority if needed.
            pass

    def save_state(self):
        """Save UI state like column widths."""
        if not self.db: return
        try:
            state = self.lib_tree.header().saveState().data().hex()
            self.db.set_setting(f'lib_panel_state_{self.app_id or "default"}', state)
        except Exception as e:
            print(f"Error saving lib state: {e}")

    def restore_state(self):
        """Restore UI state."""
        if not self.db: return
        try:
             state_hex = self.db.get_setting(f'lib_panel_state_{self.app_id or "default"}')
             if state_hex:
                 from PyQt6.QtCore import QByteArray
                 self.lib_tree.header().restoreState(QByteArray.fromHex(state_hex.encode()))
        except Exception as e:
            print(f"Error restoring lib state: {e}")

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
        self.btn_new_folder.setText(_("📁 New Folder"))
        self.btn_new_folder.setToolTip(_("Create a new library folder"))
        self.btn_reg.setText(_("🏷 Register Selected Package"))
        self.btn_reg.setToolTip(_("Register the selected folder as a library."))

    def set_app(self, app_id, db):
        self.app_id = app_id
        self.db = db
        self.refresh()
        self.restore_state()

    def focus_library(self, lib_name):
        """Finds and selects a library by name, ensuring it is visible."""
        if not lib_name: return
        
        # Search for library item
        iterator = QTreeWidgetItemIterator(self.lib_tree)
        while iterator.value():
            item = iterator.value()
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data and data.get('type') == 'library' and data.get('name') == lib_name:
                self.lib_tree.setCurrentItem(item)
                item.setSelected(True)
                
                # Ensure all parents are expanded
                p = item.parent()
                while p:
                    p.setExpanded(True)
                    p = p.parent()
                
                self.lib_tree.scrollToItem(item)
                self._update_buttons()
                return True
            iterator += 1
        return False

    def refresh(self):
        if not self.db: return
        
        # Fetch folders
        folders_list = self.db.get_lib_folders()
        all_configs = self.db.get_all_folder_configs()
        
        libraries = {}
        for rel_path, cfg in all_configs.items():
            if cfg.get('is_library', 0):
                lib_name = cfg.get('lib_name') or "Unnamed Library"
                if lib_name not in libraries: 
                    libraries[lib_name] = {'versions': [], 'any_linked': False, 'folder_id': None}
                
                cfg['_rel_path'] = rel_path
                libraries[lib_name]['versions'].append(cfg)
                
                # Use the first non-null folder_id found among versions
                if libraries[lib_name]['folder_id'] is None:
                    libraries[lib_name]['folder_id'] = cfg.get('lib_folder_id')
                
                if cfg.get('last_known_status') == 'linked':
                    libraries[lib_name]['any_linked'] = True
                if cfg.get('has_logical_conflict', 0) == 1 or cfg.get('last_known_status') == 'conflict':
                    cfg['_has_local_conflict'] = True
                    libraries[lib_name].setdefault('any_conflict', True)
                else:
                    cfg['_has_local_conflict'] = False
        
        dep_counts = self._count_dependent_packages(libraries.keys(), all_configs)
        
        # Save current selection before clearing
        selected_lib_name = None
        selected_folder_id = None
        current_items = self.lib_tree.selectedItems()
        if current_items:
            data = current_items[0].data(0, Qt.ItemDataRole.UserRole)
            if data:
                if data.get('type') == 'library':
                    selected_lib_name = data.get('name')
                elif data.get('type') == 'folder':
                    selected_folder_id = data.get('id')
        
        # Rebuild tree logic
        self.lib_tree.clear()
        
        folder_items = {} # folder_id -> item
        
        # 1. Create Folder items
        # Sort folders to ensure parents are created before children if we were doing recursive, 
        # but children might refer to non-yet-created parents. We'll do multiple passes or use a helper.
        
        pending_folders = list(folders_list)
        while pending_folders:
            deferred = []
            for f in pending_folders:
                parent_id = f.get('parent_id')
                if parent_id is None:
                    # Root folder
                    item = QTreeWidgetItem(self.lib_tree)
                elif parent_id in folder_items:
                    # Child of an existing folder
                    item = QTreeWidgetItem(folder_items[parent_id])
                else:
                    # Parent not yet created
                    deferred.append(f)
                    continue
                
                item.setText(0, f"📁 {f['name']}")
                item.setData(0, Qt.ItemDataRole.UserRole, {'type': 'folder', 'id': f['id'], 'name': f['name']})
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled)
                item.setExpanded(bool(f.get('is_expanded', 1)))
                folder_items[f['id']] = item
            
            if len(pending_folders) == len(deferred):
                # Circular dependency or missing parent - put rest at root
                for f in deferred:
                    item = QTreeWidgetItem(self.lib_tree)
                    item.setText(0, f"📁 {f['name']}")
                    item.setData(0, Qt.ItemDataRole.UserRole, {'type': 'folder', 'id': f['id'], 'name': f['name']})
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled)
                    item.setExpanded(bool(f.get('is_expanded', 1)))
                    folder_items[f['id']] = item
                break
            pending_folders = deferred

        # 2. Create Library items
        for lib_name, lib_data in sorted(libraries.items()):
            versions = lib_data['versions']
            versions.sort(key=lambda x: x.get('lib_version', ''), reverse=True)
            latest_ver = versions[0].get('lib_version', 'Unknown') if versions else 'N/A'
            
            # Find folder
            folder_id = lib_data.get('folder_id')
            parent_item = folder_items.get(folder_id) if folder_id else self.lib_tree
            
            # Find priority version
            priority_ver = None
            priority_path = None
            priority_mode = 'fixed'
            
            # (Logic for finding priority_path same as before)
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
            has_conflict = priority_cfg.get('_has_local_conflict', False) if priority_cfg else False
            is_hidden = bool(priority_cfg.get('lib_hidden', 0)) if priority_cfg else False
            is_favorite = bool(priority_cfg.get('is_favorite', 0)) if priority_cfg else False
            
            if isinstance(parent_item, QTreeWidget):
                item = QTreeWidgetItem(parent_item)
            else:
                item = QTreeWidgetItem(parent_item)
            
            item.setData(0, Qt.ItemDataRole.UserRole, {
                'type': 'library',
                'name': lib_name,
                'versions': versions,
                'priority_path': priority_path,
                'priority_status': priority_status,
                'has_conflict': has_conflict,
                'is_hidden': is_hidden,
                'is_favorite': is_favorite,
                'folder_id': folder_id
            })
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDragEnabled)
            
            # Columns - no prefix, just lib_name
            item.setText(0, lib_name)
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
            priority_combo = StyledComboBox()
            priority_combo.setFixedHeight(24)
            # Do NOT overwrite StyledComboBox stylesheet, just adjust font if needed
            priority_combo.setStyleSheet(priority_combo.styleSheet() + " QComboBox { font-size: 11px; margin-top: 2px; }")
            priority_combo.blockSignals(True) # Prevent DB updates during refresh
            priority_combo.addItem(_("🔄 Latest"), "__LATEST__")
            for v in versions:
                priority_combo.addItem(v.get('lib_version', 'Unknown'), v['_rel_path'])
            
            if priority_mode == 'latest':
                priority_combo.setCurrentIndex(0)
            elif priority_path:
                idx = priority_combo.findData(priority_path)
                if idx >= 0: priority_combo.setCurrentIndex(idx)
            priority_combo.blockSignals(False)
            
            priority_combo.currentIndexChanged.connect(
                lambda idx, name=lib_name, combo=priority_combo: self._on_priority_changed(name, combo)
            )
            self.lib_tree.setItemWidget(item, 3, priority_combo)
            
            # Dep count
            item.setText(4, str(dep_counts.get(lib_name, 0)))
            item.setTextAlignment(4, Qt.AlignmentFlag.AlignCenter)
        
        # Restore selection after rebuild
        if selected_lib_name or selected_folder_id:
            iterator = QTreeWidgetItemIterator(self.lib_tree)
            while iterator.value():
                item = iterator.value()
                data = item.data(0, Qt.ItemDataRole.UserRole)
                if data:
                    if selected_lib_name and data.get('type') == 'library' and data.get('name') == selected_lib_name:
                        self.lib_tree.setCurrentItem(item)
                        break
                    elif selected_folder_id and data.get('type') == 'folder' and data.get('id') == selected_folder_id:
                        self.lib_tree.setCurrentItem(item)
                        break
                iterator += 1
            
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
            self.btn_deploy_unlink.setText(_("🚀 Deploy"))
            self.btn_deploy_unlink.setStyleSheet("""
                QPushButton { background-color: #555; color: #888; }
            """)
            self.btn_hide.setText(_("👁 Hide"))
            self.btn_url.setEnabled(False)
            self.btn_settings.setEnabled(False)
            self.btn_props.setEnabled(False)
            self.btn_deps.setEnabled(False)
            self.btn_unregister.setEnabled(False)
            return
        
        # Disable library specific buttons for folders
        is_lib = data.get('type') == 'library'
        self.btn_url.setEnabled(is_lib)
        self.btn_settings.setEnabled(is_lib)
        self.btn_props.setEnabled(is_lib)
        self.btn_deps.setEnabled(is_lib)
        self.btn_unregister.setEnabled(is_lib)
        self.btn_hide.setEnabled(is_lib)

        if not is_lib:
            self.btn_deploy_unlink.setEnabled(False)
            self.btn_deploy_unlink.setText(_("🚀 Deploy"))
            self.btn_deploy_unlink.setStyleSheet("""
                QPushButton { background-color: #555; color: #888; }
            """)
            return

        self.btn_deploy_unlink.setEnabled(True)
        
        if data.get('priority_status') == 'linked':
            self.btn_deploy_unlink.setText(_("🔗 Unlink"))
            self.btn_deploy_unlink.setStyleSheet("""
                QPushButton { background-color: #e67e22; color: white; }
                QPushButton:hover { background-color: #f39c12; }
            """)
        else:
            self.btn_deploy_unlink.setText(_("🚀 Deploy"))
            self.btn_deploy_unlink.setStyleSheet("""
                QPushButton { background-color: #27ae60; color: white; }
                QPushButton:hover { background-color: #2ecc71; }
            """)
        
        if data.get('is_hidden'):
            self.btn_hide.setText(_("👁 Show"))
        else:
            self.btn_hide.setText(_("👁 Hide"))

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
        self._settings_dialog = LibrarySettingsDialog(self, self.db, data['name'], data['versions'], app_id=self.app_id)
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
            self, _("Unregister Library"), 
            _("Are you sure you want to remove the selected version from the library?"),
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

    # --- Folder Management ---
    def _show_context_menu(self, pos):
        item = self.lib_tree.itemAt(pos)
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #2b2b2b; color: #ffffff; border: 1px solid #555; }
            QMenu::item { padding: 5px 20px; color: #ffffff; }
            QMenu::item:selected { background-color: #3498db; color: white; }
            QMenu::item:disabled { color: #777; }
        """)
        
        data = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        
        new_folder_act = menu.addAction(_("📁 New Folder"))
        new_folder_act.triggered.connect(lambda: self._create_new_folder(item if data and data.get('type') == 'folder' else None))
        
        if data and data.get('type') == 'folder':
            menu.addSeparator()
            rename_act = menu.addAction(_("✏️ Rename Folder"))
            rename_act.triggered.connect(lambda: self._rename_folder(item))
            
            delete_act = menu.addAction(_("🗑 Delete Folder"))
            delete_act.triggered.connect(lambda: self._delete_folder(item))
            
        elif data and data.get('type') == 'library':
            lib_name = data.get('name', '')
            menu.addSeparator()
            # Title item
            title_act = menu.addAction(lib_name)
            title_act.setEnabled(False)
            menu.addSeparator()
            
            if data.get('priority_status') == 'linked':
                act_unlink = menu.addAction(_("🔗 Unlink"))
                act_unlink.triggered.connect(self._toggle_deploy)
            else:
                act_deploy = menu.addAction(_("🚀 Deploy"))
                act_deploy.triggered.connect(self._toggle_deploy)
            
            act_settings = menu.addAction(_("⚙ Settings"))
            act_settings.triggered.connect(self._open_lib_settings)
            
            menu.addSeparator()
            
            # Move to Folder submenu
            move_menu = menu.addMenu(_("📁 Move into Folder"))
            move_menu.setStyleSheet("""
                QMenu { background-color: #2b2b2b; color: #ffffff; border: 1px solid #555; }
                QMenu::item { padding: 5px 20px; color: #ffffff; }
            """)
            act_root = move_menu.addAction(_("(Root)"))
            act_root.triggered.connect(lambda: self._move_to_folder_by_id(lib_name, None))
            move_menu.addSeparator()
            
            folders = self.db.get_lib_folders() if self.db else []
            for f in folders:
                f_act = move_menu.addAction(f"📁 {f['name']}")
                f_act.triggered.connect(lambda checked, fid=f['id'], ln=lib_name: self._move_to_folder_by_id(ln, fid))
            
            menu.addSeparator()
            
            if data.get('is_hidden'):
                act_show = menu.addAction(_("👁 Show"))
                act_show.triggered.connect(self._toggle_visibility)
            else:
                act_hide = menu.addAction(_("👻 Hide"))
                act_hide.triggered.connect(self._toggle_visibility)
            
            menu.addSeparator()
            act_unreg = menu.addAction(_("🗑 Unregister"))
            act_unreg.triggered.connect(self._unregister_selected)
            
        menu.exec(self.lib_tree.viewport().mapToGlobal(pos))

    def _move_to_folder_by_id(self, lib_name, folder_id):
        """Move all versions of a library to a specific folder id."""
        if not self.db: return
        all_configs = self.db.get_all_folder_configs()
        for rp, cfg in all_configs.items():
            if cfg.get('lib_name') == lib_name and cfg.get('is_library', 0):
                self.db.update_folder_display_config(rp, lib_folder_id=folder_id)
        self.refresh()
        self.library_changed.emit()

    def _create_new_folder(self, parent_item=None):
        name, ok = QInputDialog.getText(self, _("New Folder"), _("Folder Name:"))
        if ok and name:
            parent_id = parent_item.data(0, Qt.ItemDataRole.UserRole).get('id') if parent_item else None
            self.db.add_lib_folder(name, parent_id)
            self.refresh()

    def _rename_folder(self, item):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        name, ok = QInputDialog.getText(self, _("Rename Folder"), _("New Name:"), QLineEdit.EchoMode.Normal, data.get('name'))
        if ok and name:
            self.db.update_lib_folder(data['id'], name=name)
            self.refresh()

    def _delete_folder(self, item):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        confirm = QMessageBox.question(
            self, _("Delete Folder"), 
            _("Delete folder '{name}'? (Contents will be moved to root)").format(name=data['name']),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.db.delete_lib_folder(data['id'])
            self.refresh()

    def _on_item_double_clicked(self, item, column):
        """Toggle folder expand/collapse on double-click."""
        if not item:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data and data.get('type') == 'folder':
            item.setExpanded(not item.isExpanded())

    def _on_item_expanded_collapsed(self, item):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data and data.get('type') == 'folder':
            self.db.update_lib_folder(data['id'], is_expanded=1 if item.isExpanded() else 0)

    def _sync_tree_to_db(self):
        """Recursively sync the entire tree structure to the database."""
        if not self.db: return
        
        def _process_item(item, parent_id, sort_order):
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if not data: return
            
            if data.get('type') == 'folder':
                folder_id = data['id']
                self.db.update_lib_folder(folder_id, parent_id=parent_id, sort_order=sort_order)
                # Process children
                for i in range(item.childCount()):
                    _process_item(item.child(i), folder_id, i)
            elif data.get('type') == 'library':
                # Update all versions of this library
                lib_name = data['name']
                versions = data.get('versions', [])
                for v in versions:
                    rp = v.get('_rel_path')
                    if rp:
                        self.db.update_folder_display_config(rp, lib_folder_id=parent_id)

        root = self.lib_tree.invisibleRootItem()
        for i in range(root.childCount()):
            _process_item(root.child(i), None, i)
        
        # Restore widgets by refreshing after move/reorder
        self.refresh()

    # To handle the drop, we'll monkey-patch or use a subclass. 
    # Since we can't easily subclass now without changing the init, let's inject a dropEvent handler if possible, 
    # but a safer way is to connect to a signal if it exists. 
    # Unfortunately QTreeWidget doesn't have a 'dropped' signal.
    # We will override the dropEvent by subclassing QTreeWidget and using it.
