""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を経由すること。
"""
"""
Link Master: Trash Operations Mixin
Extracted from LinkMasterWindow for modularity.
"""
import os
import time
from PyQt6.QtWidgets import QMessageBox
from src.core.lang_manager import _
from src.core.link_master.core_paths import get_trash_dir, get_trash_path_for_item
from src.core.file_handler import FileHandler

_file_handler = FileHandler()


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
            try: _file_handler.create_directory(trash_path)
            except: pass
        self._load_items_for_path(trash_path)
        self._hide_search_indicator()
        
        # Sync trash button state
        if hasattr(self, 'btn_trash'):
            self.btn_trash.setChecked(True)

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
            _file_handler.move_path(path, dest)
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
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle(_("Error"))
            msg_box.setText(_("Could not move to trash: {error}").format(error=e))
            msg_box.setIcon(QMessageBox.Icon.Critical)
            
            enhanced_styled_msg_box = """
                QMessageBox { background-color: #1e1e1e; border: 1px solid #444; color: white; }
                QLabel { color: white; font-size: 13px; background: transparent; }
                QPushButton { 
                    background-color: #3b3b3b; color: white; border: 1px solid #555; 
                    padding: 6px 16px; min-width: 80px; border-radius: 4px; font-weight: bold;
                }
                QPushButton:hover { background-color: #4a4a4a; border-color: #3498db; }
                QPushButton:pressed { background-color: #2980b9; }
            """
            msg_box.setStyleSheet(enhanced_styled_msg_box)
            msg_box.exec()

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
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle(_("Restore Failed"))
                msg_box.setText(_("Original location not known for this item."))
                msg_box.setIcon(QMessageBox.Icon.Warning)
                
                enhanced_styled_msg_box = """
                    QMessageBox { background-color: #1e1e1e; border: 1px solid #444; color: white; }
                    QLabel { color: white; font-size: 13px; background: transparent; }
                    QPushButton { 
                        background-color: #3b3b3b; color: white; border: 1px solid #555; 
                        padding: 6px 16px; min-width: 80px; border-radius: 4px; font-weight: bold;
                    }
                    QPushButton:hover { background-color: #4a4a4a; border-color: #3498db; }
                    QPushButton:pressed { background-color: #2980b9; }
                """
                msg_box.setStyleSheet(enhanced_styled_msg_box)
                msg_box.exec()
                return
            
            dest_abs = os.path.join(storage_root, origin_rel)
            
            dest_parent = os.path.dirname(dest_abs)
            if not os.path.exists(dest_parent):
                _file_handler.create_directory(dest_parent)
            
            if os.path.exists(dest_abs):
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle(_("Conflict"))
                msg_box.setText(_("Restore failed: {path} already exists.").format(path=dest_abs))
                msg_box.setIcon(QMessageBox.Icon.Warning)
                
                enhanced_styled_msg_box = """
                    QMessageBox { background-color: #1e1e1e; border: 1px solid #444; color: white; }
                    QLabel { color: white; font-size: 13px; background: transparent; }
                    QPushButton { 
                        background-color: #3b3b3b; color: white; border: 1px solid #555; 
                        padding: 6px 16px; min-width: 80px; border-radius: 4px; font-weight: bold;
                    }
                    QPushButton:hover { background-color: #4a4a4a; border-color: #3498db; }
                    QPushButton:pressed { background-color: #2980b9; }
                """
                msg_box.setStyleSheet(enhanced_styled_msg_box)
                msg_box.exec()
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
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle(_("Error"))
            msg_box.setText(_("Could not restore: {error}").format(error=e))
            msg_box.setIcon(QMessageBox.Icon.Critical)
            
            enhanced_styled_msg_box = """
                QMessageBox { background-color: #1e1e1e; border: 1px solid #444; color: white; }
                QLabel { color: white; font-size: 13px; background: transparent; }
                QPushButton { 
                    background-color: #3b3b3b; color: white; border: 1px solid #555; 
                    padding: 6px 16px; min-width: 80px; border-radius: 4px; font-weight: bold;
                }
                QPushButton:hover { background-color: #4a4a4a; border-color: #3498db; }
                QPushButton:pressed { background-color: #2980b9; }
            """
            msg_box.setStyleSheet(enhanced_styled_msg_box)
            msg_box.exec()
    
    def _do_restore_move(self, src_path, dest_abs, rel_path):
        """Actually move the file from trash to original location."""
        try:
            _file_handler.move_path(src_path, dest_abs)
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
            _file_handler.create_directory(unclass_root)
            self.db.update_folder_display_config("Unclassified", folder_type='package')
            
        name = os.path.basename(path)
        dest = os.path.join(unclass_root, name)
        
        if os.path.exists(dest):
             msg_box = QMessageBox(self)
             msg_box.setWindowTitle(_("Conflict"))
             msg_box.setText(_("Target {path} already exists.").format(path=dest))
             msg_box.setIcon(QMessageBox.Icon.Warning)
             
             enhanced_styled_msg_box = """
                 QMessageBox { background-color: #1e1e1e; border: 1px solid #444; color: white; }
                 QLabel { color: white; font-size: 13px; background: transparent; }
                 QPushButton { 
                     background-color: #3b3b3b; color: white; border: 1px solid #555; 
                     padding: 6px 16px; min-width: 80px; border-radius: 4px; font-weight: bold;
                 }
                 QPushButton:hover { background-color: #4a4a4a; border-color: #3498db; }
                 QPushButton:pressed { background-color: #2980b9; }
             """
             msg_box.setStyleSheet(enhanced_styled_msg_box)
             msg_box.exec()
             return
             
        try:
            _file_handler.move_path(path, dest)
            self.logger.info(f"Moved {name} to Unclassified")
            self._refresh_current_view()
        except Exception as e:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle(_("Error"))
            msg_box.setText(_("Could not move: {error}").format(error=e))
            msg_box.setIcon(QMessageBox.Icon.Critical)
            
            enhanced_styled_msg_box = """
                QMessageBox { background-color: #1e1e1e; border: 1px solid #444; color: white; }
                QLabel { color: white; font-size: 13px; background: transparent; }
                QPushButton { 
                    background-color: #3b3b3b; color: white; border: 1px solid #555; 
                    padding: 6px 16px; min-width: 80px; border-radius: 4px; font-weight: bold;
                }
                QPushButton:hover { background-color: #4a4a4a; border-color: #3498db; }
                QPushButton:pressed { background-color: #2980b9; }
            """
            msg_box.setStyleSheet(enhanced_styled_msg_box)
            msg_box.exec()
