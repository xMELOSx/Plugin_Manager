from PyQt6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QApplication, QTableWidgetItem, QSpinBox, QStyle
from PyQt6.QtCore import Qt, QRect, QPoint, QPointF, QRectF, QEvent, QSize
from PyQt6.QtGui import QPainter, QColor, QIcon, QPen, QBrush, QPixmap, QCursor
import os
import logging
import time
import copy
from .quick_view_manager import QuickViewManagerDialog, NaturalSortTableWidgetItem, SortableTableWidgetItem
from src.ui.toast import Toast
from src.core.lang_manager import _

class IconDelegate(QStyledItemDelegate):
    """Delegate for rendering item thumbnails/icons."""
    def __init__(self, parent, icon_cache):
        super().__init__(parent)
        self.icon_cache = icon_cache

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        icon_path = index.data(Qt.ItemDataRole.UserRole)
        if not icon_path or not os.path.exists(icon_path):
            super().paint(painter, option, index)
            return

        if icon_path not in self.icon_cache:
            self.icon_cache[icon_path] = QIcon(icon_path)
        
        icon = self.icon_cache[icon_path]
        rect = option.rect.adjusted(1, 1, -1, -1)
        # Use Pixmap for better quality scaling if possible, or just Icon.paint
        icon.paint(painter, rect, Qt.AlignmentFlag.AlignCenter)

class FavoriteDelegate(QStyledItemDelegate):
    """Delegate for rendering and toggling Favorite state."""
    def __init__(self, parent, draw_star_func):
        super().__init__(parent)
        self.draw_star = draw_star_func

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        is_fav = bool(index.data(Qt.ItemDataRole.UserRole))
        star_icon = self.draw_star(is_fav)
        rect = option.rect.adjusted(4, 4, -4, -4)
        star_icon.paint(painter, rect, Qt.AlignmentFlag.AlignCenter)

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.Type.MouseButtonRelease:
            is_fav = bool(index.data(Qt.ItemDataRole.UserRole))
            model.setData(index, not is_fav, Qt.ItemDataRole.UserRole)
            
            # Find item by rel_path stored in UserRole of Col 1 or similar?
            # Better: Get rel_path from the item's data structure directly if row mapping is risky.
            # But in Delegate mode, we can trust the model's row IF we update it properly.
            dialog = self.parent().window()
            if hasattr(dialog, '_on_fav_toggled_delegate'):
                rel_path = model.index(index.row(), 1).data(Qt.ItemDataRole.UserRole + 1)
                dialog._on_fav_toggled_delegate(rel_path, not is_fav)
            return True
        return super().editorEvent(event, model, option, index)

class ScoreDelegate(QStyledItemDelegate):
    """Delegate for editing scores with a SpinBox."""
    def createEditor(self, parent, option, index):
        editor = QSpinBox(parent)
        editor.setFrame(False)
        editor.setMinimum(0)
        editor.setMaximum(9999)
        editor.setStyleSheet("background-color: #444; color: white; border: none;") # Removed 1px solid border
        
        # Phase 1.1.70: Connect valueChanged for persistent editors
        # Since setModelData is not called reliably for persistent editors,
        # we connect the signal directly.
        row = index.row()
        dialog = self.parent().window()
        
        def on_value_changed(val):
            # Update model data
            model = index.model()
            model.setData(index, val, Qt.ItemDataRole.UserRole)
            model.setData(index, str(val), Qt.ItemDataRole.DisplayRole)
            
            # Update sort value - use parent table widget, not model
            table = self.parent()
            if table:
                item = table.item(index.row(), index.column())
                if item:
                    item._sort_value = val
            
            # Notify dialog
            rel_path = model.index(index.row(), 1).data(Qt.ItemDataRole.UserRole + 1)
            if hasattr(dialog, '_on_score_changed_delegate'):
                dialog._on_score_changed_delegate(rel_path, val)
        
        editor.valueChanged.connect(on_value_changed)
        return editor

    def setEditorData(self, editor, index):
        value = index.data(Qt.ItemDataRole.UserRole)
        editor.blockSignals(True) # Prevent signal during initialization
        editor.setValue(int(value) if value is not None else 0)
        editor.blockSignals(False)

    def setModelData(self, editor, model, index):
        # For non-persistent editors, this is the standard path
        value = editor.value()
        model.setData(index, value, Qt.ItemDataRole.UserRole)
        model.setData(index, str(value), Qt.ItemDataRole.DisplayRole)
        
        dialog = self.parent().window()
        if hasattr(dialog, '_on_score_changed_delegate'):
            rel_path = index.model().index(index.row(), 1).data(Qt.ItemDataRole.UserRole + 1)
            dialog._on_score_changed_delegate(rel_path, value)

