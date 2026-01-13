import sqlite3
import logging
import os
import json
from src.core import core_handler

class LinkMasterRegistry:
    """Manages the list of applications in the global plugins.db."""
    def __init__(self):
        self.logger = logging.getLogger("LinkMasterRegistry")
        self.db_path = core_handler.db_path
        self._apps_cache = None
        self._create_tables()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def _create_tables(self):
        schema = [
            '''CREATE TABLE IF NOT EXISTS lm_apps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                storage_root TEXT NOT NULL,
                target_root TEXT NOT NULL,
                target_root_2 TEXT,
                default_subpath TEXT,
                managed_folder_name TEXT DEFAULT '_LinkMaster_Assets',
                conflict_policy TEXT DEFAULT 'backup',
                deployment_type TEXT DEFAULT 'folder',
                cover_image TEXT,
                last_target TEXT DEFAULT 'target_root',
                default_category_style TEXT DEFAULT 'image',
                default_package_style TEXT DEFAULT 'image',
                default_skip_levels INTEGER DEFAULT 0

            )''',
            '''CREATE TABLE IF NOT EXISTS lm_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )'''
        ]
        with self.get_connection() as conn:
            for sql in schema:
                conn.execute(sql)
            # Migration check
            try:
                conn.execute("ALTER TABLE lm_apps ADD COLUMN last_target TEXT DEFAULT 'target_root'")
            except: pass
            try:
                conn.execute("ALTER TABLE lm_apps ADD COLUMN default_category_style TEXT DEFAULT 'image'")
            except: pass
            try:
                conn.execute("ALTER TABLE lm_apps ADD COLUMN default_package_style TEXT DEFAULT 'image'")
            except: pass
            try:
                conn.execute("ALTER TABLE lm_apps ADD COLUMN executables TEXT DEFAULT '[]'")
            except: pass
            try:
                conn.execute("ALTER TABLE lm_apps ADD COLUMN url_list TEXT DEFAULT '[]'")
            except: pass
            try:
                conn.execute("ALTER TABLE lm_apps ADD COLUMN deployment_rule TEXT DEFAULT 'folder'")
            except: pass
            try:
                conn.execute("ALTER TABLE lm_apps ADD COLUMN transfer_mode TEXT DEFAULT 'symlink'")
            except: pass
            try:
                conn.execute("ALTER TABLE lm_apps ADD COLUMN is_favorite INTEGER DEFAULT 0")
            except: pass
            try:
                conn.execute("ALTER TABLE lm_apps ADD COLUMN score INTEGER DEFAULT 0")
            except: pass
            try:
                conn.execute("ALTER TABLE lm_apps ADD COLUMN target_root_3 TEXT")
            except: pass
            try:
                conn.execute("ALTER TABLE lm_apps ADD COLUMN deployment_rule_b TEXT DEFAULT 'folder'")
            except: pass
            try:
                conn.execute("ALTER TABLE lm_apps ADD COLUMN deployment_rule_c TEXT DEFAULT 'folder'")
            except: pass
            try:
                conn.execute("ALTER TABLE lm_apps ADD COLUMN default_skip_levels INTEGER DEFAULT 0")
            except: pass

            conn.commit()

    def get_setting(self, key: str, default: str = None) -> str:
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT value FROM lm_settings WHERE key = ?", (key,))
            res = cur.fetchone()
            return res[0] if res else default

    def set_setting(self, key: str, value: str):
        with self.get_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO lm_settings (key, value) VALUES (?, ?)", (key, value))
            conn.commit()

    def save_tags(self, tags_json: str):
        """Persist frequent tags configuration to settings."""
        self.set_setting('frequent_tags_config', tags_json)

    def get_global(self, key: str, default=None):
        """Get a global setting value. Returns default if not found."""
        result = self.get_setting(key)
        if result is None:
            return default
        # Try to parse as int/float if possible
        try:
            return int(result)
        except (ValueError, TypeError):
            try:
                return float(result)
            except (ValueError, TypeError):
                return result

    def set_global(self, key: str, value):
        """Set a global setting value."""
        self.set_setting(key, str(value))

    def get_apps(self):
        if self._apps_cache is not None:
            return self._apps_cache
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM lm_apps")
            self._apps_cache = [dict(row) for row in cursor.fetchall()]
            return self._apps_cache

    def add_app(self, data: dict):
        self._apps_cache = None
        sql = '''INSERT INTO lm_apps (name, storage_root, target_root, target_root_2, target_root_3, default_subpath, managed_folder_name, conflict_policy, deployment_type, deployment_rule, deployment_rule_b, deployment_rule_c, transfer_mode, cover_image, is_favorite, score, default_skip_levels)
                 VALUES (:name, :storage_root, :target_root, :target_root_2, :target_root_3, :default_subpath, :managed_folder_name, :conflict_policy, :deployment_type, :deployment_rule, :deployment_rule_b, :deployment_rule_c, :transfer_mode, :cover_image, :is_favorite, :score, :default_skip_levels)'''
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, data)
            conn.commit()
            return cursor.lastrowid

    def update_app(self, app_id: int, data: dict):
        self._apps_cache = None
        valid_keys = ['name', 'storage_root', 'target_root', 'target_root_2', 'target_root_3', 'managed_folder_name', 
                      'default_subpath', 'conflict_policy', 'deployment_type', 'deployment_rule', 'deployment_rule_b', 'deployment_rule_c', 'transfer_mode',
                      'cover_image', 'last_target',
                      'default_category_style', 'default_package_style', 'executables', 'url_list',
                      'is_favorite', 'score', 'default_skip_levels']

        parts = []
        params = []
        for k in valid_keys:
            if k in data:
                parts.append(f"{k} = ?")
                params.append(data[k])
        if not parts: return
        sql = f"UPDATE lm_apps SET {', '.join(parts)} WHERE id = ?"
        params.append(app_id)
        with self.get_connection() as conn:
            conn.execute(sql, params)
            conn.commit()

    def delete_app(self, app_id: int):
        self._apps_cache = None
        with self.get_connection() as conn:
            conn.execute("DELETE FROM lm_apps WHERE id = ?", (app_id,))
            conn.commit()

    def update_app_cover(self, app_id: int, cover_image: str):
        self.update_app(app_id, {'cover_image': cover_image})

    def update_app_last_target(self, app_id: int, last_target: str):
        self.update_app(app_id, {'last_target': last_target})

