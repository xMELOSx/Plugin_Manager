"""
Link Master: Centralized Path Management
Provides helper functions for Backup/Trash folder paths.
"""
import os
import sys


def get_app_base_dir():
    """
    Get the application's base directory.
    Works for both development (src/) and packaged (PyInstaller) environments.
    """
    if getattr(sys, 'frozen', False):
        # Running as packaged executable
        return os.path.dirname(sys.executable)
    else:
        # Running in development
        # Go up from src/core/link_master to project root
        current_file = os.path.abspath(__file__)
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))


def get_resource_dir():
    """Get the resource directory path."""
    return os.path.join(get_app_base_dir(), "resource")


def get_app_resource_dir(app_name: str):
    """Get the app-specific resource directory path."""
    return os.path.join(get_resource_dir(), "app", app_name)


def get_backup_dir(app_name: str):
    """
    Get the Backup directory path for a specific app.
    Path: resource/app/{app_name}/Backup
    Creates the directory if it doesn't exist.
    """
    backup_dir = os.path.join(get_app_resource_dir(app_name), "Backup")
    if not os.path.exists(backup_dir):
        try:
            os.makedirs(backup_dir)
        except OSError:
            pass
    return backup_dir


def get_trash_dir(app_name: str):
    """
    Get the Trash directory path for a specific app.
    Path: resource/app/{app_name}/Trash
    Creates the directory if it doesn't exist.
    """
    trash_dir = os.path.join(get_app_resource_dir(app_name), "Trash")
    if not os.path.exists(trash_dir):
        try:
            os.makedirs(trash_dir)
        except OSError:
            pass
    return trash_dir


def get_backup_path_for_file(app_name: str, source_rel_path: str):
    """
    Get the backup path for a specific file.
    Maintains directory structure within the Backup folder.
    
    Args:
        app_name: The application name
        source_rel_path: Relative path from storage_root (e.g., "Category/Package/file.txt")
    
    Returns:
        Full path to the backup location
    """
    backup_dir = get_backup_dir(app_name)
    return os.path.join(backup_dir, source_rel_path.replace('/', os.sep))


def get_trash_path_for_item(app_name: str, item_name: str, timestamp: int = None):
    """
    Get the trash path for a specific item.
    Adds timestamp suffix if collision would occur.
    
    Args:
        app_name: The application name
        item_name: Name of the item (folder or file)
        timestamp: Optional timestamp for collision handling
    
    Returns:
        Full path to the trash location
    """
    trash_dir = get_trash_dir(app_name)
    dest = os.path.join(trash_dir, item_name)
    
    if timestamp and os.path.exists(dest):
        dest = os.path.join(trash_dir, f"{item_name}_{timestamp}")
    
    return dest
