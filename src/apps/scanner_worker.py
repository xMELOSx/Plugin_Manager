from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
import os
import logging
import json

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

    def set_params(self, path, target_root, storage_root, search_config=None, context="view"):
        self.current_path = path
        self.target_root = target_root
        self.storage_root = storage_root
        self.search_config = search_config
        self.context = context

    @pyqtSlot()
    def run(self):
        try:
            if not self.current_path or not os.path.exists(self.current_path):
                self.results_ready.emit([], self.current_path, self.context)
                self.finished.emit()
                return

            raw_configs = self.db.get_all_folder_configs()
            # Normalize keys to forward slashes for consistent lookup
            folder_configs = {k.replace('\\', '/'): v for k, v in raw_configs.items()}
            
            if self.search_config:
                # 1. Recursive Search Mode
                results = self._recursive_search(folder_configs)
            else:
                # 2. Standard Scan Mode
                results = self._standard_scan(folder_configs)

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
            self._detect_logical_conflicts(results, folder_configs)

            # 4. Sort logic: Categories first, then Packages, then alphabetical
            items_sorted = sorted(results, key=sort_final)
            self.results_ready.emit(items_sorted, self.current_path, self.context)
            
        except Exception as e:
            self.logger.error(f"Worker Error: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self.error.emit(str(e))
        finally:
            self.finished.emit()

    def _standard_scan(self, folder_configs):
        items = self.scanner.scan_directory(self.current_path)
        results = []
        for item in items:
            item_abs_path = os.path.join(self.current_path, item['name'])
            res = self._enrich_item(item, item_abs_path, self.current_path, folder_configs)
            results.append(res)
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
        Detects duplicate display names (local to results) and duplicate deployment targets (global).
        """
        # 1. Global Target Map
        # Map: NormalizedTargetPath -> [RelPath]
        target_map = {}
        for rel_path, cfg in folder_configs.items():
            t_override = cfg.get('target_override')
            if t_override:
                # Resolve potential relative paths to absolute for reliable comparison
                try:
                    norm_t = self.deployer._normalize_path(t_override)
                    if norm_t not in target_map: target_map[norm_t] = []
                    target_map[norm_t].append(rel_path)
                except: continue

        # 2. Local Name Groups (Case-insensitive)
        name_groups = {}
        for r in results:
            d_name = (r['config'].get('display_name') or r['item']['name']).lower()
            if d_name not in name_groups: name_groups[d_name] = []
            name_groups[d_name].append(r)

        # 3. Mark Results
        for r in results:
            # Name Conflict check
            d_name = (r['config'].get('display_name') or r['item']['name']).lower()
            if len(name_groups.get(d_name, [])) > 1:
                r['has_name_conflict'] = True
                r['has_conflict'] = True # Ensure inherited conflict flag is set
                
            # Global Target Conflict check
            t_override = r['config'].get('target_override')
            if t_override:
                norm_t = self.deployer._normalize_path(t_override)
                colliders = target_map.get(norm_t, [])
                # If more than one item in DB points here, or it collides with another result
                if len(colliders) > 1:
                    r['has_target_conflict'] = True
                    r['has_conflict'] = True

    def _enrich_item(self, item, item_abs_path, parent_path, folder_configs):
        # Rel Path for config check (standardize to '/')
        try:
            item_rel = os.path.relpath(item_abs_path, self.storage_root)
            if item_rel == ".": item_rel = ""
            item_rel = item_rel.replace('\\', '/')  # Standardize for DB lookup
        except: item_rel = ""
        
        item_config = folder_configs.get(item_rel, {})
        
        # 1. Determine Item Type (Package vs Category) for UI/logic purposes
        config_type = item_config.get('folder_type', 'auto')
        if config_type == 'auto':
            is_actually_package = self._is_package_auto(item_abs_path)
        else:
            is_actually_package = (config_type == 'package')

        # 2. Link Status - ALWAYS check for all items (reverted from package-only)
        # The item type detection is unreliable for many mod types, so we must check link status for everything.
        target_override = item_config.get('target_override')
        target_link = target_override or os.path.join(self.target_root, item['name'])
        status_info = self.deployer.get_link_status(target_link, expected_source=item_abs_path)
        link_status = status_info.get('status', 'none')
        
        # Phase 28: Sync status to DB if changed (for optimized conflict checks)
        db_status = item_config.get('last_known_status')
        if (item_config or link_status == 'linked') and db_status != link_status:
            try:
                self.db.update_folder_display_config(item_rel, last_known_status=link_status)
            except Exception as e:
                self.logger.warning(f"Failed to sync status for {item_rel}: {e}")

        # 3. Child Status Check (Folders only)
        has_linked = False
        has_conflict = False
        if os.path.isdir(item_abs_path):
            has_linked, has_conflict = self._scan_children_status(item_abs_path, self.target_root, folder_configs)
        
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
        rules_json = item_config.get('deployment_rules')
        is_partial = False
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

        return {
            'item': item,
            'abs_path': item_abs_path,
            'parent_path': parent_path,
            'config': item_config,
            'has_linked': has_linked,
            'has_conflict': has_conflict,
            'link_status': link_status,
            'is_misplaced': is_misplaced,
            'is_partial': is_partial,        # Feature 6: Yellow Border hint
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
            'has_tag_conflict': bool(item_config.get('conflict_tag'))
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
        Optimized: Use in-memory folder_configs cache and trust DB-persisted conflict flags.
        """
        has_linked = False
        has_conflict = False
        
        # Determine the relative path prefix for this folder
        try:
            folder_rel = os.path.relpath(folder_path, self.storage_root).replace('\\', '/')
            if folder_rel == ".": folder_rel = ""
        except:
            folder_rel = ""
        
        # Iterate over folder_configs and filter for direct children only
        for child_rel, child_cfg in folder_configs.items():
            # Skip if not a direct child of this folder
            child_parent = os.path.dirname(child_rel).replace('\\', '/')
            if child_parent != folder_rel:
                continue
            
            # Check link status from DB cache (already updated by TagConflictWorker)
            status = child_cfg.get('last_known_status', 'none')
            if status == 'linked':
                has_linked = True
            elif status == 'conflict':
                has_conflict = True
            
            # Trust persisted has_logical_conflict flag from TagConflictWorker
            if not has_conflict and child_cfg.get('has_logical_conflict', 0):
                has_conflict = True
            
            # Early exit if both found
            if has_linked and has_conflict:
                break
        
        return has_linked, has_conflict