class LinkMasterDB:
    """Manages application-specific data in resource/app/<app_name>/dyonis.db."""
    def __init__(self, app_name: str = None, db_path: str = None):
        self.app_name = app_name
        self.logger = logging.getLogger(f"LinkMasterDB.{app_name or 'Default'}")
        
        if db_path:
            self.db_path = db_path
        elif app_name:
            # Standard path: resource/app/<name>/dyonis.db
            # Use FileHandler for EXE compatibility (handles sys.frozen)
            from src.core.file_handler import FileHandler
            project_root = FileHandler().project_root
            app_dir = os.path.join(project_root, "resource", "app", app_name)
            os.makedirs(app_dir, exist_ok=True)
            self.db_path = os.path.join(app_dir, "dyonis.db")
            
            # Migration: link_master.db -> dyonis.db
            old_db_path = os.path.join(app_dir, "link_master.db")
            if os.path.exists(old_db_path) and not os.path.exists(self.db_path):
                import shutil
                try:
                    shutil.copy2(old_db_path, self.db_path)
                    self.logger.info(f"[Migration] Copied link_master.db -> dyonis.db for {app_name}")
                except PermissionError:
                    self.logger.warning(f"[Migration] Could not migrate link_master.db (file in use) - using old DB instead")
                    self.db_path = old_db_path  # Fallback to old path if locked
        else:
            self.db_path = core_handler.db_path # Fallback to global
            self.logger.debug("LinkMasterDB created without app_name - using global DB fallback.")
            # Skip table creation for global DB - app-specific tables should not exist there
            return  # Exit __init__ without creating tables
            
        self._create_tables()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def _create_tables(self):
        schema = [
            '''CREATE TABLE IF NOT EXISTS lm_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                version TEXT,
                description TEXT,
                author TEXT,
                storage_rel_path TEXT NOT NULL,
                preview_rel_path TEXT,
                is_enabled INTEGER DEFAULT 0,
                last_updated TEXT
            )''',
            '''CREATE TABLE IF NOT EXISTS lm_folder_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rel_path TEXT NOT NULL,
                folder_type TEXT DEFAULT 'package',
                display_style TEXT DEFAULT 'image',
                display_name TEXT,
                image_path TEXT,
                manual_preview_path TEXT, -- Phase 16.5
                is_terminal INTEGER DEFAULT 0,
                tags TEXT,
                target_override TEXT,     -- Phase 16
                deployment_rules TEXT,     -- Phase 16 (JSON)
                deploy_rule TEXT,          -- Phase 5 (A/B/C support)
                deploy_rule_b TEXT,        -- Target 2 override
                deploy_rule_c TEXT,        -- Target 3 override
                deploy_type TEXT,          -- Phase 18.15 (Override)
                conflict_policy TEXT,      -- Phase 18.15 (Override)
                conflict_tag TEXT,         -- Phase 28: Tag to check for conflicts
                conflict_scope TEXT,       -- Phase 28: Scope for conflict check (disabled/category/global)
                description TEXT,          -- Phase 28: User description
                inherit_tags INTEGER DEFAULT 1, -- Phase 18 (Allow blocking inheritance)
                trash_origin TEXT, -- Phase 18.11: Store original path for restore
                transfer_mode TEXT, -- Phase 34: Copy vs Symlink override
                UNIQUE(rel_path)
            )''',
            '''CREATE TABLE IF NOT EXISTS lm_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )''',
            '''CREATE TABLE IF NOT EXISTS lm_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                icon_rel_path TEXT,
                category TEXT,
                is_inheritable INTEGER DEFAULT 1 -- Phase 18.9
            )''',

            '''CREATE TABLE IF NOT EXISTS lm_item_tags (
                item_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY(item_id, tag_id)
            )''',
            '''CREATE TABLE IF NOT EXISTS lm_presets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT
            )''',
            '''CREATE TABLE IF NOT EXISTS lm_preset_items (
                preset_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                PRIMARY KEY(preset_id, item_id)
            )''',
            '''CREATE TABLE IF NOT EXISTS lm_preset_folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                sort_order INTEGER DEFAULT 0,
                is_expanded INTEGER DEFAULT 1
            )''',
            '''CREATE TABLE IF NOT EXISTS lm_lib_folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                parent_id INTEGER DEFAULT NULL,
                sort_order INTEGER DEFAULT 0,
                is_expanded INTEGER DEFAULT 1,
                FOREIGN KEY(parent_id) REFERENCES lm_lib_folders(id) ON DELETE CASCADE
            )''',
            '''CREATE TABLE IF NOT EXISTS lm_backup_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_path TEXT NOT NULL,
                backup_path TEXT NOT NULL,
                folder_rel_path TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(original_path)
            )''',
            # Phase 42: Deployed files tracking (User Request)
            '''CREATE TABLE IF NOT EXISTS lm_deployed_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_path TEXT NOT NULL,
                source_path TEXT NOT NULL,
                package_rel_path TEXT NOT NULL,
                deploy_type TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(target_path)
            )'''
        ]
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for sql in schema:
                cursor.execute(sql)
            
            # Migrations
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN target_override TEXT")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN deployment_rules TEXT")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN manual_preview_path TEXT")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN inherit_tags INTEGER DEFAULT 1")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_tags ADD COLUMN is_inheritable INTEGER DEFAULT 1")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN trash_origin TEXT")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN deploy_type TEXT")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN conflict_policy TEXT")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN deploy_rule TEXT")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN deploy_rule_b TEXT")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN deploy_rule_c TEXT")
            except: pass
            
            # Phase 28 Migrations
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN conflict_tag TEXT")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN conflict_scope TEXT")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN description TEXT")
            except: pass
            try:
                # Phase 28: Cache for link status to avoid expensive recursive scans
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN last_known_status TEXT")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN link_status_cache TEXT")
            except: pass

            # Quick View Manager Support (Fav/Score per item)
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN is_favorite INTEGER DEFAULT 0")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN score INTEGER DEFAULT 0")
            except: pass
            
            # Phase 34: Transfer Mode
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN transfer_mode TEXT")
            except: pass
            
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN is_visible INTEGER DEFAULT 1")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN display_style_package TEXT DEFAULT 'image'")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_presets ADD COLUMN folder TEXT")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN sort_order INTEGER DEFAULT 0")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_presets ADD COLUMN sort_order INTEGER DEFAULT 0")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_presets ADD COLUMN folder_id INTEGER DEFAULT NULL")
            except: pass
            
            # Phase 4 New Features: Library Management
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN is_library INTEGER DEFAULT 0")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN lib_name TEXT")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN lib_version TEXT")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN lib_deps TEXT")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN lib_priority INTEGER DEFAULT 0")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN lib_priority_mode TEXT")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN lib_memo TEXT")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN lib_hidden INTEGER DEFAULT 0")
            except: pass
            
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN lib_folder_id INTEGER DEFAULT NULL")
            except: pass
            
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN author TEXT")
            except: pass
            
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN size_bytes INTEGER DEFAULT 0")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN scanned_at TEXT")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN url TEXT")
            except: pass
            
            # Favorite & URL List Enhancement
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN url_list TEXT")
            except: pass

            # Phase X: Persistent Visual Flags
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN has_logical_conflict INTEGER DEFAULT 0")
            except: pass
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN is_library_alt_version INTEGER DEFAULT 0")
            except: pass
            
            # Phase 42: Separate Target Selection from Physical Path (User Request)
            try:
                cursor.execute("ALTER TABLE lm_folder_config ADD COLUMN target_selection TEXT")
            except: pass

            # Create indexes for performance
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_folder_config_lib_name ON lm_folder_config (lib_name)")
            except: pass
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_folder_config_is_library ON lm_folder_config (is_library)")
            except: pass
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_folder_config_status ON lm_folder_config (last_known_status)")
            except: pass
            
            # Phase 42: Ensure tracking tables exist for existing databases
            try:
                cursor.execute('''CREATE TABLE IF NOT EXISTS lm_backup_registry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_path TEXT NOT NULL,
                    backup_path TEXT NOT NULL,
                    folder_rel_path TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(original_path)
                )''')
            except: pass
            
            try:
                cursor.execute('''CREATE TABLE IF NOT EXISTS lm_deployed_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_path TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    package_rel_path TEXT NOT NULL,
                    deploy_type TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(target_path)
                )''')
            except: pass
            
            conn.commit()

    # --- Item Methods ---
    def get_items(self):
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM lm_items")
            return [dict(row) for row in cursor.fetchall()]

    def get_or_create_item(self, name: str, rel_path: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM lm_items WHERE storage_rel_path = ?", (rel_path,))
            row = cursor.fetchone()
            if row: return row[0]
            
            cursor.execute("INSERT INTO lm_items (name, storage_rel_path, is_enabled) VALUES (?, ?, 0)", (name, rel_path))
            conn.commit()
            return cursor.lastrowid

    def set_item_enabled_state(self, item_id: int, is_enabled: bool):
        with self.get_connection() as conn:
            conn.execute("UPDATE lm_items SET is_enabled = ? WHERE id = ?", (1 if is_enabled else 0, item_id))
            conn.commit()

    # --- Preset Methods ---
    def create_preset(self, name: str, item_ids: list, description: str = None, folder: str = None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO lm_presets (name, description, folder) VALUES (?, ?, ?)", (name, description, folder))
            preset_id = cursor.lastrowid
            vals = [(preset_id, iid) for iid in item_ids]
            cursor.executemany("INSERT INTO lm_preset_items (preset_id, item_id) VALUES (?, ?)", vals)
            conn.commit()
            return preset_id

    def get_presets(self):
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM lm_presets")
            return [dict(row) for row in cursor.fetchall()]

    def get_preset_items(self, preset_id: int):
        sql = "SELECT i.* FROM lm_items i JOIN lm_preset_items pi ON pi.item_id = i.id WHERE pi.preset_id = ?"
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql, (preset_id,))
            return [dict(row) for row in cursor.fetchall()]

    def delete_preset(self, preset_id: int):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM lm_presets WHERE id = ?", (preset_id,))
            conn.commit()

    def update_preset(self, preset_id: int, **kwargs):
        """Update preset metadata like name, description, or sort_order."""
        valid_cols = ['name', 'description', 'folder', 'sort_order']
        updates = []
        params = []
        for k, v in kwargs.items():
            if k in valid_cols:
                updates.append(f"{k} = ?")
                params.append(v)
        if not updates: return
        
        sql = f"UPDATE lm_presets SET {', '.join(updates)} WHERE id = ?"
        params.append(preset_id)
        with self.get_connection() as conn:
            conn.execute(sql, params)
            conn.commit()

    def update_preset_order(self, order_list: list):
        """Update sort_order for multiple presets at once.
        order_list: list of preset_id in the desired order.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for i, p_id in enumerate(order_list):
                cursor.execute("UPDATE lm_presets SET sort_order = ? WHERE id = ?", (i, p_id))
            conn.commit()

    # --- Preset Folder Methods ---
    def create_preset_folder(self, name: str) -> int:
        """Create a new preset folder."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO lm_preset_folders (name) VALUES (?)", (name,))
            conn.commit()
            return cursor.lastrowid

    def get_preset_folders(self) -> list:
        """Get all preset folders."""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM lm_preset_folders ORDER BY sort_order, name")
            return [dict(row) for row in cursor.fetchall()]

    def update_preset_folder(self, folder_id: int, **kwargs):
        """Update preset folder metadata."""
        valid_cols = ['name', 'sort_order', 'is_expanded']
        updates = []
        params = []
        for k, v in kwargs.items():
            if k in valid_cols:
                updates.append(f"{k} = ?")
                params.append(v)
        if not updates: return
        
        sql = f"UPDATE lm_preset_folders SET {', '.join(updates)} WHERE id = ?"
        params.append(folder_id)
        with self.get_connection() as conn:
            conn.execute(sql, params)
            conn.commit()

    def delete_preset_folder(self, folder_id: int):
        """Delete a preset folder. Presets in this folder will be moved to root."""
        with self.get_connection() as conn:
            # Move presets to root (folder_id = NULL)
            conn.execute("UPDATE lm_presets SET folder_id = NULL WHERE folder_id = ?", (folder_id,))
            conn.execute("DELETE FROM lm_preset_folders WHERE id = ?", (folder_id,))
            conn.commit()

    def move_preset_to_folder(self, preset_id: int, folder_id: int = None):
        """Move a preset to a folder. folder_id=None means root."""
        with self.get_connection() as conn:
            conn.execute("UPDATE lm_presets SET folder_id = ? WHERE id = ?", (folder_id, preset_id))
            conn.commit()

    def update_folder_order(self, order_list: list):
        """Update sort_order for preset folders."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for i, f_id in enumerate(order_list):
                cursor.execute("UPDATE lm_preset_folders SET sort_order = ? WHERE id = ?", (i, f_id))
            conn.commit()

    # --- Folder Config ---
    def get_folder_config(self, rel_path: str):
        # Normalize path to forward slashes for consistent DB lookup
        rel_path = rel_path.replace('\\', '/') if rel_path else rel_path
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM lm_folder_config WHERE rel_path = ?", (rel_path,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_folder_configs(self):
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM lm_folder_config")
            rows = cursor.fetchall()
            return {r['rel_path']: dict(r) for r in rows}

    def store_item_origin(self, rel_path, origin_rel_path):
        """Phase 18.11: Store the original relative path of an item before moving it (e.g. to Trash)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE lm_folder_config SET trash_origin = ? WHERE rel_path = ?", (origin_rel_path, rel_path))
            conn.commit()

    def get_item_origin(self, rel_path):
        """Phase 18.11: Get the original relative path for restore."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT trash_origin FROM lm_folder_config WHERE rel_path = ?", (rel_path,))
            row = cursor.fetchone()
            return row[0] if row else None

    def delete_folder_config(self, rel_path: str):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM lm_folder_config WHERE rel_path = ?", (rel_path,))
            conn.commit()

    def reset_app_folder_configs(self):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM lm_folder_config")
            conn.execute("DELETE FROM lm_items") # Reset link states too
            conn.commit()

    def update_folder_display_config(self, rel_path: str, **kwargs):
        """Update display config for a folder (Upsert)."""
        # Normalize path to forward slashes for consistent DB storage
        rel_path = rel_path.replace('\\', '/') if rel_path else rel_path
        valid_cols = ['app_id', 'folder_type', 'display_style', 'display_style_package', 'display_name', 'image_path', 'manual_preview_path', 
                       'tags', 'is_terminal', 'target_override', 'deployment_rules', 'deploy_rule', 'deploy_rule_b', 'deploy_rule_c', 'inherit_tags', 'is_visible',
                       'deploy_type', 'conflict_policy', 'transfer_mode', 'sort_order', 'last_known_status',
                       'conflict_tag', 'conflict_scope', 'description', 'author', 'url',
                       'is_favorite', 'score', 'url_list',
                       'is_library', 'lib_name', 'lib_version', 'lib_deps', 'lib_priority', 'lib_priority_mode', 'lib_memo', 'lib_hidden',
                       'lib_folder_id',
                       'has_logical_conflict', 'is_library_alt_version', 'category_deploy_status',
                       'size_bytes', 'scanned_at', 'target_selection']
        updates = []
        params = []
        for k, v in kwargs.items():
            if k in valid_cols:
                # Include None values to allow clearing fields
                updates.append(f"{k} = ?")
                params.append(v)  # None will be saved as NULL, clearing the field
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Phase 28 Fix: Case-Insensitive Lookup on Windows to prevent duplicate entries
                # If we have 'Path' and try to update 'path', we should update 'Path'.
                target_id = None
                if os.name == 'nt':
                    cursor.execute("SELECT id FROM lm_folder_config WHERE LOWER(rel_path) = ?", (rel_path.lower(),))
                else:
                    cursor.execute("SELECT id FROM lm_folder_config WHERE rel_path = ?", (rel_path,))
                
                row = cursor.fetchone()
                
                if row:
                    update_cols = []
                    update_params = []
                    for k, v in kwargs.items():
                        if k in valid_cols:
                            update_cols.append(f"{k} = ?")
                            update_params.append(v)
                    
                    if update_cols: # Only update if there are actual updates
                        update_params.append(row[0])
                        sql = f"UPDATE lm_folder_config SET {', '.join(update_cols)} WHERE id = ?"
                        logging.debug(f"[DB] UPDATE: {rel_path} with {kwargs}")
                        cursor.execute(sql, update_params)
                else:
                    # Insert new record - always insert even with no kwargs (just rel_path)
                    insert_cols = ['rel_path']
                    insert_params = [rel_path]
                    for k, v in kwargs.items():
                        if k in valid_cols and v is not None:
                            insert_cols.append(k)
                            insert_params.append(v)
                    placeholders = ['?'] * len(insert_cols)
                    sql = f"INSERT INTO lm_folder_config ({', '.join(insert_cols)}) VALUES ({', '.join(placeholders)})"
                    logging.debug(f"[DB] INSERT: {rel_path} with {kwargs}")
                    cursor.execute(sql, insert_params)
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"[DB] Error updating config for {rel_path}: {e}")
            return False


    def bulk_update_items(self, update_list: list) -> bool:
        """
        Efficiently update multiple items in a single transaction.
        update_list: list of dicts, each must have 'rel_path'.
        """
        if not update_list:
            return True
            
        try:
            with self.get_connection() as conn:
                # Disable autocommit to start a transaction explicitly via 'with' or just use manual commit
                cursor = conn.cursor()
                
                # We reuse the logic from update_folder_display_config but in one transaction
                valid_cols = {'app_id', 'folder_type', 'display_style', 'display_style_package', 'display_name', 'image_path', 'manual_preview_path', 
                             'tags', 'is_terminal', 'target_override', 'deployment_rules', 'deploy_rule', 'deploy_rule_b', 'deploy_rule_c', 'inherit_tags', 'is_visible',
                             'deploy_type', 'conflict_policy', 'transfer_mode', 'sort_order', 'last_known_status',
                             'conflict_tag', 'conflict_scope', 'description', 'author', 'url',
                             'is_favorite', 'score', 'url_list',
                             'is_library', 'lib_name', 'lib_version', 'lib_deps', 'lib_priority', 'lib_priority_mode', 'lib_memo', 'lib_hidden',
                             'lib_folder_id', 'has_logical_conflict', 'is_library_alt_version', 'size_bytes', 'scanned_at'}
                
                for item_data in update_list:
                    rel_path = item_data.get('rel_path')
                    if not rel_path: continue
                    
                    # Normalize
                    rel_path = rel_path.replace('\\', '/')
                    
                    # Extract valid fields
                    kwargs = {k: v for k, v in item_data.items() if k in valid_cols}
                    if not kwargs: continue
                    
                    # Similar lookup as update_folder_display_config
                    target_id = None
                    if os.name == 'nt':
                        cursor.execute("SELECT id FROM lm_folder_config WHERE LOWER(rel_path) = ?", (rel_path.lower(),))
                    else:
                        cursor.execute("SELECT id FROM lm_folder_config WHERE rel_path = ?", (rel_path,))
                    
                    row = cursor.fetchone()
                    if row:
                        target_id = row[0]
                        
                    if target_id:
                        updates = []
                        params = []
                        for k, v in kwargs.items():
                            updates.append(f"{k} = ?")
                            params.append(v)
                        
                        params.append(target_id)
                        cursor.execute(f"UPDATE lm_folder_config SET {', '.join(updates)} WHERE id = ?", params)
                    else:
                        insert_cols = ['rel_path']
                        insert_params = [rel_path]
                        for k, v in kwargs.items():
                            if v is not None:
                                insert_cols.append(k)
                                insert_params.append(v)
                        placeholders = ['?'] * len(insert_cols)
                        cursor.execute(f"INSERT INTO lm_folder_config ({', '.join(insert_cols)}) VALUES ({', '.join(placeholders)})", insert_params)
                
                conn.commit()
            return True
        except Exception as e:
            logging.error(f"bulk_update_items failed: {e}")
            return False


    def update_visual_flags_bulk(self, updates: dict):
        """
        Efficiently update visual flags for multiple paths in a single transaction.
        'updates' should be: { rel_path: { 'has_logical_conflict': 0/1, 'is_library_alt_version': 0/1 } }
        """
        if not updates: return
        
        sql = """
        UPDATE lm_folder_config 
        SET has_logical_conflict = ?, is_library_alt_version = ?
        WHERE rel_path = ?
        """
        
        # Prepare params list for executemany
        params = []
        for rel_p, flags in updates.items():
            # Standardize path
            rel_p = rel_p.replace('\\', '/') if rel_p else rel_p
            params.append((
                flags.get('has_logical_conflict', 0),
                flags.get('is_library_alt_version', 0),
                rel_p
            ))
            
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(sql, params)
            conn.commit()

    def get_folder_tags(self, rel_path: str) -> list:
        config = self.get_folder_config(rel_path)
        if config and config.get('tags'):
            return [t.strip() for t in config['tags'].split(',') if t.strip()]
        return []

    def get_all_tags(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Fetch from both tags and conflict_tag columns
            cursor.execute("SELECT tags, conflict_tag FROM lm_folder_config")
            rows = cursor.fetchall()
            unique = set()
            for r in rows:
                # tags column (comma separated)
                if r[0]:
                    unique.update([t.strip() for t in r[0].split(',') if t.strip()])
                # conflict_tag column (comma separated)
                if r[1]:
                    unique.update([t.strip() for t in r[1].split(',') if t.strip()])
            return sorted(list(unique))

    # --- Frequent Tag Management (lm_tags) ---
    def get_tag_definitions(self):
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM lm_tags")
            return [dict(row) for row in cursor.fetchall()]

    def update_tag_definition(self, tag_id: int, tags_data: dict):
        valid_keys = ['name', 'icon_rel_path', 'category', 'is_inheritable']
        parts = []
        params = []
        for k in valid_keys:
            if k in tags_data:
                parts.append(f"{k} = ?")
                params.append(tags_data[k])
        if not parts: return
        sql = f"UPDATE lm_tags SET {', '.join(parts)} WHERE id = ?"
        params.append(tag_id)
        with self.get_connection() as conn:
            conn.execute(sql, params)
            conn.commit()

    def add_tag_definition(self, tags_data: dict):
        sql = "INSERT INTO lm_tags (name, icon_rel_path, category, is_inheritable) VALUES (:name, :icon_rel_path, :category, :is_inheritable)"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Ensure defaults for insert
            if 'is_inheritable' not in tags_data: tags_data['is_inheritable'] = 1
            cursor.execute(sql, tags_data)
            conn.commit()
            return cursor.lastrowid

    def delete_tag_definition(self, tag_id: int):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM lm_tags WHERE id = ?", (tag_id,))
            conn.commit()

    def get_non_inheritable_tag_names(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM lm_tags WHERE is_inheritable = 0")
            return {row[0].lower() for row in cursor.fetchall()}

    # --- Settings ---
    def get_setting(self, key: str, default: str = None) -> str:
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT value FROM lm_settings WHERE key = ?", (key,))
            res = cur.fetchone()
            return res[0] if res else default

    def set_setting(self, key: str, value: str):
        with self.get_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO lm_settings (key, value) VALUES (?, ?)", (key, value))
            conn.commit()

    # --- Library Folders ---
    def get_lib_folders(self) -> list:
        """Get all library folders."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, parent_id, sort_order, is_expanded FROM lm_lib_folders ORDER BY sort_order, name")
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def add_lib_folder(self, name: str, parent_id: int = None) -> int:
        """Add a new library folder."""
        sql = "INSERT INTO lm_lib_folders (name, parent_id) VALUES (?, ?)"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (name, parent_id))
            conn.commit()
            return cursor.lastrowid

    def update_lib_folder(self, folder_id: int, **kwargs):
        """Update a library folder's details."""
        if not kwargs: return
        fields = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        sql = f"UPDATE lm_lib_folders SET {fields} WHERE id = ?"
        params = list(kwargs.values()) + [folder_id]
        with self.get_connection() as conn:
            conn.execute(sql, params)
            conn.commit()

    def delete_lib_folder(self, folder_id: int):
        """Delete a library folder and move contents to root."""
        with self.get_connection() as conn:
            # Move items in the folder to root (null)
            conn.execute("UPDATE lm_folder_config SET lib_folder_id = NULL WHERE lib_folder_id = ?", (folder_id,))
            # Move child folders to root (null)
            conn.execute("UPDATE lm_lib_folders SET parent_id = NULL WHERE parent_id = ?", (folder_id,))
            # Delete the folder itself
            conn.execute("DELETE FROM lm_lib_folders WHERE id = ?", (folder_id,))
            conn.commit()

    # =====================================================================
    # Phase 30: Backup Registry Methods
    # =====================================================================
    def register_backup(self, original_path: str, backup_path: str, folder_rel_path: str = None):
        """Register a backup file for auto-restore on unlink."""
        # Phase X: Normalize paths for consistent lookup
        original_path = original_path.replace('\\', '/').lower() if original_path else original_path
        backup_path = backup_path.replace('\\', '/').lower() if backup_path else backup_path
        
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO lm_backup_registry (original_path, backup_path, folder_rel_path)
                VALUES (?, ?, ?)
            """, (original_path, backup_path, folder_rel_path))
            conn.commit()

    def get_backup_path(self, original_path: str) -> str:
        """Get the backup path for an original file path, or None if not found."""
        original_path = original_path.replace('\\', '/').lower() if original_path else original_path
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT backup_path FROM lm_backup_registry WHERE original_path = ?", (original_path,))
            row = cursor.fetchone()
            return row[0] if row else None

    def remove_backup_entry(self, original_path: str):
        """Remove a backup entry after restore or cleanup."""
        original_path = original_path.replace('\\', '/').lower() if original_path else original_path
        with self.get_connection() as conn:
            conn.execute("DELETE FROM lm_backup_registry WHERE original_path = ?", (original_path,))
            conn.commit()
    
    def get_backups_for_folder(self, folder_rel_path: str) -> list:
        """Get all backup entries for a specific folder."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT original_path, backup_path FROM lm_backup_registry WHERE folder_rel_path = ?", (folder_rel_path,))
            return cursor.fetchall()
    
    def clear_backups_for_folder(self, folder_rel_path: str):
        """Remove all backup entries for a folder."""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM lm_backup_registry WHERE folder_rel_path = ?", (folder_rel_path,))
            conn.commit()

    # =====================================================================
    # Phase 42: Deployed Files Tracking Methods (Declarative State)
    # =====================================================================
    def register_deployed_file(self, target_path: str, source_path: str, package_rel_path: str, deploy_type: str = None):
        """Register a file or link created by the application."""
        target_path = target_path.replace('\\', '/').lower() if target_path else target_path
        source_path = source_path.replace('\\', '/').lower() if source_path else source_path
        package_rel_path = package_rel_path.replace('\\', '/') if package_rel_path else package_rel_path
        
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO lm_deployed_files (target_path, source_path, package_rel_path, deploy_type)
                VALUES (?, ?, ?, ?)
            """, (target_path, source_path, package_rel_path, deploy_type))
            conn.commit()

    def get_deployed_files_for_package(self, package_rel_path: str) -> list:
        """Get all files/links registered to a package."""
        package_rel_path = package_rel_path.replace('\\', '/') if package_rel_path else package_rel_path
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT target_path, source_path, deploy_type FROM lm_deployed_files WHERE package_rel_path = ?", (package_rel_path,))
            return cursor.fetchall()

    def remove_deployed_file_entry(self, target_path: str):
        """Remove an entry for a specific target path."""
        target_path = target_path.replace('\\', '/').lower() if target_path else target_path
        with self.get_connection() as conn:
            conn.execute("DELETE FROM lm_deployed_files WHERE target_path = ?", (target_path,))
            conn.commit()
            
    def clear_deployed_files_for_package(self, package_rel_path: str):
        """Clear all registered files for a package."""
        package_rel_path = package_rel_path.replace('\\', '/') if package_rel_path else package_rel_path
        with self.get_connection() as conn:
            conn.execute("DELETE FROM lm_deployed_files WHERE package_rel_path = ?", (package_rel_path,))
            conn.commit()

    def is_file_ours(self, target_path: str) -> bool:
        """Check if a path is registered as being deployed by Link Master."""
        target_path = target_path.replace('\\', '/').lower() if target_path else target_path
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM lm_deployed_files WHERE target_path = ?", (target_path,))
            return cursor.fetchone() is not None

# Singletons / Helpers
_registry_instance = None
def get_lm_registry():
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = LinkMasterRegistry()
    return _registry_instance

_db_instances = {}
def get_lm_db(app_name: str = None):
    """Returns an app-specific DB instance. If no name, uses global fallback."""
    if not app_name:
        return LinkMasterDB() 
    if app_name not in _db_instances:
        _db_instances[app_name] = LinkMasterDB(app_name=app_name)
    return _db_instances[app_name]
