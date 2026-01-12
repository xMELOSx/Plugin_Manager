from PyQt6.QtWidgets import QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPushButton, QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, QPoint, QSize
from PyQt6.QtGui import QPainter, QPolygon, QBrush, QColor, QIcon
from src.ui.frameless_window import FramelessDialog
from src.ui.title_bar_button import TitleBarButton
from src.core.lang_manager import _

def _draw_spinbox_arrows(painter, rect):
    """Common logic for drawing up/down arrows in spinboxes."""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # Position/Size Constants (Tailored for SpinBox buttons)
    # Width: 20px (from stylesheet)
    btn_center_x = rect.width() - 10
    btn_height = rect.height() // 2
    
    # Color: White arrow
    painter.setPen(Qt.GlobalColor.transparent)
    painter.setBrush(QBrush(QColor("#ffffff")))
    
    # Draw Up Arrow
    up_y_center = btn_height // 2
    up_points = [
        QPoint(btn_center_x - 4, up_y_center + 2),
        QPoint(btn_center_x + 4, up_y_center + 2),
        QPoint(btn_center_x, up_y_center - 3)
    ]
    painter.drawPolygon(QPolygon(up_points))
    
    # Draw Down Arrow
    down_y_center = rect.height() - (btn_height // 2)
    down_points = [
        QPoint(btn_center_x - 4, down_y_center - 2),
        QPoint(btn_center_x + 4, down_y_center - 2),
        QPoint(btn_center_x, down_y_center + 3)
    ]
    painter.drawPolygon(QPolygon(down_points))

class StyledLineEdit(QLineEdit):
    """Standardized QLineEdit with project dark theme."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QLineEdit {
                background-color: #3b3b3b;
                color: #ffffff;
                border: 1px solid #555;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QLineEdit:hover {
                border-color: #3498db;
            }
            QLineEdit:focus {
                border-color: #3498db;
                background-color: #444;
            }
        """)

