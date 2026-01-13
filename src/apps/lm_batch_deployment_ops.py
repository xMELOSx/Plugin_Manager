"""
Link Master: Batch Deployment Operations Mixin
Handles symlinking, dependency resolution, and tag conflict checks.
"""
import os
import logging
import time
from src.ui.common_widgets import FramelessMessageBox
from PyQt6.QtCore import QThread, QTimer
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy

from src.core.lang_manager import _
from src.core.link_master.deployer import DeploymentCollisionError
from src.ui.styles import apply_common_dialog_style
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

    def _batch_category_deploy_selected(self):
        """Deploys all selected categories."""
        if not self.selected_paths: return
        self.logger.info(f"Batch Category Deploy: {len(self.selected_paths)} items")
        
        app_data = self.app_combo.currentData()
        if not app_data: return
        storage_root = app_data.get('storage_root')
        if not storage_root: return
        
        for path in self.selected_paths:
            try:
                rel = os.path.relpath(path, storage_root).replace('\\', '/')
                if rel == ".": continue
                self._handle_deploy_category(rel)
            except Exception as e:
                self.logger.error(f"Failed to category deploy {path}: {e}")
        
        self._update_cards_link_status(self.selected_paths)

    def _batch_category_unlink_selected(self):
        """Unlinks all selected categories."""
        if not self.selected_paths: return
        self.logger.info(f"Batch Category Unlink: {len(self.selected_paths)} items")
        
        app_data = self.app_combo.currentData()
        if not app_data: return
        storage_root = app_data.get('storage_root')
        if not storage_root: return
        
        for path in self.selected_paths:
            try:
                rel = os.path.relpath(path, storage_root).replace('\\', '/')
                if rel == ".": continue
                self._handle_unlink_category(rel)
            except Exception as e:
                self.logger.error(f"Failed to category unlink {path}: {e}")
        
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
        tag_str = config.get('conflict_tag')
        if not tag_str: return None
        
        my_tags = [t.strip().lower() for t in tag_str.split(',') if t.strip()]
        if not my_tags: return None
        
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
            if other_cfg.get('last_known_status') != 'linked': continue
            
            other_tag_str = other_cfg.get('conflict_tag')
            if not other_tag_str: continue
            
            other_tags = [t.strip().lower() for t in other_tag_str.split(',') if t.strip()]
            
            # Check for overlap
            overlap_tag = None
            for t in my_tags:
                if t in other_tags:
                    overlap_tag = t
                    break
            
            if not overlap_tag: continue
            
            if scope == 'category':
                other_cat = os.path.dirname(other_path).replace('\\', '/')
                if other_cat != current_category: continue
            
            other_name = os.path.basename(other_path)
            return {
                'conflict': True,
                'name': other_name,
                'path': other_path,
                'tag': overlap_tag,
                'scope': scope
            }
        
        return None

    def _deploy_single(self, rel_path, update_ui=True, show_result=False, force_sweep=False):
        """Deploy a single item by relative path. Core method for all deploy operations."""
        app_data = self.app_combo.currentData()
        if not app_data: return False
        
        # Reset cancellation flag
        self._last_deploy_cancelled = False
        
        full_src = os.path.join(self.storage_root, rel_path)
        
        # 🚨 Safety Check: Block empty relative paths (prevents accidental root targeting)
        if not rel_path or rel_path == ".":
            self.logger.error(f"Deployment blocked: relative path is empty ({rel_path}).")
            return False
        
        # Phase 5: Reverse Swap Check (Package -> Category)
        # ... [omitting logic for brevity in ReplacementContent but it stays in file] ...
        try:
            parent_rel = os.path.dirname(rel_path).replace('\\', '/')
            if parent_rel and parent_rel != '.':
                parent_config = self.db.get_folder_config(parent_rel) or {}
                if parent_config.get('category_deploy_status') == 'deployed':
                    # Confirm swap
                    msg = QMessageBox(self)
                    msg.setWindowTitle(_("Package Deploy"))
                    msg.setText(_("Parent category '{cat}' is currently deployed.\nDeploying this package requires unlinking the category.\n\nProceed?").format(cat=os.path.basename(parent_rel)))
                    msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
                    msg.setDefaultButton(QMessageBox.StandardButton.Cancel)
                    apply_common_dialog_style(msg)
                    
                    if msg.exec() != QMessageBox.StandardButton.Yes:
                        self._last_deploy_cancelled = True
                        return False
                    
                    # Unlink Category
                    self.logger.info(f"[Swap] Unlinking parent category: {parent_rel}")
                    self._unlink_single(parent_rel, update_ui=False)
                    # Clear DB status
                    self.db.update_folder_display_config(parent_rel, category_deploy_status=None)
                    
                    # Force update UI to remove blue border from category
                    if update_ui:
                        self._force_refresh_visible_cards()
        except Exception as e:
            self.logger.error(f"Reverse swap check failed: {e}")
        
        config = self.db.get_folder_config(rel_path) or {}
        folder_name = os.path.basename(rel_path.rstrip('\\/'))
        
        # 🚨 Safety Check: Prevent deployment if folder_name is empty or whitespace-only
        if not folder_name or not folder_name.strip():
            self.logger.error(f"Safety Block: Deployment blocked due to empty folder name. rel_path={rel_path}")
            msg = QMessageBox(self.window() if hasattr(self, 'window') else self)
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle(_("Safety Block"))
            msg.setText(_("Deployment blocked: Folder name is empty or whitespace-only.\n\n"
                  "rel_path: {rel_path}\n\n"
                  "This can happen if the package is at the root level of storage.").format(rel_path=rel_path))
            apply_common_dialog_style(msg)
            msg.exec()
            return False
        
        # Phase 5 & 40: Resolve Deployment Rule based on current target
        target_key = getattr(self, 'current_target_key', 'target_root')
        item_rule_key = 'deploy_rule'
        app_rule_key = 'deployment_rule'
        
        if target_key == 'target_root_2':
            item_rule_key = 'deploy_rule_b'
            app_rule_key = 'deployment_rule_b'
        elif target_key == 'target_root_3':
            item_rule_key = 'deploy_rule_c'
            app_rule_key = 'deployment_rule_c'
            
        deploy_rule = config.get(item_rule_key)
        app_default_rule = app_data.get(app_rule_key) or app_data.get('deployment_rule', 'folder')
        
        if not deploy_rule or deploy_rule in ("default", "inherit"):
            # Fallback to legacy deploy_type only if it's the primary target and deploy_rule is missing
            if item_rule_key == 'deploy_rule':
                legacy_type = config.get('deploy_type')
                if legacy_type and legacy_type != 'folder':
                    deploy_rule = legacy_type
                else:
                    deploy_rule = app_default_rule
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
        target_root = app_data.get(target_key)
        if not target_link:
            if deploy_rule == 'files':
                target_link = target_root
            elif deploy_rule == 'tree':
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
                target_link = os.path.join(target_root, folder_name)

        # 🚨 Phase 42: Proactive Exhaustive transition sweep BEFORE deployment.
        # This ensures old physical files (e.g. from Flat mode) are cleared before we deploy the new state.
        # We trigger this if force_sweep is requested OR if link-level status is suspect.
        last_status = config.get('last_known_status')
        should_proactive_sweep = force_sweep or last_status in ('linked', 'partial', 'none')
        
        if should_proactive_sweep:
            self.logger.info(f"[Deploy-Sweep] Transitioning {rel_path} (Rule: {deploy_rule}, Force: {force_sweep}). Performing cleanup.")
            try:
                target_roots = [app_data.get(k) for k in ['target_root', 'target_root_2', 'target_root_3'] if app_data.get(k)]
                sweep_occured, failed_paths = self.deployer.remove_links_pointing_to(target_roots, full_src)
                
                if sweep_occured:
                    self.logger.info(f"[Deploy-Sweep] Cleaned up legacy files/links for {rel_path}")
                    from src.ui.toast import Toast
                    active_win = QApplication.activeWindow() or (self.window() if hasattr(self, 'window') else self)
                    Toast.show_toast(active_win, _("Transition sync: Legacy files cleaned up"), preset="info")
                
                if failed_paths:
                    self._show_cleanup_failure_dialog(failed_paths)
            except Exception as e:
                self.logger.warning(f"Transition sweep failed: {e}")
            
            # Phase 42: Allow UI to breather after sweep before potential re-deploy
            from PyQt6.QtWidgets import QApplication
            QApplication.processEvents()

        # --- PROACTIVE LINK CHECK ---
        # Check if already deployed correctly (mode-aware)
        status_info = self.deployer.get_link_status(
            target_link, 
            expected_source=full_src, 
            expected_transfer_mode=transfer_mode,
            deploy_rule=deploy_rule
        )
        current_status = status_info.get('status', 'none')
        self.logger.debug(f"[Deploy-Check] '{folder_name}' target_link={target_link}, current_status={current_status}")
        
        if current_status == 'linked':
            self.logger.info(f"Skipping {rel_path} - Already correctly linked to {target_link}")
            if update_ui:
                # Targeted update instead of full background refresh
                self._update_card_by_path(full_src)
            
            # Update DB status if it was not 'linked' before
            if config.get('last_known_status') != 'linked':
                self.db.update_folder_display_config(rel_path, last_known_status='linked')
            
            # Still process dependencies if any
            if config.get('lib_deps'):
                deps_to_deploy = self._resolve_dependencies([rel_path])
                if deps_to_deploy:
                    for lib_rel in deps_to_deploy:
                        if lib_rel != rel_path:
                            self._deploy_single(lib_rel, update_ui=True, force_sweep=force_sweep)
            return True
        # -------------------------------------------------------------

        rules_str = config.get('deployment_rules')
        rules = {}
        if rules_str:
            try:
                import json
                rules = json.loads(rules_str)
            except:
                self.logger.warning(f"Failed to parse deployment_rules for {rel_path}: {rules_str}")

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
                        
                        msg_box = FramelessMessageBox(self.window() if hasattr(self, 'window') else self)
                        msg_box.setIcon(FramelessMessageBox.Icon.Question)
                        msg_box.setWindowTitle(_("Library Switch"))
                        msg_box.setText(msg)
                        msg_box.setStandardButtons(FramelessMessageBox.StandardButton.Yes | FramelessMessageBox.StandardButton.No)
                        reply = msg_box.exec()
                        if reply == FramelessMessageBox.StandardButton.Yes:
                            self.logger.info(f"[LibSwitch] Unlinking {other_path} to switch to {rel_path}")
                            self._unlink_single(other_path, update_ui=True)
                        else:
                            self._last_deploy_cancelled = True
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
            
            msg_box = FramelessMessageBox(self.window() if hasattr(self, 'window') else self)
            msg_box.setIcon(FramelessMessageBox.Icon.Warning)
            msg_box.setWindowTitle(_("Conflict Swap"))
            msg_box.setText(msg)
            msg_box.setStandardButtons(FramelessMessageBox.StandardButton.Yes | FramelessMessageBox.StandardButton.No)
            reply = msg_box.exec()
            
            if reply == FramelessMessageBox.StandardButton.Yes:
                self.logger.info(f"Swapping: Disabling {conflict_data['name']} for {folder_name}")
                self._unlink_single(conflict_data['path'], update_ui=True)
                self._refresh_tag_visuals(target_tag=conflict_data.get('tag'))
            else:
                self._last_deploy_cancelled = True
                return False


        # Standard Delegation
        try:
            success = self.deployer.deploy_with_rules(
                full_src, target_link, rules, 
                deploy_rule=deploy_rule, transfer_mode=transfer_mode, 
                conflict_policy=c_policy,
                package_rel_path=rel_path # Phase 42 Tracking
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
                
            msg_box = FramelessMessageBox(self.window() if hasattr(self, 'window') else self)
            msg_box.setIcon(FramelessMessageBox.Icon.Critical)
            msg_box.setWindowTitle(_("Deployment Collision"))
            msg_box.setText(detail_txt)
            # apply_common_dialog_style(msg_box)
            msg_box.exec()
            return False
        
        try:
            if success:
                 self.logger.info(f"[DeploySingle] Success. Updating DB for {rel_path}")
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
                    msg_box.setIcon(QMessageBox.Icon.Information)
                    msg_box.setWindowTitle(_("Conflict Handled"))
                    msg_box.setText(msg)
                    apply_common_dialog_style(msg_box)
                    msg_box.exec()

                 self.logger.info(f"[DeployUI] Calling _update_card_by_path for {full_src}")
                 self._update_card_by_path(full_src)
                 
                 if hasattr(self, '_update_total_link_count'):
                     self._update_total_link_count()
                 
                 # Phase 28/Debug: Always refresh tag visuals after any deploy to ensure physical occupancy
                 # or library alt-version highlighting is updated globally.
                 tag = config.get('conflict_tag')
                 self._refresh_tag_visuals(target_tag=tag)
                 
                 if hasattr(self, 'library_panel') and self.library_panel:
                     self.library_panel.refresh()
        except Exception as e:
            self.logger.error(f"[DeploySingle] CRITICAL ERROR during post-deploy update: {e}", exc_info=True)
            import traceback
            self.logger.error(traceback.format_exc())
        
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
        
        # 🚨 DEBUG: Log unlink operation details
        self.logger.info(f"[Unlink] Starting unlink for rel_path={rel_path}")
        self.logger.debug(f"[Unlink] search_roots={search_roots}")
        
        config = self.db.get_folder_config(rel_path) or {}
        
        # 🚨 Safety Check: Block empty relative paths in unlink
        if not rel_path or rel_path == ".":
             self.logger.warning(f"Unlink blocked: relative path is empty ({rel_path}).")
             return False
             
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
                    msg_box.setIcon(QMessageBox.Icon.Question)
                    msg_box.setWindowTitle(_("Cascaded Unlink Confirmation"))
                    msg_box.setText(_("This library is used by {count} linked packages. Do you want to unlink them as well?").format(count=len(dependent_packages)))
                    msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    apply_common_dialog_style(msg_box)
                    reply = msg_box.exec()
                    if reply == QMessageBox.StandardButton.Yes:
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
            rules_json = config.get('deployment_rules')
            target_link = config.get('target_override')
            if not target_link:
                if deploy_rule == 'files':
                    target_link = search_root
                elif deploy_rule == 'tree':
                     # Tree mode logic
                     import json
                     skip_val = 0
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
            # For Files/Custom modes, we need file-by-file deletion to avoid deleting unrelated content
            if deploy_rule in ('files', 'custom'):
                 # Safe Batch Undeploy: delete source-matched files only, then prune empty dirs
                 # We use search_root as base because _safe_batch_undeploy handles mirroring/overrides internally
                 deleted_count = self._safe_batch_undeploy(full_src, search_root, deploy_rule, rules_json=rules_json)
                 if deleted_count > 0:
                      self.logger.info(f"Batch undeploy ({deploy_rule}): removed {deleted_count} items from {search_root}")
            else:
                 # 🚨 Safety Check: Avoid unlinking the search root itself unless it is genuinely a link to us
                 if target_link:
                     t_roots = {os.path.normpath(app_data.get(k)).lower() for k in ['target_root', 'target_root_2', 'target_root_3'] if app_data.get(k)}
                     if os.path.normpath(target_link).lower() in t_roots:
                         # extra safety: only allow if it's a symlink (we don't want to rmtree a root!)
                         if not os.path.islink(target_link):
                             self.logger.warning(f"Unlink Safety: Skipping search root that is not a symlink: {target_link}")
                             continue
                         
                         if not rel_path:
                              self.logger.error(f"Unlink Safety: Blocked attempt to unlink root via empty rel_path.")
                              continue

                 if self.deployer.undeploy(target_link, transfer_mode=transfer_mode, source_path_hint=full_src):
                      self.logger.info(f"Unlinked/Undeployed: {target_link}")

        # Phase: Exhaustive Transition Sweep for Manual Unlink
        # If the user clicks Unlink, we want to make sure it's REALLY unlinked even if rules changed.
        current_status = config.get('last_known_status')
        if current_status == 'linked' or current_status == 'partial':
             self.logger.info(f"[Unlink-Sweep] Performing exhaustive cleanup for: {rel_path}")
             failed_paths_list = [] # Renaming to avoid any scope confusion
             try:
                 target_roots = [app_data.get(k) for k in ['target_root', 'target_root_2', 'target_root_3'] if app_data.get(k)]
                 _, result_failed = self.deployer.remove_links_pointing_to(target_roots, full_src)
                 if result_failed:
                     failed_paths_list = result_failed
                 
                 if failed_paths_list:
                     self._show_cleanup_failure_dialog(failed_paths_list)
             except Exception as e:
                 self.logger.warning(f"Exhaustive cleanup during unlink failed: {e}")
             
             # Phase 42: Allow UI to breathe after sweep
             from PyQt6.QtWidgets import QApplication
             QApplication.processEvents()

        # Phase 28: Optimization - Stop exhaustive sweeping of all targets on every deploy/unlink.
        # This was causing "Target not found" warnings and massive filesystem overhead.
        # self.deployer.remove_links_pointing_to(search_roots, full_src) 
        self.logger.debug(f"Unlink complete for: {rel_path} (targeted roots only)")
        self.db.update_folder_display_config(rel_path, last_known_status='unlinked')

        if update_ui:
            self._update_card_by_path(full_src)
            if hasattr(self, '_update_total_link_count'):
                self._update_total_link_count()
            
            if hasattr(self, 'library_panel') and self.library_panel:
                self.library_panel.refresh()
            
            self._refresh_tag_visuals()
        
        # Phase 7: Pruning - Delegated to Safe Deployer Logic
        if hasattr(self, 'deployer') and self.deployer:
            for search_root in search_roots:
                if not search_root: continue
                try:
                    # Determine the effective pruning start path
                    if deploy_rule == 'tree':
                        # For Tree mode, we must respect skip_levels to find the correct pruning entry point
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
                            prune_entry = os.path.join(search_root, mirrored)
                        else:
                            prune_entry = search_root
                    elif deploy_rule == 'files':
                        prune_entry = search_root # Files are directly in search root
                    else:
                        # Folder mode
                        folder_name = os.path.basename(rel_path)
                        prune_entry = os.path.join(search_root, folder_name)

                    parent_dir = os.path.dirname(prune_entry)
                    # Phase 32: Ensure search roots are protected during pruning
                    self.deployer._cleanup_empty_parents(parent_dir, protected_roots=set(search_roots))
                except Exception as e:
                    self.logger.warning(f"Failed to prune parents for {search_root}: {e}")

        return True

    def _find_packages_depending_on_library(self, lib_name: str) -> list:
        """Find all linked packages that have a dependency on the specified library."""
        import json
        dependent_packages = []
        all_configs = self.db.get_all_folder_configs()
        
        for rel_path, cfg in all_configs.items():
            
            # If flattening is requested (files mode), we MUST iterate, regardless of transfer mode
            if is_flat or (transfer_mode == 'copy' and deploy_rule != 'tree'): # 'tree' handled by shutil.copytree usually? No, copy uses recursion too.
                # Recursive File Deployment Logic
                items_deployed = 0
                
                # Check target root existence
                target_base = target_root
                if target_override:
                    target_base = target_override
                
                if not os.path.exists(target_base):
                    os.makedirs(target_base, exist_ok=True)

                for root, dirs, files in os.walk(full_src):
                    rel_root = os.path.relpath(root, full_src).replace('\\', '/')
                    if rel_root == ".": rel_root = ""
                    
                    # Calculate depth for Skip Levels
                    current_depth = 0
                    if rel_root:
                        current_depth = len(rel_root.split('/'))
                    
                    # Logic for Skip Levels (Standardized)
                    # If this depth is skipped, we don't process files, but we continue walking?
                    # os.walk is recursive.
                    
                    for name in files:
                        file_rel = os.path.join(rel_root, name).replace('\\', '/')
                        # Determine final target name/rel path
                        if deploy_rule == 'files':
                            # Flatten: Target is just the filename in the root
                            status_key = file_rel # We track by source relative path
                            final_target_rel = name
                        else:
                            # Folder mode recursion (shouldn't happen here usually, but for consistency)
                            if transfer_mode == 'symlink' and not is_flat:
                                # If symlink and NOT flat, we shouldn't be here (handled by top-level link)
                                continue
                            final_target_rel = file_rel

                        target_path = os.path.join(target_base, final_target_rel)
                        source_path = os.path.join(root, name)
                        
                        # Actual deployment
                        if transfer_mode == 'symlink':
                            if self.deployer.deploy_link(source_path, target_path, conflict_policy):
                                items_deployed += 1
                        else: # copy
                            if self.deployer.deploy_copy(source_path, target_path, conflict_policy):
                                items_deployed += 1
                                
                if items_deployed > 0:
                    # Update status for the PACKAGE (Parent)
                    # Even if we linked files, the package status is "linked"
                     self.db.update_folder_display_config(rel_path, last_known_status='linked')
                     if show_result:
                        self.logger.info(f"Deployed {items_deployed} files (Flat/Recursive) for {rel_path}")
                     return True
                else:
                     return False

            # Standard Logic (Folder Link or Tree Copy or Single Folder Copy)
            # If we are here, it means [Symlink + Folder] OR [Tree Copy via shutil?]
            
            target_base = target_root
            if target_override:
                target_base = target_override
                
            # If Folder deployment (standard), we link/copy the root folder into target_base
            # BUT wait, target_base is the root (e.g. Mods). We want Mods/PackageName.
            
            final_target_path = os.path.join(target_base, os.path.basename(rel_path))
            
            if transfer_mode == 'symlink':
                # Folder Symlink
                if self.deployer.deploy_link(full_src, final_target_path, conflict_policy):
                     self.db.update_folder_display_config(rel_path, last_known_status='linked')
                     return True
            else:
                 # Folder Copy (Non-recursive single call if supported, otherwise...)
                 # Actually deployer.deploy_copy uses shutil.copytree for directories?
                 if self.deployer.deploy_copy(full_src, final_target_path, conflict_policy):
                     self.db.update_folder_display_config(rel_path, last_known_status='linked')
                     return True

            return False

    def _safe_batch_undeploy(self, source_path: str, target_base: str, deploy_rule: str, rules_json: str = None) -> int:
        """
        Unified safe undeploy for Tree, Files (Flatten), and Custom modes.
        Walks the source and deletes matching files in the target according to rules.
        """
        import json
        if not os.path.isdir(source_path): return 0
        if not os.path.isdir(target_base): return 0
        
        # Parse rules
        rules = {}
        if rules_json:
            try: rules = json.loads(rules_json)
            except: pass
        
        overrides = rules.get('overrides', rules.get('rename', {})) if deploy_rule == 'custom' else {}
        skip_levels = int(rules.get('skip_levels', 0))
        
        deleted_count = 0
        deleted_dirs = set()
        
        self.logger.debug(f"Starting safe batch undeploy: rule={deploy_rule}, target={target_base}")
        
        for root, dirs, files in os.walk(source_path):
            rel_root = os.path.relpath(root, source_path).replace('\\', '/')
            if rel_root == ".": rel_root = ""
            
            # Skip levels check
            start_lvl = 0
            if rel_root:
                start_lvl = len(rel_root.split('/'))
            
            if start_lvl < skip_levels and deploy_rule != 'files':
                continue

            for name in files:
                rel_path = f"{rel_root}/{name}" if rel_root else name
                
                # Determine deploy path (mirrors deployer logic)
                deploy_path = rel_path
                if deploy_rule == 'custom' and rel_path in overrides:
                    deploy_path = overrides[rel_path]
                elif deploy_rule == 'files':
                    deploy_path = name
                
                # Adjust for skip levels
                if skip_levels > 0 and deploy_rule != 'files':
                    parts = deploy_path.split('/')
                    if len(parts) > skip_levels:
                        deploy_path = '/'.join(parts[skip_levels:])
                    else:
                        continue

                target_file = os.path.join(target_base, deploy_path.replace('/', os.sep))
                
                if os.path.lexists(target_file):
                    try:
                        if os.path.islink(target_file):
                            os.unlink(target_file)
                        else:
                            os.remove(target_file)
                        
                        # Phase 42: Clear DB tracking
                        try: self.db.remove_deployed_file_entry(target_file)
                        except: pass

                        deleted_count += 1
                        # Mark parent for pruning
                        deleted_dirs.add(os.path.dirname(target_file))
                    except Exception as e:
                        self.logger.warning(f"Failed to delete {target_file}: {e}")

        # Prune empty directories
        if deleted_dirs:
            sorted_dirs = sorted(list(deleted_dirs), key=len, reverse=True)
            app_data = self.app_combo.currentData() if hasattr(self, 'app_combo') else None
            protected_roots = set()
            if app_data:
                for k in ['target_root', 'target_root_2', 'target_root_3']:
                    if app_data.get(k): protected_roots.add(os.path.normpath(app_data[k]).lower())
            
            for d in sorted_dirs:
                curr = d
                while curr:
                    if not os.path.isdir(curr): break
                    if os.path.normpath(curr).lower() in protected_roots: break
                    try:
                        if not os.listdir(curr):
                            os.rmdir(curr)
                            curr = os.path.dirname(curr)
                        else: break
                    except: break
                    
        return deleted_count

    def _deploy_items(self, rel_paths, skip_refresh=False):
        """Deploy multiple items. Wrapper around _deploy_single."""
        if hasattr(self.deployer, 'clear_actions'): self.deployer.clear_actions()
        
        for rel in rel_paths:
            if not self._deploy_single(rel, update_ui=False, show_result=False):
                # If it was cancelled by user, don't show error dialog
                if getattr(self, '_last_deploy_cancelled', False):
                    break
                    
                msg_box = FramelessMessageBox(self)
                msg_box.setIcon(FramelessMessageBox.Icon.Warning)
                msg_box.setWindowTitle(_("Deploy Error"))
                msg_box.setText(_("Failed to deploy {rel}").format(rel=rel))
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
                
                msg_box = FramelessMessageBox(self)
                msg_box.setIcon(FramelessMessageBox.Icon.Information)
                msg_box.setWindowTitle(_("Batch Deployment Summary"))
                msg_box.setText(summary)
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
                        has_linked, has_conflict, has_partial, has_unlinked, has_int_conf = self._scan_children_status(card.path, target_root, cached_configs=cached_configs)
                        card.set_children_status(
                            has_linked=has_linked, 
                            has_conflict=has_conflict, 
                            has_unlinked_children=has_unlinked, 
                            has_partial=has_partial,
                            has_category_conflict=has_int_conf
                        )

    def _on_card_deployment_requested(self, path, is_package=True):
        """Phase 30: Handle direct deployment toggle from card overlay button.
        Redirects to Category Deploy/Unlink if it's a category.
        """
        self.logger.info(f"[DeployRequest] Entered for: {path}, is_pkg={is_package}")
        try:
            rel = os.path.relpath(path, self.storage_root).replace('\\', '/')
            self.logger.info(f"[DeployRequest] RelPath calculated: {rel}")
        except Exception as e:
            self.logger.error(f"[DeployRequest] RelPath failed for {path} vs {self.storage_root}: {e}")
            return
        
        # 1. Category Logic
        if not is_package:
            config = self.db.get_folder_config(rel) or {}
            cat_status = config.get('category_deploy_status')
            
            if cat_status == 'deployed':
                if hasattr(self, '_handle_unlink_category'):
                    self._handle_unlink_category(rel)
            else:
                if hasattr(self, '_handle_deploy_category'):
                    self._handle_deploy_category(rel)
            return

        # 2. Package Logic
        config = self.db.get_folder_config(rel) or {}
        current_status = config.get('last_known_status', 'none')
        
        if current_status == 'linked':
            self.logger.info(f"[DirectAction] Unlinking {rel}")
            if hasattr(self, '_handle_unlink_single'):
                self._handle_unlink_single(rel)
            else:
                self._unlink_single(rel)
        else:
            self.logger.info(f"[DirectAction] Deploying {rel}")
            if hasattr(self, '_handle_deploy_single'):
                self._handle_deploy_single(rel)
            else:
                self._deploy_single(rel)

    # =========================================================================
    # Category Deploy: Deploy the category itself using its own properties
    # =========================================================================

    def _handle_deploy_category(self, category_rel_path):
        """
        Deploy the CATEGORY ITSELF (not child packages) using category's properties.
        This swaps with any deployed child packages.
        """
        if not self.storage_root: return
        
        category_abs = os.path.join(self.storage_root, category_rel_path)
        if not os.path.isdir(category_abs): return
        
        config = self.db.get_folder_config(category_rel_path) or {}
        app_data = self.app_combo.currentData() or {}
        
        # --- Pre-flight checks ---
        # 1. Check internal conflicts: packages with same conflict_tag or same library
        child_conflict_tags = set()
        child_libraries = set()
        linked_children = []
        
        try:
            for item in os.listdir(category_abs):
                child_path = os.path.join(category_abs, item)
                if os.path.isdir(child_path) and not item.startswith('.') and item not in ('_Trash', 'Trash'):
                    child_rel = os.path.join(category_rel_path, item).replace('\\', '/')
                    child_cfg = self.db.get_folder_config(child_rel) or {}
                    
                    # Collect conflict tags
                    child_tag = child_cfg.get('conflict_tag')
                    if child_tag:
                        if child_tag in child_conflict_tags:
                            msg_box = FramelessMessageBox(self)
                            msg_box.setIcon(FramelessMessageBox.Icon.Warning)
                            msg_box.setWindowTitle(_("Category Deploy"))
                            msg_box.setText(_("Cannot deploy category: Duplicate conflict tag '{tag}' found.").format(tag=child_tag))
                            # apply_common_dialog_style(msg_box) # Removed as FramelessMessageBox is already styled
                            msg_box.exec()
                            return
                        child_conflict_tags.add(child_tag)
                    
                    # Collect library names
                    lib_name = child_cfg.get('library_name')
                    if lib_name:
                        if lib_name in child_libraries:
                            msg_box = FramelessMessageBox(self)
                            msg_box.setIcon(FramelessMessageBox.Icon.Warning)
                            msg_box.setWindowTitle(_("Category Deploy"))
                            msg_box.setText(_("Cannot deploy category: Duplicate library '{lib}' found.").format(lib=lib_name))
                            # apply_common_dialog_style(msg_box) # Removed
                            msg_box.exec()
                            return
                        child_libraries.add(lib_name)
                    
                    # Track linked children for swap
                    if child_cfg.get('last_known_status') == 'linked':
                        linked_children.append(child_rel)
        except Exception as e:
            self.logger.error(f"Failed to scan category for deploy: {e}")
            return
        
        # 2. Check external tag conflicts (inherited from children)
        for tag in child_conflict_tags:
            conflict = self._check_tag_conflict(category_rel_path, {'conflict_tag': tag}, app_data)
            if conflict:
                msg_box = FramelessMessageBox(self)
                msg_box.setIcon(FramelessMessageBox.Icon.Warning)
                msg_box.setWindowTitle(_("Category Deploy"))
                msg_box.setText(_("Cannot deploy category: Tag conflict with '{name}'.").format(name=conflict.get('name', 'unknown')))
                # apply_common_dialog_style(msg_box)
                msg_box.exec()
                return
        
        if linked_children:
            # Phase 5: Swap Confirmation Dialog
            msg = FramelessMessageBox(self)
            msg.setWindowTitle(_("Category Deploy"))
            msg.setText(_("Deploying this category will unlink {count} active packages:\n\n{names}\n\nProceed?").format(
                count=len(linked_children),
                names="\n".join([os.path.basename(p) for p in linked_children[:5]]) + ("\n..." if len(linked_children) > 5 else "")
            ))
            msg.setStandardButtons(FramelessMessageBox.StandardButton.Yes | FramelessMessageBox.StandardButton.Cancel)
            msg.setDefaultButton(FramelessMessageBox.StandardButton.Cancel)
            # apply_common_dialog_style(msg)
            
            if msg.exec() != FramelessMessageBox.StandardButton.Yes:
                self.logger.info("[CategoryDeploy] Cancelled by user.")
                return

            self.logger.info(f"[CategoryDeploy] Swapping {len(linked_children)} child packages")
            for child_rel in linked_children:
                self._unlink_single(child_rel, update_ui=False)
                # Phase 5: Ensure button reset for unlinked packages
                self.db.update_folder_display_config(child_rel, last_known_status='none')
        
        # --- Deploy the category itself ---
        success = self._deploy_single(category_rel_path, update_ui=False, show_result=False)
        
        if success:
            # Update category_deploy_status in DB
            self.db.update_folder_display_config(category_rel_path, category_deploy_status='deployed')
            self.logger.info(f"[CategoryDeploy] SUCCESS: {category_rel_path}")
        else:
            self.logger.error(f"[CategoryDeploy] FAILED: {category_rel_path}")
            # If failed manually (not cancelled), warn user
            if not getattr(self, '_last_deploy_cancelled', False):
                warn = QMessageBox(self)
                warn.setWindowTitle(_("Deployment Failed"))
                warn.setText(_("Failed to deploy category."))
                warn.setIcon(QMessageBox.Icon.Warning)
                apply_common_dialog_style(warn)
                warn.exec()
        
        # --- Immediate UI refresh with Overrides ---
        overrides = {category_rel_path.replace('\\', '/'): {'category_deploy_status': 'deployed'}}
        for child_rel in linked_children:
             child_norm = child_rel.replace('\\', '/')
             overrides[child_norm] = {'last_known_status': 'none'}
             
        self._force_refresh_visible_cards(overrides=overrides)
        if hasattr(self, '_update_total_link_count'):
            self._update_total_link_count()

    def _handle_unlink_category(self, category_rel_path):
        """
        Unlink the CATEGORY ITSELF and clear category_deploy_status.
        """
        if not self.storage_root: return
        
        # Unlink the category
        self._unlink_single(category_rel_path, update_ui=False)
        
        # Clear category_deploy_status in DB
        self.db.update_folder_display_config(category_rel_path, category_deploy_status=None)
        self.logger.info(f"[CategoryUnlink] {category_rel_path}")
        
        # --- Immediate UI refresh with Overrides ---
        overrides = {category_rel_path.replace('\\', '/'): {'category_deploy_status': None}}
        self._force_refresh_visible_cards(overrides=overrides)
        
        # Explicitly refresh the card by path to be absolutely sure overlays items update 
        # (Since _force_refresh_visible_cards might have subtle logic differences)
        category_abs = os.path.join(self.storage_root, category_rel_path)
        if hasattr(self, '_update_card_by_path'):
            self._update_card_by_path(category_abs)
            
        if hasattr(self, '_update_total_link_count'):
            self._update_total_link_count()

    def _force_refresh_visible_cards(self, overrides=None):
        """Force immediate refresh of all visible ItemCards.
        overrides: dict {rel_path: {key: value}} to force memory-based updates.
        """
        overrides = overrides or {}

        # Refresh category area
        if hasattr(self, 'cat_layout'):
            for i in range(self.cat_layout.count()):
                item = self.cat_layout.itemAt(i)
                if item and item.widget():
                    card = item.widget()
                    if hasattr(card, 'path'):
                        rel = os.path.relpath(card.path, self.storage_root).replace('\\', '/')
                        config = self.db.get_folder_config(rel) or {}
                        
                        # Apply Overrides
                        ov = overrides.get(rel, {})

                        if hasattr(card, 'update_data'):
                            card.update_data(
                                link_status=ov.get('last_known_status', config.get('last_known_status', 'none')),
                                is_visible=config.get('is_visible', 1),
                                category_deploy_status=ov.get('category_deploy_status', config.get('category_deploy_status'))
                            )
                        if hasattr(card, '_update_style'):
                            card._update_style()
        
        # Refresh package area
        if hasattr(self, 'pkg_layout'):
            for i in range(self.pkg_layout.count()):
                item = self.pkg_layout.itemAt(i)
                if item and item.widget():
                    card = item.widget()
                    if hasattr(card, 'path'):
                        rel = os.path.relpath(card.path, self.storage_root).replace('\\', '/')
                        config = self.db.get_folder_config(rel) or {}
                        
                        # Apply Overrides
                        ov = overrides.get(rel, {})

                        if hasattr(card, 'update_data'):
                            # Use full update_data to ensure deploy button state (green/Link) is reset
                            # update_link_status is partial and might miss some overlay states
                            card.update_data(
                                link_status=ov.get('last_known_status', config.get('last_known_status', 'none')),
                                is_visible=config.get('is_visible', 1),
                                category_deploy_status=ov.get('category_deploy_status', config.get('category_deploy_status'))
                            )
                        if hasattr(card, '_update_style'):
                            card._update_style()
    def _show_cleanup_failure_dialog(self, failed_paths: list):
        """Show a warning dialog when cleanup fails."""
        if not failed_paths: return
        from src.ui.link_master.dialogs.frameless_dialogs import FramelessMessageBox
        
        msg = _("Some files could not be removed (they may be in use by the game):\n\n")
        limit = 10
        for i, p in enumerate(failed_paths):
            if i >= limit:
                msg += _("...and {n} others.").format(n=len(failed_paths) - limit)
                break
            msg += f"- {os.path.basename(p)}\n"
            
        msg_box = FramelessMessageBox(self.window() if hasattr(self, 'window') else None)
        msg_box.setIcon(FramelessMessageBox.Icon.Warning)
        msg_box.setWindowTitle(_("Cleanup Warning"))
        msg_box.setText(msg)
        msg_box.setStandardButtons(FramelessMessageBox.StandardButton.Ok)
        msg_box.exec()
