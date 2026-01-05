from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
                             QScrollArea, QWidget, QMessageBox, QMenu, QSpinBox, QApplication,
                             QAbstractItemView, QFrame, QGraphicsOpacityEffect)
from PyQt6.QtCore import Qt, QSize, QTimer, QPoint, QRect, QRectF, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QIcon, QPixmap, QDesktopServices, QPainter, QColor, QPen, QBrush, QAction, QPainterPath, QPolygonF, QPalette
import os
import time
import logging
import ctypes
import copy
from src.core.lang_manager import _
from src.ui.link_master.tag_bar import TagWidget
from src.ui.window_mixins import OptionsMixin
from src.ui.frameless_window import FramelessDialog
from src.ui.toast import Toast

def _normalize_tags(tags_str, lowercase=True):
    """Normalize tag string: sorted, space-trimmed, optionally lowercased."""
    if not tags_str: return ""
    if lowercase:
        tags = {t.strip().lower() for t in tags_str.split(",") if t.strip()}
    else:
        tags = {t.strip() for t in tags_str.split(",") if t.strip()}
    return ",".join(sorted(list(tags)))

class QuickEdit(QLineEdit):
    """Custom QLineEdit that handles Enter to move to next row."""
    def keyPressEvent(self, event):
        if event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter]:
            if event.modifiers() & Qt.KeyboardModifier.AltModifier:
                # Propagate Alt+Enter to dialog for saving
                p = self.parent()
                while p and not isinstance(p, QDialog):
                    p = p.parent()
                if p:
                    # Let the dialog handle its own keyPressEvent for Alt+Enter
                    # or just call the save method directly if available.
                    if hasattr(p, "_on_save_clicked"):
                        p._on_save_clicked()
                        return

            # Normal Enter: Find the parent dialog to trigger next row focus
            p = self.parent()
            while p and not hasattr(p, "focus_next_row_from"):
                p = p.parent()
            if p:
                p.focus_next_row_from(self)
                return
        super().keyPressEvent(event)

