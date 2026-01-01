""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を介すること。
"""

import os
import logging
import ctypes
from src.core import core_handler
from concurrent.futures import ThreadPoolExecutor, as_completed

def _parallel_link_worker(source_path: str, target_link_path: str, conflict_policy: str):
    """
    Top-level worker for parallel execution. Handles a single link creation.
    Returns a result dict for the main process to aggregate.
    """
    import os
    import ctypes
    
    # Simple check for admin/dev mode (informative for errors)
    def is_admin():
        try: return ctypes.windll.shell32.IsUserAnAdmin()
        except: return False

    if not os.path.exists(source_path):
        return {"status": "error", "path": target_link_path, "msg": f"Source missing: {source_path}"}
    
    # Ensure target directory
    os.makedirs(os.path.dirname(target_link_path), exist_ok=True)
    
    # Conflict handling (Simplified for parallel worker: backup or overwrite)
    action_taken = "none"
    if os.path.lexists(target_link_path):
        if conflict_policy == 'skip':
            return {"status": "skip", "path": target_link_path}
        
        try:
            if conflict_policy == 'overwrite':
                if os.path.islink(target_link_path) or os.path.isfile(target_link_path):
                    os.unlink(target_link_path)
                elif os.path.isdir(target_link_path):
                    import shutil
                    shutil.rmtree(target_link_path)
                action_taken = "overwrite"
            elif conflict_policy == 'backup':
                import time
                import random
                import string
                suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
                backup_path = f"{target_link_path}.bak_{int(time.time())}_{suffix}"
                os.rename(target_link_path, backup_path)
                action_taken = "backup"
        except Exception as e:
            return {"status": "error", "path": target_link_path, "msg": f"Conflict handle failed: {e}"}

    try:
        is_dir = os.path.isdir(source_path)
        os.symlink(source_path, target_link_path, target_is_directory=is_dir)
        return {"status": "success", "path": target_link_path, "action": action_taken}
    except OSError as e:
        msg = str(e)
        if not is_admin():
            msg += " (Admin/DevMode may be required)"
        return {"status": "error", "path": target_link_path, "msg": msg}

class Deployer:
    def __init__(self):
        self.logger = logging.getLogger("LinkMasterDeployer")
        self.last_actions = [] # Phase 1.1.6: Track actions for UI reporting
        # Cap max_workers to 60 to avoid Windows ProcessPoolExecutor limit (61)
        count = os.cpu_count() or 4
        self.max_workers = min(count, 60)
    
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
            return True
        except OSError as e:
            self.logger.error(f"Symlink creation failed: {e}")
            if not self._is_admin():
                self.logger.warning("Symlink creation often requires Administrator privileges or Developer Mode on Windows.")
            return False

    def _handle_conflict(self, path: str, policy: str) -> str:
        """Handles existing path according to policy. Returns action taken: 'backup', 'overwrite', 'skip', 'error', 'none'."""
        if policy == 'skip':
            self.logger.info(f"Policy: SKIP - preserving {path}")
            self.last_actions.append({'type': 'skip', 'path': path})
            return 'skip'
        
        if policy == 'overwrite':
            try:
                if os.path.islink(path) or os.path.isfile(path):
                    os.unlink(path)
                elif os.path.isdir(path):
                    import shutil
                    shutil.rmtree(path)
                self.logger.info(f"Policy: OVERWRITE - removed {path}")
                self.last_actions.append({'type': 'overwrite', 'path': path})
                return 'overwrite'
            except Exception as e:
                self.logger.error(f"Failed to overwrite {path}: {e}")
                return 'error'
                
        if policy == 'backup':
            try:
                import time
                backup_path = f"{path}.bak_{int(time.time())}"
                os.rename(path, backup_path)
                self.logger.info(f"Policy: BACKUP - moved {path} to {backup_path}")
                self.last_actions.append({'type': 'backup', 'path': path, 'backup_path': backup_path})
                return 'backup'
            except Exception as e:
                self.logger.error(f"Failed to backup {path}: {e}")
                return 'error'
        
        return 'error'

    def remove_link(self, target_link_path: str, source_path_hint: str = None) -> bool:
        """
        Removes the symbolic link at target_link_path.
        If it's a directory (Partial Deployment), performs recursive cleanup.
        """
        if not os.path.lexists(target_link_path):
             self.logger.warning(f"Link/Target not found to remove: {target_link_path}")
             return False
        
        if os.path.islink(target_link_path):
            try:
                os.unlink(target_link_path)
                self.logger.info(f"Symlink removed: {target_link_path}")
                # Try cleaning parent if empty
                self._cleanup_empty_parents(os.path.dirname(target_link_path))
                return True
            except OSError as e:
                self.logger.error(f"Failed to remove symlink: {e}")
                return False

        if os.path.isdir(target_link_path):
            if source_path_hint:
                self.logger.info(f"Cleaning up directory-based (Partial) deployment: {target_link_path}")
                self.cleanup_links_in_target(target_link_path, source_path_hint, recursive=True)
                # If empty after cleanup, remove it
                if not os.listdir(target_link_path):
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

    def _cleanup_empty_parents(self, path: str):
        """Recursively remove empty parent directories."""
        while path and path != os.path.dirname(path):
            try:
                if os.path.isdir(path) and not os.listdir(path):
                    os.rmdir(path)
                    self.logger.info(f"Cleaned empty parent: {path}")
                    path = os.path.dirname(path)
                else: break
            except: break

    def get_link_status(self, target_link_path: str, expected_source: str = None) -> dict:
        """
        Returns status: missing, linked, conflict
        Handles both physical symlinks and Partial Deployment directories.
        """
        if not os.path.lexists(target_link_path):
            return {"status": "missing"}
            
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
            
        # If it's a directory, it MIGHT be a partial deployment
        if os.path.isdir(target_link_path):
            if expected_source:
                exp_norm = self._normalize_path(expected_source)
                try:
                    # Recursive scan: if ANY symlink inside points to us, it's linked
                    for root, dirs, files in os.walk(target_link_path):
                        for name in files + dirs:
                            path = os.path.join(root, name)
                            if os.path.islink(path):
                                real = os.readlink(path)
                                if not os.path.isabs(real):
                                    real = os.path.join(os.path.dirname(path), real)
                                if self._normalize_path(real).startswith(exp_norm):
                                    return {"status": "linked", "type": "partial"}
                except: pass
            
            return {"status": "conflict", "type": "dir"}
             
        return {"status": "conflict", "type": "file"}

    def deploy_with_rules(self, source_path: str, target_link_path: str, rules_json: str = None, 
                          deploy_type: str = 'folder', conflict_policy: str = 'backup') -> bool:
        """
        Deploys using rules (Phase 16) and overrides (Phase 18.15).
        deploy_type: 'folder' (symlink the whole folder) or 'flatten' (symlink files inside).
        rules_json: {"exclude": ["*.txt"], "overrides": {...}}
        """
        import json
        import fnmatch
        
        rules = {}
        if rules_json:
            try:
                rules = json.loads(rules_json)
            except:
                self.logger.error(f"Invalid rules JSON: {rules_json}")
        
        # Determine if we have complex rules that REQUIRE partial deployment (individual file links)
        # Check for non-empty exclusion list or non-empty overrides map
        excludes = rules.get('exclude', [])
        overrides = rules.get('overrides', rules.get('rename', {}))
        has_complex_rules = (isinstance(excludes, list) and len(excludes) > 0) or \
                             (isinstance(overrides, dict) and len(overrides) > 0)
        
        self.logger.info(f"Deploy check: has_complex_rules={has_complex_rules} (excludes={len(excludes)}, overrides={len(overrides)})")
        
        # If 'folder' deploy and NO complex rules, use single subfolder symlink for efficiency
        if deploy_type == 'folder' and not has_complex_rules:
            self.logger.info(f"Switching to Normal Folder Deployment (No rules) for: {source_path}")
            return self.deploy_link(source_path, target_link_path, conflict_policy)
        
        self.logger.info(f"Proceeding with Partial (File-level) Deployment for: {source_path}")
            
        if not os.path.exists(source_path): return False
        
        # Cleanup PREVIOUS links in the CURRENT target_link_path
        if os.path.lexists(target_link_path) and os.path.isdir(target_link_path) and not os.path.islink(target_link_path):
            self.logger.info(f"Cleaning up previous partial deployment links in: {target_link_path}")
            self.cleanup_links_in_target(target_link_path, source_path, recursive=True)
        elif os.path.lexists(target_link_path):
            if not self._handle_conflict(target_link_path, conflict_policy):
                return False

        success = True
        links_to_create = []
        try:
            for root, dirs, files in os.walk(source_path):
                rel_root = os.path.relpath(root, source_path)
                if rel_root == ".": rel_root = ""
                
                # Filter dirs for walk only
                dirs[:] = [d for d in dirs if not self._is_excluded(os.path.join(rel_root, d), rules.get('exclude', []))]
                
                # Process files
                for f in files:
                    f_rel = os.path.join(rel_root, f).replace('\\', '/')
                    if self._is_excluded(f_rel, rules.get('exclude', [])):
                        continue
                    
                    for old, new in rules.get('overrides', rules.get('rename', {})).items():
                        # Match exact file or folder prefix
                        old_norm = old.replace('\\', '/')
                        if f_rel == old_norm or f_rel.startswith(old_norm + "/"):
                            # Replace the renamed/overridden part
                            f_target_rel = f_rel.replace(old_norm, new, 1)
                            # Update target path
                            if deploy_type == 'folder':
                                if os.path.isabs(f_target_rel):
                                    f_target = f_target_rel
                                else:
                                    f_target = os.path.join(target_link_path, f_target_rel)
                            else:
                                # Flatten mode
                                f_target = os.path.join(target_link_path, os.path.basename(f_target_rel))
                            break
                    else:
                        # No overrides matched
                        if deploy_type == 'folder':
                            f_target = os.path.join(target_link_path, f_rel)
                        else:
                            f_target = os.path.join(target_link_path, f)
                    
                    f_source = os.path.join(root, f)
                    links_to_create.append((f_source, f_target))
            
            if not links_to_create:
                return True
                
            # Execute batch deployment in parallel
            self.logger.info(f"Parallel bulk deployment: {len(links_to_create)} files")
            results = self.deploy_links_batch(links_to_create, conflict_policy)
            
            # Re-check for any errors
            for res in results:
                if res['status'] == 'error' and conflict_policy != 'skip':
                    success = False
                         
        except Exception as e:
            self.logger.error(f"Filtered deploy failed: {e}")
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
                    if res['status'] == 'error':
                        self.logger.error(f"Batch link failed: {res['path']} -> {res['msg']}")
                except Exception as exc:
                    pair = future_to_path[future]
                    self.logger.error(f"Worker generated an exception for {pair}: {exc}")
                    results.append({"status": "error", "path": pair[1], "msg": str(exc)})

        self.logger.info(f"Parallel batch ({len(link_pairs)} items) took {time.perf_counter()-t0:.3f}s")
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

    def cleanup_links_in_target(self, target_dir: str, valid_source_root: str, recursive: bool = True):
        """
        Removes ALL symlinks in target_dir that point to valid_source_root (or its children).
        If recursive=True (default), scans subdirectories.
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
        orphan_links = []
        empty_dirs = []
        
        for root_dir in search_roots:
            if not os.path.isdir(root_dir): continue
            
            # Use bottom-up walk to allow cleaning empty folders after unlinking
            for root, dirs, files in os.walk(root_dir, topdown=False):
                for name in files + dirs:
                    path = os.path.join(root, name)
                    if os.path.islink(path):
                        try:
                            # Read link and normalize
                            real = os.readlink(path)
                            if not os.path.isabs(real):
                                real = os.path.join(os.path.dirname(path), real)
                                
                            if self._normalize_path(real).startswith(source_root_norm):
                                orphan_links.append(path)
                        except: pass
                
                # Track empty folders for later cleanup (except the search root itself)
                if root != root_dir:
                    empty_dirs.append(root)
        
        # Phase 2: Parallel deletion using ThreadPoolExecutor
        removed_count = 0
        if orphan_links:
            def _unlink_safe(path):
                try:
                    os.unlink(path)
                    return True
                except:
                    return False
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                results = list(executor.map(_unlink_safe, orphan_links))
                removed_count = sum(results)
        
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



