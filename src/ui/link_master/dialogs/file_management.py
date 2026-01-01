import os
import shutil
import json
import logging
import datetime
import ctypes
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QTreeView, QHeaderView, QMessageBox, QFrame, QLineEdit,
                             QStyledItemDelegate, QCheckBox, QFileDialog, QInputDialog,
                             QWidget)
from PyQt6.QtCore import Qt, QDir, pyqtSignal, QSortFilterProxyModel, QByteArray
from PyQt6.QtGui import QFileSystemModel, QColor, QFont, QPalette

from src.ui.window_mixins import OptionsMixin
from src.core.lang_manager import _
from src.ui.frameless_window import FramelessDialog

class CheckableFileModel(QFileSystemModel):
    """ファイルシステムモデルにチェックボックスと色分け機能を追加したもの。"""
    def __init__(self, folder_path, rules, primary_target="", secondary_target=""):
        super().__init__()
        self.folder_path = folder_path
        self.rules = rules
        self.primary_target = primary_target
        self.secondary_target = secondary_target

    def flags(self, index):
        flags = super().flags(index)
        if index.isValid() and index.column() == 0:
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        return flags

    def columnCount(self, parent=None):
        # We show 5 columns: Name, Backup, Target, Size, Modified
        return 5

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            headers = [_("Name"), _("Backup"), _("Target"), _("Size"), _("Modified")]
            if 0 <= section < len(headers):
                return headers[section]
        return super().headerData(section, orientation, role)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid(): return None
        
        abs_path = self.filePath(index)
        rel = ""
        try:
            rel = os.path.relpath(abs_path, self.folder_path).replace('\\', '/')
        except: pass

        # 1. チェックボックス (除外設定)
        if role == Qt.ItemDataRole.CheckStateRole and index.column() == 0:
            if rel == ".": return None
            return Qt.CheckState.Checked if rel not in self.rules.get("exclude", []) else Qt.CheckState.Unchecked
        
        # 2. 背景色 (状態の視覚化)
        if role == Qt.ItemDataRole.BackgroundRole:
            if rel in self.rules.get("exclude", []):
                return QColor("#5d2a2a") # Dark Red (Excluded)
            if rel in self.rules.get("overrides", {}):
                return QColor("#2a3b5d") # Dark Blue (Redirected)

        # 3. フォント (視認性向上)
        if role == Qt.ItemDataRole.FontRole:
            font = QFont()
            font.setPointSize(10)
            if index.column() == 0:
                font.setBold(True)
            return font
            
        # 4. Column Remapping
        if role == Qt.ItemDataRole.DisplayRole:
            if index.column() == 1: # Backup Status
                # Phase 28: Detect backup on disk and show actual timestamp
                backup_path = os.path.join(self.folder_path, "_Backup", rel)
                if os.path.exists(backup_path) and not os.path.isdir(backup_path):
                    import datetime
                    mtime = os.path.getmtime(backup_path)
                    backup_time = datetime.datetime.fromtimestamp(mtime).strftime("%Y/%m/%d %H:%M:%S")
                    return f"[{backup_time}]"
                return ""
            
            if index.column() == 2: # Target Path
                target_path = ""
                overrides = self.rules.get("overrides", {})
                if rel in overrides:
                    target_path = overrides[rel]
                else:
                    sorted_keys = sorted(overrides.keys(), key=len, reverse=True)
                    for old in sorted_keys:
                        new = overrides[old]
                        if rel.startswith(old + "/"):
                            target_path = rel.replace(old, new, 1)
                            break
                    else:
                        if self.primary_target:
                            target_path = os.path.join(self.primary_target, rel).replace('\\', '/')
                return f"-> {target_path}" if target_path else ""
            
            if index.column() == 3: # Size (Standard Column 1)
                return super().data(self.index(index.row(), 1, index.parent()), role)
            
            if index.column() == 4: # Date Modified (Standard Column 3)
                return super().data(self.index(index.row(), 3, index.parent()), role)

        return super().data(index, role)

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role == Qt.ItemDataRole.CheckStateRole and index.column() == 0:
            abs_path = self.filePath(index)
            try:
                rel = os.path.relpath(abs_path, self.folder_path).replace('\\', '/')
                excludes = self.rules.get("exclude", [])
                if value == Qt.CheckState.Checked or value == Qt.CheckState.Checked.value:
                    if rel in excludes: excludes.remove(rel)
                else:
                    if rel not in excludes: excludes.append(rel)
                self.rules["exclude"] = excludes
                self.dataChanged.emit(self.index(index.row(), 0), 
                                      self.index(index.row(), self.columnCount()-1))
                return True
            except: pass
        return super().setData(index, value, role)

