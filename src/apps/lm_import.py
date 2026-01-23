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
import json  # Added for password history
import subprocess
from PyQt6.QtWidgets import QFileDialog, QLineEdit # Added QLineEdit explicitly
from src.core.lang_manager import _


class LMImportMixin:
    """ドラッグ&ドロップとインポート処理を担当するMixin。"""
    
    # === Password History Helpers ===
    def _get_password_history(self):
        """Retrieve password history for current app."""
        try:
            if hasattr(self, 'app_combo') and self.app_combo.count() > 0:
                data = self.app_combo.currentData()
                if data:
                    raw = data.get('password_list', '[]')
                    try:
                        return json.loads(raw) if raw else []
                    except json.JSONDecodeError:
                        return []
        except Exception as e:
            self.logger.warning(f"Failed to load password history: {e}")
        return []

    def _save_password_history(self, password):
        """Phase 19: Adds a password to the history for the CURRENT application."""
        try:
            if not password: return
            app_data = self.app_combo.currentData()
            if not app_data: return
            
            history = self._get_password_history()
            if password in history:
                history.remove(password)
            history.insert(0, password)
            
            new_json = json.dumps(history)
            
            # Phase 28/43: Update Registry AND UI Cache immediately
            if hasattr(self, 'registry'):
                self.registry.update_app(app_data['id'], {"password_list": new_json})
            
            if hasattr(self, '_sync_app_data_to_ui'):
                self._sync_app_data_to_ui(app_data['id'], {"password_list": new_json})
                
            self.logger.info(f"Saved password to history for {app_data['name']}")
        except Exception as e:
            self.logger.error(f"Failed to save password history: {e}")

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
        
        target_type = "auto" # Default to auto detection (user request)
        widget = self.childAt(pos)
        while widget:
            if widget == self.cat_scroll:
                target_type = "category"
                break
            if widget == self.pkg_scroll:
                target_type = "package"
                break
            widget = widget.parentWidget()

        changes_occurred = False
        for url in urls:
            path = url.toLocalFile()
            if os.path.exists(path):
                if self._handle_drop(path, target_type):
                    changes_occurred = True
        
        # Block signals to prevent unneeded re-scans
        self.search_bar.blockSignals(True)
        self.tag_bar.blockSignals(True)
        self.search_bar.clear()
        self.tag_bar.clear_selection()
        self.search_bar.blockSignals(False)
        self.tag_bar.blockSignals(False)
        
        # Optimized Refresh (Only if changes happened)
        if changes_occurred:
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
                # User Request: Open Target Folder or Target Category
                # This is usually the currently viewed path in the file manager
                target_path = getattr(self, 'current_path', None)
                
                # Fallback to storage_root if current_path is invalid/empty (e.g. at root)
                if not target_path or not os.path.exists(target_path):
                    app_data = self.app_combo.currentData()
                    if app_data:
                        target_path = app_data.get('storage_root')
                
                if target_path and os.path.exists(target_path):
                    subprocess.Popen(['explorer', os.path.normpath(target_path)])
                else:
                    self.logger.warning(f"Could not open explorer. Target path invalid: {target_path}")
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
        
        # If target_type is 'auto', we DO NOT resolve it here.
        # We let it pass through to the DB as 'auto', so the runtime scanner/display logic
        # handles the classification (package vs folder).
        # User explicitly requested preserving the 'auto' state.
        
        # Handle Archives (Zip / 7z / Rar)
        ext = os.path.splitext(source_path)[1].lower()
        img_exts = ['.png', '.jpg', '.jpeg', '.webp', '.bmp']
        
        if ext in img_exts:
            # Phase 66: Image Drop to Folder Import
            from src.ui.common_widgets import FramelessMessageBox
            msg = FramelessMessageBox(self)
            msg.setWindowTitle(_("Create Folder from Image"))
            msg.setText(_("Would you like to create an empty folder named '{name}' and use this image as its icon?").format(name=folder_name))
            msg.setIcon(FramelessMessageBox.Icon.Question)
            
            # 3-Choice UI: Normal, Prefix, Cancel
            # Using Yes/No/Cancel as proxies for Normal/Prefix/Cancel
            # Actually, let's use custom buttons if possible, or just re-mapped StandardButtons
            btn_normal = msg.addButton(_("Yes (Normal)"), FramelessMessageBox.ButtonRole.YesRole)
            btn_prefix = msg.addButton(_("Yes (\ue000\ue001_ Prefix)"), FramelessMessageBox.ButtonRole.YesRole)
            btn_cancel = msg.addButton(_("No / Cancel"), FramelessMessageBox.ButtonRole.NoRole)
            
            msg.setDefaultButton(btn_normal)
            msg.exec()
            
            clicked = msg.clickedButton()
            if clicked == btn_cancel:
                return False
            
            use_prefix = (clicked == btn_prefix)
            
            base_name = os.path.splitext(folder_name)[0]
            if use_prefix:
                base_name = f"\ue000\ue001_{base_name}"
            
            dest_path = os.path.join(target_dir, base_name)
            
            # Ensure unique name
            if os.path.exists(dest_path):
                import time
                dest_path = f"{dest_path}_{int(time.time())}"
                base_name = os.path.basename(dest_path)
            
            try:
                # 1. Create Empty Folder
                os.makedirs(dest_path, exist_ok=True)
                self.logger.info(f"Created empty folder from image drop: {dest_path}")
                
                # 2. Copy Image to Icon Cache
                # We reuse the logic from FolderPropertiesDialog or similar
                from src.core.file_handler import get_user_data_path, ensure_dir
                import hashlib
                import time
                import shutil
                
                app_name = app_data.get('name', 'Unknown')
                cache_dir = get_user_data_path(os.path.join("resource", "app", app_name, ".icon_cache"))
                ensure_dir(cache_dir)
                
                unique_key = f"{source_path}_{time.time()}"
                hash_name = hashlib.md5(unique_key.encode()).hexdigest()[:12]
                cache_ext = os.path.splitext(source_path)[1].lower()
                cache_filename = f"drop_{hash_name}{cache_ext}"
                cache_path = os.path.join(cache_dir, cache_filename)
                
                shutil.copy2(source_path, cache_path)
                self.logger.info(f"Copied dropped image to icon cache: {cache_path}")
                
                # 3. Register in DB with image_path
                abs_dest = os.path.abspath(dest_path)
                abs_storage = os.path.abspath(self.storage_root)
                rel_path = os.path.relpath(abs_dest, abs_storage).replace('\\', '/')
                
                self.db.update_folder_display_config(
                    rel_path,
                    display_name=base_name,
                    image_path=cache_path,
                    folder_type=target_type,
                    is_visible=1
                )
                self.logger.info(f"Registered folder with image icon: {rel_path}")
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to create folder from image drop: {e}")
                msg_err = FramelessMessageBox(self)
                msg_err.setWindowTitle(_("Error"))
                msg_err.setText(_("Failed to create folder: {error}").format(error=e))
                msg_err.setIcon(FramelessMessageBox.Icon.Critical)
                msg_err.exec()
                return False

        elif ext in ['.zip', '.7z', '.rar']:
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
                    return False

            except Exception as e:
                from src.ui.common_widgets import FramelessMessageBox
                msg = FramelessMessageBox(self)
                msg.setWindowTitle(_("Error"))
                msg.setText(_("Failed to extract archive: {error}").format(error=e))
                msg.setIcon(FramelessMessageBox.Icon.Critical)
                msg.setStandardButtons(FramelessMessageBox.StandardButton.Ok)
                msg.exec()
                return False


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
                msg.setStandardButtons(FramelessMessageBox.StandardButton.Ok)
                msg.exec()
                return False
        else:
            return False

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
        return True

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
            # Specific password handling
            if "Password is required" in str(e):
                 from PyQt6.QtWidgets import QLineEdit
                 from src.ui.common_widgets import FramelessInputDialog
                 
                 history = self._get_password_history()
                 
                 while True:
                    pwd, ok = FramelessInputDialog.getText(
                        self, _("Password Required"),
                        _("Enter password for {file}:").format(file=os.path.basename(source_path)),
                        mode=QLineEdit.EchoMode.Password,
                        history=history,
                        allow_auto_try=True if history else False
                    )
                    if not ok:
                        return False
                    
                    # Handle Auto-Try Request
                    if pwd == "<AUTO_TRY>":
                         self.logger.info("User requested Brute Force from History...")
                         found = False
                         for h_pwd in history:
                             try:
                                 with py7zr.SevenZipFile(source_path, mode='r', password=h_pwd) as z:
                                     z.extractall(path=dest_path)
                                 self.logger.info(f"Auto-unlocked with history password.")
                                 self._save_password_history(h_pwd)
                                 # Move to top happens in save
                                 found = True
                                 break
                             except Exception:
                                 continue
                         
                         if found:
                             return True
                         else:
                             from src.ui.common_widgets import FramelessMessageBox
                             msg = FramelessMessageBox(self)
                             msg.setWindowTitle(_("Failed"))
                             msg.setText(_("No valid password found in history."))
                             msg.setStandardButtons(FramelessMessageBox.StandardButton.Ok)
                             msg.exec()
                             continue # Re-prompt
                    
                    try:
                        with py7zr.SevenZipFile(source_path, mode='r', password=pwd) as z:
                            z.extractall(path=dest_path)
                        self._save_password_history(pwd)
                        return True
                    except py7zr.exceptions.PasswordRequired:
                        continue # Retry
                    except Exception as e_retry:
                        self.logger.error(f"7z extraction error (retry): {e_retry}")
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
            # Specific password handling
            if "Password required" in str(e) or "Bad password" in str(e):
                 from PyQt6.QtWidgets import QLineEdit
                 from src.ui.common_widgets import FramelessInputDialog
                 
                 history = self._get_password_history()

                 while True:
                    pwd, ok = FramelessInputDialog.getText(
                        self, _("Password Required"),
                        _("Enter password for {file}:").format(file=os.path.basename(source_path)),
                        mode=QLineEdit.EchoMode.Password,
                        history=history,
                        allow_auto_try=True if history else False
                    )
                    if not ok:
                        return False

                    # Handle Auto-Try Request
                    if pwd == "<AUTO_TRY>":
                         self.logger.info("User requested Brute Force from History (RAR)...")
                         found = False
                         for h_pwd in history:
                             try:
                                with rarfile.RarFile(source_path) as rf:
                                    rf.setpassword(h_pwd)
                                    rf.extractall(dest_path)
                                self.logger.info(f"Auto-unlocked with history password.")
                                self._save_password_history(h_pwd)
                                found = True
                                break
                             except (rarfile.PasswordRequired, rarfile.BadRarFile):
                                continue
                             except Exception:
                                continue
                         
                         if found: 
                             return True
                         else:
                             from src.ui.common_widgets import FramelessMessageBox
                             msg = FramelessMessageBox(self)
                             msg.setWindowTitle(_("Failed"))
                             msg.setText(_("No valid password found in history."))
                             msg.setStandardButtons(FramelessMessageBox.StandardButton.Ok)
                             msg.exec()
                             continue

                    try:
                        with rarfile.RarFile(source_path) as rf:
                            rf.setpassword(pwd)
                            rf.extractall(dest_path)
                        self._save_password_history(pwd)
                        return True
                    except (rarfile.PasswordRequired, rarfile.BadRarFile) as e_retry:
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
                    
                    # Capture BOTH stdout and stderr
                    result = subprocess.run(cmd, startupinfo=si, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    
                    if result.returncode == 0:
                        return True
                    
                    # 7-Zip Return Codes:
                    # 0: OK, 1: Warning, 2: Fatal Error, 7: Command line error, 8: Memory error, 255: User stopped
                    # Password errors usually result in code 2.
                    all_out = (result.stdout + result.stderr).lower()
                    is_pwd_err = any(x in all_out for x in ["password", "encrypted", "wrong", "パスワード", "暗号"])
                    
                    if is_pwd_err or result.returncode == 2:
                         from PyQt6.QtWidgets import QLineEdit
                         from src.ui.common_widgets import FramelessInputDialog
                         
                         history = self._get_password_history()
                         
                         while True:
                            pwd, ok = FramelessInputDialog.getText(
                                self, _("Password Required"),
                                _("Enter password for {file} (External 7-Zip):").format(file=os.path.basename(source_path)),
                                mode=QLineEdit.EchoMode.Password,
                                history=history,
                                allow_auto_try=True if history else False
                            )
                            if not ok:
                                return False
                            
                            # Handle Auto-Try Request
                            if pwd == "<AUTO_TRY>":
                                 self.logger.info("User requested Brute Force from History (Ext 7z)...")
                                 found = False
                                 for h_pwd in history:
                                     cmd_try = [exe, 'x', source_path, f'-o{dest_path}', f'-p{h_pwd}', '-y']
                                     res_try = subprocess.run(cmd_try, startupinfo=si, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                     if res_try.returncode == 0:
                                         self.logger.info(f"Auto-unlocked with history password.")
                                         self._save_password_history(h_pwd)
                                         found = True
                                         break
                                 
                                 if found:
                                     return True
                                 else:
                                     from src.ui.common_widgets import FramelessMessageBox
                                     msg = FramelessMessageBox(self)
                                     msg.setWindowTitle(_("Failed"))
                                     msg.setText(_("No valid password found in history."))
                                     msg.setStandardButtons(FramelessMessageBox.StandardButton.Ok)
                                     msg.exec()
                                     continue

                            # Retry with password
                            cmd_pwd = [exe, 'x', source_path, f'-o{dest_path}', f'-p{pwd}', '-y']
                            res_retry = subprocess.run(cmd_pwd, startupinfo=si, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                            
                            if res_retry.returncode == 0:
                                self._save_password_history(pwd)
                                return True
                            
                            out_retry = (res_retry.stdout + res_retry.stderr).lower()
                            if any(x in out_retry for x in ["wrong", "password", "パスワード"]):
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
                    dest_arg = dest_path if dest_path.endswith(os.sep) else dest_path + os.sep
                    cmd = [exe, 'x', '-ibck', '-inul', source_path, dest_arg]
                    
                    si = subprocess.STARTUPINFO()
                    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    
                    result = subprocess.run(cmd, startupinfo=si, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    
                    if result.returncode == 0:
                        return True
                        
                    # WinRAR Exit Codes:
                    # 0: Success, 1: Warning, 2: Fatal error, 11: Locked/Wrong password
                    all_out = (result.stdout + result.stderr).lower()
                    is_pwd_err = (result.returncode == 11) or any(x in all_out for x in ["password", "encrypted", "locked", "パスワード"])

                    if is_pwd_err:
                         from PyQt6.QtWidgets import QLineEdit
                         from src.ui.common_widgets import FramelessInputDialog
                         
                         history = self._get_password_history()
                         
                         while True:
                            pwd, ok = FramelessInputDialog.getText(
                                self, _("Password Required"),
                                _("Enter password for {file} (External WinRAR):").format(file=os.path.basename(source_path)),
                                mode=QLineEdit.EchoMode.Password,
                                history=history,
                                allow_auto_try=True if history else False
                            )
                            if not ok:
                                return False
                            
                            # Handle Auto-Try Request
                            if pwd == "<AUTO_TRY>":
                                 self.logger.info("User requested Brute Force from History (Ext WinRAR)...")
                                 found = False
                                 for h_pwd in history:
                                     # winrar uses -p<pwd>
                                     cmd_try = [exe, 'x', '-ibck', '-inul', f'-p{h_pwd}', source_path, dest_arg]
                                     res_try = subprocess.run(cmd_try, startupinfo=si)
                                     if res_try.returncode == 0:
                                         self.logger.info(f"Auto-unlocked with history password.")
                                         self._save_password_history(h_pwd)
                                         found = True
                                         break
                                 
                                 if found:
                                     return True
                                 continue # fail message already shown? No, let's keep it consistent

                            # Retry with password
                            cmd_pwd = [exe, 'x', '-ibck', '-inul', f'-p{pwd}', source_path, dest_arg]
                            res_retry = subprocess.run(cmd_pwd, startupinfo=si)
                            if res_retry.returncode == 0:
                                self._save_password_history(pwd)
                                return True
                            
                            if res_retry.returncode == 11:
                                continue
                            else:
                                break

                except Exception as e:
                    self.logger.error(f"External WinRAR execution failed: {e}")
                    continue
        
        return False
                    
        return False