class TagColumnDelegate(QStyledItemDelegate):
    """
    Delegate for rendering Tag columns efficiently without Widgets.
    Handles Icon/Text/Symbol drawing and Click events.
    """
    def __init__(self, parent, tag_info, icon_cache):
        super().__init__(parent)
        self.tag_info = tag_info
        self.icon_cache = icon_cache
        self.is_interactive = True

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        """Draw tag state."""
        # Check Item data
        is_active = bool(index.data(Qt.ItemDataRole.UserRole)) 
        
        # Draw Button-like appearance
        rect = option.rect
        center_x = rect.x() + rect.width() / 2
        center_y = rect.y() + rect.height() / 2
        size = 25 # Increased for visibility
        btn_rect = QRectF(rect.center().x() - size/2, rect.center().y() - size/2, size, size)
        
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw Background
        is_hover = (option.state & QStyle.StateFlag.State_MouseOver)
        
        bg_color = QColor("#444444") if not is_active else QColor("#5dade2") 
        if is_active:
             # Active: Solid Blue
             if is_hover:
                 bg_color = QColor("#7fbce8") # Brighter blue on hover
             painter.setBrush(QBrush(bg_color))
        else:
             # Inactive: Darker grey
             if is_hover:
                 bg_color = QColor("#555555") # Brighter grey on hover
             painter.setBrush(QBrush(bg_color))
        
        painter.setPen(QPen(QColor("#666666") if is_hover else QColor("#555555"), 1))
        painter.drawRoundedRect(btn_rect, 4, 4)
        
        # Draw Content
        mode = self.tag_info.get('display_mode', 'text')
        emoji = self.tag_info.get('emoji', '')
        display_name = self.tag_info.get('display', self.tag_info.get('name', ''))
        icon_path = self.tag_info.get('icon', '')
        
        if is_active:
             painter.setOpacity(1.0)
             text_color = QColor("#ffffff")
        else:
             painter.setOpacity(0.5)
             text_color = QColor("#aaaaaa")

        if mode == 'image' and icon_path:
            if icon_path not in self.icon_cache:
                if os.path.exists(icon_path):
                    self.icon_cache[icon_path] = QIcon(icon_path)
            icon = self.icon_cache.get(icon_path)
            if icon:
                icon.paint(painter, btn_rect.toRect().adjusted(2,2,-2,-2))
        elif mode == 'symbol' and emoji:
            painter.setPen(QPen(text_color))
            painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter, emoji)
        elif mode == 'text_symbol' and emoji:
            painter.setPen(QPen(text_color))
            # For 25px buttons, "emoji name" is too tight, but we follow setting. 
            # We'll draw emoji and small text if it fits, or just emoji for now to avoid mess.
            # BUT user says "Icon + Name" is what they see, so maybe we SHOULD draw both if requested.
            painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter, f"{emoji} {display_name[:1]}")
        else:
            painter.setPen(QPen(text_color))
            font = painter.font()
            font.setPointSize(8)
            painter.setFont(font)
            text = (display_name[:2] if len(display_name) > 2 else display_name)
            painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter, text)
            
        painter.restore()

    def editorEvent(self, event, model, option, index):
        """Handle Click and Hover (cursor)."""
        # Always check if mouse is over the actual pill rect for interactive feel
        rect = option.rect
        size = 25
        btn_rect = QRectF(rect.center().x() - size/2, rect.center().y() - size/2, size, size)
        is_over_pill = btn_rect.contains(QPointF(event.pos())) if hasattr(event, 'pos') else False

        if event.type() in [QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress]:
            view = self.parent()
            if view and is_over_pill:
                view.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            elif view:
                view.unsetCursor()

        if event.type() == QEvent.Type.MouseButtonRelease:
            if not is_over_pill:
                return False
                
            # Toggle state
            current_state = bool(index.data(Qt.ItemDataRole.UserRole))
            new_state = not current_state
            model.setData(index, new_state, Qt.ItemDataRole.UserRole)
            
            # Notify Dialog to handle logic update (DB save etc)
            table = self.parent()
            dialog = table.window()
            if hasattr(dialog, '_on_tag_toggled_delegate'):
                row = index.row()
                if hasattr(dialog, '_all_tag_columns'):
                    col_idx = index.column()
                    tag_col_idx = col_idx - 6
                    if 0 <= tag_col_idx < len(dialog._all_tag_columns):
                        tag_info = dialog._all_tag_columns[tag_col_idx]['tag_info']
                        rel_path = model.index(index.row(), 1).data(Qt.ItemDataRole.UserRole + 1)
                        dialog._on_tag_toggled_delegate(rel_path, tag_info['name'].lower(), new_state)
            return True
        return super().editorEvent(event, model, option, index)