class ProtectedLineEdit(StyledLineEdit):
    """
    StyledLineEdit that prevents startup right-click selection 
    and forces a dark theme on its context menu.
    """
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            # Show context menu directly instead of blocking the event
            # This prevents selection changes while still showing the menu
            self.showDarkContextMenu(event.globalPosition().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def showDarkContextMenu(self, pos):
        """Show custom dark-themed context menu with Japanese translations."""
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QPalette, QColor, QAction
        from src.core.lang_manager import _
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                color: #eeeeee;
                border: 1px solid #555555;
            }
            QMenu::item {
                background-color: transparent;
                padding: 4px 20px;
            }
            QMenu::item:selected {
                background-color: #3d5a80;
                color: #ffffff;
            }
            QMenu::item:disabled {
                color: #666666;
            }
        """)
        
        # Create translated actions
        undo_action = menu.addAction(_("元に戻す"))
        undo_action.triggered.connect(self.undo)
        undo_action.setEnabled(self.isUndoAvailable())
        
        redo_action = menu.addAction(_("やり直し"))
        redo_action.triggered.connect(self.redo)
        redo_action.setEnabled(self.isRedoAvailable())
        
        menu.addSeparator()
        
        cut_action = menu.addAction(_("切り取り"))
        cut_action.triggered.connect(self.cut)
        cut_action.setEnabled(self.hasSelectedText())
        
        copy_action = menu.addAction(_("コピー"))
        copy_action.triggered.connect(self.copy)
        copy_action.setEnabled(self.hasSelectedText())
        
        paste_action = menu.addAction(_("貼り付け"))
        paste_action.triggered.connect(self.paste)
        
        delete_action = menu.addAction(_("削除"))
        delete_action.triggered.connect(lambda: self.insert(""))
        delete_action.setEnabled(self.hasSelectedText())
        
        menu.addSeparator()
        
        select_all_action = menu.addAction(_("すべて選択"))
        select_all_action.triggered.connect(self.selectAll)
        select_all_action.setEnabled(len(self.text()) > 0)
        
        # Apply dark palette
        palette = menu.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#2b2b2b"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#eeeeee"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#2b2b2b"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#eeeeee"))
        menu.setPalette(palette)
        
        menu.exec(pos)

    def contextMenuEvent(self, event):
        # Override to use our custom dark context menu
        self.showDarkContextMenu(event.globalPos())



class StyledComboBox(QComboBox):
    """Premium QComboBox with a dedicated dropdown indicator area."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QComboBox {
                background-color: #3b3b3b;
                color: #ffffff;
                border: 1px solid #555;
                padding: 3px 25px 3px 6px;
                border-radius: 4px;
            }
            QComboBox:hover {
                border-color: #3498db;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 18px;
                background-color: #333;
                border: none;
                border-left: 1px solid #555;
            }
            QComboBox::down-arrow {
                image: none;
                border: none; /* Clear global CSS triangle */
                background: none;
            }
            /* Styling the internal list view */
            QComboBox QAbstractItemView {
                background-color: #3b3b3b;
                color: #ffffff;
                selection-background-color: #2980b9;
                selection-color: #ffffff;
                border: 1px solid #555;
                outline: none;
            }
        """)
    
    def paintEvent(self, event):
        """Override paintEvent to draw a custom triangle manually since QSS image is tricky."""
        super().paintEvent(event)
        from PyQt6.QtGui import QPainter, QPolygon, QBrush, QColor
        from PyQt6.QtCore import QPoint
        
        painter = QPainter(self)
        # Avoid drawing arrow if widget is too small
        if self.width() < 30:
            painter.end()
            return
            
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Calculate triangle position
        rect = self.rect()
        arrow_x = rect.width() - 9
        arrow_y = rect.height() // 2 + 1
        
        # Draw small triangle
        points = [
            QPoint(arrow_x - 4, arrow_y - 2),
            QPoint(arrow_x + 4, arrow_y - 2),
            QPoint(arrow_x, arrow_y + 3)
        ]
        
        painter.setPen(Qt.GlobalColor.transparent)
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawPolygon(QPolygon(points))
        painter.end()

class StyledSpinBox(QSpinBox):
    """Standardized QSpinBox with project dark theme."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QSpinBox {
                background-color: #3b3b3b;
                color: #ffffff;
                border: 1px solid #555;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QSpinBox:hover {
                border-color: #3498db;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #333;
                border-left: 1px solid #555;
                width: 20px;
            }
            QSpinBox::up-button { border-top-right-radius: 4px; }
            QSpinBox::down-button { border-bottom-right-radius: 4px; }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #444;
            }
            QSpinBox::up-arrow, QDoubleSpinBox::up-arrow { image: none; background: transparent; }
            QSpinBox::down-arrow, QDoubleSpinBox::down-arrow { image: none; background: transparent; }
        """)

    def paintEvent(self, event):
        """Draw custom arrows if buttons are visible."""
        super().paintEvent(event)
        # ONLY draw arrows if not hidden (Fix for overlap in Card Settings)
        if self.buttonSymbols() != QSpinBox.ButtonSymbols.NoButtons:
            painter = QPainter(self)
            _draw_spinbox_arrows(painter, self.rect())
            painter.end()


    def mousePressEvent(self, event):
        """Handle right-click to show dark context menu."""
        if event.button() == Qt.MouseButton.RightButton:
            self._showDarkContextMenu(event.globalPosition().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def _showDarkContextMenu(self, pos):
        """Show custom dark-themed context menu with Japanese translations."""
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QPalette, QColor
        from src.core.lang_manager import _
        
        line_edit = self.lineEdit()
        if not line_edit:
            return
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                color: #eeeeee;
                border: 1px solid #555555;
            }
            QMenu::item {
                background-color: transparent;
                padding: 4px 20px;
            }
            QMenu::item:selected {
                background-color: #3d5a80;
                color: #ffffff;
            }
            QMenu::item:disabled {
                color: #666666;
            }
        """)
        
        # Create translated actions
        undo_action = menu.addAction(_("元に戻す"))
        undo_action.triggered.connect(line_edit.undo)
        undo_action.setEnabled(line_edit.isUndoAvailable())
        
        redo_action = menu.addAction(_("やり直し"))
        redo_action.triggered.connect(line_edit.redo)
        redo_action.setEnabled(line_edit.isRedoAvailable())
        
        menu.addSeparator()
        
        cut_action = menu.addAction(_("切り取り"))
        cut_action.triggered.connect(line_edit.cut)
        cut_action.setEnabled(line_edit.hasSelectedText())
        
        copy_action = menu.addAction(_("コピー"))
        copy_action.triggered.connect(line_edit.copy)
        copy_action.setEnabled(line_edit.hasSelectedText())
        
        paste_action = menu.addAction(_("貼り付け"))
        paste_action.triggered.connect(line_edit.paste)
        
        delete_action = menu.addAction(_("削除"))
        delete_action.triggered.connect(lambda: line_edit.insert(""))
        delete_action.setEnabled(line_edit.hasSelectedText())
        
        menu.addSeparator()
        
        select_all_action = menu.addAction(_("すべて選択"))
        select_all_action.triggered.connect(line_edit.selectAll)
        select_all_action.setEnabled(len(line_edit.text()) > 0)
        
        # Apply dark palette
        palette = menu.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#2b2b2b"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#eeeeee"))
        menu.setPalette(palette)
        
        menu.exec(pos)


