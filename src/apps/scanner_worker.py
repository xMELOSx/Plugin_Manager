from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
import os
import logging
import json
import time

class ScannerWorker(QObject):
    results_ready = pyqtSignal(list, str, str, str, int) # items_sorted, original_path, context, app_id, gen_id
    finished = pyqtSignal()
    error = pyqtSignal(str, int) # error_msg, gen_id

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
        self.app_data = None # Phase 43: Store app data snapshot
        self.app_id = ""
        self.generation_id = 0

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

    def set_params(self, path, target_root, storage_root, search_config=None, context="view", app_data=None, target_key=None, app_id=None, generation_id=0):
        self.current_path = path
        self.target_root = target_root
        self.storage_root = storage_root
        self.search_config = search_config
        self.context = context
        self.app_data = app_data
        self.target_key = target_key
        # Phase 33/43: Store App ID and Generation ID to prevent results bleeding
        self.app_id = app_id or (app_data or {}).get('id') or ""
        self.generation_id = generation_id

    @pyqtSlot()
    def run(self):
        import time
        t_run_start = time.perf_counter()
        
        # Phase 43: Snapshot parameters at the start to prevent mid-scan corruption from app switching
        sn_path = self.current_path
        sn_target_root = self.target_root
        sn_storage_root = self.storage_root
        sn_search_config = self.search_config
        sn_context = self.context
        sn_app_data = self.app_data
        sn_target_key = self.target_key
        sn_app_id = self.app_id
        sn_gen_id = self.generation_id
        sn_db = self.db # IMPORTANT: Capture the DB instance being used for this specific scan
        
        try:
            if not sn_path or not os.path.exists(sn_path):
                self.results_ready.emit([], str(sn_path), sn_context, str(sn_app_id), sn_gen_id)
                self.finished.emit()
                return

            raw_configs = sn_db.get_all_folder_configs()
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
            
            if sn_search_config:
                # 1. Recursive Search Mode
                t_scan_start = time.perf_counter()
                results = self._recursive_search_sn(sn_path, sn_storage_root, sn_search_config, folder_configs)
                t_scan_end = time.perf_counter()
            else:
                # 2. Standard Scan Mode
                t_scan_start = time.perf_counter()
                results = self._standard_scan_sn(sn_path, sn_storage_root, sn_target_root, sn_app_data, folder_configs, sn_db)
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

            # 4. Post-process results for logical conflicts (names and targets)
            t_detect_start = time.perf_counter()
            self._detect_logical_conflicts(results, folder_configs)
            t_detect_end = time.perf_counter()

            # 5. Final Sort
            items_sorted = sorted(results, key=sort_final)
            
            t_worker_end = time.perf_counter()
            self.logger.debug(f"[WorkerProfile] app={sn_app_id} gen={sn_gen_id} context={sn_context} total={t_worker_end-t_run_start:.3f}s "
                             f"(Scan:{t_scan_end-t_scan_start:.3f}s / "
                             f"Detect:{t_detect_end-t_detect_start:.3f}s / "
                             f"Sort:{t_worker_end-t_detect_end:.3f}s)")
                             
            self.results_ready.emit(items_sorted, str(sn_path), sn_context, str(sn_app_id), sn_gen_id)
            
        except Exception as e:
            self.logger.error(f"Worker Error: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self.error.emit(str(e), sn_gen_id)
        finally:
            if hasattr(self, '_parent_config_map'): del self._parent_config_map
            if hasattr(self, '_favorite_ancestors'): del self._favorite_ancestors
            if hasattr(self, '_linked_ancestors'): del self._linked_ancestors
            self.finished.emit()

    def _standard_scan_sn(self, sn_path, sn_storage_root, sn_target_root, sn_app_data, folder_configs, sn_db):
        items = self.scanner.scan_directory(sn_path)
        results = []
        for item in items:
            item_abs_path = os.path.join(sn_path, item['name'])
            res = self._enrich_item_sn(item, item_abs_path, sn_path, sn_storage_root, sn_target_root, sn_app_data, folder_configs, sn_db)
            results.append(res)
        return results

    def _recursive_search_sn(self, sn_path, sn_storage_root, sn_search_config, folder_configs):
        query = sn_search_config.get('query', '').lower()
        terms = [t for t in query.split() if t]
        selected_tags = sn_search_config.get('selected_tags', set())
        logic = sn_search_config.get('logic', 'or')
        non_inheritable = sn_search_config.get('non_inheritable_tags', set())
        
        results = []
        start_inherited = self._get_inherited_tags_static(sn_path, sn_storage_root, folder_configs, non_inheritable)
        stack = [(sn_path, start_inherited)]
        
        while stack:
            curr_path, inherited = stack.pop()
            if not os.path.isdir(curr_path): continue
            
            try:
                with os.scandir(curr_path) as it:
                    for entry in it:
                        if not entry.is_dir(): continue
                        item_abs_path = entry.path
                        try:
                            item_rel = os.path.relpath(item_abs_path, sn_storage_root).replace('\\', '/')
                            if item_rel == ".": item_rel = ""
                        except: continue
                        
                        config = folder_configs.get(item_rel, {})
                        can_inherit = config.get('inherit_tags', 1) != 0
                        own_tags = {t.strip().lower() for t in (config.get('tags') or '').split(',') if t.strip()}
                        
                        potential_to_pass = set()
                        if can_inherit: potential_to_pass.update(inherited)
                        filtered_own = {t for t in own_tags if t not in non_inheritable}
                        potential_to_pass.update(filtered_own)

                        all_tags_for_match = own_tags | inherited
                        tag_match = True
                        if selected_tags:
                            if logic == 'and': tag_match = selected_tags.issubset(all_tags_for_match)
                            else: tag_match = not selected_tags.isdisjoint(all_tags_for_match)
                        
                        text_match = True
                        if terms:
                            display_name = (config.get('display_name') or entry.name).lower()
                            if logic == 'and': text_match = all(t in display_name for t in terms)
                            else: text_match = any(t in display_name for t in terms)
                        
                        if tag_match and text_match:
                            config_type = config.get('folder_type', 'auto')
                            is_pkg = self._is_package_auto(item_abs_path) if config_type == 'auto' else (config_type == 'package')
                            results.append({
                                'item': {'name': entry.name},
                                'abs_path': item_abs_path,
                                'is_package': is_pkg,
                                'config': config,
                                'score': 0,
                                'link_status': 'none'
                            })
                        stack.append((item_abs_path, potential_to_pass))
            except: pass
        return results

    def _detect_logical_conflicts(self, results, folder_configs):
        pass  # Feature disabled per user request

    def _enrich_item_sn(self, item, item_abs_path, parent_path, sn_storage_root, sn_target_root, sn_app_data, folder_configs, sn_db):
        item_rel = ""
        try:
            raw_rel = os.path.relpath(item_abs_path, sn_storage_root)
            item_rel = raw_rel.replace('\\', '/') if raw_rel != "." else ""
        except: pass
        
        item_config = folder_configs.get(item_rel)
        if item_config is None:
            target_lower = item_rel.lower()
            for key in folder_configs:
                if key.lower() == target_lower:
                    item_config = folder_configs[key]
                    break
        if item_config is None: item_config = {}
            
        if 'url_list' in item_config: item['url_list'] = item_config['url_list']
        if 'is_favorite' in item_config: item['is_favorite'] = item_config['is_favorite']
        if 'score' in item_config: item['score'] = item_config['score']
        if 'tags' in item_config: item['tags'] = item_config['tags']
        if 'manual_preview_path' in item_config: item['manual_preview_path'] = item_config['manual_preview_path']
        item['folder_type'] = item_config.get('folder_type', 'auto')
        
        config_type = item_config.get('folder_type', 'auto')
        is_actually_package = self._is_package_auto(item_abs_path) if config_type == 'auto' else (config_type == 'package')

        app_deploy_default = (sn_app_data or {}).get('deployment_type', 'folder')
        deploy_rule = item_config.get('deploy_rule') or item_config.get('deploy_type') or app_deploy_default
        if deploy_rule == 'flatten': deploy_rule = 'files'
        
        primary_target_root = sn_app_data.get('target_root')
        scan_base = primary_target_root if primary_target_root else sn_target_root
        
        def resolve_target_from_config(cfg):
            if not cfg: return None
            selection = cfg.get('target_selection')
            if selection:
                if selection == 'primary': return sn_app_data.get('target_root')
                elif selection == 'secondary': return sn_app_data.get('target_root_2')
                elif selection == 'tertiary': return sn_app_data.get('target_root_3')
                elif selection == 'custom': return cfg.get('target_override')
            return cfg.get('target_override')

        effective_target_base = resolve_target_from_config(item_config)
        if not effective_target_base:
            curr = os.path.dirname(item_rel)
            while curr and curr not in ("", "."):
                p_cfg = folder_configs.get(curr)
                if not p_cfg:
                    curr_lower = curr.lower()
                    for k in folder_configs:
                        if k.lower() == curr_lower:
                            p_cfg = folder_configs[k]
                            break
                inherited_base = resolve_target_from_config(p_cfg)
                if inherited_base:
                    effective_target_base = inherited_base
                    break
                curr = os.path.dirname(curr)
        
        if not effective_target_base: effective_target_base = scan_base
        
        check_path = effective_target_base if deploy_rule == 'files' else os.path.join(effective_target_base, item['name'])
        status_res = self.deployer.get_link_status(check_path, expected_source=item_abs_path, deploy_rule=deploy_rule)
        
        # 3. Child Status Check (Folders only) - Restored for Phase 4 markers
        has_linked_children = False
        has_child_conflict = False
        has_unlinked_children = False
        has_cat_conflict = False
        if os.path.isdir(item_abs_path):
            h_l, h_c, h_u, h_p, h_ic = self._scan_children_status_sn(item_abs_path, sn_storage_root, folder_configs)
            has_linked_children = h_l
            has_child_conflict = h_c
            has_unlinked_children = h_u
            has_cat_conflict = h_ic

        return {
            'item': item,
            'abs_path': item_abs_path,
            'is_package': is_actually_package,
            'config': item_config,
            'link_status': status_res.get('status', 'none'),
            'has_linked': status_res.get('status') in ('linked', 'partial'),
            'has_unlinked': status_res.get('status') == 'none',
            'is_partial': status_res.get('status') == 'partial',
            'has_conflict': status_res.get('status') == 'conflict' or has_child_conflict,
            'is_misplaced': status_res.get('status') == 'misplaced',
            'has_favorite': self._favorite_ancestors and item_rel in self._favorite_ancestors,
            'has_linked_children': has_linked_children or (self._linked_ancestors and item_rel in self._linked_ancestors),
            'has_unlinked_children': has_unlinked_children,
            'has_category_conflict': has_cat_conflict
        }

    def _get_inherited_tags_static(self, folder_path, storage_root, folder_configs, non_inheritable):
        tags = set()
        current = folder_path
        while True:
            try:
                if os.path.abspath(current) == os.path.abspath(storage_root): rel = ""
                else:
                    rel = os.path.relpath(current, storage_root).replace('\\', '/')
                    if rel == ".": rel = ""
                config = folder_configs.get(rel, {})
                t_str = config.get('tags', '')
                if t_str:
                    for t in t_str.split(','):
                        t = t.strip().lower()
                        if t and t not in non_inheritable: tags.add(t)
                if not rel or config.get('inherit_tags', 1) == 0: break
                parent = os.path.dirname(current)
                if parent == current: break
                current = parent
            except: break
        return tags

    def _scan_children_status_sn(self, folder_path, sn_storage_root, folder_configs):
        has_linked = has_conflict = has_unlinked = has_int_conf = False
        child_tags = set()
        child_libs = set()
        try:
            folder_rel = os.path.relpath(folder_path, sn_storage_root).replace('\\', '/')
            if folder_rel == ".": folder_rel = ""
        except: return False, False, False, False, False
        children = getattr(self, '_parent_config_map', {}).get(folder_rel, [])
        for child_rel, child_cfg in children:
            status = child_cfg.get('last_known_status', 'none')
            if status == 'linked': has_linked = True
            elif status == 'conflict': has_conflict = has_unlinked = True
            else: has_unlinked = True
            if child_cfg.get('has_logical_conflict', 0): has_conflict = has_unlinked = True
            ctag = child_cfg.get('conflict_tag')
            if ctag:
                if ctag in child_tags: has_int_conf = True
                child_tags.add(ctag)
            lib_name = child_cfg.get('library_name') or child_cfg.get('lib_name')
            if lib_name:
                if lib_name in child_libs: has_int_conf = True
                child_libs.add(lib_name)
        return has_linked, has_conflict, has_unlinked, False, has_int_conf
