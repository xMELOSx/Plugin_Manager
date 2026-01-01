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


class LMScanHandlerMixin:
    """スキャン結果処理とカード生成を担当するMixin。"""
    
    def _on_scan_results_ready(self, results, original_path, context="view"):
        """Populates the category and package layouts based on scan results and context."""
        import time
        start_t = time.perf_counter()
        
        # 1. Validate context and prevent race conditions
        if not self._validate_scan_context(original_path, context):
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
        
        # 5. Populate layouts with cards
        counts = self._populate_cards(results, context, storage_root, folder_configs, configs)
        
        # 6. Finalize UI (Labels, margins, styles)
        self._finalize_scan_ui(counts, context, original_path, start_t)

    def _validate_scan_context(self, original_path, context):
        """Phase 28: Scan version tracking and context validation to prevent stale results."""
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
        
        view_config = folder_configs.get(view_rel, {})
        level_default = 'mini_image'
        
        # Resolve Category display mode
        if self.cat_display_override is not None:
            view_display_mode = self.cat_display_override
        else:
            raw_mode = view_config.get('display_style') or level_default
            mapping = {'image': 'mini_image', 'text': 'text_list'}
            view_display_mode = mapping.get(raw_mode, raw_mode)
        self.current_view_display_mode = view_display_mode
        
        # Resolve Package display mode
        if self.pkg_display_override is not None:
            pkg_display_mode = self.pkg_display_override
        elif context == "search" and getattr(self, 'current_pkg_display_mode', None):
            pkg_display_mode = self.current_pkg_display_mode
        else:
            raw_pkg_mode = view_config.get('display_style_package') or view_config.get('display_style', 'mini_image')
            mapping = {'image': 'mini_image', 'text': 'text_list'}
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
            'app_cat_style_default': app_data.get('default_category_style', 'image'),
            'app_pkg_style_default': app_data.get('default_package_style', 'image'),
            'target_root': app_data.get(self.current_target_key)
        }

    def _get_sorted_results(self, results, storage_root, folder_configs):
        """Sort scan results based on Favorite, Score, Sort Order, and Name."""
        def sort_key(r):
            item_abs = r['abs_path']
            try:
                rel = os.path.relpath(item_abs, storage_root).replace('\\', '/')
            except: rel = ""
            cfg = folder_configs.get(rel, {})
            is_fav = cfg.get('is_favorite', 0) or r.get('is_favorite', 0)
            score = cfg.get('score', 0) or r.get('score', 0)
            return (
                0 if is_fav else 1,
                -int(score or 0),
                cfg.get('sort_order', 0), 
                r['item']['name'].lower()
            )
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
            
        self._update_cat_button_styles(view_config, 'mini_image')
        self._update_pkg_button_styles(view_config)
        self._release_all_active_cards(context)
        
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
            deploy_type=item_config.get('deploy_type') or configs['app_deploy_default'],
            conflict_policy=item_config.get('conflict_policy') or configs['app_conflict_default'],
            storage_root=storage_root,
            db=self.db,
            has_linked=r.get('has_linked', False),
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
            is_library_alt_version=r.get('is_library_alt_version', False),
            tags_raw=item_config.get('tags', ''),
            show_link=settings['pkg_show_link'] if use_pkg_settings else settings['cat_show_link'],
            show_deploy=settings['pkg_show_deploy'] if use_pkg_settings else settings['cat_show_deploy'],
            deploy_button_opacity=settings['opacity']
        )
        card.context = context
        card.rel_path = item_rel

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
        
        duration = time.perf_counter() - start_t
        self.logger.info(f"[Profile] _on_scan_results_ready ({context}) took {duration:.3f}s")

    def _update_cat_button_styles(self, view_config, level_default):
        """Update category display mode button styles."""
        self.btn_cat_text.setStyleSheet(self.btn_normal_style)
        self.btn_cat_image.setStyleSheet(self.btn_normal_style)
        self.btn_cat_both.setStyleSheet(self.btn_normal_style)
        
        mapping = {'image': 'mini_image', 'text': 'text_list'}
        if self.cat_display_override is not None:
            target_btn = {
                'text_list': self.btn_cat_text,
                'mini_image': self.btn_cat_image,
                'image_text': self.btn_cat_both
            }.get(self.cat_display_override)
            if target_btn: target_btn.setStyleSheet(self.btn_selected_style)
        else:
            folder_mode = mapping.get(view_config.get('display_style'), view_config.get('display_style') or level_default)
            target_btn = {
                'text_list': self.btn_cat_text,
                'mini_image': self.btn_cat_image,
                'image_text': self.btn_cat_both
            }.get(folder_mode)
            if target_btn: target_btn.setStyleSheet(self.btn_no_override_style)

    def _update_pkg_button_styles(self, view_config):
        """Update package display mode button styles."""
        self.btn_pkg_text.setStyleSheet(self.btn_normal_style)
        self.btn_pkg_image.setStyleSheet(self.btn_normal_style)
        self.btn_pkg_image_text.setStyleSheet(self.btn_normal_style)
        
        mapping = {'image': 'mini_image', 'text': 'text_list'}
        if self.pkg_display_override is not None:
            target_btn = {
                'text_list': self.btn_pkg_text,
                'mini_image': self.btn_pkg_image,
                'image_text': self.btn_pkg_image_text
            }.get(self.pkg_display_override)
            if target_btn: target_btn.setStyleSheet(self.btn_selected_style)
        else:
            folder_pkg_mode = view_config.get('display_style_package') or view_config.get('display_style', 'mini_image')
            folder_pkg_mode = mapping.get(folder_pkg_mode, folder_pkg_mode)
            target_btn = {
                'text_list': self.btn_pkg_text,
                'mini_image': self.btn_pkg_image,
                'image_text': self.btn_pkg_image_text
            }.get(folder_pkg_mode)
            if target_btn: target_btn.setStyleSheet(self.btn_no_override_style)

    def _on_scan_finished(self):
        """Called when scan is complete."""
        self._hide_search_indicator()
        if hasattr(self, '_nav_start_t') and self._nav_start_t:
            self.logger.info(f"[Profile] Category Navigation/Redraw took {time.time()-self._nav_start_t:.3f}s")
            self._nav_start_t = None

    def _scan_children_status(self, folder_path: str, target_root: str, cached_configs: dict = None) -> tuple:
        """Helper to scan direct children for status (used by top area).
        Phase 3.6: Correctly resolve child target paths via DB to avoid false conflict.
        Phase 28 Optim: Accepts cached_configs to avoid O(N) DB calls.
        """
        has_linked = False
        has_conflict = False
        
        # Get app data for storage_root
        app_data = self.app_combo.currentData()
        storage_root = app_data.get('storage_root')
        if not storage_root: return False, False
        
        # Phase 28: Fetch all configs for Tag Conflict Check
        if cached_configs is not None:
            folder_configs = cached_configs
        else:
             # Fallback for single calls (if any)
             all_configs_raw = self.db.get_all_folder_configs()
             folder_configs = {k.replace('\\', '/'): v for k, v in all_configs_raw.items()}

        # Get all configs once to avoid repeated DB hits in loop (though DB might cache)
        # For simplicity and performance, we'll just query what we need.
        try:
            with os.scandir(folder_path) as it:
                for entry in it:
                    if entry.name.startswith('.'): continue
                    
                    # Resolve relative path for DB lookup
                    try:
                        rel = os.path.relpath(entry.path, storage_root).replace('\\', '/')
                    except: continue
                    
                    cfg = self.db.get_folder_config(rel) or {}
                    # Priority: target_override > default join
                    t_override = cfg.get('target_override')
                    target_link = t_override or os.path.join(target_root, entry.name)
                    
                    # Check link status with expected source hint
                    status = self.deployer.get_link_status(target_link, expected_source=entry.path)
                    
                    if status['status'] == 'linked':
                        has_linked = True
                    elif status['status'] == 'conflict':
                        has_conflict = True
                    
                    # Phase 28: Tag Conflict Detection for Children
                    # If child is not hard-conflicted, check if it has a Tag Conflict
                    if not has_conflict: # Optimization: if already red, no need to check tag
                        tag = cfg.get('conflict_tag')
                        # Only check unlinked items for passive conflict (Red Line)
                        # (Linked items are Green)
                        if tag and status['status'] != 'linked':
                             tag = tag.strip()
                             scope = cfg.get('conflict_scope') or 'disabled'
                             if scope != 'disabled':
                                 # We need to check against ALL configs.
                                 # This is potentially heavy inside a loop, but we need it.
                                 # Optimization: Fetch all configs ONCE outside loop?
                                 # We can't easily pass it in without changing signature, 
                                 # but self.db.get_all_folder_configs() is cached in memory? 
                                 # Actually the DB class does NOT cache it all in memory across calls usually.
                                 # But for now, let's fetch here or assume caller handles perf?
                                 # Better: We fetch all_configs at start of method.
                                 current_category = os.path.dirname(rel).replace('\\', '/')
                                 
                                 # Iterate all configs to find a match
                                 for other_path, other_cfg in folder_configs.items():
                                     if other_path == rel: continue
                                     
                                     ot = other_cfg.get('conflict_tag')
                                     if not ot or ot.strip() != tag: continue
                                     
                                     if scope == 'category':
                                         oc = os.path.dirname(other_path).replace('\\', '/')
                                         if oc != current_category: continue
                                     
                                     if other_cfg.get('last_known_status') == 'linked' and \
                                        other_cfg.get('conflict_scope', 'disabled') != 'disabled':
                                         has_conflict = True
                                         break
                        
                    if has_linked and has_conflict: break
        except Exception as e:
            self.logger.warning(f"Status scan failed for {folder_path}: {e}")
            
        return has_linked, has_conflict

    def _refresh_category_cards(self):
        """Refresh children status for all Category cards (updates orange borders)."""
        app_data = self.app_combo.currentData()
        if not app_data: return
        target_root = app_data.get(self.current_target_key)
        if not target_root: return
        
        # Phase 28 Optimization: Fetch DB once!
        all_configs_raw = self.db.get_all_folder_configs()
        cached_configs = {k.replace('\\', '/'): v for k, v in all_configs_raw.items()}
        
        for i in range(self.cat_layout.count()):
            item = self.cat_layout.itemAt(i)
            if item and item.widget():
                card = item.widget()
                if hasattr(card, 'path') and hasattr(card, 'set_children_status'):
                    # Pass cache
                    has_linked, has_conflict = self._scan_children_status(card.path, target_root, cached_configs=cached_configs)
                    card.set_children_status(has_linked=has_linked, has_conflict=has_conflict)
        
        # Also refresh package card borders (green for linked, red for conflict)
        self._refresh_package_cards()

    def _refresh_package_cards(self):
        """Refresh link status for all Package cards (updates green/conflict borders)."""
        from src.ui.link_master.item_card import ItemCard
        for i in range(self.pkg_layout.count()):
            item = self.pkg_layout.itemAt(i)
            if item and item.widget():
                card = item.widget()
                if isinstance(card, ItemCard) and hasattr(card, '_check_link_status'):
                    card._check_link_status()
                    card._update_style()

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
            
        except Exception as e:
            self.logger.error(f"Manual rebuild failed: {e}")