class BackupFilterProxyModel(QSortFilterProxyModel):
    """_Backup フォルダを非表示にするためのプロキシモデル。"""
    def filterAcceptsRow(self, source_row, source_parent):
        source_index = self.sourceModel().index(source_row, 0, source_parent)
        if not source_index.isValid():
            return True
        file_name = self.sourceModel().data(source_index, Qt.ItemDataRole.DisplayRole)
        if file_name == "_Backup":
            return False
        return True

class FileManagementDialog(FramelessDialog, OptionsMixin):
    """
    個別のファイル単位での除外（チェックボックス）、場所変更（P/S/Browse）、
    バックアップ/リストアを管理するダイアログ。
    """
    def __init__(self, parent, folder_path, current_rules_json=None, primary_target="", secondary_target=""):
        super().__init__(parent)
        self.folder_path = folder_path
        self.primary_target = primary_target
        self.secondary_target = secondary_target
        self.logger = logging.getLogger("FileManagementDialog")
        
        # Parse current rules
        self.rules = {}
        if current_rules_json:
            try:
                self.rules = json.loads(current_rules_json)
            except: pass
        
        if "exclude" not in self.rules: self.rules["exclude"] = []
        if "overrides" not in self.rules: self.rules["overrides"] = self.rules.get("rename", {})
        if "backups" not in self.rules: self.rules["backups"] = {}
        
        self.setWindowTitle(_("File Management: {name}").format(name=os.path.basename(folder_path)))
        self.resize(1100, 750)
        self.load_options("file_management_dialog") # Restore geometry
        
        # FramelessDialog handled dark mode/palette
        self._apply_theme()
        self._init_ui()

    def done(self, r):
        # Save geometry and column widths before closing
        self.save_options("file_management_dialog")
        header_state = self.tree.header().saveState().toHex().data().decode()
        self.save_options("file_management_dialog_tree_widths", {"header": header_state})
        return super().done(r)

    def keyPressEvent(self, event):
        """Handle Alt+Enter for saving."""
        if event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter] and event.modifiers() & Qt.KeyboardModifier.AltModifier:
            self.accept()
            return
        super().keyPressEvent(event)

    def _apply_theme(self):
        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; color: #eee; }
            QLabel { color: #eee; }
            QFrame { background-color: #2b2b2b; border: 1px solid #444; border-radius: 4px; }
            QPushButton { 
                background-color: #3c3c3c; color: #eee; border: 1px solid #555; 
                padding: 6px 12px; border-radius: 4px; min-width: 80px;
            }
            QPushButton:hover { background-color: #4a4a4a; border: 1px solid #666; }
            QPushButton:pressed { background-color: #2d2d2d; }
            QTreeView { 
                background-color: #252526; color: #eee; border: 1px solid #333; 
                gridline-color: #333;
            }
            QTreeView::item:hover { background-color: #2a2d2e; }
            QTreeView::item:selected { background-color: #094771; color: #fff; }
            QHeaderView::section { 
                background-color: #252526; color: #ccc; border: 1px solid #333; 
                padding: 4px; font-weight: bold;
            }
            QCheckBox { color: #eee; }
            QCheckBox::indicator { width: 18px; height: 18px; }
            QInputDialog, QMessageBox { background-color: #1e1e1e; color: #eee; }
            QLineEdit { background-color: #3c3c3c; color: #eee; border: 1px solid #555; padding: 4px; }
        """)

    def _init_ui(self):
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # Define draggable area (header section) - handled by FramelessDialog
        # We can also add a title bar or just let user drag blank areas
        
        # Header Info
        header_title = QLabel(f"<b>📂 {os.path.basename(self.folder_path)}</b>")
        header_title.setText(_("<b>📂 {name}</b>").format(name=os.path.basename(self.folder_path)))
        header_title.setStyleSheet("font-size: 14pt; color: #3498db;")
        layout.addWidget(header_title)
        
        header_path = QLabel(f"Path: {self.folder_path}")
        header_path.setStyleSheet("color: #888; font-size: 9pt;")
        layout.addWidget(header_path)
        
        # Legend / Guide
        legend = QHBoxLayout()
        legend.addWidget(self._create_legend_dot("#5d2a2a", _("Excluded")))
        legend.addWidget(self._create_legend_dot("#2a3b5d", _("Redirected")))
        legend.addStretch()
        layout.addLayout(legend)

        # TreeView Setup with Custom Model
        self.model = CheckableFileModel(self.folder_path, self.rules, self.primary_target, self.secondary_target)
        self.model.setRootPath(self.folder_path)
        self.model.setFilter(QDir.Filter.NoDotAndDotDot | QDir.Filter.AllEntries)
        
        # Filter Proxy to hide _Backup
        self.proxy = BackupFilterProxyModel()
        self.proxy.setSourceModel(self.model)
        
        self.tree = QTreeView()
        self.tree.setModel(self.proxy)
        self.tree.setRootIndex(self.proxy.mapFromSource(self.model.index(self.folder_path)))
        
        # Style TreeView
        self.tree.setStyleSheet("""
            QTreeView { background-color: #2b2b2b; color: #eee; border: 1px solid #444; }
            QTreeView::item:hover { background-color: #3d3d3d; }
            QTreeView::item:selected { background-color: #3498db; color: white; }
            QHeaderView::section { background-color: #333; color: #eee; border: 1px solid #444; padding: 4px; font-weight: bold; }
            
            QPushButton#BackupBtn {
                background-color: #d35400; color: white; font-weight: bold; border-radius: 4px;
            }
            QPushButton#BackupBtn:hover { background-color: #e67e22; }
            QPushButton#BackupBtn:pressed { background-color: #a04000; }
            
            QPushButton#RestoreBtn {
                background-color: #27ae60; color: white; font-weight: bold; border-radius: 4px;
            }
            QPushButton#RestoreBtn:hover { background-color: #2ecc71; }
            QPushButton#RestoreBtn:pressed { background-color: #1e8449; }
            QPushButton#RestoreBtn:disabled { background-color: #2c3e50; color: #7f8c8d; }
        """)
        
        
        # Restore column widths or set defaults
        data = self.load_options("file_management_dialog_tree_widths")
        if data and 'header' in data:
            header_state = data['header']
            self.tree.header().restoreState(QByteArray.fromHex(header_state.encode()))
        else:
            self.tree.setColumnWidth(0, 300) # 名前
            self.tree.setColumnWidth(1, 160) # バックアップ
            self.tree.setColumnWidth(2, 300) # ターゲット
            self.tree.setColumnWidth(3, 100) # サイズ
            self.tree.setColumnWidth(4, 160) # 最終更新

        self.tree.setIndentation(12)  # Reduced for compactness per user request
        self.tree.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self.tree.setAlternatingRowColors(True)
        # Connect basic signals (Signals that don't depend on later-created buttons)
        self.model.dataChanged.connect(self._on_model_data_changed)
        self.tree.doubleClicked.connect(self._on_tree_double_clicked)
        
        layout.addWidget(self.tree)

        # Actions Panel (Selection-based)
        action_frame = QFrame()
        action_frame.setStyleSheet("background-color: #333; border-radius: 6px; border: 1px solid #444;")
        action_layout = QHBoxLayout(action_frame)
        action_layout.setContentsMargins(10, 10, 10, 10)
        
        # Section 1: Redirection
        redir_box = QVBoxLayout()
        redir_label = QLabel("<b>Redirection / Target Path</b>")
        redir_box.addWidget(redir_label)
        
        redir_btns = QHBoxLayout()
        self.btn_p = QPushButton(_("P (Primary)"))
        self.btn_p.setToolTip(_("Set to Primary Target: {target}").format(target=self.primary_target))
        self.btn_p.clicked.connect(lambda: self._set_quick_location(self.primary_target))
        self.btn_p.setStyleSheet("""
            QPushButton { background-color: #3c3c3c; color: #eee; border: 1px solid #555; border-radius: 4px; padding: 4px 8px; }
            QPushButton:hover { background-color: #4a4a4a; border: 1px solid #666; }
            QPushButton:pressed { background-color: #2b2b2b; }
        """)
        
        self.btn_s = QPushButton(_("S (Secondary)"))
        self.btn_s.setToolTip(_("Set to Secondary Target: {target}").format(target=self.secondary_target))
        self.btn_s.clicked.connect(lambda: self._set_quick_location(self.secondary_target))
        self.btn_s.setStyleSheet("""
            QPushButton { background-color: #3c3c3c; color: #eee; border: 1px solid #555; border-radius: 4px; padding: 4px 8px; }
            QPushButton:hover { background-color: #4a4a4a; border: 1px solid #666; }
            QPushButton:pressed { background-color: #2b2b2b; }
        """)
        
        self.btn_browse = QPushButton("📁 Browse...")
        self.btn_browse.clicked.connect(self._browse_location)
        self.btn_browse.setStyleSheet("""
            QPushButton { background-color: #3c3c3c; color: #eee; border: 1px solid #555; border-radius: 4px; padding: 4px 10px; }
            QPushButton:hover { background-color: #4a4a4a; border: 1px solid #666; }
            QPushButton:pressed { background-color: #2b2b2b; }
        """)
        
        redir_btns.addWidget(self.btn_p)
        redir_btns.addWidget(self.btn_s)
        redir_btns.addWidget(self.btn_browse)
        redir_box.addLayout(redir_btns)
        action_layout.addLayout(redir_box)
        
        action_layout.addSpacing(20)
        
        # Section 2: Backup Ops
        backup_box = QVBoxLayout()
        backup_label = QLabel(_("<b>Backup Operations</b>"))
        backup_box.addWidget(backup_label)
        
        backup_btns = QHBoxLayout()
        self.btn_backup = QPushButton(_("Copy to _Backup"))
        self.btn_backup.setToolTip(_("Copy file to _Backup folder and record timestamp."))
        self.btn_backup.clicked.connect(self._backup_item)
        self.btn_backup.setFixedHeight(35)
        self.btn_backup.setStyleSheet("""
            QPushButton { background-color: #3498db; color: white; font-weight: bold; border-radius: 4px; }
            QPushButton:hover { background-color: #2980b9; }
            QPushButton:pressed { background-color: #1a5276; }
        """)
        
        self.btn_restore = QPushButton(_("Restore from _Backup"))
        self.btn_restore.setToolTip(_("Restore file from _Backup folder (Overwrite)."))
        self.btn_restore.clicked.connect(self._restore_item)
        self.btn_restore.setFixedHeight(35)
        self.btn_restore.setEnabled(False) # Default disabled
        self.btn_restore.setStyleSheet("""
            QPushButton { background-color: #27ae60; color: white; font-weight: bold; border-radius: 4px; }
            QPushButton:hover { background-color: #2ecc71; }
            QPushButton:pressed { background-color: #1e8449; }
            QPushButton:disabled { background-color: #555; color: #888; }
        """)
        
        backup_btns.addWidget(self.btn_backup)
        backup_btns.addWidget(self.btn_restore)
        backup_box.addLayout(backup_btns)
        action_layout.addLayout(backup_box)
        
        layout.addWidget(action_frame)

        # Bottom Buttons
        btns = QHBoxLayout()
        btns.addStretch()
        
        btn_cancel = QPushButton(_("Cancel"))
        btn_cancel.setFixedSize(100, 35)
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)
        
        btn_save = QPushButton(_("Save Changes (Alt + Enter)"))
        btn_save.setFixedSize(220, 35)
        btn_save.setStyleSheet("background-color: #3498db; color: white; font-weight: bold; font-size: 11pt;")
        btn_save.clicked.connect(self.accept)
        btns.addWidget(btn_save)
        
        layout.addLayout(btns)
        
        self.set_content_widget(content_widget)

        self.btn_backup.setObjectName("BackupBtn")
        self.btn_restore.setObjectName("RestoreBtn")

        # Now connect selection signals after buttons are ready
        self.tree.selectionModel().selectionChanged.connect(self._update_button_states)
        # Initial check
        self._update_button_states()

    def _create_legend_dot(self, color, text):
        container = QWidget()
        l = QHBoxLayout(container)
        l.setContentsMargins(0,0,0,0)
        dot = QLabel()
        dot.setFixedSize(12, 12)
        dot.setStyleSheet(f"background-color: {color}; border-radius: 6px;")
        l.addWidget(dot)
        l.addWidget(QLabel(text))
        return container

    def get_selected_rel_paths(self):
        """Returns a list of relative paths for all selected items."""
        selected_indices = self.tree.selectionModel().selectedRows(0)
        if not selected_indices: return []
        
        rels = []
        for proxy_index in selected_indices:
            index = self.proxy.mapToSource(proxy_index)
            abs_path = self.model.filePath(index)
            try:
                rel = os.path.relpath(abs_path, self.folder_path).replace('\\', '/')
                rels.append((rel, index))
            except:
                pass
        return rels

    def get_selected_rel_path(self):
        # Legacy support for single selection methods
        res = self.get_selected_rel_paths()
        return res[0][0] if res else None

    def _set_quick_location(self, target_base):
        selected = self.get_selected_rel_paths()
        if not selected: return
        
        for rel, index in selected:
            # If target_base is the Primary target, REMOVE the override
            # to restore default deployment behavior (folder link, etc.)
            if target_base == self.primary_target:
                # Remove this item's override to use default deployment
                if rel in self.rules.get("overrides", {}):
                    del self.rules["overrides"][rel]
                    self.logger.info(f"Removed target override for {rel} (restored to default)")
            elif target_base:
                # target_base already includes the mod's target folder name (from LMFileManagementMixin)
                new_path = os.path.join(target_base, rel).replace('\\', '/')
                self.rules["overrides"][rel] = new_path
                self.logger.info(f"Set target override for {rel} -> {new_path}")
            
            self._refresh_model_row(index)

    def _browse_location(self):
        selected = self.get_selected_rel_paths()
        if not selected: return
        
        new_dir = QFileDialog.getExistingDirectory(self, "Select Target Folder")
        if not new_dir: return
        
        for rel, index in selected:
            self.rules["overrides"][rel] = new_dir.replace('\\', '/')
            self._refresh_model_row(index)

    def _backup_item(self):
        selected = self.get_selected_rel_paths()
        if not selected: return
        
        confirm = QMessageBox.question(self, _("Confirm Backup"), 
                                     _("{count} 件のアイテムを _Backup フォルダにコピー（上書き保存）しますか？").format(count=len(selected)))
        if confirm != QMessageBox.StandardButton.Yes: return

        backup_root = os.path.join(self.folder_path, "_Backup")
        success_count = 0
        
        for rel, index in selected:
            abs_path = self.model.filePath(index)
            if rel == "." or os.path.isdir(abs_path): continue 

            dest_path = os.path.join(backup_root, rel)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            
            try:
                shutil.copy2(abs_path, dest_path)
                # Phase 28: Stop recording in JSON rules (detected from disk now)
                success_count += 1
                self._refresh_model_row(index)
            except Exception as e:
                self.logger.error(f"Failed to backup {rel}: {e}")

        if success_count > 0:
            self.logger.info(f"Backed up {success_count} item(s)")
            # Phase 28: Immediate update to enable Restore button
            self._update_button_states()

    def _restore_item(self):
        selected = self.get_selected_rel_paths()
        if not selected: return
        
        confirm = QMessageBox.question(self, _("Confirm Restore"), 
                                     _("{count} 件のアイテムをバックアップから復元（上書き）しますか？").format(count=len(selected)))
        if confirm != QMessageBox.StandardButton.Yes: return
        
        backup_root = os.path.join(self.folder_path, "_Backup")
        success_count = 0
        
        for rel, index in selected:
            abs_path = self.model.filePath(index) 
            src_path = os.path.join(backup_root, rel)
            
            if not os.path.exists(src_path):
                continue
                
            try:
                shutil.copy2(src_path, abs_path)
                success_count += 1
                self._refresh_model_row(index)
            except Exception as e:
                self.logger.error(f"Failed to restore {rel}: {e}")

        if success_count > 0:
            self.logger.info(f"Restored {success_count} item(s)")
            QMessageBox.information(self, _("Success"), _("{count} 件のアイテムを復元しました。").format(count=success_count))

    def get_rules_json(self):
        # Phase 28: Remove backups from saved info
        clean_rules = self.rules.copy()
        if "backups" in clean_rules:
            del clean_rules["backups"]
        return json.dumps(clean_rules, indent=2)

    def _update_button_states(self):
        """Enable/Disable restore button based on selection backup status."""
        if not hasattr(self, 'btn_restore') or not self.btn_restore:
            return
            
        indexes = self.tree.selectionModel().selectedRows()
        can_restore = False
        
        for idx in indexes:
            # Check backup column (1)
            backup_idx = self.proxy.mapToSource(idx) # Map proxy index back to source model
            backup_status = self.model.data(self.model.index(backup_idx.row(), 1, backup_idx.parent()), Qt.ItemDataRole.DisplayRole)
            if backup_status not in ["---", None, ""]:
                can_restore = True
                break
        
        self.btn_restore.setEnabled(can_restore)

    def _on_tree_double_clicked(self, proxy_index):
        """Open paths in explorer based on column."""
        index = self.proxy.mapToSource(proxy_index)
        abs_path = self.model.filePath(index)
        col = proxy_index.column()
        
        import subprocess
        import sys
        if sys.platform != 'win32': return
        
        if col == 0: # Name column -> Open containing folder (File only per requirement)
            if os.path.exists(abs_path) and os.path.isfile(abs_path):
                subprocess.Popen(['explorer', '/select,', abs_path.replace('/', '\\')])
                
        elif col == 1: # Backup column -> Open _Backup folder
            rel = ""
            try:
                rel = os.path.relpath(abs_path, self.folder_path).replace('\\', '/')
            except: pass
            
            backup_folder = os.path.join(self.folder_path, "_Backup")
            backup_file = os.path.join(backup_folder, rel)
            
            if os.path.exists(backup_file):
                subprocess.Popen(['explorer', '/select,', backup_file.replace('/', '\\')])
            elif os.path.exists(backup_folder):
                subprocess.Popen(['explorer', backup_folder.replace('/', '\\')])

        elif col == 2: # Target column
            target_path_str = self.model.data(index, Qt.ItemDataRole.DisplayRole)
            if "->" in target_path_str:
                path = target_path_str.split("->")[-1].strip()
                if path and os.path.exists(path):
                    if os.path.isfile(path):
                        subprocess.Popen(['explorer', '/select,', path.replace('/', '\\')])
                    else:
                        subprocess.Popen(['explorer', path.replace('/', '\\')])

    def _on_model_data_changed(self, topLeft, bottomRight, roles):
        """Synchronizes checkbox states across multiple selections."""
        if Qt.ItemDataRole.CheckStateRole in roles:
            # Avoid infinite recursion
            self.model.blockSignals(True)
            try:
                new_state = topLeft.data(Qt.ItemDataRole.CheckStateRole)
                selected = self.get_selected_rel_paths()
                
                # If the changed item is among the selected ones, apply to all selected
                source_paths = [s[0] for s in selected]
                changed_index = topLeft
                changed_abs = self.model.filePath(changed_index)
                try:
                    changed_rel = os.path.relpath(changed_abs, self.folder_path).replace('\\', '/')
                    if changed_rel in source_paths:
                        excludes = self.rules.get("exclude", [])
                        for rel, idx in selected:
                            if rel == ".": continue
                            if new_state == Qt.CheckState.Checked or new_state == Qt.CheckState.Checked.value:
                                if rel in excludes: excludes.remove(rel)
                            else:
                                if rel not in excludes: excludes.append(rel)
                            # Refresh visually
                            self._refresh_model_row(idx)
                        self.rules["exclude"] = excludes
                except: pass
            finally:
                self.model.blockSignals(False)

    def _refresh_model_row(self, source_index):
        """Emits dataChanged for the entire row to force UI update."""
        if not source_index.isValid(): return
        row = source_index.row()
        parent = source_index.parent()
        # QFileSystemModel uses indices for columnCount too
        col_count = self.model.columnCount(parent)
        self.model.dataChanged.emit(
            self.model.index(row, 0, parent),
            self.model.index(row, col_count - 1, parent)
        )
