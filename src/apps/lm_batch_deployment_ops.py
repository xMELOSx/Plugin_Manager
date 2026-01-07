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
from src.core.link_master.deployer import DeploymentCollisionError
from .lm_batch_ops_worker import TagConflictWorker
from src.core.file_handler import FileHandler

_file_handler = FileHandler()

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

    def _deploy_category(self, category_rel_path: str, update_ui: bool = True) -> dict:
        """Deploy all packages within a category folder.
        
        Features:
        - Validates internal conflicts (same tag, same library) and blocks if found
        - Unlinks existing category items before deploying
        - Tracks category-level deployment status
        - Shows deep blue border for category-deployed state
        
        Returns:
            dict with keys: 'success' (bool), 'deployed_count' (int), 'errors' (list), 'blocked_reason' (str or None)
        """
        result = {'success': False, 'deployed_count': 0, 'errors': [], 'blocked_reason': None}
        
        app_data = self.app_combo.currentData()
        if not app_data:
            result['errors'].append("No app selected")
            return result
        
        category_abs = os.path.join(self.storage_root, category_rel_path)
        if not os.path.isdir(category_abs):
            result['errors'].append(f"Not a directory: {category_rel_path}")
            return result
        
        # Step 1: Collect all child packages (immediate subdirectories)
        child_packages = []
        try:
            for item in os.listdir(category_abs):
                item_path = os.path.join(category_abs, item)
                if os.path.isdir(item_path) and not item.startswith('.') and item != '_Trash' and item != 'Trash':
                    child_rel = os.path.join(category_rel_path, item).replace('\\', '/')
                    child_packages.append(child_rel)
        except Exception as e:
            result['errors'].append(f"Failed to list children: {e}")
            return result
        
        if not child_packages:
            result['errors'].append("No packages found in category")
            return result
        
        # Step 2: Validate internal conflicts (same tag within category)
        tag_map = {}  # tag -> list of rel_paths
        library_map = {}  # lib_name -> list of rel_paths
        
        for child_rel in child_packages:
            config = self.db.get_folder_config(child_rel) or {}
            
            # Check tags
            conflict_scope = config.get('conflict_scope', 'disabled')
            if conflict_scope != 'disabled':
                tags_raw = config.get('conflict_tags', '')
                if tags_raw:
                    for tag in [t.strip().lower() for t in tags_raw.split(',') if t.strip()]:
                        if tag not in tag_map:
                            tag_map[tag] = []
                        tag_map[tag].append(child_rel)
            
            # Check library (same library name within category)
            if config.get('is_library', 0):
                lib_name = (config.get('lib_name') or os.path.basename(child_rel)).strip().lower()
                if lib_name:
                    if lib_name not in library_map:
                        library_map[lib_name] = []
                    library_map[lib_name].append(child_rel)
        
        # Step 3: Block if internal conflicts exist
        conflicts = []
        for tag, paths in tag_map.items():
            if len(paths) > 1:
                conflicts.append(f"Tag '{tag}': {', '.join([os.path.basename(p) for p in paths])}")
        
        for lib, paths in library_map.items():
            if len(paths) > 1:
                conflicts.append(f"Library '{lib}': {', '.join([os.path.basename(p) for p in paths])}")
        
        if conflicts:
            result['blocked_reason'] = "\n".join(conflicts)
            return result
        
        # Step 4: Unlink existing category items (if any are linked)
        for child_rel in child_packages:
            try:
                self._unlink_single(child_rel, update_ui=False, _cascade=False)
            except:
                pass  # Ignore unlink errors
        
        # Step 5: Deploy all packages
        deployed_count = 0
        for child_rel in child_packages:
            try:
                if self._deploy_single(child_rel, update_ui=False, show_result=False):
                    deployed_count += 1
                else:
                    result['errors'].append(f"Failed to deploy: {os.path.basename(child_rel)}")
            except Exception as e:
                result['errors'].append(f"{os.path.basename(child_rel)}: {e}")
        
        # Step 6: Mark category as deployed in DB
        self.db.update_folder_display_config(category_rel_path, category_deploy_status='deployed')
        
        result['success'] = deployed_count > 0
        result['deployed_count'] = deployed_count
        
        # Step 7: Update UI
        if update_ui:
            self._refresh_tag_visuals()
            self._refresh_category_cards()
        
        self.logger.info(f"[CategoryDeploy] {category_rel_path}: {deployed_count}/{len(child_packages)} deployed")
        
        return result

    def _deploy_single(self, rel_path, update_ui=True, show_result=False):
        """Deploy a single item by relative path. Core method for all deploy operations."""
        app_data = self.app_combo.currentData()

        if not app_data: return False
        target_root = app_data.get(self.current_target_key)
        if not target_root: return False
        
        full_src = os.path.join(self.storage_root, rel_path)
        
        # Phase 28: Optimization - DO NOT call _unlink_single (sweepy) before every deploy.
        # The deployer.deploy_with_rules will handle conflict at the SPECIFIC target path.
        # This prevents "Target not found" warnings on un-related targets like GIMI2 when only GIMI is active.
        # self._unlink_single(rel_path, update_ui=False, _cascade=False) 
        
        config = self.db.get_folder_config(rel_path) or {}
        folder_name = os.path.basename(rel_path)
        
        # Phase 5: Resolve Deployment Rule and Transfer Mode
        deploy_rule = config.get('deploy_rule')
        
        # Determine App-Default based on selected target
        app_rule_key = 'deployment_rule'
        target_key = getattr(self, 'current_target_key', 'target_root')
        if target_key == 'target_root_2': app_rule_key = 'deployment_rule_b'
        elif target_key == 'target_root_3': app_rule_key = 'deployment_rule_c'
        
        app_default_rule = app_data.get(app_rule_key) or app_data.get('deployment_rule', 'folder')
        
        if not deploy_rule or deploy_rule in ("default", "inherit"):
            # Fallback to legacy deploy_type if set to something other than 'folder'
            legacy_type = config.get('deploy_type')
            if legacy_type and legacy_type != 'folder':
                deploy_rule = legacy_type
            else:
                deploy_rule = app_default_rule
        
        # Keep internal compatibility: 'flatten' -> 'files'
        if deploy_rule == 'flatten':
            deploy_rule = 'files'
            
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
                # 'files' (formerly flatten): Deploy contents directly into target_root
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
                    target_link = target_root
            else:
                # 'folder': Create a subfolder with the package name
                target_link = os.path.join(target_root, folder_name)

        rules = config.get('deployment_rules')

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
                        msg = _("Different version of '{name}' is already active.\n\n"
                                "Current version: {old_ver}\n"
                                "Switching to: {new_ver}\n\n"
                                "Do you want to switch versions?").format(
                                    name=lib_name, old_ver=old_ver, new_ver=new_ver
                                )
                        
                        msg_box = QMessageBox(self)
                        msg_box.setWindowTitle(_("Library Switch"))
                        msg_box.setText(msg)
                        msg_box.setIcon(QMessageBox.Icon.Question)
                        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                        
                        enhanced_styled_msg_box = """
                            QMessageBox { background-color: #1e1e1e; border: 1px solid #444; color: white; }
                            QLabel { color: white; font-size: 13px; background: transparent; }
                            QPushButton { 
                                background-color: #3b3b3b; color: white; border: 1px solid #555; 
                                padding: 6px 16px; min-width: 80px; border-radius: 4px; font-weight: bold;
                            }
                            QPushButton:hover { background-color: #4a4a4a; border-color: #3498db; }
                            QPushButton:pressed { background-color: #2980b9; }
                        """
                        msg_box.setStyleSheet(enhanced_styled_msg_box)
                        
                        if msg_box.exec() == QMessageBox.StandardButton.Yes:
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
            msg = _("Conflict Detected!\n\n"
                   "Package '{old_name}' is already active with tag '{tag}'.\n"
                   "Scope: {scope}\n\n"
                   "Overwrite target with link?\n"
                   "This will DISABLE '{old_name}' and enable '{new_name}'.").format(
                       old_name=conflict_data['name'], tag=conflict_data['tag'], 
                       scope=conflict_data['scope'], new_name=folder_name
                   )
            
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle(_("Conflict Swap"))
            msg_box.setText(msg)
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
            enhanced_styled_msg_box = """
                QMessageBox { background-color: #1e1e1e; border: 1px solid #444; color: white; }
                QLabel { color: white; font-size: 13px; background: transparent; }
                QPushButton { 
                    background-color: #3b3b3b; color: white; border: 1px solid #555; 
                    padding: 6px 16px; min-width: 80px; border-radius: 4px; font-weight: bold;
                }
                QPushButton:hover { background-color: #4a4a4a; border-color: #3498db; }
                QPushButton:pressed { background-color: #2980b9; }
            """
            msg_box.setStyleSheet(enhanced_styled_msg_box)
            
            if msg_box.exec() == QMessageBox.StandardButton.Yes:
                self.logger.info(f"Swapping: Disabling {conflict_data['name']} for {folder_name}")
                self._unlink_single(conflict_data['path'], update_ui=True)
                self._refresh_tag_visuals(target_tag=conflict_data.get('tag'))
            else:
                return False

        try:
            success = self.deployer.deploy_with_rules(
                full_src, target_link, rules, 
                deploy_rule=deploy_rule, transfer_mode=transfer_mode, 
                conflict_policy=c_policy
            )
        except DeploymentCollisionError as e:
            self.logger.warning(f"Deployment aborted due to collisions: {full_src}")
            
            # Show Dialog
            detail_txt = _("The following file collisions were detected. Deployment aborted.\n\n")
            
            # Limit display to first 10
            display_limit = 10
            count = 0
            for item in e.collisions:
                if count >= display_limit:
                    detail_txt += _("...and {n} others.").format(n=len(e.collisions) - count)
                    break
                
                # item is dict: target, source_existing, source_conflicting
                tgt = item['target']
                src_exist = os.path.basename(item['source_existing'])
                src_new = os.path.basename(item['source_conflicting'])
                detail_txt += f"Target: {tgt}\n  - Existing: {src_exist}\n  - Conflict: {src_new}\n\n"
                count += 1
                
            msg_box = QMessageBox(self.window())
            msg_box.setWindowTitle(_("Deployment Collision"))
            msg_box.setText(detail_txt)
            msg_box.setIcon(QMessageBox.Icon.Critical)
            
            enhanced_styled_msg_box = """
                QMessageBox { background-color: #1e1e1e; border: 1px solid #444; color: white; }
                QLabel { color: white; font-size: 13px; background: transparent; }
                QPushButton { 
                    background-color: #3b3b3b; color: white; border: 1px solid #555; 
                    padding: 6px 16px; min-width: 80px; border-radius: 4px; font-weight: bold;
                }
                QPushButton:hover { background-color: #4a4a4a; border-color: #3498db; }
                QPushButton:pressed { background-color: #2980b9; }
            """
            msg_box.setStyleSheet(enhanced_styled_msg_box)
            msg_box.exec()
            return False
        
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
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle(_("Conflict Handled"))
                msg_box.setText(msg)
                msg_box.setIcon(QMessageBox.Icon.Information)
                
                enhanced_styled_msg_box = """
                    QMessageBox { background-color: #1e1e1e; border: 1px solid #444; color: white; }
                    QLabel { color: white; font-size: 13px; background: transparent; }
                    QPushButton { 
                        background-color: #3b3b3b; color: white; border: 1px solid #555; 
                        padding: 6px 16px; min-width: 80px; border-radius: 4px; font-weight: bold;
                    }
                    QPushButton:hover { background-color: #4a4a4a; border-color: #3498db; }
                    QPushButton:pressed { background-color: #2980b9; }
                """
                msg_box.setStyleSheet(enhanced_styled_msg_box)
                msg_box.exec()

             # self.logger.debug(f"[DeployUI] Calling _update_card_by_path for {full_src}")
             self._update_card_by_path(full_src)
             if hasattr(self, '_update_total_link_count'):
                 self._update_total_link_count()
             
             # Phase 28/Debug: Always refresh tag visuals after any deploy to ensure physical occupancy
             # or library alt-version highlighting is updated globally.
             tag = config.get('conflict_tag')
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
        if 'target_root_3' in app_data: search_roots.append(app_data['target_root_3'])
        
        # Phase 7: Filter out None values to prevent TypeError in os.path.isdir
        search_roots = [r for r in search_roots if r is not None]
        
        config = self.db.get_folder_config(rel_path) or {}
        if config.get('target_override'):
             search_roots.append(config.get('target_override'))
             
        full_src = os.path.join(self.storage_root, rel_path)
        
        if _cascade and config.get('is_library', 0):
            lib_name = config.get('lib_name')
            if lib_name:
                dependent_packages = self._find_packages_depending_on_library(lib_name)
                if dependent_packages:
                    # Phase 1.1.25: Preventative confirmation (centralized)
                    msg_box = QMessageBox(self)
                    msg_box.setWindowTitle(_("Cascaded Unlink Confirmation"))
                    msg_box.setText(_("This library is used by {count} linked packages. Do you want to unlink them as well?").format(count=len(dependent_packages)))
                    msg_box.setIcon(QMessageBox.Icon.Question)
                    msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    
                    enhanced_styled_msg_box = """
                        QMessageBox { background-color: #1e1e1e; border: 1px solid #444; color: white; }
                        QLabel { color: white; font-size: 13px; background: transparent; }
                        QPushButton { 
                            background-color: #3b3b3b; color: white; border: 1px solid #555; 
                            padding: 6px 16px; min-width: 80px; border-radius: 4px; font-weight: bold;
                        }
                        QPushButton:hover { background-color: #4a4a4a; border-color: #3498db; }
                        QPushButton:pressed { background-color: #2980b9; }
                    """
                    msg_box.setStyleSheet(enhanced_styled_msg_box)
                    
                    if msg_box.exec() == QMessageBox.StandardButton.Yes:
                        for dep_rel in dependent_packages:
                            self._unlink_single(dep_rel, update_ui=True, _cascade=False)

        # Phase 5: Resolve Deployment Rule and Transfer Mode (Identical logic to _deploy_single)
        deploy_rule = config.get('deploy_rule')
        
        # Determine App-Default based on selected target
        app_rule_key = 'deployment_rule'
        target_key = getattr(self, 'current_target_key', 'target_root')
        if target_key == 'target_root_2': app_rule_key = 'deployment_rule_b'
        elif target_key == 'target_root_3': app_rule_key = 'deployment_rule_c'
        
        app_default_rule = app_data.get(app_rule_key) or app_data.get('deployment_rule', 'folder')
        
        if not deploy_rule or deploy_rule in ("default", "inherit"):
            legacy_type = config.get('deploy_type')
            if legacy_type and legacy_type != 'folder':
                deploy_rule = legacy_type
            else:
                deploy_rule = app_default_rule
        
        # Keep internal compatibility: 'flatten' -> 'files'
        if deploy_rule == 'flatten':
            deploy_rule = 'files'
            
        transfer_mode = config.get('transfer_mode')
        if not transfer_mode or transfer_mode == "default":
            transfer_mode = app_data.get('transfer_mode', 'symlink')

        # Proceed with unlinking
        self.logger.debug(f"Exhaustive sweep unlinking for: {rel_path} (Rule: {deploy_rule}, Mode: {transfer_mode})")
        
        for search_root in search_roots:
            if not search_root or not os.path.exists(search_root):
                continue

            # Determine Target Link Path (Replicated from deployer logic)
            target_link = config.get('target_override')
            if not target_link:
                if deploy_rule == 'files':
                    target_link = search_root
                elif deploy_rule == 'tree':
                     # Tree mode logic
                     import json
                     skip_val = 0
                     rules_json = config.get('deployment_rules')
                     if rules_json:
                         try:
                             rules_obj = json.loads(rules_json)
                             skip_val = int(rules_obj.get('skip_levels', 0))
                         except: pass
                     
                     parts = rel_path.replace('\\', '/').split('/')
                     if len(parts) > skip_val:
                         mirrored = "/".join(parts[skip_val:])
                         target_link = os.path.join(search_root, mirrored)
                     else:
                         target_link = search_root
                else:
                    folder_name = os.path.basename(rel_path)
                    target_link = os.path.join(search_root, folder_name)
            
            # Use unified undeploy with transfer_mode
            # For Tree+Copy mode, we need file-by-file deletion to avoid deleting unrelated content
            if deploy_rule == 'tree' and transfer_mode == 'copy':
                 # Safe Tree Undeploy: delete source-matched files only, then prune empty dirs
                 deleted_count = self._safe_tree_undeploy(full_src, target_link)
                 if deleted_count > 0:
                      self.logger.info(f"Tree undeploy: removed {deleted_count} items from {target_link}")
            else:
                 if self.deployer.undeploy(target_link, transfer_mode=transfer_mode, source_path_hint=full_src):
                      self.logger.info(f"Unlinked/Undeployed: {target_link}")

        # Phase 28: Optimization - Stop exhaustive sweeping of all targets on every deploy/unlink.
        # This was causing "Target not found" warnings and massive filesystem overhead.
        # self.deployer.remove_links_pointing_to(search_roots, full_src) 
        self.logger.debug(f"Unlink complete for: {rel_path} (targeted roots only)")
        self.db.update_folder_display_config(rel_path, last_known_status='unlinked')

        if update_ui:
            self._update_card_by_path(full_src)
            if hasattr(self, '_update_total_link_count'):
                self._update_total_link_count()
            
            # Phase 33 BugFix: Ensure parent category borders (orange/partial) are refreshed
            # when a single item is unlinked.
            if hasattr(self, '_refresh_category_cards'):
                self._refresh_category_cards()

            if hasattr(self, 'library_panel') and self.library_panel:
                self.library_panel.refresh()
            
            self._refresh_tag_visuals()
        
        # Phase 7: Pruning - Remove newly empty parent directories up to target roots
        for search_root in search_roots:
            if not search_root or not os.path.exists(search_root): continue
            
            # Determine the path that was targeted for this mod in this root
            # We don't know the EXACT rule used during deploy, so we try parent of the likely targets
            likely_targets = [
                os.path.join(search_root, os.path.basename(rel_path)), # folder mode
                # For tree/custom, it depends on rel_path. We can try to reconstruct it or just use the exhaustive list.
                # Actually, the deployer.remove_links_pointing_to already cleans up empty dirs it finds.
                # But we want to be more proactive for "tree" modes where intermediate folders were created.
            ]
            
            # If we know it's tree/custom, we can be more specific. 
            # For now, let's just use the rel_path mapped to search_root as a candidate for clearing.
            candidate = os.path.join(search_root, rel_path.replace('\\', '/'))
            curr = os.path.dirname(candidate)
            
            while curr and len(curr) > len(search_root):
                if os.path.exists(curr) and os.path.isdir(curr):
                    try:
                        if not os.listdir(curr):
                            self.logger.info(f"[Pruning] Removing empty directory: {curr}")
                            _file_handler.remove_empty_dir(curr)
                            curr = os.path.dirname(curr)
                        else:
                            break
                    except: break
                else: break

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
            
            # Handle both string and dict formats
            for dep in lib_deps:
                dep_name = dep.get('name', '') if isinstance(dep, dict) else dep
                if dep_name == lib_name:
                    dependent_packages.append(rel_path)
                    break 
        
        return dependent_packages

    def _safe_tree_undeploy(self, source_path: str, target_root: str) -> int:
        """
        Safely undeploy Tree mode copies by deleting only source-matched files,
        then pruning only empty directories.
        
        Args:
            source_path: The source folder that was deployed.
            target_root: The target folder where files were copied to.
        
        Returns:
            Number of items deleted.
        """
        import shutil
        
        if not os.path.isdir(source_path):
             self.logger.warning(f"Source path is not a directory: {source_path}")
             return 0
        
        deleted_count = 0
        deleted_dirs = []  # Track directories to prune later
        
        # Phase 1: Delete files that match source structure
        for root, dirs, files in os.walk(source_path, topdown=False):
            # Calculate relative path from source_path
            rel_root = os.path.relpath(root, source_path)
            if rel_root == '.':
                 target_dir = target_root
            else:
                 target_dir = os.path.join(target_root, rel_root)
            
            # Delete files
            for f in files:
                target_file = os.path.join(target_dir, f)
                if os.path.exists(target_file) and not os.path.islink(target_file):
                    try:
                        _file_handler.remove_path(target_file)
                        deleted_count += 1
                        self.logger.debug(f"Deleted file: {target_file}")
                    except Exception as e:
                        self.logger.warning(f"Failed to delete file {target_file}: {e}")
            
            # Mark directories for potential pruning (handle later)
            for d in dirs:
                target_subdir = os.path.join(target_dir, d)
                if os.path.isdir(target_subdir) and not os.path.islink(target_subdir):
                    deleted_dirs.append(target_subdir)
        
        # Add the root target itself for pruning check
        deleted_dirs.append(target_root)
        
        # Phase 2: Prune ONLY empty directories (deepest first via sorting by length)
        # Sort by path length descending to process deepest dirs first
        deleted_dirs.sort(key=lambda x: len(x), reverse=True)
        
        for d in deleted_dirs:
            if os.path.isdir(d):
                try:
                    # Only remove if EMPTY
                    if not os.listdir(d):
                        _file_handler.remove_empty_dir(d)
                        deleted_count += 1
                        self.logger.debug(f"Pruned empty dir: {d}")
                except Exception as e:
                    self.logger.debug(f"Could not prune dir {d}: {e}")
        
        return deleted_count

    def _deploy_items(self, rel_paths, skip_refresh=False):
        """Deploy multiple items. Wrapper around _deploy_single."""
        if hasattr(self.deployer, 'clear_actions'): self.deployer.clear_actions()
        
        for rel in rel_paths:
            if not self._deploy_single(rel, update_ui=False, show_result=False):
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle(_("Deploy Error"))
                msg_box.setText(_("Failed to deploy {rel}").format(rel=rel))
                msg_box.setIcon(QMessageBox.Icon.Warning)
                
                enhanced_styled_msg_box = """
                    QMessageBox { background-color: #1e1e1e; border: 1px solid #444; color: white; }
                    QLabel { color: white; font-size: 13px; background: transparent; }
                    QPushButton { 
                        background-color: #3b3b3b; color: white; border: 1px solid #555; 
                        padding: 6px 16px; min-width: 80px; border-radius: 4px; font-weight: bold;
                    }
                    QPushButton:hover { background-color: #4a4a4a; border-color: #3498db; }
                    QPushButton:pressed { background-color: #2980b9; }
                """
                msg_box.setStyleSheet(enhanced_styled_msg_box)
                msg_box.exec()
                break
        
        if hasattr(self.deployer, 'last_actions') and self.deployer.last_actions:
            actions = self.deployer.last_actions
            backups = [a for a in actions if a['type'] == 'backup']
            overwrites = [a for a in actions if a['type'] == 'overwrite']
            
            if backups or overwrites:
                summary = _("Batch deployment finished with actions:\n")
                if backups: summary += _("- Backups created: {count} items\n").format(count=len(backups))
                if overwrites: summary += _("- Files overwritten: {count} items\n").format(count=len(overwrites))
                
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle(_("Batch Deployment Summary"))
                msg_box.setText(summary)
                msg_box.setIcon(QMessageBox.Icon.Information)
                
                enhanced_styled_msg_box = """
                    QMessageBox { background-color: #1e1e1e; border: 1px solid #444; color: white; }
                    QLabel { color: white; font-size: 13px; background: transparent; }
                    QPushButton { 
                        background-color: #3b3b3b; color: white; border: 1px solid #555; 
                        padding: 6px 16px; min-width: 80px; border-radius: 4px; font-weight: bold;
                    }
                    QPushButton:hover { background-color: #4a4a4a; border-color: #3498db; }
                    QPushButton:pressed { background-color: #2980b9; }
                """
                msg_box.setStyleSheet(enhanced_styled_msg_box)
                msg_box.exec()

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
        if not result:
             return
        
        # Phase 28/31 Optim: Use pre-calculated maps for matching
        # 1. Package loop uses absolute paths (for individual card pinpoint updates)
        # 2. Category refresh uses relative paths (for hierarchical status calculation)
        abs_config_map = result.get('abs_config_map', {})
        all_configs = result.get('all_configs', {}) # Relative path map (from DB)
        
        change_count = 0
        card_count = 0
        
        # Helper to normalize path for matching (same logic as Worker)
        def norm_match(p):
            if not p: return ""
            p = p.replace('\\', '/')
            return p.lower() if os.name == 'nt' else p

        # Pre-process abs_config_map keys for speed
        norm_abs_map = {norm_match(k): v for k, v in abs_config_map.items()}

        pkg_lay = getattr(self, 'pkg_layout', None)
        if pkg_lay:
            for i in range(pkg_lay.count()):
                item = pkg_lay.itemAt(i)
                if item and item.widget():
                    card = item.widget()
                    card_count += 1
                    card_changed = False
                    
                    # Match by normalized absolute path
                    path_key = norm_match(getattr(card, 'path', ''))
                    cfg = norm_abs_map.get(path_key, {})
                    
                    if cfg:
                        is_alt = bool(cfg.get('is_library_alt_version', False))
                        if getattr(card, 'is_library_alt_version', False) != is_alt:
                            card.is_library_alt_version = is_alt
                            card_changed = True
    
                        has_logical = bool(cfg.get('has_logical_conflict', False))
                        if getattr(card, 'has_logical_conflict', False) != has_logical:
                            card.has_logical_conflict = has_logical
                            card_changed = True
    
                        if card_changed:
                            change_count += 1
                            card._update_style()
        
        # Phase 28: Refresh category borders (Hierarchical status)
        # CRITICAL FIX: Must pass Relative Path map (all_configs) to _refresh_category_cards_cached
        # passing abs_config_map was causing every folder to show ZERO status.
        self._refresh_category_cards_cached(all_configs)
        
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
        
        cat_lay = getattr(self, 'cat_layout', None)
        if cat_lay:
            for i in range(cat_lay.count()):
                item = cat_lay.itemAt(i)
                if item and item.widget():
                    card = item.widget()
                    if hasattr(card, 'path') and hasattr(card, 'set_children_status'):
                        has_linked, has_conflict, has_partial, has_unlinked = self._scan_children_status(card.path, target_root, cached_configs=cached_configs)
                        card.set_children_status(has_linked=has_linked, has_conflict=has_conflict, has_unlinked_children=has_unlinked, has_partial=has_partial)

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
