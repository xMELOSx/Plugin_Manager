import os
import sqlite3
import logging
from typing import Optional, Any
import threading

class FileHandler:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(FileHandler, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        import sys
        if getattr(sys, 'frozen', False):
            # EXE packaged mode: Persistence next to the EXE
            self.project_root = os.path.dirname(sys.executable)
        else:
            # Development mode: src/core/file_handler.py -> 3 levels up to project root
            self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.log_dir = os.path.join(self.project_root, "logs")
        
        # Global database in config directory
        self.config_dir = os.path.join(self.project_root, "config")
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
        self.db_path = os.path.join(self.config_dir, "global.db")
        
        # Migration: plugins.db -> config/global.db
        old_db_path = os.path.join(self.project_root, "plugins.db")
        if os.path.exists(old_db_path) and not os.path.exists(self.db_path):
            import shutil
            try:
                shutil.copy2(old_db_path, self.db_path)
                print(f"[Migration] Copied plugins.db -> config/global.db")
            except PermissionError:
                print(f"[Migration] Could not migrate plugins.db (file in use) - using old DB instead")
                self.db_path = old_db_path  # Fallback to old path if locked
        
        self._setup_logging()
        self._init_db()

    def _setup_logging(self):
        # 既に他の場所（main.pyなど）でログが設定されている場合は、
        # rootロガーのハンドラをリセットせずにそのまま使う
        if logging.getLogger().hasHandlers():
            self.logger = logging.getLogger("Core")
            return

        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
            
        log_file = os.path.join(self.log_dir, "app.log")
        
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("Core")
        self.logger.info("FileHandler initialized. (Fallback logging used)")

    def _init_db(self):
        """Initialize the SQLite database with required tables."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Create a simple metadata table for now
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS system_metadata (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                ''')
                conn.commit()
            self.logger.info(f"Database initialized at {self.db_path}")
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise

    def get_db_connection(self) -> sqlite3.Connection:
        """Returns a new connection to the SQLite database."""
        try:
            return sqlite3.connect(self.db_path)
        except Exception as e:
            self.logger.error(f"Failed to connect to database: {e}")
            raise

    def read_text_file(self, path: str) -> str:
        """Reads a text file safely."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self.logger.error(f"Failed to read file {path}: {e}")
            raise

    def write_text_file(self, path: str, content: str) -> None:
        """Writes content to a text file safely."""
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.logger.info(f"Successfully wrote to {path}")
        except Exception as e:
            self.logger.error(f"Failed to write file {path}: {e}")
            raise
    
    def log_message(self, level: str, message: str):
        """Standardized logging method."""
        level = level.upper()
        if level == "DEBUG":
            self.logger.debug(message)
        elif level == "INFO":
            self.logger.info(message)
        elif level == "WARNING":
            self.logger.warning(message)
        elif level == "ERROR":
            self.logger.error(message)
        elif level == "CRITICAL":
            self.logger.critical(message)
        else:
            self.logger.info(f"[UNKNOWN LEVEL {level}] {message}")

    # =========================================================================
    # Extended File Operations (Atomic / Safe Wrappers)
    # =========================================================================

    def path_exists(self, path: str) -> bool:
        """Check if path exists safely."""
        return os.path.exists(path)

    def is_dir(self, path: str) -> bool:
        """Check if path is a directory."""
        return os.path.isdir(path)

    def is_file(self, path: str) -> bool:
        """Check if path is a file."""
        return os.path.isfile(path)

    def is_link(self, path: str) -> bool:
        """Check if path is a symlink/junction."""
        return os.path.islink(path)
    
    def join_path(self, *args) -> str:
        """Join path components."""
        return os.path.join(*args)

    def get_parent(self, path: str) -> str:
        """Get parent directory."""
        return os.path.dirname(path)

    def ensure_directory(self, path: str):
        """Ensure a directory exists."""
        try:
            os.makedirs(path, exist_ok=True)
        except Exception as e:
            self.logger.error(f"Failed to create directory {path}: {e}")
            raise

    def remove_path(self, path: str):
        """Safely remove a file, directory, or link."""
        try:
            if not os.path.lexists(path):
                return
            
            if os.path.islink(path) or os.path.isfile(path):
                os.unlink(path)
                self.logger.debug(f"Removed file/link: {path}")
            elif os.path.isdir(path):
                import shutil
                shutil.rmtree(path)
                self.logger.debug(f"Removed directory tree: {path}")
        except Exception as e:
            self.logger.error(f"Failed to remove {path}: {e}")
            raise

    def remove_empty_dir(self, path: str):
        """Remove a directory only if it is empty."""
        try:
            os.rmdir(path)
            self.logger.debug(f"Removed empty directory: {path}")
        except OSError:
            pass # Not empty, ignore

    def move_path(self, src: str, dst: str):
        """Rename/Move a file or directory."""
        try:
            os.rename(src, dst)
            self.logger.debug(f"Moved {src} -> {dst}")
        except Exception as e:
            self.logger.error(f"Failed to move {src} -> {dst}: {e}")
            raise

    def copy_path(self, src: str, dst: str):
        """Copy a file or directory tree."""
        import shutil
        try:
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            self.logger.debug(f"Copied {src} -> {dst}")
        except Exception as e:
            self.logger.error(f"Failed to copy {src} -> {dst}: {e}")
            raise

    def create_symlink(self, src: str, dst: str, target_is_directory: bool = False):
        """Create a symbolic link."""
        try:
            os.symlink(src, dst, target_is_directory=target_is_directory)
            self.logger.debug(f"Created symlink {src} -> {dst}")
        except Exception as e:
            self.logger.error(f"Failed to create symlink {src} -> {dst}: {e}")
            raise

