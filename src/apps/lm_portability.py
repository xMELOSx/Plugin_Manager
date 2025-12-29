"""
Link Master: Portability Mixin
インポート/エクスポート（JSONとリソースの統合）を担当するMixin。
Phase 28: ZIP形式 (.dioco) でのエクスポート/インポート対応。
"""
import os
import json
import shutil
import logging
import re
import tempfile
import zipfile
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QInputDialog

class LMPortabilityMixin:
    """フォルダ設定とリソースのインポート/エクスポートを担当するMixin。"""
    
    @staticmethod
    def _is_valid_path(path):
        """パスの長さと無効な文字をチェックする。"""
        if len(path) > 255:
            return False, "パスが長すぎます（最大255文字）。"
        invalid_chars = r'[<>:"|?*]'
        if re.search(invalid_chars, os.path.basename(path)):
            return False, "ファイル名に無効な文字が含まれています (< > : \" | ? *)。"
        return True, ""

    def _export_hierarchy(self, start_rel_path):
        """指定された相対パス以下のフォルダ設定とリソースを .dioco (ZIP) 形式でエクスポート。"""
        if not hasattr(self, 'db') or not self.db: return
        
        # 1. 階層の深さを指定
        depth, ok = QInputDialog.getInt(self, "Export Depth", 
                                       "エクスポートする階層の深さを指定してください:\n(1=選択フォルダのみ, 2=子フェーズまで, ...)", 
                                       value=2, min=1)
        if not ok: return

        # 2. 保存先ファイルの選択 (.dioco)
        app_name = getattr(self, 'app_name', 'unknown')
        default_filename = f"{app_name}_export.dioco"
        dest_file, _ = QFileDialog.getSaveFileName(
            self, "エクスポート先の選択", 
            default_filename,
            "Dionys Control Export (*.dioco)"
        )
        if not dest_file: return
        
        if not dest_file.endswith('.dioco'):
            dest_file += '.dioco'
        
        # パスバリデーション
        is_valid, err_msg = self._is_valid_path(dest_file)
        if not is_valid:
            QMessageBox.warning(self, "Export Path Error", err_msg)
            return

        # 3. 設定の収集
        all_configs = self.db.get_all_folder_configs()
        target_configs = {}
        
        base_depth = start_rel_path.count('/') + 1 if start_rel_path else 0
        prefix = start_rel_path + "/" if start_rel_path else ""
        
        for k, v in all_configs.items():
            is_in_range = (k == start_rel_path or k.startswith(prefix))
            if is_in_range:
                item_depth = k.count('/') + 1 if k else 0
                rel_depth = item_depth - base_depth + 1
                
                if rel_depth <= depth:
                    config_copy = v.copy()
                    config_copy['target_override'] = None
                    target_configs[k] = config_copy
        
        if not target_configs:
            QMessageBox.information(self, "Export", "範囲内または指定の深さにエクスポート対象の設定が見つかりません。")
            return

        # 4. 一時ディレクトリに構造を作成
        with tempfile.TemporaryDirectory() as temp_dir:
            resource_dir = os.path.join(temp_dir, "resource", "app", app_name)
            os.makedirs(resource_dir, exist_ok=True)
            
            final_configs = {}
            success_count = 0
            
            for rel_path, config in target_configs.items():
                for key in ['image_path', 'manual_preview_path']:
                    file_path = config.get(key)
                    if file_path:
                        actual_path = None
                        if os.path.isabs(file_path):
                            actual_path = file_path
                        elif hasattr(self, 'storage_root') and self.storage_root:
                            actual_path = os.path.join(self.storage_root, file_path)
                        
                        if actual_path and os.path.exists(actual_path):
                            try:
                                if start_rel_path:
                                    sub_res_rel = os.path.relpath(rel_path, start_rel_path)
                                    if sub_res_rel == ".": sub_res_rel = ""
                                else:
                                    sub_res_rel = rel_path
                            except ValueError:
                                sub_res_rel = ""
                                
                            res_dest_subdir = os.path.join(resource_dir, sub_res_rel)
                            os.makedirs(res_dest_subdir, exist_ok=True)
                            
                            filename = os.path.basename(actual_path)
                            res_dest_file = os.path.join(res_dest_subdir, filename)
                            
                            try:
                                shutil.copy2(actual_path, res_dest_file)
                                config[key] = os.path.relpath(res_dest_file, temp_dir).replace('\\', '/')
                            except Exception as e:
                                self.logger.error(f"Failed to copy resource {actual_path}: {e}")
                
                final_configs[rel_path] = config
                success_count += 1

            # 5. JSONの保存
            json_data = {
                "version": "2.0",  # ZIP/dioco format
                "app_name": app_name,
                "export_root_rel": start_rel_path,
                "configs": final_configs
            }
            
            json_path = os.path.join(temp_dir, "config.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=4, ensure_ascii=False)
            
            # 6. ZIPアーカイブ作成
            try:
                with zipfile.ZipFile(dest_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(temp_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, temp_dir)
                            zipf.write(file_path, arcname)
                
                QMessageBox.information(self, "Export", f"エクスポート完了: {success_count} 件の設定を保存しました。\n{dest_file}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"ZIPの作成に失敗しました: {e}")

    def _import_portability_package(self):
        """エクスポートされた .dioco ファイルから設定とリソースをインポートする。"""
        # 1. ソースファイルの選択
        source_file, _ = QFileDialog.getOpenFileName(
            self, "インポートファイルの選択", 
            "",
            "Dionys Control Export (*.dioco);;All Files (*)"
        )
        if not source_file: return
        
        # 2. ZIPファイルを一時ディレクトリに展開
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                with zipfile.ZipFile(source_file, 'r') as zipf:
                    zipf.extractall(temp_dir)
            except zipfile.BadZipFile:
                # フォールバック: 古いフォルダ形式のサポート
                if os.path.isdir(source_file):
                    temp_dir = source_file # Use directly
                else:
                    QMessageBox.warning(self, "Import Error", "無効なファイル形式です。.diocoファイルを選択してください。")
                    return
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"ZIPの展開に失敗しました: {e}")
                return
            
            json_path = os.path.join(temp_dir, "config.json")
            if not os.path.exists(json_path):
                QMessageBox.warning(self, "Import Error", "config.json が見つかりません。")
                return
                
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"JSONの読み込みに失敗しました: {e}")
                return
                
            configs = data.get("configs", {})
            if not configs:
                QMessageBox.warning(self, "Import", "インポート可能な設定が見つかりません。")
                return
                
            # 3. リソースの復元先ディレクトリの準備
            app_name = getattr(self, 'app_name', 'unknown')
            dest_res_base = os.path.join(self.thumbnail_manager.resource_root, app_name, "imported")
            os.makedirs(dest_res_base, exist_ok=True)
            
            import_count = 0
            current_dest_rel = self._get_current_rel_path()
            storage_root = getattr(self, 'storage_root', None)
            
            for rel_path, config in configs.items():
                # インポート先の相対パスを決定
                if data.get("export_root_rel"):
                    try:
                        base_rel = os.path.relpath(rel_path, data["export_root_rel"])
                        new_rel = os.path.normpath(os.path.join(current_dest_rel, base_rel)).replace('\\', '/')
                    except:
                        new_rel = os.path.normpath(os.path.join(current_dest_rel, os.path.basename(rel_path))).replace('\\', '/')
                else:
                    new_rel = os.path.normpath(os.path.join(current_dest_rel, os.path.basename(rel_path))).replace('\\', '/')
                
                # 物理フォルダの作成
                if storage_root:
                    abs_dest_dir = os.path.join(storage_root, new_rel)
                    os.makedirs(abs_dest_dir, exist_ok=True)

                # リソースの復元
                for key in ['image_path', 'manual_preview_path']:
                    res_rel = config.get(key)
                    if res_rel and not os.path.isabs(res_rel):
                        src_res = os.path.join(temp_dir, res_rel)
                        if os.path.exists(src_res):
                            parts = res_rel.replace('\\', '/').split('/')
                            if 'resource' in parts:
                                idx = parts.index('resource')
                                if len(parts) > idx + 3 and parts[idx+1] == 'app':
                                    sub_path = "/".join(parts[idx+3:-1])
                                else:
                                    sub_path = "/".join(parts[idx+1:-1])
                            else:
                                sub_path = os.path.dirname(res_rel)
                            
                            target_dir = os.path.join(dest_res_base, sub_path)
                            os.makedirs(target_dir, exist_ok=True)
                            
                            dest_file_path = os.path.join(target_dir, os.path.basename(src_res))
                            try:
                                shutil.copy2(src_res, dest_file_path)
                                config[key] = os.path.normpath(dest_file_path).replace('\\', '/')
                            except Exception as e:
                                self.logger.error(f"Failed to restore resource {src_res}: {e}")
                
                # データベースの更新
                try:
                    data_to_store = {k: v for k, v in config.items() if k not in ['id', 'rel_path']}
                    self.db.update_folder_display_config(new_rel, **data_to_store)
                    import_count += 1
                except Exception as e:
                    self.logger.error(f"Failed to import config for {new_rel}: {e}")
                
            QMessageBox.information(self, "Import", f"{import_count} 件の設定をインポートしました。")
            self._refresh_current_view()