class StyledDoubleSpinBox(QDoubleSpinBox):
    """Standardized QDoubleSpinBox with project dark theme."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #3b3b3b;
                color: #ffffff;
                border: 1px solid #555;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QDoubleSpinBox:hover {
                border-color: #3498db;
            }
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                background-color: #333;
                border-left: 1px solid #555;
                width: 20px;
            }
            QDoubleSpinBox::up-button { border-top-right-radius: 4px; }
            QDoubleSpinBox::down-button { border-bottom-right-radius: 4px; }
            QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
                background-color: #444;
            }
            QDoubleSpinBox::up-arrow, QDoubleSpinBox::down-arrow { image: none; background: transparent; }
        """)

    def paintEvent(self, event):
        """Draw custom arrows if buttons are visible."""
        super().paintEvent(event)
        # ONLY draw arrows if not hidden (Fix for overlap in Card Settings)
        if self.buttonSymbols() != QSpinBox.ButtonSymbols.NoButtons:
            painter = QPainter(self)
            _draw_spinbox_arrows(painter, self.rect())
            painter.end()

    def mousePressEvent(self, event):
        """Handle right-click to show dark context menu."""
        if event.button() == Qt.MouseButton.RightButton:
            self._showDarkContextMenu(event.globalPosition().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def _showDarkContextMenu(self, pos):
        """Show custom dark-themed context menu with Japanese translations."""
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QPalette, QColor
        from src.core.lang_manager import _
        
        line_edit = self.lineEdit()
        if not line_edit:
            return
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                color: #eeeeee;
                border: 1px solid #555555;
            }
            QMenu::item {
                background-color: transparent;
                padding: 4px 20px;
            }
            QMenu::item:selected {
                background-color: #3d5a80;
                color: #ffffff;
            }
            QMenu::item:disabled {
                color: #666666;
            }
        """)
        
        # Create translated actions
        undo_action = menu.addAction(_("元に戻す"))
        undo_action.triggered.connect(line_edit.undo)
        undo_action.setEnabled(line_edit.isUndoAvailable())
        
        redo_action = menu.addAction(_("やり直し"))
        redo_action.triggered.connect(line_edit.redo)
        redo_action.setEnabled(line_edit.isRedoAvailable())
        
        menu.addSeparator()
        
        cut_action = menu.addAction(_("切り取り"))
        cut_action.triggered.connect(line_edit.cut)
        cut_action.setEnabled(line_edit.hasSelectedText())
        
        copy_action = menu.addAction(_("コピー"))
        copy_action.triggered.connect(line_edit.copy)
        copy_action.setEnabled(line_edit.hasSelectedText())
        
        paste_action = menu.addAction(_("貼り付け"))
        paste_action.triggered.connect(line_edit.paste)
        
        delete_action = menu.addAction(_("削除"))
        delete_action.triggered.connect(lambda: line_edit.insert(""))
        delete_action.setEnabled(line_edit.hasSelectedText())
        
        menu.addSeparator()
        
        select_all_action = menu.addAction(_("すべて選択"))
        select_all_action.triggered.connect(line_edit.selectAll)
        select_all_action.setEnabled(len(line_edit.text()) > 0)
        
        # Apply dark palette
        palette = menu.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#2b2b2b"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#eeeeee"))
        menu.setPalette(palette)
        
        menu.exec(pos)


class StyledButton(QPushButton):
    """
    Standardized QPushButton with premium hover effects and pointing hand cursor.
    Supports 'Gray', 'Blue', 'Green' style presets.
    """
    def __init__(self, text, parent=None, style_type="Gray"):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.style_type = style_type
        self._apply_style()

    def _apply_style(self):
        # Color Map
        colors = {
            "Gray":  {"bg": "#3b3b3b", "hover": "#4a4a4a", "border": "#555", "hover_border": "#777"},
            "Blue":  {"bg": "#2980b9", "hover": "#3498db", "border": "#3498db", "hover_border": "#fff"},
            "Green": {"bg": "#27ae60", "hover": "#2ecc71", "border": "#2ecc71", "hover_border": "#fff"},
            "Red":   {"bg": "#c0392b", "hover": "#e74c3c", "border": "#e74c3c", "hover_border": "#fff"}
        }
        
        c = colors.get(self.style_type, colors["Gray"])
        
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['bg']};
                color: #ffffff;
                border: 1px solid {c['border']};
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {c['hover']};
                border-color: {c['hover_border']};
            }}
            QPushButton:pressed {{
                background-color: #222;
                padding-top: 7px;
                padding-left: 13px;
            }}
            QPushButton:disabled {{
                background-color: #2c2c2c;
                color: #555;
                border-color: #333;
            }}
        """)

    def set_style_type(self, style_type: str):
        self.style_type = style_type
        self._apply_style()

