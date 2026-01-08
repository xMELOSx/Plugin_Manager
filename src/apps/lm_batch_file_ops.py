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
                    
        # Note: Removed _update_parent_category_status() for performance
        # self._update_parent_category_status()
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
        """Opens property edit dialog for a single path."""
        app_data = self.app_combo.currentData()
        if not app_data: return
        
        from src.ui.link_master.dialogs import FolderPropertiesDialog
        storage_root = app_data.get('storage_root')
        try:
            rel = os.path.relpath(abs_path, storage_root).replace('\\', '/')
            if rel == ".": rel = ""
        except: rel = ""
        
        current_config = self.db.get_folder_config(rel) or {}
        
        dialog = FolderPropertiesDialog(
            parent=self,
            folder_path=abs_path,
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
        if dialog.exec():
            data = dialog.get_data()
            
            # Phase 14: Auto-Redeploy on Settings Change
            # If item was linked and deployment settings changed, re-deploy with new settings
            was_linked = current_config.get('last_known_status') == 'linked'
            old_rule = current_config.get('deploy_rule') or current_config.get('deploy_type')
            old_mode = current_config.get('transfer_mode', 'symlink')
            new_rule = data.get('deploy_rule')
            new_mode = data.get('transfer_mode', 'symlink')
            
            settings_changed = (old_rule != new_rule) or (old_mode != new_mode)
            
            if was_linked and settings_changed:
                self.logger.info(f"[AutoRedeploy] Settings changed for linked item: {rel}")
                self.logger.info(f"  Old: rule={old_rule}, mode={old_mode}")
                self.logger.info(f"  New: rule={new_rule}, mode={new_mode}")
                
                # Unlink using OLD settings (before DB update)
                # This is handled by _unlink_single which reads from current DB
                self._unlink_single(rel, update_ui=False)
            
            # Save new settings to DB
            self.db.update_folder_display_config(rel, **data)
            
            # Re-deploy with new settings if was linked and settings changed
            if was_linked and settings_changed:
                self.logger.info(f"[AutoRedeploy] Re-deploying with new settings: {rel}")
                self._deploy_single(rel, update_ui=True)
            
            abs_norm = abs_path.replace('\\', '/')
            card = self._get_active_card_by_path(abs_norm)
            if card:
                card.update_data(**data)
            
            if 'conflict_tag' in data or 'conflict_scope' in data:
                 self._refresh_tag_visuals()

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

    def _on_property_edit_accepted(self, dialog, is_batch, target_paths, original_config):
        """Handle saving and UI updates after non-modal property dialog is accepted."""
        data = dialog.get_data()
        app_data = self.app_combo.currentData()
        if not app_data: return
        storage_root = app_data.get('storage_root')
        
        LINK_AFFECTING_KEYS = {
            'folder_type', 'deploy_type', 'conflict_policy', 
            'deployment_rules', 'inherit_tags', 'conflict_tag', 'conflict_scope'
        }
        TAG_AFFECTING_KEYS = {'conflict_tag', 'conflict_scope', 'is_library', 'lib_name'}
        
        if not is_batch:
            # Single Mode Update
            path = target_paths[0]
            try:
                rel = os.path.relpath(path, storage_root).replace('\\', '/')
                if rel == ".": rel = ""
            except: rel = ""
            
            impacts_link = any(k in data and data[k] != original_config.get(k) for k in LINK_AFFECTING_KEYS)
            self.db.update_folder_display_config(rel, **data)
            
            abs_norm = path.replace('\\', '/')
            card = self._get_active_card_by_path(abs_norm)
            if card:
                card.update_data(**data)
                if card.link_status == 'linked' and impacts_link:
                    self.logger.info(f"Auto-syncing {rel} after link-impacting property change...")
                    self._deploy_single(rel)
        else:
            # Batch Mode Update
            batch_updates = {k: v for k, v in data.items() if v is not None and v != "KEEP"}
            if not batch_updates: return
            
            for path in target_paths:
                try:
                    rel = os.path.relpath(path, storage_root).replace('\\', '/')
                    if rel == ".": rel = ""
                    self.db.update_folder_display_config(rel, **batch_updates)
                    
                    abs_norm = path.replace('\\', '/')
                    card = self._get_active_card_by_path(abs_norm)
                    if card:
                        card.update_data(**batch_updates)
                        if card.link_status == 'linked' and any(k in batch_updates for k in {'deploy_type', 'conflict_policy', 'deployment_rules'}):
                            self.logger.info(f"Auto-syncing batch item {rel}...")
                            self._deploy_single(rel)
                except Exception as e:
                    self.logger.error(f"Batch update failed for {path}: {e}")
        
        if any(k in data for k in TAG_AFFECTING_KEYS):
             self._refresh_tag_visuals()

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
        # Debug logging (set to debug level for cleaner output)
        # self.logger.debug(f"[CardUpdate] Looking for: {target_path}")
        for layout in [self.cat_layout, self.pkg_layout]:
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget():
                    w = item.widget()
                    if isinstance(w, ItemCard):
                        w_path = norm(w.path or "")
                        if w_path == target_path:
                            # self.logger.debug(f"[CardUpdate] Found card: {w.folder_name}")
                            if getattr(w, 'is_package', True):
                                w.update_link_status()
                            else:
                                # For categories, we need a hierarchical refresh!
                                if hasattr(self, '_refresh_category_cards'):
                                    self._refresh_category_cards()
                            card_found = True
                            break
            if card_found: break
        
        if not card_found:
            self.logger.debug(f"[CardUpdate] Card NOT found for: {target_path}")
            
        # Note: Removed _update_parent_category_status() call here for performance.
        # Individual card update via QTimer.singleShot now handles overlay updates properly.

