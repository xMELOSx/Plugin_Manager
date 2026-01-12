from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, 
                             QPushButton, QHBoxLayout, QLabel, QMenu,
                             QAbstractItemView)
from src.ui.common_widgets import FramelessMessageBox, FramelessInputDialog
from PyQt6.QtCore import pyqtSignal, Qt
from src.core.lang_manager import _
from src.core.link_master.database import get_lm_db

# Constants for item types
ITEM_TYPE_FOLDER = 1
ITEM_TYPE_PRESET = 2


class PresetTreeWidget(QTreeWidget):
    """Custom QTreeWidget with proper drop handling for preset folders."""
    
    items_reordered = pyqtSignal()  # Emitted after any drag-drop operation
    
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def dropEvent(self, event):
        """Handle drop - only allow presets to be children of folders, not other presets."""
        target_item = self.itemAt(event.position().toPoint())
        
        if target_item:
            target_type = target_item.data(0, Qt.ItemDataRole.UserRole + 1)
            # Don't allow dropping onto a preset (only onto folders or empty space)
            if target_type == ITEM_TYPE_PRESET:
                # Find the parent folder of the target, or root
                parent = target_item.parent()
                if parent:
                    # Re-parent to the folder, not the preset
                    pass  # Let default behavior handle sibling placement
                # Allow normal sibling reordering
        
        super().dropEvent(event)
        self.items_reordered.emit()