class FramelessMessageBox(FramelessDialog):
    """
    Standardized Frameless Message Box to replace native QMessageBox.
    Uses Common Window styling (FramelessDialog).
    """
    class Icon:
        NoIcon = 0
        Information = 1
        Warning = 2
        Critical = 3
        Question = 4

    class StandardButton:
        NoButton = 0
        Ok = 1024
        Cancel = 4194304
        Yes = 16384
        No = 65536
        # Add others as needed

    def __init__(self, parent=None):
        super().__init__(parent)
        self.resize(400, 200)
        self.set_resizable(False)
        self._setup_ui()
        self.set_title_bar_icon_visible(True)
        self.set_default_icon()
        self._result = self.StandardButton.NoButton
        self._clicked_button = None
        
        # Play confirmation sound
        try:
            from PyQt6.QtCore import QUrl
            from PyQt6.QtMultimedia import QSoundEffect
            import os
            # Assume sound is in src/resource/se relative to project root
            # We need to find the absolute path. Assuming standard project structure.
            # Using __file__ of common_widgets.py -> src/ui/common_widgets.py
            # ../../resource/se/confirmation.wav
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            sound_path = os.path.join(base_dir, "src", "resource", "se", "confirmation.wav")
            
            if os.path.exists(sound_path):
                self.effect = QSoundEffect()
                self.effect.setSource(QUrl.fromLocalFile(sound_path))
                self.effect.setVolume(0.5)
                self.effect.play()
        except: pass

    def _setup_ui(self):
        # Initial Setup is done by FramelessDialog._init_frameless_ui
        # We just populate the content area
        
        # Main Layout (HBox: Icon + VBox(Text + Buttons))
        self.msg_layout = QHBoxLayout()
        self.msg_layout.setContentsMargins(20, 20, 20, 20)
        self.msg_layout.setSpacing(15)
        
        # Icon Label
        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(48, 48)
        self.icon_lbl.setVisible(False)
        self.msg_layout.addWidget(self.icon_lbl, 0, Qt.AlignmentFlag.AlignTop)
        
        # Right Side (Text + Buttons)
        self.right_layout = QVBoxLayout()
        self.right_layout.setSpacing(20)
        
        self.text_lbl = QLabel()
        self.text_lbl.setWordWrap(True)
        self.text_lbl.setStyleSheet("color: #eeeeee; font-size: 13px;")
        self.text_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.text_lbl.setCursor(Qt.CursorShape.IBeamCursor)
        self.right_layout.addWidget(self.text_lbl)
        
        self.pixel_btn_layout = QHBoxLayout()
        self.pixel_btn_layout.setSpacing(10)
        self.pixel_btn_layout.addStretch()
        
        self.right_layout.addLayout(self.pixel_btn_layout)
        self.msg_layout.addLayout(self.right_layout)
        
        # Set content to FramelessDialog
        container = QWidget()
        container.setLayout(self.msg_layout)
        self.set_content_widget(container)

    def setIcon(self, icon_enum):
        from PyQt6.QtWidgets import QApplication, QStyle
        style = QApplication.style()
        icon = None
        if icon_enum == self.Icon.Information:
            icon = style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)
        elif icon_enum == self.Icon.Warning:
            icon = style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning)
        elif icon_enum == self.Icon.Critical:
            icon = style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxCritical)
        elif icon_enum == self.Icon.Question:
            icon = style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxQuestion)
            
        if icon:
            self.icon_lbl.setPixmap(icon.pixmap(48, 48))
            self.icon_lbl.setVisible(True)
        else:
            self.icon_lbl.setVisible(False)

    def setInformativeText(self, text):
        """Supported for compatibility, appends to main text with newline."""
        current = self.text_lbl.text()
        if current:
            self.text_lbl.setText(current + "\n\n" + text)
        else:
            self.text_lbl.setText(text)

    def setText(self, text):
        self.text_lbl.setText(text)

    def setStandardButtons(self, buttons):
        # Clear existing buttons
        while self.pixel_btn_layout.count() > 1: # Keep stretch
            item = self.pixel_btn_layout.takeAt(1)
            if item.widget(): item.widget().deleteLater()
            
        # Add Buttons based on flags (Simple implementation for common uses)
        if buttons & self.StandardButton.Ok:
            self._add_btn("OK", self.StandardButton.Ok, "Blue")
            
        if buttons & self.StandardButton.Yes:
            self._add_btn(_("Yes"), self.StandardButton.Yes, "Blue")
            
        if buttons & self.StandardButton.No:
            self._add_btn(_("No"), self.StandardButton.No, "Gray")
            
        if buttons & self.StandardButton.Cancel:
            self._add_btn(_("Cancel"), self.StandardButton.Cancel, "Gray")

    def addButton(self, text, code, style="Gray"):
        """Mimic QMessageBox.addButton to support custom buttons."""
        # Auto-detect style based on code if not provided
        if style == "Gray":
            if code in [self.StandardButton.Ok, self.StandardButton.Yes]:
                style = "Blue"
            elif code == self.StandardButton.NoButton: # Default to success if it's a primary action
                style = "Green"
        
        btn = StyledButton(text, style_type=style)
        btn.setMinimumWidth(100)
        btn.clicked.connect(lambda _, b=btn, c=code: self._done(c, b))
        self.pixel_btn_layout.addWidget(btn)
        return btn

    def _add_btn(self, text, code, style="Gray"):
        self.addButton(text, code, style)
        
    def setDefaultButton(self, code):
        # Optional: Set focus
        pass

    def _done(self, code, button=None):
        self._result = code
        self._clicked_button = button
        if code in [self.StandardButton.Ok, self.StandardButton.Yes]:
            self.accept()
        else:
            self.reject()

    def clickedButton(self):
        """Standard QMessageBox compatibility."""
        return self._clicked_button

    def exec(self):
        super().exec()
        return self._result

    @staticmethod
    def information(parent, title, text):
        dlg = FramelessMessageBox(parent)
        dlg.setWindowTitle(title)
        dlg.setText(text)
        dlg.setIcon(FramelessMessageBox.Icon.Information)
        dlg.setStandardButtons(FramelessMessageBox.StandardButton.Ok)
        return dlg.exec()

    @staticmethod
    def warning(parent, title, text):
        dlg = FramelessMessageBox(parent)
        dlg.setWindowTitle(title)
        dlg.setText(text)
        dlg.setIcon(FramelessMessageBox.Icon.Warning)
        dlg.setStandardButtons(FramelessMessageBox.StandardButton.Ok)
        return dlg.exec()

    @staticmethod
    def critical(parent, title, text):
        dlg = FramelessMessageBox(parent)
        dlg.setWindowTitle(title)
        dlg.setText(text)
        dlg.setIcon(FramelessMessageBox.Icon.Critical)
        dlg.setStandardButtons(FramelessMessageBox.StandardButton.Ok)
        return dlg.exec()

