"""
Link Master: Search Functionality Mixin
Phase 19.8: Major search overhaul with modes, depth limit, NOT search
Phase 32: Background thread search to prevent UI freeze
"""
import os
import time
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QObject
from src.core.lang_manager import _
from src.ui.link_master.item_card import ItemCard


class SearchWorker(QObject):
    """Worker to perform file system search in background thread."""
    finished = pyqtSignal(list)  # Emit search results when done
    error = pyqtSignal(str)
    
    def __init__(self, storage_root, folder_configs, non_inheritable, 
                 terms, not_terms, include_tags, exclude_tags, logic, selected_segments):
        super().__init__()
        self.storage_root = storage_root
        self.folder_configs = folder_configs
        self.non_inheritable = non_inheritable
        self.terms = terms
        self.not_terms = not_terms
        self.include_tags = include_tags
        self.exclude_tags = exclude_tags
        self.logic = logic
        self.selected_segments = selected_segments
        self._cancelled = False
    
    def cancel(self):
        self._cancelled = True
    
    def run(self):
        """Execute search in background thread."""
        try:
            results = self._search_two_levels(self.storage_root)
            if not self._cancelled:
                self.finished.emit(results)
        except Exception as e:
            if not self._cancelled:
                self.error.emit(str(e))
    
    def _search_two_levels(self, storage_path):
        """Scan two levels of directories for matching items."""
        results = []
        if not storage_path or not os.path.isdir(storage_path):
            return results
        
        try:
            with os.scandir(storage_path) as cat_iter:
                for cat_entry in cat_iter:
                    if self._cancelled:
                        return results
                    if not cat_entry.is_dir():
                        continue
                    if cat_entry.name.startswith('_'):
                        continue
                    
                    cat_abs = cat_entry.path
                    cat_rel = cat_entry.name
                    cat_config = self.folder_configs.get(cat_rel.replace('\\', '/'), {})
                    cat_type = 'category'
                    
                    cat_own_tags = {t.strip().lower() for t in (cat_config.get('tags') or '').split(',') if t.strip()}
                    cat_effective_tags = cat_own_tags
                    cat_inheritable_tags = cat_own_tags - self.non_inheritable
                    
                    if self._check_match(cat_entry.name, cat_config, cat_effective_tags):
                        results.append({
                            'name': cat_entry.name,
                            'path': cat_abs,
                            'rel_path': cat_rel,
                            'config': cat_config,
                            'type': cat_type,
                            'effective_tags': cat_effective_tags
                        })
                    
                    # Level 2: Packages
                    try:
                        with os.scandir(cat_abs) as pkg_iter:
                            for pkg_entry in pkg_iter:
                                if self._cancelled:
                                    return results
                                if not pkg_entry.is_dir():
                                    continue
                                if pkg_entry.name.startswith('_'):
                                    continue
                                
                                pkg_abs = pkg_entry.path
                                pkg_rel = f"{cat_rel}/{pkg_entry.name}"
                                pkg_config = self.folder_configs.get(pkg_rel.replace('\\', '/'), {})
                                pkg_type = pkg_config.get('folder_type', 'package')
                                
                                pkg_own_tags = {t.strip().lower() for t in (pkg_config.get('tags') or '').split(',') if t.strip()}
                                pkg_effective_tags = pkg_own_tags | cat_inheritable_tags
                                
                                if self._check_match(pkg_entry.name, pkg_config, pkg_effective_tags):
                                    results.append({
                                        'name': pkg_entry.name,
                                        'path': pkg_abs,
                                        'rel_path': pkg_rel,
                                        'config': pkg_config,
                                        'type': pkg_type,
                                        'effective_tags': pkg_effective_tags
                                    })
                    except Exception:
                        pass
        except Exception:
            pass
        
        return results
    
    def _check_match(self, name, config, effective_tags):
        """Check if item matches search criteria."""
        name_lower = name.lower()
        memo = (config.get('memo') or '').lower()
        
        # NOT terms exclusion
        for nt in self.not_terms:
            if nt in name_lower or nt in memo:
                return False
        
        # Exclude tags
        for et in self.exclude_tags:
            if et in effective_tags:
                return False
        
        # Positive matching
        if self.logic == 'and':
            if self.terms and not all(t in name_lower or t in memo for t in self.terms):
                return False
            if self.include_tags and not self.include_tags.issubset(effective_tags):
                return False
        else:  # 'or' logic
            matched = False
            if self.terms:
                if any(t in name_lower or t in memo for t in self.terms):
                    matched = True
            if self.include_tags:
                if self.include_tags & effective_tags:
                    matched = True
            if not self.terms and not self.include_tags:
                matched = True
            if not matched:
                return False
        
        return True


