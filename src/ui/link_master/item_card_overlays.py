from PyQt6.QtCore import Qt

def update_overlays_geometry(card_w, card_h, display_mode, is_favorite, has_urls, 
                           show_link, show_deploy, link_status, star_label, url_label, 
                           deploy_btn, opacity=0.8):
    """Calculate and apply geometries for card overlays."""
    is_text_mode = display_mode == 'text_list'
    use_overlays = not is_text_mode
    
    # 1. Star Overlay (QLabel for favorites)
    if star_label:
        if is_favorite and use_overlays:
            star_label.setGeometry(6, 6, 28, 28)
            star_label.show()
            star_label.raise_()
        else:
            star_label.hide()
            
    # 2. URL Overlay
    if url_label:
        if has_urls and show_link:
            url_label.setGeometry(card_w - 30, 8, 24, 24)
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
            
            # Update appearance depends on status
            _apply_deploy_btn_style(deploy_btn, link_status, opacity)
            deploy_btn.show()
            deploy_btn.raise_()
        else:
            deploy_btn.hide()

def _apply_deploy_btn_style(btn, link_status, opacity):
    if link_status == 'linked':
        icon_char = "🔗"
        base_color = f"rgba(39, 174, 96, {opacity})"
        hover_color = "rgba(46, 204, 113, 0.95)"
        border_color = "#1e8449"
    elif link_status == 'conflict':
        icon_char = "⚠"
        base_color = f"rgba(231, 76, 60, {opacity})"
        hover_color = "rgba(241, 100, 85, 0.95)"
        border_color = "#943126"
    else:
        icon_char = "🚀"
        base_color = f"rgba(52, 152, 219, {opacity})"
        hover_color = "rgba(93, 173, 226, 0.95)"
        border_color = "#2471a3"

    style = f"""
        QPushButton {{ 
            background-color: {base_color}; 
            color: white; 
            border-radius: 12px; 
            font-size: 11px; 
            border: 1px solid {border_color}; 
        }}
        QPushButton:hover {{ 
            background-color: {hover_color}; 
        }}
    """
    btn.setText(icon_char)
    btn.setStyleSheet(style)
