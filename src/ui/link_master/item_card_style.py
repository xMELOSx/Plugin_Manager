def get_card_colors(link_status, is_misplaced, is_partial, has_logical_conflict, 
                    has_conflict_children, is_library_alt_version, is_registered,
                    is_package, is_selected, is_focused, has_name_conflict=False, 
                    has_target_conflict=False, has_linked_children=False, has_unlinked_children=False, has_partial_children=False,
                    category_deploy_status=None):
    """Calculate status and background colors for ItemCard."""
    status_color = "#444"
    bg_color = "#333"
    
    # Priority 1: Conflicts (Red border)
    # Only physical link conflict, target conflict, or logical conflict trigger red
    # NOTE: has_name_conflict REMOVED - it was unwanted functionality
    if link_status == 'conflict' or \
         has_logical_conflict or \
         has_target_conflict or \
         (not is_package and has_conflict_children):  # Categories with conflict children
        status_color = COLOR_RED
        bg_color = "#3d2a2a"
    # Priority 2: Library Alt Version
    elif is_library_alt_version:
        status_color = COLOR_LIB_ALT
        bg_color = "#2d3d2a"
    # Priority 3: Misplaced
    elif is_misplaced:
        status_color = COLOR_PINK
        bg_color = "#3d2a35"
    # Priority 4: Partial Link
    elif is_partial and (link_status == 'linked' or link_status == 'partial'):
        status_color = COLOR_YELLOW
        bg_color = "#3d3d2a"
    # Priority 5: Linked (for PACKAGES)
    elif link_status == 'linked':
        status_color = COLOR_GREEN
        bg_color = "#2a332a"
    # Priority 6: Unregistered
    elif not is_registered:
        status_color = COLOR_PURPLE
        bg_color = "#322a3d"
    # Priority 7: Category hierarchical status (ONLY for categories, not packages)
    elif not is_package:
        # Category Deploy status (deep blue)
        if category_deploy_status == 'deployed':
            status_color = COLOR_CATEGORY_DEPLOYED
            bg_color = "#1a2a3a"
        # Categories: Check children status
        elif has_partial_children:
            status_color = COLOR_YELLOW
            bg_color = "#3d3d2a"
        elif has_linked_children:
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
COLOR_RED = "#e74c3c"
COLOR_GREEN = "#27ae60"
COLOR_ORANGE = "#e67e22"
COLOR_YELLOW = "#f1c40f"
COLOR_PINK = "#ff69b4"
COLOR_PURPLE = "#9b59b6"
COLOR_LIB_ALT = "#9acd32"
COLOR_HIDDEN = "#888"
COLOR_NORMAL_TEXT = "#ddd"
COLOR_CATEGORY_DEPLOYED = "#1e5a8f"  # Deep blue for category deploy
COLOR_SELECTION_BG = "#2a3b4d"
COLOR_FOCUSED_BG = "#34495e"
COLOR_FOCUSED_BORDER = "#5DADE2"
COLOR_SELECTED_BORDER = "#3498DB"
COLOR_HOVER_BORDER = "#666666"
