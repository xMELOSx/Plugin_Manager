from PyQt6.QtCore import QObject, pyqtSignal
import os
import logging
from src.core.link_master.database import LinkMasterDB

logger = logging.getLogger("TagConflictWorker")

class TagConflictWorker(QObject):
    """
    Background worker to calculate Tag Conflicts to avoid UI freeze.
    Fetches DB configs and builds an active tag map.
    Phase 28.5: Uses isolated DB connection to avoid Threading crashes.
    """
    finished = pyqtSignal(object) # returns dict { 'active_tags_map': ..., 'all_configs': ... }
    
    def __init__(self, db_path, storage_root, target_root=None):
        super().__init__()
        self.db_path = db_path
        self.storage_root = storage_root
        self.target_root = target_root
        
    def run(self):
        if not self.storage_root:
            logger.debug("TagConflictWorker: storage_root is None, skipping run.")
            self.finished.emit(None)
            return

        import time
        start_t = time.time()
        try:
            # Create ISOLATED DB instance for this thread
            local_db = LinkMasterDB(db_path=self.db_path)
            
            # 1. Build Index of Active States
            all_configs = local_db.get_all_folder_configs()
            active_tags_map = {}
            active_library_names = set()
            active_targets_map = {} # norm_target -> rel_path
            tag_conflicted_categories = set()
            
            # Step 1: Collect Active State (Linked items) and Library Names
            linked_count = 0
            for p, cfg in all_configs.items():
                if not p: continue

                # Skip trash items and corrupted paths
                if '/Trash/' in p or p.startswith('..') or '/Trash' in p:
                    continue
                
                # Skip orphaned DB entries (folder no longer exists on disk)
                abs_check = os.path.join(self.storage_root, p) if not os.path.isabs(p) else p
                if not os.path.exists(abs_check):
                    continue
                    
                if cfg.get('last_known_status') == 'linked':
                    linked_count += 1
                    # Library tracking
                    if cfg.get('is_library', 0):
                        lib_name = cfg.get('lib_name')
                        if lib_name:
                            active_library_names.add(lib_name.strip().lower())

                    # Occupied Target Tracking (Global)
                    if self.target_root:
                        folder_name = os.path.basename(p)
                        target_path = cfg.get('target_override') or os.path.join(self.target_root, folder_name)
                        norm_target = target_path.replace('\\', '/').lower()
                        active_targets_map[norm_target] = p

                    # Tag tracking (Index ALL linked tags)
                    if cfg.get('conflict_scope', 'disabled') != 'disabled':
                        tag_str = cfg.get('conflict_tag')
                        if tag_str:
                            tags = [t.strip() for t in tag_str.split(',') if t.strip()]
                            for t in tags:
                                if not t: continue
                                rel_p = p
                                if os.path.isabs(p):
                                    try: rel_p = os.path.relpath(p, self.storage_root)
                                    except: pass
                                
                                cat_path = os.path.dirname(rel_p).replace('\\', '/')
                                if t not in active_tags_map: active_tags_map[t] = []
                                active_tags_map[t].append({
                                    'path': p,
                                    'scope': cfg.get('conflict_scope', 'disabled'),
                                    'cat': cat_path
                                })

            logger.debug(f"[Profile] TagConflictWorker: Indexed {len(all_configs)} items, {linked_count} linked. Found {len(active_tags_map)} active tags.")

            # Step 2: Identify Conflicts and Library Alts for ALL items
            conflict_count = 0
            alt_count = 0
            bulk_updates = {} # For DB update inside worker
            abs_config_map = {} # For UI thread matching

            for p, cfg in all_configs.items():
                if not p: continue

                # Skip trash items and corrupted paths (same filter as Step 1)
                if '/Trash/' in p or p.startswith('..') or '/Trash' in p:
                    continue
                
                # Skip orphaned DB entries (folder no longer exists on disk)
                abs_check = os.path.join(self.storage_root, p) if not os.path.isabs(p) else p
                if not os.path.exists(abs_check):
                    continue
                    
                # Normalized path for matching
                norm_p = p.replace('\\', '/')
                rel_p = p
                abs_p = p
                if not os.path.isabs(p):
                    abs_p = os.path.join(self.storage_root, p).replace('\\', '/')
                else:
                    try: rel_p = os.path.relpath(p, self.storage_root).replace('\\', '/')
                    except: pass
                
                my_cat = os.path.dirname(rel_p).replace('\\', '/')
                
                has_logical_conflict = False
                is_library_alt_version = False
                
                status = cfg.get('last_known_status', 'none')
                is_linked = (status == 'linked')

                # A. Library Alt Version Check
                if cfg.get('is_library', 0) and not is_linked:
                    lib_name = cfg.get('lib_name')
                    if lib_name and lib_name.strip().lower() in active_library_names:
                        is_library_alt_version = True
                        alt_count += 1
                
                # B. Tag Match Conflict
                tag_str = cfg.get('conflict_tag')
                scope = cfg.get('conflict_scope', 'disabled')
                if tag_str and scope != 'disabled':
                    my_tags = [t.strip() for t in tag_str.split(',') if t.strip()]
                    for tag in my_tags:
                        matches = active_tags_map.get(tag, [])
                        for m in matches:
                            if m.get('path') == p: continue
                            if scope == 'global' or m['scope'] == 'global':
                                has_logical_conflict = True
                                logger.debug(f"[ConflictDebug] TAG GLOBAL: '{p}' conflicts with '{m.get('path')}' via tag '{tag}'")
                                break
                            if scope == 'category' and m['cat'] == my_cat:
                                has_logical_conflict = True
                                logger.debug(f"[ConflictDebug] TAG CATEGORY: '{p}' conflicts with '{m.get('path')}' via tag '{tag}' in category '{my_cat}'")
                                break
                        if has_logical_conflict:
                            break
                
                # C. Global Physical Occupancy Check
                if not has_logical_conflict and self.target_root:
                    folder_name = os.path.basename(p)
                    target_path = cfg.get('target_override') or os.path.join(self.target_root, folder_name)
                    norm_target = target_path.replace('\\', '/').lower()
                    if norm_target in active_targets_map and active_targets_map[norm_target] != p:
                        has_logical_conflict = True
                        logger.debug(f"[ConflictDebug] PHYSICAL OCCUPANCY: '{p}' conflicts with '{active_targets_map[norm_target]}' at target '{norm_target}'")
                
                # D. Physical status override
                if not has_logical_conflict and status == 'conflict':
                    has_logical_conflict = True
                    logger.debug(f"[ConflictDebug] DB STATUS: '{p}' has 'conflict' status in DB")

                # Step 2.6: Persistent marking
                cfg['has_logical_conflict'] = has_logical_conflict
                cfg['is_library_alt_version'] = is_library_alt_version
                if has_logical_conflict:
                    conflict_count += 1
                    tag_conflicted_categories.add(my_cat)

                # Prepare bulk update for DB
                bulk_updates[rel_p] = {
                    'has_logical_conflict': 1 if has_logical_conflict else 0,
                    'is_library_alt_version': 1 if is_library_alt_version else 0
                }
                # Prepare result for UI thread matching by absolute path (Case-insensitive for Windows)
                match_p = abs_p.lower() if os.name == 'nt' else abs_p
                abs_config_map[match_p] = cfg

            # 2.7: Perform DB Update in Background Thread
            local_db.update_visual_flags_bulk(bulk_updates)

            logger.debug(f"[Profile] TagConflictWorker: Detected {conflict_count} conflicts, {alt_count} library alts. Time: {time.time()-start_t:.3f}s")
            
            # 3. Return results (now includes abs_config_map)
            result = {
                'active_tags_map': active_tags_map,
                'active_library_names': list(active_library_names),
                'active_targets_map': active_targets_map,
                'tag_conflicted_categories': list(tag_conflicted_categories),
                'all_configs': all_configs,
                'abs_config_map': abs_config_map
            }
            self.finished.emit(result)
            
        except Exception as e:
            import traceback
            logger.error(f"TagConflictWorker Error: {e}")
            logger.error(traceback.format_exc())
            self.finished.emit(None)
