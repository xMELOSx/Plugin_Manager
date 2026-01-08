"""
Link Master: Trash Operations Mixin
Extracted from LinkMasterWindow for modularity.
"""
import os
import shutil
import time
from PyQt6.QtWidgets import QMessageBox
from src.core.link_master.core_paths import get_trash_dir, get_trash_path_for_item


class LMTrashMixin:
    """Mixin providing trash operation methods for LinkMasterWindow."""
    
    def _open_trash_view(self):
        """Navigate to the Trash folder. Toggles back if already in Trash."""
        app_data = self.app_combo.currentData()
        if not app_data: return
        
        trash_path = get_trash_dir(app_data['name']).replace('\\', '/')
        current_view = getattr(self, 'current_view_path', "").replace('\\', '/')
        
        # Toggle back to last path if already in trash
        if current_view == trash_path:
            pre_path = getattr(self, '_pre_trash_path', app_data['storage_root'])
            self._load_items_for_path(pre_path)
            return

        # Save current path as return point before entering trash
        self._pre_trash_path = current_view
        
        # Clear filters before opening Trash view
        self.search_bar.clear()
        self.tag_bar.clear_selection()
        
        if not os.path.exists(trash_path):
            try: os.makedirs(trash_path)
            except: pass
        self._load_items_for_path(trash_path)
        self._hide_search_indicator()

    def _on_package_move_to_trash(self, path, refresh=True):
        """Move a package/folder to the _Trash folder.
        
        Uses _trash_single core method for visual feedback.
        """
        if refresh:
            # Single-item from context menu: use core method with visual feedback
            if hasattr(self, '_trash_single'):
                self._trash_single(path, update_ui=True)
                return
        
        # Batch operation fallback or refresh=False
        app_data = self.app_combo.currentData()
        if not app_data: return
        trash_root = get_trash_dir(app_data['name'])
            
        name = os.path.basename(path)
        dest = os.path.join(trash_root, name)
        
        # Handle collision
        if os.path.exists(dest):
            dest = os.path.join(trash_root, f"{name}_{int(time.time())}")
            
        try:
            shutil.move(path, dest)
            self.logger.info(f"Moved {name} to Trash")

            # Store origin for restore
            try:
                original_rel = os.path.relpath(path, app_data['storage_root']).replace('\\', '/')
                if original_rel == ".": original_rel = ""
                
                trash_rel = os.path.relpath(dest, app_data['storage_root']).replace('\\', '/')
                if trash_rel == ".": trash_rel = ""

                self.db.update_folder_display_config(trash_rel)
                self.db.store_item_origin(trash_rel, original_rel)
            except Exception as e:
                self.logger.error(f"Failed to store trash origin: {e}")
            
            if refresh:
                # Targeted removal of the trashed card
                self._remove_card_by_path(path)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not move to trash: {e}")

    def _on_package_restore(self, path, refresh=True):
        """Restore an item from Trash to its original location.
        
        Shows visual feedback before move, then removes card (no full rebuild).
        """
        app_data = self.app_combo.currentData()
        if not app_data: return
        storage_root = app_data['storage_root']
        
        try:
            rel_path = os.path.relpath(path, storage_root).replace('\\', '/')
            if rel_path == ".": rel_path = ""
            
            origin_rel = self.db.get_item_origin(rel_path)
            if not origin_rel:
                QMessageBox.warning(self, "Restore Failed", "Original location not known for this item.")
                return
            
            dest_abs = os.path.join(storage_root, origin_rel)
            
            dest_parent = os.path.dirname(dest_abs)
            if not os.path.exists(dest_parent):
                os.makedirs(dest_parent)
            
            if os.path.exists(dest_abs):
                QMessageBox.warning(self, "Conflict", f"Restore failed: {dest_abs} already exists.")
                return
            
            if refresh:
                # Show visual feedback (trashed/dimmed) before moving
                self._update_card_trashed_by_path(path, True)
                
                # Use QTimer for visual delay before move
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(300, lambda: self._do_restore_move(path, dest_abs, rel_path))
            else:
                # Direct move without visual feedback (batch operation)
                self._do_restore_move(path, dest_abs, rel_path)
            
        except Exception as e:
            self.logger.error(f"Restore Error: {e}")
            QMessageBox.critical(self, "Error", f"Could not restore: {e}")
    
    def _do_restore_move(self, src_path, dest_abs, rel_path):
        """Actually move the file from trash to original location."""
        try:
            shutil.move(src_path, dest_abs)
            self.logger.info(f"Restored {os.path.basename(src_path)} to {os.path.relpath(dest_abs, self.storage_root)}")
            
            self.db.store_item_origin(rel_path, None)
            
            # Remove the card from view (no full rebuild)
            self._remove_card_by_path(src_path)
        except Exception as e:
            self.logger.error(f"Restore move error: {e}")
            # Revert visual on error
            self._update_card_trashed_by_path(src_path, False)

    def _on_package_move_to_unclassified(self, path):
        """Move a misplaced package to Category/Unclassified."""
        app_data = self.app_combo.currentData()
        if not app_data: return
        unclass_root = os.path.join(app_data['storage_root'], "Unclassified")
        if not os.path.exists(unclass_root):
            os.makedirs(unclass_root)
            self.db.update_folder_display_config("Unclassified", folder_type='package')
            
        name = os.path.basename(path)
        dest = os.path.join(unclass_root, name)
        
        if os.path.exists(dest):
             QMessageBox.warning(self, "Conflict", f"Target {dest} already exists.")
             return
             
        try:
            shutil.move(path, dest)
            self.logger.info(f"Moved {name} to Unclassified")
            self._refresh_current_view()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not move: {e}")
