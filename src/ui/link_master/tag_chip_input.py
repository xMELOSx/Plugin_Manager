from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QLineEdit, QCompleter, QScrollArea, QMenu, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QGuiApplication
from src.ui.flow_layout import FlowLayout
from src.ui.common_widgets import StyledLineEdit

class TagItem(QLabel):
    """A simplified tag item that looks like text and is clickable to delete."""
    clicked = pyqtSignal()
    
    def __init__(self, tag, parent=None):
        super().__init__(parent)
        self.tag_name = tag
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setTextFormat(Qt.TextFormat.RichText)
        self._update_text(hover=False)
        # Strictly text-like: no border, no background, minimal padding
        self.setStyleSheet("font-size: 11px; padding: 0px 0px; background: transparent; border: none;")
        self.setMinimumSize(self.sizeHint())
        
    def _update_text(self, hover=False):
        color = "#e74c3c" if hover else "#3498db"
        decoration = "text-decoration: underline;" if hover else ""
        # Comma is NO LONGER inside TagItem to allow separate management: 「カンマはそれ単体で間に入るようにして」
        self.setText(f"<span style='color: {color}; {decoration}'>{self.tag_name}</span>")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            
    def enterEvent(self, event):
        self._update_text(hover=True)
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self._update_text(hover=False)
        super().leaveEvent(event)

