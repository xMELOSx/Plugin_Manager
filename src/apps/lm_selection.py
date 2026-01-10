"""
Link Master: Selection and Context Menu Mixin
Extracted from LinkMasterWindow for modularity.
"""
import os
from PyQt6.QtWidgets import QMenu, QApplication
from PyQt6.QtCore import Qt
from src.ui.link_master.item_card import ItemCard


class LMSelectionMixin:
    """Mixin providing selection and context menu methods for LinkMasterWindow."""
    
    def _handle_item_click(self, path, area_type):
        """Processes selection based on keyboard modifiers."""
        modifiers = QApplication.keyboardModifiers()
        
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            if path in self.selected_paths:
                self.selected_paths.remove(path)
            else:
                self.selected_paths.add(path)
            self._last_selected_path = path
        elif modifiers & Qt.KeyboardModifier.ShiftModifier and getattr(self, '_last_selected_path', None):
            layout = self.cat_layout if area_type == "category" else self.pkg_layout
            all_paths = []
            for i in range(layout.count()):
                w = layout.itemAt(i).widget()
                if isinstance(w, ItemCard):
                    all_paths.append(w.path)
            
            try:
                idx1 = all_paths.index(self._last_selected_path)
                idx2 = all_paths.index(path)
                start_idx, end_idx = min(idx1, idx2), max(idx1, idx2)
                for i in range(start_idx, end_idx + 1):
                    self.selected_paths.add(all_paths[i])
            except:
                self.selected_paths.add(path)
        else:
            self.selected_paths = {path}
            self._last_selected_path = path
            
            if area_type == "category":
                self._on_category_selected(path)

        self._update_selection_visuals()

    def _update_selection_visuals(self):
        """Syncs is_selected state of all cards with self.selected_paths."""
        for layout in [self.cat_layout, self.pkg_layout]:
            for i in range(layout.count()):
                widget = layout.itemAt(i).widget()
                if isinstance(widget, ItemCard):
                    is_selected = widget.path in self.selected_paths
                    is_focused = (widget.path == getattr(self, '_last_selected_path', None))
                    widget.set_selected(is_selected, is_focused)

    def _show_cat_context_menu(self, pos):
        self._show_batch_context_menu(pos, "category")

    def _show_pkg_context_menu(self, pos):
        self._show_batch_context_menu(pos, "package")

    def _show_batch_context_menu(self, pos, area_type):
        """Shows batch context menu for selected cards."""
        layout = self.cat_layout if area_type == "category" else self.pkg_layout
        global_pos = (self.cat_container if area_type == "category" else self.pkg_container).mapToGlobal(pos)
        
        child = (self.cat_container if area_type == "category" else self.pkg_container).childAt(pos)
        if child:
            card = child
            while card and not isinstance(card, ItemCard):
                card = card.parent()
            
            if card and isinstance(card, ItemCard):
                if card.path not in self.selected_paths:
                    self.selected_paths = {card.path}
                    self._last_selected_path = card.path
                    self._update_selection_visuals()

        if not self.selected_paths: return

        # Create menu with explicit parent to prevent style leakage
        menu = QMenu(self)
        menu.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)  # Auto-cleanup
        
        from src.ui.styles import MenuStyles
        menu.setStyleSheet(MenuStyles.CONTEXT)
        
        count = len(self.selected_paths)
        from src.core.lang_manager import _
        menu.addAction(_("Selected: {count} item(s)").format(count=count)).setEnabled(False)
        menu.addSeparator()

        active_card = None
        if count == 1:
            path = list(self.selected_paths)[0]
            for layout_obj in [self.cat_layout, self.pkg_layout]:
                for i in range(layout_obj.count()):
                    w = layout_obj.itemAt(i).widget()
                    if isinstance(w, ItemCard) and w.path == path:
                        active_card = w
                        break
                if active_card: break

        if active_card:
            # Need relative path for unified menu
            if self.storage_root:
                try:
                    rel_path = os.path.relpath(active_card.path, self.storage_root).replace('\\', '/')
                    if rel_path == ".": rel_path = ""
                    menu = self._create_item_context_menu(rel_path)
                except Exception as e:
                    self.logger.error(f"Failed to create context menu: {e}")
                    return
            else:
                return
            
            if not menu: return
            
            # Phase 18.9: Misplaced / Move Actions (If not in trash)
            if active_card.is_misplaced and not active_card.is_trash_view:
                menu.addSeparator()
                action_unclass = menu.addAction("📦 Move to Unclassified")
                action_unclass.triggered.connect(lambda: active_card.request_move_to_unclassified.emit(active_card.path))
            
            # Removed Move to Top/Bottom for folders

        else:
            from src.core.lang_manager import _
            from src.ui.styles import MenuStyles

            menu = QMenu(self)
            menu.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            menu.setStyleSheet(MenuStyles.CONTEXT)
            
            count = len(self.selected_paths)
            menu.addAction(_("Batch Edit ({count} items)").format(count=count)).setEnabled(False)
            menu.addSeparator()
            
            # Determine selection composition
            has_categories = False
            has_packages = False
            for path in self.selected_paths:
                rel = os.path.relpath(path, self.storage_root).replace('\\', '/') if self.storage_root else ''
                cfg = self.db.get_folder_config(rel) if self.db else {}
                folder_type = cfg.get('folder_type', 'auto') if cfg else 'auto'
                if folder_type == 'category':
                    has_categories = True
                elif folder_type == 'package':
                    has_packages = True
                else:
                    # Auto-detect based on heuristic
                    if hasattr(self, '_detect_folder_type'):
                        detected = self._detect_folder_type(path)
                        if detected == 'category':
                            has_categories = True
                        else:
                            has_packages = True
                    else:
                        has_packages = True  # Default to package
            
            # Category Deploy/Unlink
            act_cat_deploy = menu.addAction(_("📁 Batch Category Deploy"))
            act_cat_deploy.triggered.connect(self._batch_category_deploy_selected)
            
            act_cat_unlink = menu.addAction(_("📁 Batch Category Unlink"))
            act_cat_unlink.triggered.connect(self._batch_category_unlink_selected)
            
            menu.addSeparator()
            
            # Package Deploy/Unlink
            act_deploy = menu.addAction(_("🚀 Batch Deploy (Links)"))
            act_deploy.triggered.connect(self._batch_deploy_selected)
            
            act_separate = menu.addAction(_("🔗 Batch Separate (Remove Links)"))
            act_separate.triggered.connect(self._batch_separate_selected)
            
            menu.addSeparator()
            
            # Disable based on view and selection
            mixed_selection = has_categories and has_packages
            is_category_view = (area_type == "category")
            
            if mixed_selection:
                # Both types selected - disable all deploy/unlink
                act_cat_deploy.setEnabled(False)
                act_cat_unlink.setEnabled(False)
                act_deploy.setEnabled(False)
                act_separate.setEnabled(False)
            elif is_category_view:
                # Category view - disable package operations
                act_deploy.setEnabled(False)
                act_separate.setEnabled(False)
            else:
                # Package view - disable category operations
                act_cat_deploy.setEnabled(False)
                act_cat_unlink.setEnabled(False)
            
            # Favorite actions FIRST (swapped per user request)
            act_fav = menu.addAction("🌟 " + _("Batch Add to Favorites"))
            act_fav.triggered.connect(lambda: self._batch_favorite_selected(True))
            
            act_unfav = menu.addAction("❇ " + _("Batch Remove from Favorites"))
            act_unfav.triggered.connect(lambda: self._batch_favorite_selected(False))
            
            menu.addSeparator()
            
            # Visibility actions AFTER favorites (swapped)
            act_show = menu.addAction(_("👁 Show All"))
            act_show.triggered.connect(lambda: self._batch_visibility_selected(True))
            
            act_hide = menu.addAction(_("👻 Hide All"))
            act_hide.triggered.connect(lambda: self._batch_visibility_selected(False))
            
            menu.addSeparator()


        any_in_trash = False
        any_misplaced = False
        for layout_obj in [self.cat_layout, self.pkg_layout]:
            for i in range(layout_obj.count()):
                w = layout_obj.itemAt(i).widget()
                if isinstance(w, ItemCard) and w.path in self.selected_paths:
                    if w.is_trash_view: any_in_trash = True
                    if w.is_misplaced: any_misplaced = True
        
        if any_misplaced and not any_in_trash:
            act_unclass = menu.addAction(_("📦 Move Selected to Unclassified"))
            act_unclass.triggered.connect(self._batch_unclassified_selected)
            menu.addSeparator()

        # Phase 19.x Fix: Only add batch-specific items if multiple items selected
        if not active_card:
            # Need strict import inside method to avoid circ import if needed, 
            # though _ is usually safe. Redundant import safe here.
            from src.core.lang_manager import _
            
            act_batch = menu.addAction(_("📝 Batch Edit Properties..."))
            act_batch.triggered.connect(self._batch_edit_properties_selected)
            
            # Phase 26: Quick View Manager removed from batch context menu per user request
            
            act_explorer = menu.addAction(_("📂 Open Selected in Explorer"))
            act_explorer.triggered.connect(self._batch_open_in_explorer)
            menu.addSeparator()

        
        if any_in_trash:
            if active_card:
                # Restore to original already exists in factory, but let's ensure consistency or remove here
                pass
            else:
                act_restore = menu.addAction(_("📦 Restore Selected"))
                act_restore.triggered.connect(self._batch_restore_selected)
        else:
            if not active_card:
                act_trash = menu.addAction(_("🗑 Move Selected to Trash"))
                act_trash.triggered.connect(self._batch_trash_selected)

        menu.exec(global_pos)

    def _clear_selection(self):
        """Clears all selected paths and updates visuals."""
        self.selected_paths.clear()
        self._last_selected_path = None
        self._update_selection_visuals()

    def _on_container_mouse_press(self, event, container):
        """Clears selection only if 'Empty Space' (Background) is clicked."""
        child = container.childAt(event.pos())
        
        if not child:
            self._clear_selection()
        
        event.accept()