class TagFlowPreview(QWidget):
    """
    Extremely lightweight tag container using QPainter for performance.
    Handles rendering and hit-testing for thousands of tags without widget overhead.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(34)
        self.setMouseTracking(True)
        
        # Data
        self._tag_cache = None
        self._icon_cache = None
        self._current_tags = set()
        self._click_handler = None
        self._on_render_done = None
        self._hover_tag = None # Track mouse hover
        
        # Layout metrics (calculated during paint)
        self._tag_rects = [] # List of (rect, tag_name, is_sep)
        
    def set_tags(self, tag_cache, current_tags, click_handler, on_render_done=None, icon_cache=None):
        """Update tag data and trigger repaint."""
        self._tag_cache = tag_cache
        self._icon_cache = icon_cache
        self._current_tags = current_tags
        self._click_handler = click_handler
        self._on_render_done = on_render_done
        self.update()

    def paintEvent(self, event):
        if not self._tag_cache:
            return
            
        t_start = time.perf_counter()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Layout constants
        margin_x = 5
        margin_y = 4
        spacing = 4
        cur_x = margin_x
        
        self._tag_rects = []
        
        # Fetch all tags from cache (they are already ordered if we prepare correctly)
        for tag_name, cache in self._tag_cache.items():
            info = cache['info']
            is_sep = info.get('is_sep', False)
            
            if is_sep:
                # Render separator (vertical line or dots)
                sep_w = 8
                sep_rect = QRect(cur_x, margin_y, sep_w, self.height() - margin_y*2)
                
                painter.setPen(QPen(QColor(100, 100, 100, 100), 1))
                painter.drawLine(cur_x + 4, margin_y + 4, cur_x + 4, self.height() - margin_y - 4)
                
                self._tag_rects.append((sep_rect, tag_name, True))
                cur_x += sep_w + spacing
                continue

            # Render Tag Pill
            is_selected = cache['lower_name'] in self._current_tags
            
            # Phase 1.1.12: Respect display_mode
            display_mode = info.get('display_mode', 'text')
            # Backward compatibility (same as TagWidget)
            if 'display_mode' not in info and not info.get('prefer_emoji', True) and info.get('icon'):
                display_mode = 'image'
            
            name = info.get('display', tag_name)
            emoji = info.get('emoji', '')
            icon_path = info.get('icon', '')
            
            # Calculate content and width
            content_text = ""
            icon_pixmap = None
            
            if display_mode == 'image' and icon_path and os.path.exists(icon_path):
                # Use shared icon cache if provided
                if self._icon_cache and icon_path in self._icon_cache:
                    # _icon_cache stores QIcon, we need QPixmap
                    icon_pixmap = self._icon_cache[icon_path].pixmap(22, 22)
                else:
                    icon_pixmap = QPixmap(icon_path)
            elif display_mode == 'symbol' and emoji:
                content_text = emoji
            elif display_mode == 'text_symbol' and emoji:
                content_text = f"{emoji} {name}"
            elif display_mode == 'text' or not emoji:
                content_text = name
            else: # Fallback to name
                content_text = name

            font_metrics = painter.fontMetrics()
            if icon_pixmap and not icon_pixmap.isNull():
                pill_w = 28 # Fixed square-ish for image only
                # Scale for display
                icon_pixmap = icon_pixmap.scaled(22, 22, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            else:
                text_w = font_metrics.horizontalAdvance(content_text)
                pill_w = text_w + 16 # Padding
            
            pill_rect = QRect(cur_x, margin_y, pill_w, self.height() - margin_y*2)
            
            # Background
            bg_color = QColor(60, 60, 60)
            if is_selected:
                bg_color = QColor(52, 152, 219) # Blue primary
            
            if self._hover_tag == tag_name:
                # Slight highlight for hover
                if is_selected:
                    bg_color = QColor(74, 174, 241) # Brighter blue
                else:
                    bg_color = QColor(80, 80, 80) # Brighter gray
            
            painter.setBrush(QBrush(bg_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(pill_rect, 4, 4)
            
            # Content
            if icon_pixmap and not icon_pixmap.isNull():
                # Draw image centered
                ix = pill_rect.center().x() - icon_pixmap.width() // 2
                iy = pill_rect.center().y() - icon_pixmap.height() // 2
                painter.drawPixmap(ix, iy, icon_pixmap)
            else:
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, content_text)
            
            self._tag_rects.append((pill_rect, tag_name, False))
            cur_x += pill_w + spacing
            
            # Stop if out of width
            if cur_x > self.width():
                break

        if self._on_render_done:
            self._on_render_done(time.perf_counter() - t_start)

    def mouseMoveEvent(self, event):
        pos = event.pos()
        old_hover = self._hover_tag
        self._hover_tag = None
        for rect, tag_name, is_sep in self._tag_rects:
            if not is_sep and rect.contains(pos):
                self._hover_tag = tag_name
                break
        
        if old_hover != self._hover_tag:
            self.update()

    def leaveEvent(self, event):
        self._hover_tag = None
        self.update()

    def mousePressEvent(self, event):
        if not self._click_handler:
            return
            
        pos = event.pos()
        for rect, tag_name, is_sep in self._tag_rects:
            if not is_sep and rect.contains(pos):
                self._click_handler(tag_name, self)
                self.update()
                break

class NaturalSortTableWidgetItem(QTableWidgetItem):
    """Custom item for natural sorting (e.g., 1, 2, 10 instead of 1, 10, 2)."""
    def __init__(self, value, display_text=None):
        super().__init__(display_text if display_text is not None else str(value))
        self._sort_value = self._get_natural_sort_key(str(value))

    def _get_natural_sort_key(self, s):
        import re
        return [int(c) if c.isdigit() else c.lower() for c in re.split('([0-9]+)', s)]

    def __lt__(self, other):
        if not isinstance(other, NaturalSortTableWidgetItem):
            return super().__lt__(other)
        return self._sort_value < other._sort_value

    def set_value(self, value, display_text=None):
        """Update both display text and internal sort key."""
        self.setText(display_text if display_text is not None else str(value))
        self._sort_value = self._get_natural_sort_key(str(value))

class SortableTableWidgetItem(QTableWidgetItem):
    """Custom item for sorting by specific data types (bool, int) instead of string."""
    def __init__(self, value, display_text=None):
        super().__init__(display_text if display_text is not None else str(value))
        self._sort_value = value

    def __lt__(self, other):
        return self._sort_value < other._sort_value

    def set_value(self, value, display_text=None):
        """Update both display text and internal sort value."""
        self.setText(display_text if display_text is not None else str(value))
        self._sort_value = value
        

class QuickViewManagerDialog(FramelessDialog, OptionsMixin):
    """
    Bulk edit dialog for currently visible items in the category/package area.
    Supports editing: Icon (Emoji/Image), Display Name, and Tags (via Toggles).
    """
    def __init__(self, parent=None, items_data: list = None, frequent_tags=None, db=None, storage_root=None, thumbnail_loader=None, show_hidden=True):
        # Pass None as parent to prevent composition artifacts (darkening of main window)
        super().__init__(None)
        self.setObjectName("QuickViewManagerDialog")
        self._base_title = _("Quick View Manager (Mode 1: Cached)")
        self.setWindowTitle(self._base_title)
        
        # 1. State Initialization
        # Phase 1.1.25: Use deepcopy to prevent in-place modification of parent data on Cancel
        self._raw_items_data = copy.deepcopy(items_data or []) 
        self.items_data = copy.deepcopy(self._raw_items_data)
        self.frequent_tags = frequent_tags or []
        self._last_items_data = self.items_data # For caching comparison
        self._last_frequent_tags = self.frequent_tags
        
        self.db = db
        self.storage_root = storage_root
        self.thumbnail_loader = thumbnail_loader
        self.show_hidden_items = show_hidden
        self.active_tags = self.frequent_tags # Phase 1.1.11: include separators in active_tags
        
        self._tag_cache = {} 
        self._icon_cache = {}
        self._prepare_tag_cache()
        
        self.current_load_row = 0
        self.load_batch_size = 100 
        
        # Track pending tag changes in memory {row: {tag_name: bool}}
        self._pending_tag_changes = {}
        self._widget_map = {} # Phase 1.1.45: Direct pointers {rel_path: {'fav': btn, 'score': spin, 'name': edit, 'tags': {name: btn}}}
        self.results = [] # To be populated on accept (rel_path: {key: val})

        # Profiling stats
        self._profile_start_time = 0.0
        self._last_chunk_end_time = 0.0
        self._total_gap_time = 0.0
        self._total_render_time = 0.0
        self._total_tag_creation_time = 0.0

        # 2. Window Setup
        # Sync opacity from parent if available
        if parent and hasattr(parent, '_bg_opacity'):
            self.set_background_opacity(parent._bg_opacity)
        
        # Disable auto-show to prevent "Flash" of empty table
        # We will show it manually after first chunk of data is loaded
        self._auto_fade_in = False 
        
        # Ensure global window opacity is 1.0 (Opaque) to rely solely on paintEvent for transparency
        self.setWindowOpacity(0.0) # Start hidden (0.0) unlike default
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) 
        # FramelessDialog handles opacity and styling (default 0.95 opacity, matching main window style)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Tool)
        
        self.resize(1000, 700) # Initial size
        self.center_on_screen()

        # 3. UI Setup
        self._init_ui()
        # Phase 1.1.60: Initialize original state markers for change detection
        for item in self.items_data:
            item['_orig_fav'] = item.get('is_favorite', False)
            item['_orig_score'] = int(item.get('score', 0))
            item['_orig_name'] = item.get('display_name') or ""
            # CRITICAL: Always use the SAME normalization for original markers
            item['_orig_tags'] = _normalize_tags(item.get('tags', ''), lowercase=True)

        self._load_table_data()

    def reload_data(self, items_data, frequent_tags, context_id=None):
        """Reload data for Cached Mode."""
        items_data_copy = copy.deepcopy(items_data or [])
        
        for item in items_data_copy:
            # Phase 1.1.120: FORCE overwrite original state markers on fresh data
            # This ensures that even if card data has persistent 'wrong' markers,
            # we align them to the actual current values on every fresh load.
            item['_orig_fav'] = item.get('is_favorite', False)
            item['_orig_score'] = int(item.get('score', 0))
            item['_orig_name'] = item.get('display_name') or ""
            # Marker comparison base is ALWAYS lowercase for reliable change detection
            item['_orig_tags'] = _normalize_tags(item.get('tags', ''), lowercase=True)

        last_items = getattr(self, '_last_items_data', None)
        last_tags = getattr(self, '_last_frequent_tags', None)
        last_context = getattr(self, '_last_context_id', None)
        
        # Cache Hit Check (Structural Equality)
        # Phase 1.1.150: Allow Tag/Value changes to stay cached.
        # We only reload if the items count or paths have changed.
        # Value updates (Fav/Score/Name/Tags) are handled by _reset_ui_to_data fast-sync.
        items_match = (last_items is not None and len(last_items) == len(items_data_copy))
        if items_match:
            for i in range(len(items_data_copy)):
                if items_data_copy[i]['rel_path'] != last_items[i]['rel_path']:
                    items_match = False
                    break
                    
        tags_match = False
        if last_tags == frequent_tags:
            tags_match = True
            if last_tags and frequent_tags:
                for t1, t2 in zip(last_tags, frequent_tags):
                    if t1.get('display_mode') != t2.get('display_mode'):
                        logging.info(f"[QuickViewAudit] Miss! Display settings changed for tag '{t1.get('name')}'")
                        tags_match = False
                        break

        context_match = (last_context == context_id)
        if not items_match: logging.debug("[QuickViewAudit] Items mismatch.")
        if not tags_match: logging.debug("[QuickViewAudit] Tags/Settings mismatch.")
        if not context_match: logging.debug("[QuickViewAudit] Context mismatch.")
        
        is_cache_hit = items_match and tags_match and context_match
        
        # Phase 1.1.152: Always prepare tag metadata and cache BEFORE UI sync/load
        self.frequent_tags = frequent_tags or []
        self.active_tags = self.frequent_tags
        self._prepare_tag_cache()

        if is_cache_hit:
             logging.info("[QuickViewCache] Hit! Ensuring UI is exhaustively synced.")
             self.items_data = items_data_copy 
             self._pending_tag_changes.clear()
             self._reset_ui_to_data()
             self.setWindowOpacity(1.0)
             self.show()
             return
        
        logging.info(f"[QuickViewCache] Miss! Reloading items={len(items_data_copy)}, tags={len(frequent_tags)}")
        self.items_data = items_data_copy
        self._raw_items_data = copy.deepcopy(self.items_data)
        self._last_items_data = self.items_data
        self._last_frequent_tags = frequent_tags
        self._last_context_id = context_id
        
        self.frequent_tags = frequent_tags or []
        self.active_tags = self.frequent_tags
        
        self._pending_tag_changes.clear()
        
        # 1. Update Columns
        self.table.setSortingEnabled(False)
        self._widget_map.clear() # Phase 1.1.45: Clear direct pointers
        
        # Build tag columns
        self._display_tags = []
        self._all_tag_columns = []
        display_idx = 0
        for t in self.active_tags:
            is_sep = t.get('is_sep', False)
            if is_sep:
                self._all_tag_columns.append({'type': 'sep', 'tag_info': t})
            else:
                self._all_tag_columns.append({'type': 'tag', 'tag_info': t, 'display_idx': display_idx})
                self._display_tags.append(t)
                display_idx += 1
                
        # Tag Headers
        fixed_headers = [_("No."), _("Icon"), _("Fav"), _("Score"), _("Folder Name"), _("Display Name")]
        headers = fixed_headers + [col['tag_info'].get('name', '|') for col in self._all_tag_columns]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        
        # Re-apply styles/widths
        self.table.setColumnWidth(0, 40) # No.
        self.table.setColumnWidth(1, 40) # Icon
        self.table.setColumnWidth(2, 40) # Fav
        self.table.setColumnWidth(3, 60) # Score
        self.table.setColumnWidth(4, 150) # Folder
        
        for i, col_info in enumerate(self._all_tag_columns):
            col_idx = 6 + i
            if col_info['type'] == 'sep':
                self.table.setColumnWidth(col_idx, 4)
            else:
                self.table.setColumnWidth(col_idx, 32)
        
        # 2. Reset and Load
        self.table.clearContents()
        self.table.setRowCount(0)
        
        self._tag_cache = {} 
        self._icon_cache = {}
        self._prepare_tag_cache()
        
        self.current_load_row = 0
        self._pending_tag_changes = {}
        self.results = []
        
        # Profiling stats reset
        self._profile_start_time = time.perf_counter()
        self._last_chunk_end_time = 0.0
        self._total_gap_time = 0.0
        
        # Trigger load
        self.table.setRowCount(len(self.items_data))
        self._load_next_chunk()


    def _update_tag_btn_style(self, btn, is_active):
        if is_active:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3498db; 
                    border: none; 
                    border-radius: 10px;
                    padding: 0px;
                }
                QPushButton:hover {
                    background-color: #5dade2;
                }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #555; 
                    border: none; 
                    border-radius: 10px;
                    padding: 0px;
                }
                QPushButton:hover {
                    background-color: #777;
                }
            """)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        # Phase 1.1.14: Set app icon for title bar (same as main window)
        icon_path = os.path.abspath(os.path.join("src", "resource", "icon", "icon.jpg"))
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path).scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            # Create rounded mask for transparency
            from PyQt6.QtGui import QPainter, QPainterPath
            rounded = QPixmap(pixmap.size())
            rounded.fill(Qt.GlobalColor.transparent)
            painter = QPainter(rounded)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            path = QPainterPath()
            path.addRoundedRect(0, 0, 24, 24, 4, 4)
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, pixmap)
            painter.end()
            self.icon_label.setPixmap(rounded)
            self.icon_label.setVisible(True)
            self.setWindowIcon(QIcon(rounded))
        else:
            self.set_default_icon()
            
        # Sync background opacity with main window
        if self.parent() and hasattr(self.parent(), '_bg_opacity'):
            self._bg_opacity = self.parent()._bg_opacity
            self._update_stylesheet()
            
        # Fix click-through: Reset global window opacity to 1.0
        self.setWindowOpacity(1.0)
            
        QTimer.singleShot(0, self._load_table_data)
    
    def _update_tag_btn_style(self, btn, is_active):
        if is_active:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3498db; 
                    border: none; 
                    border-radius: 10px;
                    padding: 0px;
                }
                QPushButton:hover {
                    background-color: #5dade2;
                }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #555; 
                    border: none; 
                    border-radius: 10px;
                    padding: 0px;
                }
                QPushButton:hover {
                    background-color: #777;
                }
            """)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

    def _on_tag_toggled(self, row, tag_name, checked, btn):
        # Deprecated
        pass

    def _on_header_clicked(self, col):
        """Handle header click to implement descending-first sort."""
        hh = self.table.horizontalHeader()
        
        # Skip separator and spacer columns - reset indicator
        is_separator = False
        if col >= 6:
            col_offset = col - 6
            if col_offset < len(self._all_tag_columns):
                if self._all_tag_columns[col_offset]['type'] == 'sep':
                    is_separator = True
            elif col_offset >= len(self._all_tag_columns):
                # Spacer column
                is_separator = True
        
        if is_separator:
            # Restore previous sort indicator
            if self._last_sort_col >= 0:
                hh.setSortIndicator(self._last_sort_col, hh.sortIndicatorOrder())
            else:
                hh.setSortIndicator(-1, Qt.SortOrder.DescendingOrder)
            return
        
        current_order = hh.sortIndicatorOrder()
        
        if col != self._last_sort_col:
            # Special case for "interesting" columns: Descending first
            if col in [2, 3] or col >= 6: # Fav, Score, Tags
                new_order = Qt.SortOrder.DescendingOrder
            else:
                new_order = Qt.SortOrder.AscendingOrder
        else:
            # Same column: toggle order based on tracked state
            new_order = Qt.SortOrder.AscendingOrder if self._last_sort_order == Qt.SortOrder.DescendingOrder else Qt.SortOrder.DescendingOrder
        
        # Perform manual sort
        self.table.sortItems(col, new_order)
        # Manually update the visual indicator since setSortingEnabled(False) prevents auto-updates
        hh.setSortIndicator(col, new_order)
        
        self._last_sort_col = col
        self._last_sort_order = new_order

    def _prepare_tag_cache(self):
        """Pre-calculate metadata for active tags once to avoid redundant O(N*M) lookups."""
        from collections import OrderedDict
        self._tag_cache = OrderedDict() # Maintain order for rendering
        for t in self.active_tags:
            tag_name = t.get('name', '')
            lower = tag_name.lower()
            self._tag_cache[lower] = {
                'info': t,
                'lower_name': lower
            }

    def _update_window_title(self):
        """Update window title to show unsaved status if changes exist."""
        has_changes = self._has_real_changes()
        title = self._base_title
        if has_changes:
            title += f" - {_('未保存')}"
        
        if self.windowTitle() != title:
            self.setWindowTitle(title)

    def _draw_star_icon(self, is_active: bool, size: int = 24) -> QIcon:
        """Generate a star icon programmatically to ensure visibility."""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Star Polygon
        # Simple 5-point star path
        path = QPainterPath()
        cx, cy = size / 2, size / 2
        outer_radius = size * 0.4
        inner_radius = size * 0.2
        import math
        points = []
        for i in range(10):
            angle = math.radians(i * 36 - 90) # Start at top (-90 deg)
            r = outer_radius if i % 2 == 0 else inner_radius
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        path.closeSubpath()
        
        if is_active:
            color = QColor("#f1c40f") # Yellow
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
        else:
            color = QColor("#888888") # Gray
            painter.setBrush(Qt.BrushStyle.NoBrush) # Outline only? Or Gray fill?
            # Let's do Gray Border for inactive, or Gray Fill? Use Icon style.
            # User said "Fav Icon disappeared". Old one was "☆" (Outline).
            # Let's do Gray Outline for inactive.
            pen = QPen(color)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            
        painter.drawPath(path)
        painter.end()
        return QIcon(pixmap)


    def _init_ui(self):
        # UI Setup (Apply styles before layout)
        self.setStyleSheet("""
            /* Root - transparent for frameless effect */
            QDialog { background: transparent; }
            
            /* Main Content Area - Match Main Window visual appearance */
            QWidget {
                color: #ffffff;
            }
            
            /* Table styling */
            QTableWidget { 
                background-color: transparent;
                alternate-background-color: rgba(255, 255, 255, 0.05);
                color: #ffffff; 
                gridline-color: #444; 
                border: none;
                selection-background-color: #3498db;
            }
            
            /* Horizontal Header */
            QHeaderView::section {
                background-color: #333;
                color: #ffffff;
                border: 1px solid #444;
                font-weight: bold;
                padding: 6px;
            }
            
            /* Vertical Header */
            QHeaderView::section:vertical {
                background-color: #333;
                color: #ffffff;
                border: 1px solid #444;
                padding: 4px 8px;
            }
            
            QTableCornerButton::section { background-color: #333; border: 1px solid #444; }
            
            QLineEdit { 
                background-color: #3a3a3a; 
                color: #ffffff; 
                border: 1px solid #555; 
                padding: 4px; 
                border-radius: 4px; 
            }
            QLineEdit:focus { border: 1px solid #3498db; background-color: #444; }
            
            QLabel { color: #ffffff; background: transparent; } 
            
            QPushButton {
                background-color: #3a3a3a;
                color: #ffffff;
                border: 1px solid #555;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #4a4a4a; }
            QPushButton#save_btn { background-color: #3498db; border-color: #2980b9; }
            
            QScrollBar:vertical {
                background-color: #353535;
                width: 12px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background-color: #555;
                min-height: 20px;
                border-radius: 4px;
            }
            QToolTip { background-color: #333; color: #fff; border: 1px solid #555; padding: 4px; }
        """)

        # Create a container widget for content
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(5, 0, 5, 5) # Reduced top margin
        
        # 1. Hide Vertical Header and fix scrollbar flicker
        self.table = QTableWidget()
        self.table.verticalHeader().setVisible(False)
        # Phase 1.1.15: Force scrollbar to be always visible to prevent rendering flicker
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        
        # 2. Dynamic Headers
        # Fixed: No, Icon, Fav, Score, Folder, Name
        fixed_headers = [_("No."), _("Icon"), _("Fav"), _("Score"), _("Folder Name"), _("Display Name")]
        
        # Build tag columns including separators as visual dividers
        # _display_tags = non-separator tags (for data binding)
        # _all_tag_columns = all columns including separators (for rendering)
        self._display_tags = []
        self._all_tag_columns = []  # List of {'type': 'tag'|'sep', 'tag_info': ...}
        self._tag_col_to_display_idx = {}  # Maps column index to _display_tags index
        
        display_idx = 0
        for t in self.active_tags:
            is_sep = t.get('is_sep', False)
            if is_sep:
                self._all_tag_columns.append({'type': 'sep', 'tag_info': t})
            else:
                self._all_tag_columns.append({'type': 'tag', 'tag_info': t, 'display_idx': display_idx})
                self._display_tags.append(t)
                display_idx += 1
        
        # Tag Headers
        tag_headers = []
        tag_header_icons = {}  # {col_idx: QIcon}
        separator_cols = []  # Columns that are separators
        
        for i, col_info in enumerate(self._all_tag_columns):
            col_idx = 6 + i
            
            if col_info['type'] == 'sep':
                # Separator column - thin divider
                tag_headers.append("|")
                separator_cols.append(col_idx)
            else:
                t = col_info['tag_info']
                self._tag_col_to_display_idx[col_idx] = col_info['display_idx']
                
                mode = t.get('display_mode', 'text')
                emoji = t.get('emoji', '')
                name = t.get('display', t.get('name', ''))
                icon_path = t.get('icon', '')
                
                # For image mode, try to load icon
                if mode == 'image' and icon_path and os.path.exists(icon_path):
                    if icon_path not in self._icon_cache:
                        self._icon_cache[icon_path] = QIcon(icon_path)
                    tag_header_icons[col_idx] = self._icon_cache[icon_path]
                    header_text = ""
                elif mode == 'symbol' and emoji:
                    header_text = emoji
                elif mode == 'text_symbol' and emoji:
                    header_text = emoji
                else:
                    header_text = name[:3] if len(name) > 3 else name
                
                tag_headers.append(header_text)
            
        all_headers = fixed_headers + tag_headers
        self.table.setColumnCount(len(all_headers))
        self.table.setHorizontalHeaderLabels(all_headers)
        
        # Set icons for tag columns that use image mode
        for col_idx, icon in tag_header_icons.items():
            item = self.table.horizontalHeaderItem(col_idx)
            if item:
                item.setIcon(icon)
        
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(False) # Don't stretch last tag column
        
        # Column widths
        self.table.setColumnWidth(0, 40)  # No.
        self.table.setColumnWidth(1, 40)  # Icon
        self.table.setColumnWidth(2, 40)  # Fav
        self.table.setColumnWidth(3, 60)  # Score
        self.table.setColumnWidth(4, 150) # Folder Name
        # Display Name column should stretch to fill space
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        
        # Set Tag/Separator Column widths
        for i, col_info in enumerate(self._all_tag_columns):
            col_idx = 6 + i
            if col_info['type'] == 'sep':
                self.table.setColumnWidth(col_idx, 2)  # Narrower separator (half of current 4)
                # Disable sorting for separator columns
                sep_header = self.table.horizontalHeaderItem(col_idx)
                if sep_header:
                    sep_header.setFlags(sep_header.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            else:
                self.table.setColumnWidth(col_idx, 32) # Compact tag toggles
        
        # Add spacer column at the end to prevent accidental scrolling
        spacer_col = self.table.columnCount()
        self.table.setColumnCount(spacer_col + 1)
        spacer_item = QTableWidgetItem("")
        spacer_item.setFlags(spacer_item.flags() & ~Qt.ItemFlag.ItemIsEnabled)  # Non-sortable
        self.table.setHorizontalHeaderItem(spacer_col, spacer_item)
        self.table.setColumnWidth(spacer_col, 16)  # Smaller spacer
        
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection) # Disable drag selection
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus) # Prevent focus border
        
        # Disable Qt's built-in sorting - we handle it manually in _on_header_clicked
        # This prevents separator columns from being sorted
        self.table.setSortingEnabled(False)
        
        # Default sort order: We don't force sortItems() here to respect backend loading order.
        # Just set the indicator to show metadata to user.
        self.table.horizontalHeader().setSortIndicator(4, Qt.SortOrder.AscendingOrder)
        self._last_sort_col = 4
        self._last_sort_order = Qt.SortOrder.AscendingOrder
        self.table.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        
        # Set palette for horizontal header
        hh = self.table.horizontalHeader()
        hh_palette = hh.palette()
        hh_palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
        hh_palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
        hh_palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
        hh_palette.setColor(QPalette.ColorRole.Base, QColor(51, 51, 51))
        hh_palette.setColor(QPalette.ColorRole.Button, QColor(51, 51, 51))
        hh.setPalette(hh_palette)
        
        layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 5, 20, 10) # Prevent right-edge clipping
        btn_layout.setSpacing(12)
        btn_layout.addStretch()
        
        self.cancel_btn = QPushButton(_("Cancel"))
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setMinimumWidth(100)
        self.cancel_btn.setStyleSheet("background-color: #666666; color: white; border-radius: 4px; padding: 6px;")
        
        self.save_btn = QPushButton(_("Save All (Alt + Enter)"))
        self.save_btn.clicked.connect(self._on_save_clicked)
        self.save_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; width: 220px; border-radius: 4px; padding: 6px;")
        
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)
        
        
        # Load window geometry
        self.load_options("quick_view_manager")
        
        # Set the content widget to the frameless window
        self.set_content_widget(content_widget)

    def focus_next_row_from(self, widget):
        """Focus the name editor in the next row."""
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, 5) == widget: # Name is now col 5
                next_row = row + 1
                if next_row < self.table.rowCount():
                    next_widget = self.table.cellWidget(next_row, 5)
                    if isinstance(next_widget, QLineEdit):
                        next_widget.setFocus()
                        next_widget.selectAll()
                        self.table.scrollTo(self.table.model().index(next_row, 5))
                break

    def _reset_ui_to_data(self):
        """Ultra-fast reset using _widget_map pointers (Extreme Speed < 5ms)."""
        if not self.table or not self._widget_map: return
        t_start = time.perf_counter()
        self.table.blockSignals(True)
        
        # Create a mapping for faster lookup
        item_map = {i['rel_path']: i for i in self.items_data}
        
        # Baseline identification for Sort/No logic
        rel_path_to_row = {item['rel_path']: idx for idx, item in enumerate(self.items_data)}
        
        for rel_path, widgets in self._widget_map.items():
            item = item_map.get(rel_path)
            if not item: continue
            
            # 0. No. Column Synchronization
            no_item = widgets.get('no_item')
            if no_item:
                logical_row = rel_path_to_row.get(rel_path, 0)
                no_item.set_value(logical_row + 1, str(logical_row + 1))
            
            # 1. Icon (Display settings fix)
            icon_btn = widgets.get('icon_btn')
            if icon_btn:
                icon_path = item.get('image_path')
                if icon_path:
                    if len(icon_path) <= 4:
                        icon_btn.setIcon(QIcon())
                        icon_btn.setText(icon_path)
                    else:
                        if icon_path not in self._icon_cache:
                            self._icon_cache[icon_path] = QIcon(icon_path)
                        icon_btn.setIcon(self._icon_cache[icon_path])
                        icon_btn.setText("")
                else:
                    icon_btn.setIcon(QIcon())
                    icon_btn.setText("❓")

            # 2. Favorite
            btn_fav = widgets.get('fav')
            if btn_fav:
                is_fav = item.get('is_favorite', False)
                if btn_fav.isChecked() != is_fav:
                    btn_fav.blockSignals(True)
                    btn_fav.setChecked(is_fav)
                    btn_fav.setIcon(self._draw_star_icon(is_fav))
                    btn_fav.blockSignals(False)
                
                fav_sort = widgets.get('fav_sort')
                if fav_sort: fav_sort.set_value(1 if is_fav else 0, "")
            
            # 2. Score
            spin = widgets.get('score')
            if spin:
                score_val = int(item.get('score', 0))
                if spin.value() != score_val:
                    spin.blockSignals(True)
                    spin.setValue(score_val)
                    spin.blockSignals(False)
                
                score_sort = widgets.get('score_sort')
                if score_sort: score_sort.set_value(score_val, str(score_val))
            
            # 3. Name
            edit = widgets.get('name')
            if edit:
                display_name = item.get('display_name', '')
                if edit.text() != display_name:
                    edit.blockSignals(True)
                    edit.setText(display_name)
                    edit.blockSignals(False)
                
                name_sort = widgets.get('name_sort')
                if name_sort:
                    folder_name = os.path.basename(rel_path)
                    name_sort.set_value(display_name or folder_name, "") # Keep empty text!
            
            # 4. Tags
            item_tags_str = item.get('tags', '') or ""
            current_tags_set = {t.strip().lower() for t in item_tags_str.split(",") if t.strip()}
            
            tag_widgets = widgets.get('tags', {})
            tag_sort_items = widgets.get('tag_sort_items', {})
            
            # Phase 1.1.105: Exhaustive tag button reset (Icon/Text/Emoji + Style)
            # This is critical to fix the "Label Bug" settings ignore issue.
            for tag_name, btn_tag in tag_widgets.items():
                is_active = tag_name in current_tags_set
                tag_info = self._tag_cache.get(tag_name, {}).get('info', {})
                self._sync_tag_button(btn_tag, tag_info, is_active, tag_name)
                
                ts_item = tag_sort_items.get(tag_name)
                if ts_item: ts_item.set_value(1 if is_active else 0, "")
        
        # Phase 1.1.106: Guarantee sort consistency on re-load/reset
        self.table.sortItems(4, Qt.SortOrder.AscendingOrder)
        hh = self.table.horizontalHeader()
        hh.setSortIndicator(4, Qt.SortOrder.AscendingOrder)
        self._last_sort_col = 4
        self._last_sort_order = Qt.SortOrder.AscendingOrder
        
        self.table.blockSignals(False)
        logging.info(f"[QuickViewCache] Extreme UI & Sort Reset completed in {time.perf_counter() - t_start:.3f}s")

    def keyPressEvent(self, event):
        """Handle Alt+Enter for saving."""
        if event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter] and event.modifiers() & Qt.KeyboardModifier.AltModifier:
            self._on_save_clicked() # This calls _perform_save and accept()
            event.accept()
            return
        super().keyPressEvent(event)

    def _has_real_changes(self):
        """Directly probe widgets for changes against original state (Immune to sorting)."""
        if not self._widget_map: 
            logging.debug("[QuickViewAudit] No widget map, assuming no changes.")
            return False
        
        # Create a fast lookup for original data by rel_path
        item_map = {i['rel_path']: i for i in self.items_data}
        
        for rel_path, widgets in self._widget_map.items():
            item = item_map.get(rel_path)
            if not item: continue
            
            # 1. Fav
            fav_cb = widgets.get('fav')
            if fav_cb:
                cur_fav = fav_cb.isChecked()
                orig_fav = item.get('_orig_fav', False)
                if cur_fav != orig_fav:
                    logging.info(f"[QuickViewAudit] Change detected in Fav: {rel_path} ({orig_fav} -> {cur_fav})")
                    return True
            
            # 2. Score
            score_spin = widgets.get('score')
            if score_spin:
                cur_score = score_spin.value()
                orig_score = item.get('_orig_score', 0)
                if cur_score != orig_score:
                    logging.info(f"[QuickViewAudit] Change detected in Score: {rel_path} ({orig_score} -> {cur_score})")
                    return True
            
            # 3. Name (Mode 1 uses internal edits)
            name_edit = widgets.get('name')
            if name_edit:
                cur_name = name_edit.text()
                orig_name = (item.get('_orig_name') or "")
                if cur_name != orig_name:
                    logging.info(f"[QuickViewAudit] Change detected in Name: {rel_path} ('{orig_name}' -> '{cur_name}')")
                    return True
            
            # 4. Tags (Incorporate pending changes)
            original_tags_norm = item.get('_orig_tags', "")
            
            # Construct final state by applying pending changes to item['tags']
            current_tags_set = {t.strip().lower() for t in (item.get('tags') or "").split(",") if t.strip()}
            if rel_path in self._pending_tag_changes:
                for tag, state in self._pending_tag_changes[rel_path].items():
                    if state: current_tags_set.add(tag.lower())
                    else: current_tags_set.discard(tag.lower())
            
            final_tags_norm = ",".join(sorted(list(current_tags_set)))
            if final_tags_norm != original_tags_norm:
                logging.info(f"[QuickViewAudit] Change detected in Tags: {rel_path} ('{original_tags_norm}' -> '{final_tags_norm}')")
                return True
                
        return False

    def reject(self):
        """Handle Close button or Esc: Prompt if changes exist."""
        if self._has_real_changes():
            from src.core.lang_manager import _
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle(_("Save Changes"))
            msg_box.setText(_("You have unsaved changes. Do you want to save them before closing?"))
            msg_box.setStandardButtons(QMessageBox.StandardButton.Save | 
                                       QMessageBox.StandardButton.Discard | 
                                       QMessageBox.StandardButton.Cancel)
            msg_box.setDefaultButton(QMessageBox.StandardButton.Save)
            
            # Translate buttons if needed (already handled by system usually, but consistent style)
            ret = msg_box.exec()
            
            if ret == QMessageBox.StandardButton.Save:
                self._on_save_clicked() # This calls _perform_save and accept()
                return
            elif ret == QMessageBox.StandardButton.Cancel:
                return # Stay in dialog
            # If Discard, proceed to restore data and close

        self.save_options("quick_view_manager")
        # Restore original data to ensure the cache stays clean
        self.items_data.clear()
        self.items_data.extend(copy.deepcopy(self._raw_items_data))
        
        # Reset change buffers to prevent leaking discards into next open
        if hasattr(self, '_pending_tag_changes'):
            self._pending_tag_changes.clear()
        if hasattr(self, '_pending_changes'): # Mode 2
            self._pending_changes.clear()
        self._has_changes = False
        
        self._last_items_data = copy.deepcopy(self.items_data)
        # Phase 1.1.40 REMOVAL: Do NOT invalidate context_id.
        # This preserves column settings/structure while _reset_ui_to_data handles visual sync.
        
        super().reject()

    def accept(self):
        """Override accept to save window state before closing."""
        self.save_options("quick_view_manager")
        super().accept()
        
    def closeEvent(self, event):
        """Save window geometry on close."""
        self.save_options("quick_view_manager")
        super().closeEvent(event)

    def _load_table_data(self):
        """Initial table setup and starting chunked load (Phase 1.1.5)."""
        self._profile_start_time = time.perf_counter()
        logging.info(f"[QuickViewProfile] Starting load for {len(self.items_data)} items.")
        print(f"[DEBUG] QuickViewManager: items_data count = {len(self.items_data)}, active_tags count = {len(self.active_tags)}")
        # Phase 1.1.8: Removed setUpdatesEnabled(False) to allow immediate display
        self.table.setSortingEnabled(False) # Disable sorting during load
        self.table.clearContents() # Phase 7: Ensure clean slate to prevent stale widgets from previous context
        self._widget_map.clear() # Phase 1.1.45: Clear pointers on fresh load
        self.table.setRowCount(len(self.items_data))
        self.current_load_row = 0
        self._load_next_chunk()

    def _load_next_chunk(self):
        """Load a batch of rows to keep the UI responsive."""
        start = self.current_load_row
        end = min(start + self.load_batch_size, len(self.items_data))
        
        # Detailed timing for this chunk
        now = time.perf_counter()
        if self._last_chunk_end_time > 0:
            self._total_gap_time += (now - self._last_chunk_end_time)
            
        t_icon_total = 0
        t_name_total = 0
        t_tag_total = 0
        t_row_total = 0
        chunk_start = now
        
        try:
            for row in range(start, end):
                t_row_start = time.perf_counter()
                item = self.items_data[row]
                # Map widget initialization
                rel_path = item['rel_path']
                if rel_path not in self._widget_map:
                    self._widget_map[rel_path] = {'tags': {}, 'tag_sort_items': {}}
                
                # 0. No. Cell - Black BG, White Text
                no_item = NaturalSortTableWidgetItem(row + 1)
                no_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                no_item.setBackground(QColor("#000000"))
                no_item.setForeground(QColor("#ffffff"))
                self.table.setItem(row, 0, no_item)
                
                # 1. Icon Cell
                t_icon_start = time.perf_counter()
                icon_widget = QWidget()
                icon_layout = QHBoxLayout(icon_widget)
                icon_layout.setContentsMargins(2, 2, 2, 2)
                
                icon_path = item.get('image_path')
                icon_btn = QPushButton()
                icon_btn.setFixedSize(36, 36)
                icon_btn.setProperty("rel_path", item.get('rel_path'))
                
                if icon_path:
                    if len(icon_path) <= 4:
                        icon_btn.setIcon(QIcon())
                        icon_btn.setText(icon_path)
                    else:
                        if icon_path not in self._icon_cache:
                            self._icon_cache[icon_path] = QIcon(icon_path)
                        icon_btn.setIcon(self._icon_cache[icon_path])
                        icon_btn.setIconSize(QSize(32, 32))
                        icon_btn.setText("") # Ensure no leftover text
                else:
                    icon_btn.setIcon(QIcon())
                    icon_btn.setText("❓")
                
                icon_btn.clicked.connect(lambda ch, btn=icon_btn: self._on_icon_btn_clicked(btn))
                icon_layout.addWidget(icon_btn, alignment=Qt.AlignmentFlag.AlignCenter)
                self.table.setCellWidget(row, 1, icon_widget)
                
                # Phase 1.1.110: Map Icon/No for exhaustive sync
                self._widget_map[rel_path]['icon_btn'] = icon_btn
                self._widget_map[rel_path]['no_item'] = no_item

                t_icon_total += time.perf_counter() - t_icon_start
                
                # 2. Favorite (CheckBox) - Col 2
                fav_widget = QWidget()
                fav_layout = QHBoxLayout(fav_widget)
                fav_layout.setContentsMargins(0,0,0,0)
                fav_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                
                fav_cb = QPushButton()
                fav_cb.setCheckable(True)
                is_fav = item.get('is_favorite', False)
                fav_cb.setChecked(is_fav)
                fav_cb.setFixedSize(24, 24)
                fav_cb.setText("") 
                fav_cb.setIcon(self._draw_star_icon(is_fav))
                fav_cb.setIconSize(QSize(22, 22))
                fav_cb.setStyleSheet(f"background: transparent; border: none;") 
                
                self._widget_map[rel_path]['fav'] = fav_cb
                
                fav_cb.toggled.connect(lambda checked, rel=rel_path: self._on_fav_toggled_v2(rel, checked))
                fav_cb.setProperty("rel_path", item['rel_path'])
                fav_cb.setProperty("is_fav_editor", True) 
                
                fav_layout.addWidget(fav_cb)
                
                fav_sort_item = SortableTableWidgetItem(1 if is_fav else 0, "")
                self.table.setItem(row, 2, fav_sort_item)
                self.table.setCellWidget(row, 2, fav_widget)
                self._widget_map[rel_path]['fav_sort'] = fav_sort_item

                # 3. Score (SpinBox) - Col 3
                score_widget = QWidget()
                score_layout = QHBoxLayout(score_widget)
                score_layout.setContentsMargins(0,0,0,0)
                score_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                
                score_val = int(item.get('score', 0))
                score_spin = QSpinBox()
                score_spin.setRange(0, 9999)
                score_spin.setValue(score_val)
                score_spin.setFixedWidth(60)
                score_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
                score_spin.setStyleSheet("""
                    QSpinBox { background-color: #333; color: white; border: 1px solid #555; border-radius: 4px; }
                    QSpinBox::up-button, QSpinBox::down-button { background-color: #444; width: 16px; }
                    QSpinBox::up-button:hover, QSpinBox::down-button:hover { background-color: #555; }
                """)
                self._widget_map[item['rel_path']]['score'] = score_spin
                score_spin.valueChanged.connect(lambda val, rel=item['rel_path']: self._on_score_changed_v2(rel, val))
                score_spin.setProperty("rel_path", item['rel_path'])
                score_spin.setProperty("is_score_editor", True) 
                
                score_layout.addWidget(score_spin)
                
                score_sort_item = SortableTableWidgetItem(score_val, "")
                self.table.setItem(row, 3, score_sort_item)
                self.table.setCellWidget(row, 3, score_widget)
                self._widget_map[item['rel_path']]['score_sort'] = score_sort_item

                # 4. Folder Name (Read-only context) - Col 4
                folder_name = os.path.basename(item.get('rel_path'))
                folder_item = NaturalSortTableWidgetItem(folder_name)
                folder_item.setForeground(QColor("#bbbbbb")) 
                font = folder_item.font()
                font.setItalic(True)
                folder_item.setFont(font)
                self.table.setItem(row, 4, folder_item)
                self._widget_map[item['rel_path']]['folder_sort'] = folder_item
                
                # 5. Display Name (Editable) - Col 5
                t_name_start = time.perf_counter()
                name_edit = QuickEdit(item.get('display_name') or "")
                name_edit.setPlaceholderText(folder_name)
                name_edit.setStyleSheet("color: #ffffff; background-color: #4a4a4a; border: 1px solid #555; padding: 4px; border-radius: 4px;")
                name_edit.textChanged.connect(lambda text, rel=item['rel_path']: self._on_name_edited_v2(rel, text))
                self._widget_map[item['rel_path']]['name'] = name_edit
                self.table.setCellWidget(row, 5, name_edit)
                sort_name = (item.get('display_name') or folder_name)
                name_sort_item = NaturalSortTableWidgetItem(sort_name, "") 
                self.table.setItem(row, 5, name_sort_item) 
                self._widget_map[item['rel_path']]['name_sort'] = name_sort_item
                t_name_total += time.perf_counter() - t_name_start
                
                # 6+. Tags/Separator Columns
                t_tag_start = time.perf_counter()
                current_tags = {t.strip().lower() for t in (item.get('tags') or "").split(",") if t.strip()}
                
                for i, col_info in enumerate(self._all_tag_columns):
                    col_idx = 6 + i
                    
                    if col_info['type'] == 'sep':
                        sep_label = QLabel("|")
                        sep_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        sep_label.setStyleSheet("color: #666; font-weight: bold;")
                        self.table.setCellWidget(row, col_idx, sep_label)
                    else:
                        tag_info = col_info['tag_info']
                        tag_name = tag_info.get('name', '')
                        lower_name = tag_name.lower()
                        is_active = lower_name in current_tags
                        
                        mode = tag_info.get('display_mode', 'text')
                        emoji = tag_info.get('emoji', '')
                        display_name = tag_info.get('display', tag_name)
                        icon_path = tag_info.get('icon', '')
                        
                        tag_btn = QPushButton()
                        tag_btn.setCheckable(True)
                        tag_btn.setFixedSize(31, 31) 
                        tag_btn.setProperty("rel_path", item['rel_path']) 
                        tag_btn.setProperty("tag_name", lower_name) 
                        
                        self._sync_tag_button(tag_btn, tag_info, is_active, tag_name)
                        
                        self._widget_map[item['rel_path']]['tags'][lower_name] = tag_btn
                        
                        tag_btn.toggled.connect(lambda ch, btn=tag_btn: self._on_tag_toggled_v2(btn.property("rel_path"), btn.property("tag_name"), ch, btn))
                        
                        tag_widget = QWidget()
                        tag_layout = QHBoxLayout(tag_widget)
                        tag_layout.setContentsMargins(0,0,0,0)
                        tag_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        tag_layout.addWidget(tag_btn)
                        
                        self.table.setCellWidget(row, col_idx, tag_widget)
                        
                        tag_sort_item = SortableTableWidgetItem(1 if is_active else 0, "")
                        self.table.setItem(row, col_idx, tag_sort_item)
                        self._widget_map[item['rel_path']]['tag_sort_items'][lower_name] = tag_sort_item

                t_tag_total += time.perf_counter() - t_tag_start
                self.table.setRowHeight(row, 44)
                t_row_total += time.perf_counter() - t_row_start
        except Exception as e:
            logging.error(f"[QuickView] Critical error in load_next_chunk row {row}: {e}", exc_info=True)

        chunk_time = time.perf_counter() - chunk_start
        self._last_chunk_end_time = time.perf_counter()
        # logging.info(f"[QuickViewProfile] Chunk {start}-{end}: {chunk_time:.3f}s")
        
        self.current_load_row = end
        
        if self.current_load_row < len(self.items_data):
            QTimer.singleShot(0, self._load_next_chunk)
        else:
            # Full load finished
            self.table.resizeColumnsToContents()
            
            # Enforce min/max widths for tag columns (index 6+)
            for i in range(6, self.table.columnCount()):
                if self.table.columnWidth(i) < 41:
                    self.table.setColumnWidth(i, 41)
            
            # Reduce separators
            for i, col_info in enumerate(self._all_tag_columns):
                 if col_info['type'] == 'sep':
                     self.table.setColumnWidth(6+i, 2)

            # Wait until EVERYTHING is fully loaded and layout is settled
            self.table.updateGeometry()
            QApplication.processEvents()
            
            # Final visibility enforcement
            self.setWindowOpacity(1.0)
            self.show()
            self.raise_()
            self.activateWindow()
            self.table.sortItems(4, Qt.SortOrder.AscendingOrder)
            self.table.horizontalHeader().setSortIndicator(4, Qt.SortOrder.AscendingOrder)
            self._last_sort_col = 4
            self._last_sort_order = Qt.SortOrder.AscendingOrder
            
            logging.info(f"[QuickViewProfile] Finished loading. Total time: {time.perf_counter() - self._profile_start_time:.3f}s")
            self._total_tag_creation_time = t_tag_total # For debug logging access

    def _sync_tag_button(self, btn, tag_info, is_active, tag_name=""):
        """Unified method to sync tag button content and style based on info and state."""
        btn.blockSignals(True)
        btn.setChecked(is_active)
        
        if tag_info:
            display_mode = tag_info.get('display_mode', 'text')
            emoji = tag_info.get('emoji', '')
            icon_path = tag_info.get('icon', '')
            display_text = tag_info.get('display', tag_name)
            
            # Phase 1.1.140: Standardized Mode Checks
            # Both 'icon' and 'image' are treated as image-based buttons.
            if (display_mode == 'icon' or display_mode == 'image') and icon_path and os.path.exists(icon_path):
                if icon_path not in self._icon_cache:
                    self._icon_cache[icon_path] = QIcon(icon_path)
                btn.setIcon(self._icon_cache[icon_path])
                btn.setIconSize(QSize(24, 24))
                btn.setText("") # Ensure no leftover text
            elif (display_mode == 'symbol' or display_mode == 'text_symbol') and emoji:
                btn.setIcon(QIcon()) # Ensure no leftover icon
                btn.setText(emoji)
            else:
                btn.setIcon(QIcon())
                btn.setText(display_text[:2] if len(display_text) > 2 else display_text)
        else:
            # Fallback if no tag info found in cache
            btn.setIcon(QIcon())
            btn.setText((tag_name or "")[:2])
        
        self._update_tag_btn_style(btn, is_active)
        btn.blockSignals(False)


    
    def _track_tag_creation(self, dt):
        """Collect rendering times."""
        self._total_tag_creation_time += dt

    def _on_icon_btn_clicked(self, btn):
        # Open a simple context menu for Select Photo
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        # Use white background per user request
        menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                color: #333333;
                border: 1px solid #ddd;
            }
            QMenu::item:selected {
                background-color: #f0f0f0;
            }
        """)
        
        act_photo = menu.addAction(_("📷 Select Photo..."))
        
        action = menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))
        if action == act_photo:
            from PyQt6.QtWidgets import QFileDialog
            file_path, filter_str = QFileDialog.getOpenFileName(self, _("Select Icon"), "", "Images (*.png *.jpg *.jpeg *.webp *.ico *.svg)")
            if file_path:
                btn.setIcon(QIcon(file_path))
                btn.setText("")
                btn.setProperty("new_icon", file_path)

    def _on_tag_toggled_v2(self, rel_path, tag_name, checked, sender_btn):
        """Handle click on tag button using persistent rel_path."""
        if not rel_path: return
        
        item = next((i for i in self.items_data if i['rel_path'] == rel_path), None)
        if not item: return
        
        if rel_path in self._pending_tag_changes and self._pending_tag_changes[rel_path].get(tag_name.lower()) == checked:
             return # No real change from pending state
             
        if rel_path not in self._pending_tag_changes:
            self._pending_tag_changes[rel_path] = {}
        # Phase 1.1.85: Always store lowercase to match comparison
        self._pending_tag_changes[rel_path][tag_name.lower()] = checked

        current_tags_list = [t.strip().lower() for t in (item.get('tags') or "").split(",") if t.strip()]
        
        lower_target = tag_name.lower()
        if checked:
            if lower_target not in current_tags_list:
                current_tags_list.append(lower_target)
        else:
            if lower_target in current_tags_list:
                current_tags_list.remove(lower_target)
        
        new_tags_str = ",".join(sorted(current_tags_list))
        item['tags'] = new_tags_str
        
        # Phase 1.1.95: Update styling
        self._update_tag_btn_style(sender_btn, checked)

        self._has_changes = True # Flag potential change
        self._update_window_title()
        # Find the row and column of the sender button
        row = -1
        col = -1
        for r_idx in range(self.table.rowCount()):
            for c_idx in range(6, self.table.columnCount()): # Only check tag columns
                widget = self.table.cellWidget(r_idx, c_idx)
                if widget:
                    btn = widget.findChild(QPushButton)
                    if btn is sender_btn: # Found the sender button
                        row = r_idx
                        col = c_idx
                        break
            if row != -1:
                break
        
        if row != -1 and col != -1:
            sort_item = self.table.item(row, col)
            if sort_item:
                sort_item._sort_value = 1 if checked else 0
                # Trigger sorting update if currently sorted by this column
                if self.table.horizontalHeader().sortIndicatorSection() == col:
                    self.table.sortItems(col, self.table.horizontalHeader().sortIndicatorOrder())
        
        # User Feedback: Immediate row hiding if "Hidden" is selected and show_hidden is False
        is_hidden_now = any(t in ["hidden", "非表示"] for t in current_tags_list)
        if is_hidden_now and not self.show_hidden_items:
             self.table.setRowHidden(row, True)
        elif not is_hidden_now and not self.show_hidden_items:
             # If it was hidden and now isn't, unhide it (if show_hidden is False)
             self.table.setRowHidden(row, False)

        self._has_changes = True

    def _on_tag_w_clicked(self, tag_name, preview_widget):
        """Handle click on painter-based tag."""
        # Update row internal state
        row = self.table.indexAt(preview_widget.pos()).row()
        if row < 0: return
        
        item = self.items_data[row]
        current_tags_list = [t.strip().lower() for t in (item.get('tags') or "").split(",") if t.strip()]
        
        lower_target = tag_name.lower()
        if lower_target in current_tags_list:
            current_tags_list.remove(lower_target)
        else:
            current_tags_list.append(lower_target)
        
        new_tags_str = ",".join(current_tags_list)
        item['tags'] = new_tags_str # Update local items_data
        
        # Update widget's selection set
        preview_widget._current_tags = set(current_tags_list)
        
        # User Feedback: Immediate row hiding if "Hidden" is selected and show_hidden is False
        # Assuming "Hidden" or "非表示" might be the tag name
        is_hidden_now = any(t in ["hidden", "非表示"] for t in current_tags_list)
        if is_hidden_now and not self.show_hidden_items:
             self.table.setRowHidden(row, True)

    def _on_fav_toggled_v2(self, rel_path, checked):
        # Find item by rel_path (robust against sorting)
        item = next((i for i in self.items_data if i['rel_path'] == rel_path), None)
        if not item: return
        
        if item.get('is_favorite') == checked: return # Guard against redundant signals
        item['is_favorite'] = checked
        
        # Update star icon on the sender if possible
        sender = self.sender()
        if sender and hasattr(sender, 'setIcon'):
            sender.setIcon(self._draw_star_icon(checked))
        
        # Update Sorting Item
        row = -1
        for r in range(self.table.rowCount()):
            w = self.table.cellWidget(r, 2) # Fav column
            if w:
                btn = w.findChild(QPushButton)
                if btn and btn.property("rel_path") == rel_path:
                    row = r
                    break
        
        if row != -1:
            sort_item = self.table.item(row, 2)
            if sort_item:
                sort_item._sort_value = 1 if checked else 0
                # Trigger sorting update if currently sorted by this column
        self._has_changes = True
        self._update_window_title()

    def _on_score_changed_v2(self, rel_path, val):
        item = next((i for i in self.items_data if i['rel_path'] == rel_path), None)
        if not item: return
        
        if int(item.get('score', 0)) == val: return # Guard
        item['score'] = val
        
        # Update Sorting Item
        row = -1
        for r in range(self.table.rowCount()):
            w = self.table.cellWidget(r, 3) # Score column
            if w:
                spin = w.findChild(QSpinBox)
                if spin and spin.property("rel_path") == rel_path:
                    row = r
                    break
                    
        if row != -1:
            sort_item = self.table.item(row, 3)
            if sort_item:
                sort_item._sort_value = val
                # Trigger sorting update if currently sorted by this column
                if self.table.horizontalHeader().sortIndicatorSection() == 3:
                    self.table.sortItems(3, self.table.horizontalHeader().sortIndicatorOrder())
        
        self._has_changes = True
        self._update_window_title()

    def _on_name_edited_v2(self, rel_path, text):
        """Handle live text change for name in Mode 1."""
        item = next((i for i in self.items_data if i['rel_path'] == rel_path), None)
        if not item: return
        
        # Update live data so _has_real_changes() works
        item['display_name'] = text
        
        # O(1) variant using widget_map for fast sorting update
        it_sort = self._widget_map.get(rel_path, {}).get('name_sort')
        if it_sort:
            it_sort.setText(text if text else os.path.basename(rel_path))
            if self.table.horizontalHeader().sortIndicatorSection() == 5:
                self.table.sortItems(5, self.table.horizontalHeader().sortIndicatorOrder())

        self._has_changes = True
        self._update_window_title()

    def _on_save_clicked(self):
        self._perform_save()
        self.accept()

    def _perform_save(self):
        """Collect changes by mapping table widgets back to items_data via rel_path."""
        self._has_changes = False
        update_list = []
        
        # Create a mapping for quick access to items_data
        item_map = {i['rel_path']: i for i in self.items_data}
        
        for row in range(self.table.rowCount()):
            # Get rel_path from a reliable widget in this row
            fav_widget_container = self.table.cellWidget(row, 2)
            if not fav_widget_container: continue
            
            btn_fav = fav_widget_container.findChild(QPushButton)
            if not btn_fav: continue
            
            rel_path = btn_fav.property("rel_path")
            item_data = item_map.get(rel_path)
            if not item_data: continue
            
            changes = {}
            
            # 1. Favorite
            is_fav = btn_fav.isChecked()
            orig_fav = item_data.get('_orig_fav', False)
            if is_fav != orig_fav:
                changes['is_favorite'] = is_fav
                logging.debug(f"[SaveDebug] {rel_path}: Fav changed {orig_fav} -> {is_fav}")
            
            # 2. Score
            score_widget_container = self.table.cellWidget(row, 3)
            if score_widget_container:
                spin = score_widget_container.findChild(QSpinBox)
                if spin:
                    sc = spin.value()
                    orig_score = item_data.get('_orig_score', 0)
                    if sc != orig_score:
                        changes['score'] = sc
                        logging.debug(f"[SaveDebug] {rel_path}: Score changed {orig_score} -> {sc}")
            
            # 3. Display Name
            name_widget = self.table.cellWidget(row, 5)
            if isinstance(name_widget, QLineEdit):
                name_text = name_widget.text().strip()
                orig_name = item_data.get('_orig_name', "")
                # Phase 1.1.71: Only save if there's a REAL change
                # If both are empty (or effectively empty), it's not a change
                # If user typed something different, that's a change
                if name_text != orig_name:
                    # Additional guard: Empty "" to "" is not a change
                    if not (name_text == "" and orig_name == ""):
                        changes['display_name'] = name_text
                        logging.debug(f"[SaveDebug] {rel_path}: Name changed '{orig_name}' -> '{name_text}'")

            # 4. Tags
            if rel_path in self._pending_tag_changes:
                row_changes = self._pending_tag_changes[rel_path]
                if row_changes:
                    # Construct final tags set
                    original_tags_set = {t.strip().lower() for t in (item_data.get('_orig_tags', '')).split(',') if t.strip()}
                    
                    # Casing fix: Try to preserve original casing from item_data['tags'] if available
                    raw_tags = item_data.get('tags', '')
                    casing_map = {t.strip().lower(): t.strip() for t in raw_tags.split(',') if t.strip()}
                    
                    final_tags_list = []
                    # Construct current tags including pending changes
                    current_tags_set = {t.strip().lower() for t in raw_tags.split(",") if t.strip()}
                    if rel_path in self._pending_tag_changes:
                        for tag, state in self._pending_tag_changes[rel_path].items():
                            if state: current_tags_set.add(tag.lower())
                            else: current_tags_set.discard(tag.lower())
                    
                    for t_low in sorted(list(current_tags_set)):
                        # If tag existed, use its old casing. If new or from frequent list, use that.
                        preserved = casing_map.get(t_low)
                        if preserved: 
                            final_tags_list.append(preserved)
                        else:
                            # Search in frequent_tags for correct casing
                            freq_match = next((ft['name'] for ft in self.frequent_tags if ft['name'].lower() == t_low), t_low)
                            final_tags_list.append(freq_match)
                            
                    new_tags_str = ",".join(final_tags_list)
                    # Compare using lowercase normalization to avoid 144-items bug
                    if _normalize_tags(new_tags_str, lowercase=True) != item_data.get('_orig_tags', ''):
                        changes['tags'] = new_tags_str

            if changes:
                changes['rel_path'] = rel_path
                update_list.append(changes)
        
        if update_list:
            if self.db:
                try:
                    success = self.db.bulk_update_items(update_list) # Assume this exists or db.update_item loop
                    if success:
                        # Phase 1.1.15: Populate results to trigger immediate UI refresh in main window
                        self.results = update_list
                        
                        # Phase 1.1.100: Update original state markers after successful save
                        # This prevents stale comparisons on next save attempt
                        for changes in update_list:
                            rp = changes.get('rel_path')
                            item = next((i for i in self.items_data if i['rel_path'] == rp), None)
                            if item:
                                if 'is_favorite' in changes:
                                    item['is_favorite'] = changes['is_favorite']
                                    item['_orig_fav'] = changes['is_favorite']
                                if 'score' in changes:
                                    item['score'] = changes['score']
                                    item['_orig_score'] = changes['score']
                                if 'display_name' in changes:
                                    item['display_name'] = changes['display_name']
                                    item['_orig_name'] = changes['display_name']
                                if 'tags' in changes:
                                    item['tags'] = changes['tags']
                                    # ALWAYS use absolute lowercase for comparison base
                                    item['_orig_tags'] = _normalize_tags(changes['tags'], lowercase=True)
                        
                        # Clear pending tag changes to prevent stale data
                        self._pending_tag_changes.clear()
                        
                        self._update_window_title() # Remove "Unsaved" marker
                        self.accept()
                    else:
                        QMessageBox.critical(self, _("Error"), _("Failed to update items."))
                except Exception as e:
                    QMessageBox.critical(self, "Error", _("Failed to save changes: {e}").format(e=str(e)))
            else:
                 QMessageBox.information(self, "Demo", f"Would update {len(update_list)} items:\n{update_list}")
                 self.accept()
        else:
            self.accept()
