"""
Link Master: Batch File Operations Mixin
Handles visibility, favorites, trash, explorer actions, and properties.
"""
import os
import logging
import time
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import QTimer
from src.ui.link_master.item_card import ItemCard
from src.core.lang_manager import _
from src.core.link_master.core_paths import get_trash_dir

class LMFileOpsMixin:
    """Mixin for file-related batch operations (visibility, favorites, trash, etc.)."""

    def _update_cards_link_status(self, paths):
        """Partial update: Update link status for specific cards without rebuild."""
        for layout in [self.cat_layout, self.pkg_layout]:
            for i in range(layout.count()):
                w = layout.itemAt(i).widget()
                if isinstance(w, ItemCard) and w.path in paths:
                    w.update_link_status()
                    
        self._update_parent_category_status()
        self._refresh_tag_visuals()
    
    def _update_cards_hidden_state(self, paths, is_hidden: bool):
        """Partial update: Update hidden state for specific cards without rebuild."""
        for layout in [self.cat_layout, self.pkg_layout]:
            for i in range(layout.count()):
                w = layout.itemAt(i).widget()
                if isinstance(w, ItemCard) and w.path in paths:
                    w.update_hidden(is_hidden)

    def _update_cards_favorite_state(self, paths, is_favorite: bool):
        """Partial update: Update favorite state for multiple cards."""
        for layout in [self.cat_layout, self.pkg_layout]:
            for i in range(layout.count()):
                w = layout.itemAt(i).widget()
                if isinstance(w, ItemCard) and w.path in paths:
                    w.update_data(is_favorite=is_favorite)
    
    def _update_parent_category_status(self):
        """Update parent category cards to reflect child link status."""
        if hasattr(self, '_refresh_category_cards'):
            self._refresh_category_cards()
    
    def _batch_open_in_explorer(self):
        """Opens selected folders in Windows Explorer."""
        if not self.selected_paths: return
        import subprocess
        paths = list(self.selected_paths)[:5]
        for p in paths:
            if os.path.exists(p):
                subprocess.Popen(['explorer', os.path.normpath(p)])

    def _batch_visibility_selected(self, visible: bool):
        """Toggles visibility for all selected items."""
        if not self.selected_paths: return
        self.logger.info(f"Batch Visibility ({visible}): {len(self.selected_paths)} items")
        
        app_data = self.app_combo.currentData()
        if not app_data: return
        storage_root = app_data.get('storage_root')
        if not storage_root: return
        
        for path in self.selected_paths:
            try:
                rel = os.path.relpath(path, storage_root).replace('\\', '/')
                if rel == ".": rel = ""
                self._set_visibility_single(rel, visible, update_ui=False)
            except: pass
            
        self._update_cards_hidden_state(self.selected_paths, not visible)

    def _batch_favorite_selected(self, favorite: bool):
        """Toggles favorite state for all selected items."""
        if not self.selected_paths: return
        self.logger.info(f"Batch Favorite ({favorite}): {len(self.selected_paths)} items")
        
        app_data = self.app_combo.currentData()
        if not app_data: return
        storage_root = app_data.get('storage_root')
        if not storage_root: return
        
        for path in self.selected_paths:
            try:
                rel = os.path.relpath(path, storage_root).replace('\\', '/')
                if rel == ".": rel = ""
                self._set_favorite_single(rel, favorite, update_ui=False)
            except: pass
            
        self._update_cards_favorite_state(self.selected_paths, favorite)

    def _batch_trash_selected(self):
        """Moves all selected items to trash."""
        if not self.selected_paths: return
        
        msg = QMessageBox(self)
        msg.setWindowTitle(_("Batch Trash"))
        msg.setText(_("Move {count} items to trash?").format(count=len(self.selected_paths)))
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if msg.exec() != QMessageBox.StandardButton.Yes: return
        
        for path in list(self.selected_paths):
            self._trash_single(path, update_ui=True)
            
        self.selected_paths.clear()

    def _batch_restore_selected(self):
        """Restores all selected items from trash."""
        if not self.selected_paths: return
        for path in list(self.selected_paths):
            self._on_package_restore(path, refresh=False)
        self.selected_paths.clear()

    def _batch_unclassified_selected(self):
        """Moves all selected misplaced items to unclassified."""
        if not self.selected_paths: return
        self.logger.info(f"Batch Unclassified: {len(self.selected_paths)} items")
        for path in list(self.selected_paths):
            self._on_package_move_to_unclassified(path)
        self.selected_paths.clear()
        self._refresh_current_view()

    def _open_properties_for_path(self, abs_path: str):
        """Opens property edit dialog for a single path. Unified to use batch method state."""
        # Sync selection state to the target path so the batch method picks it up correctly
        original_selection = set(self.selected_paths)
        self.selected_paths = {abs_path}
        try:
            self._batch_edit_properties_selected()
        finally:
            # Restore selection afterwards if needed, but usually properties dialog is non-modal
            # and we want the card to stay selected. If we restore immediately, the dialog's
            # on_accepted might use the restored selection.
            # Actually, _batch_edit_properties_selected captures target_paths internally.
            self.selected_paths = original_selection

    def _open_properties_from_rel_path(self, rel_path: str):
        """Wrapper to open properties EDIT dialog from a relative path."""
        app_data = self.app_combo.currentData()
        if not app_data: return
        storage_root = app_data.get('storage_root')
        if not storage_root: return
        abs_path = os.path.join(storage_root, rel_path)
        self._open_properties_for_path(abs_path)

    def _view_properties_from_rel_path(self, rel_path: str):
        """Open PreviewWindow from a relative path."""
        app_data = self.app_combo.currentData()
        if not app_data: return
        storage_root = app_data.get('storage_root')
        if not storage_root: return
        abs_path = os.path.join(storage_root, rel_path)
        
        from src.ui.link_master.preview_window import PreviewWindow
        folder_config = self.db.get_folder_config(rel_path) or {}
        
        preview_paths = []
        if os.path.isdir(abs_path):
            manual_preview = folder_config.get('manual_preview_path', '')
            if manual_preview:
                preview_paths = [p.strip() for p in manual_preview.split(';') if p.strip()]
            else:
                image_exts = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')
                try:
                    for f in os.listdir(abs_path):
                        if f.lower().endswith(image_exts):
                            preview_paths.append(os.path.join(abs_path, f))
                except: pass
        
        target_root = app_data.get(self.current_target_key)
        
        self.preview_window = PreviewWindow(
            paths=preview_paths,
            parent=self,
            folder_path=abs_path,
            folder_config=folder_config,
            db=self.db,
            storage_root=storage_root,
            deployer=self.deployer,
            target_dir=target_root
        )
        self.preview_window.show()

    def _batch_edit_properties_selected(self):
        """Opens property edit dialog (Single or Batch mode). Non-modal."""
        if not self.selected_paths: return
        app_data = self.app_combo.currentData()
        if not app_data: return
        
        from src.ui.link_master.dialogs import FolderPropertiesDialog
        
        # Capture paths to avoid issues if selection changes while non-modal dialog is open
        target_paths = list(self.selected_paths)
        is_batch = len(target_paths) > 1
        
        if not is_batch:
            # Single Mode
            path = target_paths[0]
            storage_root = app_data.get('storage_root')
            try:
                rel = os.path.relpath(path, storage_root).replace('\\', '/')
                if rel == ".": rel = ""
            except: rel = ""
            
            current_config = self.db.get_folder_config(rel) or {}
            
            dialog = FolderPropertiesDialog(
                parent=self,
                folder_path=path,
                current_config=current_config,
                batch_mode=False,
                app_name=app_data['name'],
                storage_root=storage_root,
                thumbnail_manager=self.thumbnail_manager,
                app_deploy_default=app_data.get('deployment_type', 'folder'),
                app_conflict_default=app_data.get('conflict_policy', 'backup'),
                app_cat_style_default=app_data.get('default_category_style', 'image'),
                app_pkg_style_default=app_data.get('default_package_style', 'image')
            )
        else:
            # Batch Mode
            dialog = FolderPropertiesDialog(
                parent=self, 
                folder_path="",
                current_config={},
                batch_mode=True, 
                app_name=app_data['name'],
                storage_root=app_data.get('storage_root'),
                thumbnail_manager=self.thumbnail_manager,
                app_deploy_default=app_data.get('deployment_type', 'folder'),
                app_conflict_default=app_data.get('conflict_policy', 'backup'),
                app_cat_style_default=app_data.get('default_category_style', 'image'),
                app_pkg_style_default=app_data.get('default_package_style', 'image')
            )
            current_config = {}

        # Store reference to prevent garbage collection
        if not hasattr(self, '_property_edit_dialogs'):
            self._property_edit_dialogs = []
        # Cleanup old closed ones
        self._property_edit_dialogs = [d for d in self._property_edit_dialogs if d.isVisible()]
        self._property_edit_dialogs.append(dialog)
        
        # Connect accepted signal
        dialog.accepted.connect(lambda d=dialog, b=is_batch, p=target_paths, c=current_config: 
                                 self._on_property_edit_accepted(d, b, p, c))
        
        dialog.show()

    LINK_AFFECTING_KEYS = {
        'folder_type', 'deploy_type', 'deploy_rule', 'transfer_mode', 
        'conflict_policy', 'deployment_rules', 'inherit_tags', 
        'conflict_tag', 'conflict_scope', 'target_selection', 'target_override'
    }
    TAG_AFFECTING_KEYS = {'conflict_tag', 'conflict_scope', 'is_library', 'lib_name'}

    def _apply_folder_config_updates(self, target_paths, data, original_configs=None, is_batch=False):
        """
        Unified method to save folder properties, update UI, and trigger sweeps if needed.
        target_paths: list of absolute paths.
        data: dict of new property values.
        original_configs: dict of {abs_path: current_config_dict} for impact checking.
        """
        app_data = self.app_combo.currentData()
        if not app_data: return
        storage_root = app_data.get('storage_root')
        
        # 1. Determine changes and impacted items
        updates_to_apply = data
        if is_batch:
            # Phase 61: Allow None for certain keys (Restoring Default)
            allow_none_keys = {'display_style', 'display_style_package'}
            updates_to_apply = {
                k: v for k, v in data.items() 
                if (v is not None or k in allow_none_keys) and v != "KEEP"
            }
            if not updates_to_apply: return

        for abs_path in target_paths:
            try:
                rel = os.path.relpath(abs_path, storage_root).replace('\\', '/')
                if rel == ".": rel = ""
                
                # Check impact
                impacts_link = False
                if original_configs and abs_path in original_configs:
                    orig = original_configs[abs_path]
                    import json
                    
                    def normalize_json(s):
                        if not s: return None
                        try:
                            return json.dumps(json.loads(s), sort_keys=True)
                        except: return s
                        
                    for k in self.LINK_AFFECTING_KEYS:
                        if k not in updates_to_apply: continue
                        v = updates_to_apply[k]
                        orig_v = orig.get(k)
                        if v == orig_v: continue
                        
                        # JSON normalization for deployment_rules
                        if k == 'deployment_rules':
                            if normalize_json(v) == normalize_json(orig_v):
                                continue
                            
                        impacts_link = True
                        break
                else:
                    # If no original provided, assume impact if any affecting key is in updates (Safe default)
                    impacts_link = any(k in updates_to_apply for k in self.LINK_AFFECTING_KEYS)
                
                # Capture current link status BEFORE any updates
                # Phase 28: Use robust normalization matching the improved _get_active_card_by_path
                search_path = abs_path.replace('\\', '/')
                card = self._get_active_card_by_path(search_path)
                
                was_linked = False
                if card:
                    was_linked = (card.link_status in ('linked', 'partial'))
                else:
                    cfg = self.db.get_folder_config(rel)
                    was_linked = (cfg and cfg.get('last_known_status') in ('linked', 'partial'))

                # DB Update
                self.db.update_folder_display_config(rel, **updates_to_apply)
                
                # UI Update (Card)
                if card:
                    # Update card data (includes is_partial calculation removal)
                    card.update_data(**updates_to_apply)
                    
                    # Trigger Sweep/Deploy if WAS linked and configuration changed.
                    if impacts_link and was_linked:
                        self.logger.info(f"[Property-Sync] Config changed for linked item {rel}. Triggering forceful sweep.")
                        self._deploy_single(rel, update_ui=True, force_sweep=True)
                    else:
                        # Even if not link-impacting, we might need a status refresh (e.g. metadata only)
                        card.update_link_status()
                else:
                    self.logger.debug(f"[Batch-UI] No active card found for path: {search_path}")
                    
                    # If no card but WAS linked, we should still sweep
                    if impacts_link and was_linked:
                         self.logger.info(f"[Property-Sync] No card found but linked item {rel} changed. Sweeping.")
                         self._deploy_single(rel, update_ui=False, force_sweep=True)

            except Exception as e:
                self.logger.error(f"Failed to apply update for {abs_path}: {e}")

        # Final UI Refreshes & Notification
        if any(k in updates_to_apply for k in self.TAG_AFFECTING_KEYS):
            self._refresh_tag_visuals()

        from PyQt6.QtWidgets import QApplication
        from src.ui.toast import Toast
        active_win = QApplication.activeWindow() or (self.window() if hasattr(self, 'window') else self)
        Toast.show_toast(active_win, _("Folder properties saved successfully"), preset="success")
    
    def _on_property_edit_accepted(self, dialog, is_batch, target_paths, original_config):
        """Handle saving and UI updates after non-modal property dialog is accepted."""
        data = dialog.get_data()
        
        # Check if anything actually changed
        has_real_changes = False
        if not is_batch:
            # Single: compare with original
            import json
            def normalize_json(s):
                if not s: return None
                try: return json.dumps(json.loads(s), sort_keys=True)
                except: return s
                
            for k, v in data.items():
                orig_v = original_config.get(k)
                if v == orig_v: continue
                
                # JSON normalization for deployment_rules
                if k == 'deployment_rules':
                    if normalize_json(v) == normalize_json(orig_v):
                        continue
                
                has_real_changes = True
                break
        else:
            # Batch: if any value is not "KEEP" and not None
            has_real_changes = any(v is not None and v != "KEEP" for v in data.values())

        if not has_real_changes:
            from src.ui.toast import Toast
            Toast.show_toast(self, _("変更はありません"), preset="warning")
            return

        # Map original_config to dictionary of {path: config} for the unified method
        original_configs_map = {}
        if not is_batch:
            original_configs_map[target_paths[0]] = original_config
        
        # Call consolidated method
        self._apply_folder_config_updates(target_paths, data, original_configs=original_configs_map, is_batch=is_batch)

    def _set_visibility_single(self, rel_path, visible: bool, update_ui=True):
        """Set visibility for a single item."""
        try:
            self.db.update_folder_display_config(rel_path, is_visible=(1 if visible else 0))
            if update_ui:
                app_data = self.app_combo.currentData()
                storage_root = app_data.get('storage_root') if app_data else None
                if storage_root:
                    full_path = os.path.join(storage_root, rel_path)
                    self._update_card_hidden_by_path(full_path, not visible)
            return True
        except Exception as e:
            self.logger.error(f"Failed to set visibility for {rel_path}: {e}")
            return False

    def _set_favorite_single(self, rel_path, favorite: bool, update_ui=True):
        """Set favorite state for a single item."""
        try:
            self.db.update_folder_display_config(rel_path, is_favorite=(1 if favorite else 0))
            if update_ui:
                app_data = self.app_combo.currentData()
                storage_root = app_data.get('storage_root') if app_data else None
                if storage_root:
                    full_path = os.path.join(storage_root, rel_path)
                    self._update_card_favorite_by_path(full_path, favorite)
            return True
        except Exception as e:
            self.logger.error(f"Failed to set favorite for {rel_path}: {e}")
            return False

    def _update_card_favorite_by_path(self, abs_path, is_favorite: bool):
        """Update a single card's favorite state by its absolute path."""
        abs_path_norm = abs_path.replace('\\', '/')
        for layout in [self.cat_layout, self.pkg_layout]:
            for i in range(layout.count()):
                w = layout.itemAt(i).widget()
                if isinstance(w, ItemCard) and w.path.replace('\\', '/') == abs_path_norm:
                    w.update_data(is_favorite=is_favorite)
                    return

    def _trash_single(self, abs_path, update_ui=True):
        """Move a single item to trash."""
        if update_ui:
            self._update_card_trashed_by_path(abs_path, True)
            QTimer.singleShot(300, lambda: self._do_trash_move(abs_path))
            return True
        else:
            return self._do_trash_move(abs_path)
    
    def _do_trash_move(self, abs_path):
        """Actually move the file to trash."""
        app_data = self.app_combo.currentData()
        if not app_data: return False
        
        # Phase 66: Unlink before trash to avoid orphaned/dead links
        if hasattr(self, 'deployer') and self.deployer:
            try:
                storage_root = app_data.get('storage_root')
                if storage_root:
                    # Robust relative path calculation
                    rel_path = os.path.relpath(abs_path, storage_root).replace('\\', '/')
                    if rel_path == ".": rel_path = ""
                    
                    # Unlink from all targets to be exhaustive
                    target_roots = [
                        app_data.get('target_root'),
                        app_data.get('target_root_2'),
                        app_data.get('target_root_3')
                    ]
                    for root in target_roots:
                        if root and os.path.isdir(root):
                            self.deployer.unlink_folder(app_data['name'], rel_path, root)
            except Exception as e:
                self.logger.error(f"Failed to unlink before trash: {e}")
        
        # Use new resource/app/{app}/Trash path
        trash_root = get_trash_dir(app_data['name'])
            
        name = os.path.basename(abs_path)
        dest = os.path.join(trash_root, name)
        
        if os.path.exists(dest):
            dest = os.path.join(trash_root, f"{name}_{int(time.time())}")
            
        try:
            import shutil
            shutil.move(abs_path, dest)
            self.logger.info(f"Moved {name} to Trash")

            try:
                original_rel = os.path.relpath(abs_path, app_data['storage_root']).replace('\\', '/')
                if original_rel == ".": original_rel = ""
                trash_rel = os.path.relpath(dest, app_data['storage_root']).replace('\\', '/')
                if trash_rel == ".": trash_rel = ""

                self.db.update_folder_display_config(trash_rel)
                self.db.store_item_origin(trash_rel, original_rel)
            except Exception as e:
                self.logger.error(f"Failed to store trash origin: {e}")
            
            self._remove_card_by_path(abs_path)
            self.db.update_folder_display_config(original_rel, last_known_status='unlinked')
            self._refresh_tag_visuals()
            return True
        except Exception as e:
            self.logger.error(f"Trash error: {e}")
            self._update_card_trashed_by_path(abs_path, False)
            return False

    def _update_card_hidden_by_path(self, abs_path, is_hidden: bool):
        """Update a single card's hidden state by its absolute path."""
        abs_path_norm = abs_path.replace('\\', '/')
        for layout in [self.cat_layout, self.pkg_layout]:
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget():
                    w = item.widget()
                    if isinstance(w, ItemCard):
                        card_path_norm = w.path.replace('\\', '/') if w.path else ''
                        if card_path_norm == abs_path_norm:
                            w.update_hidden(is_hidden)
                            return
    
    def _update_card_trashed_by_path(self, abs_path, is_trashed: bool):
        """Update a single card's trashed state by its absolute path."""
        for layout in [self.cat_layout, self.pkg_layout]:
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget():
                    w = item.widget()
                    if isinstance(w, ItemCard) and w.path == abs_path:
                        w.update_trashed(is_trashed)
                        return
    
    def _remove_card_by_path(self, abs_path):
        """Remove a single card from the view."""
        card = self._get_active_card_by_path(abs_path)
        if card:
            self._release_card(card)

    def _update_card_by_path(self, abs_path):
        """Update a single card's visual state by its absolute path. Robust normalization."""
        def norm(p):
            try:
                # Harmonize slashes and handle case-insensitivity on Windows
                return os.path.normpath(p).replace('\\', '/').lower() if os.name == 'nt' else os.path.normpath(p)
            except:
                return p

        target_path = norm(abs_path)
        card_found = False
        
        # INFO Logging for debugging (as requested)
        self.logger.info(f"[CardUpdate] Looking for: {target_path}")
        
        for layout_name, layout in [('cat', self.cat_layout), ('pkg', self.pkg_layout)]:
            if not layout: continue
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget():
                    w = item.widget()
                    if isinstance(w, ItemCard):
                        w_path = norm(w.path or "")
                        if w_path == target_path:
                            self.logger.info(f"[CardUpdate] HIT in {layout_name}_layout: {w.folder_name}")
                            
                            # Phase 51: DO NOT force 'linked' status. Let the card re-detect its actual state
                            # (which handles excludes and partial failures correctly).
                            w.update_link_status() # This triggers _check_link_status()
                            
                            # Force full Widget repaint and overlay refresh
                            w.update()
                            card_found = True
                            break
            if card_found: break
        
        if not card_found:
            self.logger.warning(f"[CardUpdate] Card NOT found for: {target_path}")
            
        # Restore hierarchical refresh to ensure category frames are correct
        self._update_parent_category_status()

