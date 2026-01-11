"""
Link Master: Scan Handler Mixin
スキャン結果処理とカード生成ロジック。

依存するコンポーネント:
- ItemCard (src/ui/link_master/item_card.py)
- LMDatabase (src/core/link_master/database.py)

依存する親クラスの属性:
- cat_layout, pkg_layout: FlowLayout
- cat_result_label, pkg_result_label: QLabel
- app_combo: QComboBox
- deployer: Deployer
- image_loader: ImageLoader
- thumbnail_manager: ThumbnailManager
- db: LMDatabase
- selected_paths: set
- show_hidden: bool
- search_bar, tag_bar: widgets
- preset_filter_mode, preset_filter_paths, preset_filter_categories: preset filtering
"""
import os
import time
from src.core.lang_manager import _
from src.ui.link_master.item_card import ItemCard
import re # Phase 33: Natural Sort


class LMScanHandlerMixin:
    """スキャン結果処理とカード生成を担当するMixin。"""
    
    def _on_scan_results_ready(self, results, original_path, context="view", app_id=None):
        """Populates the category and package layouts based on scan results and context."""
        import time
        start_t = time.perf_counter()
        
        # Reset scan-in-progress flag to allow new scans
        self._scan_in_progress = False
        
        # 1. Validate context and prevent race conditions (Phase 33: includes app_id)
        if not self._validate_scan_context(original_path, context, app_id):
            return
            
        # Phase 34: Scan Suppression during Critical Operations (e.g. Category Deployment)
        if getattr(self, '_scan_suppressed', False):
            self.logger.info(f"[Scan] Results ignored due to suppression (Context: {context})")
            return
            
        app_data = self.app_combo.currentData()
        if not app_data: return
        storage_root = app_data.get('storage_root')
        
        # 2. Get display configurations and folder configs
        configs = self._get_display_configs(original_path, context, storage_root, app_data)
        folder_configs = configs['folder_configs']
        view_config = configs['view_config']
        
        # 3. Sort results
        results = self._get_sorted_results(results, storage_root, folder_configs)
        
        # 4. Prepare layouts (Clear, release cards, batch mode)
        self._prepare_layouts_for_redraw(context, app_data, view_config)
        
        # Phase 33: Apply setUpdatesEnabled to the ENTIRE WINDOW to prevent layout recalculations
        # during the 145+ card update loop. This is the key optimization.
        self.setUpdatesEnabled(False)
        try:
            # 5. Populate layouts with cards
            counts = self._populate_cards(results, context, storage_root, folder_configs, configs)
            
            # 6. Finalize UI (Labels, margins, styles)
            self._finalize_scan_ui(counts, context, original_path, start_t)
        finally:
            self.setUpdatesEnabled(True)


    def _validate_scan_context(self, original_path, context, app_id=None):
        """Phase 28: Scan version tracking and context validation to prevent stale results."""
        # Phase 33: App ID Validation to prevent bleed between different apps
        if app_id and hasattr(self, 'current_app_id'):
            if str(app_id) != str(self.current_app_id):
                self.logger.warning(f"[RaceCondition] Rejected stale scan results for App ID: {app_id} (Current: {self.current_app_id})")
                return False

        if not hasattr(self, '_scan_version'):
            self._scan_version = 0
            
        current_view = getattr(self, 'current_view_path', None)
        current_selection = getattr(self, 'current_path', None)
        
        if context == "view":
            if current_view and original_path:
                if os.path.normpath(current_view).replace('\\', '/') != os.path.normpath(original_path).replace('\\', '/'):
                    return False
        elif context == "contents":
            if current_selection is None and original_path:
                return False
            if current_selection and original_path:
                if os.path.normpath(current_selection).replace('\\', '/') != os.path.normpath(original_path).replace('\\', '/'):
                    return False
        return True

    def _get_display_configs(self, original_path, context, storage_root, app_data):
        """Resolve all display modes, folder configs, and common app settings."""
        app_name = app_data.get('name')
        
        # Load configs from DB
        from src.core.link_master.database import get_lm_db
        db = get_lm_db(app_name)
        raw_configs = db.get_all_folder_configs()
        folder_configs = {k.replace('\\', '/'): v for k, v in raw_configs.items()}
        
        # Resolve view relation
        if context == "contents":
            view_path = original_path if original_path else storage_root
        else:
            view_path = original_path if original_path else getattr(self, 'current_view_path', storage_root)
        try:
            view_rel = os.path.relpath(view_path, storage_root).replace('\\', '/')
            if view_rel == ".": view_rel = ""
        except: view_rel = ""
        
        # Phase 32 Fix: App Defaults take precedence over Root Config if set in Root
        # But normally Folder Config overrides App Default.
        # User requested: Root folder should respect App Settings.
        # We enforce this by ignoring display keys in view_config for Root ("").
        view_config = folder_configs.get(view_rel, {}).copy() # Copy to avoid mutating global cache if reused
        if view_rel == "":
            view_config.pop('display_style', None)
            view_config.pop('display_style_package', None)
        
        # Defaults from App Data
        app_cat_style_default = app_data.get('default_category_style', 'image')
        app_pkg_style_default = app_data.get('default_package_style', 'image')
        
        # Mapping for legacy modes
        mapping = {'image': 'mini_image', 'text': 'text_list'}
        
        # Resolve Category display mode
        if self.cat_display_override is not None:
            view_display_mode = self.cat_display_override
        else:
            raw_mode = view_config.get('display_style') or app_cat_style_default
            view_display_mode = mapping.get(raw_mode, raw_mode)
        self.current_view_display_mode = view_display_mode
        
        # Resolve Package display mode
        if self.pkg_display_override is not None:
            pkg_display_mode = self.pkg_display_override
        elif context == "search" and getattr(self, 'current_pkg_display_mode', None):
            pkg_display_mode = self.current_pkg_display_mode
        else:
            raw_pkg_mode = view_config.get('display_style_package') or view_config.get('display_style') or app_pkg_style_default
            pkg_display_mode = mapping.get(raw_pkg_mode, raw_pkg_mode)
        self.current_pkg_display_mode = pkg_display_mode
        
        return {
            'folder_configs': folder_configs,
            'view_config': view_config,
            'view_display_mode': view_display_mode,
            'pkg_display_mode': pkg_display_mode,
            'app_name': app_name,
            'app_deploy_default': app_data.get('deployment_type', 'folder'),
            'app_conflict_default': app_data.get('conflict_policy', 'backup'),
            'app_cat_style_default': app_cat_style_default,
            'app_pkg_style_default': app_pkg_style_default,
            'target_root': app_data.get(self.current_target_key)
        }

    def _get_sorted_results(self, results, storage_root, folder_configs):
        """Sort scan results based on Name (Natural, Ascending)."""
        def sort_key(r):
            import re
            name_str = r['item']['name'].lower()
            return [int(c) if c.isdigit() else c for c in re.split('([0-9]+)', name_str)]

        results.sort(key=sort_key)
        return results

    def _prepare_layouts_for_redraw(self, context, app_data, view_config):
        """Clear headers, release cards, and enable batch modes."""
        has_selection = bool(getattr(self, 'current_path', None))
        if context == "view" or context == "search":
            if not has_selection or context == "search":
                self.pkg_result_label.setText("")
            self.cat_result_label.setText("")
        elif context == "contents":
            self.pkg_result_label.setText("")
            
        # Determine defaults for button update (using mapping)
        mapping = {'image': 'mini_image', 'text': 'text_list'}
        app_cat_def = app_data.get('default_category_style', 'image')
        cat_level_def = mapping.get(app_cat_def, app_cat_def)
        
        app_pkg_def = app_data.get('default_package_style', 'image')
        pkg_level_def = mapping.get(app_pkg_def, app_pkg_def)
        self._update_cat_button_styles(view_config, cat_level_def)
        self._update_pkg_button_styles(view_config, pkg_level_def)
        
        # Phase 33: Cancel any pending image load requests from previous folder
        # This prevents stale images from appearing and focuses resources on current folder
        if hasattr(self, 'image_loader') and hasattr(self.image_loader, 'cancel_pending'):
            self.image_loader.cancel_pending()
        
        self._release_all_active_cards(context)

        
        # Phase 33: Removed redundant "Phase 32 Extra Safety" loops here.
        # _release_all_active_cards already handles removeWidget and hide().
        # The duplicate loop was causing 2x layout traversal overhead.

        if hasattr(self, 'pkg_container'): self.pkg_container.setUpdatesEnabled(False)
        if hasattr(self, 'cat_container'): self.cat_container.setUpdatesEnabled(False)
        if hasattr(self, 'pkg_layout') and hasattr(self.pkg_layout, 'setBatchMode'):
            self.pkg_layout.setBatchMode(True)
        if hasattr(self, 'cat_layout') and hasattr(self.cat_layout, 'setBatchMode'):
            self.cat_layout.setBatchMode(True)

    def _populate_cards(self, results, context, storage_root, folder_configs, configs):
        """Acquire and update cards for all results."""
        cat_count = 0
        pkg_count = 0
        current_has_selection = bool(getattr(self, 'current_path', None))
        
        # Cache mode-specific settings
        vd_mode = configs['view_display_mode']
        pk_mode = configs['pkg_display_mode']
        
        settings = {
            'cat_show_link': getattr(self, f'cat_{vd_mode}_show_link', True),
            'cat_show_deploy': getattr(self, f'cat_{vd_mode}_show_deploy', True),
            'pkg_show_link': getattr(self, f'pkg_{pk_mode}_show_link', True),
            'pkg_show_deploy': getattr(self, f'pkg_{pk_mode}_show_deploy', True),
            'opacity': getattr(self, 'deploy_button_opacity', 0.8)
        }
        
        for r in results:
            item_abs_path = r['abs_path']
            try:
                item_rel = os.path.relpath(item_abs_path, storage_root).replace('\\', '/')
                if item_rel == ".": item_rel = ""
            except: item_rel = ""
            
            item_config = folder_configs.get(item_rel, {})
            is_package = r.get('is_package', False)
            use_pkg_settings = (is_package or context == "contents")
            
            # Card Acquisition
            item_type = "package" if use_pkg_settings else "category"
            card = self._acquire_card(item_type)
            
            # Data Update
            self._update_card_from_result(card, r, item_rel, item_config, storage_root, configs, settings, context)
            
            # Selection State
            if item_abs_path in self.selected_paths or item_abs_path == getattr(self, 'current_path', None):
                card.set_selected(True)
                if item_abs_path not in self.selected_paths:
                    self.selected_paths.add(item_abs_path)
            
            # Layout Allocation
            if item_type == "package":
                self._setup_card_layout(card, pk_mode, "pkg")
                self.pkg_layout.addWidget(card)
                pkg_count += 1
            else:
                self._setup_card_layout(card, vd_mode, "cat")
                self.cat_layout.addWidget(card)
                cat_count += 1
            card.show()
            
        return {'cat': cat_count, 'pkg': pkg_count}

    def _update_card_from_result(self, card, r, item_rel, item_config, storage_root, configs, settings, context):
        """Unified method to update card data from a scan result."""
        is_package = r.get('is_package', False)
        use_pkg_settings = (is_package or context == "contents")
        
        # Resolve Image
        img_path = None
        cfg_img = item_config.get('image_path')
        if cfg_img:
            img_path = cfg_img if os.path.isabs(cfg_img) else os.path.join(storage_root, cfg_img)
        elif r.get('thumbnail'):
            img_path = os.path.join(r['abs_path'], r['thumbnail'])

        card.update_data(
            name=item_config.get('display_name') or r['item']['name'],
            path=r['abs_path'],
            image_path=img_path,
            is_registered=(item_rel in configs['folder_configs']),
            target_override=item_config.get('target_override'),
            deployment_rules=item_config.get('deployment_rules'),
            manual_preview_path=item_config.get('manual_preview_path'),
            is_hidden=(item_config.get('is_visible', 1) == 0),
            deploy_rule=r.get('deploy_rule') or item_config.get('deploy_rule') or item_config.get('deploy_type') or configs['app_deploy_default'],
            conflict_policy=item_config.get('conflict_policy') or configs['app_conflict_default'],
            storage_root=storage_root,
            db=self.db,
            context=context,
            has_linked=r.get('has_linked', False),
            has_unlinked=r.get('has_unlinked', False),
            has_favorite=r.get('has_favorite', False),
            has_conflict_children=r.get('has_conflict', False),
            link_status=r.get('link_status', 'none'),
            has_logical_conflict=r.get('has_logical_conflict', False),
            has_name_conflict=r.get('has_name_conflict', False),
            has_target_conflict=r.get('has_target_conflict', False),
            is_misplaced=r.get('is_misplaced', False) if (not is_package and context != "contents") else False,
            is_package=is_package,
            is_trash_view=r.get('is_trash_view', False),
            loader=self.image_loader,
            deployer=self.deployer,
            target_dir=configs['target_root'],
            app_name=configs['app_name'],
            thumbnail_manager=self.thumbnail_manager,
            app_deploy_default=configs['app_deploy_default'],
            app_conflict_default=configs['app_conflict_default'],
            app_cat_style_default=configs['app_cat_style_default'],
            app_pkg_style_default=configs['app_pkg_style_default'],
            is_partial=r.get('is_partial', False),
            conflict_tag=item_config.get('conflict_tag'),
            conflict_scope=item_config.get('conflict_scope'),
            is_favorite=r.get('is_favorite', 0),
            score=r.get('score', 0),
            url_list=r.get('url_list', '[]'),
            lib_name=item_config.get('lib_name', ''),
            is_library=r.get('is_library', 0),
            is_library_alt_version=r.get('is_library_alt_version', False),
            tags_raw=item_config.get('tags', ''),
            show_link=settings['pkg_show_link'] if use_pkg_settings else settings['cat_show_link'],
            show_deploy=self._calculate_show_deploy(is_package, use_pkg_settings, settings),
            deploy_button_opacity=settings['opacity'],
            category_deploy_status=item_config.get('category_deploy_status')
        )
        card.context = context
        card.rel_path = item_rel
        
    def _calculate_show_deploy(self, is_package, use_pkg_settings, settings):
        """Calculate deploy button visibility based on settings and context."""
        base_visible = settings['pkg_show_deploy'] if use_pkg_settings else settings['cat_show_deploy']
        if not base_visible: return False
        
        # Original: visible if it IS a package, OR if we are in Category View (top layout)
        if is_package or not use_pkg_settings:
            return True
        
        # New: if it's a folder in Package View (bottom layout), check Debug Override
        from src.ui.link_master.item_card import ItemCard
        if not is_package and use_pkg_settings:
            return getattr(ItemCard, 'ALLOW_FOLDER_DEPLOY_IN_PKG_VIEW', False)
            
        return False

    def _setup_card_layout(self, card, mode, prefix):
        """Apply scale and dimensions to a card based on its display mode."""
        card.set_display_mode(mode)
        scale = getattr(self, f'{prefix}_{mode}_scale', 1.0)
        base_w = getattr(self, f'{prefix}_{mode}_card_w', 160)
        base_h = getattr(self, f'{prefix}_{mode}_card_h', 200)
        base_img_w = getattr(self, f'{prefix}_{mode}_img_w', 140)
        base_img_h = getattr(self, f'{prefix}_{mode}_img_h', 120)
        card.set_card_params(base_w, base_h, base_img_w, base_img_h, scale)

    def _finalize_scan_ui(self, counts, context, original_path, start_t):
        """Update result labels, adjust spacing, and resume layout updates."""
        # 1. Update Labels
        self._update_total_link_count()
        if self.search_bar.text().strip() or self.tag_bar.get_selected_tags():
            self.cat_result_label.setText(f"({counts['cat']})")
        
        if self.preset_filter_mode:
            self.pkg_result_label.setText(_("Package Count: {count}/{total}").format(
                count=counts['pkg'], total=len(self.preset_filter_paths)))
        else:
            self.pkg_result_label.setText(_("Package Count: {count}").format(count=counts['pkg']))

        # 2. Adjust Spacing
        vd_mode = self.current_view_display_mode
        pk_mode = self.current_pkg_display_mode
        for mode, prefix, layout in [(vd_mode, 'cat', self.cat_layout), (pk_mode, 'pkg', self.pkg_layout)]:
            scale = getattr(self, f'{prefix}_{mode}_scale', 1.0)
            spacing = max(2, int(10 * scale))
            margin = max(4, int(10 * scale))
            layout.setSpacing(spacing)
            layout.setContentsMargins(margin, margin, margin, margin)
            layout.invalidate()
            if layout.parentWidget():
                layout.parentWidget().updateGeometry()

        # 3. Resume Updates
        for layout in [self.pkg_layout, self.cat_layout]:
            if hasattr(layout, 'setBatchMode'): layout.setBatchMode(False)
        if hasattr(self, 'pkg_container'): self.pkg_container.setUpdatesEnabled(True)
        if hasattr(self, 'cat_container'): self.cat_container.setUpdatesEnabled(True)

        self._apply_card_filters()
        
        # Note: _refresh_category_cards removed from hot path for performance.
        # Category status is updated via deploy_changed signal from individual cards.
        # Phase 33: DISABLED - Scanner already calculates link_status for all items.
        # The 200ms delayed _refresh_category_cards was causing a 1-2 second GUI lock
        # by re-checking link status for all 41+ cards via filesystem access.
        # from PyQt6.QtCore import QTimer
        # QTimer.singleShot(200, self._refresh_category_cards)

        
        duration = time.perf_counter() - start_t
        self.logger.debug(f"[Profile] _on_scan_results_ready ({context}) took {duration:.3f}s")

    def _update_cat_button_styles(self, view_config, level_default):
        """Update category display mode button styles."""
        for btn in [self.btn_cat_text, self.btn_cat_image, self.btn_cat_both]:
            if hasattr(btn, '_force_state'):
                btn._force_state(False)
            else:
                btn.setStyleSheet(self.btn_normal_style)
        
        mapping = {'image': 'mini_image', 'text': 'text_list'}
        if self.cat_display_override is not None:
            target_btn = {
                'text_list': self.btn_cat_text,
                'mini_image': self.btn_cat_image,
                'image_text': self.btn_cat_both
            }.get(self.cat_display_override)
            if target_btn:
                if hasattr(target_btn, '_force_state'):
                    target_btn._force_state(True, is_override=True)
                else:
                    target_btn.setStyleSheet(self.btn_selected_style)
        else:
            folder_mode = mapping.get(view_config.get('display_style'), view_config.get('display_style') or level_default)
            target_btn = {
                'text_list': self.btn_cat_text,
                'mini_image': self.btn_cat_image,
                'image_text': self.btn_cat_both
            }.get(folder_mode)
            if target_btn:
                if hasattr(target_btn, '_force_state'):
                    target_btn._force_state(True, is_override=False)
                else:
                    target_btn.setStyleSheet(self.btn_no_override_style)

    def _update_pkg_button_styles(self, view_config, level_default='mini_image'):
        """Update package display mode button styles."""
        for btn in [self.btn_pkg_text, self.btn_pkg_image, self.btn_pkg_image_text]:
            if hasattr(btn, '_force_state'):
                btn._force_state(False)
            else:
                btn.setStyleSheet(self.btn_normal_style)
        
        mapping = {'image': 'mini_image', 'text': 'text_list'}
        if self.pkg_display_override is not None:
            target_btn = {
                'text_list': self.btn_pkg_text,
                'mini_image': self.btn_pkg_image,
                'image_text': self.btn_pkg_image_text
            }.get(self.pkg_display_override)
            if target_btn:
                if hasattr(target_btn, '_force_state'):
                    target_btn._force_state(True, is_override=True)
                else:
                    target_btn.setStyleSheet(self.btn_selected_style)
        else:
            folder_pkg_mode = view_config.get('display_style_package') or view_config.get('display_style') or level_default
            folder_pkg_mode = mapping.get(folder_pkg_mode, folder_pkg_mode)
            target_btn = {
                'text_list': self.btn_pkg_text,
                'mini_image': self.btn_pkg_image,
                'image_text': self.btn_pkg_image_text
            }.get(folder_pkg_mode)
            if target_btn:
                if hasattr(target_btn, '_force_state'):
                    target_btn._force_state(True, is_override=False)
                else:
                    target_btn.setStyleSheet(self.btn_no_override_style)

    def _on_scan_finished(self):
        """Called when scan is complete."""
        self._hide_search_indicator()
        if hasattr(self, '_nav_start_t') and self._nav_start_t:
            self.logger.debug(f"[Profile] Category Navigation/Redraw took {time.time()-self._nav_start_t:.3f}s")
            self._nav_start_t = None

    def _scan_children_status(self, folder_path: str, target_root: str, cached_configs: dict = None) -> tuple:
        """Helper to scan direct children for status (used by top area).
        
        UNIFIED APPROACH: Uses DB's last_known_status for consistency with initial load.
        Phase 28 Optim: Accepts cached_configs to avoid O(N) DB calls.
        """
        has_linked = False
        has_conflict = False
        has_partial = False
        has_unlinked = False 
        has_internal_conflict = False
        
        # Get app data for storage_root
        app_data = self.app_combo.currentData()
        storage_root = app_data.get('storage_root')
        if not storage_root: return False, False, False, False
        
        # Get folder_path relative to storage_root
        try:
            folder_rel = os.path.relpath(folder_path, storage_root).replace('\\', '/')
            if folder_rel == ".": folder_rel = ""
        except: 
            return False, False, False, False
        
        # Phase 28: Fetch all configs
        if cached_configs is not None:
            folder_configs = cached_configs
        else:
            all_configs_raw = self.db.get_all_folder_configs()
            folder_configs = {k.replace('\\', '/'): v for k, v in all_configs_raw.items()}

        # Iterate all configs to find children of this folder
        folder_prefix = folder_rel + "/" if folder_rel else ""
        
        child_tags = set()
        child_libs = set()
        
        for rel_path, cfg in folder_configs.items():
            # Check if this is a DIRECT child of folder_path
            if not rel_path.startswith(folder_prefix):
                continue
            
            # Get the part after the prefix
            child_part = rel_path[len(folder_prefix):]
            
            # Skip if not direct child (has subdirectories)
            if "/" in child_part:
                continue
            
            # Skip if it's the folder itself
            if not child_part:
                continue
            
            # Check DB status
            status = cfg.get('last_known_status', 'none')
            
            if status == 'linked':
                has_linked = True
                # Check if partial (custom rules)
                if cfg.get('deploy_type') == 'custom' or cfg.get('deploy_rule') == 'custom':
                    import json
                    try:
                        rules_json = cfg.get('deployment_rules')
                        if rules_json:
                            ro = json.loads(rules_json)
                            if ro.get('exclude') or ro.get('overrides') or ro.get('rename'):
                                has_partial = True
                    except: pass
            elif status == 'conflict':
                has_conflict = True
                has_unlinked = True # Conflict is also unlinked in terms of "not successfully linked"
            else:
                has_unlinked = True # 'none' or 'misplaced' or partial? No, partial is linked.
            
            # Also check has_logical_conflict flag from DB
            if cfg.get('has_logical_conflict', 0):
                has_conflict = True
                has_unlinked = True
            
            # Phase 35: Internal Conflict Check
            ctag_str = cfg.get('conflict_tag')
            if ctag_str:
                my_tags = [t.strip().lower() for t in ctag_str.split(',') if t.strip()]
                for t in my_tags:
                    if t in child_tags:
                        has_internal_conflict = True
                    child_tags.add(t)
                
                # Also check External Tag Conflict for this child tag
                if not has_internal_conflict and hasattr(self, '_check_tag_conflict'):
                     # Note: we pass card_rel as context to ignore itself, but here context is folder_rel
                     ext_conflict = self._check_tag_conflict(folder_rel, {'conflict_tag': ctag_str}, app_data)
                     if ext_conflict:
                         has_internal_conflict = True

            lib_name = cfg.get('library_name') or cfg.get('lib_name')
            if lib_name:
                if lib_name in child_libs:
                    has_internal_conflict = True
                child_libs.add(lib_name)
            
            # Early exit if all found
            if has_linked and has_conflict and has_partial and has_unlinked:
                break
            
        return has_linked, has_conflict, has_partial, has_unlinked, has_internal_conflict


    def _refresh_category_cards(self):
        """Refresh children status for all Category cards (updates orange borders)."""
        import time
        t_start = time.perf_counter()
        
        app_data = self.app_combo.currentData()
        if not app_data: return
        target_root = app_data.get(self.current_target_key)
        if not target_root: return
        
        # Phase 28 Optimization: Fetch DB once!
        all_configs_raw = self.db.get_all_folder_configs()
        cached_configs = {k.replace('\\', '/'): v for k, v in all_configs_raw.items()}
        
        cat_count = 0
        for layout in [self.cat_layout, self.pkg_layout]:
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget():
                    card = item.widget()
                    if isinstance(card, ItemCard) and card.is_package is False:
                            cat_count += 1
                            # Pass cache
                            has_linked, has_conflict, has_partial, has_unlinked, has_int_conf = self._scan_children_status(card.path, target_root, cached_configs=cached_configs)
                            card.set_children_status(
                                has_linked=has_linked, 
                                has_conflict=has_conflict, 
                                has_partial=has_partial, 
                                has_unlinked_children=has_unlinked,
                                has_category_conflict=has_int_conf
                            )
        
        t_cat_end = time.perf_counter()
        self.logger.debug(f"[Profile] _refresh_category_cards ({cat_count} cards) took {(t_cat_end-t_start)*1000:.1f}ms")
        
        # Also refresh package card borders (green for linked, red for conflict)
        self._refresh_package_cards()
        
        t_total_end = time.perf_counter()
        self.logger.debug(f"[Profile] _refresh_category_cards TOTAL took {(t_total_end-t_start)*1000:.1f}ms")

    def _refresh_package_cards(self):
        """Refresh link status for all Package cards (updates green/conflict borders)."""
        import time
        t_start = time.perf_counter()
        
        # Phase 34: Suppression Check
        if getattr(self, '_scan_suppressed', False):
            return
        
        from src.ui.link_master.item_card import ItemCard
        pkg_count = 0
        for i in range(self.pkg_layout.count()):
            item = self.pkg_layout.itemAt(i)
            if item and item.widget():
                card = item.widget()
                if isinstance(card, ItemCard) and hasattr(card, '_check_link_status'):
                    pkg_count += 1
                    card._check_link_status()
                    card._update_style()
        
        t_end = time.perf_counter()
        self.logger.debug(f"[Profile] _refresh_package_cards ({pkg_count} cards) took {(t_end-t_start)*1000:.1f}ms")

    def _set_cat_display_mode(self, mode):
        """Change display mode for all category cards."""
        self.cat_display_override = mode
        scale = getattr(self, 'cat_scale', 1.0)
        base_w = getattr(self, f'cat_{mode}_card_w', 160)
        base_h = getattr(self, f'cat_{mode}_card_h', 220)
        base_img_w = getattr(self, f'cat_{mode}_img_w', 140)
        base_img_h = getattr(self, f'cat_{mode}_img_h', 140)
        
        for i in range(self.cat_layout.count()):
            item = self.cat_layout.itemAt(i)
            if item and item.widget():
                card = item.widget()
                if hasattr(card, 'set_display_mode'):
                    card.set_display_mode(mode)
                if hasattr(card, 'set_card_params'):
                    card.set_card_params(base_w, base_h, base_img_w, base_img_h, scale)

    def _reorder_item(self, path, direction):
        """Handle manual reordering (Move to Top/Bottom)."""
        app_data = self.app_combo.currentData()
        if not app_data: return
        storage_root = app_data.get('storage_root')
        if not storage_root: return
        
        try:
            rel_path = os.path.relpath(path, storage_root).replace('\\', '/')
            parent_rel = os.path.dirname(rel_path)
            
            all_configs = self.db.get_all_folder_configs()
            siblings = []
            for r, cfg in all_configs.items():
                if os.path.dirname(r) == parent_rel:
                    siblings.append((r, cfg.get('sort_order', 0)))
            
            if not siblings:
                new_order = 0
            else:
                orders = [s[1] for s in siblings]
                if direction == "top":
                    new_order = min(orders) - 1
                else:
                    new_order = max(orders) + 1
            
            self.db.update_folder_display_config(rel_path, sort_order=new_order)
            self._refresh_current_view()
        except Exception as e:
            self.logger.error(f"Reorder failed: {e}")
            
    def _update_total_link_count(self):
        """Phase 28: Lightning-fast total count lookup via DB cache."""
        if not hasattr(self, 'db') or not self.db: return
        
        total_link_count = 0
        try:
            # Query the database for any folder marked as 'linked' or 'partial' 
            # This is vastly faster than a recursive disk scan.
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                # Count ALL types (Categories and Packages) as requested
                sql = "SELECT COUNT(*) FROM lm_folder_config WHERE last_known_status IN ('linked', 'partial')"
                cur.execute(sql)
                res = cur.fetchone()
                total_link_count = res[0] if res else 0
        except Exception as e:
            self.logger.warning(f"Fast total count query failed: {e}")
            
        if hasattr(self, 'total_link_count_label'):
            self.total_link_count_label.setText(_("Total Links: {count}").format(count=total_link_count))

        # Phase 33/Debug: Ensure newly created cards receive the latest highlight calculations
        if hasattr(self, '_refresh_tag_visuals'):
            self._refresh_tag_visuals()

        # Phase 28: Also update the local categorization link count (Packages)
        if hasattr(self, 'pkg_link_count_label'):
            local_link_count = 0
            if hasattr(self, 'pkg_layout') and self.pkg_layout:
                for i in range(self.pkg_layout.count()):
                    item = self.pkg_layout.itemAt(i)
                    if not item: continue
                    w = item.widget()
                    if isinstance(w, ItemCard) and w.link_status in ['linked', 'partial']:
                        local_link_count += 1
            self.pkg_link_count_label.setText(_("Link Count In Category: {count}").format(count=local_link_count))

    def _manual_rebuild(self):
        """Phase 28: Full recursive scan to re-validate and cache link statuses in DB."""
        app_data = self.app_combo.currentData()
        if not app_data: return
        
        storage_root = app_data.get('storage_root')
        target_roots = [r for r in [app_data.get('target_root'), app_data.get('target_root_2')] if r and os.path.exists(r)]
        if not (storage_root and os.path.exists(storage_root)): return

        self.logger.info("Starting manual rebuild of link status cache...")
        try:
            # 1. Clear all cached statuses first (Optional but cleaner)
            with self.db.get_connection() as conn:
                conn.execute("UPDATE lm_folder_config SET last_known_status = 'none'")
            
            # 2. Recursive scan to find ALL physical folders
            for root, dirs, _ in os.walk(storage_root):
                dirs[:] = [d for d in dirs if not (d in ["_Trash", "_Backup"] or d.startswith('.'))]
                
                for d in dirs:
                    abs_src = os.path.join(root, d)
                    rel = os.path.relpath(abs_src, storage_root).replace('\\', '/')
                    
                    cfg = self.db.get_folder_config(rel) or {}
                    
                    # Check status in any target root
                    status = 'none'
                    for t_root in target_roots:
                        t_link = cfg.get('target_override') or os.path.join(t_root, d)
                        res = self.deployer.get_link_status(t_link, expected_source=abs_src)
                        if res.get('status') in ['linked', 'partial']:
                            status = res['status']
                            break
                    
                    # Update cache selectively (ignore 'none' to save writes if we cleared)
                    if status != 'none':
                        self.db.update_folder_display_config(rel, last_known_status=status)
            
            self.logger.info("Manual rebuild complete.")
            self._update_total_link_count()
            self._refresh_current_view() # Refresh UI to show new colors
            
            # Phase 28: Also trigger tag visual refresh for library version syncing
            if hasattr(self, '_refresh_tag_visuals'):
                self._refresh_tag_visuals()
        except Exception as e:
            self.logger.error(f"Manual rebuild failed: {e}")

