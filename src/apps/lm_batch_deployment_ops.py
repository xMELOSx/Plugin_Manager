"""
Link Master: Batch Deployment Operations Mixin
Handles symlinking, dependency resolution, and tag conflict checks.
"""
import os
import logging
import time
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import QThread, QTimer

from src.core.lang_manager import _
from .lm_batch_ops_worker import TagConflictWorker

class LMDeploymentOpsMixin:
    """Mixin for deployment-related batch operations."""

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

    def _deploy_single_from_rel_path(self, rel_path: str):
        """Wrapper for library panel deploy signal."""
        self._deploy_single(rel_path, update_ui=True)

    def _unlink_single_from_rel_path(self, rel_path: str):
        """Wrapper for library panel unlink signal."""
        self._unlink_single(rel_path, update_ui=True)

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
                        candidates.sort(key=lambda x: x.get('lib_version', ''), reverse=True)
                    else:
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

    def _check_tag_conflict(self, rel_path, config, app_data, cached_configs=None):
        """
        Check if deploying the item at rel_path causes a conflict based on 'conflict_tag'.
        Returns a conflict message string if a conflict exists, otherwise None.
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
            
            if scope == 'category':
                other_cat = os.path.dirname(other_path).replace('\\', '/')
                if other_cat != current_category: continue
            
            if other_cfg.get('last_known_status') == 'linked':
                other_name = os.path.basename(other_path)
                return {
                    'conflict': True,
                    'name': other_name,
                    'path': other_path,
                    'tag': tag,
                    'scope': scope
                }
        
        return None

    def _deploy_single(self, rel_path, update_ui=True, show_result=False):
        """Deploy a single item by relative path. Core method for all deploy operations."""
        app_data = self.app_combo.currentData()
        if not app_data: return False
        target_root = app_data.get(self.current_target_key)
        if not target_root: return False
        
        full_src = os.path.join(self.storage_root, rel_path)
        
        # Force sweep-unlink before deploying
        self._unlink_single(rel_path, update_ui=False)
        
        config = self.db.get_folder_config(rel_path) or {}
        folder_name = os.path.basename(rel_path)
        target_link = config.get('target_override') or os.path.join(target_root, folder_name)
        
        rules = config.get('deployment_rules')
        d_type = config.get('deploy_type') or app_data.get('deployment_type', 'folder')
        c_policy = config.get('conflict_policy') or app_data.get('conflict_policy', 'backup')

        # Library Version Conflict Check
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
                        
                        reply = QMessageBox.question(self, _("Library Switch"), msg,
                                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                        if reply == QMessageBox.StandardButton.Yes:
                            self.logger.info(f"[LibSwitch] Unlinking {other_path} to switch to {rel_path}")
                            self._unlink_single(other_path, update_ui=True)
                        else:
                            return False

        # Library Dependencies
        if config.get('lib_deps'):
            deps_to_deploy = self._resolve_dependencies([rel_path])
            if deps_to_deploy:
                self.logger.info(f"Auto-Deploying {len(deps_to_deploy)} dependencies for {folder_name}")
                for lib_rel in deps_to_deploy:
                     if lib_rel != rel_path:
                         self._deploy_single(lib_rel, update_ui=True)
        
        # Conflict Tag Check
        conflict_data = self._check_tag_conflict(rel_path, config, app_data)
        if conflict_data:
            msg = (f"Conflict Detected!\n\n"
                   f"Package '{conflict_data['name']}' is already active with tag '{conflict_data['tag']}'.\n"
                   f"Scope: {conflict_data['scope']}\n\n"
                   f"Overwrite target with link?\n"
                   f"This will DISABLE '{conflict_data['name']}' and enable '{folder_name}'.")
            
            reply = QMessageBox.warning(self, _("Conflict Swap"), msg, 
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.Yes:
                self.logger.info(f"Swapping: Disabling {conflict_data['name']} for {folder_name}")
                self._unlink_single(conflict_data['path'], update_ui=True)
                self._refresh_tag_visuals(target_tag=conflict_data.get('tag'))
            else:
                return False

        success = self.deployer.deploy_with_rules(
            full_src, target_link, rules, 
            deploy_type=d_type, conflict_policy=c_policy
        )
        
        if success:
             self.db.update_folder_display_config(rel_path, last_known_status='linked')
             
             if show_result and hasattr(self.deployer, 'last_actions') and self.deployer.last_actions:
                actions = self.deployer.last_actions
                msg = _("Deployment successful with conflict handling:\n")
                for act in actions:
                    t = act.get('type')
                    p = os.path.basename(act.get('path'))
                    if t == 'backup': msg += _("- Backup created for {path}\n").format(path=p)
                    elif t == 'overwrite': msg += _("- Overwritten existing {path}\n").format(path=p)
                QMessageBox.information(self, _("Conflict Handled"), msg)

             if update_ui:
                self._update_card_by_path(full_src)
                if hasattr(self, '_update_total_link_count'):
                    self._update_total_link_count()
                
                tag = config.get('conflict_tag')
                is_lib = config.get('is_library', 0)
                if tag or is_lib:
                    self._refresh_tag_visuals(target_tag=tag)
                
                if hasattr(self, 'library_panel') and self.library_panel:
                    self.library_panel.refresh()
        
        return success

    def _unlink_single(self, rel_path, update_ui=True, _cascade=True):
        """Remove link for a single item by relative path."""
        app_data = self.app_combo.currentData()
        if not app_data: return False
        
        search_roots = []
        if 'target_root' in app_data: search_roots.append(app_data['target_root'])
        if 'target_root_2' in app_data: search_roots.append(app_data['target_root_2'])
        
        config = self.db.get_folder_config(rel_path) or {}
        if config.get('target_override'):
             search_roots.append(config.get('target_override'))
             
        full_src = os.path.join(self.storage_root, rel_path)
        
        self.logger.debug(f"Exhaustive sweep unlinking for: {rel_path}")
        self.deployer.remove_links_pointing_to(search_roots, full_src)
        
        self.db.update_folder_display_config(rel_path, last_known_status='unlinked')

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
            
            if hasattr(self, 'library_panel') and self.library_panel:
                self.library_panel.refresh()
            
            self._refresh_tag_visuals()
        
        return True

    def _find_packages_depending_on_library(self, lib_name: str) -> list:
        """Find all linked packages that have a dependency on the specified library."""
        import json
        dependent_packages = []
        all_configs = self.db.get_all_folder_configs()
        
        for rel_path, cfg in all_configs.items():
            if cfg.get('is_library', 0):
                continue
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

    def _deploy_items(self, rel_paths, skip_refresh=False):
        """Deploy multiple items. Wrapper around _deploy_single."""
        if hasattr(self.deployer, 'clear_actions'): self.deployer.clear_actions()
        
        for rel in rel_paths:
            if not self._deploy_single(rel, update_ui=False, show_result=False):
                QMessageBox.warning(self, _("Deploy Error"), _("Failed to deploy {rel}").format(rel=rel))
                break
        
        if hasattr(self.deployer, 'last_actions') and self.deployer.last_actions:
            actions = self.deployer.last_actions
            backups = [a for a in actions if a['type'] == 'backup']
            overwrites = [a for a in actions if a['type'] == 'overwrite']
            
            if backups or overwrites:
                summary = _("Batch deployment finished with actions:\n")
                if backups: summary += _("- Backups created: {count} items\n").format(count=len(backups))
                if overwrites: summary += _("- Files overwritten: {count} items\n").format(count=len(overwrites))
                QMessageBox.information(self, _("Batch Deployment Summary"), summary)

        if not skip_refresh:
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
            abs_paths = [os.path.join(self.storage_root, rel) for rel in rel_paths]
            self._update_cards_link_status(set(abs_paths))
            if hasattr(self, '_update_total_link_count'):
                self._update_total_link_count()

    def _refresh_tag_visuals(self, target_tag=None):
        """
        Phase 28 Async: Background visual update for Tag Conflicts.
        Starts a thread to fetch DB and build active tag map.
        Updates UI on signal receipt.
        """
        app_data = self.app_combo.currentData()
        if not app_data: return
        
        if not hasattr(self, '_tag_refresh_pending'):
            self._tag_refresh_pending = False
            
        if hasattr(self, '_tag_sync_thread') and self._tag_sync_thread is not None:
            try:
                if self._tag_sync_thread.isRunning():
                    self._tag_refresh_pending = True
                    return
            except RuntimeError:
                self._tag_sync_thread = None

        self._tag_sync_thread = QThread(self)
        target_root = app_data.get(getattr(self, 'current_target_key', 'target_root'))
        
        self._tag_sync_worker = TagConflictWorker(self.db.db_path, self.storage_root, target_root)
        self._tag_sync_worker.moveToThread(self._tag_sync_thread)
        
        self._tag_sync_thread.started.connect(self._tag_sync_worker.run)
        self._tag_sync_worker.finished.connect(self._on_tag_refresh_finished)
        self._tag_sync_worker.finished.connect(self._tag_sync_thread.quit)
        self._tag_sync_worker.finished.connect(self._tag_sync_worker.deleteLater)
        self._tag_sync_thread.finished.connect(self._tag_sync_thread.deleteLater)
        self._tag_sync_thread.finished.connect(self._cleanup_tag_thread)
        
        self._tag_sync_thread.start()
    
    def _cleanup_tag_thread(self):
        """Clean up the Python reference to the thread."""
        self._tag_sync_thread = None

    def _on_tag_refresh_finished(self, result):
        """Callback from background worker. Updates visible cards on Main Thread."""
        if not result: return
        
        cached_configs = {k.replace('\\', '/'): v for k, v in result['all_configs'].items()} 
        
        change_count = 0
        card_count = 0

        for i in range(self.pkg_layout.count()):
            item = self.pkg_layout.itemAt(i)
            if item and item.widget():
                card = item.widget()
                card_count += 1
                card_changed = False
                
                try:
                    rel = os.path.relpath(card.path, self.storage_root).replace('\\', '/')
                except: rel = ""
                
                cfg = cached_configs.get(rel, {})
                
                is_alt = cfg.get('is_library_alt_version', False)
                if getattr(card, 'is_library_alt_version', False) != is_alt:
                    card.is_library_alt_version = is_alt
                    card_changed = True

                has_logical = cfg.get('has_logical_conflict', False)
                if getattr(card, 'has_logical_conflict', False) != has_logical:
                    card.has_logical_conflict = has_logical
                    card_changed = True

                if card_changed:
                    change_count += 1
                    card._update_style()
        
        bulk_updates = {}
        for rel_p, cfg in cached_configs.items():
            is_alt = cfg.get('is_library_alt_version', False)
            has_logical = cfg.get('has_logical_conflict', False)
            bulk_updates[rel_p] = {
                'has_logical_conflict': 1 if has_logical else 0,
                'is_library_alt_version': 1 if is_alt else 0
            }
        
        self.db.update_visual_flags_bulk(bulk_updates)
        self._refresh_category_cards_cached(cached_configs)
        
        if hasattr(self, 'library_panel') and self.library_panel:
             self.library_panel.refresh()

        if getattr(self, '_tag_refresh_pending', False):
            self._tag_refresh_pending = False
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
                    has_linked, has_conflict = self._scan_children_status(card.path, target_root, cached_configs=cached_configs)
                    card.set_children_status(has_linked=has_linked, has_conflict=has_conflict)

    def _on_card_deployment_requested(self, path):
        """Phase 30: Handle direct deployment toggle from card overlay button."""
        try:
            rel = os.path.relpath(path, self.storage_root).replace('\\', '/')
        except: return
        
        config = self.db.get_folder_config(rel) or {}
        current_status = config.get('last_known_status', 'none')
        
        if current_status == 'linked':
            self.logger.info(f"[DirectAction] Unlinking {rel}")
            self._unlink_single(rel)
        else:
            self.logger.info(f"[DirectAction] Deploying {rel}")
            self._deploy_single(rel)
