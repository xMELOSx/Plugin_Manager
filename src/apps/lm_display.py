"""
Link Master: Display Mode Mixin
表示モード切替とオーバーライドのロジック。

依存するコンポーネント:
- ItemCard (set_display_mode, set_card_params を呼び出し)

依存する親クラスの属性:
- cat_display_override, pkg_display_override: str | None
- cat_layout, pkg_layout: FlowLayout
- btn_cat_text, btn_cat_image, btn_cat_both: QPushButton
- btn_pkg_text, btn_pkg_image, btn_pkg_image_text: QPushButton
- btn_show_hidden: QPushButton
- btn_normal_style, btn_selected_style, btn_no_override_style: str
- app_combo: QComboBox
- current_view_path, current_path: str
- storage_root: str
"""
import os
import logging
from src.core.lang_manager import _


class LMDisplayMixin:
    """表示モード切替とオーバーライドを担当するMixin。"""
    
    def _update_override_buttons(self):
        """Syncs the toolbar button styles with current override state."""
        for prefix in ['cat', 'pkg']:
            override = getattr(self, f'{prefix}_display_override')
            active_mode = override or 'image_text'
            
            # Map modes to buttons
            if prefix == 'cat':
                btns = {
                    'text_list': self.btn_cat_text,
                    'mini_image': self.btn_cat_image,
                    'image_text': self.btn_cat_both
                }
            else:
                btns = {
                    'text_list': self.btn_pkg_text,
                    'mini_image': self.btn_pkg_image,
                    'image_text': self.btn_pkg_image_text
                }
            
            # Reset all using component methods when available
            for btn in btns.values():
                if hasattr(btn, '_force_state'):
                    btn._force_state(False)
                else:
                    btn.setStyleSheet(self.btn_normal_style)
            
            # Highlight active
            if override and override in btns:
                target = btns[override]
                if hasattr(target, '_force_state'):
                    target._force_state(True)
                else:
                    target.setStyleSheet(self.btn_selected_style)
    
    def _toggle_cat_display_mode(self, mode, force=False):
        """Toggle category display mode button - click again to deselect and return to default."""
        # Phase 57: Prevent _refresh_package_cards from running during display mode change
        self._display_mode_changing = True
        
        if not force and self.cat_display_override == mode:
            self.cat_display_override = None
        else:
            self.cat_display_override = mode
        
        # Get view config for Blue state logic
        app_data = self.app_combo.currentData()
        view_config = {}
        if app_data:
            storage_root = app_data.get('storage_root')
            view_path = getattr(self, 'current_view_path', storage_root)
            try:
                view_rel = os.path.relpath(view_path, storage_root).replace('\\', '/')
                if view_rel == ".": view_rel = ""
                from src.core.link_master.database import get_lm_db
                db = get_lm_db(app_data['name'])
                view_config = db.get_folder_config(view_rel) or {}
            except: 
                pass

        # Reset all to normal
        for btn in [self.btn_cat_text, self.btn_cat_image, self.btn_cat_both]:
            if hasattr(btn, '_force_state'): btn._force_state(False)
            else: btn.setStyleSheet(self.btn_normal_style)
        
        mapping = {'image': 'mini_image', 'text': 'text_list'}
        if self.cat_display_override is not None:
            # Green for Override
            target = {
                'text_list': self.btn_cat_text,
                'mini_image': self.btn_cat_image,
                'image_text': self.btn_cat_both
            }.get(self.cat_display_override)
            if target:
                if hasattr(target, '_force_state'): target._force_state(True, is_override=True)
                else: target.setStyleSheet(self.btn_selected_style)
            apply_mode = self.cat_display_override
        else:
            # Blue for Default
            app_cat_default = app_data.get('default_category_style', 'image_text')
            folder_mode = mapping.get(view_config.get('display_style'), view_config.get('display_style') or mapping.get(app_cat_default, app_cat_default))
            target = {
                'text_list': self.btn_cat_text,
                'mini_image': self.btn_cat_image,
                'image_text': self.btn_cat_both
            }.get(folder_mode)
            if target:
                if hasattr(target, '_force_state'): target._force_state(True, is_override=False)
                else: target.setStyleSheet(self.btn_no_override_style)
            apply_mode = folder_mode

        # Update existing cards
        if hasattr(self, 'cat_layout'):
            scale = getattr(self, f'cat_{apply_mode}_scale', 1.0)
            base_w = getattr(self, f'cat_{apply_mode}_card_w', 160)
            base_h = getattr(self, f'cat_{apply_mode}_card_h', 220)
            base_img_w = getattr(self, f'cat_{apply_mode}_img_w', 140)
            base_img_h = getattr(self, f'cat_{apply_mode}_img_h', 140)

            # Profiling
            import time
            t_start = time.perf_counter()
            count = self.cat_layout.count()
            
            # Centralized update loop optimizations
            # Phase 1.1.15: Enable Batch Mode to skip relayout on every item update
            if hasattr(self.cat_layout, 'setBatchMode'):
                self.cat_layout.setBatchMode(True)
            
            # Disable updates to prevent flicker and intermediate repaints
            self.cat_container.setUpdatesEnabled(False)
            
            for i in range(count):
                widget = self.cat_layout.itemAt(i).widget()
                if hasattr(widget, 'set_display_mode'):
                    widget.set_display_mode(apply_mode)
            
            t_mid = time.perf_counter()
            
            # Phase 1.1.5: Centralized apply to ensure dynamic spacing is updated correctly
            if hasattr(self, '_apply_card_params_to_layout'):
                self._apply_card_params_to_layout('category', apply_mode)
                
            # Finish batch mode (triggers one final layout)
            if hasattr(self.cat_layout, 'setBatchMode'):
                self.cat_layout.setBatchMode(False)
                
            self.cat_container.setUpdatesEnabled(True)
            
            t_end = time.perf_counter()
            logging.info(f"[DisplayMode] Cat toggle to '{apply_mode}' for {count} items took {(t_end - t_start):.4f}s (WidgetUpdate: {(t_mid-t_start):.4f}s, Layout: {(t_end-t_mid):.4f}s)")
        
        # Phase 57: Reset display mode changing flag with delay to skip debounced refresh
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(200, self._reset_display_mode_flag)

    def _toggle_pkg_display_mode(self, mode, force=False):
        """Toggle package display mode button - click again to deselect and return to default."""
        # Phase 57: Prevent _refresh_package_cards from running during display mode change
        self._display_mode_changing = True
        
        if not force and self.pkg_display_override == mode:
            self.pkg_display_override = None
        else:
            self.pkg_display_override = mode

        # Get view config
        app_data = self.app_combo.currentData()
        view_config = {}
        if app_data:
            storage_root = app_data.get('storage_root')
            view_path = getattr(self, 'current_path', storage_root)
            try:
                view_rel = os.path.relpath(view_path, storage_root).replace('\\', '/')
                if view_rel == ".": view_rel = ""
                from src.core.link_master.database import get_lm_db
                db = get_lm_db(app_data['name'])
                view_config = db.get_folder_config(view_rel) or {}
            except: 
                pass

        for btn in [self.btn_pkg_text, self.btn_pkg_image, self.btn_pkg_image_text]:
            if hasattr(btn, '_force_state'): btn._force_state(False)
            else: btn.setStyleSheet(self.btn_normal_style)
        
        mapping = {'image': 'mini_image', 'text': 'text_list'}
        if self.pkg_display_override is not None:
            target = {
                'text_list': self.btn_pkg_text,
                'mini_image': self.btn_pkg_image,
                'image_text': self.btn_pkg_image_text
            }.get(self.pkg_display_override)
            if target:
                if hasattr(target, '_force_state'): target._force_state(True, is_override=True)
                else: target.setStyleSheet(self.btn_selected_style)
            apply_mode = self.pkg_display_override
        else:
            # Blue for Default
            app_pkg_default = app_data.get('default_package_style', 'image_text')
            folder_pkg_mode = view_config.get('display_style_package') or view_config.get('display_style') or mapping.get(app_pkg_default, app_pkg_default)
            folder_pkg_mode = mapping.get(folder_pkg_mode, folder_pkg_mode)
            target = {
                'text_list': self.btn_pkg_text,
                'mini_image': self.btn_pkg_image,
                'image_text': self.btn_pkg_image_text
            }.get(folder_pkg_mode)
            if target:
                if hasattr(target, '_force_state'): target._force_state(True, is_override=False)
                else: target.setStyleSheet(self.btn_no_override_style)
            apply_mode = folder_pkg_mode

        # Update existing cards
        if hasattr(self, 'pkg_layout'):
            scale = getattr(self, f'pkg_{apply_mode}_scale', 1.0)
            base_w = getattr(self, f'pkg_{apply_mode}_card_w', 160)
            base_h = getattr(self, f'pkg_{apply_mode}_card_h', 220)
            base_img_w = getattr(self, f'pkg_{apply_mode}_img_w', 140)
            base_img_h = getattr(self, f'pkg_{apply_mode}_img_h', 140)

            # Profiling
            import time
            t_start = time.perf_counter()
            count = self.pkg_layout.count()

            for i in range(count):
                widget = self.pkg_layout.itemAt(i).widget()
                if hasattr(widget, 'set_display_mode'):
                    widget.set_display_mode(apply_mode)
            
            t_mid = time.perf_counter()

            # Phase 1.1.5: Centralized apply to ensure dynamic spacing is updated correctly
            if hasattr(self, '_apply_card_params_to_layout'):
                self._apply_card_params_to_layout('package', apply_mode)
                
            t_end = time.perf_counter()
            logging.info(f"[DisplayMode] Pkg toggle to '{apply_mode}' for {count} items took {(t_end - t_start):.4f}s (WidgetUpdate: {(t_mid-t_start):.4f}s, Layout: {(t_end-t_mid):.4f}s)")
        
        # Phase 57: Reset display mode changing flag with delay to skip debounced refresh
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(200, self._reset_display_mode_flag)

    def _reset_display_mode_flag(self):
        """Phase 57: Helper to reset display mode changing flag."""
        self._display_mode_changing = False

    def _toggle_show_hidden(self):
        """Toggle visibility of hidden folders."""
        self.show_hidden = not self.show_hidden
        
        # Restore requested icon for hidden state: '=' if not showing, '👁' if showing
        if hasattr(self, 'btn_show_hidden'):
             self.btn_show_hidden.toggle() # Update checked state for stylesheet
             self.btn_show_hidden.setText("👁" if self.show_hidden else "＝")
             
        self._set_btn_show_hidden_style()
        self._apply_card_filters()
        self._save_last_state()

    def _set_btn_show_hidden_style(self):
        if not hasattr(self, 'btn_show_hidden'): return
        self.btn_show_hidden.setToolTip(_("Showing hidden folders") if self.show_hidden else _("Show hidden folders"))
        # TitleBarButton manages icon through its text property, which we set in factory

    def _toggle_favorite_filter(self):
        """Toggle filter to show only favorited items."""
        toggled_on = self.btn_filter_favorite.toggle()
        self.favorite_filter_mode = toggled_on
        self._apply_card_filters()

    def _toggle_linked_filter(self):
        """Toggle filter to show only linked categories and categories containing linked packages."""
        toggled_on = self.btn_filter_linked.toggle()
        
        # Uncheck the other filter if this is checked
        if toggled_on:
            if self.btn_filter_unlinked.toggled_state:
                self.btn_filter_unlinked.toggle()  # Force off
            self.link_filter_mode = 'linked'
        else:
            self.link_filter_mode = None
        
        self._apply_card_filters()

    def _toggle_unlinked_filter(self):
        """Toggle filter to show only unlinked categories and categories containing unlinked packages."""
        toggled_on = self.btn_filter_unlinked.toggle()
        
        # Uncheck the other filter if this is checked
        if toggled_on:
            if self.btn_filter_linked.toggled_state:
                self.btn_filter_linked.toggle()  # Force off
            self.link_filter_mode = 'unlinked'
        else:
            self.link_filter_mode = None
        
        self._apply_card_filters()

    def _apply_card_filters(self):
        """Phase 28: Fast in-memory filter applying without re-scan."""
        from src.ui.link_master.item_card import ItemCard
        
        if hasattr(self, 'cat_layout'):
            visible_cat_count = 0
            for i in range(self.cat_layout.count()):
                item = self.cat_layout.itemAt(i)
                if not item: continue
                card = item.widget()
                if not isinstance(card, ItemCard): continue
                
                visible = self._should_card_be_visible(card)
                card.setVisible(visible)
                if visible:
                    visible_cat_count += 1
            
            # Update counts
            if hasattr(self, 'cat_result_label'):
                self.cat_result_label.setText(_("Category Count: {count}").format(count=visible_cat_count))
        
        # Process Package cards
        if hasattr(self, 'pkg_layout'):
            visible_pkg_count = 0
            linked_pkg_count = 0
            for i in range(self.pkg_layout.count()):
                item = self.pkg_layout.itemAt(i)
                if not item: continue
                card = item.widget()
                if not isinstance(card, ItemCard): continue
                
                visible = self._should_card_be_visible(card)
                card.setVisible(visible)
                if visible:
                    visible_pkg_count += 1
                    if card.link_status in ['linked', 'partial']:
                        linked_pkg_count += 1
            
            # Update counts
            if hasattr(self, 'pkg_result_label'):
                self.pkg_result_label.setText(_("Package Count: {count}").format(count=visible_pkg_count))
            if hasattr(self, 'pkg_link_count_label'):
                self.pkg_link_count_label.setText(_("Link Count In Category: {count}").format(count=linked_pkg_count))
        
        # Phase 28: Force layout reflow to eliminate gaps from hidden cards
        if hasattr(self, 'cat_layout'):
            self.cat_layout.invalidate()
            if hasattr(self.cat_layout, 'update'): self.cat_layout.update()
        if hasattr(self, 'pkg_layout'):
            self.pkg_layout.invalidate()
            if hasattr(self.pkg_layout, 'update'): self.pkg_layout.update()
        if hasattr(self, 'cat_container'): self.cat_container.updateGeometry()
        if hasattr(self, 'pkg_container'): self.pkg_container.updateGeometry()

    def _should_card_be_visible(self, card) -> bool:
        """Determines if a card should be visible based on current filters."""
        is_show_hidden = getattr(self, 'show_hidden', False)
        
        # 1. Check hidden filter
        if not is_show_hidden and getattr(card, 'is_hidden', False):
            return False
            
        # 2. Check _Trash visibility
        if not is_show_hidden:
            card_path = getattr(card, 'path', "")
            if os.path.basename(card_path) == '_Trash':
                return False
        
        # 3. Check View Context Selection
        # Requirement: In 'view' context (top area), if a category is selected (current_path set),
        # we hide packages in that same area to avoid visual noise/confusion.
        context = getattr(card, 'context', 'view')
        current_selection = getattr(self, 'current_path', None)
        if context == "view" and current_selection and getattr(card, 'is_package', False):
            return False

        # 4. Check Preset Filter
        if getattr(self, 'preset_filter_mode', False):
            rel_path = getattr(card, 'rel_path', "")
            if context == "contents":
                if rel_path not in getattr(self, 'preset_filter_paths', set()):
                    return False
            else:
                if getattr(card, 'is_package', False):
                    if rel_path not in getattr(self, 'preset_filter_paths', set()):
                        return False
                else:
                    if rel_path not in getattr(self, 'preset_filter_categories', set()):
                        return False

        # 5. Check link filter
        link_mode = getattr(self, 'link_filter_mode', None)
        if link_mode == 'linked':
            # Show if: item is linked/partial OR category has linked children
            if card.link_status not in ['linked', 'partial'] and not getattr(card, 'has_linked_children', False):
                return False
        elif link_mode == 'unlinked':
            # Packages: show if NOT fully linked (none, conflict, partial?)
            # User request: "Non-linked". Usually implies anything that isn't green (linked).
            # Partial has distinct status, Conflict has distinct status.
            # Assuming we show everything except 'linked'.
            if getattr(card, 'is_package', False):
                if card.link_status == 'linked':
                    return False
            else:
                # Categories: only show if they contain unlinked packages
                # This depends on set_children_status being called correctly.
                if not getattr(card, 'has_unlinked_children', False):
                    return False
        
        # 6. Check favorite filter
        if getattr(self, 'favorite_filter_mode', False):
            if not getattr(card, 'is_favorite', False) and not getattr(card, 'has_favorite', False):
                return False
        
        return True
