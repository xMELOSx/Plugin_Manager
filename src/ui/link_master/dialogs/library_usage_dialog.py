from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTreeWidget, QTreeWidgetItem, QComboBox,
                             QMessageBox, QHeaderView)
from PyQt6.QtCore import Qt
from src.core.lang_manager import _
from src.ui.common_widgets import StyledComboBox
import json

class LibraryUsageDialog(QDialog):
    """
    パッケージが使用するライブラリを設定するダイアログ。
    利用可能なライブラリ一覧を表示し、依存関係を定義します。
    """
    def __init__(self, parent, db, current_deps_json):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle(_("Library Settings"))
        self.resize(600, 500)
        
        # Parse current dependencies
        # format: [{"name": "LibName", "version_mode": "latest"|"priority"|"specific", "version": "v1.0"}, ...]
        self.current_deps = []
        if current_deps_json:
            try:
                self.current_deps = json.loads(current_deps_json)
            except: pass
            
        self._init_ui()
        self._load_libraries()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("<b>📦 Library Dependencies</b>"))
        layout.addWidget(QLabel(_("Select libraries this package uses.")))
        
        # Tree: Library Name | Included? | Version Mode | Specific Version
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([_("Library Name"), _("Version Mode"), _("Specific Version")])
        self.tree.setColumnWidth(0, 200)
        self.tree.setColumnWidth(1, 150)
        
        layout.addWidget(self.tree)
        
        # Buttons
        btns = QHBoxLayout()
        btns.addStretch()
        
        btn_cancel = QPushButton(_("Cancel"))
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)
        
        btn_save = QPushButton(_("Save"))
        btn_save.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold;")
        btn_save.clicked.connect(self._save)
        btns.addWidget(btn_save)
        
        layout.addLayout(btns)
        
        # Style
        self.setStyleSheet("""
            QDialog { background-color: #2b2b2b; color: #ddd; }
            QTreeWidget { background-color: #222; border: 1px solid #444; color: #eee; }
            QHeaderView::section { background-color: #333; color: #eee; border: none; padding: 4px; }
            QComboBox { background-color: #333; color: #eee; border: 1px solid #555; }
        """)

    def _load_libraries(self):
        all_configs = self.db.get_all_folder_configs()
        
        # Group by Library Name (skip hidden libraries)
        libraries = {}  # name -> [versions]
        hidden_libs = set()
        
        # First pass: find hidden libraries
        for rel, cfg in all_configs.items():
            if cfg.get('is_library', 0) and cfg.get('lib_hidden', 0):
                name = cfg.get('lib_name')
                if name:
                    hidden_libs.add(name)
        
        # Second pass: collect non-hidden libraries
        for rel, cfg in all_configs.items():
            if cfg.get('is_library', 0):
                name = cfg.get('lib_name') or "Unnamed"
                if name in hidden_libs:
                    continue  # Skip hidden libraries
                libraries.setdefault(name, []).append({
                    'version': cfg.get('lib_version') or 'Unknown',
                    'rel_path': rel
                })
        
        # Populate Tree
        for lib_name in sorted(libraries.keys()):
            item = QTreeWidgetItem(self.tree)
            item.setText(0, lib_name)
            item.setCheckState(0, Qt.CheckState.Unchecked)
            
            # Find if currently used
            existing = next((d for d in self.current_deps if d.get('name') == lib_name), None)
            
            if existing:
                item.setCheckState(0, Qt.CheckState.Checked)
            
            # Version Mode Combo: 優先 (use global priority version) or 任意 (choose specific)
            combo_mode = StyledComboBox()
            combo_mode.addItems([_("Preferred"), _("Specific")])
            if existing:
                mode = existing.get('version_mode', 'priority')
                if mode == 'priority' or mode == 'latest': 
                    combo_mode.setCurrentIndex(0)  # Preferred
                elif mode == 'specific': 
                    combo_mode.setCurrentIndex(1)  # Specific
            else:
                combo_mode.setCurrentIndex(0) # Default to Preferred
                
            self.tree.setItemWidget(item, 1, combo_mode)
            
            # Specific Version Combo
            combo_ver = StyledComboBox()
            versions = sorted([v['version'] for v in libraries[lib_name]], reverse=True)
            combo_ver.addItems(versions)
            if existing and existing.get('version'):
                combo_ver.setCurrentText(existing.get('version'))
            
            # Enable/Disable based on mode - 任意 only
            combo_ver.setEnabled(combo_mode.currentIndex() == 1)  # Index 1 = Specific
            combo_mode.currentIndexChanged.connect(lambda idx, c=combo_ver: c.setEnabled(idx == 1))
            
            self.tree.setItemWidget(item, 2, combo_ver)
            item.setData(0, Qt.ItemDataRole.UserRole, lib_name)

    def _save(self):
        new_deps = []
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            if item.checkState(0) == Qt.CheckState.Checked:
                lib_name = item.data(0, Qt.ItemDataRole.UserRole)
                
                combo_mode = self.tree.itemWidget(item, 1)
                mode_text = combo_mode.currentText()
                mode = 'priority'
                if combo_mode.currentIndex() == 0: mode = 'priority'  # Preferred
                elif combo_mode.currentIndex() == 1: mode = 'specific'  # Specific
                
                combo_ver = self.tree.itemWidget(item, 2)
                ver = combo_ver.currentText()
                
                new_deps.append({
                    "name": lib_name,
                    "version_mode": mode,
                    "version": ver
                })
                
        self.result_json = json.dumps(new_deps)
        self.accept()

    def get_result_json(self):
        return getattr(self, 'result_json', '[]')
