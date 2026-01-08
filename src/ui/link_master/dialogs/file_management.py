import os
import shutil
import json
import logging
import datetime
import ctypes
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QTreeView, QHeaderView, QMessageBox, QFrame, QLineEdit,
                             QStyledItemDelegate, QCheckBox, QFileDialog, QInputDialog,
                             QWidget, QMenu, QApplication, QStyle, QStyleOptionViewItem)
from PyQt6.QtCore import Qt, QDir, pyqtSignal, QSortFilterProxyModel, QByteArray, QPoint
from PyQt6.QtGui import QFileSystemModel, QColor, QFont, QPalette, QAction, QIcon, QPen, QBrush

from src.ui.window_mixins import OptionsMixin
from src.core.lang_manager import _
from src.ui.frameless_window import FramelessDialog
from src.core.link_master.core_paths import get_backup_dir, get_backup_path_for_file

class SelectionAwareDelegate(QStyledItemDelegate):
    """Delegate that brightens background color for selected items, preserving state visibility."""
    def paint(self, painter, option, index):
        # Create a local copy for modification
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        
        # 1. Capture original selection/hover states
        is_selected = opt.state & QStyle.StateFlag.State_Selected
        is_hovered = opt.state & QStyle.StateFlag.State_MouseOver
        
        # 2. Get status-based background color from model
        bg_color = index.data(Qt.ItemDataRole.BackgroundRole)
        base_color = bg_color if isinstance(bg_color, QColor) else None
        
        if is_selected or is_hovered:
            # Determine "overwrite" color: Default (#444) or status-based (lighter)
            if base_color:
                if is_selected:
                    draw_color = base_color.lighter(210) # Significantly brighter
                else: # is_hovered
                    draw_color = base_color.lighter(150) # Moderately brighter
            else:
                draw_color = QColor("#444444")
            
            # 3. Leverage the "Overwriting" behavior the user noted
            # Set this color as BOTH the palette's Highlight and the background brush.
            # ALSO force the text color to white to prevent Qt from switching it to black for contrast.
            opt.palette.setColor(QPalette.ColorRole.Highlight, draw_color)
            opt.palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
            opt.palette.setColor(QPalette.ColorRole.Text, QColor("#ffffff"))
            opt.backgroundBrush = QBrush(draw_color)
            
        # 4. Delegate to base class - let it draw using our modified colors
        super().paint(painter, opt, index)

    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            # Requirements: Ensure editor text is visible (no excessive internal padding)
            editor.setStyleSheet("background-color: #2d2d2d; color: #ffffff; border: 1px solid #555; padding: 2px; margin: 0;")
        return editor