class FramelessInputDialog(FramelessDialog):
    """
    Standardized Frameless Input Dialog to replace QInputDialog.
    Supports text and integer inputs.
    """
    def __init__(self, parent=None, title="", label="", text="", value=0, min_val=0, max_val=100, is_int=False, items=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.set_resizable(False)
        self.set_default_icon()
        self._is_int = is_int
        self._items = items
        self._setup_ui(label, text, value, min_val, max_val)
        self.resize(350, 200)

    def _setup_ui(self, label, text, value, min_val, max_val):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        self.label = QLabel(label)
        self.label.setWordWrap(True)
        self.label.setStyleSheet("color: #eeeeee; font-size: 13px;")
        layout.addWidget(self.label)

        if self._items:
            self.input_field = StyledComboBox()
            for item in self._items:
                self.input_field.addItem(item)
            if text in self._items:
                self.input_field.setCurrentText(text)
            layout.addWidget(self.input_field)
        elif self._is_int:
            self.input_field = StyledSpinBox()
            self.input_field.setRange(min_val, max_val)
            self.input_field.setValue(value)
            self.input_field.setMinimumHeight(35)
            layout.addWidget(self.input_field)
        else:
            self.input_field = StyledLineEdit()
            self.input_field.setText(text)
            self.input_field.setMinimumHeight(35)
            self.input_field.returnPressed.connect(self.accept)
            layout.addWidget(self.input_field)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        self.ok_btn = StyledButton(_("OK"), style_type="Blue")
        self.ok_btn.setMinimumWidth(80)
        self.ok_btn.clicked.connect(self.accept)
        
        self.cancel_btn = StyledButton(_("Cancel"), style_type="Gray")
        self.cancel_btn.setMinimumWidth(80)
        self.cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.set_content_widget(content)

    def showEvent(self, event):
        super().showEvent(event)
        # Ensure we focus the input field after window is shown
        if hasattr(self, 'input_field'):
            self.input_field.setFocus()
            if isinstance(self.input_field, QLineEdit):
                self.input_field.selectAll()

    def value(self):
        if self._items:
            return self.input_field.currentText()
        if self._is_int:
            return self.input_field.value()
        return self.input_field.text()

    @staticmethod
    def getText(parent, title, label, text=""):
        dlg = FramelessInputDialog(parent, title, label, text=text)
        if dlg.exec():
            return dlg.value(), True
        return "", False

    @staticmethod
    def getInt(parent, title, label, value=0, min_val=0, max_val=100, step=1):
        dlg = FramelessInputDialog(parent, title, label, value=value, min_val=min_val, max_val=max_val, is_int=True)
        # step and other args can be added as needed
        if dlg.exec():
            return dlg.value(), True
        return value, False

    @staticmethod
    def getItem(parent, title, label, items, current=0, editable=False):
        dlg = FramelessInputDialog(parent, title, label, items=items, text=items[current] if items and current < len(items) else "")
        if dlg.exec():
            return dlg.value(), True
        return "", False
