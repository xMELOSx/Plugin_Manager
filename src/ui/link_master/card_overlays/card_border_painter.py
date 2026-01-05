from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush


class CardBorderPainter:
    """Utility class for drawing card borders (selection, hover, status)."""
    
    # Color constants
    COLOR_RED = "#e74c3c"
    COLOR_GREEN = "#27ae60"
    COLOR_YELLOW = "#f1c40f"
    COLOR_PINK = "#ff69b4"
    COLOR_PURPLE = "#9b59b6"
    COLOR_LIB_ALT = "#9acd32"
    COLOR_DEFAULT = "#444"
    
    @staticmethod
    def draw_status_border(painter: QPainter, rect: QRectF, status_color: str, 
                           bg_color: str, radius: int = 8, border_width: int = 2):
        """Draw outer status border with background fill."""
        rect = QRectF(rect) # Ensure float precision
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background
        painter.setBrush(QBrush(QColor(bg_color)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, radius, radius)
        
        # Draw border
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(status_color), border_width))
        inner_rect = rect.adjusted(border_width/2, border_width/2, -border_width/2, -border_width/2)
        painter.drawRoundedRect(inner_rect, radius - border_width/2, radius - border_width/2)
    
    @staticmethod
    def draw_selection_border(painter: QPainter, rect: QRectF, is_selected: bool, 
                               is_focused: bool, is_hovered: bool, display_mode: str = 'standard'):
        """Draw inner selection/hover border.
        
        Args:
            painter: Active QPainter instance
            rect: Card rectangle
            is_selected: Card is currently selected
            is_focused: Card has focus (keyboard navigation)
            is_hovered: Mouse is hovering over card
            display_mode: 'standard', 'mini_image', or 'text_list'
        """
        if not is_selected and not is_hovered:
            return
            
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        pen_width = 2 if is_selected else 1
        inner_offset = 4
        
        if is_selected:
            color = "#5DADE2" if is_focused else "#3498DB"
            pen = QPen(QColor(color), pen_width, Qt.PenStyle.SolidLine)
        elif is_hovered:
            pen = QPen(QColor("#666666"), pen_width, Qt.PenStyle.SolidLine)
        else:
            return
            
        painter.setPen(pen)
        
        base_radius = 4 if display_mode == 'mini_image' else 8
        inner_radius = max(0, base_radius - inner_offset)
        inner_rect = QRectF(rect).adjusted(inner_offset, inner_offset, -inner_offset, -inner_offset)
        
        painter.drawRoundedRect(inner_rect, inner_radius, inner_radius)
        
        # Focus indicator (dotted line)
        if is_focused:
            painter.setPen(QPen(QColor("#AED6F1"), 1, Qt.PenStyle.DotLine))
            inner_rect_2 = inner_rect.adjusted(1, 1, -1, -1)
            painter.drawRoundedRect(inner_rect_2, max(0, inner_radius-1), max(0, inner_radius-1))
    
    @staticmethod
    def draw_debug_hitbox(painter: QPainter, rect: QRectF):
        """Draw debug hitbox rectangle (red outline)."""
        painter.setPen(QPen(QColor(255, 0, 0, 150), 2))
        painter.drawRect(rect.adjusted(0, 0, -1, -1))