class QuickViewDelegateDialog(QuickViewManagerDialog):
    """
    Mode 2: High Performance QuickView using Delegates.
    Avoids creating thousands of QWidgets.
    """
    def __init__(self, parent, items_data, frequent_tags, db, storage_root, show_hidden=True, scope="category"):
        super().__init__(parent, items_data, frequent_tags, db, storage_root, show_hidden, scope=scope)
        self.setObjectName("QuickViewDelegateDialog")
        # Base title is already set by super().__init__ based on scope
        self.setWindowTitle(self._base_title)
        self._pending_changes = {} # rel_path -> {key: val}
        self.results = [] # Always list for parity
        
        self._load_table_data()
        
    def _load_table_data(self):
        """Override to use Delegates instead of CellWidgets."""
        # 1. Setup Columns/Delegates
        # 0: No (Natural Sort)
        # 1: Icon
        self.table.setItemDelegateForColumn(1, IconDelegate(self.table, self._icon_cache))
        # 2: Fav
        self.table.setItemDelegateForColumn(2, FavoriteDelegate(self.table, self._draw_star_icon))
        # 3: Score
        self.table.setItemDelegateForColumn(3, ScoreDelegate(self.table))
        
        # Tag Columns (index 6+)
        for i, col_data in enumerate(self._all_tag_columns):
            col_idx = 6 + i
            if col_data['type'] == 'tag':
                delegate = TagColumnDelegate(self.table, col_data['tag_info'], self._icon_cache)
                self.table.setItemDelegateForColumn(col_idx, delegate)
        
        # Apply Column Widths
        self.table.setColumnWidth(0, 40) # No.
        self.table.setColumnWidth(1, 40) # Icon
        self.table.setColumnWidth(2, 40) # Fav
        self.table.setColumnWidth(3, 50) # Score
        self.table.setColumnWidth(4, 150) # Folder
        self.table.setColumnWidth(5, 200) # Display Name
        
        for i, col_info in enumerate(self._all_tag_columns):
            col_idx = 6 + i
            if col_info['type'] == 'sep':
                self.table.setColumnWidth(col_idx, 2) # Narrower separator
            else:
                self.table.setColumnWidth(col_idx, 32)

        # Connect itemChanged for Display Name persistence
        # We need to block signals during data fill to prevent recursive calls
        self.table.setMouseTracking(True) # Phase 16: Enable tracking for cursor changes
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.items_data))
        self._load_all_data_delegate()
        
        # Phase 1.1.30: Open persistent editors for parity with Mode 1
        for r in range(self.table.rowCount()):
            it_score = self.table.item(r, 3)
            if it_score: self.table.openPersistentEditor(it_score)
            it_name = self.table.item(r, 5)
            if it_name: self.table.openPersistentEditor(it_name)
        
        self.table.blockSignals(False)
        
        # Phase 16: Ensure Display Name column stretches AFTER everything is loaded
        from PyQt6.QtWidgets import QHeaderView
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch) # Re-apply after resize
        
        # Enforce separator widths AFTER automatic resize
        for i, col_info in enumerate(self._all_tag_columns):
            if col_info['type'] == 'sep':
                self.table.setColumnWidth(6 + i, 2)
        
        # Connect after loading
        self.table.itemChanged.connect(self._on_item_changed_delegate)
        
    def _load_all_data_delegate(self):
        self._profile_start_time = time.perf_counter()
        self.table.setSortingEnabled(False)
        for row, item in enumerate(self.items_data):
            self._create_row_delegate(row, item)
        self.table.setSortingEnabled(True)
        
        # Initial Fade In
        self.table.updateGeometry()
        # Ensure scrollbars are updated
        QApplication.processEvents()
        
        total_time = time.perf_counter() - self._profile_start_time
        logging.info(f"[QuickViewProfile] Delegate Load Finished in {total_time:.3f}s")
        
        # Phase 1.1.21: Final visibility enforcement
        self.setWindowOpacity(1.0)
        self.show()
        
        # Phase 16: Force layout settlement after show()
        self.table.updateGeometry()
        QApplication.processEvents()
        
        # 1. First automatic resize
        self.table.resizeColumnsToContents()
        
        # 2. Stretch specific columns
        from PyQt6.QtWidgets import QHeaderView
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        
        # 3. Finally enforce separator widths AFTER automatic resize
        for i, col_info in enumerate(self._all_tag_columns):
            if col_info['type'] == 'sep':
                self.table.setColumnWidth(6 + i, 2)
        
        self.raise_()
        self.activateWindow()
        
        # Diagnostic Log
        logging.info(f"[QuickViewDebug] Delegate State: Pos={self.pos()}, Size={self.size()}, Visible={self.isVisible()}, Opacity={self.windowOpacity()}")

        
    def _create_row_delegate(self, row, item):
        # 0. No
        no_item = NaturalSortTableWidgetItem(row + 1)
        no_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 0, no_item)
        
        # 1. Icon (Display)
        icon_path = item.get('image_path', '')
        icon_item = QTableWidgetItem()
        icon_item.setData(Qt.ItemDataRole.UserRole, icon_path)
        # Phase 1.1.31: Store rel_path for robust mapping in delegates
        icon_item.setData(Qt.ItemDataRole.UserRole + 1, item['rel_path']) 
        icon_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 1, icon_item)
        
        # 2. Fav
        is_fav = item.get('is_favorite', False)
        fav_item = SortableTableWidgetItem(1 if is_fav else 0, "")
        fav_item.setData(Qt.ItemDataRole.UserRole, is_fav)
        fav_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 2, fav_item)
        
        # 3. Score
        score_val = item.get('score', 0)
        score_item = SortableTableWidgetItem(score_val, str(score_val))
        score_item.setData(Qt.ItemDataRole.UserRole, score_val)
        score_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 3, score_item)
        
        # 4. Folder
        folder_name = os.path.basename(item.get('rel_path', ''))
        folder_item = NaturalSortTableWidgetItem(folder_name)
        folder_item.setForeground(QColor("#888888")) # Grey folder names
        font = folder_item.font()
        font.setItalic(True)
        folder_item.setFont(font)
        folder_item.setFlags(folder_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, 4, folder_item)
        
        # 5. Name (Editable)
        display_name = item.get('display_name', '') or folder_name
        name_item = NaturalSortTableWidgetItem(display_name)
        name_item.setFlags(name_item.flags() | Qt.ItemFlag.ItemIsEditable)
        name_item.setData(Qt.ItemDataRole.UserRole, item['rel_path']) # Store for mapping
        self.table.setItem(row, 5, name_item)
        
        # 6+. Tags (Handled by Delegates, we just need to set UserRole data)
        current_tags = set(t.strip().lower() for t in (item.get('tags') or "").split(",") if t.strip())
        
        for i, col_data in enumerate(self._all_tag_columns):
            col_idx = 6 + i
            if col_data['type'] == 'tag':
                tag_name = col_data['tag_info']['name'].lower()
                is_active = tag_name in current_tags
                
                table_item = SortableTableWidgetItem(1 if is_active else 0, "")
                table_item.setData(Qt.ItemDataRole.UserRole, is_active)
                self.table.setItem(row, col_idx, table_item)

    def _on_tag_toggled_delegate(self, rel_path, tag_name, new_state):
        """Handle tag toggle from delegate."""
        item = next((i for i in self.items_data if i['rel_path'] == rel_path), None)
        if not item: return
        
        current_tags = set(t.strip().lower() for t in (item.get('tags') or "").split(",") if t.strip())
        
        if new_state:
            current_tags.add(tag_name)
        else:
            current_tags.discard(tag_name)
            
        new_tags_str = ",".join(sorted(list(current_tags)))
        item['tags'] = new_tags_str
        
        # Update Sort Item
        self._update_sort_data_for_tag(rel_path, tag_name, 1 if new_state else 0)
        
        self._record_pending_change(rel_path, 'tags', new_tags_str)
        self._update_window_title()


    def _on_fav_toggled_delegate(self, rel_path, is_fav):
        item = next((i for i in self.items_data if i['rel_path'] == rel_path), None)
        if not item: return
        
        item['is_favorite'] = is_fav
        self._update_sort_data(rel_path, 2, 1 if is_fav else 0)
        self._record_pending_change(rel_path, 'is_favorite', is_fav) # Phase 1.1.262: Pass Boolean for better parity
        self._update_window_title()

    def _on_score_changed_delegate(self, rel_path, score):
        item = next((i for i in self.items_data if i['rel_path'] == rel_path), None)
        if not item: return
        
        item['score'] = score
        self._update_sort_data(rel_path, 3, score)
        self._record_pending_change(rel_path, 'score', score)
        self._update_window_title()

    def _on_item_changed_delegate(self, table_item):
        """Handle manual text edits for Display Name."""
        col = table_item.column()
        if col != 5: return # Only handle Display Name (Col 5)
        
        rel_path = table_item.data(Qt.ItemDataRole.UserRole)
        if not rel_path: return
        
        item = next((i for i in self.items_data if i['rel_path'] == rel_path), None)
        if not item: return
        
        new_name = table_item.text().strip()
        if new_name != item.get('display_name'):
            item['display_name'] = new_name
            self._record_pending_change(rel_path, 'display_name', new_name)
            self._update_window_title()

    def _update_sort_data(self, rel_path, col, val):
        """Update internal sort state for delegates (finding row by rel_path)."""
        for r in range(self.table.rowCount()):
            # Col 1 stores rel_path in UserRole + 1
            if self.table.item(r, 1).data(Qt.ItemDataRole.UserRole + 1) == rel_path:
                sort_item = self.table.item(r, col)
                if sort_item:
                    sort_item._sort_value = val
                    # Re-sort if needed
                    if self.table.horizontalHeader().sortIndicatorSection() == col:
                        self.table.sortItems(col, self.table.horizontalHeader().sortIndicatorOrder())
                break

    def _update_sort_data_for_tag(self, rel_path, tag_name, val):
        """Update internal sort state for tag columns in Mode 2."""
        # Find column index for this tag
        col = -1
        for i, col_data in enumerate(self._all_tag_columns):
            if col_data['type'] == 'tag' and col_data['tag_info']['name'].lower() == tag_name.lower():
                col = 6 + i
                break
        
        if col != -1:
            self._update_sort_data(rel_path, col, val)

    def _record_pending_change(self, rel_path, key, value):
        """Buffer changes locally before saving."""
        if rel_path not in self._pending_changes:
            self._pending_changes[rel_path] = {}
        self._pending_changes[rel_path][key] = value
        self._has_changes = True

    def _on_interim_save_clicked(self):
        """Perform save without closing the dialog (Mode 2)."""
        saved, count = self._perform_save()
        if saved:
            if count > 0:
                from src.ui.toast import Toast
                Toast.show_toast(self.parent(), _("Changes saved! ({0} items)").format(count), preset="success")
            else:
                from src.ui.toast import Toast
                Toast.show_toast(self.parent(), _("変更はありません"), preset="warning")

    def _perform_save(self):
        """Mode 2 specific save logic."""
        if not hasattr(self, '_pending_changes') or not self._pending_changes:
            return True, 0

        count = 0
        if self.db:
            try:
                # IMPORTANT: Use copy to avoid modification during iteration
                pending = dict(self._pending_changes)
                logging.info(f"[QuickViewMode2] Attempting to save {len(pending)} modified items...")
                
                for rel_path, changes in pending.items():
                    # Ensure path normalization
                    norm_rel = rel_path.replace('\\', '/')
                    logging.info(f"[QuickViewMode2] Saving {norm_rel}: {changes}")
                    self.db.update_folder_display_config(norm_rel, **changes)
                    
                    # Update results for Main Window
                    data = {'rel_path': norm_rel}
                    data.update(changes)
                    # Check if already in results to avoid duplicates
                    existing = next((r for r in self.results if r['rel_path'] == norm_rel), None)
                    if existing:
                        existing.update(changes)
                    else:
                        self.results.append(data)
                    
                    # Update local item data to keep sync during interim saves
                    item = next((i for i in self.items_data if i['rel_path'] == rel_path or i['rel_path'] == norm_rel), None)
                    if item:
                        item.update(changes)
                        # CRITICAL: Update _orig_* markers so _has_real_changes() syncs correctly
                        if 'is_favorite' in changes: item['_orig_fav'] = changes['is_favorite']
                        if 'score' in changes: item['_orig_score'] = int(changes['score'])
                        if 'display_name' in changes: item['_orig_name'] = changes['display_name']
                        if 'tags' in changes: 
                            from .quick_view_manager import _normalize_tags
                            item['_orig_tags'] = _normalize_tags(changes['tags'], lowercase=True)
                    
                    count += 1
                logging.info(f"[QuickViewMode2] Successfully saved {count} items.")
            except Exception as e:
                logging.error(f"Failed bulk save in Mode 2: {e}", exc_info=True)
                return False, 0
                
        self._pending_changes.clear()
        self._has_changes = False
        if hasattr(self, '_update_window_title'):
             self._update_window_title()
        return True, count

    def _on_save_clicked(self):
        """Override to perform bulk save and close."""
        saved, count = self._perform_save()
        if saved:
            # Handled by Main Window
            self.accept()

    def reject(self):
        from src.ui.toast import Toast
        if self.parent():
             Toast.show_toast(self.parent(), _("Edit Cancelled"), preset="warning")
        super().reject()

