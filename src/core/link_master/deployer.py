import os
import logging
import ctypes
import copy
import time
import shutil
from src.core import core_handler
from concurrent.futures import ThreadPoolExecutor, as_completed
# FIX: Import safety_block directly as module
import src.core.link_master.safety_block as safety_verifier


class DeploymentCollisionError(Exception):
    """Raised when multiple source files map to the same target path during deployment."""
    def __init__(self, collisions, message="Deployment cancelled due to target collisions"):
        self.collisions = collisions # List of (source, target) tuples
        self.message = message
        super().__init__(self.message)

def _parallel_link_worker(source_path: str, target_link_path: str, conflict_policy: str):
    """
    Top-level worker for parallel execution. Handles a single link creation.
    Returns a result dict for the main process to aggregate.
    """
    import ctypes
    from src.core import core_handler
    
    # Simple check for admin/dev mode (informative for errors)
    def is_admin():
        try: return ctypes.windll.shell32.IsUserAnAdmin()
        except: return False

    if not core_handler.path_exists(source_path):
        return {"status": "error", "path": target_link_path, "msg": f"Source missing: {source_path}"}
    
    # Ensure target directory
    try:
        core_handler.ensure_directory(core_handler.get_parent(target_link_path))
    except Exception as e:
        return {"status": "error", "path": target_link_path, "msg": f"Failed to create directory: {e}"}
    
    # Conflict handling (Simplified for parallel worker: backup or overwrite)
    action_taken = "none"
    if core_handler.path_exists(target_link_path) or core_handler.is_link(target_link_path):
        if conflict_policy == 'skip':
            return {"status": "skip", "path": target_link_path}
        
        try:
            if conflict_policy == 'overwrite':
                core_handler.remove_path(target_link_path)
                action_taken = "overwrite"
            elif conflict_policy == 'backup':
                import time
                import random
                import string
                suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
                backup_path = f"{target_link_path}.bak_{int(time.time())}_{suffix}"
                core_handler.move_path(target_link_path, backup_path)
                action_taken = "backup"
        except Exception as e:
            return {"status": "error", "path": target_link_path, "msg": f"Conflict handle failed: {e}"}

    try:
        is_dir = core_handler.is_dir(source_path)
        core_handler.create_symlink(source_path, target_link_path, target_is_directory=is_dir)
        return {"status": "success", "path": target_link_path, "action": action_taken}
    except OSError as e:
        msg = str(e)
        if not is_admin():
            msg += " (Admin/DevMode may be required)"
        return {"status": "error", "path": target_link_path, "msg": msg}
    except Exception as e:
        return {"status": "error", "path": target_link_path, "msg": str(e)}

def _parallel_copy_worker(source_path: str, target_path: str, conflict_policy: str):
    """
    Top-level worker for parallel file copy execution.
    Returns a result dict for the main process to aggregate.
    """
    from src.core import core_handler
    
    if not core_handler.path_exists(source_path):
        return {"status": "error", "path": target_path, "msg": f"Source missing: {source_path}"}
    
    # Ensure target directory
    target_dir = core_handler.get_parent(target_path)
    if target_dir:
        try:
            core_handler.ensure_directory(target_dir)
        except: pass
    
    # Conflict handling
    action_taken = "none"
    if core_handler.path_exists(target_path) or core_handler.is_link(target_path):
        if conflict_policy == 'skip':
            return {"status": "skip", "path": target_path}
        
        try:
            if conflict_policy == 'overwrite':
                core_handler.remove_path(target_path)
                action_taken = "overwrite"
            elif conflict_policy == 'backup':
                # Phase 42: Simplified Managed Backup for Parallel Worker
                base_backup = f"{target_path}.bak"
                backup_path = base_backup
                counter = 1
                while os.path.exists(backup_path):
                    backup_path = f"{base_backup}_{counter}"
                    counter += 1
                
                core_handler.move_path(target_path, backup_path)
                final_backup_path = backup_path
                action_taken = "backup"
        except Exception as e:
            return {"status": "error", "path": target_path, "msg": f"Conflict handle failed: {e}"}

    final_backup_path = None

    try:
        core_handler.copy_path(source_path, target_path)
        return {
            "status": "success", 
            "path": target_path, 
            "action": action_taken, 
            "mode": "copy", 
            "source": source_path,
            "backup_path": final_backup_path if action_taken == "backup" else None
        }
    except Exception as e:
        return {"status": "error", "path": target_path, "msg": str(e)}

