import os
from typing import List, Dict
from src.ui.link_master.item_card import ItemCard

# Phase 28: Add sip to check for deleted C++ objects
try:
    from PyQt6 import sip
except ImportError:
    import sip # Fallback

class LMCardPoolMixin:
    """Phase 28: Manages separate pools for Category and Package cards to ensure correct reuse."""
    
    def _init_card_pool(self):
        """Initializes the pooling structures."""
        # Pools for unused widgets
        self._cat_pool: List[ItemCard] = []
        self._pkg_pool: List[ItemCard] = []
        
        # Tracking active (visible) widgets
        self._active_cat_cards: List[ItemCard] = []
        self._active_pkg_cards: List[ItemCard] = []
        
        # User configurable settings (defaults)
        self.max_pool_size = 100 # Per pool
        self.search_cache_enabled = False
        
        # Phase 2: Load opacity from registry
        self.deploy_button_opacity = 0.8 # Default
        if hasattr(self, 'registry') and self.registry:
            try:
                saved_opacity = self.registry.get_setting('deploy_button_opacity')
                if saved_opacity:
                    self.deploy_button_opacity = int(saved_opacity) / 100.0
            except: pass

    def _set_deploy_button_opacity(self, opacity: int):
        """Update deploy button opacity for all cards in pool and active."""
        f_opacity = opacity / 100.0
        self.deploy_button_opacity = f_opacity
        
        # Phase 2: Persist to registry
        if hasattr(self, 'registry') and self.registry:
            try:
                self.registry.set_setting('deploy_button_opacity', str(opacity))
            except: pass
            
        # Update all active cards
        for card in self._active_cat_cards + self._active_pkg_cards:
            if not sip.isdeleted(card):
                card.set_deploy_button_opacity(f_opacity)
                
        # Update pooled cards
        for card in self._cat_pool + self._pkg_pool:
            if not sip.isdeleted(card):
                card.set_deploy_button_opacity(f_opacity)

    def _set_pool_size(self, size: int):
        """Phase 28: Adjust maximum number of widgets stored in each pool."""
        self.max_pool_size = size
        
        # Phase 28: Persist to GLOBAL registry (not app-specific DB)
        if hasattr(self, 'registry') and self.registry:
            try:
                self.registry.set_setting('pool_size', str(size))
            except: pass
        
        # Prune pools if exceeding new limit
        while len(self._cat_pool) > size:
            card = self._cat_pool.pop()
            card.setParent(None)
            card.deleteLater()
        while len(self._pkg_pool) > size:
            card = self._pkg_pool.pop()
            card.setParent(None)
            card.deleteLater()

    def _set_search_cache_enabled(self, enabled: bool):
        """Phase 28: Toggle search result pooling."""
        self.search_cache_enabled = enabled

    def _acquire_card(self, item_type: str = "package") -> ItemCard:
        """Retrieves a card from the appropriate pool or creates a new one."""
        pool = self._pkg_pool if item_type == "package" else self._cat_pool
        active_list = self._active_pkg_cards if item_type == "package" else self._active_cat_cards
        
        card = None
        while pool:
            candidate = pool.pop()
            if not sip.isdeleted(candidate):
                card = candidate
                # Phase 28 Fix: Reset Visual State on reuse
                if hasattr(card, 'set_selected'):
                    card.set_selected(False, False)
                break
        
        if not card:
            card = self._create_new_base_card(item_type)
            
        if card not in active_list:
            active_list.append(card)
            
        return card

    def _create_new_base_card(self, item_type: str) -> ItemCard:
        """Factory method for creating a fresh ItemCard and connecting its signals."""
        app_data = self.app_combo.currentData() or {}
        is_package = (item_type == "package")
        
        # Get app_name and storage_root from app_data
        app_name = app_data.get('name')
        storage_root = app_data.get('storage_root')
        
        card = ItemCard(
            name="Loading...",
            path="",
            loader=self.image_loader,
            deployer=self.deployer,
            storage_root=storage_root,
            db=self.db,
            is_package=is_package,
            app_name=app_name,
            thumbnail_manager=self.thumbnail_manager,
            app_deploy_default=app_data.get('deployment_type', 'folder'),
            app_conflict_default=app_data.get('conflict_policy', 'backup')
        )
        
        # Phase 2: Apply current opacity settings
        opacity = getattr(self, 'deploy_button_opacity', 0.8)
        
        # Phase 31: Get current display toggles from current mode settings
        # Determine which mode this card type will use
        if is_package:
            pkg_mode = getattr(self, 'pkg_display_override', None) or 'image_text'
            show_link = getattr(self, f'pkg_{pkg_mode}_show_link', True)
            show_deploy = getattr(self, f'pkg_{pkg_mode}_show_deploy', True)
        else:
            cat_mode = getattr(self, 'cat_display_override', None) or 'image_text'
            show_link = getattr(self, f'cat_{cat_mode}_show_link', True)
            show_deploy = getattr(self, f'cat_{cat_mode}_show_deploy', True)
        
        card.update_data(
            deploy_button_opacity=opacity,
            show_link=show_link,
            show_deploy=show_deploy
        )
        
        # Permanent signal connections (Handlers are stable across reuses)
        card.request_move_to_unclassified.connect(self._on_package_move_to_unclassified)
        card.request_move_to_trash.connect(self._on_package_move_to_trash)
        card.request_restore.connect(self._on_package_restore)
        card.request_reorder.connect(self._reorder_item)
        # 🚨 DEBOUNCED: Use request method to coalesce rapid updates
        card.deploy_changed.connect(self._request_refresh_category_cards)
        card.deploy_changed.connect(self._update_total_link_count)
        
        # Phase 30: Direct deployment toggle from card overlay button
        if hasattr(self, '_on_card_deployment_requested'):
            card.request_deployment_toggle.connect(self._on_card_deployment_requested)
        elif hasattr(self, 'toggle_deployment'):
            card.request_deployment_toggle.connect(self.toggle_deployment)
        else:
             # Fallback/Direct if mixin not fully initialized
             card.request_deployment_toggle.connect(card.toggle_deployment)
        
        # Connect partial redeploy request
        if hasattr(self, '_handle_redeploy_request'):
            card.request_redeploy.connect(self._handle_redeploy_request)
        
        # Phase 28: Alt+Double-Click to open property editor for any item
        if hasattr(self, '_open_properties_for_path'):
            card.request_edit_properties.connect(self._open_properties_for_path)
            
        # Phase 32: Focus library in management tab
        if hasattr(self, '_on_request_focus_library'):
            card.request_focus_library.connect(self._on_request_focus_library)
        
        if is_package:
            card.single_clicked.connect(lambda p: self._handle_item_click(p, "package"))
            # Phase 28: Open property view instead of batch edit
            if hasattr(self, '_show_property_view_for_card'):
                card.double_clicked.connect(lambda p: self._show_property_view_for_card(p))
            else:
                self.logger.error("[Pool] _show_property_view_for_card not available for package double-click!")
        else:
            card.single_clicked.connect(lambda p: self._handle_item_click(p, "category"))
            # Phase 28: Debug - verify method exists before connecting
            if hasattr(self, '_navigate_to_path'):
                card.double_clicked.connect(self._navigate_to_path)
            else:
                self.logger.error("[Pool] _navigate_to_path not available for double-click connection!")
            
        return card

    def _release_all_active_cards(self, context="all"):
        """Returns active cards to their respective pools with optimized layout operations."""
        # Phase 33: Batch mode optimization - disable updates during mass removal
        cat_layout = getattr(self, 'cat_layout', None)
        pkg_layout = getattr(self, 'pkg_layout', None)
        
        # 1. Categories
        if context in ["all", "category", "cat", "view"]:
            if cat_layout:
                # Batch removal - collect all cards first, then remove
                cards_to_release = list(self._active_cat_cards)
                self._active_cat_cards.clear()
                
                for card in cards_to_release:
                    if sip.isdeleted(card):
                        continue
                    try:
                        if not isinstance(card, ItemCard):
                            card.hide()
                            card.setParent(None)
                            card.deleteLater()
                            continue
                        
                        # Phase 33: Just hide, don't removeWidget yet
                        # The layout will be cleared in batch below
                        card.hide()
                        
                        if len(self._cat_pool) < self.max_pool_size:
                            self._cat_pool.append(card)
                        else:
                            card.setParent(None)
                            card.deleteLater()
                    except (RuntimeError, AttributeError):
                        continue
                
                # Phase 33: Clear layout in one batch operation
                while cat_layout.count():
                    item = cat_layout.takeAt(0)
                    # Widget already hidden, no need to hide again

        # 2. Packages
        if context in ["all", "package", "pkg", "contents"]:
            if pkg_layout:
                cards_to_release = list(self._active_pkg_cards)
                self._active_pkg_cards.clear()
                
                for card in cards_to_release:
                    if sip.isdeleted(card):
                        continue
                    try:
                        if not isinstance(card, ItemCard):
                            card.hide()
                            card.setParent(None)
                            card.deleteLater()
                            continue
                        
                        card.hide()
                        
                        if len(self._pkg_pool) < self.max_pool_size:
                            self._pkg_pool.append(card)
                        else:
                            card.setParent(None)
                            card.deleteLater()
                    except (RuntimeError, AttributeError):
                        continue
                
                while pkg_layout.count():
                    item = pkg_layout.takeAt(0)

    def _release_card(self, card: ItemCard):
        """Releases a single card back to its pool."""
        if sip.isdeleted(card): return
        if not isinstance(card, ItemCard): return
        
        # Determine pool based on its role
        is_package = card.is_package
        active_list = self._active_pkg_cards if is_package else self._active_cat_cards
        pool = self._pkg_pool if is_package else self._cat_pool
        
        if card in active_list:
            active_list.remove(card)
            
        # Remove from layout if possible
        if is_package and hasattr(self, 'pkg_layout'):
            self.pkg_layout.removeWidget(card)
        elif not is_package and hasattr(self, 'cat_layout'):
            self.cat_layout.removeWidget(card)
            
        card.hide()
        
        if len(pool) < self.max_pool_size:
            pool.append(card)
        else:
            card.setParent(None)
            card.deleteLater()

    def _get_active_card_by_path(self, path: str) -> ItemCard:
        """Utility to find an already visible card. Robust normalization."""
        if not path: return None
        try:
            # Phase 28 Fix: Always normalize to forward slashes for reliable matching regardless of input source
            target = os.path.normpath(path).replace('\\', '/').lower()
        except: return None
        
        for card in self._active_cat_cards + self._active_pkg_cards:
            if not sip.isdeleted(card):
                try:
                    # Use ItemCard's pre-calculated norm_path for speed and stability
                    card_path = getattr(card, 'norm_path', '').lower()
                    if not card_path:
                        card_path = os.path.normpath(card.path).replace('\\', '/').lower()

                    if card_path == target:
                        return card
                except: continue
        return None
