"""
Link Master: File Management Mixin
個別のファイル管理（ダイアログの起動とルール保存）を担当するMixin。
"""
import os
import logging
from src.ui.link_master.dialogs import FileManagementDialog

class LMFileManagementMixin:
    def _open_file_management(self, rel_path, override_rule=None):
        """指定された相対パスのフォルダに対してファイル管理ダイアログを開く。"""
        if not hasattr(self, 'db') or not self.db: return
        if not hasattr(self, 'storage_root') or not self.storage_root: return
        
        abs_path = os.path.join(self.storage_root, rel_path)
        if not os.path.exists(abs_path):
            self.logger.error(f"File management target not found: {abs_path}")
            return
            
        config = self.db.get_folder_config(rel_path) or {}
        
        # Phase 5: Get P/S paths for quick redirection
        app_data = self.app_combo.currentData() if hasattr(self, 'app_combo') else {}
        # Resolve mod-specific folders for Primary, Secondary, and Tertiary targets
        mod_name = os.path.basename(rel_path)
        primary_root = app_data.get('target_root', '')
        secondary_root = app_data.get('target_root_2', '')
        tertiary_root = app_data.get('target_root_3', '')
        
        mod_primary_base = config.get('target_override') or os.path.join(primary_root, mod_name) if primary_root else ""
        mod_secondary_base = os.path.join(secondary_root, mod_name) if secondary_root else ""
        mod_tertiary_base = os.path.join(tertiary_root, mod_name) if tertiary_root else ""
        
        # Phase 5: Get Deploy Rule for defaults
        deploy_rule = override_rule
        if not deploy_rule or deploy_rule in ("default", "inherit"):
            config_rule = config.get('deploy_rule')
            if config_rule and config_rule not in ("default", "inherit"):
                deploy_rule = config_rule
            else:
                app_default_rule = app_data.get('deployment_rule', 'folder')
                deploy_rule = app_default_rule

        # Pass None as parent to prevent OS compositor alpha failure with transparent windows
        diag = FileManagementDialog(None, abs_path, config.get('deployment_rules'), 
                                   primary_target=mod_primary_base, secondary_target=mod_secondary_base, tertiary_target=mod_tertiary_base,
                                   app_name=app_data.get('name', ''), storage_root=self.storage_root)
        
        # Non-modal: Use show() instead of exec() to allow main window interaction
        # Store reference to prevent garbage collection
        self._current_file_mgmt_dialog = diag
        
        # Connect finished signal for async result handling
        diag.finished.connect(lambda result: self._on_file_management_finished(diag, rel_path, result))
        diag.show()
    
    def _on_file_management_finished(self, diag, rel_path, result):
        """Handle FileManagementDialog result asynchronously."""
        # Clean up reference
        self._current_file_mgmt_dialog = None
        
        if result != 1:  # QDialog.Accepted = 1
            return
            
        new_rules = diag.get_rules_json()
        try:
            # 🚨 Phase 42: Use Unified Property Saving (Centralized in LMFileOpsMixin)
            abs_path = os.path.join(self.storage_root, rel_path)
            if hasattr(self, '_apply_folder_config_updates'):
                self._apply_folder_config_updates([abs_path], {'deployment_rules': new_rules})
            else:
                # Fallback if not mixed into window
                self.db.update_folder_display_config(rel_path, deployment_rules=new_rules)
                self.logger.warning(f"LMFileManagementMixin: _apply_folder_config_updates not found on self. Minimal save performed.")

        except Exception as e:
            self.logger.error(f"Failed to save deployment rules: {e}")
