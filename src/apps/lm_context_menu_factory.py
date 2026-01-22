""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を介すること。
"""

import os
from PyQt6.QtWidgets import QMenu
from src.core.lang_manager import _

def create_item_context_menu(window, rel_path, is_package_context=False):
    """Centralized factory to create a context menu for any item (Category or Package).
    Used by ItemCard, ExplorerPanel, and Breadcrumbs.
    """
    if not window.storage_root: return None
    full_src = os.path.join(window.storage_root, rel_path)
    if not os.path.exists(full_src): return None
    
    config = window.db.get_folder_config(rel_path) or {}
    # Check for both legacy _Trash and new resource/app/{app}/Trash paths
    path_normalized = rel_path.replace('\\\\', '/')
    is_trash_view = "_Trash" in path_normalized or "/Trash" in path_normalized
    
    menu = QMenu(window)
    menu.setStyleSheet(window._menu_style())
    
    folder_name = os.path.basename(rel_path) if rel_path else _("Root")
    
    # Phase 33: Simplified Root Menu
    if not rel_path:
        # 1. Deploy All
        act_dep = menu.addAction(_("🚀 Deploy Links (Deploy All)"))
        act_dep.triggered.connect(lambda: window._handle_deploy_single(rel_path))
        
        menu.addSeparator()
        
        # 2. Open in Explorer - use full_src which equals storage_root for root menu
        storage_path = window.storage_root  # Capture value now, not later
        act_explore = menu.addAction(_("📁 Open in Explorer"))
        act_explore.triggered.connect(lambda checked=False, p=storage_path: window._open_path_in_explorer(p))
        
        return menu

    menu.addAction(_("Category/Package: {name}").format(name=folder_name)).setEnabled(False)
    menu.addSeparator()

    # 1. Deployment Actions (or Restore if in Trash)
    if is_trash_view:
        act_restore = menu.addAction(_("📦 Restore to Original"))
        act_restore.triggered.connect(lambda: window._on_package_restore(full_src))
    else:
        app_data = window.app_combo.currentData()
        target_dir = app_data.get(window.current_target_key) if app_data else None
        
        if window.deployer and target_dir:
            # Phase 5 & 7: Standardized Rule Resolution
            deploy_rule = config.get('deploy_rule')
            if not deploy_rule or deploy_rule in ("default", "inherit"):
                # Fallback to legacy deploy_type if set
                legacy_type = config.get('deploy_type')
                if legacy_type and legacy_type != 'folder':
                    deploy_rule = legacy_type
                else:
                    # Determine App-Default based on current target key
                    current_target_key = getattr(window, 'current_target_key', 'target_root')
                    app_rule_key = 'deployment_rule'
                    if current_target_key == 'target_root_2': app_rule_key = 'deployment_rule_b'
                    elif current_target_key == 'target_root_3': app_rule_key = 'deployment_rule_c'
                    
                    app_default_rule = app_data.get(app_rule_key) or app_data.get('deployment_rule', 'folder')
                    deploy_rule = app_default_rule
            
            # Reconstruct Target Path based on Rule & Selection logic (Phase 42)
            # 1. Resolve Target Base (Root)
            target_base = target_dir # Default to current app target root
            
            sel = config.get('target_selection')
            ov_val = config.get('target_override')
            
            if sel == 'primary': 
                target_base = app_data.get('target_root', target_base)
            elif sel == 'secondary': 
                target_base = app_data.get('target_root_2', target_base)
            elif sel == 'tertiary': 
                target_base = app_data.get('target_root_3', target_base)
            elif sel == 'custom' and ov_val:
                target_base = ov_val
            elif ov_val: # Legacy fallback
                # Try simple match? Or just treat as custom if no selection
                 target_base = ov_val
                 
            # 2. Join with item name based on rule
            # Phase: Use correct hierarchical mirroring for Tree mode (Sync with ItemCard logic)
            target_link = target_base # fallback
            
            if not sel and not ov_val: # Standard default
                if deploy_rule == 'files':
                    target_link = target_base
                elif deploy_rule == 'tree':
                    import json
                    skip_val = 0
                    rules_json = config.get('deployment_rules')
                    if rules_json:
                        try:
                            rules_obj = json.loads(rules_json)
                            skip_val = int(rules_obj.get('skip_levels', 0))
                        except: pass
                    
                    # Use accurate relative path from storage root for mirroring
                    try:
                        # rel_path is already relative to storage_root
                        parts = rel_path.replace('\\', '/').split('/')
                        if len(parts) > skip_val:
                            mirrored = "/".join(parts[skip_val:])
                            target_link = os.path.join(target_base, mirrored)
                        else:
                            target_link = target_base
                    except:
                        target_link = os.path.join(target_base, folder_name)
                else:
                    target_link = os.path.join(target_base, folder_name)

            else:
                # Explicit Target (Override/Selection) logic - Simple append of folder name
                target_link = os.path.join(target_base, folder_name)

            # Skip the old block
            if False:
             target_link = config.get('target_override')
             if not target_link:
                if deploy_rule == 'files':
                    target_link = target_dir
                elif deploy_rule == 'tree':
                    import json
                    skip_val = 0
                    rules_json = config.get('deployment_rules')
                    if rules_json:
                        try:
                            rules_obj = json.loads(rules_json)
                            skip_val = int(rules_obj.get('skip_levels', 0))
                        except: pass
                    
                    parts = rel_path.replace('\\', '/').split('/')
                    if len(parts) > skip_val:
                        mirrored = "/".join(parts[skip_val:])
                        target_link = os.path.join(target_dir, mirrored)
                    else:
                        target_link = target_dir
                else:
                    target_link = os.path.join(target_dir, folder_name)

                    target_link = os.path.join(target_dir, folder_name)
            
            # Phase 14 Fix: Resolve transfer_mode for accurate status check
            tm = config.get('transfer_mode')
            if not tm or tm == 'KEEP':
                # Try getting parent mode
                try:
                    p_rel = os.path.dirname(rel_path)
                    if p_rel and p_rel != '.' and p_rel != rel_path:
                         p_conf = window.db.get_folder_config(p_rel)
                         if p_conf:
                             tm = p_conf.get('transfer_mode')
                except: pass
            
            if not tm or tm == 'KEEP':
                 tm = app_data.get('transfer_mode', 'symlink')

            # Phase: Resolve deploy_rule specifically for detection
            deploy_rule = config.get('deploy_rule')
            if not deploy_rule or deploy_rule == 'inherit':
                deploy_rule = config.get('deploy_type', 'folder')
            if deploy_rule == 'flatten': deploy_rule = 'files'

            # Fix target_link for Files mode if not already set by overrides
            if deploy_rule == 'files' and not config.get('target_override'):
                 target_link = target_dir

            # Phase 51: Parse rules for exclude-aware check in Context Menu
            rules_dict = {}
            rules_str = config.get('deployment_rules')
            if rules_str:
                try:
                    import json
                    rules_dict = json.loads(rules_str)
                except: pass

            status_res = window.deployer.get_link_status(
                target_link, 
                expected_source=full_src, 
                expected_transfer_mode=tm, 
                deploy_rule=deploy_rule,
                rules=rules_dict
            )
            status = status_res.get('status', 'none')

            
            # Phase 28: Check Tag Conflict
            tag_conflict = window._check_tag_conflict(rel_path, config, app_data)
            
            # Phase: Detect if this is a Category (has subfolders with packages)
            is_category = False
            
            # Use explicit context flag if provided (e.g. from Package List)
            # If is_package_context is True, we force it to be treated as a package (Deploy Link)
            is_package_view = is_package_context
            
            # Also check global mode ONLY if we are generic (but careful not to override explicit context)
            if not is_package_view and hasattr(window, 'search_mode') and hasattr(window.search_mode, 'currentData'):
                # Only trust global mode if we are essentially in a "Package Only" environment
                # BUT user said Top is Category View. So global mode 'all_packages' might be active while we click on Top.
                # So we should rely more on is_package_context passed by the caller.
                pass 
            
            if not is_package_view:
                # 1. Prioritize explicit config if available
                db_type = config.get('folder_type')
                if db_type == 'category':
                    is_category = True
                elif db_type == 'package':
                    is_category = False
                else:
                    # 2. Heuristic check (auto-detect)
                    # If an explicit deployment rule is set, it's very likely a package, even if it has subfolders.
                    if deploy_rule in ('tree', 'files', 'custom'):
                        is_category = False
                    else:
                        # Standard heuristic (Category = contains subdirectories)
                        try:
                            for item in os.listdir(full_src):
                                if os.path.isdir(os.path.join(full_src, item)) and not item.startswith('.') and item not in ('_Trash', 'Trash'):
                                    is_category = True
                                    break
                        except:
                            pass
            
            if is_category:
                # Category-specific menu
                category_status = config.get('category_deploy_status')
                if category_status == 'deployed':
                    act_unlink_cat = menu.addAction(_("🔗 Unlink Category (Unlink All)"))
                    act_unlink_cat.triggered.connect(lambda: window._handle_unlink_category(rel_path))
                else:
                    act_dep_cat = menu.addAction(_("📦 Deploy Category (All Packages)"))
                    act_dep_cat.triggered.connect(lambda: window._handle_deploy_category(rel_path))
            elif status in ('linked', 'partial'):
                if status == 'partial':
                    act_redeploy = menu.addAction(_("⚠ Re-deploy (Repair)"))
                    act_redeploy.triggered.connect(lambda: window._deploy_single(rel_path, update_ui=True))

                act_rem = menu.addAction(_("🔗 Unlink (Remove Safe)"))
                act_rem.triggered.connect(lambda: window._handle_unlink_single(rel_path))
            elif status == 'conflict':
                menu.addAction(_("⚠ Conflict: File Exists")).setEnabled(False)
                act_swap = menu.addAction(_("🔄 Overwrite Target with Link"))
                act_swap.setToolTip(_("Delete the conflicting file in target and create a symlink to this source."))
                act_swap.triggered.connect(lambda: window._handle_conflict_swap(rel_path, target_link))
            elif tag_conflict:
                # Phase 28: Tag Conflict Menu
                menu.addAction(_("⚠ Conflict: Tag '{tag}'").format(tag=tag_conflict['tag'])).setEnabled(False)
                act_swap = menu.addAction(_("🔄 Overwrite Target (Swap)"))
                act_swap.setToolTip(_("Disable '{name}' and enable this item.").format(name=tag_conflict['name']))
                # Route to _handle_deploy_single which now has the Swap Dialog
                act_swap.triggered.connect(lambda: window._handle_deploy_single(rel_path))
            else:
                act_dep = menu.addAction(_("🚀 Deploy Link"))
                act_dep.triggered.connect(lambda: window._handle_deploy_single(rel_path))

    # 2. Favorites (moved above Visibility)
    if not is_trash_view:
        is_favorite = bool(config.get('is_favorite', 0))
        if is_favorite:
            act_fav = menu.addAction("❇ " + _("Remove from Favorites"))
            act_fav.triggered.connect(lambda: window._set_favorite_single(rel_path, False))
        else:
            act_fav = menu.addAction("🌟 " + _("Add to Favorites"))
            act_fav.triggered.connect(lambda: window._set_favorite_single(rel_path, True))

    # 3. Visibility
    if not is_trash_view:
        is_hidden = (config.get('is_visible', 1) == 0)
        if is_hidden:
            act_vis = menu.addAction(_("👁 Show Category/Package"))
            act_vis.triggered.connect(lambda: window._update_folder_visibility(rel_path, False))
        else:
            act_vis = menu.addAction(_("👻 Hide Category/Package"))
            act_vis.triggered.connect(lambda: window._update_folder_visibility(rel_path, True))

    menu.addSeparator()
    
    # 3. Properties & Explorer
    act_props_view = menu.addAction(_("📋 View Properties"))
    act_props_view.triggered.connect(lambda: window._show_property_view_for_card(full_src))

    act_props = menu.addAction(_("📝 Edit Properties"))
    act_props.triggered.connect(window._batch_edit_properties_selected)
    
    act_files = menu.addAction(_("🛠 Manage Files (Exclude/Move)..."))
    act_files.triggered.connect(lambda: window._open_file_management(rel_path))
    
    menu.addSeparator()
    
    act_explore = menu.addAction(_("📁 Open in Explorer"))
    act_explore.triggered.connect(lambda: window._open_path_in_explorer(full_src))

    menu.addSeparator()
    
    # 4. Trash / Restore
    if rel_path:
        if not is_trash_view:
            act_trash = menu.addAction(_("🗑 Move Category/Package to Trash"))
            act_trash.triggered.connect(lambda: window._on_package_move_to_trash(full_src))
            
    return menu