class CheckableFileModel(QFileSystemModel):
    """ファイルシステムモデルにチェックボックス、転送モード切替、ターゲット編集機能を追加したもの。"""
    def __init__(self, folder_path, storage_root, rules, primary_target="", secondary_target="", tertiary_target="", app_name=""):
        super().__init__()
        self.folder_path = folder_path
        self.storage_root = storage_root
        self.rules = rules
        self.primary_target = primary_target
        self.secondary_target = secondary_target
        self.tertiary_target = tertiary_target
        self.app_name = app_name

    def flags(self, index):
        flags = super().flags(index)
        if not index.isValid(): return flags
        if index.column() == 0:
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        elif index.column() == 3: # Target Column
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def columnCount(self, parent=None):
        # Name(0), Backup(1), Mode(2), Target(3), Size(4), Modified(5)
        return 6

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            headers = [_("名前"), _("バックアップ"), _("モード"), _("ターゲット"), _("サイズ"), _("更新日時")]
            if 0 <= section < len(headers):
                return headers[section]
        return super().headerData(section, orientation, role)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid(): return None
        
        abs_path = self.filePath(index)
        rel_from_folder = ""
        rel_from_storage = ""
        try:
            rel_from_folder = os.path.relpath(abs_path, self.folder_path).replace('\\', '/')
            rel_from_storage = os.path.relpath(abs_path, self.storage_root).replace('\\', '/')
        except: pass

        # 1. チェックボックス (除外設定)
        if role == Qt.ItemDataRole.CheckStateRole and index.column() == 0:
            if rel_from_folder == ".": return None
            return Qt.CheckState.Checked if rel_from_folder not in self.rules.get("exclude", []) else Qt.CheckState.Unchecked
        
        # 2. 背景色 (状態の視覚化)
        if role == Qt.ItemDataRole.BackgroundRole:
            if rel_from_folder in self.rules.get("exclude", []):
                return QColor("#5d2a2a") # Dark Red (Disabled/Excluded) - Reverted from Gray

            
            # Check for override
            if rel_from_folder in self.rules.get("overrides", {}):
                # Only show blue if it's NOT pointing to primary target (default)
                target = self.rules["overrides"][rel_from_folder]
                is_default_loc = False
                if self.primary_target and target:
                     expected_default = os.path.join(self.primary_target, rel_from_folder).replace('\\', '/')
                     if target == expected_default:
                         is_default_loc = True
                
                if not is_default_loc:
                    return QColor("#2a3b5d") # Dark Blue (Redirected - Non Default)


        # 3. フォント
        if role == Qt.ItemDataRole.FontRole:
            font = QFont()
            font.setPointSize(10)
            if index.column() == 0: font.setBold(True)
            return font
            
        # 4. 内容の出し分け
        if role in [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole]:
            if index.column() == 1: # Backup
                b_path = get_backup_path_for_file(self.app_name, rel_from_storage) if self.app_name else ""
                if b_path and os.path.exists(b_path) and not os.path.isdir(b_path):
                    mtime = os.path.getmtime(b_path)
                    return datetime.datetime.fromtimestamp(mtime).strftime("%Y/%m/%d %H:%M")
                return ""
            
            if index.column() == 2: # Mode (Symbolic/Copy/Default)
                overrides = self.rules.get("transfer_overrides", {})
                return overrides.get(rel_from_folder, "Default")
            
            if index.column() == 3: # Target
                overrides = self.rules.get("overrides", {})
                if rel_from_folder in overrides:
                    return overrides[rel_from_folder]
                else:
                    # Inherit from parent redirect if exists
                    sorted_keys = sorted(overrides.keys(), key=len, reverse=True)
                    for old in sorted_keys:
                        new = overrides[old]
                        if rel_from_folder.startswith(old + "/"):
                            return rel_from_folder.replace(old, new, 1)
                    
                    # App Default (Primary)
                    if self.primary_target:
                        return os.path.join(self.primary_target, rel_from_folder).replace('\\', '/')
                return ""
            
            if index.column() == 4: # Size
                return super().data(self.index(index.row(), 1, index.parent()), role)
            
            if index.column() == 5: # Modified
                return super().data(self.index(index.row(), 3, index.parent()), role)
                
        # White text for readability (Requirement: 白文字)
        if role == Qt.ItemDataRole.ForegroundRole:
            return QColor("#ffffff")

        return super().data(index, role)

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid(): return False
        
        abs_path = self.filePath(index)
        try:
            rel = os.path.relpath(abs_path, self.folder_path).replace('\\', '/')
        except: return False

        if role == Qt.ItemDataRole.CheckStateRole and index.column() == 0:
            excludes = self.rules.get("exclude", [])
            # PyQt6 safe check state comparison
            is_checked = False
            if isinstance(value, Qt.CheckState):
                is_checked = (value == Qt.CheckState.Checked)
            else:
                try:
                    # Handle int or str values
                    v_int = int(value)
                    is_checked = (v_int == Qt.CheckState.Checked.value)
                except (ValueError, TypeError):
                    # Fallback for unexpected types
                    is_checked = (str(value) == str(Qt.CheckState.Checked.value))

            if is_checked:
                if rel in excludes: excludes.remove(rel)
            else:
                if rel not in excludes: excludes.append(rel)
            self.rules["exclude"] = excludes
            self.dataChanged.emit(index, self.index(index.row(), self.columnCount()-1))
            return True

            
        if role == Qt.ItemDataRole.EditRole and index.column() == 2: # Mode Edit
            if "transfer_overrides" not in self.rules: self.rules["transfer_overrides"] = {}
            if value == "Default":
                if rel in self.rules["transfer_overrides"]: del self.rules["transfer_overrides"][rel]
            else:
                self.rules["transfer_overrides"][rel] = value
            self.dataChanged.emit(self.index(index.row(), 0), self.index(index.row(), self.columnCount()-1))
            return True

        if role == Qt.ItemDataRole.EditRole and index.column() == 3: # Target Edit
            if "overrides" not in self.rules: self.rules["overrides"] = {}
            if value:
                self.rules["overrides"][rel] = value.replace('\\', '/')
            else:
                if rel in self.rules["overrides"]: del self.rules["overrides"][rel]
            self.dataChanged.emit(self.index(index.row(), 0), self.index(index.row(), self.columnCount()-1))
            return True
            
        return super().setData(index, value, role)

class BackupFilterProxyModel(QSortFilterProxyModel):
    """_Backup フォルダやシステムファイルを非表示にするためのプロキシモデル。"""
    def filterAcceptsRow(self, source_row, source_parent):
        source_index = self.sourceModel().index(source_row, 0, source_parent)
        if not source_index.isValid():
            return True
        file_name = self.sourceModel().data(source_index, Qt.ItemDataRole.DisplayRole)
        # 以前の _Backup フォルダやシステムファイルを隠す
        if file_name in ["_Backup", ".lm_deploy_info.json", "desktop.ini"]:
            return False
        return True
