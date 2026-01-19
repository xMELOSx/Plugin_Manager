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
from PyQt6.QtWidgets import QFileDialog
from src.core.lang_manager import _


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
                type_name = _("Folder") if target_type == "category" else _("Package")
                path = QFileDialog.getExistingDirectory(self, _("Select Folder to Import as {type}").format(type=type_name))
                paths = [path] if path else []
            elif result == "archive":
                type_name = _("Folder") if target_type == "category" else _("Package")
                paths, _filter = QFileDialog.getOpenFileNames(
                    self, 
                    _("Select Archive(s) to Import as {type}").format(type=type_name), 
                    "", 
                    _("Archives (*.zip *.7z *.rar);;Zip Files (*.zip);;7z Files (*.7z);;Rar Files (*.rar);;All Files (*.*)")
                )
            else:
                return

            if paths:
                if self.preset_filter_mode:
                    self.preset_filter_mode = False
                
                for path in paths:
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
        
        # Handle Archives (Zip / 7z / Rar)
        ext = os.path.splitext(source_path)[1].lower()
        if ext in ['.zip', '.7z', '.rar']:
            folder_name = os.path.splitext(folder_name)[0]
            dest_path = os.path.join(target_dir, folder_name)
            
            if os.path.exists(dest_path):
                import time
                dest_path = f"{dest_path}_{int(time.time())}"
                folder_name = os.path.basename(dest_path)
            
            self.logger.info(f"Extracting archive {source_path} to {dest_path}")
            
            try:
                success = False
                if ext == '.zip':
                    with zipfile.ZipFile(source_path, 'r') as zip_ref:
                        zip_ref.extractall(dest_path)
                    success = True
                        
                elif ext == '.7z':
                    if self._extract_7z_internal(source_path, dest_path):
                        success = True
                    else:
                        success = self._extract_with_external(source_path, dest_path)

                elif ext == '.rar':
                    if self._extract_rar_internal(source_path, dest_path):
                        success = True
                    else:
                        success = self._extract_with_external(source_path, dest_path)

                if success:
                    self.logger.info(f"Successfully extracted {source_path}")
                else:
                    from src.ui.common_widgets import FramelessMessageBox
                    msg = FramelessMessageBox(self)
                    msg.setWindowTitle(_("Extraction Failed"))
                    msg.setText(_("Failed to extract archive. Please ensure py7zr/rarfile is installed OR WinRAR/7-Zip is available."))
                    msg.setIcon(FramelessMessageBox.Icon.Warning)
                    msg.setStandardButtons(FramelessMessageBox.StandardButton.Ok)
                    msg.exec()
                    return

            except Exception as e:
                from src.ui.common_widgets import FramelessMessageBox
                msg = FramelessMessageBox(self)
                msg.setWindowTitle(_("Error"))
                msg.setText(_("Failed to extract archive: {error}").format(error=e))
                msg.setIcon(FramelessMessageBox.Icon.Critical)
                msg.setStandardButtons(FramelessMessageBox.StandardButton.Ok)
                msg.exec()
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
                from src.ui.common_widgets import FramelessMessageBox
                msg = FramelessMessageBox(self)
                msg.setWindowTitle(_("Error"))
                msg.setText(_("Failed to copy folder: {error}").format(error=e))
                msg.setIcon(FramelessMessageBox.Icon.Critical)
                msg.setStandardButtons(FramelessMessageBox.StandardButton.Ok)
                msg.exec()
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

    def _extract_7z_internal(self, source_path, dest_path):
        """Try extracting with py7zr."""
        try:
            import py7zr
            with py7zr.SevenZipFile(source_path, mode='r') as z:
                z.extractall(path=dest_path)
            return True
        except ImportError:
            self.logger.warning("py7zr not found. Falling back to external.")
            return False
        except Exception as e:
            # Handle Password Protection
            if "Password is required" in str(e):
                from PyQt6.QtWidgets import QLineEdit
                from src.ui.common_widgets import FramelessInputDialog
                password = None
                while True:
                    pwd, ok = FramelessInputDialog.getText(
                        self, _("Password Required"),
                        _("Enter password for {file}:").format(file=os.path.basename(source_path)),
                        mode=QLineEdit.EchoMode.Password
                    )
                    if not ok:
                        return False # User cancelled
                    
                    try:
                        with py7zr.SevenZipFile(source_path, mode='r', password=pwd) as z:
                            z.extractall(path=dest_path)
                        return True
                    except Exception as e_retry:
                        if "Password is required" in str(e_retry) or "Bad password" in str(e_retry):
                            continue # Wrong password, ask again
                        else:
                            self.logger.error(f"py7zr extraction error (retry): {e_retry}")
                            return False

            self.logger.error(f"py7zr extraction error: {e}")
            return False

    def _extract_rar_internal(self, source_path, dest_path):
        """Try extracting with rarfile."""
        try:
            import rarfile
            # Check for unrar
            try:
                rarfile.tool_setup()
            except rarfile.RarCannotExec:
                self.logger.warning("rarfile: UnRAR not found. Falling back to external.")
                return False
                
            with rarfile.RarFile(source_path) as rf:
                rf.extractall(dest_path)
            return True
        except ImportError:
            self.logger.warning("rarfile library not found. Falling back to external.")
            return False
        except Exception as e:
             # Handle Password Protection
             if "Bad password" in str(e) or "Password required" in str(e): # rarfile usually throws UnrarError or BadRarFile
                from PyQt6.QtWidgets import QLineEdit
                from src.ui.common_widgets import FramelessInputDialog
                while True:
                    pwd, ok = FramelessInputDialog.getText(
                        self, _("Password Required"),
                        _("Enter password for {file}:").format(file=os.path.basename(source_path)),
                        mode=QLineEdit.EchoMode.Password
                    )
                    if not ok:
                        return False

                    try:
                        with rarfile.RarFile(source_path) as rf:
                           rf.setpassword(pwd)
                           rf.extractall(dest_path)
                        return True
                    except Exception as e_retry:
                        # rarfile doesn't always have clean error messages for bad password, usually just "BadRarFile" or custom code
                        if "Bad password" in str(e_retry) or "crc" in str(e_retry).lower(): # CRC often fails on wrong password
                             continue
                        else:
                             self.logger.error(f"rarfile extraction error (retry): {e_retry}")
                             return False

             self.logger.error(f"rarfile extraction error: {e}")
             return False

    def _extract_with_external(self, source_path, dest_path):
        """Fallback: try to find WinRAR or 7-Zip installed on the system and use them."""
        import subprocess
        
        # 1. 7-Zip (64-bit and 32-bit candidates)
        seven_zip_paths = [
            r"C:\Program Files\7-Zip\7z.exe",
            r"C:\Program Files (x86)\7-Zip\7z.exe"
        ]
        
        for exe in seven_zip_paths:
            if os.path.exists(exe):
                try:
                    self.logger.info(f"Attempting extraction with 7-Zip: {exe}")
                    # 7z x "source" -o"dest" -y
                    # 7z x "source" -o"dest" -y
                    cmd = [exe, 'x', source_path, f'-o{dest_path}', '-y']
                    # Create startup info to hide console window
                    si = subprocess.STARTUPINFO()
                    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    
                    # Ensure stdin is closed to prevent hangs on password prompt
                    result = subprocess.run(cmd, startupinfo=si, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
                    
                    if result.returncode == 0:
                        return True
                    
                    # Check for password error in stderr
                    # 7-Zip usually prints "Wrong password" or "Enter password" if failed
                    err_out = result.stderr
                    if "Wrong password" in err_out or "Enter password" in err_out or "Can not open encrypted archive" in err_out:
                         from PyQt6.QtWidgets import QLineEdit
                         from src.ui.common_widgets import FramelessInputDialog
                         
                         while True:
                            pwd, ok = FramelessInputDialog.getText(
                                self, _("Password Required"),
                                _("Enter password for {file} (External 7-Zip):").format(file=os.path.basename(source_path)),
                                mode=QLineEdit.EchoMode.Password
                            )
                            if not ok:
                                return False
                            
                            # Retry with password
                            cmd_pwd = cmd + [f'-p{pwd}']
                            res_retry = subprocess.run(cmd_pwd, startupinfo=si, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
                            
                            if res_retry.returncode == 0:
                                return True
                            
                            err_retry = res_retry.stderr
                            if "Wrong password" in err_retry:
                                continue
                            else:
                                break # Other error
                                
 
                    continue # Try next executable or fail
                except Exception as e:
                    self.logger.error(f"External 7-Zip execution failed: {e}")
                    continue
        
        # 2. WinRAR
        winrar_paths = [
            r"C:\Program Files\WinRAR\WinRAR.exe",
            r"C:\Program Files (x86)\WinRAR\WinRAR.exe"
        ]
        
        for exe in winrar_paths:
            if os.path.exists(exe):
                try:
                    self.logger.info(f"Attempting extraction with WinRAR: {exe}")
                    # WinRAR x -ibck -inul "source" "dest\"
                    # Note: WinRAR expects dest folder to end with backslash for extraction to folder
                    dest_arg = dest_path if dest_path.endswith(os.sep) else dest_path + os.sep
                    cmd = [exe, 'x', '-ibck', '-inul', source_path, dest_arg]
                    
                    si = subprocess.STARTUPINFO()
                    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    
                    subprocess.run(cmd, check=True, startupinfo=si)
                    return True
                except subprocess.CalledProcessError:
                    continue
                    
        return False
