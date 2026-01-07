"""
Link Master: Preset Management Mixin
Extracted from LinkMasterWindow for modularity.
"""
import os
from PyQt6.QtWidgets import QMessageBox, QInputDialog


class LMPresetsMixin:
    """Mixin providing preset management methods for LinkMasterWindow."""
    
    def _create_preset(self):
        if not self.current_app_id: return
        
        app_data = self.app_combo.currentData()
        storage_root = app_data.get('storage_root')
        target_root = app_data.get(self.current_target_key)
        
        if not storage_root or not target_root: return
        
        active_items = []
        storage_root_norm = os.path.normcase(os.path.abspath(storage_root))
        if storage_root_norm.startswith("\\\\?\\"): storage_root_norm = storage_root_norm[4:]
        if not storage_root_norm.endswith(os.sep): storage_root_norm += os.sep
        
        count = 0 
        try:
            with os.scandir(target_root) as it:
                for entry in it:
                    # Skip .bak files and non-symlinks
                    if not entry.is_symlink():
                        continue
                    if entry.name.endswith('.bak') or '.bak_' in entry.name:
                        continue
                        
                    try:
                        real_target = os.readlink(entry.path)
                        if not os.path.isabs(real_target):
                            real_target = os.path.join(target_root, real_target)
                        
                        real_abs = os.path.abspath(real_target)
                        if real_abs.startswith("\\\\?\\"):
                            real_abs = real_abs[4:]
                        real_norm = os.path.normcase(real_abs)
                        
                        if real_norm.startswith(storage_root_norm):
                            rel_path = os.path.relpath(real_abs, os.path.abspath(storage_root))
                            item = {
                                "name": entry.name,
                                "storage_rel_path": rel_path
                            }
                            active_items.append(item)
                            count += 1
                    except OSError:
                        pass
        except OSError as e:
            self.logger.error(f"Failed to scan target for links: {e}")

        if count == 0:
            QMessageBox.warning(self, "Empty", "No active links found to save.")
            return

        # UI for Name only (Folder and Description skipped for now)
        name, ok = QInputDialog.getText(self, "プリセット保存", "プリセット名:")
        if not ok or not name: return
        
        item_ids = []
        for item in active_items:
            item_id = self.db.get_or_create_item(item['name'], item['storage_rel_path'])
            item_ids.append(item_id)
            
        try:
            self.db.create_preset(name, item_ids)
            QMessageBox.information(self, "成功", f"プリセット '{name}' を {count} アイテムで作成しました！")
            self.presets_panel.refresh()
        except Exception as e:
            QMessageBox.critical(self, "エラー", str(e))

    def _load_preset(self, preset_id):
        items = self.db.get_preset_items(preset_id)
        if not items: return
        
        app_data = self.app_combo.currentData()
        target_root = app_data.get(self.current_target_key)
        storage_root = app_data.get('storage_root')
        if not target_root: return
        
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Load Preset")
        msg_box.setText("How would you like to load this preset?")
        msg_box.setInformativeText("Replace: Removes ALL existing links for this app first.\nAppend: Adds to existing links (conflicts skipped).")
        
        btn_replace = msg_box.addButton("Replace All", QMessageBox.ButtonRole.DestructiveRole)
        btn_append = msg_box.addButton("Append / Add", QMessageBox.ButtonRole.AcceptRole)
        btn_cancel = msg_box.addButton(QMessageBox.StandardButton.Cancel)
        
        msg_box.exec()
        
        clicked = msg_box.clickedButton()
        if clicked == btn_cancel:
            return
            
        if clicked == btn_replace:
            self.deployer.cleanup_links_in_target(target_root, storage_root)
        
        success_count = 0
        skipped_count = 0
        preset_paths = set()
        preset_categories = set()
        
        links_to_create = []
        is_append_mode = (clicked == btn_append)
        
        for item in items:
            rel_path = item['storage_rel_path']
            source = os.path.join(storage_root, rel_path)
            target = os.path.join(target_root, item['name']) 
            
            # In append mode, skip if target already exists (don't create .bak)
            if is_append_mode and os.path.exists(target):
                skipped_count += 1
                continue
            
            links_to_create.append((source, target))
            
            preset_paths.add(rel_path)
            parts = rel_path.replace('/', os.sep).split(os.sep)
            if len(parts) >= 1:
                preset_categories.add(parts[0])
        
        if links_to_create:
            self.logger.info(f"Loading preset in parallel ({len(links_to_create)} items)...")
            results = self.deployer.deploy_links_batch(links_to_create, 'backup' if not is_append_mode else 'skip')
            success_count = sum(1 for r in results if r['status'] == 'success')
            error_count = sum(1 for r in results if r['status'] == 'error')
            if error_count > 0:
                self.logger.error(f"Preset load had {error_count} errors.")
                
        QMessageBox.information(self, "Deployed", f"Deployed {success_count}/{len(items)} items from preset.")
        
        self.preset_filter_mode = True
        self.preset_filter_paths = preset_paths
        self.preset_filter_categories = preset_categories
        self.presets_panel.clear_filter_btn.show()
        
        self._on_app_changed(self.app_combo.currentIndex())

    def _preview_preset(self, preset_id):
        """Preview items in a preset before loading them."""
        items = self.db.get_preset_items(preset_id)
        if not items: 
            self.preset_filter_mode = False
            self.preset_filter_paths = set()
            self.preset_filter_categories = set()
            self.presets_panel.clear_filter_btn.hide()
            self._on_app_changed(self.app_combo.currentIndex())
            return
            
        preset_paths = set()
        preset_categories = set()
        
        for item in items:
            rel_path = item['storage_rel_path'].replace('\\', '/')
            preset_paths.add(rel_path)
            
            parts = rel_path.split('/')
            # Add parent category paths for nested items
            if len(parts) > 1:
                for i in range(1, len(parts)):
                    cat_p = '/'.join(parts[:i])
                    preset_categories.add(cat_p)
            # Also add the item's own path if it's a category (single folder without subpath)
            # This handles directly linked categories
            if len(parts) == 1:
                preset_categories.add(rel_path)

        
        self.preset_filter_mode = True
        self.preset_filter_paths = preset_paths
        self.preset_filter_categories = preset_categories
        self.current_preset_id = preset_id
        self.presets_panel.clear_filter_btn.setText("🔓 絞り込み解除")
        self.presets_panel.clear_filter_btn.show()
        
        # Phase 28: Use rebuild instead of on_app_changed to preserve current path
        self._rebuild_current_view()
        
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, lambda: self.presets_panel.focus_preset(preset_id))
        
        total_in_preset = len(self.preset_filter_paths)
        self.pkg_result_label.setText(f"(0/{total_in_preset})")

    def _delete_preset(self, preset_id):
        try:
            self.db.delete_preset(preset_id)
            self.presets_panel.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to delete: {e}")

    def _clear_preset_filter(self):
        """Clear preset filter mode and show all items."""
        self.preset_filter_mode = False
        self.preset_filter_paths = set()
        self.preset_filter_categories = set()
        self.presets_panel.clear_filter_btn.hide()
        # Phase 28: Use rebuild to properly reset category view
        self._rebuild_current_view()

    def _unload_active_links(self):
        """Removes all symlinks in target directory that belong to current app/storage."""
        app_data = self.app_combo.currentData()
        if not app_data: return
        target_root = app_data.get(self.current_target_key)
        storage_root = app_data.get('storage_root')
        if not target_root or not storage_root: return
        
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Unload Links")
        msg_box.setText("Are you sure you want to remove ALL active symlinks for this app?")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        
        # Style to match dark theme and ensure visibility
        msg_box.setStyleSheet("""
            QMessageBox { background-color: #2b2b2b; }
            QLabel { color: #ffffff; }
            QPushButton { 
                background-color: #3b3b3b; color: #ffffff; 
                border: 1px solid #555; border-radius: 4px; padding: 4px 12px;
            }
            QPushButton:hover { background-color: #4a4a4a; }
        """)
        
        reply = msg_box.exec()
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.deployer.cleanup_links_in_target(target_root, storage_root)
                QMessageBox.information(self, "Success", "All links unloaded.")
                self._on_app_changed(self.app_combo.currentIndex()) # Refresh view
                
                # Phase 28/Debug: Explicitly clear all highlight borders after bulk unlink
                if hasattr(self, '_refresh_tag_visuals'):
                    self._refresh_tag_visuals()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Unload failed: {e}")

