from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
import os
import logging
import json
import time

class ScannerWorker(QObject):
    results_ready = pyqtSignal(list, str, str) # items_sorted, original_path, context
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, scanner, deployer, db):
        super().__init__()
        self.scanner = scanner
        self.deployer = deployer
        self.db = db
        self.logger = logging.getLogger("ScannerWorker")
        self.current_path = None
        self.target_root = None
        self.storage_root = None
        self.context = "view" # Default context
        
        # Search Params
        self.search_config = None # {query, logic, selected_tags, is_global, non_inheritable_tags}

    def _is_package_auto(self, abs_path):
        """Heuristic: Check if folder contains package-like config files."""
        if not abs_path or not os.path.isdir(abs_path):
            return False
        package_indicators = {'.json', '.ini', '.yaml', '.toml', '.yml'}
        try:
            with os.scandir(abs_path) as it:
                for entry in it:
                    if entry.is_file():
                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext in package_indicators:
                            return True
        except: pass
        return False

    
    def set_db(self, db):
        """Update database reference when app changes."""
        self.db = db

    def set_params(self, path, target_root, storage_root, search_config=None, context="view", app_data=None, target_key=None, app_id=None):
        self.current_path = path
        self.target_root = target_root
        self.storage_root = storage_root
        self.search_config = search_config
        self.context = context
        self.app_data = app_data
        self.target_key = target_key
        # Phase 33: Store App ID to prevent results from different apps bleeding in
        self.app_id = app_id or (app_data or {}).get('id') or ""

    @pyqtSlot()
    def run(self):
        import time
        t_run_start = time.perf_counter()
        try:
            if not self.current_path or not os.path.exists(self.current_path):
                self.results_ready.emit([], self.current_path, self.context)
                self.finished.emit()
                return

            raw_configs = self.db.get_all_folder_configs()
            # Normalize keys to forward slashes for consistent lookup
            folder_configs = {k.replace('\\', '/'): v for k, v in raw_configs.items()}
            
            # Phase 28 Optimization: Pre-group folder configs by parent for O(1) child scan
            self._parent_config_map = {}
            # Phase Hierarchical Filtering: Pre-calculate ancestor paths for favorites and links
            self._favorite_ancestors = set()
            self._linked_ancestors = set()
            
            for rel, cfg in folder_configs.items():
                p_rel = os.path.dirname(rel).replace('\\', '/')
                if p_rel == ".": p_rel = ""
                if p_rel not in self._parent_config_map:
                    self._parent_config_map[p_rel] = []
                self._parent_config_map[p_rel].append((rel, cfg))
                
                # Ancestor tracking
                if cfg.get('is_favorite', 0):
                    parts = rel.split('/')
                    for i in range(len(parts)):
                        ancestor = '/'.join(parts[:i])
                        self._favorite_ancestors.add(ancestor)
                
                if cfg.get('last_known_status') in ('linked', 'partial'):
                    parts = rel.split('/')
                    for i in range(len(parts)):
                        ancestor = '/'.join(parts[:i])
                        self._linked_ancestors.add(ancestor)
            
            if self.search_config:
                # 1. Recursive Search Mode
                t_scan_start = time.perf_counter()
                results = self._recursive_search(folder_configs)
                t_scan_end = time.perf_counter()
            else:
                # 2. Standard Scan Mode
                t_scan_start = time.perf_counter()
                results = self._standard_scan(folder_configs)
                t_scan_end = time.perf_counter()

            # 3. Sort logic: Categories first, then Packages, then alphabetical
            def sort_final(r):
                config_type = r['config'].get('folder_type', 'auto')
                if config_type == 'auto':
                    is_package = self._is_package_auto(r['abs_path'])
                else:
                    is_package = (config_type == 'package')



                
                type_score = 1 if is_package else 0
                return (type_score, r['item']['name'].lower())

            # 3. Post-process results for logical conflicts (names and targets)
            t_detect_start = time.perf_counter()
            self._detect_logical_conflicts(results, folder_configs)
            t_detect_end = time.perf_counter()

            # 4. Sort logic: Categories first, then Packages, then alphabetical
            items_sorted = sorted(results, key=sort_final)
            
            t_worker_end = time.perf_counter()
            self.logger.debug(f"[WorkerProfile] context={self.context} total={t_worker_end-t_run_start:.3f}s "
                             f"(Scan:{t_scan_end-t_scan_start:.3f}s / "
                             f"Detect:{t_detect_end-t_detect_start:.3f}s / "
                             f"Sort:{t_worker_end-t_detect_end:.3f}s)")
                             
            self.results_ready.emit(items_sorted, self.current_path, self.context)
            
        except Exception as e:
            self.logger.error(f"Worker Error: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self.error.emit(str(e))
        finally:
            self.finished.emit()

    def _standard_scan(self, folder_configs):
        import time
        t_en_total = 0
        t_en_link = 0
        t_en_child = 0
        t_en_auto = 0
        
        items = self.scanner.scan_directory(self.current_path)
        results = []
        for item in items:
            t_s = time.perf_counter()
            item_abs_path = os.path.join(self.current_path, item['name'])
            res = self._enrich_item(item, item_abs_path, self.current_path, folder_configs)
            results.append(res)
            
            t_en_total += (time.perf_counter() - t_s)
            t_en_link += res.get('_profile_link', 0)
            t_en_child += res.get('_profile_child', 0)
            t_en_auto += res.get('_profile_auto', 0)
            
        self.logger.debug(f"[WorkerProfile] _standard_scan items={len(items)} "
                         f"Total:{t_en_total:.3f}s (Link:{t_en_link:.3f}s / Child:{t_en_child:.3f}s / Auto:{t_en_auto:.3f}s)")
        # Clean up optimization map after use
        if hasattr(self, '_parent_config_map'):
            del self._parent_config_map
        if hasattr(self, '_favorite_ancestors'):
            del self._favorite_ancestors
        if hasattr(self, '_linked_ancestors'):
            del self._linked_ancestors
        return results

    def _recursive_search(self, folder_configs):
        query = self.search_config.get('query', '').lower()
        terms = [t for t in query.split() if t]
        selected_tags = self.search_config.get('selected_tags', set())
        logic = self.search_config.get('logic', 'or')
        non_inheritable = self.search_config.get('non_inheritable_tags', set())
        
        results = []
        
        # Initial tags for the start point
        start_inherited = self._get_inherited_tags_static(self.current_path, self.storage_root, folder_configs, non_inheritable)
        
        stack = [(self.current_path, start_inherited)]
        
        while stack:
            curr_path, inherited = stack.pop()
            if not os.path.isdir(curr_path): continue
            
            try:
                with os.scandir(curr_path) as it:
                    for entry in it:
                        if not entry.is_dir(): continue
                        
                        item_abs_path = entry.path
                        try:
                            item_rel = os.path.relpath(item_abs_path, self.storage_root)
                            if item_rel == ".": item_rel = ""
                            item_rel = item_rel.replace('\\', '/')  # Standardize for DB lookup
                        except: continue
                        
                        config = folder_configs.get(item_rel, {})

                        
                        # Inheritance Logic
                        can_inherit = config.get('inherit_tags', 1) != 0
                        own_tags = {t.strip().lower() for t in (config.get('tags') or '').split(',') if t.strip()}
                        
                        # Filtered list of tags that CAN be passed down
                        # (Only own_tags that are NOT in non_inheritable + inherited tags if allowed)
                        potential_to_pass = set()
                        if can_inherit:
                            potential_to_pass.update(inherited) # Pass down parent tags
                        
                        # Add own tags (Note: Tag level non-inheritable check is usually for the TAG itself,
                        # but here we follow parent implementation which checks if a tag is allowed to be inherited at all globally)
                        filtered_own = {t for t in own_tags if t not in non_inheritable}
                        potential_to_pass.update(filtered_own)

                        # Match Logic
                        all_tags_for_match = own_tags | inherited
                        
                        # Tag Match
                        tag_match = True
                        if selected_tags:
                            if logic == 'and':
                                tag_match = selected_tags.issubset(all_tags_for_match)
                            else:
                                tag_match = not selected_tags.isdisjoint(all_tags_for_match)
                        
                        # Text Match
                        text_match = True
                        if terms:
                            # Use display name if available
                            display_name = (config.get('display_name') or entry.name).lower()
                            if logic == 'and':
                                text_match = all(t in display_name for t in terms)
                            else:
                                text_match = any(t in display_name for t in terms)
                        
                        config_type = config.get('folder_type', 'auto')
                        if config_type == 'auto':
                            is_pkg = self._is_package_auto(item_abs_path)
                        else:
                            is_pkg = (config_type == 'package')

                            
                        if tag_match and text_match:
                            item_dict = {'name': entry.name, 'is_dir': True}
                            results.append(self._enrich_item(item_dict, item_abs_path, curr_path, folder_configs))
                        
                        # Recurse if not a package (Filter Nested Packages)
                        if not is_pkg:
                            stack.append((item_abs_path, potential_to_pass))
                            
            except PermissionError:
                continue
            except Exception as e:
                self.logger.warning(f"Error scanning {curr_path}: {e}")
                
        return results

    def _detect_logical_conflicts(self, results, folder_configs):
        """
        DISABLED: This method was detecting duplicate deployment targets (global).
        NOTE: This feature is intentionally disabled per user request.
        """
        # =====================================================================
        # DISABLED: [競合] label feature was not desired.
        # The code below has been commented out to prevent the 
        # "has_target_conflict" flag from ever being set to True.
        # =====================================================================
        pass  # No-op function - feature disabled
        # 1. Global Target Map
        # Map: NormalizedTargetPath -> [RelPath]
        # target_map = {}
        # for rel_path, cfg in folder_configs.items():
        #     t_override = cfg.get('target_override')
        #     if t_override:
        #         try:
        #             norm_t = self.deployer._normalize_path(t_override)
        #             if norm_t not in target_map: target_map[norm_t] = []
        #             target_map[norm_t].append(rel_path)
        #         except: continue
        #
        # # 2. Mark Results with Target Conflict only
        # for r in results:
        #     t_override = r['config'].get('target_override')
        #     if t_override:
        #         norm_t = self.deployer._normalize_path(t_override)
        #         colliders = target_map.get(norm_t, [])
        #         if len(colliders) > 1:
        #             r['has_target_conflict'] = True
        #             r['has_conflict'] = True

    def _enrich_item(self, item, item_abs_path, parent_path, folder_configs):
        # Rel Path for config check (standardize to '/')
        item_rel = ""
        try:
            raw_rel = os.path.relpath(item_abs_path, self.storage_root)
            if raw_rel == ".": raw_rel = ""
            item_rel = raw_rel.replace('\\', '/')  # Standard format
        except: pass
        
        # Phase 36 Fix: Case-Insensitive Config Lookup
        # Windows file system logic: 'Foo' should match config for 'foo'
        # We need to find the correct key in folder_configs that matches item_rel (case-insensitive)
        item_config = folder_configs.get(item_rel)
        if item_config is None:
            # Fallback: linear search for case check (only if direct hit fails)
            target_lower = item_rel.lower()
            for key in folder_configs:
                if key.lower() == target_lower:
                    item_config = folder_configs[key]
                    break
        
        if item_config is None:
            item_config = {}
            
        # Phase 42 Fix: Explicitly preserve metadata from config to item
        # This ensures UI receives the persisted values even if scanner didn't populate them from file system
        if 'url_list' in item_config: item['url_list'] = item_config['url_list']
        if 'is_favorite' in item_config: item['is_favorite'] = item_config['is_favorite']
        if 'score' in item_config: item['score'] = item_config['score']
        if 'tags' in item_config: item['tags'] = item_config['tags']
        if 'manual_preview_path' in item_config: item['manual_preview_path'] = item_config['manual_preview_path']
        item['folder_type'] = item_config.get('folder_type', 'auto') # Carry this over too
        
        # 1. Determine Item Type (Package vs Category) for UI/logic purposes
        t_auto_start = time.perf_counter()
        config_type = item_config.get('folder_type', 'auto')
        if config_type == 'auto':
            is_actually_package = self._is_package_auto(item_abs_path)
        else:
            is_actually_package = (config_type == 'package')
        t_auto_end = time.perf_counter()

        # 2. Link Status - Hierarchical Rule Resolution
        t_link_start = time.perf_counter()
        target_override = item_config.get('target_override')
        
        # Phase 35: Standardized target path calculation (matches ItemCard logic)
        app_deploy_default = (self.app_data or {}).get('deployment_type', 'folder')
        deploy_rule = item_config.get('deploy_rule') or item_config.get('deploy_type') or app_deploy_default
        if deploy_rule == 'flatten': deploy_rule = 'files'

        # STRICT TARGET LOGIC:
        # 1. Use Item's 'target_override' if set.
        # 2. If not, check PARENT directories for 'target_override' (Inheritance).
        # 3. Use Primary Target Root (Target A) defined in App Settings as fallback.
        
        primary_target_root = self.app_data.get('target_root')
        scan_base = primary_target_root if primary_target_root else self.target_root
        
        # Logic to determine effective target root and relative path for deployment
        effective_target_base = scan_base
        effective_rel_path = item_rel
        
        # Helper to resolve actual target path from Config
        def resolve_target_from_config(cfg, item_name_for_fallback=None):
            if not cfg: return None
            
            # 1. New Schema: Explicit Selection
            selection = cfg.get('target_selection')
            if selection:
                if selection == 'primary':
                    return self.app_data.get('target_root')
                elif selection == 'secondary':
                    return self.app_data.get('target_root_2')
                elif selection == 'tertiary':
                    return self.app_data.get('target_root_3')
                elif selection == 'custom':
                    return cfg.get('target_override')
            
            # 2. Legacy Fallback: Infer from 'target_override' path matching
            # This handles old DBs or "Garbage Value" cleanup dynamically
            raw_override = cfg.get('target_override')
            if raw_override:
                # Normalization for dynamic check
                ov_norm = os.path.normpath(raw_override).lower() if os.name == 'nt' else os.path.normpath(raw_override)
                targets = {
                    'primary': self.app_data.get('target_root'),
                    'secondary': self.app_data.get('target_root_2'),
                    'tertiary': self.app_data.get('target_root_3')
                }
                for key, val in targets.items():
                    if val:
                        val_norm = os.path.normpath(val).lower() if os.name == 'nt' else os.path.normpath(val)
                        if ov_norm == val_norm:
                            return val # Dynamic Match!
                
                # No dynamic match -> Treat as Custom
                return raw_override
            
            return None

        # 1. Resolve Target Base
        # Check Item Level
        item_target_base = resolve_target_from_config(item_config)
        
        # Check Inheritance if not set on item
        ancestor_override = None
        ancestor_rel_path = ""
        
        if not item_target_base:
             # Walk up from parent_rel
            parent_rel = os.path.dirname(item_rel)
            curr = parent_rel
            while curr:
                if curr == "" or curr == ".": break
                
                # Case-insensitive lookup
                p_cfg = folder_configs.get(curr)
                if not p_cfg:
                    curr_lower = curr.lower()
                    for k in folder_configs:
                        if k.lower() == curr_lower:
                            p_cfg = folder_configs[k]
                            break
                            
                inherited_base = resolve_target_from_config(p_cfg)
                if inherited_base:
                    # Found ancestor with explicit target!
                    item_target_base = inherited_base
                    ancestor_override = inherited_base # For logging
                    ancestor_rel_path = curr
                    
                    # Calculate remaining path
                    try:
                        remaining_subpath = os.path.relpath(item_rel, curr).replace('\\', '/')
                    except:
                        remaining_subpath = item['name']
                    
                    # Adjust item_rel effectively for the final join
                    # But wait, logic below expects 'scan_base' + 'item_rel' OR 'target_link'
                    # We need to set 'scan_base' to the resolved root, and modify how we join.
                    break
                
                curr = os.path.dirname(curr)

        # Apply Resolved Base
        if item_target_base:
             scan_base = item_target_base # The resolved target becomes the new Base Root
             
             if ancestor_override:
                  # Inherited: Use the relative path from the ancestor
                  # Example: Item "A/B", Ancestor "A"->Override "T". Result "T/B".
                  effective_rel_to_base = remaining_subpath
                  
                  # Logging for debug
                  scan_base_debug = f"[Inherited from {ancestor_rel_path}] {ancestor_override}"
             else:
                  # Direct Override: The item IS the child of the base.
                  # Example: Item "A"->Override "T". Result "T/A".
                  # UNLESS we are in 'files' mode? 
                  # For 'folder' mode: T/A.
                  # For 'files' mode: T/A (if flattening into T/A) or T (if flattening into T directly)?
                  # App standard is: Roots contain the Item Folders.
                  effective_rel_to_base = item['name']
                  scan_base_debug = f"[Direct Override] {item_target_base}"

             # Construct final link based on rule
             if deploy_rule == 'files':
                 # Flatten: usually creates the folder anyway in LinkMaster?
                 # Or does it link individual files? 
                 # If 'flatten' (files), we assume the target FOLDER is scan_base/item_name
                 # And we put files inside.
                 target_link = os.path.join(scan_base, effective_rel_to_base)
                 
             elif deploy_rule == 'tree': 
                 target_link = os.path.join(scan_base, effective_rel_to_base)
                 
             else: # folder (default)
                 target_link = os.path.join(scan_base, effective_rel_to_base)
                 
        else:
             # Standard default logic (Primary Root)
             # Use original relative path from storage root
             if deploy_rule == 'files':
                 target_link = os.path.join(scan_base, item['name'])
             elif deploy_rule == 'tree':
                  rules_json = item_config.get('deployment_rules')
                  skip_val = 0
                  if rules_json:
                     try:
                         ro = json.loads(rules_json)
                         skip_val = int(ro.get('skip_levels', 0))
                     except: pass
                  
                  parts = item_rel.split('/')
                  if len(parts) > skip_val:
                     mirrored = "/".join(parts[skip_val:])
                     target_link = os.path.join(scan_base, mirrored)
                  else:
                     target_link = scan_base
             else:
                 target_link = os.path.join(scan_base, item_rel)

            
        # DEBUG: Trace target calculation for specific item
        # if "15Folder" in item_rel: 
        
        # Phase 42: Files mode special handling
        # In files mode, individual files are placed directly in scan_base (not in a folder)
        # We need to check if any source file exists in the target
        if deploy_rule == 'files' and os.path.isdir(item_abs_path):
            # Check if at least one file from source exists in scan_base
            files_found = 0
            files_total = 0
            try:
                for f in os.listdir(item_abs_path):
                    f_path = os.path.join(item_abs_path, f)
                    if os.path.isfile(f_path):
                        files_total += 1
                        target_file = os.path.join(scan_base, f)
                        if os.path.exists(target_file) or os.path.islink(target_file):
                            files_found += 1
            except:
                pass
            
            if files_found > 0 and files_found >= files_total:
                link_status = 'linked'
            elif files_found > 0:
                link_status = 'partial'
            else:
                link_status = 'none'
            status_info = {'status': link_status}
        else:
            status_info = self.deployer.get_link_status(target_link, expected_source=item_abs_path)
            link_status = status_info.get('status', 'none')
        
        # Phase 28: Sync status to DB if changed (for optimized conflict checks)
        db_status = item_config.get('last_known_status')
        
        # DEBUG LOGGING for analysis
        if link_status == 'none' and db_status == 'linked':
             self.logger.warning(f"[SCAN DEBUG] Lost Link: {item_rel}")
             self.logger.warning(f"  > Override: {target_override}")
             self.logger.warning(f"  > Rule: {deploy_rule}")
             self.logger.warning(f"  > ScanBase: {scan_base}")
             self.logger.warning(f"  > Looking At: {target_link}")
             self.logger.warning(f"  > Exists?: {os.path.exists(target_link)}")
             self.logger.warning(f"  > Symlink?: {os.path.islink(target_link)}")

        t_link_end = time.perf_counter()
        
        # FIX Step 3784: Always trust this scan result because it's based on STATIC properties.
        # We are no longer shifting targets dynamically, so "none" means "not in Primary/Override".
        if (item_config or link_status != 'none') and db_status != link_status:
             try:
                 # If existing is 'conflict', be careful about overwriting it unless current is definitive
                 if db_status == 'conflict' and link_status not in ('linked', 'partial'):
                     pass # Keep conflict if new is just 'none' or 'misplaced'
                 else:
                     self.db.update_folder_display_config(item_rel, last_known_status=link_status)
             except Exception as e:
                 self.logger.warning(f"Failed to sync status for {item_rel}: {e}")

        # 3. Child Status Check (Folders only)
        has_linked = item_rel in getattr(self, '_linked_ancestors', set())
        has_favorite = item_rel in getattr(self, '_favorite_ancestors', set())
        has_conflict = False
        t_child_start = time.perf_counter()
        if os.path.isdir(item_abs_path):
            # Scan children for physical status and hierarchical conflicts
            h_l, h_c, h_u, h_p, h_ic = self._scan_children_status(item_abs_path, self.target_root, folder_configs)
            has_linked = has_linked or h_l
            has_conflict = h_c
        else:
            h_u = h_p = h_ic = False
        t_child_end = time.perf_counter()
        
        # 4. Misplaced Detection (Phase 18.11 Enhanced)
        is_misplaced = False
        comp_rel = item_rel.replace('\\', '/')
        depth = comp_rel.count('/')
        
        # If it's NOT a package yet but in Category area (Level 1/2), check for json/ini
        if depth <= 1 and not is_actually_package:
            # Heuristic: If it contains package-like config files, it might be a misplaced package
            package_indicators = {'.json', '.ini', '.yaml', '.toml', '.yml'}
            try:
                if os.path.isdir(item_abs_path):
                    with os.scandir(item_abs_path) as it:
                        for entry in it:
                            if entry.is_file():
                                ext = os.path.splitext(entry.name)[1].lower()
                                if ext in package_indicators:
                                    is_misplaced = True
                                    break
            except: pass

        # Partial Deployment Check (Feature 6)
        # Determine if this item has file-level exclusions or overrides
        is_partial = False
        if deploy_rule == 'tree':
            # Phase 2.5: Tree mode always assumes a full mirror and IGNORES custom rules for 'partial' status.
            is_partial = False
        else:
            rules_json = item_config.get('deployment_rules')
            if rules_json:
                try:
                    rules = json.loads(rules_json)
                    if rules.get('exclude'):
                        is_partial = True
                    if rules.get('rename'):
                        # Check if any rename is internal (within the folder)
                        is_partial = True
                except: pass

        # Phase 28: Use persistent conflict flags from DB/Config
        # These are calculated by TagConflictWorker and persisted in the DB.
        db_logical = item_config.get('has_logical_conflict', 0)
        has_logical_conflict = (db_logical == 1) or (link_status == 'conflict')

        # Phase X: Use persistent library alt version flags from DB/Config
        db_alt = item_config.get('is_library_alt_version', 0)
        is_library_alt_version = (db_alt == 1) and (link_status != 'linked')

        t_end = time.perf_counter()
        return {
            'item': item,
            'abs_path': item_abs_path,
            'parent_path': parent_path,
            'config': item_config,
            'has_linked': has_linked,
            'has_favorite': has_favorite, # Add explicit flag
            'has_conflict': has_conflict,
            'link_status': link_status,
            'is_misplaced': is_misplaced,
            'is_partial': is_partial or h_p,        # Feature 6: Yellow Border hint
            'has_unlinked_children': h_u,
            'has_category_conflict': h_ic,
            'is_package': is_actually_package,  # Added for root package display support
            'is_linked': (link_status == 'linked'),  # Convenience flag for counting
            'has_name_conflict': False, # Default
            'has_target_conflict': False, # Default
            'has_logical_conflict': has_logical_conflict, # Consistently use has_logical_conflict (from tag logic or physical conflict)
            'is_library_alt_version': is_library_alt_version, # Phase X: Yellow-green mark
            'thumbnail': item.get('image_rel_path'), # Relay auto-detected thumbnail
            'is_favorite': item_config.get('is_favorite', 0),  # Favorite flag
            'score': item_config.get('score', 0),  # Favorite score
            'url_list': item_config.get('url_list', '[]'),  # URL list JSON
            'conflict_tag': item_config.get('conflict_tag'),
            'conflict_scope': item_config.get('conflict_scope'),
            'has_tag_conflict': bool(item_config.get('conflict_tag')),
            'is_library': item_config.get('is_library', 0),  # Phase 30: Library flag
            'lib_name': item_config.get('lib_name', ''),     # Phase 30: Library name
            '_profile_link': t_link_end - t_link_start,
            '_profile_child': t_child_end - t_child_start,
            '_profile_auto': t_auto_end - t_auto_start
        }

    def _get_inherited_tags_static(self, folder_path, storage_root, folder_configs, non_inheritable):
        tags = set()
        current = folder_path
        while True:
            try:
                if os.path.abspath(current) == os.path.abspath(storage_root):
                    rel = ""
                else:
                    rel = os.path.relpath(current, storage_root)
                    if rel == ".": rel = ""
                
                config = folder_configs.get(rel, {})
                t_str = config.get('tags', '')
                if t_str:
                    for t in t_str.split(','):
                        t = t.strip().lower()
                        if t and t not in non_inheritable:
                            tags.add(t)
                
                if not rel: break
                if config.get('inherit_tags', 1) == 0: break
                
                parent = os.path.dirname(current)
                if parent == current: break
                current = parent
            except:
                break
        return tags

    def _scan_children_status(self, folder_path: str, target_root: str, folder_configs: dict) -> tuple:
        """
        Hyper-Optimized: Use pre-calculated _parent_config_map for O(1) lookup.
        """
        has_linked = False
        has_conflict = False
        has_unlinked = False
        has_int_conf = False
        child_tags = set()
        child_libs = set()
        
        # Determine the relative path of THIS folder
        try:
            folder_rel = os.path.relpath(folder_path, self.storage_root).replace('\\', '/')
            if folder_rel == ".": folder_rel = ""
        except:
            return False, False, False, False, False
        
        # Phase 28: Use pre-grouped child configs instead of scanning ALL configs
        children = getattr(self, '_parent_config_map', {}).get(folder_rel, [])
        
        for child_rel, child_cfg in children:
            # Check link status from DB cache
            status = child_cfg.get('last_known_status', 'none')
            if status == 'linked':
                has_linked = True
            elif status == 'conflict':
                has_conflict = True
                has_unlinked = True
            else:
                has_unlinked = True
            
            # Trust persisted has_logical_conflict flag
            if child_cfg.get('has_logical_conflict', 0):
                has_conflict = True
                has_unlinked = True
            
            # Phase 35: Internal Conflict Check (Warning Icon)
            ctag = child_cfg.get('conflict_tag')
            if ctag:
                if ctag in child_tags:
                    has_int_conf = True
                child_tags.add(ctag)
                
                # Check for External Tag conflict if internal not found yet
                if not has_int_conf and hasattr(self, 'parent'):
                     # We can't easily call self.parent._check_tag_conflict from here (thread safety)
                     # But we can assume it will be picked up by UI refresh as a secondary pass
                     pass

            lib_name = child_cfg.get('library_name') or child_cfg.get('lib_name')
            if lib_name:
                if lib_name in child_libs:
                    has_int_conf = True
                child_libs.add(lib_name)
        
        return has_linked, has_conflict, has_unlinked, False, has_int_conf
