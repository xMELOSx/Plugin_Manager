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
    is_trash_view = "_Trash" in rel_path.replace('\\\\', '/')
    
    menu = QMenu(window)
    menu.setStyleSheet(window._menu_style())
    
    folder_name = os.path.basename(rel_path) if rel_path else _("Root")
    menu.addAction(_("Folder: {name}").format(name=folder_name)).setEnabled(False)
    menu.addSeparator()

    # 1. Deployment Actions (or Restore if in Trash)
    if is_trash_view:
        act_restore = menu.addAction(_("📦 Restore to Original"))
        act_restore.triggered.connect(lambda: window._on_package_restore(full_src))
    else:
        app_data = window.app_combo.currentData()
        target_dir = app_data.get(window.current_target_key) if app_data else None
        
        if window.deployer and target_dir:
            target_link = config.get('target_override') or os.path.join(target_dir, folder_name)
            status_res = window.deployer.get_link_status(target_link, expected_source=full_src)
            status = status_res.get('status', 'none')
            
            # Phase 28: Check Tag Conflict
            tag_conflict = window._check_tag_conflict(rel_path, config, app_data)
            
            if status == 'linked':
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
            act_vis = menu.addAction(_("👁 Show Item"))
            act_vis.triggered.connect(lambda: window._update_folder_visibility(rel_path, False))
        else:
            act_vis = menu.addAction(_("👻 Hide Item"))
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
            act_trash = menu.addAction(_("🗑 Move to Trash"))
            act_trash.triggered.connect(lambda: window._on_package_move_to_trash(full_src))
            
    return menu

