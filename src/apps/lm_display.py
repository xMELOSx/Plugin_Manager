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
            
            # Reset all
            for btn in btns.values():
                btn.setStyleSheet(self.btn_normal_style)
            
            # Highlight active
            if override and override in btns:
                btns[override].setStyleSheet(self.btn_selected_style)
    
    def _toggle_cat_display_mode(self, mode, force=False):
        """Toggle category display mode button - click again to deselect and return to default."""
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
        self.btn_cat_text.setStyleSheet(self.btn_normal_style)
        self.btn_cat_image.setStyleSheet(self.btn_normal_style)
        self.btn_cat_both.setStyleSheet(self.btn_normal_style)
        
        mapping = {'image': 'mini_image', 'text': 'text_list'}
        if self.cat_display_override is not None:
            # Green for Override
            target = {
                'text_list': self.btn_cat_text,
                'mini_image': self.btn_cat_image,
                'image_text': self.btn_cat_both
            }.get(self.cat_display_override)
            if target: target.setStyleSheet(self.btn_selected_style)
            apply_mode = self.cat_display_override
        else:
            # Blue for Default
            folder_mode = mapping.get(view_config.get('display_style'), view_config.get('display_style') or 'mini_image')
            target = {
                'text_list': self.btn_cat_text,
                'mini_image': self.btn_cat_image,
                'image_text': self.btn_cat_both
            }.get(folder_mode)
            if target: target.setStyleSheet(self.btn_no_override_style)
            apply_mode = folder_mode

        # Update existing cards
        if hasattr(self, 'cat_layout'):
            scale = getattr(self, f'cat_{apply_mode}_scale', 1.0)
            base_w = getattr(self, f'cat_{apply_mode}_card_w', 160)
            base_h = getattr(self, f'cat_{apply_mode}_card_h', 220)
            base_img_w = getattr(self, f'cat_{apply_mode}_img_w', 140)
            base_img_h = getattr(self, f'cat_{apply_mode}_img_h', 140)

            for i in range(self.cat_layout.count()):
                widget = self.cat_layout.itemAt(i).widget()
                if hasattr(widget, 'set_display_mode'):
                    widget.set_display_mode(apply_mode)
                if hasattr(widget, 'set_card_params'):
                    widget.set_card_params(base_w, base_h, base_img_w, base_img_h, scale)

    def _toggle_pkg_display_mode(self, mode, force=False):
        """Toggle package display mode button - click again to deselect and return to default."""
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

        self.btn_pkg_text.setStyleSheet(self.btn_normal_style)
        self.btn_pkg_image.setStyleSheet(self.btn_normal_style)
        self.btn_pkg_image_text.setStyleSheet(self.btn_normal_style)
        
        mapping = {'image': 'mini_image', 'text': 'text_list'}
        if self.pkg_display_override is not None:
            target = {
                'text_list': self.btn_pkg_text,
                'mini_image': self.btn_pkg_image,
                'image_text': self.btn_pkg_image_text
            }.get(self.pkg_display_override)
            if target: target.setStyleSheet(self.btn_selected_style)
            apply_mode = self.pkg_display_override
        else:
            folder_pkg_mode = view_config.get('display_style_package') or view_config.get('display_style', 'mini_image')
            folder_pkg_mode = mapping.get(folder_pkg_mode, folder_pkg_mode)
            target = {
                'text_list': self.btn_pkg_text,
                'mini_image': self.btn_pkg_image,
                'image_text': self.btn_pkg_image_text
            }.get(folder_pkg_mode)
            if target: target.setStyleSheet(self.btn_no_override_style)
            apply_mode = folder_pkg_mode

        # Update existing cards
        if hasattr(self, 'pkg_layout'):
            scale = getattr(self, f'pkg_{apply_mode}_scale', 1.0)
            base_w = getattr(self, f'pkg_{apply_mode}_card_w', 160)
            base_h = getattr(self, f'pkg_{apply_mode}_card_h', 220)
            base_img_w = getattr(self, f'pkg_{apply_mode}_img_w', 140)
            base_img_h = getattr(self, f'pkg_{apply_mode}_img_h', 140)

            for i in range(self.pkg_layout.count()):
                widget = self.pkg_layout.itemAt(i).widget()
                if hasattr(widget, 'set_display_mode'):
                    widget.set_display_mode(apply_mode)
                if hasattr(widget, 'set_card_params'):
                    widget.set_card_params(base_w, base_h, base_img_w, base_img_h, scale)

    def _toggle_show_hidden(self):
        """Toggle visibility of hidden folders."""
        self.show_hidden = not self.show_hidden
        if self.show_hidden:
            self.btn_show_hidden.setText("👁")
            self.btn_show_hidden.setToolTip(_("Showing hidden folders (click to hide)"))
            self.btn_show_hidden.setStyleSheet(self.btn_selected_style)
        else:
            self.btn_show_hidden.setText("=")
            self.btn_show_hidden.setToolTip(_("Show hidden folders"))
            self.btn_show_hidden.setStyleSheet(self.btn_normal_style)
        self._apply_card_filters()

    def _toggle_linked_filter(self):
        """Toggle filter to show only linked categories and categories containing linked packages."""
        is_checked = self.btn_filter_linked.isChecked()
        
        # Uncheck the other filter if this is checked
        if is_checked:
            self.btn_filter_unlinked.setChecked(False)
            self.link_filter_mode = 'linked'
            self.btn_filter_linked.setStyleSheet(self.btn_selected_style)
            self.btn_filter_unlinked.setStyleSheet(self.btn_normal_style)
        else:
            self.link_filter_mode = None
            self.btn_filter_linked.setStyleSheet(self.btn_normal_style)
        
        self._apply_card_filters()

    def _toggle_unlinked_filter(self):
        """Toggle filter to show only unlinked categories and categories containing unlinked packages."""
        is_checked = self.btn_filter_unlinked.isChecked()
        
        # Uncheck the other filter if this is checked
        if is_checked:
            self.btn_filter_linked.setChecked(False)
            self.link_filter_mode = 'unlinked'
            self.btn_filter_unlinked.setStyleSheet(self.btn_selected_style)
            self.btn_filter_linked.setStyleSheet(self.btn_normal_style)
        else:
            self.link_filter_mode = None
            self.btn_filter_unlinked.setStyleSheet(self.btn_normal_style)
        
        self._apply_card_filters()

    def _apply_card_filters(self):
        """Phase 28: Fast in-memory filter applying without re-scan."""
        from src.ui.link_master.item_card import ItemCard
        
        # Process Category cards
        if hasattr(self, 'cat_layout'):
            for i in range(self.cat_layout.count()):
                item = self.cat_layout.itemAt(i)
                if not item: continue
                card = item.widget()
                if not isinstance(card, ItemCard): continue
                
                visible = self._should_card_be_visible(card)
                card.setVisible(visible)
        
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
        # Check hidden filter
        if not getattr(self, 'show_hidden', False) and getattr(card, 'is_hidden', False):
            return False
        
        # Check link filter
        link_mode = getattr(self, 'link_filter_mode', None)
        if link_mode == 'linked':
            if card.link_status not in ['linked', 'partial'] and not getattr(card, 'has_linked_children', False):
                return False
        elif link_mode == 'unlinked':
            if card.link_status in ['linked', 'partial'] or getattr(card, 'has_linked_children', False):
                return False
        
        return True
