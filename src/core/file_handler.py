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

    # ========== File System Operations ==========
    
    def create_directory(self, path: str, exist_ok: bool = True) -> None:
        """Creates a directory (and parent directories) safely.
        
        Args:
            path: The directory path to create.
            exist_ok: If True, don't raise error if directory exists.
        """
        try:
            os.makedirs(path, exist_ok=exist_ok)
            self.logger.debug(f"Created directory: {path}")
        except Exception as e:
            self.logger.error(f"Failed to create directory {path}: {e}")
            raise

    def move_path(self, src: str, dest: str) -> str:
        """Moves a file or directory to a new location.
        
        Args:
            src: Source path (file or directory).
            dest: Destination path.
            
        Returns:
            The final destination path.
        """
        import shutil
        try:
            result = shutil.move(src, dest)
            self.logger.debug(f"Moved: {src} -> {dest}")
            return result
        except Exception as e:
            self.logger.error(f"Failed to move {src} to {dest}: {e}")
            raise

    def remove_path(self, path: str, force: bool = False) -> bool:
        """Removes a file or directory.
        
        Args:
            path: Path to remove.
            force: If True, remove directories recursively. If False, only remove files or empty dirs.
            
        Returns:
            True if successful, False otherwise.
        """
        import shutil
        try:
            if os.path.isfile(path) or os.path.islink(path):
                os.remove(path)
                self.logger.debug(f"Removed file: {path}")
            elif os.path.isdir(path):
                if force:
                    shutil.rmtree(path)
                    self.logger.debug(f"Removed directory (recursive): {path}")
                else:
                    os.rmdir(path)  # Only works on empty dirs
                    self.logger.debug(f"Removed empty directory: {path}")
            return True
        except Exception as e:
            self.logger.warning(f"Failed to remove {path}: {e}")
            return False

    def remove_empty_dir(self, path: str) -> bool:
        """Removes an empty directory. Silent fail if not empty or doesn't exist.
        
        Args:
            path: Directory path to remove.
            
        Returns:
            True if removed, False otherwise.
        """
        try:
            if os.path.isdir(path) and not os.listdir(path):
                os.rmdir(path)
                self.logger.debug(f"Removed empty directory: {path}")
                return True
            return False
        except Exception as e:
            self.logger.debug(f"Could not remove directory {path}: {e}")
            return False