class PresetsPanel(QWidget):
    load_preset = pyqtSignal(int)   # preset_id
    delete_preset = pyqtSignal(int) # preset_id
    create_preset = pyqtSignal()    # Signal to create new preset
    preview_preset = pyqtSignal(int)  # Emit preset_id when preset is selected (for preview highlights)
    clear_filter = pyqtSignal()       # Phase 18.11: Clear preset filter
    unload_request_signal = pyqtSignal() # New: Request unloading all links
    order_changed = pyqtSignal(list)    # Emit list of [preset_id] in new order
    edit_preset_properties = pyqtSignal(int) # Emit preset_id


    def __init__(self, parent=None, db=None):
        super().__init__(parent)
        self.current_app_id = None
        self.db = db  # Can be passed in constructor or set via set_db()
        self._init_ui()

    def set_db(self, db):
        """Set the DB instance from parent window."""
        self.db = db


    def _init_ui(self):
        from src.ui.styles import ButtonStyles
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Header
        self.header_lbl = QLabel(_("<b>Presets</b>"), self)
        self.header_lbl.setStyleSheet("font-weight: bold; color: #ccc;")
        layout.addWidget(self.header_lbl)
        
        # Tree Widget (Custom class for proper drag-drop handling)
        self.tree_widget = PresetTreeWidget(self)
        self.tree_widget.setHeaderHidden(True)
        self.tree_widget.setIndentation(12)  # Reduce indentation for compact display
        self.tree_widget.setStyleSheet("""
            QTreeWidget {
                background-color: #2b2b2b;
                border: 1px solid #444;
                color: #ddd;
            }
            QTreeWidget::item {
                padding: 4px;
            }
            QTreeWidget::item:selected {
                background-color: #3498db;
            }
        """)
        
        # Enable drag-and-drop
        self.tree_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.tree_widget.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.tree_widget.setDragEnabled(True)
        self.tree_widget.setAcceptDrops(True)
        self.tree_widget.setDropIndicatorShown(True)
        
        self.tree_widget.itemClicked.connect(self._on_item_selected)
        self.tree_widget.itemExpanded.connect(self._on_item_expanded)
        self.tree_widget.itemCollapsed.connect(self._on_item_collapsed)
        self.tree_widget.items_reordered.connect(self._save_order_and_folders)
        
        # Context Menu
        self.tree_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self._show_context_menu)
        
        layout.addWidget(self.tree_widget)

        # Buttons Cluster (Bottom)
        
        # Buttons Row 1: Deploy / Unlink (Upper row of the set)
        btn_layout2 = QHBoxLayout()
        btn_layout2.setContentsMargins(0, 5, 0, 0)
        
        self.btn_load = QPushButton(_("🚀 Deploy"), self)
        self.btn_load.clicked.connect(self._on_load_clicked)
        self.btn_load.setStyleSheet(ButtonStyles.SUCCESS)
        btn_layout2.addWidget(self.btn_load, 1) # Set stretch to 1
        
        self.btn_unload = QPushButton(_("🔓 Unlink"), self)
        self.btn_unload.clicked.connect(lambda: self.unload_request_signal.emit())
        self.btn_unload.setStyleSheet(ButtonStyles.PRIMARY)
        self.btn_unload.setToolTip(_("Remove all active links for this app"))
        btn_layout2.addWidget(self.btn_unload, 1)
        
        layout.addLayout(btn_layout2)
        
        # Buttons Row 2: Create / Folder / Delete (Lower row of the set)
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 5, 0, 5)
        
        # Create Preset Button (Restored)
        self.btn_add = QPushButton(_("💾 Create"), self)
        self.btn_add.clicked.connect(self.create_preset.emit)
        self.btn_add.setStyleSheet(ButtonStyles.PRIMARY)
        btn_layout.addWidget(self.btn_add)
        
        # Folder button for organizing presets
        self.btn_folder = QPushButton(_("📁 Folder"), self)
        self.btn_folder.setStyleSheet(ButtonStyles.DEFAULT)
        self.btn_folder.clicked.connect(self._on_create_folder_clicked)
        btn_layout.addWidget(self.btn_folder)
        
        self.btn_del = QPushButton(_("🗑 Delete"), self)
        self.btn_del.clicked.connect(self._on_delete_clicked)
        self.btn_del.setStyleSheet(ButtonStyles.DANGER)
        btn_layout.addWidget(self.btn_del)
        
        layout.addLayout(btn_layout)

        # Clear Filter Button (shown when filter is active)
        self.clear_filter_btn = QPushButton(_("🔓 Clear Filter"), self)
        self.clear_filter_btn.clicked.connect(lambda: self.clear_filter.emit())
        self.clear_filter_btn.setStyleSheet(ButtonStyles.WARNING)
        self.clear_filter_btn.hide()
        layout.addWidget(self.clear_filter_btn)
    
    def retranslate_ui(self):
        """Update strings for current language."""
        from src.core.lang_manager import _
        self.header_lbl.setText(_("<b>Presets</b>"))
        self.btn_folder.setText(_("📁 Folder"))
        self.btn_del.setText(_("🗑 Delete"))
        self.btn_load.setText(_("🚀 Deploy"))
        self.btn_unload.setText(_("🔓 Unlink"))
        self.btn_unload.setToolTip(_("Remove all active links for this app"))
        self.clear_filter_btn.setText(_("🔓 Clear Filter"))

    def _on_save_clicked(self):
        self.create_preset.emit()

    def _on_create_folder_clicked(self):
        """Create a folder to organize presets."""
        from src.core.lang_manager import _
        name, ok = FramelessInputDialog.getText(self, _("Create Folder"), _("Folder Name:"))
        if ok and name and self.db:
            self.db.create_preset_folder(name)
            self.refresh()

    def set_app(self, app_id: int):
        self.current_app_id = app_id
        self.refresh()

    def refresh(self, preserve_selection=True):
        """Refresh the tree, optionally preserving current selection."""
        # Store current selection for restoration
        selected_preset_id = None
        if preserve_selection:
            current = self.tree_widget.currentItem()
            if current and current.data(0, Qt.ItemDataRole.UserRole + 1) == ITEM_TYPE_PRESET:
                selected_preset_id = current.data(0, Qt.ItemDataRole.UserRole)
        
        self.tree_widget.clear()
        if not self.current_app_id or not self.db: return
        
        # Get folders and presets
        folders = self.db.get_preset_folders()
        presets = self.db.get_presets()
        
        # Create folder items and a map
        folder_items = {}
        for f in folders:
            item = QTreeWidgetItem(self.tree_widget)
            item.setText(0, f"📁 {f['name']}")
            item.setData(0, Qt.ItemDataRole.UserRole, f['id'])
            item.setData(0, Qt.ItemDataRole.UserRole + 1, ITEM_TYPE_FOLDER)
            # Folders can accept drops
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDropEnabled)
            item.setExpanded(f.get('is_expanded', 1) == 1)
            folder_items[f['id']] = item
        
        # Sort presets by sort_order
        presets.sort(key=lambda x: (x.get('sort_order', 0), x['name'].lower()))
        
        # Add presets to their folders or root
        for p in presets:
            folder_id = p.get('folder_id')
            if folder_id and folder_id in folder_items:
                parent = folder_items[folder_id]
            else:
                parent = self.tree_widget.invisibleRootItem()
            
            item = QTreeWidgetItem(parent)
            item.setText(0, p['name'])
            item.setData(0, Qt.ItemDataRole.UserRole, p['id'])
            item.setData(0, Qt.ItemDataRole.UserRole + 1, ITEM_TYPE_PRESET)
            item.setToolTip(0, p.get('description', ''))
            # Presets cannot accept drops (prevent becoming folders)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDropEnabled)
        
        # Restore selection
        if selected_preset_id is not None:
            self.focus_preset(selected_preset_id)

    def focus_preset(self, preset_id):
        """Select and scroll to the preset with the given ID."""
        iterator = self._iterate_all_items()
        for item in iterator:
            if (item.data(0, Qt.ItemDataRole.UserRole + 1) == ITEM_TYPE_PRESET and
                item.data(0, Qt.ItemDataRole.UserRole) == preset_id):
                self.tree_widget.setCurrentItem(item)
                self.tree_widget.scrollToItem(item)
                # Expand parent if in folder
                parent = item.parent()
                if parent:
                    parent.setExpanded(True)
                break
    
    def _iterate_all_items(self):
        """Iterator for all items in tree (including children)."""
        root = self.tree_widget.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            yield item
            for j in range(item.childCount()):
                yield item.child(j)

    def _on_item_selected(self, item, column):
        """Emit preview signal when preset is clicked (before loading)."""
        if item:
            item_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
            if item_type == ITEM_TYPE_PRESET:
                preset_id = item.data(0, Qt.ItemDataRole.UserRole)
                self.preview_preset.emit(preset_id)
    
    def _on_item_expanded(self, item):
        """Save expanded state for folders."""
        if item.data(0, Qt.ItemDataRole.UserRole + 1) == ITEM_TYPE_FOLDER:
            folder_id = item.data(0, Qt.ItemDataRole.UserRole)
            if self.db:
                self.db.update_preset_folder(folder_id, is_expanded=1)
    
    def _on_item_collapsed(self, item):
        """Save collapsed state for folders."""
        if item.data(0, Qt.ItemDataRole.UserRole + 1) == ITEM_TYPE_FOLDER:
            folder_id = item.data(0, Qt.ItemDataRole.UserRole)
            if self.db:
                self.db.update_preset_folder(folder_id, is_expanded=0)

    def _on_load_clicked(self):
        item = self.tree_widget.currentItem()
        if item and item.data(0, Qt.ItemDataRole.UserRole + 1) == ITEM_TYPE_PRESET:
            preset_id = item.data(0, Qt.ItemDataRole.UserRole)
            self.load_preset.emit(preset_id)

    def _on_delete_clicked(self):
        from src.core.lang_manager import _
        item = self.tree_widget.currentItem()
        if not item: return
        
        item_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
        item_id = item.data(0, Qt.ItemDataRole.UserRole)
        
        if item_type == ITEM_TYPE_FOLDER:
            from src.ui.common_widgets import FramelessMessageBox
            msg = FramelessMessageBox(self)
            msg.setWindowTitle(_("Delete Folder"))
            msg.setText(_("Delete folder '{folder_name}'?\n(Presets inside will be moved to root)").format(folder_name=item.text(0)))
            msg.setIcon(FramelessMessageBox.Icon.Question)
            msg.setStandardButtons(FramelessMessageBox.StandardButton.Yes | FramelessMessageBox.StandardButton.No)
            
            if msg.exec() == FramelessMessageBox.StandardButton.Yes:
                self.db.delete_preset_folder(item_id)
                self.refresh(preserve_selection=False)
        elif item_type == ITEM_TYPE_PRESET:
            from src.ui.common_widgets import FramelessMessageBox
            msg = FramelessMessageBox(self)
            msg.setWindowTitle(_("Delete Preset"))
            msg.setText(_("Delete '{preset_name}'?").format(preset_name=item.text(0)))
            msg.setIcon(FramelessMessageBox.Icon.Question)
            msg.setStandardButtons(FramelessMessageBox.StandardButton.Yes | FramelessMessageBox.StandardButton.No)
            
            if msg.exec() == FramelessMessageBox.StandardButton.Yes:
                self.delete_preset.emit(item_id)


    def dropEvent(self, event):
        """Handle drop to move preset into folder."""
        # This is handled by QTreeWidget's internal move, but we need to update DB
        super().dropEvent(event)
        self._save_order_and_folders()
    
    def _save_order_and_folders(self):
        """Save the current order and folder assignments to DB."""
        if not self.db: return
        
        root = self.tree_widget.invisibleRootItem()
        preset_order = []
        folder_order = []
        
        for i in range(root.childCount()):
            item = root.child(i)
            item_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
            item_id = item.data(0, Qt.ItemDataRole.UserRole)
            
            if item_type == ITEM_TYPE_FOLDER:
                folder_order.append(item_id)
                # Presets inside this folder
                for j in range(item.childCount()):
                    child = item.child(j)
                    if child.data(0, Qt.ItemDataRole.UserRole + 1) == ITEM_TYPE_PRESET:
                        preset_id = child.data(0, Qt.ItemDataRole.UserRole)
                        preset_order.append(preset_id)
                        self.db.move_preset_to_folder(preset_id, item_id)
            else:
                # Root level preset
                preset_order.append(item_id)
                self.db.move_preset_to_folder(item_id, None)
        
        self.db.update_preset_order(preset_order)
        self.db.update_folder_order(folder_order)
        self.order_changed.emit(preset_order)

    def _show_context_menu(self, pos):
        from src.core.lang_manager import _
        from src.ui.styles import MenuStyles
        item = self.tree_widget.itemAt(pos)
        if not item: return
        
        item_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
        item_id = item.data(0, Qt.ItemDataRole.UserRole)
        
        menu = QMenu()
        menu.setStyleSheet(MenuStyles.CONTEXT)
        
        if item_type == ITEM_TYPE_FOLDER:
            act_rename = menu.addAction(_("✏️ Rename"))
            menu.addSeparator()
            act_del = menu.addAction(_("🗑 Delete"))
            
            action = menu.exec(self.tree_widget.viewport().mapToGlobal(pos))
            
            if action == act_rename:
                name, ok = FramelessInputDialog.getText(self, _("Rename Folder"), _("New Name:"), text=item.text(0).replace("📁 ", ""))
                if ok and name:
                    self.db.update_preset_folder(item_id, name=name)
                    self.refresh()
            elif action == act_del:
                self._on_delete_clicked()
        else:
            # Preset context menu
            act_load = menu.addAction(_("🚀 Deploy"))
            act_props = menu.addAction(_("📝 Properties"))
            menu.addSeparator()
            
            # Move to folder submenu
            folders = self.db.get_preset_folders() if self.db else []
            if folders:
                move_menu = menu.addMenu(_("📁 Move to Folder"))
                act_root = move_menu.addAction(_("(Root)"))
                folder_actions = {}
                for f in folders:
                    act = move_menu.addAction(f['name'])
                    folder_actions[act] = f['id']
            else:
                act_root = None
                folder_actions = {}
            
            menu.addSeparator()
            act_top = menu.addAction(_("⏫ Move to Top"))
            act_bottom = menu.addAction(_("⏬ Move to Bottom"))
            menu.addSeparator()
            act_del = menu.addAction(_("🗑 Delete"))
            
            action = menu.exec(self.tree_widget.viewport().mapToGlobal(pos))
            
            if action == act_load:
                self.load_preset.emit(item_id)
            elif action == act_props:
                self.edit_preset_properties.emit(item_id)
            elif action == act_root:
                self.db.move_preset_to_folder(item_id, None)
                self.refresh()
            elif action in folder_actions:
                self.db.move_preset_to_folder(item_id, folder_actions[action])
                self.refresh()
            elif action == act_top:
                self._move_item_to_position(item, 0)
            elif action == act_bottom:
                self._move_item_to_position(item, -1)
            elif action == act_del:
                self._on_delete_clicked()
    
    def _move_item_to_position(self, item, position):
        """Move item to top (0) or bottom (-1) within its parent scope."""
        parent = item.parent() or self.tree_widget.invisibleRootItem()
        index = parent.indexOfChild(item)
        
        if position == 0 and index > 0:
            parent.takeChild(index)
            parent.insertChild(0, item)
            self.tree_widget.setCurrentItem(item)
            self._save_order_and_folders()
        elif position == -1 and index < parent.childCount() - 1:
            parent.takeChild(index)
            parent.addChild(item)
            self.tree_widget.setCurrentItem(item)
            self._save_order_and_folders()
