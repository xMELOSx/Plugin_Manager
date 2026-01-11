    
    window.pkg_title_lbl = QLabel(_("<b>Packages</b>"), pkg_group, styleSheet="color: #fff;")
    pkg_header.addWidget(window.pkg_title_lbl)
    
    window.total_link_count_label = QLabel(_("Total Links: 0"), pkg_group, styleSheet="color: #3498db; font-weight: bold;")
    pkg_header.addWidget(window.total_link_count_label)
    
    pkg_header.addWidget(QLabel("|", pkg_group, styleSheet="color: #555;"))
    
    window.pkg_link_count_label = QLabel("", pkg_group, styleSheet="color: #27ae60; font-weight: bold;")
    pkg_header.addWidget(window.pkg_link_count_label)
    
    window.pkg_result_label = QLabel("", pkg_group, styleSheet="color: #fff;")
    pkg_header.addWidget(window.pkg_result_label)
    
    pkg_header.addStretch()
    
    pkg_header.addWidget(QLabel("|", pkg_group, styleSheet="color: #555;"))
    
    window.btn_pkg_text = TitleBarButton("T", pkg_group, is_toggle=True)
    window.btn_pkg_text.setObjectName("pkg_mode_text_btn")
    window.btn_pkg_text.setFixedSize(36, 26)
    window.btn_pkg_text.clicked.connect(lambda: window._toggle_pkg_display_mode("text_list"))
    pkg_header.addWidget(window.btn_pkg_text)
    
    window.btn_pkg_image = TitleBarButton("🖼", pkg_group, is_toggle=True)
    window.btn_pkg_image.setObjectName("pkg_mode_image_btn")
    window.btn_pkg_image.setFixedSize(36, 26)
    window.btn_pkg_image.clicked.connect(lambda: window._toggle_pkg_display_mode("mini_image"))
    pkg_header.addWidget(window.btn_pkg_image)
    
    window.btn_pkg_image_text = TitleBarButton("🖼T", pkg_group, is_toggle=True)
    window.btn_pkg_image_text.setObjectName("pkg_mode_combined_btn")
    window.btn_pkg_image_text.setFixedSize(44, 26)
    window.btn_pkg_image_text.clicked.connect(lambda: window._toggle_pkg_display_mode("image_text"))
    pkg_header.addWidget(window.btn_pkg_image_text)
    
    pkg_header.addWidget(QLabel("|", pkg_group, styleSheet="color: #555;"))
    
    window.btn_pkg_quick_manage = ActionButton("⚡", pkg_group, is_toggle=False, trigger_on_release=True)
    window.btn_pkg_quick_manage.setObjectName("pkg_quick_manage_btn")
    window.btn_pkg_quick_manage.setFixedSize(28, 26)
    window.btn_pkg_quick_manage.setToolTip(_("Quick View Manager for Packages"))
    window.btn_pkg_quick_manage.released.connect(lambda: window._open_quick_view_cached(scope="package"))
    pkg_header.addWidget(window.btn_pkg_quick_manage)
