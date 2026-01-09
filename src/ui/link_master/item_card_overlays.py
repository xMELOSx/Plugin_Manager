from PyQt6.QtCore import Qt


def update_overlays_geometry(card_w, card_h, display_mode, is_favorite, has_urls, 
                           show_link, show_deploy, link_status, star_label, url_label, 
                           deploy_btn, lib_btn=None, is_library=False, opacity=0.8, is_package=True,
                           has_category_conflict=False):
    """Calculate and apply geometries for card overlays.
    
    Note: Styling is now handled by the overlay components themselves.
    This function only manages position and visibility.
    """
    is_text_mode = display_mode == 'text_list'
    use_overlays = not is_text_mode
    
    # 1. Star Overlay
    if star_label:
        if is_favorite and use_overlays:
            star_label.setGeometry(6, 6, 28, 28)
            star_label.show()
            star_label.raise_()
        else:
            star_label.hide()
            
    # 2. URL Overlay
    if url_label:
        if has_urls and show_link and use_overlays:
            url_label.setGeometry(card_w - 30, 6, 24, 24)
            url_label.show()
            url_label.raise_()
        else:
            url_label.hide()

    # 3. Deploy Btn
    if deploy_btn:
        if show_deploy:
            if is_text_mode:
                deploy_btn.setGeometry(card_w - 30, (card_h - 24) // 2, 24, 24)
            else:
                deploy_btn.setGeometry(card_w - 30, card_h - 30, 24, 24)
            
            # Use component method if available
            if hasattr(deploy_btn, 'setStatus'):
                deploy_btn.setStatus(link_status, opacity, is_category=not is_package, has_conflict=has_category_conflict)
            deploy_btn.show()
            deploy_btn.raise_()
        else:
            deploy_btn.hide()

    # 4. Library Overlay
    if lib_btn:
        if is_library and use_overlays:
            lib_btn.setGeometry(6, card_h - 30, 24, 24)
            lib_btn.show()
            lib_btn.raise_()
        else:
            lib_btn.hide()
