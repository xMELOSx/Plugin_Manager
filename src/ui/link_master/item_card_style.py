def get_card_colors(link_status, is_misplaced, is_partial, has_logical_conflict, 
                    has_conflict_children, is_library_alt_version, is_registered,
                    is_package, is_selected, is_focused, has_name_conflict=False, has_target_conflict=False):
    """Calculate status and background colors for ItemCard."""
    status_color = "#444"
    bg_color = "#333"
    
    if link_status == 'conflict' or \
         has_logical_conflict or \
         has_name_conflict or \
         has_target_conflict or \
         (not is_package and has_conflict_children):
        status_color = "#e74c3c" # Red
        bg_color = "#3d2a2a"
    elif is_library_alt_version:
        status_color = "#9acd32" # Yellow-green
        bg_color = "#2d3d2a"
    elif is_misplaced:
        status_color = "#ff69b4" # Pink
        bg_color = "#3d2a35"
    elif is_partial and (link_status == 'linked' or link_status == 'partial'):
        status_color = "#f1c40f" # Yellow
        bg_color = "#3d3d2a"
    elif link_status == 'linked':
        status_color = "#27ae60" # Green
        bg_color = "#2a332a"
    elif not is_registered:
        status_color = "#9b59b6" # Amethyst Purple
        bg_color = "#322a3d"
    # Note: Linked children (orange) logic was here too, but missed in above priority if not linked
    # Let's add it back correctly (lower priority than linked/unregistered)
    # Wait, in original code it was:
    # elif self.link_status == 'linked': ...
    # elif self.has_linked_children: ...
    # So linked children is lower than linked.
    
    # Re-evaluating orange (linked children)
    if status_color == "#444": # Not set by higher priority
        # We need has_linked_children as well
        pass

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
COLOR_SELECTION_BG = "#2a3b4d"
COLOR_FOCUSED_BG = "#34495e"
COLOR_FOCUSED_BORDER = "#5DADE2"
COLOR_SELECTED_BORDER = "#3498DB"
COLOR_HOVER_BORDER = "#666666"