class TagChipInput(QWidget):
    """
    A tag input widget that displays tags as text items below the input field.
    Tags can be added via Enter and removed by clicking or pressing Backspace in an empty input.
    """
    tags_changed = pyqtSignal(list)
    
    def __init__(self, parent=None, placeholder="", suggestions=None, quick_tags=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2)
        
        # Input field on TOP for alignment with FormLayout labels
        self.line_edit = StyledLineEdit()
        self.line_edit.setPlaceholderText(placeholder)
        self.layout.addWidget(self.line_edit)
        
        # Display field (ScrollArea) for wrapping behavior
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setMaximumHeight(80) # Limit growth
        self.scroll_area.setStyleSheet("background-color: #1a1a1a; border-radius: 4px; border: 1px solid #333;")
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        self.chip_panel = QWidget()
        self.chip_panel.setStyleSheet("background-color: transparent;")
        self.chip_layout = FlowLayout(self.chip_panel)
        # Tight layout as requested
        self.chip_layout.setContentsMargins(4, 2, 4, 4)
        self.chip_layout.setSpacing(0) 
        
        self.scroll_area.setWidget(self.chip_panel)
        self.layout.addWidget(self.scroll_area)
        
        self.tags = []
        self.suggestions = suggestions or []
        self.quick_tags = [qt.lower() for qt in (quick_tags or [])]
        
        self.line_edit.returnPressed.connect(self._on_enter)
        self.line_edit.installEventFilter(self)
        
        # Right-click context menu for the panel
        self.chip_panel.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.chip_panel.customContextMenuRequested.connect(self._show_context_menu)
        
        self._update_completer()

    def _show_context_menu(self, pos):
        if not self.tags: return
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #2c2c2c; color: #eee; border: 1px solid #555; }
            QMenu::item:selected { background-color: #3498db; }
        """)
        
        from src.core.lang_manager import _
        copy_action = QAction(_("📋 Copy All Tags (CSV)"), self)
        copy_action.triggered.connect(self._copy_all_tags)
        menu.addAction(copy_action)
        
        menu.exec(self.chip_panel.mapToGlobal(pos))

    def _copy_all_tags(self):
        if self.tags:
            csv_text = ", ".join(self.tags)
            QGuiApplication.clipboard().setText(csv_text)

    def eventFilter(self, obj, event):
        if obj == self.line_edit and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Backspace and not self.line_edit.text() and self.tags:
                self._remove_last_tag()
                return True
        return super().eventFilter(obj, event)

    def _on_enter(self):
        text = self.line_edit.text().strip()
        if text:
            # Handle comma-separated input (useful for pasting)
            new_tags = [t.strip() for t in text.split(',') if t.strip()]
            for tag in new_tags:
                self.add_tag(tag)
            self.line_edit.clear()

    def add_tag(self, tag, update=True):
        tag_lower = tag.strip().lower()
        if not tag_lower:
            return
            
        if tag_lower not in [t.lower() for t in self.tags]:
            # If not initial, add a comma separator first
            if self.tags:
                comma = QLabel(",")
                comma.setObjectName("commaSeparator")
                comma.setStyleSheet("color: white; font-size: 11px; padding: 0px 3px 0px 1px; background: transparent; border: none;")
                self.chip_layout.addWidget(comma)
                comma.show()

            tag_name = tag.strip()
            self.tags.append(tag_name)
            self._create_tag_item(tag_name)
            self.tags_changed.emit(self.tags)
            
            if update:
                self.update_layout()

    def update_layout(self):
        """Force layout recalculation and panel refresh."""
        self.chip_layout.activate()
        self.chip_panel.adjustSize()
        self.chip_panel.update()
        self.updateGeometry()

    def _create_tag_item(self, tag):
        item = TagItem(tag, self.chip_panel)
        item.clicked.connect(lambda: self.remove_tag(tag))
        item.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        item.customContextMenuRequested.connect(lambda pos: self._show_context_menu(item.mapToParent(pos)))
        
        item.show()
        self.chip_layout.addWidget(item)

    def remove_tag(self, tag):
        tag_lower = tag.lower()
        target_idx = -1
        for i, t in enumerate(self.tags):
            if t.lower() == tag_lower:
                target_idx = i
                break
                
        if target_idx != -1:
            actual_tag = self.tags.pop(target_idx)
            
            # Find the widget and its associated comma
            # Comma removal strategy: 
            # If it's NOT the first tag, it had a comma BEFORE it.
            # If it IS the first tag but there are more, the following comma should be removed.
            
            widgets_to_remove = []
            tag_widget_idx = -1
            
            # Pass 1: Find the TagItem index in the layout
            for i in range(self.chip_layout.count()):
                w = self.chip_layout.itemAt(i).widget()
                if isinstance(w, TagItem) and w.tag_name == actual_tag:
                    tag_widget_idx = i
                    widgets_to_remove.append(w)
                    break
            
            if tag_widget_idx != -1:
                # Pass 2: Identify associated comma
                if tag_widget_idx > 0:
                    # Comma is likely the previous widget
                    prev_w = self.chip_layout.itemAt(tag_widget_idx - 1).widget()
                    if prev_w and prev_w.objectName() == "commaSeparator":
                        widgets_to_remove.append(prev_w)
                elif tag_widget_idx == 0 and self.chip_layout.count() > 1:
                    # Comma is the next widget
                    next_w = self.chip_layout.itemAt(1).widget()
                    if next_w and next_w.objectName() == "commaSeparator":
                        widgets_to_remove.append(next_w)
                
                # Perform removal
                for w in widgets_to_remove:
                    # Need to find index again as it changes
                    for i in range(self.chip_layout.count()):
                        if self.chip_layout.itemAt(i).widget() == w:
                            self.chip_layout.takeAt(i)
                            break
                    w.deleteLater()
            
            self.tags_changed.emit(self.tags)
            self.update_layout()

    def _remove_last_tag(self):
        if self.tags:
            self.remove_tag(self.tags[-1])

    def get_tags(self):
        return self.tags

    def set_tags(self, tags):
        # Clear existing
        while self.chip_layout.count():
            layout_item = self.chip_layout.takeAt(0)
            if layout_item and layout_item.widget():
                layout_item.widget().deleteLater()
        self.tags = []
        
        # Add new
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(',') if t.strip()]
            
        for t in tags:
            self.add_tag(t, update=False)
            
        # Robust update for initial display: force layout after all items are added
        QTimer.singleShot(10, self.update_layout)

    def _update_completer(self):
        filtered = [s for s in self.suggestions if s.lower() not in self.quick_tags]
        completer = QCompleter(filtered)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        
        popup = completer.popup()
        popup.setStyleSheet("""
            QAbstractItemView {
                background-color: #2c2c2c;
                color: #eeeeee;
                border: 1px solid #555;
                selection-background-color: #3498db;
            }
        """)
        
        self.line_edit.setCompleter(completer)

    def set_suggestions(self, suggestions):
        self.suggestions = suggestions
        self._update_completer()

    def set_quick_tags(self, quick_tags):
        self.quick_tags = [qt.lower() for qt in (quick_tags or [])]
        self._update_completer()