class LMSearchMixin:
    """Mixin providing search functionality for LinkMasterWindow."""
    
    def _perform_search(self):
        """
        Search for categories and packages based on query and selected tags.
        """
        start_t = time.time()
        query = self.search_bar.text().strip().lower()
        selected_segments = self.tag_bar.get_selected_segments()
        selected_tags = {t.lower() for t in self.tag_bar.get_selected_tags()}
        logic = self.search_logic.currentData() or 'or'
        search_mode = getattr(self, 'search_mode', None)
        mode = search_mode.currentData() if search_mode else 'all_packages'
        
        app_data = self.app_combo.currentData()
        if not app_data: return
        
        app_id = app_data.get('id')
        storage_root = app_data.get('storage_root')
        target_root = app_data.get(self.current_target_key)
        
        # If no active filter, just refresh current path normally
        if not query and not selected_tags:
            if hasattr(self, 'current_view_path') and self.current_view_path:
                self._load_items_for_path(self.current_view_path)
            elif storage_root:
                self._load_items_for_path(storage_root)
            
            self.non_inheritable_tags = self._get_non_inheritable_tags_from_json()
            return

        self._show_search_indicator()
        
        folder_configs = self.db.get_all_folder_configs()
        
        # Parse query for terms and NOT terms (! prefix)
        terms = []
        not_terms = []
        for t in query.split():
            t_stripped = t.strip()
            if t_stripped.startswith('!') and len(t_stripped) > 1:
                not_terms.append(t_stripped[1:].lower())  # Remove ! prefix
            elif t_stripped:
                terms.append(t_stripped.lower())
        
        # Parse tags for NOT tags (! prefix)
        include_tags = set()
        exclude_tags = set()
        for tag in selected_tags:
            if tag.startswith('!') and len(tag) > 1:
                exclude_tags.add(tag[1:].lower())
            else:
                include_tags.add(tag.lower())
        
        self.logger.info(f"[Search] terms={terms}, not_terms={not_terms}, include_tags={include_tags}, exclude_tags={exclude_tags}, mode={mode}")
        
        # Get non-inheritable tags
        non_inheritable = getattr(self, 'non_inheritable_tags', set())
        
        # Search function - only scan categories (level 1) and their direct children (level 2 = packages)
        # DO NOT recurse into packages
        def search_two_levels(storage_path):
            results = []
            if not storage_path or not os.path.isdir(storage_path): return results
            
            from PyQt6.QtWidgets import QApplication
            
            try:
                # Level 1: Categories (direct children of storage_root)
                with os.scandir(storage_path) as cat_iter:
                    for cat_entry in cat_iter:
                        # Process UI events to keep UI responsive
                        QApplication.processEvents()
                        
                        if not cat_entry.is_dir(): continue
                        if cat_entry.name.startswith('_'): continue  # Skip _Trash etc
                        
                        cat_abs = cat_entry.path
                        cat_rel = cat_entry.name
                        
                        cat_config = folder_configs.get(cat_rel.replace('\\', '/'), {})
                        
                        # FORCE type based on path depth, not DB
                        # Level 1 = category (no "/" in rel_path)
                        cat_type = 'category'
                        
                        # Category tags
                        cat_own_tags = {t.strip().lower() for t in (cat_config.get('tags') or '').split(',') if t.strip()}
                        cat_effective_tags = cat_own_tags
                        # Filter inheritable tags (for passing to children) - remove non-inheritable
                        cat_inheritable_tags = cat_own_tags - non_inheritable
                        
                        # Check if category matches
                        cat_matches = self._check_match(
                            cat_entry.name, cat_config, cat_effective_tags,
                            terms, not_terms, include_tags, exclude_tags, logic
                        )
                        
                        if cat_matches:
                            results.append({
                                'name': cat_config.get('display_name') or cat_entry.name,
                                'path': cat_abs,
                                'rel_path': cat_rel,
                                'config': cat_config,
                                'type': cat_type,
                                'effective_tags': cat_effective_tags
                            })
                        
                        # Level 2: Packages (direct children of category)
                        # Always scan level 2 - they are packages
                        try:
                            with os.scandir(cat_abs) as pkg_iter:
                                for pkg_entry in pkg_iter:
                                    if not pkg_entry.is_dir(): continue
                                    if pkg_entry.name.startswith('_'): continue
                                    
                                    pkg_abs = pkg_entry.path
                                    pkg_rel = f"{cat_rel}/{pkg_entry.name}"
                                    
                                    pkg_config = folder_configs.get(pkg_rel.replace('\\', '/'), {})
                                    
                                    # FORCE type based on path depth
                                    # Level 2 = package (has "/" in rel_path)
                                    pkg_type = 'package'
                                    
                                    # Package tags (inherit from category, but only inheritable tags)
                                    can_inherit = pkg_config.get('inherit_tags', 1) != 0
                                    pkg_own_tags = {t.strip().lower() for t in (pkg_config.get('tags') or '').split(',') if t.strip()}
                                    # Use cat_inheritable_tags (filtered), not cat_effective_tags
                                    pkg_effective_tags = pkg_own_tags | (cat_inheritable_tags if can_inherit else set())
                                    
                                    # Check if package matches
                                    pkg_matches = self._check_match(
                                        pkg_entry.name, pkg_config, pkg_effective_tags,
                                        terms, not_terms, include_tags, exclude_tags, logic,
                                        selected_segments=selected_segments
                                    )
                                    
                                    if pkg_matches:
                                        results.append({
                                            'name': pkg_config.get('display_name') or pkg_entry.name,
                                            'path': pkg_abs,
                                            'rel_path': pkg_rel,
                                            'config': pkg_config,
                                            'type': pkg_type,
                                            'effective_tags': pkg_effective_tags
                                        })
                        except Exception as e:
                            self.logger.error(f"Search Error in category {cat_abs}: {e}")
                            
            except Exception as e:
                self.logger.error(f"Search Error in {storage_path}: {e}")
                
            return results

        all_results = search_two_levels(storage_root)
        
        self.logger.info(f"[Search] Total results: {len(all_results)}")
        
        # Debug: Log types of each result
        for r in all_results[:10]:  # First 10 for debugging
            self.logger.info(f"[Search] Result: {r['name']} -> type={r['type']}, rel_path={r['rel_path']}")
        
        # Split results by type
        cat_results = [r for r in all_results if r['type'] == 'category']
        pkg_results = [r for r in all_results if r['type'] == 'package']
        
        self.logger.info(f"[Search] Before mode filter: cats={len(cat_results)}, pkgs={len(pkg_results)}, mode={mode}")

        
        # Apply search mode filtering
        if mode == 'categories_only':
            # Only show categories that match
            pkg_results = []
        elif mode == 'cats_with_packages':
            # Show categories that contain matching packages
            if pkg_results:
                matched_parent_cats = set()
                for pkg in pkg_results:
                    parts = pkg['rel_path'].replace('\\', '/').split('/')
                    if len(parts) >= 1:
                        matched_parent_cats.add(parts[0])
                
                # Filter categories to only those with matching packages
                cat_results = [c for c in cat_results if c['name'] in matched_parent_cats]
                
                # Also add parent categories that aren't in results
                for cat_name in matched_parent_cats:
                    cat_path = os.path.join(storage_root, cat_name)
                    if os.path.isdir(cat_path):
                        if not any(c['name'] == cat_name for c in cat_results):
                            cat_results.append({
                                'name': cat_name,
                                'path': cat_path,
                                'rel_path': cat_name,
                                'config': folder_configs.get(cat_name, {}),
                                'type': 'category'
                            })
            else:
                cat_results = []  # No matching packages = no categories
        # mode == 'all_packages' (default) - show all matches as-is

        self._search_context = {
            'target_root': target_root, 
            'app_id': app_id, 
            'storage_root': storage_root, 
            'query': query
        }

        self._display_search_results(cat_results, pkg_results)
    
    def _check_match(self, name, config, effective_tags, terms, not_terms, include_tags, exclude_tags, logic, selected_segments=None):
        """Helper to check if an item matches search criteria."""
        # Tag matching (for explicit tag selection via tag bar)
        tag_match = True
        
        # Phase 20: Segment-based logic (OR within separator, AND between separators)
        if selected_segments:
            for segment in selected_segments:
                # Each segment (OR-group) must have at least one match in effective_tags
                if not any(tag in effective_tags for tag in segment):
                    tag_match = False
                    break
        elif include_tags:
            # Fallback for simple flat tag sets
            tag_match = bool(include_tags & effective_tags)
        
        if exclude_tags and tag_match:
            if exclude_tags & effective_tags:
                tag_match = False
        
        # Text matching - search BOTH folder name AND tags
        text_match = True
        name_lower = name.lower()
        tags_str = " ".join(effective_tags)
        author_lower = (config.get('author') or "").lower()
        searchable_text = f"{name_lower} {author_lower} {tags_str}"
        
        if terms:
            # Match if term is in name OR in any tag
            text_match = all(term in searchable_text for term in terms)
        
        if not_terms and text_match:
            if any(nt in searchable_text for nt in not_terms):
                text_match = False
        
        return tag_match and text_match
        
    def _display_search_results(self, cat_results, pkg_results):
        """Display search results in respective areas."""
        ctx = self._search_context
        query = ctx['query']
        target_root = ctx['target_root']
        storage_root = ctx['storage_root']
        
        self.cat_result_label.setText(_("🔍 {n} hit(s)").format(n=len(cat_results)) if cat_results else _("🔍 0 hits"))
        self.pkg_result_label.setText(_("🔍 {n} hit(s)").format(n=len(pkg_results)) if pkg_results else _("🔍 0 hits"))
        
        # Phase 28: CARD POOLING - Respect the toggle
        use_pool = getattr(self, 'search_cache_enabled', False)
        
        # Phase 32: Remove orphan QLabel widgets (e.g., "No packages match" message) from layouts
        # before releasing ItemCard instances.
        for layout in [getattr(self, 'cat_layout', None), getattr(self, 'pkg_layout', None)]:
            if layout:
                items_to_remove = []
                for i in range(layout.count()):
                    item = layout.itemAt(i)
                    if item and item.widget() and isinstance(item.widget(), QLabel):
                        items_to_remove.append(item.widget())
                for widget in items_to_remove:
                    layout.removeWidget(widget)
                    widget.deleteLater()
        
        # Always use release call to ensure tracking lists are cleared correctly
        # If use_pool is False, the cards will be released to the pool, but 
        # not acquired back in the loop below (which uses ItemCard directly).
        self._release_all_active_cards("all")

        # Phase 31: Fetch visibility per mode
        cat_mode = getattr(self, 'cat_display_override', None) or getattr(self, 'current_view_display_mode', None) or 'mini_image'
        pkg_mode = getattr(self, 'pkg_display_override', None) or getattr(self, 'current_pkg_display_mode', None) or 'mini_image'
        
        cat_show_link = getattr(self, f'cat_{cat_mode}_show_link', True)
        cat_show_deploy = getattr(self, f'cat_{cat_mode}_show_deploy', True)
        pkg_show_link = getattr(self, f'pkg_{pkg_mode}_show_link', True)
        pkg_show_deploy = getattr(self, f'pkg_{pkg_mode}_show_deploy', True)
        opacity = getattr(self, 'deploy_button_opacity', 0.8)

        # 1. Categories
        if cat_results:
            self.logger.info(f"[Profile] Search: Displaying {min(len(cat_results), 50)} categories...")
        
        # Pull app_data once outside loops
        app_data = self.app_combo.currentData()
        app_name = app_data.get('name') if app_data else "Unknown"

        for r in cat_results[:50]:
            item_abs_path = r['path']
            
            img_path = None
            thumb = self.thumbnail_manager.get_thumbnail_path(app_name, r['rel_path'])
            if os.path.exists(thumb):
                img_path = thumb
            elif r['config'].get('image_path') and os.path.exists(r['config'].get('image_path')):
                 img_path = r['config'].get('image_path')
            
            is_package_val = (r['type'] == 'package')

            if use_pool:
                card = self._acquire_card("category")
                card.update_data(
                    name=r['name'],
                    path=item_abs_path,
                    image_path=img_path,
                    target_dir=target_root,
                    storage_root=storage_root,
                    db=self.db,
                    app_name=app_name,
                    thumbnail_manager=self.thumbnail_manager,
                    show_link=cat_show_link,
                    show_deploy=cat_show_deploy,
                    deploy_button_opacity=opacity,
                    # Pass full scanner metadata
                    **{k: v for k, v in r.items() if k not in ['name', 'path', 'item', 'config']}
                )
            else:
                card = ItemCard(
                    name=r['name'], path=item_abs_path, image_path=img_path,
                    loader=self.image_loader, deployer=self.deployer, target_dir=target_root,
                    storage_root=storage_root, db=self.db,
                    app_name=app_name,
                    is_package=is_package_val,
                    is_registered=bool(r['config']),
                    thumbnail_manager=self.thumbnail_manager,
                    show_link=cat_show_link,
                    show_deploy=cat_show_deploy,
                    deploy_button_opacity=opacity,
                    # Pass config specifically if it exists
                    target_override=r['config'].get('target_override'),
                    deployment_rules=r['config'].get('deployment_rules'),
                    manual_preview_path=r['config'].get('manual_preview_path'),
                )
                self._active_cat_cards.append(card)
                # Connect signals for non-pooled cards manually
                card.single_clicked.connect(lambda p=item_abs_path: self._handle_item_click(p, "category"))
                if not is_package_val:
                    card.double_clicked.connect(self._on_category_selected)

            # Scaling & Layout
            cat_mode = getattr(self, 'cat_display_override', None) or getattr(self, 'current_view_display_mode', None) or 'mini_image'
            card.set_display_mode(cat_mode)
            
            # Apply proper card dimensions
            scale = getattr(self, f'cat_{cat_mode}_scale', 1.0)
            base_w = getattr(self, f'cat_{cat_mode}_card_w', 160)
            base_h = getattr(self, f'cat_{cat_mode}_card_h', 200)
            base_img_w = getattr(self, f'cat_{cat_mode}_img_w', 140)
            base_img_h = getattr(self, f'cat_{cat_mode}_img_h', 120)
            card.set_card_params(base_w, base_h, base_img_w, base_img_h, scale)
            
            self.cat_layout.addWidget(card)
            card.show()
        
        if cat_results:
            self.logger.info(f"[Profile] Search: Category display finished.")
        else:
            lbl = QLabel(_("No categories match: {q}").format(q=query))
            lbl.setStyleSheet("color: #888; font-style: italic;")
            self.cat_layout.addWidget(lbl)
        
        # 2. Packages
        if pkg_results:
            self.logger.info(f"[Profile] Search: Displaying {min(len(pkg_results), 100)} packages...")

        for r in pkg_results[:100]:
            item_abs_path = r['path']
            
            img_path = None
            thumb = self.thumbnail_manager.get_thumbnail_path(app_name, r['rel_path'])
            if os.path.exists(thumb):
                img_path = thumb
            elif r['config'].get('image_path') and os.path.exists(r['config'].get('image_path')):
                 img_path = r['config'].get('image_path')
            
            display_name = r['config'].get('display_name') or r['name']

            if use_pool:
                card = self._acquire_card("package")
                card.update_data(
                    name=display_name,
                    path=item_abs_path,
                    image_path=img_path,
                    target_dir=target_root,
                    storage_root=storage_root,
                    db=self.db,
                    app_name=app_name,
                    thumbnail_manager=self.thumbnail_manager,
                    show_link=pkg_show_link,
                    show_deploy=pkg_show_deploy,
                    deploy_button_opacity=opacity,
                    # Pass full scanner metadata (is_partial, is_library_alt_version, has_logical_conflict, etc)
                    **{k: v for k, v in r.items() if k not in ['name', 'path', 'item', 'config']}
                )
            else:
                card = ItemCard(
                    name=display_name, path=item_abs_path, image_path=img_path,
                    loader=self.image_loader, deployer=self.deployer, target_dir=target_root,
                    storage_root=storage_root, db=self.db, 
                    app_name=app_name,
                    is_package=True,
                    is_registered=bool(r['config']),
                    thumbnail_manager=self.thumbnail_manager,
                    show_link=pkg_show_link,
                    show_deploy=pkg_show_deploy,
                    deploy_button_opacity=opacity,
                    # Pass config specifically if it exists
                    target_override=r['config'].get('target_override'),
                    deployment_rules=r['config'].get('deployment_rules'),
                    manual_preview_path=r['config'].get('manual_preview_path'),
                )
                self._active_pkg_cards.append(card)
                card.single_clicked.connect(lambda p=item_abs_path: self._handle_item_click(p, "package"))
                card.deploy_changed.connect(self._refresh_category_cards)
            
            # Use pkg style setting
            pkg_mode = getattr(self, 'pkg_display_override', None) or getattr(self, 'current_pkg_display_mode', None) or 'mini_image'
            card.set_display_mode(pkg_mode)
            
            # Apply proper card dimensions
            scale = getattr(self, f'pkg_{pkg_mode}_scale', 1.0)
            base_w = getattr(self, f'pkg_{pkg_mode}_card_w', 160)
            base_h = getattr(self, f'pkg_{pkg_mode}_card_h', 200)
            base_img_w = getattr(self, f'pkg_{pkg_mode}_img_w', 140)
            base_img_h = getattr(self, f'pkg_{pkg_mode}_img_h', 120)
            card.set_card_params(base_w, base_h, base_img_w, base_img_h, scale)

            self.pkg_layout.addWidget(card)
            card.show()
        
        if pkg_results:
            self.logger.info(f"[Profile] Search: Package display finished.")
        else:
            lbl = QLabel(_("No packages match: {q}").format(q=query))
            lbl.setStyleSheet("color: #888; font-style: italic;")
            self.pkg_layout.addWidget(lbl)
        
        self._hide_search_indicator()
        
        # Phase 28: Force layout refresh to avoid overlapping/alignment issues
        if hasattr(self, 'cat_layout'):
            self.cat_layout.invalidate()
            if self.cat_layout.parentWidget():
                self.cat_layout.parentWidget().updateGeometry()
        if hasattr(self, 'pkg_layout'):
            self.pkg_layout.invalidate()
            if self.pkg_layout.parentWidget():
                self.pkg_layout.parentWidget().updateGeometry()
        
        # Refresh orange borders for categories with linked packages
        self._refresh_category_cards()
        
        # Phase 28: Logging search profile
        if hasattr(self, 'logger'):
            duration = time.time() - start_t if 'start_t' in locals() else -1
            self.logger.info(f"[Profile] Search display finished. Total duration: {duration:.3f}s")
    
    def _show_search_indicator(self):
        """Show floating search indicator overlay with animated dots."""
        if not hasattr(self, '_search_overlay'):
            self._search_overlay = QLabel(_("🔍 Searching"), self)
            self._search_overlay.setStyleSheet("""
                background-color: rgba(39, 174, 96, 0.9);
                color: white;
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            """)
            self._search_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self._search_dot_count = 0
        
        if not hasattr(self, '_search_anim_timer'):
            self._search_anim_timer = QTimer(self)
            self._search_anim_timer.timeout.connect(self._update_search_dots)
        
        self._search_anim_timer.start(400)
        
        self._search_overlay.setText(_("🔍 Searching"))
        self._search_overlay.adjustSize()
        x = (self.width() - self._search_overlay.width()) // 2
        y = 80
        self._search_overlay.move(x, y)
        self._search_overlay.show()
        self._search_overlay.raise_()
    
    def _update_search_dots(self):
        """Animate dots in search indicator."""
        self._search_dot_count = (self._search_dot_count % 3) + 1
        dots = "." * self._search_dot_count
        self._search_overlay.setText(_("🔍 Searching{dots}").format(dots=dots))
        self._search_overlay.adjustSize()
    
    def _hide_search_indicator(self):
        """Hide search indicator overlay and stop animation."""
        if hasattr(self, '_search_anim_timer') and self._search_anim_timer:
            self._search_anim_timer.stop()
        if hasattr(self, '_search_overlay') and self._search_overlay:
            self._search_overlay.hide()
    
    def _clear_search(self):
        """Clear search and restore normal view."""
        self.search_bar.clear()
        self.tag_bar.clear_selection()  # Also clear tag selection
        
        self.cat_result_label.setText("")
        self.pkg_result_label.setText("")
        
        # Phase 28: Restore view AND selected category
        # Need to delay category selection to allow view to load first (async scan)
        saved_category = getattr(self, 'current_path', None)
        
        if hasattr(self, 'current_view_path') and self.current_view_path:
            self._load_items_for_path(self.current_view_path, force=True)
            
            # Delay category selection to allow scanner to complete
            if saved_category:
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(300, lambda: self._on_category_selected(saved_category))
