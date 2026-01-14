def get_card_colors(link_status, is_misplaced, is_partial, has_logical_conflict, 
                    has_conflict_children, is_library_alt_version, is_registered,
                    is_package, is_selected, is_focused, has_name_conflict=False, 
                    has_target_conflict=False, has_linked_children=False, has_unlinked_children=False, 
                    has_partial_children=False, category_deploy_status=None, context=None,
                    is_intentional=False, has_intentional_children=False):
    """Calculate status and background colors for ItemCard based on Priority.
    
    Priority Order (User Requested):
    1. RED (Conflict)
    2. YELLOW (Accidental Partial / File Loss)
    3. ORANGE (Intentional Partial / Custom Rules)
    4. GREEN (Linked)
    5. BLUE (Category Deployed via Folder mode)
    6. Others (Misplaced, Lib Alt, Unregistered)
    """
    status_color = "#444"
    bg_color = "#333"
    
    # Priority 1: Conflicts (Red)
    if link_status == 'conflict' or \
         has_logical_conflict or \
         has_target_conflict or \
         (not is_package and has_conflict_children):
        status_color = COLOR_RED
        bg_color = "#3d2a2a"

    # Priority 2: Accidental Partial / File Loss (Yellow)
    # Triggered if status is 'partial' OR if it's 'linked' but NOT 'is_intentional' (though that shouldn't happen)
    elif (link_status == 'partial' and not is_intentional) or \
         (not is_package and has_partial_children):
        status_color = COLOR_YELLOW
        bg_color = "#3d3d2a"

    # Priority 3: Intentional Partial / Custom Rules (Orange)
    elif (is_intentional and (link_status == 'linked' or link_status == 'partial')) or \
         (not is_package and has_intentional_children):
        status_color = COLOR_ORANGE
        bg_color = "#3d322a"

    # Priority 4: Misplaced (Pink)
    elif is_misplaced:
        status_color = COLOR_PINK
        bg_color = "#3d2a35"

    # Priority 5: Library Alt Version (Lime)
    elif is_library_alt_version:
        status_color = COLOR_LIB_ALT
        bg_color = "#2d3d2a"

    # Priority 6: Category Deploy Status (Blue)
    elif not is_package and category_deploy_status == 'deployed' and context != 'contents':
        status_color = COLOR_CATEGORY_DEPLOYED
        bg_color = "#1a2a3d"

    # Priority 7: Linked (Green)
    elif link_status == 'linked':
        status_color = COLOR_GREEN
        bg_color = "#2a332a"
        
    # Priority 8: Unregistered (Purple)
    elif not is_registered and SHOW_UNREGISTERED_BORDER:
        status_color = COLOR_PURPLE
        bg_color = "#322a3d"

    # Category Priority Fallback for Linked Children
    elif not is_package and has_linked_children:
        status_color = COLOR_GREEN
        bg_color = "#2a332a"
    
    return status_color, bg_color

def get_card_stylesheet(status_color, bg_color, radius="8px"):
    """Generate the QSS for ItemCard."""
    return f"""
        ItemCard {{
            background-color: {bg_color};
            border: 2px solid {status_color};
            border-radius: {radius};
        }}
        ItemCard:hover {{
            background-color: #3d4a59;
        }}
        QPushButton {{
            border: none;
            border-radius: 12px;
            color: white;
        }}
        QLabel {{
            background: transparent;
        }}
    """

# Color Constants
SHOW_UNREGISTERED_BORDER = False  # Phase 42: Toggleable from debug window
COLOR_RED = "#e74c3c"
COLOR_GREEN = "#27ae60"
COLOR_ORANGE = "#e67e22"
COLOR_YELLOW = "#f1c40f"
COLOR_PINK = "#ff69b4"
COLOR_PURPLE = "#9b59b6"
COLOR_LIB_ALT = "#9acd32"
COLOR_HIDDEN = "#888"
COLOR_NORMAL_TEXT = "#ddd"
COLOR_SELECTION_BG = "#2a3b4d"
COLOR_FOCUSED_BG = "#34495e"
COLOR_FOCUSED_BORDER = "#5DADE2"
COLOR_SELECTED_BORDER = "#3498DB"
COLOR_HOVER_BORDER = "#666666"
COLOR_CATEGORY_DEPLOYED = "#2980b9"  # Deep blue for deployed categories

# Note: Phase 5 Common Dialog Style was moved to src.ui.styles.apply_common_dialog_style
