"""
Link Master: Batch Operations Mixin
Extracted from LinkMasterWindow for modularity.
"""
import os
import logging
import time
from PyQt6.QtWidgets import QMessageBox
from src.ui.link_master.item_card import ItemCard
from PyQt6.QtCore import QThread
from .lm_batch_ops_worker import TagConflictWorker
from src.core.link_master.core_paths import get_trash_dir


class LMBatchOpsMixin:
    """Mixin providing batch operation methods for LinkMasterWindow."""
    
    def _update_cards_link_status(self, paths):
        """Partial update: Update link status for specific cards without rebuild."""
        for layout in [self.cat_layout, self.pkg_layout]:
            for i in range(layout.count()):
                w = layout.itemAt(i).widget()
                if isinstance(w, ItemCard) and w.path in paths:
                    w.update_link_status()  # Re-check and update border
                    
        # Note: Removed _update_parent_category_status() for performance
        # self._update_parent_category_status()
        
        # Phase 28 RE-FIX: Always trigger a full tag/library refresh after status change
        self._refresh_tag_visuals()
    
    def _update_cards_hidden_state(self, paths, is_hidden: bool):
        """Partial update: Update hidden state for specific cards without rebuild."""
        for layout in [self.cat_layout, self.pkg_layout]:
            for i in range(layout.count()):
                w = layout.itemAt(i).widget()
                if isinstance(w, ItemCard) and w.path in paths:
                    w.update_hidden(is_hidden)
    
    def _update_parent_category_status(self):
        """Update parent category cards to reflect child link status.
        
        Delegates to _refresh_category_cards which properly scans child
        packages for their link status using _scan_children_status.
        """
        # Use the correct method from LMScanHandlerMixin
        if hasattr(self, '_refresh_category_cards'):
            self._refresh_category_cards()

    
    def _batch_open_in_explorer(self):
        """Opens selected folders in Windows Explorer."""
        if not self.selected_paths: return
        import subprocess
        # Limit to 5 at once
        paths = list(self.selected_paths)[:5]
        for p in paths:
            if os.path.exists(p):
                subprocess.Popen(['explorer', os.path.normpath(p)])

    def _batch_deploy_selected(self):
        """Deploys all selected items."""
        if not self.selected_paths: return
        self.logger.info(f"Batch Deploy: {len(self.selected_paths)} items")
        
        app_data = self.app_combo.currentData()
        if not app_data: return
        storage_root = app_data.get('storage_root')
        if not storage_root: return
        
        # Convert to relative paths and call _deploy_items
        rel_paths = []
        for path in self.selected_paths:
            try:
                rel = os.path.relpath(path, storage_root).replace('\\', '/')
                if rel == ".": rel = ""
                rel_paths.append(rel)
            except: pass
        
        if rel_paths:
            self._deploy_items(rel_paths, skip_refresh=True)
            # Partial update instead of full rebuild
            self._update_cards_link_status(self.selected_paths)

    def _resolve_dependencies(self, rel_paths):
        """
        Recursively find all required libraries for the given rel_paths.
        Returns a list of rel_paths for libraries in deployment order (dependencies first).
        """
        import json
        resolved_libs = [] # List of rel_path
        seen_lib_names = {} # lib_name -> selected_rel_path
        
        all_configs = self.db.get_all_folder_configs()
        # Group libraries by name for resolution
        libraries_by_name = {}
        for rp, cfg in all_configs.items():
            if cfg.get('is_library'):
                lname = cfg.get('lib_name')
                if lname:
                    if lname not in libraries_by_name: libraries_by_name[lname] = []
                    cfg['_rel_path'] = rp
                    libraries_by_name[lname].append(cfg)

        def resolve_recursive(rel_path):
            cfg = all_configs.get(rel_path, {})
            deps_str = cfg.get('lib_deps', '[]')
            try:
                deps = json.loads(deps_str) if deps_str else []
            except:
                deps = []
                
            for dep in deps:
                # Handle both string (legacy/simple) and dict (advanced) formats
                if isinstance(dep, str): 
                    dep_name = dep
                    mode = 'priority'
                    target_ver = None
                else: 
                    dep_name = dep.get('name')
                    mode = dep.get('version_mode', 'priority') # 'latest', 'priority', 'specific'
                    target_ver = dep.get('version')
                
                if not dep_name: continue
                if dep_name in seen_lib_names: 
                     # Already resolved this library? Check if version conflict? 
                     # For now, first come first served (or "Priority" wins effectively if sorted right)
                     continue 
                
                # Find candidates
                candidates = libraries_by_name.get(dep_name, [])
                if not candidates:
                    self.logger.warning(f"Dependency not found: {dep_name}")
                    continue
                
                # Filter/Sort based on Mode
                selected_cfg = None
                
                if mode == 'specific' and target_ver:
                    # Find exact match
                    for c in candidates:
                        if c.get('lib_version') == target_ver:
                            selected_cfg = c
                            break
                    if not selected_cfg:
                        self.logger.warning(f"Specific version {target_ver} for {dep_name} not found. Falling back to priority.")
                
                if not selected_cfg:
                    # Sort candidates
                    if mode == 'latest':
                        # Sort by version text descending
                        candidates.sort(key=lambda x: x.get('lib_version', ''), reverse=True)
                    else:
                        # Priority: lib_priority DESC, then lib_version DESC
                        candidates.sort(key=lambda x: (x.get('lib_priority', 0), x.get('lib_version', '')), reverse=True)
                        
                    selected_cfg = candidates[0]

                selected_rp = selected_cfg['_rel_path']
                
                seen_lib_names[dep_name] = selected_rp
                resolve_recursive(selected_rp) 
                
                if selected_rp not in resolved_libs:
                    resolved_libs.append(selected_rp)

        for rp in rel_paths:
            resolve_recursive(rp)
            
        return resolved_libs

    def _batch_separate_selected(self):
        """Removes links for all selected items."""
        if not self.selected_paths: return
        self.logger.info(f"Batch Separate: {len(self.selected_paths)} items")
        
        app_data = self.app_combo.currentData()
        if not app_data: return
        storage_root = app_data.get('storage_root')
        if not storage_root: return
        
        # Convert to relative paths and call _remove_links
        rel_paths = []
        for path in self.selected_paths:
            try:
                rel = os.path.relpath(path, storage_root).replace('\\', '/')
                if rel == ".": rel = ""
                rel_paths.append(rel)
            except: pass
        
        if rel_paths:
            self._remove_links(rel_paths, skip_refresh=True)
            # Partial update instead of full rebuild
            self._update_cards_link_status(self.selected_paths)

    def _batch_visibility_selected(self, visible: bool):
        """Toggles visibility for all selected items. Uses core _set_visibility_single."""
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
            
        # Batch update: update all affected cards at once
        self._update_cards_hidden_state(self.selected_paths, not visible)

    def _batch_trash_selected(self):
        """Moves all selected items to trash. Uses core _trash_single."""
        if not self.selected_paths: return
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Batch Trash")
        msg.setText(f"Move {len(self.selected_paths)} items to trash?")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if msg.exec() != QMessageBox.StandardButton.Yes: return
        
        # Use core _trash_single for each item (shows strikethrough first)
        for path in list(self.selected_paths):
            self._trash_single(path, update_ui=True)
            
        self.selected_paths.clear()
        # Individual _trash_single calls now handle UI removal (no-rebuild)


    def _batch_restore_selected(self):
        """Restores all selected items from trash."""
        if not self.selected_paths: return
        for path in list(self.selected_paths):
            self._on_package_restore(path, refresh=False)
        self.selected_paths.clear()
        # Individual _on_package_restore calls now handle UI removal


    def _batch_unclassified_selected(self):
        """Moves all selected misplaced items to unclassified."""
        if not self.selected_paths: return
        self.logger.info(f"Batch Unclassified: {len(self.selected_paths)} items")
        for path in list(self.selected_paths):
            self._on_package_move_to_unclassified(path)
        self.selected_paths.clear()
        self._refresh_current_view()

    def _open_properties_for_path(self, abs_path: str):
        """Opens property edit dialog for a single path (Alt+Double-Click shortcut)."""
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
            app_cat_style_default=app_data.get('default_category_style', 'image_text'),
            app_pkg_style_default=app_data.get('default_package_style', 'image_text')
        )
        if dialog.exec():
            data = dialog.get_data()
            
            self.db.update_folder_display_config(rel, **data)
            
            # Targeted UI update
            abs_norm = abs_path.replace('\\', '/')
            card = self._get_active_card_by_path(abs_norm)
            if card:
                card.update_data(**data)
            
            # If Conflict Tag or Scope changed, refresh related cards
            if 'conflict_tag' in data or 'conflict_scope' in data:
                 self._refresh_tag_visuals()

    def _open_properties_from_rel_path(self, rel_path: str):
        """Wrapper to open properties EDIT dialog from a relative path (for library panel signals)."""
        app_data = self.app_combo.currentData()
        if not app_data:
            return
        storage_root = app_data.get('storage_root')
        if not storage_root:
            return
        abs_path = os.path.join(storage_root, rel_path)
        self._open_properties_for_path(abs_path)

    def _view_properties_from_rel_path(self, rel_path: str):
        """Open PreviewWindow (read-only view) from a relative path (for library panel 表示 buttons)."""
        app_data = self.app_combo.currentData()
        if not app_data:
            return
        storage_root = app_data.get('storage_root')
        if not storage_root:
            return
        abs_path = os.path.join(storage_root, rel_path)
        
        from src.ui.link_master.preview_window import PreviewWindow
        
        # Get folder config
        folder_config = self.db.get_folder_config(rel_path) or {}
        
        # Get preview paths from folder
        preview_paths = []
        if os.path.isdir(abs_path):
            manual_preview = folder_config.get('manual_preview_path', '')
            if manual_preview:
                preview_paths = [p.strip() for p in manual_preview.split(';') if p.strip()]
            else:
                # Auto-detect images
                image_exts = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')
                try:
                    for f in os.listdir(abs_path):
                        if f.lower().endswith(image_exts):
                            preview_paths.append(os.path.join(abs_path, f))
                except:
                    pass
        
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

    def _deploy_single_from_rel_path(self, rel_path: str):
        """Wrapper for library panel deploy signal."""
        self._deploy_single(rel_path, update_ui=True)

    def _unlink_single_from_rel_path(self, rel_path: str):
        """Wrapper for library panel unlink signal."""
        self._unlink_single(rel_path, update_ui=True)

    def _batch_edit_properties_selected(self):
        """Opens property edit dialog (Single or Batch mode)."""
        if not self.selected_paths: return
        
        app_data = self.app_combo.currentData()
        if not app_data: return
        
        from src.ui.link_master.dialogs import FolderPropertiesDialog
        
        if len(self.selected_paths) == 1:
            # Single Mode
            path = list(self.selected_paths)[0]
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
                app_pkg_style_default=app_data.get('default_package_style', 'image'),
                app_skip_levels_default=app_data.get('default_skip_levels', 0)

            )
            if dialog.exec():
                data = dialog.get_data()
                
                # Phase 3.5: Identify if link-impacting properties changed
                LINK_AFFECTING_KEYS = {
                    'folder_type', 'deploy_type', 'conflict_policy', 
                    'deployment_rules', 'inherit_tags', 'conflict_tag', 'conflict_scope'
                }
                impacts_link = any(k in data and data[k] != current_config.get(k) for k in LINK_AFFECTING_KEYS)
                
                self.db.update_folder_display_config(rel, **data)
                
                # Targeted UI + Auto-Sync
                abs_norm = os.path.normpath(path).replace('\\', '/')
                card = self._get_active_card_by_path(abs_norm)
                
                # Handling Profiling Log
                self.logger.info(f"PROFILE: Property Edit Return. Path={abs_norm}")
                self.logger.info(f"PROFILE: Dialog Data Keys: {list(data.keys())}")
                if 'image_path' in data:
                    self.logger.info(f"PROFILE: New image_path: {data['image_path']}")
                self.logger.info(f"PROFILE: Card found? {card is not None}")

                if card:
                    card.update_data(**data)
                    # Phase 3.5: Auto-sync if currently linked AND link properties changed
                    if card.link_status == 'linked' and impacts_link:
                        self.logger.info(f"Auto-syncing {rel} after link-impacting property change...")
                        self._deploy_single(rel)
                
                # Phase 28: If Conflict Tag, Scope, or LIBRARY properties changed, we MUST refresh related cards
                TAG_AFFECTING_KEYS = {'conflict_tag', 'conflict_scope', 'is_library', 'lib_name'}
                if any(k in data for k in TAG_AFFECTING_KEYS):
                     self._refresh_tag_visuals()
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
                app_pkg_style_default=app_data.get('default_package_style', 'image'),
                app_skip_levels_default=app_data.get('default_skip_levels', 0)

            )
            
            if dialog.exec():
                data = dialog.get_data()
                storage_root = app_data.get('storage_root')
                
                batch_updates = {k: v for k, v in data.items() if v is not None}
                if not batch_updates: return
                
                for path in self.selected_paths:
                    try:
                        rel = os.path.relpath(path, storage_root).replace('\\', '/')
                        if rel == ".": rel = ""
                        self.db.update_folder_display_config(rel, **batch_updates)
                        
                        # Phase 3.5: Batch Auto-sync
                        abs_norm = os.path.normpath(path).replace('\\', '/')
                        card = self._get_active_card_by_path(abs_norm)
                        if card:
                            card.update_data(**batch_updates)
                            if card.link_status == 'linked' and any(k in batch_updates for k in {'deploy_type', 'conflict_policy', 'deployment_rules'}):
                                self.logger.info(f"Auto-syncing batch item {rel}...")
                                self._deploy_single(rel)
                    except Exception as e:
                        self.logger.error(f"Batch update failed for {path}: {e}")
                
                # Phase 28: Batch Mode refresh for tags/libraries
                TAG_AFFECTING_KEYS = {'conflict_tag', 'conflict_scope', 'is_library', 'lib_name'}
                if any(k in batch_updates for k in TAG_AFFECTING_KEYS):
                     self._refresh_tag_visuals()

    # ===== Core Single-Item Methods =====
    
    def _set_visibility_single(self, rel_path, visible: bool, update_ui=True):
        """Set visibility for a single item. Core method for all visibility operations.
        
        Args:
            rel_path: Relative path from storage_root
            visible: True to show, False to hide
            update_ui: If True, update the card's visual state
        
        Returns:
            bool: True if successful
        """
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
    
    def _trash_single(self, abs_path, update_ui=True):
        """Move a single item to trash. Core method for all trash operations.
        
        Args:
            abs_path: Absolute path of the item to trash
            update_ui: If True, update the card's visual state (strikethrough)
        
        Returns:
            bool: True if successful
        """
        if update_ui:
            # Show strikethrough first, then move after a short delay
            self._update_card_trashed_by_path(abs_path, True)
            
            # Use QTimer to delay the actual file move for visual feedback
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(300, lambda: self._do_trash_move(abs_path))
            return True
        else:
            # Direct move without visual feedback (batch operation)
            return self._do_trash_move(abs_path)
    
    def _do_trash_move(self, abs_path):
        """Actually move the file to trash. Called after visual feedback delay."""
        app_data = self.app_combo.currentData()
        if not app_data: return False
        
        # Use new resource/app/{app}/Trash path
        trash_root = get_trash_dir(app_data['name'])
            
        name = os.path.basename(abs_path)
        dest = os.path.join(trash_root, name)
        
        import time
        if os.path.exists(dest):
            dest = os.path.join(trash_root, f"{name}_{int(time.time())}")
            
        try:
            import shutil
            shutil.move(abs_path, dest)
            self.logger.info(f"Moved {name} to Trash")

            # Store origin for restore
            try:
                original_rel = os.path.relpath(abs_path, app_data['storage_root']).replace('\\', '/')
                if original_rel == ".": original_rel = ""
                
                trash_rel = os.path.relpath(dest, app_data['storage_root']).replace('\\', '/')
                if trash_rel == ".": trash_rel = ""

                self.db.update_folder_display_config(trash_rel)
                self.db.store_item_origin(trash_rel, original_rel)
            except Exception as e:
                self.logger.error(f"Failed to store trash origin: {e}")
            
            # Remove the trashed card from view (instead of full rebuild)
            self._remove_card_by_path(abs_path)
            
            # Phase 28: Update DB status to ensure this item doesn't cause conflicts
            self.db.update_folder_display_config(original_rel, last_known_status='unlinked') # Set original to unlinked
            
            # Phase 28: Refresh visuals for others (ghost conflict removal)
            self._refresh_tag_visuals()
            
            return True
        except Exception as e:
            self.logger.error(f"Trash error: {e}")
            # Revert strikethrough on error
            self._update_card_trashed_by_path(abs_path, False)
            return False

    def _update_card_hidden_by_path(self, abs_path, is_hidden: bool):
        """Update a single card's hidden state by its absolute path."""
        # Normalize path for comparison
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
                            self.logger.debug(f"Updated hidden state for {abs_path}: {is_hidden}")
                            return
        self.logger.warning(f"Card not found for hidden update: {abs_path}")
    
    def _update_card_trashed_by_path(self, abs_path, is_trashed: bool):
        """Update a single card's trashed state (strikethrough) by its absolute path."""
        for layout in [self.cat_layout, self.pkg_layout]:
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget():
                    w = item.widget()
                    if isinstance(w, ItemCard) and w.path == abs_path:
                        w.update_trashed(is_trashed)
                        return
    
    def _remove_card_by_path(self, abs_path):
        """Phase 28: Remove a single card from the view by releasing it to the pool."""
        card = self._get_active_card_by_path(abs_path)
        if card:
            self._release_card(card)

    def _refresh_tag_visuals(self, target_tag=None):
        """
        Phase 28 Async: Background visual update for Tag Conflicts.
        Starts a thread to fetch DB and build active tag map.
        Updates UI on signal receipt.
        """
        app_data = self.app_combo.currentData()
        if not app_data: return
        
        # Initialize pending flag if not exists
        if not hasattr(self, '_tag_refresh_pending'):
            self._tag_refresh_pending = False
            
        # Guard: Check if thread exists and is running safely
        if hasattr(self, '_tag_sync_thread') and self._tag_sync_thread is not None:
            try:
                if self._tag_sync_thread.isRunning():
                    # Thread is busy. Mark pending so we run again immediately after finish.
                    self._tag_refresh_pending = True
                    return
            except RuntimeError:
                # Thread object deleted but reference remains
                self._tag_sync_thread = None

        # Parent QThread to self to prevent premature GC/Crash
        self._tag_sync_thread = QThread(self)
        
        # Phase 30: Get target_root from current app selection
        target_root = app_data.get(getattr(self, 'current_target_key', 'target_root'))
        
        # Pass DB PATH, not object, to ensure thread-local connection
        self._tag_sync_worker = TagConflictWorker(self.db.db_path, self.storage_root, target_root)
        self._tag_sync_worker.moveToThread(self._tag_sync_thread)
        
        # Connect signals
        self._tag_sync_thread.started.connect(self._tag_sync_worker.run)
        self._tag_sync_worker.finished.connect(self._on_tag_refresh_finished)
        self._tag_sync_worker.finished.connect(self._tag_sync_thread.quit)
        self._tag_sync_worker.finished.connect(self._tag_sync_worker.deleteLater)
        self._tag_sync_thread.finished.connect(self._tag_sync_thread.deleteLater)
        # Cleanup python reference
        self._tag_sync_thread.finished.connect(self._cleanup_tag_thread)
        
        self._tag_sync_thread.start()
    
    def _cleanup_tag_thread(self):
        """Clean up the Python reference to the thread."""
        self._tag_sync_thread = None

    def _on_card_deployment_requested(self, path):
        """Phase 30: Handle direct deployment toggle from card overlay button."""
        app_data = self.app_combo.currentData()
        if not app_data: return
        
        try:
            rel = os.path.relpath(path, self.storage_root).replace('\\', '/')
        except: return
        
        # Determine current status from DB cache/config
        config = self.db.get_folder_config(rel) or {}
        current_status = config.get('last_known_status', 'none')
        
        if current_status == 'linked':
            self.logger.info(f"[DirectAction] Unlinking {rel}")
            self._unlink_single(rel)
        else:
            self.logger.info(f"[DirectAction] Deploying {rel}")
            self._deploy_single(rel)
        
    def _on_tag_refresh_finished(self, result):
        """Callback from background worker. Updates visible cards on Main Thread."""
        start_t = time.time()
        if not result: return
        
        active_tags_map = result.get('active_tags_map', {})
        active_library_names = set(result.get('active_library_names', []))
        active_targets_map = result.get('active_targets_map', {})
        cached_configs = {k.replace('\\', '/'): v for k, v in result['all_configs'].items()} 
        
        # Phase 30: Get target_root from current app selection for matching logic
        app_data = self.app_combo.currentData()
        target_root = app_data.get(getattr(self, 'current_target_key', 'target_root')) if app_data else None
        
        change_count = 0
        card_count = 0

        # 1. Update Visible Packages (Tags and Libraries)
        for i in range(self.pkg_layout.count()):
            item = self.pkg_layout.itemAt(i)
            if item and item.widget():
                card = item.widget()
                card_count += 1
                card_changed = False
                
                # --- Library Indicator Logic ---
                try:
                    rel = os.path.relpath(card.path, self.storage_root).replace('\\', '/')
                except: rel = ""
                
                cfg = cached_configs.get(rel, {})
                
                # Use pre-calculated status from worker
                is_alt = cfg.get('is_library_alt_version', False)
                if getattr(card, 'is_library_alt_version', False) != is_alt:
                    # self.logger.debug(f"[LibSync] {rel}: is_alt={is_alt}")
                    card.is_library_alt_version = is_alt
                    card_changed = True

                # --- Package Tag Conflict Logic ---
                has_logical = cfg.get('has_logical_conflict', False)
                if getattr(card, 'has_logical_conflict', False) != has_logical:
                    # self.logger.debug(f"[TagSync] {rel}: conflict={has_logical}")
                    card.has_logical_conflict = has_logical
                    card_changed = True

                if card_changed:
                    # self.logger.debug(f"[HighlightSync] Updating Card: {rel} (alt={card.is_library_alt_version}, conflict={card.has_logical_conflict})")
                    change_count += 1
                    card._update_style()
                else:
                    # self.logger.debug(f"[HighlightSync] No Change for Card: {rel}")
                    pass
        
        # 1.5 Sync Logical/Library Flags to DB (Phase 2 Persistence)
        # OPTIMIZED: Use bulk update instead of individual commits.
        bulk_updates = {}
        for rel_p, cfg in cached_configs.items():
            is_alt = cfg.get('is_library_alt_version', False)
            has_logical = cfg.get('has_logical_conflict', False)
            bulk_updates[rel_p] = {
                'has_logical_conflict': 1 if has_logical else 0,
                'is_library_alt_version': 1 if is_alt else 0
            }
        
        self.db.update_visual_flags_bulk(bulk_updates)

        print(f"[Profile] Tag UI Refresh: Updated {change_count}/{card_count} visible cards, synced {len(bulk_updates)} DB configs (BULK). Total Time: {time.time()-start_t:.3f}s")
        
        # 2. Refresh Category Borders (Physical + Logical via children status)
        self._refresh_category_cards_cached(cached_configs)
        
        # 3. Synchronize Library Panel (Phase 2)
        if hasattr(self, 'library_panel') and self.library_panel:
             self.library_panel.refresh()

        # 4. Check Pending Queue to catch latest state
        if getattr(self, '_tag_refresh_pending', False):
            self._tag_refresh_pending = False
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._refresh_tag_visuals())

    def _refresh_category_cards_cached(self, cached_configs):
        """Updated helper to accept cache from async worker."""
        app_data = self.app_combo.currentData()
        if not app_data: return
        target_root = app_data.get(self.current_target_key)
        if not target_root: return
        
        for i in range(self.cat_layout.count()):
            item = self.cat_layout.itemAt(i)
            if item and item.widget():
                card = item.widget()
                if hasattr(card, 'path') and hasattr(card, 'set_children_status'):
                    # Pass cache
                    has_linked, has_conflict, has_partial = self._scan_children_status(card.path, target_root, cached_configs=cached_configs)
                    card.set_children_status(has_linked=has_linked, has_conflict=has_conflict, has_partial=has_partial)

    # Phase 28: Tag Conflict Logic
    def _check_tag_conflict(self, rel_path, config, app_data, cached_configs=None):
        """
        Check if deploying the item at rel_path causes a conflict based on 'conflict_tag'.
        Returns a conflict message string if a conflict exists, otherwise None.
        Phase 28 Optim: Accepts cached_configs to avoid O(N) DB calls.
        """
        tag = config.get('conflict_tag')
        if not tag: return None
        
        scope = config.get('conflict_scope', 'disabled')
        if scope == 'disabled': return None
        
        if cached_configs is not None:
             all_configs = cached_configs
        else:
             all_configs = self.db.get_all_folder_configs()
             
        target_root = app_data.get(self.current_target_key)
        if not target_root: return None
        
        current_category = os.path.dirname(rel_path).replace('\\', '/')
        
        for other_path, other_cfg in all_configs.items():
            if other_path == rel_path: continue # Skip self
            
            other_tag = other_cfg.get('conflict_tag')
            if other_tag != tag: continue
            
            # Check Scope
            # If MY scope is global, I check everyone.
            # If MY scope is category, I only check my category.
            # (Note: Logic applies to what *I* consider a conflict)
            if scope == 'category':
                other_cat = os.path.dirname(other_path).replace('\\', '/')
                if other_cat != current_category: continue
            
            # Phase 28 Optimization: Use 'last_known_status' from DB (recorded by _deploy_single/_scan)
            # This is much faster than checking file existence
            # Phase 28 Optimization: Use 'last_known_status' from DB (recorded by _deploy_single/_scan)
            # This is much faster than checking file existence
            if other_cfg.get('last_known_status') == 'linked':
                other_name = os.path.basename(other_path)
                # Conflict Found! Return details for Swap
                return {
                    'conflict': True,
                    'name': other_name,
                    'path': other_path,
                    'tag': tag,
                    'scope': scope
                }
        
        return None

    def _deploy_single(self, rel_path, update_ui=True):
        """Deploy a single item by relative path. Core method for all deploy operations."""
        app_data = self.app_combo.currentData()
        if not app_data: return False
        target_root = app_data.get(self.current_target_key)
        if not target_root: return False
        
        full_src = os.path.join(self.storage_root, rel_path)
        
        # Phase 3.5 enhancement: Force a sweep-unlink BEFORE deploying 
        # to ensure old redirections/rules are cleared from the disk.
        self._unlink_single(rel_path, update_ui=False)
        
        # Phase 5: Resolve Deployment Rule and Transfer Mode
        deploy_rule = config.get('deploy_rule')
        
        # Determine App-Default based on selected target
        app_rule_key = 'deployment_rule'
        if self.current_target_key == 'target_root_2': app_rule_key = 'deployment_rule_b'
        elif self.current_target_key == 'target_root_3': app_rule_key = 'deployment_rule_c'
        
        app_default_rule = app_data.get(app_rule_key) or app_data.get('deployment_rule', 'folder')
        
        if not deploy_rule or deploy_rule in ("default", "inherit"):
            deploy_rule = app_default_rule
        
        if deploy_rule == 'flatten': deploy_rule = 'files' # Legacy compat
            
        transfer_mode = config.get('transfer_mode')
        if not transfer_mode or transfer_mode == "default":
            transfer_mode = app_data.get('transfer_mode', 'symlink')

        c_policy = config.get('conflict_policy') or app_data.get('conflict_policy', 'backup')
        if c_policy == "default":
             c_policy = app_data.get('conflict_policy', 'backup')

        # Determine Target Link Path
        target_link = config.get('target_override')
        if not target_link:
            if deploy_rule == 'files':
                target_link = target_root
            elif deploy_rule == 'tree':
                # Reconstruct hierarchy from storage root (Phase 7 fix)
                import json
                rules_json = config.get('deployment_rules')
                skip_val = 0
                if rules_json:
                    try:
                        rules_obj = json.loads(rules_json)
                        skip_val = int(rules_obj.get('skip_levels', 0))
                    except: pass
                
                parts = rel_path.replace('\\', '/').split('/')
                if len(parts) > skip_val:
                    mirrored = "/".join(parts[skip_val:])
                    target_link = os.path.join(target_root, mirrored)
                else:
                    target_link = target_root # Fallback to root if all levels skipped
            else:
                target_link = os.path.join(target_root, folder_name)

        rules = config.get('deployment_rules')

        # Phase X: Library Version Conflict Check
        if config.get('is_library', 0):
            lib_name = config.get('lib_name')
            if lib_name:
                lib_name_norm = lib_name.strip().lower()
                all_configs = self.db.get_all_folder_configs()
                for other_path, other_cfg in all_configs.items():
                    if other_path == rel_path: continue
                    other_lib_name = other_cfg.get('lib_name')
                    if other_lib_name and other_lib_name.strip().lower() == lib_name_norm and \
                       other_cfg.get('last_known_status') == 'linked' and \
                       other_cfg.get('is_library', 0):
                        
                        old_ver = other_cfg.get('lib_version', 'Unknown')
                        new_ver = config.get('lib_version', 'Unknown')
                        msg = (f"すでに別のバージョンの「{lib_name}」が有効です。\n\n"
                               f"現在のバージョン: {old_ver}\n"
                               f"切り替え先: {new_ver}\n\n"
                               f"バージョンを切り替えますか？")
                        
                        reply = QMessageBox.question(self, "ライブラリ切り替え", msg,
                                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                        if reply == QMessageBox.StandardButton.Yes:
                            self.logger.info(f"[LibSwitch] Unlinking {other_path} to switch to {rel_path}")
                            self._unlink_single(other_path, update_ui=True)
                        else:
                            return False

        # Phase X: Library Dependencies (Deploy Deps First)
        # Check if we have libs to deploy
        deployed_lib_paths = []
        if config.get('lib_deps'):
            deps_to_deploy = self._resolve_dependencies([rel_path])
            if deps_to_deploy:
                self.logger.info(f"Auto-Deploying {len(deps_to_deploy)} dependencies for {folder_name}")
                for lib_rel in deps_to_deploy:
                     if lib_rel != rel_path:
                         # Deploy library with UI update for immediate feedback
                         lib_full = os.path.join(self.storage_root, lib_rel)
                         if self._deploy_single(lib_rel, update_ui=True):
                             deployed_lib_paths.append(lib_full)
        
        # Phase 28: Conflict Tag Check
        conflict_data = self._check_tag_conflict(rel_path, config, app_data)
        if conflict_data:
            msg = (f"Conflict Detected!\n\n"
                   f"Package '{conflict_data['name']}' is already active with tag '{conflict_data['tag']}'.\n"
                   f"Scope: {conflict_data['scope']}\n\n"
                   f"Overwrite target with link?\n"
                   f"This will DISABLE '{conflict_data['name']}' and enable '{folder_name}'.")
            
            # Using similar phrasing to standard overwrite dialog
            reply = QMessageBox.warning(self, "Conflict Swap", msg, 
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.Yes:
                # Swap Action: URLINK the other item first
                self.logger.info(f"Swapping: Disabling {conflict_data['name']} for {folder_name}")
                self._unlink_single(conflict_data['path'], update_ui=True)
                # Phase 28: Ensure the unlinked item gets its Red Line (Tag Conflict) immediately
                # Update visuals for both the old item (now unlinked -> might be red) and others
                self._refresh_tag_visuals(target_tag=conflict_data.get('tag'))
            else:
                return False

        success = self.deployer.deploy_with_rules(
            full_src, target_link, rules, 
            deploy_rule=deploy_rule, transfer_mode=transfer_mode, 
            conflict_policy=c_policy
        )
        
        if success:
             # Phase 28: Record status in DB for fast conflict checks
             self.db.update_folder_display_config(rel_path, last_known_status='linked')
             
             if update_ui:
                # Update only the affected card
                self._update_card_by_path(full_src)
                if hasattr(self, '_update_total_link_count'):
                    self._update_total_link_count()
                
                # Phase 28: Refresh Tag Conflict visuals for OTHERS now that I am linked
                # (My linking might have caused conflicts for them, or marked alts for libraries)
                tag = config.get('conflict_tag')
                is_lib = config.get('is_library', 0)
                if tag or is_lib:
                    self._refresh_tag_visuals(target_tag=tag)
                
                # Phase 2: Immediate Library Panel sync
                if hasattr(self, 'library_panel') and self.library_panel:
                    self.library_panel.refresh()
        
        return success
    
    def _unlink_single(self, rel_path, update_ui=True, _cascade=True):
        """Remove link for a single item by relative path. Core method for all unlink operations."""
        app_data = self.app_combo.currentData()
        if not app_data: return False
        
        # Sweep all potential target roots for this app (Sweep ALL to ensure absolute cleanup)
        search_roots = []
        if 'target_root' in app_data: search_roots.append(app_data['target_root'])
        if 'target_root_2' in app_data: search_roots.append(app_data['target_root_2'])
        if 'target_root_3' in app_data: search_roots.append(app_data['target_root_3'])
        
        # Also include any specifically overridden top-level targets for this mod
        config = self.db.get_folder_config(rel_path) or {}
        if config.get('target_override'):
             search_roots.append(config.get('target_override'))
             
        full_src = os.path.join(self.storage_root, rel_path)
        
        self.logger.debug(f"Exhaustive sweep unlinking for: {rel_path}")
        self.deployer.remove_links_pointing_to(search_roots, full_src)
        
        # Phase 28: Record status in DB
        self.db.update_folder_display_config(rel_path, last_known_status='unlinked')

        # Phase 28: If this is a LIBRARY, find and unlink all packages that depend on it
        if _cascade and config.get('is_library', 0):
            lib_name = config.get('lib_name')
            if lib_name:
                dependent_packages = self._find_packages_depending_on_library(lib_name)
                if dependent_packages:
                    reply = QMessageBox.question(
                        self, "依存パッケージをアンリンク", 
                        f"ライブラリ「{lib_name}」をアンリンクしました。\n\n"
                        f"このライブラリに依存する {len(dependent_packages)} 個のパッケージもアンリンクしますか？",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        for dep_rel in dependent_packages:
                            self._unlink_single(dep_rel, update_ui=True, _cascade=False)

        if update_ui:
            self._update_card_by_path(full_src)
            if hasattr(self, '_update_total_link_count'):
                self._update_total_link_count()
            
            # Phase 2: Immediate Library Panel sync
            if hasattr(self, 'library_panel') and self.library_panel:
                self.library_panel.refresh()
            
            # Phase 28 RE-FIX: Always trigger a full tag/library refresh after status change
            # This ensures "Library Alternative" markers (yellow-green) update for cards
            # that weren't directly part of this operation.
            self._refresh_tag_visuals()
            if hasattr(self, '_update_total_link_count'):
                self._update_total_link_count()
            
            # Phase 28: Refresh Tag Conflict visuals for OTHERS
            # (If I was the source of a conflict, unlinking me should clear their red lines)
        
        return True

    def _find_packages_depending_on_library(self, lib_name: str) -> list:
        """Find all linked packages that have a dependency on the specified library."""
        import json
        dependent_packages = []
        all_configs = self.db.get_all_folder_configs()
        
        for rel_path, cfg in all_configs.items():
            # Skip libraries themselves
            if cfg.get('is_library', 0):
                continue
            # Only consider currently linked packages
            if cfg.get('last_known_status') != 'linked':
                continue
            
            lib_deps_json = cfg.get('lib_deps', '[]')
            try:
                lib_deps = json.loads(lib_deps_json) if lib_deps_json else []
            except:
                lib_deps = []
            
            if lib_name in lib_deps:
                dependent_packages.append(rel_path)
        
        return dependent_packages
    
    
    def _update_card_by_path(self, abs_path):
        """Update a single card's visual state by its absolute path."""
        # Phase 28 Fix: Normalize path for matching to avoid case-sensitivity issues
        target_path = os.path.normpath(abs_path).lower() if os.name == 'nt' else abs_path
        
        # DEBUG LOGGING for UI Update
        self.logger.debug(f"[UIUpdate] Targeting: {target_path} (Original: {abs_path})")

        for layout in [self.cat_layout, self.pkg_layout]:
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget():
                    w = item.widget()
                    if isinstance(w, ItemCard):
                        w_path = os.path.normpath(w.path).lower() if os.name == 'nt' else w.path
                        if w_path == target_path:
                            # Use display_name instead of text()
                            self.logger.info(f"[UIUpdate] HIT: {getattr(w, 'display_name', 'Unknown')}")
                            w.update_link_status()
                            return
        self.logger.warning(f"[UIUpdate] MISS: No card found for {target_path}")
        # Note: Removed _update_parent_category_status() for performance
        # self._update_parent_category_status()

    # ===== Batch Wrappers (use single-item methods) =====
    
    def _deploy_items(self, rel_paths, skip_refresh=False):
        """Deploy multiple items. Wrapper around _deploy_single."""
        for rel in rel_paths:
            if not self._deploy_single(rel, update_ui=False):
                QMessageBox.warning(self, "Deploy Error", f"Failed to deploy {rel}")
                break
        
        if not skip_refresh:
            # Convert to absolute paths for update
            abs_paths = [os.path.join(self.storage_root, rel) for rel in rel_paths]
            self._update_cards_link_status(set(abs_paths))
            if hasattr(self, '_update_total_link_count'):
                self._update_total_link_count()

    def _remove_links(self, rel_paths, skip_refresh=False):
        """Remove links for multiple items. Wrapper around _unlink_single."""
        for rel in rel_paths:
            if not self._unlink_single(rel, update_ui=False):
                self.logger.warning(f"Failed to remove link for {rel}")
        
        if not skip_refresh:
            # Convert to absolute paths for update
            abs_paths = [os.path.join(self.storage_root, rel) for rel in rel_paths]
            self._update_cards_link_status(set(abs_paths))
            if hasattr(self, '_update_total_link_count'):
                self._update_total_link_count()
