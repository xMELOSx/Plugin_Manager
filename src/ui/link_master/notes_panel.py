from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QListWidget, QListWidgetItem, 
                             QPushButton, QHBoxLayout, QLabel, QMenu, QSplitter)
from PyQt6.QtGui import QKeySequence, QShortcut
from src.ui.common_widgets import FramelessMessageBox, FramelessInputDialog, ProtectedTextEdit
from PyQt6.QtCore import pyqtSignal, Qt
from src.core.lang_manager import _
import os
import json

class NotesPanel(QWidget):
    # Signals
    note_selected = pyqtSignal(str) # note_id or filename
    request_external_edit = pyqtSignal(str)
    
    def __init__(self, parent=None, storage_path=None):
        super().__init__(parent)
        self.storage_path = storage_path # e.g. root/resource/app/[app]/notes/
        self.current_app_id = None
        self._note_order = [] # List of filenames
        self._last_saved_content = "" # For dirty check
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Header
        header = QHBoxLayout()
        self.header_lbl = QLabel(_("<b>Quick Notes</b>"), self)
        header.addWidget(self.header_lbl)
        self.btn_add = QPushButton("✚", self)
        self.btn_add.setFixedSize(28, 28)
        self.btn_add.setToolTip(_("Add New Note"))
        self.btn_add.setStyleSheet("""
            QPushButton { 
                background-color: #3b3b3b; color: #fff; font-size: 16px; 
                border: 1px solid #555; border-radius: 4px; padding: 2px;
            }
            QPushButton:hover { background-color: #4a4a4a; border-color: #777; }
            QPushButton:pressed { background-color: #222; padding-top: 4px; padding-left: 4px; }
        """)
        self.btn_add.clicked.connect(self._add_note)
        header.addWidget(self.btn_add)
        layout.addLayout(header)
        
        # Use a Splitter for List vs Editor
        self.splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.splitter.setHandleWidth(4)
        self.splitter.setStyleSheet("QSplitter::handle { background-color: #444; }")
        
        # List Container
        self.list_widget = QListWidget(self)
        self.list_widget.setStyleSheet("""
            QListWidget { background-color: #2b2b2b; border: 1px solid #444; color: #ddd; }
            QListWidget::item { padding: 4px; }
            QListWidget::item:selected { background-color: #3498db; }
        """)
        # Enable D&D reordering
        from PyQt6.QtWidgets import QAbstractItemView
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list_widget.setDragEnabled(True)
        self.list_widget.setAcceptDrops(True)
        self.list_widget.model().rowsMoved.connect(self._on_rows_moved)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        
        # Context Menu
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        
        self.splitter.addWidget(self.list_widget)
        
        # Editor Container
        self.editor_container = QWidget()
        ec_layout = QVBoxLayout(self.editor_container)
        ec_layout.setContentsMargins(0, 5, 0, 0)
        
        # Track changes for dirty state
        self.editor = ProtectedTextEdit(self)
        self.editor.textChanged.connect(self._on_editor_text_changed)
        self.editor.setPlaceholderText(_("Select a note to edit..."))
        self.editor.setStyleSheet("background-color: #222; color: #eee; border: 1px solid #444;")
        ec_layout.addWidget(self.editor, 1)
        
        # Editor Buttons
        self.editor_btns = QWidget(self)
        eb_layout = QHBoxLayout(self.editor_btns)
        eb_layout.setContentsMargins(0, 0, 0, 0)
        
        btn_style = """
            QPushButton { 
                background-color: #3b3b3b; color: #fff; font-size: 14px; 
                border: 1px solid #555; border-radius: 4px; padding: 5px 10px; 
            }
            QPushButton:hover { background-color: #4a4a4a; border-color: #777; }
            QPushButton:pressed { background-color: #222; padding-top: 7px; padding-left: 11px; }
        """
        
        self.btn_save = QPushButton(_("💾 Save"), self.editor_btns)
        self.btn_save.setMouseTracking(True)
        self.btn_save.setStyleSheet(btn_style)
        self.btn_save.clicked.connect(self._save_current_note)
        eb_layout.addWidget(self.btn_save)
        
        self.btn_external = QPushButton(_("🚀 Open Externally"), self.editor_btns)
        self.btn_external.setMouseTracking(True)
        self.btn_external.setStyleSheet(btn_style)
        self.btn_external.clicked.connect(self._open_external)
        eb_layout.addWidget(self.btn_external)
        
        ec_layout.addWidget(self.editor_btns)
        self.splitter.addWidget(self.editor_container)
        
        layout.addWidget(self.splitter, 1)

        # Initial Heights: Give list more space
        self.splitter.setSizes([300, 500])
        self.editor_container.hide()
        
        # Shortcut for Alt+Enter Save
        self.save_shortcut = QShortcut(QKeySequence("Alt+Return"), self)
        self.save_shortcut.activated.connect(self._save_current_note)
        self.save_shortcut_win = QShortcut(QKeySequence("Alt+Enter"), self)
        self.save_shortcut_win.activated.connect(self._save_current_note)

    def retranslate_ui(self):
        """Update strings for current language."""
        from src.core.lang_manager import _
        self.header_lbl.setText(_("<b>Quick Notes</b>"))
        self.btn_add.setToolTip(_("Add New Note"))
        self.editor.setPlaceholderText(_("Select a note to edit..."))
        self.btn_save.setText(_("💾 Save"))
        self.btn_external.setText(_("🚀 Open Externally"))

    def set_app(self, app_id, storage_path):
        self.current_app_id = app_id
        self.storage_path = storage_path
        if storage_path:
            os.makedirs(storage_path, exist_ok=True)
        self.refresh()

    def refresh(self):
        self.list_widget.clear()
        self.editor_container.hide()
        
        if not self.storage_path or not os.path.exists(self.storage_path):
            return
            
        # Load index/order if exists
        index_path = os.path.join(self.storage_path, "notes_index.json")
        order = []
        last_note = None
        if os.path.exists(index_path):
            try:
                with open(index_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    order = data.get("order", [])
                    last_note = data.get("last_note", None)
            except: pass
            
        files = [f for f in os.listdir(self.storage_path) if f.endswith(".txt")]
        
        # Merge order with existing files
        final_list = []
        for name in order:
            if name in files:
                final_list.append(name)
                files.remove(name)
        final_list.extend(sorted(files)) # Append new/unsorted files
        
        for n in final_list:
            item = QListWidgetItem(n)
            self.list_widget.addItem(item)
        
        # Restore last selected note
        if last_note:
            for i in range(self.list_widget.count()):
                if self.list_widget.item(i).text() == last_note:
                    self.list_widget.setCurrentRow(i)
                    self._on_item_clicked(self.list_widget.item(i))
                    break

    def is_dirty(self):
        """Check if current editor content differs from saved file."""
        if not self.editor.isVisible(): return False
        return self.editor.toPlainText() != self._last_saved_content

    def maybe_save(self):
        """Show confirmation dialog if there are unsaved changes. 
        Returns True if safe to proceed, False if user cancelled.
        """
        if not self.is_dirty(): return True
        
        from src.ui.common_widgets import FramelessMessageBox
        
        msg = FramelessMessageBox(self)
        msg.setIcon(FramelessMessageBox.Icon.Question)
        msg.setWindowTitle(_("Unsaved Changes"))
        msg.setText(_("Note '{name}' has unsaved changes.").format(name=getattr(self, 'current_note', '')))
        msg.text_lbl.setText(_("<b>{title}</b><br><br>Do you want to save your changes?").format(title=_("Unsaved Changes")))
        
        msg.addButton(_("Save"), FramelessMessageBox.StandardButton.Save, style="Blue")
        msg.addButton(_("Discard"), FramelessMessageBox.StandardButton.Discard, style="Gray")
        msg.addButton(_("Cancel"), FramelessMessageBox.StandardButton.Cancel, style="Gray")
        
        ret = msg.exec()
        if ret == FramelessMessageBox.StandardButton.Save:
            return self._save_current_note()
        elif ret == FramelessMessageBox.StandardButton.Discard:
            return True
        else: # Cancel
            return False

    def _on_editor_text_changed(self):
        """Handle text change to update UI or state if needed."""
        # We check dirty status on demand or via styling if we wanted
        pass

    def retranslate_ui(self):
        """Update strings in NotesPanel."""
        from src.core.lang_manager import _
        self.header_lbl.setText(_("<b>Quick Notes</b>"))
        self.btn_add.setToolTip(_("Add New Note"))
        self.editor.setPlaceholderText(_("Select a note to edit..."))
        self.btn_save.setText(_("💾 Save"))
        self.btn_external.setText(_("🚀 Open Externally"))

    def _add_note(self):
        if not self.storage_path: return
        name, ok = FramelessInputDialog.getText(self, _("New Note"), _("Note Name:"))
        if ok and name:
            if not name.endswith(".txt"): name += ".txt"
            path = os.path.join(self.storage_path, name)
            if not os.path.exists(path):
                with open(path, 'w', encoding='utf-8') as f:
                    f.write("")
                self.refresh()
                # Select the new one
                for i in range(self.list_widget.count()):
                    if self.list_widget.item(i).text() == name:
                        self.list_widget.setCurrentRow(i)
                        self._on_item_clicked(self.list_widget.item(i))
                        break

    def _rename_note(self, item):
        if not self.storage_path: return
        old_name = item.text()
        new_name, ok = FramelessInputDialog.getText(self, _("Rename Note"), _("New Name:"), text=old_name)
        if ok and new_name and new_name != old_name:
            if not new_name.endswith(".txt"): new_name += ".txt"
            old_path = os.path.join(self.storage_path, old_name)
            new_path = os.path.join(self.storage_path, new_name)
            
            if os.path.exists(new_path):
                msg = FramelessMessageBox(self)
                msg.setIcon(FramelessMessageBox.Icon.Warning)
                msg.setWindowTitle(_("Rename"))
                msg.setText(_("A note with that name already exists."))
                msg.exec()
                return
                
            try:
                os.rename(old_path, new_path)
                self.refresh()
                # Restore selection
                for i in range(self.list_widget.count()):
                    if self.list_widget.item(i).text() == new_name:
                        self.list_widget.setCurrentRow(i)
                        self._on_item_clicked(self.list_widget.item(i))
                        break
            except Exception as e:
                msg = FramelessMessageBox(self)
                msg.setIcon(FramelessMessageBox.Icon.Critical)
                msg.setWindowTitle(_("Error"))
                msg.setText(_("Failed to rename note: {e}").format(e=e))
                msg.exec()

    def _on_item_clicked(self, item):
        if not item: return
        
        # Check for unsaved changes before switching
        if hasattr(self, 'current_note') and self.current_note != item.text():
            if not self.maybe_save():
                # Revert selection in list_widget without triggering recursions
                self.list_widget.blockSignals(True)
                for i in range(self.list_widget.count()):
                    if self.list_widget.item(i).text() == self.current_note:
                        self.list_widget.setCurrentRow(i)
                        break
                self.list_widget.blockSignals(False)
                return

        self.current_note = item.text()
        path = os.path.join(self.storage_path, self.current_note)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                self.editor.setPlainText(content)
                self._last_saved_content = content
            self.editor_container.show()
            # Save last selected note
            self._save_last_note(self.current_note)
        except Exception as e:
            msg = FramelessMessageBox(self)
            msg.setIcon(FramelessMessageBox.Icon.Critical)
            msg.setWindowTitle(_("Error"))
            msg.setText(_("Failed to read note: {e}").format(e=e))
            msg.exec()

    def _save_current_note(self):
        if not hasattr(self, 'current_note') or not self.current_note: return False
        path = os.path.join(self.storage_path, self.current_note)
        try:
            content = self.editor.toPlainText()
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            self._last_saved_content = content
            
            # Show Toast
            from src.ui.toast import Toast
            Toast.show_toast(self, _("Note Saved!"), preset="success")
            return True
        except Exception as e:
            msg = FramelessMessageBox(self)
            msg.setIcon(FramelessMessageBox.Icon.Critical)
            msg.setWindowTitle(_("Error"))
            msg.setText(_("Failed to save note: {e}").format(e=e))
            msg.exec()
            return False

    def _open_external(self):
        if not hasattr(self, 'current_note') or not self.current_note: return
        
        # Phase 32.5: Ensure changes are saved before opening externally
        if not self.maybe_save():
            return
            
        path = os.path.join(self.storage_path, self.current_note)
        self.request_external_edit.emit(path)

    def _show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item: return
        
        menu = QMenu()
        act_open = menu.addAction(_("🚀 Open Externally"))
        act_rename = menu.addAction(_("✏ Rename"))
        act_top = menu.addAction(_("⏫ Move to Top"))
        act_bottom = menu.addAction(_("⏬ Move to Bottom"))
        menu.addSeparator()
        act_del = menu.addAction(_("🗑 Delete"))
        
        action = menu.exec(self.list_widget.viewport().mapToGlobal(pos))
        
        path = os.path.join(self.storage_path, item.text())
        if action == act_open:
            self.request_external_edit.emit(path)
        elif action == act_rename:
            self._rename_note(item)
        elif action == act_del:
            msg = FramelessMessageBox(self)
            msg.setWindowTitle(_("Delete"))
            msg.setText(_("Delete '{item_text}'?").format(item_text=item.text()))
            msg.setStandardButtons(FramelessMessageBox.StandardButton.Ok | FramelessMessageBox.StandardButton.Cancel)
            if msg.exec() == FramelessMessageBox.StandardButton.Ok:
                os.remove(path)
                self.refresh()
        elif action == act_top:
            row = self.list_widget.row(item)
            if row > 0:
                self.list_widget.takeItem(row)
                self.list_widget.insertItem(0, item)
                self.list_widget.setCurrentItem(item)
                self._save_order()
        elif action == act_bottom:
            row = self.list_widget.row(item)
            if row < self.list_widget.count() - 1:
                self.list_widget.takeItem(row)
                self.list_widget.addItem(item)
                self.list_widget.setCurrentItem(item)
                self._save_order()

    def _on_rows_moved(self, parent, start, end, destination, row):
        """Called after drag-and-drop reordering."""
        self._save_order()

    def _save_order(self):
        """Persist current list order to notes_index.json."""
        if not self.storage_path: return
        order = []
        for i in range(self.list_widget.count()):
            order.append(self.list_widget.item(i).text())
        
        index_path = os.path.join(self.storage_path, "notes_index.json")
        try:
            # Preserve last_note if exists
            existing_data = {}
            if os.path.exists(index_path):
                with open(index_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            existing_data["order"] = order
            with open(index_path, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f)
        except Exception as e:
            print(f"Failed to save notes order: {e}")

    def _save_last_note(self, note_name):
        """Persist last selected note to notes_index.json."""
        if not self.storage_path: return
        index_path = os.path.join(self.storage_path, "notes_index.json")
        try:
            existing_data = {}
            if os.path.exists(index_path):
                with open(index_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            existing_data["last_note"] = note_name
            with open(index_path, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f)
        except Exception as e:
            print(f"Failed to save last note: {e}")
