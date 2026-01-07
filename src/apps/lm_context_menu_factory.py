""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を介すること。
"""

import os
from PyQt6.QtWidgets import QMenu
from src.core.lang_manager import _

def create_item_context_menu(window, rel_path):
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
            
            # Reconstruct Target Path based on Rule
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

            status_res = window.deployer.get_link_status(target_link, expected_source=full_src, expected_transfer_mode=tm)
            status = status_res.get('status', 'none')

            # Phase: Detect if this is a Category (has subfolders with packages)
            is_category = False
            child_count = 0
            try:
                for item in os.listdir(full_src):
                    if os.path.isdir(os.path.join(full_src, item)) and not item.startswith('.') and item not in ('_Trash', 'Trash'):
                        child_count += 1
                        if child_count > 0:
                            is_category = True
                            break
            except:
                pass
            
            # Phase 28: Check Tag Conflict
            tag_conflict = window._check_tag_conflict(rel_path, config, app_data)
            
            if is_category:
                # Category-specific menu
                category_status = config.get('category_deploy_status')
                if category_status == 'deployed':
                    act_unlink_cat = menu.addAction(_("🔗 Unlink Category (Unlink All)"))
                    act_unlink_cat.triggered.connect(lambda: window._handle_unlink_category(rel_path))
                else:
                    act_dep_cat = menu.addAction(_("📦 Deploy Category (All Packages)"))
                    act_dep_cat.triggered.connect(lambda: window._handle_deploy_category(rel_path))
            elif status == 'linked':

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

