import os
import sys

def get_project_root():
    """Returns absolute path to project root.
    EXE: Directory containing executable.
    DEV: Directory containing 'src'.
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    # Dev mode: 2 levels up from src/utils/path_utils.py
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_resource_path(relative_path):
    """Get absolute path to read-only resource.
    Works for dev and for PyInstaller (_MEIPASS).
    """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = get_project_root()
    return os.path.join(base_path, relative_path)

def get_user_data_path(relative_path=""):
    """Get absolute path to writable user data area (local project root)."""
    base = get_project_root()
    return os.path.join(base, relative_path)

def ensure_dir(path):
    """Ensure directory exists."""
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    return path
