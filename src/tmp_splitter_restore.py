    
    saved_cat_height = window.registry.get_global("category_view_height", 200)
    window._category_fixed_height = saved_cat_height
    window.v_splitter.setSizes([saved_cat_height, 400])
    window.v_splitter.setStretchFactor(0, 0)
    window.v_splitter.setStretchFactor(1, 1)
    window.v_splitter.splitterMoved.connect(window._on_splitter_moved)
    
    # Ensure splitter is in layout (Add as fail-safe if not added earlier)
    # right_layout.addWidget(window.v_splitter, 1) # Added at top, but ensure stretch here if needed? 
    # The top addWidget didn't have stretch factor 1. Let's update it or rely on splitter behavior.
    # Standard practice: set stretch on layout add.
    
    # We added right_layout.addWidget(window.v_splitter) at the top. 
    # Let's verify if we need to set stretch on the item in layout.
    # But more importantly, the deleted block contained: 
    # right_layout.addWidget(window.v_splitter, 1)
    # So we should probably re-add it here with stretch 1, or update the top one.
    # To avoid double add, let's assume the top one is fine, BUT we need the splitter configuration.
    
    # Also, we explicitly added groups to splitter earlier (4300, 4301). 
    # Windows.v_splitter.addWidget(cat_group) 
    # Windows.v_splitter.addWidget(pkg_group)
    # These are already in the code.
