"""
Link Master: Import Mixin
ドラッグ&ドロップとインポートダイアログのハンドラー。

依存するコンポーネント:
- ImportTypeDialog (src/ui/link_master/dialogs/)
- QFileDialog

依存する親クラスの属性:
- app_combo, current_view_path, current_path, storage_root
- preset_filter_mode, db, logger, deployer
- cat_scroll, pkg_scroll, search_bar, tag_bar
"""
import os
import shutil
import zipfile
import subprocess
from PyQt6.QtWidgets import QFileDialog, QMessageBox


class LMImportMixin:
    """ドラッグ&ドロップとインポート処理を担当するMixin。"""
    
    def dragEnterEvent(self, event):
        """Accept drag events with URLs."""
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Handle drop events for folders and zips."""
        urls = event.mimeData().urls()
        if not urls: return
        
        # Auto-disable preset filter to ensure new items are visible
        if self.preset_filter_mode:
            self.preset_filter_mode = False
            self.logger.info("Preset filter disabled automatically for drop/import")
        
        # Determine target area based on drop position
        pos = event.position().toPoint()
        
        target_type = "package"
        widget = self.childAt(pos)
        while widget:
            if widget == self.cat_scroll:
                target_type = "category"
                break
            if widget == self.pkg_scroll:
                target_type = "package"
                break
            widget = widget.parentWidget()

        for url in urls:
            path = url.toLocalFile()
            if os.path.exists(path):
                self._handle_drop(path, target_type)
        
        # Block signals to prevent unneeded re-scans
        self.search_bar.blockSignals(True)
        self.tag_bar.blockSignals(True)
        self.search_bar.clear()
        self.tag_bar.clear_selection()
        self.search_bar.blockSignals(False)
        self.tag_bar.blockSignals(False)
        
        # Optimized Refresh
        if target_type == "package" and getattr(self, 'current_path', None):
            self._on_category_selected(self.current_path, force=True)
            self._refresh_category_cards()
        else:
            self._refresh_current_view()

    def _open_import_dialog(self, target_type):
        """Opens a custom dark-themed dialog to select import type or open explorer."""
        from src.ui.link_master.dialogs import ImportTypeDialog
        
        dialog = ImportTypeDialog(self, target_type)
        if dialog.exec():
            result = dialog.get_result()
            
            if result == "explorer":
                app_data = self.app_combo.currentData()
                if not app_data: return
                storage_root = app_data.get('storage_root')
                
                target_path = getattr(self, 'current_path', storage_root)
                if target_path and os.path.exists(target_path):
                    subprocess.Popen(['explorer', os.path.normpath(target_path)])
                return

            if result == "folder":
                path = QFileDialog.getExistingDirectory(self, f"Select Folder to Import as {target_type}")
            elif result == "zip":
                path, _filter = QFileDialog.getOpenFileName(self, f"Select Zip to Import as {target_type}", "", "Zip Files (*.zip);;All Files (*.*)")
            else:
                return

            if path:
                if self.preset_filter_mode:
                    self.preset_filter_mode = False
                self._handle_drop(path, target_type)
                # Optimized Refresh
                if target_type == "package" and getattr(self, 'current_path', None):
                    self.search_bar.blockSignals(True)
                    self.tag_bar.blockSignals(True)
                    self._on_category_selected(self.current_path, force=True)
                    self.search_bar.blockSignals(False)
                    self.tag_bar.blockSignals(False)
                    self._refresh_category_cards()
                else:
                    self._refresh_current_view()

    def _handle_drop(self, source_path: str, target_type: str):
        """Processes a dropped folder or zip file."""
        app_data = self.app_combo.currentData()
        if not app_data or not self.current_view_path: return
        
        storage_root = app_data.get('storage_root')
        target_root = app_data.get(self.current_target_key)
        
        # Determine target directory based on context
        current_path = getattr(self, 'current_path', None)
        if target_type == "package" and current_path and os.path.isdir(current_path):
            target_dir = current_path
            self.logger.info(f"Targeting active category for package drop: {target_dir}")
        else:
            target_dir = self.current_view_path
            self.logger.info(f"Targeting current view path: {target_dir}")
        
        # Defensive Check: Don't copy into game folder
        if target_root and os.path.abspath(target_dir) == os.path.abspath(target_root):
            self.logger.warning(f"Drop target was target_root! Redirecting to storage_root: {storage_root}")
            target_dir = storage_root
            if hasattr(self, 'current_view_path'):
                self.current_view_path = storage_root
        
        folder_name = os.path.basename(source_path)
        
        # Handle Zip
        if source_path.lower().endswith('.zip'):
            folder_name = os.path.splitext(folder_name)[0]
            dest_path = os.path.join(target_dir, folder_name)
            
            if os.path.exists(dest_path):
                import time
                dest_path = f"{dest_path}_{int(time.time())}"
                folder_name = os.path.basename(dest_path)
            
            try:
                with zipfile.ZipFile(source_path, 'r') as zip_ref:
                    zip_ref.extractall(dest_path)
                self.logger.info(f"Extracted {source_path} to {dest_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to extract zip: {e}")
                return
        # Handle Folder
        elif os.path.isdir(source_path):
            dest_path = os.path.join(target_dir, folder_name)
            
            if os.path.exists(dest_path):
                import time
                dest_path = f"{dest_path}_{int(time.time())}"
                folder_name = os.path.basename(dest_path)
                
            try:
                shutil.copytree(source_path, dest_path)
                self.logger.info(f"Copied folder {source_path} to {dest_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to copy folder: {e}")
                return
        else:
            return

        # Register in Database
        abs_dest = os.path.abspath(dest_path)
        abs_storage = os.path.abspath(self.storage_root)
        
        try:
            rel_path = os.path.relpath(abs_dest, abs_storage).replace('\\', '/')
            if rel_path == ".": rel_path = ""
        except Exception as e:
            self.logger.error(f"Path Normalization Error: {e}")
            rel_path = folder_name
            
        self.logger.info(f"Normalized Registration: dest={abs_dest} | storage={abs_storage} | rel={rel_path}")

        self.db.update_folder_display_config(
            rel_path,
            display_name=folder_name,
            folder_type=target_type,
            is_visible=1
        )
        self.logger.info(f"Registered dropped item as {target_type}: {rel_path}")