""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を経由すること。
"""
"""
Link Master: File Management Dialog
"""
class FileManagementDialog(FramelessDialog, OptionsMixin):
    """
    ファイル単位の高度な構成（ターゲットパス編集、シンボリック切替、バックアップ）を行うダイアログ。
    """
    def __init__(self, parent, folder_path, current_rules_json=None, primary_target="", secondary_target="", tertiary_target="", app_name="", storage_root=""):
        super().__init__(parent)
        # Tool flag: Don't show in taskbar, stay above main window (like DebugWindow/OptionsWindow)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Tool)
        
        self.folder_path = folder_path
        self.storage_root = storage_root or folder_path
        self.primary_target = primary_target
        self.secondary_target = secondary_target
        self.tertiary_target = tertiary_target
        self.app_name = app_name
        self.logger = logging.getLogger("FileManagementDialog")
        
        # Rules Parsing
        self.rules = {}
        if current_rules_json:
            try:
                self.rules = json.loads(current_rules_json)
            except: pass
        if "exclude" not in self.rules: self.rules["exclude"] = []
        if "overrides" not in self.rules: self.rules["overrides"] = self.rules.get("rename", {})
        if "transfer_overrides" not in self.rules: self.rules["transfer_overrides"] = {}
        
        self.setWindowTitle(_("File Management: {name}").format(name=os.path.basename(folder_path)))
        self.resize(900, 600)
        self.load_options("file_management_dialog")
        
        self._apply_theme()
        self._init_ui()

    def _apply_theme(self):
        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; color: #eee; }
            QLabel { color: #eee; border: none; background: transparent; }
            /* Only apply border to content frames, not label containers */
            QFrame#ToolsFrame { background-color: transparent; border: none; }
            QPushButton { 
                background-color: #3c3c3c; color: #eee; border: 1px solid #555; 
                padding: 6px 12px; border-radius: 4px; min-width: 60px;
            }
            QPushButton:hover { background-color: #4a4a4a; border: 1px solid #666; }
            QPushButton:pressed { background-color: #2d2d2d; }
            QPushButton#ActionBtn { background-color: #3498db; font-weight: bold; }
            QPushButton#ActionBtn:hover { background-color: #2980b9; }
            
            QTreeView { 
                background-color: #1a1a1a; 
                color: #ffffff; border: 1px solid #333; 
            }

            QHeaderView::section { 
                background-color: #333; color: #ffffff; border: 1px solid #222; 
                padding: 6px; font-weight: bold;
            }
            QHeaderView { background-color: #333; color: #ffffff; }
            QLineEdit { background-color: #2d2d2d; color: #fff; border: 1px solid #444; border-radius: 4px; padding: 5px; }
            QCheckBox { color: #ccc; font-size: 10pt; }
            
            /* Tooltip styling for visibility */
            QToolTip { 
                background-color: #f0f0f0; 
                color: #000000; 
                border: 1px solid #666; 
                padding: 4px;
                font-size: 9pt;
            }
            
            QMessageBox { background-color: #2b2b2b; }
            QMessageBox QLabel { color: #ffffff !important; font-size: 11pt; min-width: 300px; padding: 10px; }
            QMessageBox QPushButton { background-color: #444; color: #fff; border: 1px solid #666; padding: 8px 20px; min-width: 80px; }
            QMessageBox QPushButton:hover { background-color: #555; }
        """)

    def _init_ui(self):
        # Phase 35: Use inherited layout from FramelessDialog instead of detached QWidget
        main_layout = self.content_layout
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)
        
        # Header
        header = QHBoxLayout()
        # Clickable Folder Icon + Title
        title_container = QWidget(self)
        title_h = QHBoxLayout(title_container)
        title_h.setContentsMargins(0,0,0,0)
        
        icon_btn = QPushButton("📂")
        icon_btn.setFixedSize(30, 30)
        icon_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; font-size: 18pt; }
            QPushButton:hover { background-color: rgba(255, 255, 255, 0.15); border-radius: 4px; }
        """)
        icon_btn.setToolTip(_("ソースフォルダを開く"))
        icon_btn.clicked.connect(lambda: os.startfile(os.path.normpath(self.folder_path)))
        title_h.addWidget(icon_btn)
        
        title = QLabel(f"<span style='font-size: 16pt; color: #ffffff; font-weight: bold;'>{os.path.basename(self.folder_path)}</span>")
        title_h.addWidget(title)
        header.addWidget(title_container)
        
        header.addStretch()
        main_layout.addLayout(header)
        
        path_info = QLabel(_("Source: {path}").format(path=self.folder_path))
        path_info.setOpenExternalLinks(True)
        path_info.setStyleSheet("color: #888; font-family: 'Consolas'; font-size: 9pt;")
        main_layout.addWidget(path_info)

        # Legend (Below Source, Simplified)
        legend_layout = QHBoxLayout()
        legend_layout.addWidget(self._create_legend_dot("#2a3b5d", _("リダイレクト済み (青)")))
        legend_layout.addSpacing(15)
        legend_layout.addWidget(self._create_legend_dot("#5d2a2a", _("無効 (赤)"))) # Reverted to Red
        legend_layout.addStretch()
        main_layout.addLayout(legend_layout)

        # Main Tree Initialization
        self.model = CheckableFileModel(self.folder_path, self.storage_root, self.rules, 
                                        self.primary_target, self.secondary_target, self.tertiary_target, self.app_name)
        self.model.setRootPath(self.folder_path)
        
        self.proxy = BackupFilterProxyModel()
        self.proxy.setSourceModel(self.model)
        
        self.tree = QTreeView()
        self.tree.setMouseTracking(True)
        self.tree.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.tree.setItemDelegate(SelectionAwareDelegate(self.tree))
        self.tree.setModel(self.proxy)
        self.tree.setRootIndex(self.proxy.mapFromSource(self.model.index(self.folder_path)))
        self.tree.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self.tree.setAlternatingRowColors(True)

        self.tree.setStyleSheet("""
            QTreeView {
                background-color: #1a1a1a; 
                alternate-background-color: #242424;
                color: #ffffff; border: 1px solid #333; 
            }
            QTreeView::item {
                padding: 4px;
            }
            QLineEdit {
                background-color: #252525;
                color: #ffffff;
                border: 1px solid #555;
                selection-background-color: #3498db;
            }
            /* Header styling - MUST be inside tree stylesheet */
            QHeaderView::section {
                background-color: #333;
                color: #ffffff;
                border: 1px solid #222;
                padding: 6px;
                font-weight: bold;
            }
            QHeaderView {
                background-color: #333;
                color: #ffffff;
            }
        """)
        self.tree.setEditTriggers(QTreeView.EditTrigger.DoubleClicked | QTreeView.EditTrigger.SelectedClicked | QTreeView.EditTrigger.EditKeyPressed)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        # Establish Column Widths
        self.tree.setColumnWidth(0, 320) # 名前 (Name)
        self.tree.setColumnWidth(1, 140) # バックアップ (Backup)
        self.tree.setColumnWidth(2, 80)  # モード (Mode)
        self.tree.setColumnWidth(3, 400) # ターゲット (Target)
        self.tree.setColumnWidth(4, 90)  # サイズ (Size)
        
        # Try to restore user preference, but clamp minimum to prevent "collapsed" UI
        header_state = self.load_options("file_management_dialog_tree_widths")
        if header_state and 'header' in header_state:
            self.tree.header().restoreState(QByteArray.fromHex(header_state['header'].encode()))
            if self.tree.columnWidth(0) < 50: # Fail-safe
                self.tree.setColumnWidth(0, 320)
                self.tree.setColumnWidth(3, 400)

        # Tree Container
        self.tree_container = QWidget()
        tree_sub_layout = QVBoxLayout(self.tree_container)
        tree_sub_layout.setContentsMargins(0, 0, 0, 0)
        tree_sub_layout.addWidget(self.tree)
        
        main_layout.addWidget(self.tree_container, 1) # Add tree with stretch

        # Toolbar / Quick Actions
        tools_frame = QFrame(self)
        tools_frame.setObjectName("ToolsFrame")
        tools_layout = QVBoxLayout(tools_frame)
        tools_layout.setSpacing(12)
        main_layout.addWidget(tools_frame) # Add tools below tree

        LABEL_WIDTH = 110 # For alignment - defined here for batch header

        # Section Header: 一括設定 - Aligned with デフォルト button left edge
        batch_header_row = QHBoxLayout()
        batch_header_row.setContentsMargins(0, 0, 0, 0)
        batch_header_row.setSpacing(0)
        # Create a dummy label to match spacing of rows below it
        dummy_label = QLabel()
        dummy_label.setFixedWidth(LABEL_WIDTH)
        dummy_label.setMargin(0)
        batch_header_row.addWidget(dummy_label)
        batch_header_row.addSpacing(12) 
        
        batch_header = QLabel(_("<b>選択アイテム操作</b>"))
        batch_header.setStyleSheet("color: #ffffff; font-size: 11pt; padding: 2px 0;")
        batch_header_row.addWidget(batch_header)
        batch_header_row.addStretch()
        tools_layout.addLayout(batch_header_row)

        LABEL_WIDTH = 110 # For alignment

        def create_aligned_label(text):
            lbl = QLabel(text)
            lbl.setFixedWidth(LABEL_WIDTH)
            lbl.setStyleSheet("color: #ffffff; font-weight: bold;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return lbl

        # Row 1: モード (Mode) - デフォルト | シンボリック | コピー
        mode_row = QHBoxLayout()
        mode_row.setContentsMargins(0, 0, 0, 0)
        mode_row.setSpacing(12) # Use 12 between all items
        mode_row.addWidget(create_aligned_label(_("モード:")))
        
        # Mode buttons: Standardized width 110px
        mode_configs = [
            (_("デフォルト"), "Default", "#444", "#666"),
            (_("シンボリック"), "symlink", "#2980b9", "#2980b9"),
            (_("コピー"), "copy", "#0e4b7b", "#0e4b7b"),
        ]
        for m_lbl, m_val, m_bg, m_border in mode_configs:
            btn = QPushButton(m_lbl)
            btn.setStyleSheet(f"""
                QPushButton {{ 
                    background-color: {m_bg}; color: white; font-weight: bold; 
                    min-width: 110px; max-width: 110px; padding: 6px 12px; border: 2px solid {m_border}; border-radius: 4px;
                }}
                QPushButton:hover {{ background-color: #555; border: 2px solid #888; }}
                QPushButton:pressed {{ background-color: #333; }}
            """)
            btn.clicked.connect(lambda _, m=m_val: self._apply_mode_batch(m))
            mode_row.addWidget(btn)
        
        mode_row.addStretch()
        tools_layout.addLayout(mode_row)
        
        # Row 2: ファイル操作 (File Operations) - 有効化 | 無効化 | バックアップ | 復元
        file_ops_row = QHBoxLayout()
        file_ops_row.setContentsMargins(0, 0, 0, 0)
        file_ops_row.setSpacing(12)
        file_ops_row.addWidget(create_aligned_label(_("ファイル操作:")))
        
        # Operations: Unified width 110px
        btn_enable = QPushButton(_("有効化"))
        btn_enable.setStyleSheet("""
            QPushButton { 
                background-color: #444; color: white; font-weight: bold; 
                min-width: 110px; max-width: 110px; padding: 6px 12px; border: 2px solid #666; border-radius: 4px;
            }
            QPushButton:hover { background-color: #555; border: 2px solid #888; }
            QPushButton:pressed { background-color: #333; }
        """)
        btn_enable.clicked.connect(lambda: self._set_enabled_batch(True))
        file_ops_row.addWidget(btn_enable)
        
        btn_disable = QPushButton(_("無効化"))
        btn_disable.setStyleSheet("""
            QPushButton { 
                background-color: #a93226; color: white; font-weight: bold; 
                min-width: 110px; max-width: 110px; padding: 6px 12px; border: 2px solid #a93226; border-radius: 4px;
            }
            QPushButton:hover { background-color: #c0392b; border: 2px solid #e74c3c; }
            QPushButton:pressed { background-color: #7b241c; }
        """)
        btn_disable.clicked.connect(lambda: self._set_enabled_batch(False))
        file_ops_row.addWidget(btn_disable)
        
        self.btn_backup = QPushButton(_("バックアップ"))
        self.btn_backup.setStyleSheet("""
            QPushButton {
                background-color: #e67e22; color: white; font-weight: bold;
                min-width: 110px; max-width: 110px; padding: 6px 12px; border: 2px solid #e67e22; border-radius: 4px;
            }
            QPushButton:hover { background-color: #d35400; border: 2px solid #e67e22; }
            QPushButton:pressed { background-color: #b94500; }
        """)
        self.btn_backup.clicked.connect(self._backup_item)
        file_ops_row.addWidget(self.btn_backup)
        
        self.btn_restore = QPushButton(_("復元"))
        self.btn_restore.setStyleSheet("""
            QPushButton {
                background-color: #27ae60; color: white; font-weight: bold;
                min-width: 110px; max-width: 110px; padding: 6px 12px; border: 2px solid #27ae60; border-radius: 4px;
            }
            QPushButton:hover { background-color: #219a52; border: 2px solid #27ae60; }
            QPushButton:pressed { background-color: #1a7a40; }
        """)
        self.btn_restore.clicked.connect(self._restore_item)
        file_ops_row.addWidget(self.btn_restore)
        
        file_ops_row.addStretch()
        tools_layout.addLayout(file_ops_row)
        
        # Row 3: ターゲット (Target) - プライマリ | セカンダリ | ターシャリ
        target_row = QHBoxLayout()
        target_row.setContentsMargins(0, 0, 0, 0)
        target_row.setSpacing(12)
        target_row.addWidget(create_aligned_label(_("ターゲット:")))
        
        # Target buttons: Unified 110px
        target_configs = [
            (_("プライマリ"), self.primary_target, "#555", "#666"),
            (_("セカンダリ"), self.secondary_target, "#2980b9", "#2980b9"),
            (_("ターシャリ"), self.tertiary_target, "#8e44ad", "#8e44ad"),
        ]
        for t_lbl, t_val, t_bg, t_border in target_configs:
            btn = QPushButton(t_lbl)
            btn.setStyleSheet(f"""
                QPushButton {{ 
                    background-color: {t_bg}; color: white; font-weight: bold; 
                    min-width: 110px; max-width: 110px; padding: 6px 12px; border: 2px solid {t_border}; border-radius: 4px;
                }}
                QPushButton:hover {{ background-color: #666; border: 2px solid #888; }}
                QPushButton:pressed {{ background-color: #333; }}
                QPushButton:disabled {{ background-color: #333; color: #666; border: 2px solid #444; }}
            """)
            btn.setToolTip(t_val or _("未設定"))
            if not t_val: btn.setEnabled(False)
            btn.clicked.connect(lambda _, v=t_val: self._apply_target_batch(v))
            target_row.addWidget(btn)
        
        target_row.addStretch()
        tools_layout.addLayout(target_row)
        
        # Row 4: 任意パス (Manual Path) - Input + Folder Icon + 適用
        manual_row = QHBoxLayout()
        manual_row.addWidget(create_aligned_label(_("任意パス:")))
        manual_row.addSpacing(12)
        
        self.target_edit = QLineEdit()
        self.target_edit.setPlaceholderText(_("任意パス"))
        self.target_edit.setStyleSheet("background-color: #2d2d2d; color: #ffffff; border: 1px solid #555; padding: 5px; border-radius: 4px;")
        self.target_edit.setText(self.primary_target)
        manual_row.addWidget(self.target_edit, 1)
        
        btn_browse_target = QPushButton("📁")
        btn_browse_target.setFixedWidth(35)
        btn_browse_target.setStyleSheet("""
            QPushButton {
                background-color: #e67e22; color: white; font-size: 14pt;
                border: none; border-radius: 4px; padding: 4px;
            }
            QPushButton:hover { background-color: #d35400; }
        """)
        btn_browse_target.setToolTip(_("フォルダを選択"))
        btn_browse_target.clicked.connect(self._browse_manual_target)
        manual_row.addWidget(btn_browse_target)
        
        self.btn_apply_redir = QPushButton(_("適用"))
        self.btn_apply_redir.setStyleSheet("""
            QPushButton {
                background-color: #2980b9; color: white; font-weight: bold;
                min-width: 80px; padding: 6px 12px; border: none; border-radius: 4px;
            }
            QPushButton:hover { background-color: #3498db; }
            QPushButton:pressed { background-color: #1a5276; }
        """)
        self.btn_apply_redir.clicked.connect(self._apply_manual_redirect)
        manual_row.addWidget(self.btn_apply_redir)
        
        tools_layout.addLayout(manual_row)
        main_layout.addWidget(tools_frame)




        # Footer
        footer = QHBoxLayout()
        footer.addStretch()
        
        btn_cancel = QPushButton(_("キャンセル"))
        btn_cancel.setFixedWidth(160)
        btn_cancel.setFixedHeight(35)
        # Force visible style for cancel button
        btn_cancel.setStyleSheet("background-color: #444; color: white; border: 1px solid #555; border-radius: 4px;")
        btn_cancel.clicked.connect(self.reject)
        footer.addWidget(btn_cancel)
        
        btn_save = QPushButton(_("変更を反映して閉じる (Alt+Enter)"))
        btn_save.setFixedWidth(200) # Slightly wider text
        btn_save.setFixedHeight(35)
        btn_save.setStyleSheet("background-color: #3498db; color: white; font-weight: bold; border-radius: 4px;")
        btn_save.clicked.connect(self.accept)
        footer.addWidget(btn_save)
        main_layout.addLayout(footer)
        

        
        # Phase 35: Layout is already in self.content_layout, no need for set_content_widget
        
        # Double click on Tree
        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; border: 1px solid #444; }
            QTreeView { background-color: #1e1e1e; border: 1px solid #444; color: #ddd; }
            QLineEdit { background-color: #2b2b2b; color: #fff; border: 1px solid #555; }
        """)
        # Double click on Tree
        self.tree.doubleClicked.connect(self._on_tree_double_clicked)

    def _apply_target_batch(self, target_root):
        """Apply a target root preset (P, S, or T) to selected items."""
        selected = self.get_selected_items()
        if not selected: return
        
        for rel, s_idx in selected:
            if target_root:
                # Calculate new path: root + relative path from original folder
                new_path = os.path.join(target_root, rel).replace('\\', '/')
                self.model.setData(s_idx.siblingAtColumn(3), new_path, Qt.ItemDataRole.EditRole)
            else:
                # Clear override
                self.model.setData(s_idx.siblingAtColumn(3), "", Qt.ItemDataRole.EditRole)
        
        # Force refresh to show changes immediately
        self.tree.viewport().update()

    def _apply_mode_batch(self, mode):
        """Apply a transfer mode (Default, symlink, copy) to selected items."""
        selected = self.get_selected_items()
        if not selected: return
        
        for rel, s_idx in selected:
            self.model.setData(s_idx.siblingAtColumn(2), mode, Qt.ItemDataRole.EditRole)
        
        # Force refresh to show changes immediately
        self.tree.viewport().update()

    def _set_enabled_batch(self, enabled: bool):
        """Set enabled/disabled state for selected items (add/remove from exclude list)."""
        selected = self.get_selected_items()
        if not selected: return
        
        for rel, s_idx in selected:
            if rel == ".": continue
            # Use CheckStateRole to toggle exclude state
            new_state = Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked
            self.model.setData(s_idx.siblingAtColumn(0), new_state, Qt.ItemDataRole.CheckStateRole)
        
        # Force refresh to show changes immediately
        self.tree.viewport().update()

    def _show_context_menu(self, pos):
        """Show context menu based on which column was clicked."""
        from PyQt6.QtGui import QAction
        idx = self.tree.indexAt(pos)
        if not idx.isValid(): return
        
        # Get the column that was clicked
        column = idx.column()
        
        menu = QMenu(self)
        
        if column == 0:  # Name column -> Source folder
            action = QAction(_("エクスプローラーで開く (ソース)"), self)
            action.triggered.connect(lambda: self._open_in_explorer(idx, mode='source'))
            menu.addAction(action)
            
        elif column == 1:  # Backup column -> Backup folder
            action = QAction(_("エクスプローラーで開く (バックアップ)"), self)
            action.triggered.connect(lambda: self._open_in_explorer(idx, mode='backup'))
            menu.addAction(action)
            
        elif column == 3:  # Target column -> Target folder
            action = QAction(_("エクスプローラーで開く (ターゲット)"), self)
            action.triggered.connect(lambda: self._open_in_explorer(idx, mode='target'))
            menu.addAction(action)
            
        else:  # Other columns: default to source
            action = QAction(_("エクスプローラーで開く (ソース)"), self)
            action.triggered.connect(lambda: self._open_in_explorer(idx, mode='source'))
            menu.addAction(action)
        
        menu.exec(self.tree.mapToGlobal(pos))

    def _open_in_explorer(self, p_idx, mode='source'):
        """Open source, backup, or target in Windows explorer.
        
        Args:
            p_idx: Proxy model index
            mode: 'source', 'backup', or 'target'
        """
        import subprocess
        s_idx = self.proxy.mapToSource(p_idx)
        path = None
        
        if mode == 'source':
            path = self.model.filePath(s_idx)
        elif mode == 'backup':
            # Get relative path for backup lookup
            abs_path = self.model.filePath(s_idx)
            try:
                rel_from_storage = os.path.relpath(abs_path, self.storage_root).replace('\\', '/')
            except:
                rel_from_storage = None
            
            if rel_from_storage and self.app_name:
                path = get_backup_path_for_file(self.app_name, rel_from_storage)
        elif mode == 'target':
            path = self.model.data(s_idx.siblingAtColumn(3), Qt.ItemDataRole.DisplayRole)
        
        if not path:
            QMessageBox.warning(self, _("エラー"), _("パスが見つかりません。"))
            return
            
        norm_path = os.path.normpath(path)
        
        # If path doesn't exist, find the closest existing parent
        if not os.path.exists(norm_path):
            original_path = norm_path
            while norm_path and not os.path.exists(norm_path):
                parent = os.path.dirname(norm_path)
                if parent == norm_path:  # Reached root
                    break
                norm_path = parent
            
            if not os.path.exists(norm_path):
                QMessageBox.warning(self, _("エラー"), 
                    _("パスが存在しません: {path}").format(path=original_path))
                return
        
        # Open in explorer
        if os.path.isfile(norm_path):
            subprocess.Popen(['explorer', '/select,', norm_path])
        else:
            subprocess.Popen(['explorer', norm_path])

        self.btn_backup.setObjectName("BackupBtn")
        self.btn_restore.setObjectName("RestoreBtn")

        # Now connect selection signals after buttons are ready
        self.tree.selectionModel().selectionChanged.connect(self._update_button_states)
        # Initial check
        self._update_button_states()

    def _update_button_states(self):
        selected = self.get_selected_items()
        has_selection = len(selected) > 0
        
        # Enable actions only if something is selected
        if hasattr(self, 'btn_backup'): self.btn_backup.setEnabled(has_selection)
        if hasattr(self, 'btn_restore'): self.btn_restore.setEnabled(has_selection)

    def _switch_to_source(self):
        """Switch TreeView to Source (Storage) folder."""
        self.btn_view_source.setChecked(True)
        self.btn_view_target.setChecked(False)
        self.model.setRootPath(self.folder_path)
        self.tree.setRootIndex(self.proxy.mapFromSource(self.model.index(self.folder_path)))

    def _switch_to_target(self):
        """Switch TreeView to Target (Symlink) folder if it exists."""
        target_path = self.primary_target
        if not target_path or not os.path.exists(target_path):
             QMessageBox.information(self, _("ターゲット"), _("ターゲットパスが未設定、または存在しません。"))
             self.btn_view_source.setChecked(True)
             self.btn_view_target.setChecked(False)
             return
             
        self.btn_view_source.setChecked(False)
        self.btn_view_target.setChecked(True)
        self.model.setRootPath(target_path)
        self.tree.setRootIndex(self.proxy.mapFromSource(self.model.index(target_path)))

    def _on_tree_double_clicked(self, proxy_idx):
        if hasattr(self, 'btn_apply_redir'): self.btn_apply_redir.setEnabled(has_selection)
        if hasattr(self, 'btn_toggle_mode'): self.btn_toggle_mode.setEnabled(has_selection)

    def _create_legend_dot(self, color, text):
        container = QWidget(self)
        l = QHBoxLayout(container)
        l.setContentsMargins(0,0,0,0)
        dot = QLabel()
        dot.setFixedSize(12, 12)
        dot.setStyleSheet(f"background-color: {color}; border-radius: 6px;")
        l.addWidget(dot)
        # Use HTML for guaranteed white text (bypasses CSS cascade issues)
        text_lbl = QLabel(f"<span style='color: #ffffff;'>{text}</span>")
        l.addWidget(text_lbl)
        return container

    def get_selected_items(self):
        idxs = self.tree.selectionModel().selectedRows(0)
        items = []
        for p_idx in idxs:
            s_idx = self.proxy.mapToSource(p_idx)
            abs_p = self.model.filePath(s_idx)
            try:
                rel = os.path.relpath(abs_p, self.folder_path).replace('\\', '/')
                items.append((rel, s_idx))
            except: pass
        return items

    def _apply_manual_redirect(self):
        """Apply manual target path to selected items. Always appends filename to folder targets."""
        target = self.target_edit.text().strip().replace('\\', '/')
        if not target: return
        
        selected = self.get_selected_items()
        if not selected:
            return

        for rel, s_idx in selected:
            if rel == ".": continue
            
            # Always append filename - this is the core safety fix.
            # User wants folder paths to always get file appended.
            base_name = os.path.basename(rel)
            
            # If target does NOT end with the filename, append it.
            if not target.rstrip('/').lower().endswith(base_name.lower()):
                resolved_target = os.path.join(target, base_name).replace('\\', '/')
            else:
                resolved_target = target
            
            if resolved_target == self.primary_target:
                if rel in self.rules.get("overrides", {}): del self.rules["overrides"][rel]
            else:
                self.rules["overrides"][rel] = resolved_target
            
            self._refresh_row(s_idx)

    def _browse_manual_target(self):
        path = QFileDialog.getExistingDirectory(self, _("ターゲットフォルダを選択"))
        if path:
            self.target_edit.setText(path.replace('\\', '/'))

    def _apply_mode_override(self):
        mode = "symlink" if self.cb_symbolic.isChecked() else "copy"
        selected = self.get_selected_items()
        for rel, s_idx in selected:
            if rel == ".": continue
            self.rules["transfer_overrides"][rel] = mode
            self._refresh_row(s_idx)

    def _backup_item(self):
        selected = self.get_selected_items()
        if not selected: return
        
        msg = QMessageBox(self)
        msg.setWindowTitle(_("バックアップの確認"))
        msg.setText(_("{count} 件のアイテムをバックアップしますか？\n（既存のバックアップは上書きされます）").format(count=len(selected)))
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setIcon(QMessageBox.Icon.Question)
        if msg.exec() != QMessageBox.StandardButton.Yes: return

        backup_root = get_backup_dir(self.app_name) if self.app_name else ""
        if not backup_root: return

        count = 0
        for rel, s_idx in selected:
            abs_p = self.model.filePath(s_idx)
            if rel == "." or os.path.isdir(abs_p): continue
            
            try:
                rel_from_storage = os.path.relpath(abs_p, self.storage_root).replace('\\', '/')
            except: rel_from_storage = rel
            
            dest = os.path.join(backup_root, rel_from_storage)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            try:
                shutil.copy2(abs_p, dest)
                count += 1
                self._refresh_row(s_idx)
            except Exception as e:
                self.logger.error(f"Backup failed for {rel}: {e}")
                
        if count > 0:
            QMessageBox.information(self, _("完了"), _("{n} 件のバックアップを完了しました。").format(n=count))

    def _restore_item(self):
        selected = self.get_selected_items()
        if not selected: return
        
        msg = QMessageBox(self)
        msg.setWindowTitle(_("復元の確認"))
        msg.setText(_("{count} 件のアイテムをバックアップから復元しますか？\n（現在のファイルは上書きされます）").format(count=len(selected)))
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setIcon(QMessageBox.Icon.Warning)
        if msg.exec() != QMessageBox.StandardButton.Yes: return

        backup_root = get_backup_dir(self.app_name) if self.app_name else ""
        count = 0
        for rel, s_idx in selected:
            abs_p = self.model.filePath(s_idx)
            try:
                rel_from_storage = os.path.relpath(abs_p, self.storage_root).replace('\\', '/')
            except: rel_from_storage = rel
            
            src = os.path.join(backup_root, rel_from_storage)
            if os.path.exists(src):
                try:
                    shutil.copy2(src, abs_p)
                    count += 1
                    self._refresh_row(s_idx)
                except Exception as e:
                    self.logger.error(f"Restore failed: {e}")
                    
        if count > 0:
            QMessageBox.information(self, _("完了"), _("{n} 件の復元が完了しました。").format(n=count))

    def _refresh_row(self, s_idx):
        if not s_idx.isValid(): return
        self.model.dataChanged.emit(self.model.index(s_idx.row(), 0, s_idx.parent()),
                                    self.model.index(s_idx.row(), self.model.columnCount()-1, s_idx.parent()))

    def _on_tree_double_clicked(self, p_idx):
        if QApplication.keyboardModifiers() == Qt.KeyboardModifier.AltModifier:
            self._open_in_explorer(p_idx)
            return
        pass

    def get_rules_json(self):
        return json.dumps(self.rules, indent=2)

    def done(self, r):
        self.save_options("file_management_dialog")
        header_state = self.tree.header().saveState().toHex().data().decode()
        self.save_options("file_management_dialog_tree_widths", {"header": header_state})
        return super().done(r)