class Deployer:
    def __init__(self, app_name: str = None):
        self.logger = logging.getLogger("LinkMasterDeployer")
        self.last_actions = [] # Phase 1.1.6: Track actions for UI reporting
        self._app_name = app_name  # Phase 30: For database access
        # Cap max_workers to 60 to avoid Windows ProcessPoolExecutor limit (61)
        count = os.cpu_count() or 4
        self.max_workers = min(count, 60)
        self.allow_symlinks = True  # Phase 1: Set by LinkMasterWindow based on capability test
    
    @property
    def _db(self):
        """Get database instance for backup registry persistence."""
        from src.core.link_master.database import get_lm_db
        return get_lm_db(self._app_name)
    
    def clear_actions(self):
        self.last_actions = []

    def _is_admin(self):
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    def deploy_link(self, source_path: str, target_link_path: str, conflict_policy: str = 'backup') -> bool:
        """
        Creates a symbolic link at target_link_path pointing to source_path.
        Returns Top-level success status.
        """
        if not os.path.exists(source_path):
            self.logger.error(f"Source not found: {source_path}")
            return False

        if os.path.lexists(target_link_path):
            action = self._handle_conflict(target_link_path, conflict_policy)
            if action == 'skip':
                return False
            if action == 'error':
                return False

        # Ensure target directory exists
        target_dir = os.path.dirname(target_link_path)
        if not os.path.exists(target_dir):
            try:
                os.makedirs(target_dir)
            except OSError as e:
                self.logger.error(f"Failed to create target dir: {e}")
                return False

        try:
            # On Windows, symlinks require Admin OR Developer Mode
            # target_is_directory is required for folder symlinks on Windows
            is_dir = os.path.isdir(source_path)
            os.symlink(source_path, target_link_path, target_is_directory=is_dir)
            self.logger.info(f"Symlink created ({'Dir' if is_dir else 'File'}): {target_link_path} -> {source_path}")
            
            # Phase 42: Register deployment
            if hasattr(self, '_pkg_rel'):
                self._db.register_deployed_file(target_link_path, source_path, self._pkg_rel, deploy_type='symlink')
                
            return True
        except OSError as e:
            self.logger.error(f"Symlink creation failed: {e}")
            if not self._is_admin():
                self.logger.warning("Symlink creation often requires Administrator privileges or Developer Mode on Windows.")
            return False

    def deploy_copy(self, source_path: str, target_path: str, conflict_policy: str = 'overwrite') -> bool:
        """
        Copies file/folder from source_path to target_path (actual copy, not symlink).
        Default policy is 'overwrite' since this mode is for config files that need updating.
        """
        import shutil
        
        if not os.path.exists(source_path):
            self.logger.error(f"Source not found for copy: {source_path}")
            return False

        if os.path.lexists(target_path):
            action = self._handle_conflict(target_path, conflict_policy)
            if action == 'skip':
                return False
            if action == 'error':
                return False

        # Ensure target directory exists
        target_dir = os.path.dirname(target_path)
        if target_dir and not os.path.exists(target_dir):
            try:
                os.makedirs(target_dir)
            except OSError as e:
                self.logger.error(f"Failed to create target dir: {e}")
                return False

        try:
            if os.path.isdir(source_path):
                shutil.copytree(source_path, target_path)
                self.logger.info(f"Folder copied: {source_path} -> {target_path}")
            else:
                shutil.copy2(source_path, target_path)
                self.logger.info(f"File copied: {source_path} -> {target_path}")
            
            # Phase 42: Register in DB (New standard)
            if hasattr(self, '_pkg_rel'):
                self._db.register_deployed_file(target_path, source_path, self._pkg_rel, deploy_type='copy')
            
            return True
        except Exception as e:
            self.logger.error(f"Copy failed: {e}")
            return False
    

    def _handle_conflict(self, path: str, policy: str) -> str:
        """Handles existing path according to policy. Returns action taken: 'backup', 'overwrite', 'skip', 'error', 'none'."""
        if policy == 'skip':
            self.logger.info(f"Policy: SKIP - preserving {path}")
            self.last_actions.append({'type': 'skip', 'path': path})
            return 'skip'
        
        if policy == 'overwrite':
            try:
                core_handler.remove_path(path)
                self.logger.info(f"Policy: OVERWRITE - removed {path}")
                self.last_actions.append({'type': 'overwrite', 'path': path})
                return 'overwrite'
            except Exception as e:
                self.logger.error(f"Failed to overwrite {path}: {e}")
                return 'error'
                
        if policy == 'backup':
            # Phase 42: Prevent infinite backups
            # If the file is already registered as 'ours', overwrite it instead of backing up.
            try:
                if self._db.is_file_ours(path):
                    self.logger.info(f"Policy: BACKUP - Path '{path}' is already registered as our deployment. Overwriting instead of creating redundant backup.")
                    core_handler.remove_path(path)
                    return 'overwrite'
            except: pass

            try:
                # Managed Backup Naming (User Request)
                # Instead of bak_TIMESTAMP, use .bak, .bak_1, .bak_2 etc.
                base_backup = f"{path}.bak"
                backup_path = base_backup
                counter = 1
                while os.path.exists(backup_path):
                    backup_path = f"{base_backup}_{counter}"
                    counter += 1
                
                core_handler.move_path(path, backup_path)
                self.logger.info(f"Policy: BACKUP - moved {path} to {backup_path}")
                self.last_actions.append({'type': 'backup', 'path': path, 'backup_path': backup_path})
                
                # Registering backup path logic 
                try:
                    self._db.register_backup(path, backup_path)
                except Exception as e:
                    self.logger.warning(f"Failed to register backup in DB (ignoring): {e}")
                
                return 'backup'
            except Exception as e:
                self.logger.error(f"Failed to backup {path}: {e}")
                return 'error'
        
        return 'error'

    def remove_link(self, target_link_path: str, source_path_hint: str = None, restore_backups: bool = True) -> bool:
        """
        Removes the symbolic link at target_link_path.
        If it's a directory (Partial Deployment), performs recursive cleanup.
        If restore_backups=True, restores any .bak files that were created during deploy.
        """
        if not os.path.lexists(target_link_path):
             self.logger.debug(f"Link/Target not found to remove: {target_link_path}")
             return True
        
        if os.path.islink(target_link_path):
            try:
                os.unlink(target_link_path)
                self.logger.info(f"Symlink removed: {target_link_path}")
                
                # Phase 42: Clear DB tracking
                try: self._db.remove_deployed_file_entry(target_link_path)
                except: pass

                # Check for backup to restore
                if restore_backups:
                    self._restore_backup_if_exists(target_link_path)
                
                # Try cleaning parent if empty
                self._cleanup_empty_parents(os.path.dirname(target_link_path))
                return True
            except OSError as e:
                self.logger.error(f"Failed to remove symlink: {e}")
                return False

        # Handle copied files (not symlinks)
        if os.path.isfile(target_link_path):
            try:
                
                os.unlink(target_link_path)
                self.logger.info(f"Copied file removed: {target_link_path}")
                
                # Phase 42: Clear DB tracking
                try: self._db.remove_deployed_file_entry(target_link_path)
                except: pass

                # Check for backup to restore
                if restore_backups:
                    self._restore_backup_if_exists(target_link_path)
                
                self._cleanup_empty_parents(os.path.dirname(target_link_path))
                return True
            except OSError as e:
                self.logger.error(f"Failed to remove file: {e}")
                return False

        if os.path.isdir(target_link_path):
            
            if source_path_hint:
                self.logger.info(f"Cleaning up directory-based (Partial) deployment: {target_link_path}")
                self.cleanup_links_in_target(target_link_path, source_path_hint, recursive=True, restore_backups=restore_backups)
                # If empty after cleanup, remove it
                # 🚨 Safety: NEVER remove target_link_path if it looks like a search root (< 5 path parts)
                parts = target_link_path.replace('\\', '/').split('/')
                if len(parts) >= 5 and not os.listdir(target_link_path):
                    try:
                        os.rmdir(target_link_path)
                        self._cleanup_empty_parents(os.path.dirname(target_link_path))
                        return True
                    except: pass
                # Even if not fully empty (manual files), we consider success for the Mod's part
                return True
            else:
                self.logger.error("Cannot remove directory-based link without source_path_hint.")
                return False

        return False

    def _restore_backup_if_exists(self, original_path: str) -> bool:
        """Restore a backup file if it exists in the backup registry (persisted in database)."""
        try:
            backup_path = self._db.get_backup_path(original_path)
            if backup_path:
                if os.path.exists(backup_path):
                    try:
                        os.rename(backup_path, original_path)
                        self.logger.info(f"Backup restored: {backup_path} -> {original_path}")
                        self._db.remove_backup_entry(original_path)
                        return True
                    except Exception as e:
                        self.logger.error(f"Failed to restore backup: {e}")
                else:
                    # Backup file no longer exists
                    self._db.remove_backup_entry(original_path)
        except Exception as e:
            # Handle missing table or other DB errors gracefully
            self.logger.debug(f"Backup lookup skipped (table may not exist): {e}")
        return False

    def _cleanup_empty_parents(self, path: str, protected_roots: set = None) -> str:
        """Recursively remove empty parent directories.
        NEVER removes any path that is in protected_roots or is a parent of them.
        If protected_roots is None, automatically fetches ALL target roots from ALL apps using LinkMasterRegistry.
        Returns the path of the protected root that stopped the pruning, or None if it reached root or stopped as expected.
        """
        # 🚨 AUTO-FETCH ALL TARGET ROOTS FROM GLOBAL REGISTRY
        if protected_roots is None:
            protected_roots = set()
            try:
                from src.core.link_master.database import LinkMasterRegistry
                registry = LinkMasterRegistry()
                all_apps = registry.get_apps()
                for app in all_apps:
                    for key in ['target_root', 'target_root_2', 'target_root_3']:
                        val = app.get(key)
                        if val:
                            protected_roots.add(val)
                self.logger.info(f"[Prune Safety] Protected roots from Registry: {protected_roots}")
            except Exception as e:
                self.logger.warning(f"Failed to auto-fetch protected roots: {e}")
        
        norm_protected = {os.path.normpath(p).lower() for p in protected_roots if p}
        
        while path:
            try:
                parent = core_handler.get_parent(path)
                if not parent or path == parent:
                    break
            except: break

            norm_path = os.path.normpath(path).lower()
            
            # Safety: Never remove if this path IS a protected root
            if norm_path in norm_protected:
                self.logger.warning(f"[Prune Safety] Pruning stopped at protected root: {path}")
                return path
            
            # Safety: Never remove if this path is a PARENT of any protected root
            is_parent_of_protected = any(p.startswith(norm_path + os.sep) or p.startswith(norm_path + '/') for p in norm_protected)
            if is_parent_of_protected:
                self.logger.warning(f"[Prune Safety] Pruning stopped at parent of protected root: {path}")
                return path

            try:
                if core_handler.is_dir(path) and not os.listdir(path):
                    core_handler.remove_empty_dir(path)
                    self.logger.info(f"Cleaned empty parent: {path}")
                    path = parent
                else: break
            except: break
        
        return None

    def get_link_status(self, target_link_path: str, expected_source: str = None, 
                        expected_transfer_mode: str = 'symlink', deploy_rule: str = 'folder', rules: dict = None) -> dict:
        """
        Checks if the target_link_path is a valid link to expected_source.
        Returns {'status': 'linked'|'conflict'|'none', 'type': 'symlink'|'junction'|'file'|'dir'}
        
        Args:
            target_link_path: The path where the link should be.
            expected_source: The source path it should point to.
            expected_transfer_mode: 'symlink' or 'copy'. If 'copy', physical files are valid links.
            deploy_rule: 'folder', 'files', 'tree', etc. used for specialized checks.
            rules: (dict) Optional deployment rules for Custom/Tree modes.
        """
        if not os.path.exists(target_link_path) and not os.path.islink(target_link_path):
            return {"status": "none", "type": "none"}
        
        # Phase 42: Declarative State Check
        # If registered in DB, it's ours.
        if self._db.is_file_ours(target_link_path):
             return {"status": "linked", "type": expected_transfer_mode}

        # Check for Copy Mode validity FIRST (Physical Tree / Physical Copy Fix)
        # 🚨 Safety: If we expect a copy, we only treat it as linked if metadata exists 
        # OR if it's a file. If it's a directory, it might just be the search root (collision!).

        # -------------------------------------------------------------------------
        # 🚨 UNIFIED FLATTEN (FILES) MODE CHECK
        # This block handles BOTH Copy and Symlink detection for 'files' mode identically.
        # It relies on strict source-file enumeration to avoid ghost detection in target roots.
        # -------------------------------------------------------------------------
        if (deploy_rule == 'files' or deploy_rule == 'custom') and expected_source and os.path.isdir(expected_source):
             # Ensure target directory exists (it might be the root itself)
             if os.path.isdir(target_link_path):
                 files_found = 0
                 files_total = 0
                 
                 # Prepare Excludes ONLY if Custom Mode
                 excludes = []
                 if deploy_rule == 'custom' and rules:
                     excludes = rules.get('exclude', [])

                 missing_samples = []
                 try:
                     import fnmatch
                     # Get list of all items in source (files and dirs)
                     all_items = os.listdir(expected_source)
                     for f in all_items:
                         f_path = os.path.join(expected_source, f)
                         
                         # Exclude Check (Apply to both files and dirs)
                         if excludes and any(fnmatch.fnmatch(f, pat) for pat in excludes):
                             continue
                             
                         files_total += 1
                         target_file = os.path.join(target_link_path, f)
                         
                         is_valid = False
                         if os.path.islink(target_file):
                             # Link Verification
                             real = os.readlink(target_file)
                             if not os.path.isabs(real):
                                 real = os.path.join(os.path.dirname(target_file), real)
                             
                             if self._normalize_path(real) == self._normalize_path(f_path):
                                 files_found += 1
                                 is_valid = True
                         elif os.path.exists(target_file):
                             # Physical existence check (for Copy mode)
                             # Note: We take existence as "linked" for simplicity in copy mode
                             files_found += 1
                             is_valid = True
                         
                         if not is_valid and len(missing_samples) < 3:
                             missing_samples.append(f)

                 except Exception as e:
                     # self.logger.warning(f"Flat check error: {e}")
                     pass
                 
                 res = {"status": "none", "type": "none"}
                 if files_total == 0:
                     # If all items are excluded, it's effectively linked if target root exists
                     res = {"status": "linked", "type": expected_transfer_mode if expected_transfer_mode else "dir"}
                 elif files_found > 0:
                     if files_found >= files_total:
                         res = {"status": "linked", "type": expected_transfer_mode if expected_transfer_mode else "dir"}
                     else:
                         res = {"status": "partial", "type": expected_transfer_mode if expected_transfer_mode else "dir", 
                                "missing_samples": missing_samples}
                 
                 return res

        if expected_transfer_mode == 'copy':
             is_link = os.path.islink(target_link_path)
             exists = os.path.exists(target_link_path)
             
             if exists and not is_link:
                 
                 if os.path.isfile(target_link_path):
                     # If it's a file, we can't easily verify source without metadata, 
                     # but it's better than incorrectly flagging search roots as linked.
                     return {"status": "linked", "type": "copy"}

                 # For directories, existence is NOT enough if it could be a search root.
                 from src.core.link_master.database import LinkMasterRegistry
                 registry = LinkMasterRegistry()
                 all_apps = registry.get_apps()
                 protected_roots = set()
                 for app in all_apps:
                     for key in ['target_root', 'target_root_2', 'target_root_3']:
                         if app.get(key): protected_roots.add(os.path.normpath(app.get(key)).lower())
                 
                 if os.path.normpath(target_link_path).lower() in protected_roots:
                     return {"status": "none", "type": "search_root"}
                 
                 # If it's a subfolder that is NOT a search root, it's likely our folder-level deployment.
                 return {"status": "linked", "type": "copy"}
             
             # If it IS a symlink but we expected copy, it's technically a conflict (or user change)
             # But let's fall through to standard check.

        # Standard Symlink Check
        if os.path.islink(target_link_path):
            real_target = os.readlink(target_link_path)
            if expected_source:
                norm_real = self._normalize_path(real_target)
                norm_exp = self._normalize_path(expected_source)
                if norm_real == norm_exp:
                    return {"status": "linked", "target": real_target}
                else:
                    return {"status": "conflict", "target": real_target}
            return {"status": "linked", "target": real_target}
            
        # If it's a directory, it MIGHT be a partial deployment or a physical copy
        if os.path.isdir(target_link_path):
            if expected_source:
                exp_norm = self._normalize_path(expected_source)
                try:
                    # 1. Symlink-based partial detection (Standard Tree/Folder Fallback)
                    # Note: We skip this if we already handled 'files' mode to avoid double counting or inefficiency
                    # But for tree mode, we still need it? 
                    # If deploy_rule was 'files', we returned above (if >0 found). 
                    # If deploy_rule was 'files' and found 0, we fall through.
                    # 🚨 FIX: For 'files' mode, we should NOT scan recursively. 
                    # If we didn't find the specific files above, we shouldn't hunt for ghosts in subdirs.
                    
                    if deploy_rule != 'files':
                        for root, dirs, files in os.walk(target_link_path):
                            for name in files + dirs:
                                path = os.path.join(root, name)
                                if os.path.islink(path):
                                    real = os.readlink(path)
                                    if not os.path.isabs(real):
                                        real = os.path.join(os.path.dirname(path), real)
                                    
                                    real_norm = self._normalize_path(real)
                                    if real_norm.startswith(exp_norm):
                                        return {"status": "linked", "type": "partial"}
                except: pass
            
            # 2. DB-based directory detection (Phase 43)
            # This handles physical "tree" deployments where files are registered but the root folder is not.
            if self._db.is_directory_ours(target_link_path, expected_source_prefix=expected_source):
                return {"status": "linked", "type": "copy"}

            # Phase 42: Exact DB match for the directory itself (folder-level copy)
            db_source = self._db.get_deployed_file_source(target_link_path)
            if db_source and expected_source:
                if self._normalize_path(db_source) == self._normalize_path(expected_source):
                    return {"status": "linked", "type": "copy"}
            
            # If expected_source is specified but no link to it was found, treat as 'none'
            return {"status": "none", "type": "dir_no_match"}
        
        # Check DB for copy deployment (Phase 42)
        db_source = self._db.get_deployed_file_source(target_link_path)
        if db_source and expected_source:
            if self._normalize_path(db_source) == self._normalize_path(expected_source):
                return {"status": "linked", "type": "copy"}
             
        return {"status": "conflict", "type": "file"}
    
    
    def undeploy_copy(self, target_path: str, force: bool = False) -> bool:
        """Remove a copy deployment and its metadata.
        
        Args:
            target_path: The path to the copied file/folder.
            force: If True, delete even without metadata (for Physical Tree copies).
        """
        import shutil
        
        # Check if target exists
        if not os.path.exists(target_path):
             self.logger.debug(f"Target does not exist, nothing to undeploy: {target_path}")
             return False
        
        # If it's a symlink, this is wrong - should use _cleanup_link
        if os.path.islink(target_path):
             self.logger.warning(f"Target is a symlink, use _cleanup_link instead: {target_path}")
             return self._cleanup_link(target_path)
        
        # Check DB tracking (Phase 42)
        is_ours = self._db.is_file_ours(target_path)
        if not is_ours and not force:
            # Final fallback: Check Legacy sidecar for transition
            if os.path.isdir(target_path):
                meta_file = os.path.join(target_path, ".lm_deploy_info.json")
            else:
                meta_file = target_path + ".lm_deploy_info"
            
            if not os.path.exists(meta_file):
                self.logger.warning(f"No copy registration (DB or Legacy) found for: {target_path}")
                return False
        
        try:
            # Cleanup Legacy metadata if exists
            if os.path.isdir(target_path):
                meta_file = os.path.join(target_path, ".lm_deploy_info.json")
            else:
                meta_file = target_path + ".lm_deploy_info"
            
            if os.path.exists(meta_file):
                try: os.remove(meta_file)
                except: pass
            
            # Phase 42: Clear DB tracking
            try: self._db.remove_deployed_file_entry(target_path)
            except: pass

            # 🚨 Safety Check: NEVER remove a directory if it's a registered search root
            if os.path.isdir(target_path):
                # Get protected roots from registry
                from src.core.link_master.database import LinkMasterRegistry
                registry = LinkMasterRegistry()
                all_apps = registry.get_apps()
                protected_roots = set()
                for app in all_apps:
                    for key in ['target_root', 'target_root_2', 'target_root_3']:
                        if app.get(key): protected_roots.add(os.path.normpath(app.get(key)).lower())
                
                norm_target = os.path.normpath(target_path).lower()
                if norm_target in protected_roots:
                     self.logger.error(f"Undeploy Safety: Blocked attempt to delete search root: {target_path}")
                     return False
                
                # If verified not a root, we can rmtree.
                try:
                    import shutil
                    shutil.rmtree(target_path)
                    self.logger.info(f"Successfully removed copy-deployed directory: {target_path}")
                except Exception as e:
                    self.logger.error(f"Failed to rmtree {target_path}: {e}")
                    return False
            elif os.path.exists(target_path):
                os.remove(target_path)
            
            # Phase X: Restore backups for copy mode too
            self._restore_backup_if_exists(target_path)
            
            self.logger.info(f"Copy deployment removed: {target_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to remove copy deployment: {e}")
            return False

    def undeploy(self, target_path: str, transfer_mode: str = 'symlink', source_path_hint: str = None) -> bool:
        """Unified undeploy method handles symlink or copy based on mode."""
        if transfer_mode == 'copy':
            # Force=True to handle Physical Tree copies without metadata
            return self.undeploy_copy(target_path, force=True)
        else:
            return self.remove_link(target_path, source_path_hint=source_path_hint)

    def deploy_with_rules(self, source_path: str, target_link_path: str, rules: dict = None, 
                          deploy_rule: str = 'inherit', transfer_mode: str = 'symlink', 
                          conflict_policy: str = 'backup', package_rel_path: str = None) -> bool:
        """
        Deploys source to target using specified rules.
        Supports 'custom' mode which allows mixed symlink/copy based on JSON rules.
        """
        import json
        
        # Ensure rules is a dict (handle potential string input for robustness)
        if isinstance(rules, str):
            try: rules = json.loads(rules)
            except: 
                self.logger.error(f"Invalid rules JSON: {rules}")
                rules = {}
        
        # 1. Custom Mode Logic
        if deploy_rule == 'custom':
            if not os.path.exists(source_path): return False
            if not os.path.isdir(source_path):
                # If source is file, just deploy it using default mode
                if transfer_mode == 'copy':
                    return self.deploy_copy(source_path, target_link_path, conflict_policy)
                else:
                    return self.deploy_link(source_path, target_link_path, conflict_policy)

            # Ensure target root directory exists (for the flat items)
            try:
                if not os.path.exists(target_link_path):
                    os.makedirs(target_link_path, exist_ok=True)
            except: pass

            success_all = True
            
            # Use 'exclude' list from rules
            import fnmatch
            excludes = rules.get('exclude', []) if (rules and isinstance(rules, dict)) else []

            # Iterate source files
            for item_name in os.listdir(source_path):
                # Exclude Check
                if excludes and any(fnmatch.fnmatch(item_name, pat) for pat in excludes):
                    continue

                src_item = os.path.join(source_path, item_name)
                dst_item = os.path.join(target_link_path, item_name)
                
                item_mode = transfer_mode # Default to App Default
                
                # Check granular rules if available
                # USER FEEDBACK: JSON uses "transfer_overrides" key: {"file.ext": "copy"}
                if rules and isinstance(rules, dict):
                    t_overrides = rules.get('transfer_overrides', {})
                    if item_name in t_overrides:
                        val = t_overrides[item_name]
                        if val in ['copy', 'symlink']: 
                            item_mode = val
                            
                # Execute Deployment
                res = False
                if item_mode == 'copy':
                    res = self.deploy_copy(src_item, dst_item, conflict_policy)
                else:
                    res = self.deploy_link(src_item, dst_item, conflict_policy)
                
                if not res: success_all = False
                
            return success_all

        # 2. Flat (Files) Mode
        if deploy_rule == 'files':
             if not os.path.exists(source_path) or not os.path.isdir(source_path): return False
             try:
                 if not os.path.exists(target_link_path): os.makedirs(target_link_path, exist_ok=True)
             except: pass
             
             success_all = True
             for item_name in os.listdir(source_path):
                 src_item = os.path.join(source_path, item_name)
                 dst_item = os.path.join(target_link_path, item_name)
                 
                 res = False
                 if transfer_mode == 'copy':
                     res = self.deploy_copy(src_item, dst_item, conflict_policy)
                 else:
                     res = self.deploy_link(src_item, dst_item, conflict_policy)
                 if not res: success_all = False
             return success_all
        
        # 3. Default Folder/Tree Mode logic (Standard single link/copy)
        # Phase 42: Store package info for workers
        self._pkg_rel = package_rel_path
        
        # 1.1. Resolve Rule (Phase 5 Logic)
        resolved_rule = deploy_rule
        if not resolved_rule or resolved_rule == 'inherit':
            # This is expected to be handled by the caller (batch_ops) 
            # by looking up the app-specific default for target A/B/C.
            # If we reach here with 'inherit', default to 'folder'.
            resolved_rule = 'folder'

        # 2. Determine Real Transfer Mode
        real_mode = transfer_mode
        if real_mode == 'symlink' and not self.allow_symlinks:
            self.logger.info("Symlinks not available on this system. Falling back to COPY mode.")
            real_mode = 'copy'
            
        # 3. Quick Path for Folder-level operations
        # JSON-based excludes/overrides/skip_levels are strictly Custom/Tree Mode features
        is_custom = resolved_rule == 'custom'
        is_tree = resolved_rule == 'tree'
        
        excludes = rules.get('exclude', []) if is_custom else []
        overrides = rules.get('overrides', rules.get('rename', {})) if is_custom else {}
        skip_levels = int(rules.get('skip_levels', 0)) if (is_custom or is_tree) else 0
        
        has_complex_filters = (isinstance(excludes, list) and len(excludes) > 0) or \
                              (isinstance(overrides, dict) and len(overrides) > 0) or \
                              (skip_levels > 0)
        
        # If 'folder' rule and NO filters/skips/overrides, we can just link/copy the root once
        if resolved_rule == 'folder' and not has_complex_filters:
            if real_mode == 'copy':
                return self.deploy_copy(source_path, target_link_path, conflict_policy)
            else:
                return self.deploy_link(source_path, target_link_path, conflict_policy)

        # 4. Partial / File-level Deployment for 'files', 'tree', or 'folder' with filters
        self.logger.info(f"Proceeding with Partial Deployment: rule={deploy_rule}, mode={real_mode}, skip={skip_levels}, target_root={target_link_path}")
            
        if not os.path.exists(source_path): 
            self.logger.error(f"Source path missing for deploy: {source_path}")
            return False
        
        # If target exists but is not a directory (and it should be for partial deploy), handle conflict
        if os.path.lexists(target_link_path) and not os.path.isdir(target_link_path):
            if not self._handle_conflict(target_link_path, conflict_policy):
                return False
        
        # Ensure target dir exists
        os.makedirs(target_link_path, exist_ok=True)

        files_to_deploy = []
        try:
            for root, dirs, files in os.walk(source_path):
                # Calculate base relative path from source root
                rel_root = os.path.relpath(root, source_path).replace('\\', '/')
                if rel_root == ".": rel_root = ""
                
                # Filter dirs for walk optimization
                dirs[:] = [d for d in dirs if not self._is_excluded((f"{rel_root}/{d}" if rel_root else d), excludes)]
                
                start_lvl = 0
                if rel_root:
                    start_lvl = len(rel_root.split('/'))
                
                # Skip levels check
                if start_lvl < skip_levels:
                    # If we are below skip levels, we don't deploy files here, 
                    # but we continue walking into subdirs
                    # Note: dirs are already filtered above
                    continue

                for name in files:
                    rel_path = f"{rel_root}/{name}" if rel_root else name
                    
                    if self._is_excluded(rel_path, excludes):
                        continue
                        
                    # Check overrides/renames
                    deploy_path = rel_path
                    if resolved_rule == 'custom' and rel_path in overrides:
                         deploy_path = overrides[rel_path]
                    
                    # 🚨 NEW: Handle 'files' (Flatten) mode - strip directory structure
                    if resolved_rule == 'files':
                        deploy_path = name

                    # Determine target path
                    # Adjust for skip levels: remove first N components
                    if skip_levels > 0 and resolved_rule != 'files':
                        parts = deploy_path.split('/')
                        if len(parts) > skip_levels:
                            deploy_path = '/'.join(parts[skip_levels:])
                        else:
                            continue # Should be covered by dir continue, but safety
                    
                    full_target = os.path.join(target_link_path, deploy_path.replace('/', os.sep))
                    src_full = os.path.join(root, name)
                    files_to_deploy.append((src_full, full_target))

            # Phase 45 Checks for Collisions and Safety
            # Check collisions
            unique_targets = {}
            collisions = []
            for src, tgt in files_to_deploy:
                tgt_norm = tgt.lower() if os.name == 'nt' else tgt
                
                if tgt_norm in unique_targets:
                    collisions.append((src, tgt)) 
                else:
                    unique_targets[tgt_norm] = src

            if collisions:
                self.logger.warning(f"Aborting deployment due to {len(collisions)} collisions.")
                detailed_collisions = []
                for src_new, tgt_new in collisions:
                    tgt_norm = tgt_new.lower() if os.name == 'nt' else tgt_new
                    src_existing = unique_targets[tgt_norm]
                    detailed_collisions.append({
                        'target': tgt_new,
                        'source_existing': src_existing,
                        'source_conflicting': src_new
                    })
                raise DeploymentCollisionError(detailed_collisions)

            # Phase 45 CRITICAL: Atomic Safety Check
            # Use safety_verifier (imported at module level)
            safety_issues = []
            for src, tgt in files_to_deploy:
                # Check target path safety
                if not safety_verifier.verify_safety(tgt, operation='deploy', silent=True, logger=self.logger):
                   safety_issues.append(tgt)
                   
            if safety_issues:
                self.logger.error(f"Aborting batch deployment due to {len(safety_issues)} safety violations.")
                self.logger.error(f"First violation: {safety_issues[0]}")
                return False

            if not files_to_deploy:
                return True # Nothing to do after filtering

            if real_mode == 'copy':
                self.logger.info(f"Parallel bulk copy: {len(files_to_deploy)} files")
                results = self.deploy_copies_batch(files_to_deploy, conflict_policy)
                # Phase X: Save metadata to facilitate unlinking and status check
                # Check for overall success in results
                any_success = any(r['status'] == 'success' for r in results)
                # Phase 42: Register all successful files in DB
                for res in results:
                    if res.get('status') == 'success' and package_rel_path:
                        self._db.register_deployed_file(res['path'], res.get('source', ''), package_rel_path, deploy_type='copy')
            else:
                self.logger.info(f"Parallel bulk symlink: {len(files_to_deploy)} files")
                results = self.deploy_links_batch(files_to_deploy, conflict_policy)
                
                # Phase 42: Register all successful symlinks in DB
                for res in results:
                    if res.get('status') == 'success' and package_rel_path:
                        source_map = {tgt: src for src, tgt in files_to_deploy}
                        self._db.register_deployed_file(res['path'], source_map.get(res['path'], ''), package_rel_path, deploy_type='symlink')
            
            # Check for generic failure
            success = True
            for res in results:
                if res.get('status') == 'error' and conflict_policy != 'skip':
                    success = False
                          
        except DeploymentCollisionError:
            raise
        except Exception as e:
            self.logger.error(f"deploy_with_rules internal failure: {e}")
            return False
            
        return success

    def deploy_links_batch(self, link_pairs: list, conflict_policy: str = 'backup') -> list:
        """
        Processes multiple link creations in parallel using ProcessPoolExecutor.
        link_pairs: List of (source_path, target_link_path)
        """
        import time
        t0 = time.perf_counter()
        results = []
        
        # Collect results
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_path = {
                executor.submit(_parallel_link_worker, src, tgt, conflict_policy): (src, tgt) 
                for src, tgt in link_pairs
            }
            
            for future in as_completed(future_to_path):
                try:
                    res = future.result()
                    results.append(res)
                    # Sync back to internal actions tracker for reporting
                    if res['status'] != 'error' and res.get('action') != 'none':
                        self.last_actions.append({'type': res.get('action'), 'path': res['path']})
                    
                    # Phase 14: Register backup if created
                    if res.get('backup_path'):
                        # Using original path (res['path']) as key
                        self._db.register_backup(res['path'], res['backup_path'])
                        
                    if res['status'] == 'error':
                        self.logger.error(f"Batch link failed: {res['path']} -> {res['msg']}")
                except Exception as exc:
                    pair = future_to_path[future]
                    self.logger.error(f"Worker generated an exception for {pair}: {exc}")
                    results.append({"status": "error", "path": pair[1], "msg": str(exc)})

        self.logger.info(f"Parallel batch ({len(link_pairs)} items) took {time.perf_counter()-t0:.3f}s")
        return results

    def deploy_copies_batch(self, copy_pairs: list, conflict_policy: str = 'overwrite') -> list:
        """
        Processes multiple file copies in parallel using ThreadPoolExecutor.
        copy_pairs: List of (source_path, target_path)
        """
        import time
        t0 = time.perf_counter()
        results = []
        
        # Collect results
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_path = {
                executor.submit(_parallel_copy_worker, src, tgt, conflict_policy): (src, tgt) 
                for src, tgt in copy_pairs
            }
            
            for future in as_completed(future_to_path):
                try:
                    res = future.result()
                    results.append(res)
                    # Sync back to internal actions tracker for reporting
                    if res['status'] != 'error' and res.get('action') != 'none':
                        self.last_actions.append({'type': 'copy', 'path': res['path']})
                        
                    # Phase 14: Register backup if created
                    if res.get('backup_path'):
                        self._db.register_backup(res['path'], res['backup_path'])
                        
                    if res['status'] == 'error':
                        self.logger.error(f"Batch copy failed: {res['path']} -> {res['msg']}")
                except Exception as exc:
                    pair = future_to_path[future]
                    self.logger.error(f"Copy worker generated an exception for {pair}: {exc}")
                    results.append({"status": "error", "path": pair[1], "msg": str(exc)})

        self.logger.info(f"Parallel copy batch ({len(copy_pairs)} items) took {time.perf_counter()-t0:.3f}s")
        return results

    def _is_excluded(self, rel_path: str, exclude_list: list) -> bool:
        import fnmatch
        path_norm = rel_path.replace("\\", "/")
        parts = path_norm.split("/")
        
        # Phase 28: Global hard-coded exclusions for internal folders
        # Check if ANY part of the path is restricted
        restricted = {"_Backup", "_Trash"}
        for part in parts:
            if part in restricted or part.startswith('.'):
                return True
        
        # Check custom patterns against both full rel_path and basename
        base = parts[-1] if parts else ""
        for pattern in exclude_list:
            if fnmatch.fnmatch(path_norm, pattern) or fnmatch.fnmatch(base, pattern):
                return True
        return False

    @staticmethod
    def _normalize_path(path: str) -> str:
        """
        Robust normalization for Windows paths, handling \\?\\ prefix,
        case sensitivity, and absolute resolution.
        """
        if not path: return ""
        
        # 1. Resolve Absolute
        abs_path = os.path.abspath(path)
        
        # 2. Strip Extended Length Prefix if present
        # Note: \\ in python string is \, so \\\\?\\
        if abs_path.startswith("\\\\?\\"):
            abs_path = abs_path[4:]
            
        # 3. Normcase (lowercase on Windows)
        return os.path.normcase(abs_path)

    def cleanup_links_in_target(self, target_dir: str, valid_source_root: str, recursive: bool = True, restore_backups: bool = True):
        """
        Removes ALL symlinks in target_dir that point to valid_source_root (or its children).
        If recursive=True (default), scans subdirectories.
        If restore_backups=True, restores backed up files after removing links.
        """
        if not os.path.isdir(target_dir): return
        
        valid_source_root_norm = self._normalize_path(valid_source_root)
        
        if recursive:
            # bottom-up to clean empty folders
            for root, dirs, files in os.walk(target_dir, topdown=False):
                for name in files + dirs:
                    path = os.path.join(root, name)
                    if os.path.islink(path):
                        try:
                            real = os.readlink(path)
                            if not os.path.isabs(real):
                                real = os.path.join(os.path.dirname(path), real)
                            if self._normalize_path(real).startswith(valid_source_root_norm):
                                os.unlink(path)
                                self.logger.info(f"Recursive cleanup removed: {path}")
                                # Restore backup if exists
                                if restore_backups:
                                    self._restore_backup_if_exists(path)
                        except: pass
                # After cleaning files/links in this dir, try removing dir if empty
                if root != target_dir: # Don't remove the root we started with
                    try:
                        if not os.listdir(root):
                            os.rmdir(root)
                            self.logger.info(f"Cleaned empty subfolder: {root}")
                    except: pass
        else:
            # Standard Top-level scan
            try:
                with os.scandir(target_dir) as it:
                    for entry in it:
                        if entry.is_symlink():
                            try:
                                real = os.readlink(entry.path)
                                if not os.path.isabs(real):
                                    real = os.path.join(os.path.dirname(entry.path), real)
                                if self._normalize_path(real).startswith(valid_source_root_norm):
                                    os.unlink(entry.path)
                                    self.logger.info(f"Cleanup removed: {entry.path}")
                            except: pass
            except Exception as e:
                self.logger.error(f"Cleanup scan failed: {e}")
    def remove_links_pointing_to(self, search_roots: list, source_root: str):
        """
        Sweeps through a list of search roots and removes ANY symlink found
        that points specifically into the source_root.
        Uses ThreadPoolExecutor for parallel deletion.
        """
        import time
        t0 = time.perf_counter()
        source_root_norm = self._normalize_path(source_root)
        self.logger.info(f"Sweeping for orphaned links pointing to: {source_root_norm}")
        
        # Phase 1: Collect all orphaned links
        orphan_links = set()
        empty_dirs = []
        
        for root_dir in search_roots:
            if not os.path.isdir(root_dir): continue
            
            # Phase: DB-backed Sweep (Declarative)
            # Find any files registered in the DB for this source package
            # This is much faster and more reliable than scanning the whole target tree for copies.
            try:
                # We need the relative path of the package to query the DB
                # If source_root is e.g. "C:/Mods/Packages/MyMod" and storage_root is "C:/Mods/Packages"
                # then rel_path is "MyMod"
                if hasattr(self, '_db'):
                    # Phase 42: Slash Consistency Fix
                    # Normalize search root for DB query (DB uses '/' and lowercase on Windows)
                    # Use a set for orphan_links for fast lookup
                    source_root_db = source_root_norm.replace('\\', '/')
                    
                    with self._db.get_connection() as conn:
                        cursor = conn.cursor()
                        # Use LIKE to match all files inside this source package
                        # register_deployed_file already lowercases source_path, so this matches efficiently
                        cursor.execute("SELECT target_path FROM lm_deployed_files WHERE source_path LIKE ?", (f"{source_root_db}%",))
                        db_items = [row[0] for row in cursor.fetchall()]
                        for item_path in db_items:
                            if os.path.exists(item_path) or os.path.islink(item_path):
                                orphan_links.add(item_path)
                                self.logger.debug(f"[Sweep-DB] Found registered item: {item_path}")
            except Exception as e:
                self.logger.warning(f"DB-backed sweep query failed: {e}")

            # Use bottom-up walk to allow cleaning empty folders after unlinking (Legacy/Safety fallback)
            for root, dirs, files in os.walk(root_dir, topdown=False):
                for name in files + dirs:
                    path = os.path.join(root, name)
                    if path in orphan_links: continue # Already found via DB
                    
                    if os.path.islink(path):
                        try:
                            # Read link and normalize
                            real = os.readlink(path)
                            if not os.path.isabs(real):
                                real = os.path.join(os.path.dirname(path), real)
                                
                            real_norm = self._normalize_path(real)
                            # Safe Match: exact or sub-path
                            if real_norm == source_root_norm or real_norm.startswith(source_root_norm + "/"):
                                orphan_links.add(path)
                        except: pass
                    else:
                        # Check for copy metadata (Legacy/External fallback)
                        source_meta = self._db.get_deployed_file_source(path)
                        if source_meta:
                            meta_norm = self._normalize_path(source_meta)
                            if meta_norm == source_root_norm or meta_norm.startswith(source_root_norm + "/"):
                                orphan_links.add(path)
                
                # Track empty folders for later cleanup
                if root != root_dir:
                    empty_dirs.append(root)
        
        # Phase 2: Parallel deletion using ThreadPoolExecutor
        removed_count = 0
        if orphan_links:
            def _unlink_safe(path):
                try:
                    if os.name == 'nt':
                        path_key = path.replace('\\', '/').lower()
                    else:
                        path_key = path
                        
                    if os.path.islink(path):
                        os.unlink(path)
                        self.logger.debug(f"[Sweep] Unlinked symlink: {path}")
                    elif os.path.isdir(path):
                        shutil.rmtree(path)
                        self.logger.info(f"[Sweep] Removed physical directory (copy): {path}")
                    else:
                        os.remove(path)
                        self.logger.debug(f"[Sweep] Removed file: {path}")
                    
                    # Phase 42: Clear DB entry
                    if hasattr(self, '_db'):
                        self._db.remove_deployed_file_entry(path_key)
                        
                    return True
                except Exception as e:
                    self.logger.warning(f"Sweep cleanup failed for {path}: {e}")
                    return False
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Use wait to get results in order and match with paths
                futures = {executor.submit(_unlink_safe, p): p for p in orphan_links}
                failed_paths = []
                for future in as_completed(futures):
                    if not future.result():
                        failed_paths.append(futures[future])
                    else:
                        removed_count += 1
        
        # Phase 3: Cleanup empty folders (sequential, as order matters)
        dirs_removed = 0
        for d in empty_dirs:
            try:
                if os.path.isdir(d) and not os.listdir(d):
                    os.rmdir(d)
                    dirs_removed += 1
            except: pass
        
        elapsed = time.perf_counter() - t0
        self.logger.info(f"Sweep completed: Removed {removed_count} orphaned links, {dirs_removed} empty dirs in {elapsed:.3f}s")
        
        return removed_count > 0, failed_paths



