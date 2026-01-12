"""
Link Master: Tags Mixin
タグ管理とフィルタリングのロジック。

依存するコンポーネント:
- TagManagerDialog (src/ui/link_master/dialogs/)
- LMDatabase

依存する親クラスの属性:
- db, app_combo, current_app_id, tag_bar, cat_layout
- search_bar, cat_result_label, non_inheritable_tags
"""
import os
import json


class LMTagsMixin:
    """タグ管理とフィルタリングを担当するMixin。"""
    
    def _load_tags_for_app(self):
        """Load available tags for the current app."""
        if not self.current_app_id: return
        
        # Only load Quick Tags (managed via Tag Manager)
        frequent = self._load_quick_tags()
        
        final_tags = list(frequent)
        
        self.tag_bar.set_tags(final_tags)
        
        # Refresh non-inheritable tags cache
        self.non_inheritable_tags = self._get_non_inheritable_tags_from_json()

    def _open_tag_manager(self):
        """Open the TagManagerDialog."""
        from src.ui.link_master.dialogs import TagManagerDialog
        d = TagManagerDialog(self, self.db, registry=self.registry)
        if d.exec():
            print("[LMTagsMixin] Tag Manager closed. Refreshing UI...")
            self._load_tags_for_app()
            # 💡 Also trigger tag bar refresh explicitly
            if hasattr(self.tag_bar, 'refresh_tags'):
                self.tag_bar.refresh_tags()

    def _load_quick_tags(self):
        """Load quick tags from DB, supporting both JSON config and CSV fallback."""
        # 1. Try Loading JSON Config for Rich Tags
        raw_config = self.db.get_setting('frequent_tags_config', '[]')
        try:
            tags_data = json.loads(raw_config)
            if isinstance(tags_data, list) and tags_data:
                results = []
                for t in tags_data:
                    if not isinstance(t, dict): continue
                    
                    # Handle Separator
                    if t.get('name') == '|' or t.get('is_sep'):
                         results.append({'name': '|', 'display': '|', 'value': '|', 'icon': '', 'emoji': '', 'is_sep': True, 'is_inheritable': True})
                         continue
                        
                    name = t.get('name', '')
                    if name:
                        # Load ALL relevant fields for full consistency
                        results.append({
                            'name': name,
                            'display': t.get('display', name), # Fallback to name
                            'value': t.get('value', name),
                            'icon': t.get('icon', ''),
                            'emoji': t.get('emoji', ''),
                            'display_mode': t.get('display_mode', 'text'),
                            'prefer_emoji': t.get('prefer_emoji', True),
                            'is_inheritable': t.get('is_inheritable', True),
                            'is_sep': False
                        })
                return results
        except:
            pass
            
        # 2. Fallback to Simple CSV
        raw = self.db.get_setting('frequent_tags', '')
        parts = [t.strip() for t in raw.split(',') if t.strip()]
        return [{'name': t, 'display': t, 'value': t, 'icon': '', 'emoji': '', 'is_sep': False} for t in parts]

    def _on_tags_changed(self, tags):
        """Called when tag selection changes.
        
        Dual behavior:
        - Normal mode (no search text): Filter categories by selected tags
        - Search mode (text entered): Trigger full tag-based search
        """
        query = self.search_bar.text().strip()
        
        if query:
            # Search mode: Perform full tag+text search
            from PyQt6.QtCore import QTimer
            self._show_search_indicator()
            QTimer.singleShot(100, self._perform_search)
        else:
            # Normal mode: Filter categories by tag (hide non-matching)
            self._filter_categories_by_tags(tags)
    
    def _filter_categories_by_tags(self, selected_tags):
        """Filter visible categories by selected tags (normal mode)."""
        if not selected_tags:
            # No tags selected - show all categories
            for i in range(self.cat_layout.count()):
                item = self.cat_layout.itemAt(i)
                if item and item.widget():
                    item.widget().setVisible(True)
            self.cat_layout.invalidate()
            if self.cat_layout.parentWidget():
                self.cat_layout.parentWidget().updateGeometry()
            self.cat_result_label.setText("")
            return
        
        app_data = self.app_combo.currentData()
        if not app_data: return
        storage_root = app_data.get('storage_root')
        folder_configs = self.db.get_all_folder_configs()
        
        # Phase 20: Segment-based logic
        selected_segments = self.tag_bar.get_selected_segments()
        visible_count = 0
        
        for i in range(self.cat_layout.count()):
            item = self.cat_layout.itemAt(i)
            if not item or not item.widget(): continue
            
            card = item.widget()
            if not hasattr(card, 'path'): continue
            
            try:
                rel_path = os.path.relpath(card.path, storage_root).replace('\\', '/')
                config = folder_configs.get(rel_path, {})
                cat_tags = {t.strip().lower() for t in (config.get('tags') or '').split(',') if t.strip()}
                
                # Match logic: (Segment1-Tag1 OR Segment1-Tag2) AND (Segment2-Tag1) ...
                match = True
                for segment in selected_segments:
                    if not any(tag in cat_tags for tag in segment):
                        match = False
                        break
                
                card.setVisible(match)
                if match:
                    visible_count += 1
            except:
                card.setVisible(True)
        
        # Force layout update to ensure cards are reflowed (left-aligned) correctly
        self.cat_layout.invalidate()
        if self.cat_layout.parentWidget():
            self.cat_layout.parentWidget().updateGeometry()
            
        self.cat_result_label.setText(f"🏷️ {visible_count} (タグフィルター: セグメントAND)")

    def _get_non_inheritable_tags_from_json(self):
        """Parse quick_tags_config to find tags marked as non-inheritable."""
        raw = self.db.get_setting('frequent_tags_config', '[]')
        try:
            tags_data = json.loads(raw)
            return {t['name'].lower() for t in tags_data if isinstance(t, dict) and not t.get('is_inheritable', True)}
        except:
            return set()

    def _get_inherited_tags(self, folder_path, folder_configs):
        """Calculate inherited tags for a folder path up to storage_root."""
        if not folder_path: return set()
        
        app_data = self.app_combo.currentData()
        if not app_data: return set()
        storage_root = app_data.get('storage_root')
        
        tags = set()
        current = folder_path
        
        # Walk up until storage_root
        while True:
            try:
                # Check boundaries
                if os.path.abspath(current) == os.path.abspath(storage_root):
                    rel = ""
                else:
                    rel = os.path.relpath(current, storage_root)
                    if rel == ".": rel = ""
                
                config = folder_configs.get(rel, {})
                t_str = config.get('tags', '')
                if t_str:
                    for t in t_str.split(','):
                        t = t.strip().lower()
                        if t and t not in self.non_inheritable_tags:
                            tags.add(t)
                
                # Stop if at root
                if not rel: break
                
                # Stop if inheritance is blocked for this folder
                if config.get('inherit_tags', 1) == 0:
                    break

                # Move up
                parent = os.path.dirname(current)

                if parent == current: break  # Safety
                current = parent
            except:
                break
                
        return tags
