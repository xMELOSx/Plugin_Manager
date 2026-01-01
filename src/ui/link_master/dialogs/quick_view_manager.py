from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
                             QScrollArea, QWidget, QMessageBox, QMenu, QSpinBox)
from PyQt6.QtCore import Qt, QSize, QTimer, QPoint, QRect, QRectF
from PyQt6.QtGui import QIcon, QAction, QPainter, QPen, QBrush, QColor, QPolygonF, QPixmap, QPalette
import os
import time
import logging
import ctypes
from src.core.lang_manager import _
from src.ui.link_master.tag_bar import TagWidget
from src.ui.window_mixins import OptionsMixin
from src.ui.frameless_window import FramelessDialog

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
            else:
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

class SortableTableWidgetItem(QTableWidgetItem):
    """Custom item for sorting by specific data types (bool, int) instead of string."""
    def __init__(self, value, display_text=None):
        super().__init__(display_text if display_text is not None else str(value))
        self._sort_value = value

    def __lt__(self, other):
        return self._sort_value < other._sort_value

class QuickViewManagerDialog(FramelessDialog, OptionsMixin):
    """
    Bulk edit dialog for currently visible items in the category/package area.
    Supports editing: Icon (Emoji/Image), Display Name, and Tags (via Toggles).
    """
    def __init__(self, parent=None, items_data: list = None, frequent_tags=None, db=None, storage_root=None, thumbnail_loader=None, show_hidden=True):
        super().__init__(parent)
        
        # FramelessDialog handles opacity and styling (default 0.95 opacity, matching main window style)
        
        self.setWindowTitle(_("Quick View Manager"))
        self.setMinimumSize(850, 500)
        self.items_data = items_data or [] # List of dicts {rel_path, display_name, tags, image_path, ...}
        self.frequent_tags = frequent_tags or [] # List of dicts {name, display, emoji, ...}
        self.db = db
        self.storage_root = storage_root
        self.thumbnail_loader = thumbnail_loader
        self.show_hidden_items = show_hidden
        self.results = [] # To be populated on accept
        
        # Phase 1.1.11: include separators in active_tags
        self.active_tags = self.frequent_tags
        self._tag_cache = {} 
        self._icon_cache = {}
        self._prepare_tag_cache()
        
        self.current_load_row = 0
        self.load_batch_size = 100 
        self.load_timer = QTimer(self)
        self.load_timer.timeout.connect(self._load_next_chunk)
        
        # Profiling stats
        self._last_chunk_end_time = 0.0
        self._total_gap_time = 0.0
        self._total_render_time = 0.0
        self._total_tag_creation_time = 0.0
        
        # Track pending tag changes in memory {row: {tag_name: bool}}
        self._pending_tag_changes = {}
        
        # UI Setup (Apply styles before layout to prevent white flash)
        # IMPORTANT: Maintain transparency for the root dialog
        self.setStyleSheet("""
            /* Root - transparent for frameless effect */
            QDialog { background: transparent; }
            
            /* Main Content Area - Match Main Window visual appearance */
            QWidget {
                background-color: #353535;
                color: #ffffff;
            }
            
            /* Table styling */
            QTableWidget { 
                background-color: #353535;
                color: #ffffff; 
                gridline-color: #444; 
                border: none;
                selection-background-color: #3498db;
            }
            
            /* Horizontal Header (column names) */
            QHeaderView::section {
                background-color: #333;
                color: #ffffff;
                border: 1px solid #444;
                font-weight: bold;
                padding: 6px;
            }
            
            /* Vertical Header (row numbers) - WHITE TEXT */
            QHeaderView::section:vertical {
                background-color: #333;
                color: #ffffff;
                border: 1px solid #444;
                padding: 4px 8px;
            }
            
            QTableCornerButton::section { background-color: #333; border: 1px solid #444; }
            
            /* Input Fields */
            QLineEdit { 
                background-color: #3a3a3a; 
                color: #ffffff; 
                border: 1px solid #555; 
                padding: 4px; 
                border-radius: 4px; 
            }
            QLineEdit:focus { border: 1px solid #3498db; background-color: #444; }
            
            /* Labels */
            QLabel { color: #ffffff; background: transparent; } 
            
            /* Buttons */
            QPushButton {
                background-color: #3a3a3a;
                color: #ffffff;
                border: 1px solid #555;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #4a4a4a; }
            QPushButton#save_btn { background-color: #3498db; border-color: #2980b9; }
            QPushButton#save_btn:hover { background-color: #2980b9; }
            
            /* Scrollbar */
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
            QScrollBar::handle:vertical:hover { background-color: #666; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            
            QToolTip { background-color: #333; color: #fff; border: 1px solid #555; padding: 4px; }
        """)
        
        self._init_ui()
        # Phase 1.1.14: Set app icon for title bar (same as main window)
        import os
        from PyQt6.QtGui import QIcon, QPixmap
        from PyQt6.QtCore import Qt
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
        QTimer.singleShot(0, self._load_table_data)
    
    def _update_tag_btn_style(self, btn, is_active):
        if is_active:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3498db; 
                    border: none; 
                    border-radius: 10px;
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
                }
                QPushButton:hover {
                    background-color: #777;
                }
            """)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

    def _on_tag_toggled(self, row, tag_lower, checked, btn):
        # Update UI style
        self._update_tag_btn_style(btn, checked)
        
        # Track change
        if row not in self._pending_tag_changes:
            self._pending_tag_changes[row] = {}
        self._pending_tag_changes[row][tag_lower] = checked
        
        # Find column for this tag to update sort
        # Search in _all_tag_columns (includes separators for correct column indices)
        tag_col = -1
        for i, col_info in enumerate(self._all_tag_columns):
            if col_info['type'] != 'sep':
                if col_info['tag_info'].get('name', '').lower() == tag_lower:
                    tag_col = 6 + i
                    break
        
        if tag_col != -1:
            sort_item = self.table.item(row, tag_col)
            if sort_item:
                # Update _sort_value for correct sorting
                sort_item._sort_value = 1 if checked else 0
                # Live sort
                if self.table.isSortingEnabled() and self.table.horizontalHeader().sortIndicatorSection() == tag_col:
                    self.table.sortItems(tag_col, self.table.horizontalHeader().sortIndicatorOrder())

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
            # New column: start with descending
            new_order = Qt.SortOrder.DescendingOrder
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
            self._tag_cache[tag_name] = {
                'info': t,
                'lower_name': tag_name.lower()
            }


    def _init_ui(self):
        # Create a container widget for content
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(5, 0, 5, 5) # Reduced top margin
        
        # 1. Hide Vertical Header
        self.table = QTableWidget()
        self.table.verticalHeader().setVisible(False)
        
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
                self.table.setColumnWidth(col_idx, 4)  # Very thin separator
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
        
        # Default sort order: Descending first
        self.table.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.DescendingOrder)
        self._last_sort_col = -1
        self._last_sort_order = Qt.SortOrder.DescendingOrder
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
        btn_layout.addStretch()
        self.save_btn = QPushButton(_("Save All (Alt + Enter)"))
        self.save_btn.clicked.connect(self._on_save_clicked)
        self.save_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; width: 220px; border-radius: 4px; padding: 6px;")
        
        self.cancel_btn = QPushButton(_("Cancel"))
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setMinimumWidth(80)
        self.cancel_btn.setStyleSheet("background-color: #666666; color: white; border-radius: 4px; padding: 6px;") # Gray Cancel Button
        
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
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

    def keyPressEvent(self, event):
        """Handle Alt+Enter for saving."""
        if event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter] and event.modifiers() & Qt.KeyboardModifier.AltModifier:
            self._on_save_clicked()
            return
        super().keyPressEvent(event)

    def reject(self):
        """Override reject to save window state before closing."""
        self.save_options("quick_view_manager")
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
        
        for row in range(start, end):
            t_row_start = time.perf_counter()
            item = self.items_data[row]
            # Phase 1.1.13: Store original tags to detect changes later
            if '_orig_tags' not in item:
                item['_orig_tags'] = item.get('tags', '')
            
            # 0. No. Cell - Black BG, White Text
            no_item = SortableTableWidgetItem(row + 1)
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
                if len(icon_path) <= 4: # Likely emoji
                    icon_btn.setText(icon_path)
                else:
                    if icon_path not in self._icon_cache:
                        self._icon_cache[icon_path] = QIcon(icon_path)
                    icon_btn.setIcon(self._icon_cache[icon_path])
                    icon_btn.setIconSize(QSize(32, 32))
            else:
                icon_btn.setText("❓")
            
            icon_btn.clicked.connect(lambda ch, btn=icon_btn: self._on_icon_btn_clicked(btn))
            icon_layout.addWidget(icon_btn, alignment=Qt.AlignmentFlag.AlignCenter)
            self.table.setCellWidget(row, 1, icon_widget)
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
            # Use star emoji or icon
            fav_cb.setText("★" if is_fav else "☆")
            fav_cb.setStyleSheet(f"color: {'#f1c40f' if is_fav else '#888'}; border: none; font-size: 18px;")
            fav_cb.toggled.connect(lambda checked, btn=fav_cb: [
                btn.setText("★" if checked else "☆"),
                btn.setStyleSheet(f"color: {'#f1c40f' if checked else '#888'}; border: none; font-size: 18px;")
            ])
            fav_cb.toggled.connect(lambda checked, r=row: self._on_fav_toggled(r, checked))
            # Store original value for change detection
            item['_orig_fav'] = is_fav
            fav_cb.setProperty("is_fav_editor", True)
            
            fav_layout.addWidget(fav_cb)
            
            
            # Sort item for Favorite column (2)
            fav_sort_item = SortableTableWidgetItem(1 if is_fav else 0, "")
            self.table.setItem(row, 2, fav_sort_item)
            self.table.setCellWidget(row, 2, fav_widget)

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
            # Dark theme for SpinBox
            score_spin.setStyleSheet("""
                QSpinBox { background-color: #333; color: white; border: 1px solid #555; border-radius: 4px; }
                QSpinBox::up-button, QSpinBox::down-button { background-color: #444; width: 16px; }
                QSpinBox::up-button:hover, QSpinBox::down-button:hover { background-color: #555; }
            """)
            score_spin.valueChanged.connect(lambda val, r=row: self._on_score_changed(r, val))
            # Store original
            item['_orig_score'] = score_val
            score_spin.setProperty("is_score_editor", True)
            
            score_layout.addWidget(score_spin)
            
            # Sort item for Score column (3)
            score_sort_item = SortableTableWidgetItem(score_val, "")
            self.table.setItem(row, 3, score_sort_item)
            self.table.setCellWidget(row, 3, score_widget)

            # 4. Folder Name (Read-only context) - Col 4
            folder_name = os.path.basename(item.get('rel_path'))
            # Use Item directly to avoid shadow/double-text issues
            # We used SortableTableWidgetItem or just QTableWidgetItem
            folder_item = QTableWidgetItem(folder_name)
            folder_item.setForeground(QColor("#bbbbbb")) # Grayish text
            # folder_item.setBackground(QColor("transparent"))
            # Make it italic?
            font = folder_item.font()
            font.setItalic(True)
            folder_item.setFont(font)
            self.table.setItem(row, 4, folder_item)
            
            # 5. Display Name (Editable) - Col 5
            t_name_start = time.perf_counter()
            name_edit = QuickEdit(item.get('display_name') or "")
            name_edit.setPlaceholderText(folder_name)
            # Styling input
            name_edit.setStyleSheet("color: #ffffff; background-color: #4a4a4a; border: 1px solid #555; padding: 4px; border-radius: 4px;")
            self.table.setCellWidget(row, 5, name_edit)
            # Sort item uses empty text to avoid shadow, but SortableTableWidgetItem uses internal value
            sort_name = (item.get('display_name') or folder_name).lower()
            name_sort_item = SortableTableWidgetItem(sort_name, "") # Empty display text!
            self.table.setItem(row, 5, name_sort_item) 
            t_name_total += time.perf_counter() - t_name_start
            
            # 6+. Tags/Separator Columns
            t_tag_start = time.perf_counter()
            # Current tags set
            current_tags = {t.strip().lower() for t in (item.get('tags') or "").split(",") if t.strip()}
            
            for i, col_info in enumerate(self._all_tag_columns):
                col_idx = 6 + i
                
                if col_info['type'] == 'sep':
                    # Separator column - just a vertical line
                    sep_label = QLabel("|")
                    sep_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    sep_label.setStyleSheet("color: #666; font-weight: bold;")
                    self.table.setCellWidget(row, col_idx, sep_label)
                    # No sort item for separators
                else:
                    tag_info = col_info['tag_info']
                    tag_name = tag_info.get('name', '')
                    lower_name = tag_name.lower()
                    is_active = lower_name in current_tags
                    
                    # Get display mode and content
                    mode = tag_info.get('display_mode', 'text')
                    emoji = tag_info.get('emoji', '')
                    display_name = tag_info.get('display', tag_name)
                    icon_path = tag_info.get('icon', '')
                    
                    # Create toggle button with tag content
                    tag_btn = QPushButton()
                    tag_btn.setCheckable(True)
                    tag_btn.setChecked(is_active)
                    tag_btn.setFixedSize(26, 26)  # Compact button size
                    
                    # Set button content based on display_mode
                    if mode == 'image' and icon_path and os.path.exists(icon_path):
                        # Show icon
                        if icon_path not in self._icon_cache:
                            self._icon_cache[icon_path] = QIcon(icon_path)
                        tag_btn.setIcon(self._icon_cache[icon_path])
                        tag_btn.setIconSize(QSize(22, 22))  # Fill button
                    elif mode == 'symbol' and emoji:
                        tag_btn.setText(emoji)
                    elif mode == 'text_symbol' and emoji:
                        tag_btn.setText(emoji)
                    else:  # text fallback
                        tag_btn.setText(display_name[:2])  # First 2 chars
                    
                    # Styling with hover effect
                    self._update_tag_btn_style(tag_btn, is_active)
                    
                    tag_btn.toggled.connect(lambda ch, btn=tag_btn, nm=lower_name, r=row: self._on_tag_toggled(r, nm, ch, btn))
                    
                    # Layout container for centering
                    tag_widget = QWidget()
                    tag_layout = QHBoxLayout(tag_widget)
                    tag_layout.setContentsMargins(0,0,0,0)
                    tag_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    tag_layout.addWidget(tag_btn)
                    
                    self.table.setCellWidget(row, col_idx, tag_widget)
                    
                    # Sort Item (1 or 0)
                    tag_sort_item = SortableTableWidgetItem(1 if is_active else 0, "")
                    self.table.setItem(row, col_idx, tag_sort_item)

            t_tag_total += time.perf_counter() - t_tag_start
            
            self.table.setRowHeight(row, 44)
            t_row_total += time.perf_counter() - t_row_start

        chunk_time = time.perf_counter() - chunk_start
        self._last_chunk_end_time = time.perf_counter()
        logging.info(f"[QuickViewProfile] Chunk {start}-{end}: {chunk_time:.3f}s (Icon: {t_icon_total:.3f}s, Name: {t_name_total:.3f}s, Tags: {t_tag_total:.3f}s)")

        self.current_load_row = end
        if self.current_load_row < len(self.items_data):
            QTimer.singleShot(0, self._load_next_chunk) # Next tick (0ms)
        else:
            elapsed = time.perf_counter() - self._profile_start_time
            logging.info(f"[QuickViewProfile] Finished loading. Total time: {elapsed:.3f}s")
            self.table.setSortingEnabled(True) # Re-enable sorting
            logging.info(f"[QuickViewProfile] >> Gap/Wait time: {self._total_gap_time:.3f}s")
            logging.info(f"[QuickViewProfile] >> Tag rendering (sync): {self._total_tag_creation_time:.3f}s")
    
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

    def _on_fav_toggled(self, row, checked):
        # Update sort item (Col 2) - Must update _sort_value for correct sorting!
        sort_item = self.table.item(row, 2)
        if sort_item:
            # Update _sort_value directly (used by SortableTableWidgetItem.__lt__)
            sort_item._sort_value = 1 if checked else 0
            # Re-sort if sorting is enabled and sort column is this one
            if self.table.isSortingEnabled() and self.table.horizontalHeader().sortIndicatorSection() == 2:
                self.table.sortItems(2, self.table.horizontalHeader().sortIndicatorOrder())

    def _on_score_changed(self, row, val):
        # Value comes from SpinBox as int (Col 3)
        sort_item = self.table.item(row, 3)
        if sort_item:
            # Update _sort_value directly
            sort_item._sort_value = val
            # Re-sort if needed
            if self.table.isSortingEnabled() and self.table.horizontalHeader().sortIndicatorSection() == 3:
                self.table.sortItems(3, self.table.horizontalHeader().sortIndicatorOrder())

    def _on_save_clicked(self):
        # Gather data from table
        update_list = []
        for row in range(self.table.rowCount()):
            item_data = self.items_data[row]
            rel_path = item_data.get('rel_path')
            
            changes = {}
            
            # Check icon (Col 1)
            icon_widget = self.table.cellWidget(row, 1)
            if icon_widget:
                icon_btn = icon_widget.findChild(QPushButton)
                new_icon = icon_btn.property("new_icon")
                if new_icon:
                    changes['image_path'] = new_icon

            # Check favorite (Column 2)
            fav_widget = self.table.cellWidget(row, 2)
            if fav_widget:
                for child in fav_widget.children():
                     if isinstance(child, QPushButton) and child.property("is_fav_editor"):
                         is_fav = child.isChecked()
                         if is_fav != item_data.get('_orig_fav', False):
                             changes['is_favorite'] = is_fav
                         break
            
            # Check score (Column 3)
            score_widget = self.table.cellWidget(row, 3)
            if score_widget:
                for child in score_widget.children():
                    if isinstance(child, QSpinBox) and child.property("is_score_editor"):
                        sc = child.value()
                        if sc != item_data.get('_orig_score', 0):
                            changes['score'] = sc
                        break

            # Check display name (Column 5)
            name_widget = self.table.cellWidget(row, 5)
            if isinstance(name_widget, QLineEdit):
                name_text = name_widget.text().strip()
                if name_text != (item_data.get('display_name') or ""):
                    changes['display_name'] = name_text
            
            # Check tags (Pending changes)
            if row in self._pending_tag_changes:
                row_changes = self._pending_tag_changes[row]
                if row_changes:
                    # Reconstruct tags string
                    original_tags_set = {t.strip().lower() for t in (item_data.get('tags') or "").split(",") if t.strip()}
                    
                    # Apply changes
                    final_tags_set = set(original_tags_set)
                    for tag, state in row_changes.items():
                        if state:
                            final_tags_set.add(tag)
                        else:
                            final_tags_set.discard(tag)
                    
                    # Sort and join
                    # Preserving case is hard since we only have lower names here, 
                    # but typically tags are case-insensitive or we can recover case from frequent_tags
                    # For now just join them.
                    new_tags_str = ",".join(sorted(list(final_tags_set)))
                    
                    if new_tags_str != item_data.get('tags', ''):
                        changes['tags'] = new_tags_str

            if changes:
                changes['rel_path'] = rel_path
                update_list.append(changes)
        
        if update_list:
            if self.db:
                try:
                    success = self.db.bulk_update_items(update_list) # Assume this exists or db.update_item loop
                    if success:
                        # Custom styled message box
                        msg = QMessageBox(self)
                        msg.setWindowTitle(_("Success"))
                        msg.setText(_(f"Updated {len(update_list)} items successfully."))
                        msg.setIcon(QMessageBox.Icon.Information)
                        # Apply dark theme style to message box
                        msg.setStyleSheet("""
                            QMessageBox { background-color: #353535; color: #ffffff; }
                            QLabel { color: #ffffff; }
                            QPushButton { background-color: #3498db; color: white; padding: 6px 16px; border-radius: 4px; }
                            QPushButton:hover { background-color: #2980b9; }
                        """)
                        msg.exec()
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
