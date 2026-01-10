""" 🚨 厳守ルール: ファイル操作禁止 🚨
ファイルI/Oは、必ず src.core.file_handler を経由すること。
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QCheckBox, QComboBox, QFrame, QSpinBox, QMessageBox, QSpacerItem, QSizePolicy)
from src.ui.common_widgets import StyledSpinBox
from PyQt6.QtCore import Qt, pyqtSignal
from src.ui.styles import apply_common_dialog_style

class ToolsPanel(QWidget):
    """
    Sidebar panel for special administrative actions (🔧).
    """
    request_reset_all = pyqtSignal()
    request_manual_rebuild = pyqtSignal()
    pool_size_changed = pyqtSignal(int)
    search_cache_toggled = pyqtSignal(bool)
    request_import = pyqtSignal()
    request_export = pyqtSignal()
    request_size_check = pyqtSignal()
    deploy_opacity_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        from src.core.lang_manager import _
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # Header (referenced in retranslate_ui)
        header_layout = QHBoxLayout()
        self.header_lbl = QLabel(_("<b>Special Tools</b>"))
        header_layout.addWidget(self.header_lbl)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Title (Old title retained for legacy search but hidden or secondary)
        self.title_lbl = QLabel(_("🔧 Special Actions"))
        self.title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #ddd;")
        self.title_lbl.hide() # We use header_lbl now
        layout.addWidget(self.title_lbl)
        
        line = QFrame(self)
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #444;")
        layout.addWidget(line)

        # 1. Manual Rebuild (First)
        rebuild_group = QWidget(self)
        rebuild_layout = QVBoxLayout(rebuild_group)
        rebuild_layout.setContentsMargins(0, 0, 0, 0)
        
        self.rebuild_label = QLabel(_("Manual Rebuild"))
        self.rebuild_label.setStyleSheet("color: #bbb; font-weight: bold;")
        rebuild_layout.addWidget(self.rebuild_label)
        
        self.rebuild_desc = QLabel(_("Clear cache and rescan all folders to ensure data integrity."))
        self.rebuild_desc.setWordWrap(True)
        self.rebuild_desc.setStyleSheet("color: #888; font-size: 11px;")
        rebuild_layout.addWidget(self.rebuild_desc)
        
        self.btn_rebuild = QPushButton(_("Run Manual Rebuild"))
        self.btn_rebuild.setStyleSheet("""
            QPushButton { 
                background-color: #2980b9; color: white; border-radius: 4px; padding: 6px; font-weight: bold;
            }
            QPushButton:hover { background-color: #3498db; }
        """)
        self.btn_rebuild.clicked.connect(self.request_manual_rebuild.emit)
        rebuild_layout.addWidget(self.btn_rebuild)
        
        layout.addWidget(rebuild_group)

        # 2. UI Optimization (Second)
        pool_group = QWidget(self)
        pool_layout = QVBoxLayout(pool_group)
        pool_layout.setContentsMargins(0, 0, 0, 0)
        
        self.pool_label = QLabel(_("UI Performance Settings"))
        self.pool_label.setStyleSheet("color: #bbb; font-weight: bold;")
        pool_layout.addWidget(self.pool_label)
        
        self.pool_desc = QLabel(_("Adjust widget pooling settings."))
        self.pool_desc.setStyleSheet("color: #888; font-size: 11px;")
        pool_layout.addWidget(self.pool_desc)

        # Max Pool Size
        size_layout = QHBoxLayout()
        self.size_lbl = QLabel(_("Pool Size:"))
        self.size_lbl.setStyleSheet("color: #ddd;")
        size_layout.addWidget(self.size_lbl)
        
        self.spin_pool_size = StyledSpinBox()
        self.spin_pool_size.setRange(50, 1000)
        self.spin_pool_size.setSingleStep(50)
        self.spin_pool_size.setStyleSheet("background-color: #333; color: white; border: 1px solid #555;")
        self.spin_pool_size.editingFinished.connect(lambda: self.pool_size_changed.emit(self.spin_pool_size.value()))
        size_layout.addWidget(self.spin_pool_size)
        pool_layout.addLayout(size_layout)
        
        # Search Cache
        self.chk_search_cache = QCheckBox(_("Enable Search Result Caching"))
        self.chk_search_cache.setStyleSheet("color: #ddd;")
        self.chk_search_cache.toggled.connect(self.search_cache_toggled.emit)
        pool_layout.addWidget(self.chk_search_cache)
        
        layout.addWidget(pool_group)
        
        # 3. Portability (Import/Export) - Third
        port_group = QWidget(self)
        port_layout = QVBoxLayout(port_group)
        port_layout.setContentsMargins(0, 0, 0, 0)
        
        self.port_label = QLabel(_("Import/Export (Portability)"))
        self.port_label.setStyleSheet("color: #bbb; font-weight: bold;")
        port_layout.addWidget(self.port_label)
        
        self.port_desc = QLabel(_("Export/Import current app settings and images as .dioco files."))
        self.port_desc.setStyleSheet("color: #888; font-size: 11px;")
        port_layout.addWidget(self.port_desc)
        
        port_btns = QHBoxLayout()
        self.btn_export = QPushButton(_("📤 Export"))
        self.btn_export.setStyleSheet("""
            QPushButton { background-color: #7f8c8d; color: white; border-radius: 4px; padding: 6px; font-weight: bold; }
            QPushButton:hover { background-color: #95a5a6; }
        """)
        self.btn_export.clicked.connect(self.request_export.emit)
        
        self.btn_import = QPushButton(_("📥 Import"))
        self.btn_import.setStyleSheet("""
            QPushButton { background-color: #16a085; color: white; border-radius: 4px; padding: 6px; font-weight: bold; }
            QPushButton:hover { background-color: #1abc9c; }
        """)
        self.btn_import.clicked.connect(self.request_import.emit)
        
        port_btns.addWidget(self.btn_export)
        port_btns.addWidget(self.btn_import)
        port_layout.addLayout(port_btns)
        
        layout.addWidget(port_group)
        
        # 3.5 Bulk Size Check (New Phase 30)
        line2 = QFrame(self)
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setFrameShadow(QFrame.Shadow.Sunken)
        line2.setStyleSheet("background-color: #444; margin-top: 5px;")
        layout.addWidget(line2)

        size_group = QWidget(self)
        size_layout = QVBoxLayout(size_group)
        size_layout.setContentsMargins(0, 5, 0, 0)

        size_layout.addSpacing(10)
        size_layout.addWidget(self._create_h_line())
        size_layout.addSpacing(10)

        # Level 30: Detailed Package Size Management Section
        self.size_header = QLabel(_("📦 Package Size Management"))
        self.size_header.setStyleSheet("color: #bbb; font-weight: bold; font-size: 13px;")
        size_layout.addWidget(self.size_header)

        self.size_desc = QLabel(_("Recalculate disk usage for all packages. Useful for verifying actual size when managing large mods."))
        self.size_desc.setWordWrap(True)
        self.size_desc.setStyleSheet("color: #888; font-size: 11px; margin-bottom: 5px;")
        size_layout.addWidget(self.size_desc)

        self.btn_check_sizes = QPushButton(_("Run All Size Checks"))
        self.btn_check_sizes.setFixedHeight(30)
        self.btn_check_sizes.setStyleSheet("""
            QPushButton {
                background-color: #2c3e50;
                color: #ecf0f1;
                border: 1px solid #34495e;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #34495e;
            }
            QPushButton:disabled {
                background-color: #222;
                color: #555;
            }
        """)
        self.btn_check_sizes.clicked.connect(self.request_size_check.emit)
        size_layout.addWidget(self.btn_check_sizes)
        
        self.lbl_last_size_check = QLabel(_("Last check: Not run"))
        self.lbl_last_size_check.setStyleSheet("color: #777; font-size: 10px; font-style: italic; margin-top: 2px;")
        size_layout.addWidget(self.lbl_last_size_check)

        layout.addWidget(size_group)

        # 3.8 UI Display Settings (Phase 2)
        ui_group = QWidget(self)
        ui_layout = QVBoxLayout(ui_group)
        ui_layout.setContentsMargins(0, 5, 0, 0)
        
        ui_layout.addWidget(self._create_h_line())
        ui_layout.addSpacing(5)
        
        self.ui_header = QLabel(_("🎨 Display Settings"))
        self.ui_header.setStyleSheet("color: #bbb; font-weight: bold; font-size: 13px;")
        ui_layout.addWidget(self.ui_header)

        opacity_layout = QHBoxLayout()
        self.opacity_lbl = QLabel(_("Deploy Button Opacity:"))
        self.opacity_lbl.setStyleSheet("color: #ddd; font-size: 11px;")
        opacity_layout.addWidget(self.opacity_lbl)
        
        from PyQt6.QtWidgets import QSlider
        self.slider_deploy_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_deploy_opacity.setRange(0, 100)
        self.slider_deploy_opacity.setValue(80) # Default 80%
        self.slider_deploy_opacity.setStyleSheet("""
            QSlider::groove:horizontal { background: #444; height: 4px; border-radius: 2px; }
            QSlider::handle:horizontal { background: #3498db; border: 1px solid #2980b9; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }
        """)
        self.slider_deploy_opacity.valueChanged.connect(self.deploy_opacity_changed.emit)
        opacity_layout.addWidget(self.slider_deploy_opacity)
        
        ui_layout.addLayout(opacity_layout)
        layout.addWidget(ui_group)

        # 4. Reset All Attributes (Last, with warning styling)
        reset_group = QWidget(self)
        reset_layout = QVBoxLayout(reset_group)
        reset_layout.setContentsMargins(0, 0, 0, 0)
        
        self.reset_label = QLabel(_("⚠ Reset All Folder Attributes"))
        self.reset_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
        reset_layout.addWidget(self.reset_label)
        
        self.reset_desc = QLabel(_("Bulk delete all folder settings (type, display, tags) for the current app and reset to initial state."))
        self.reset_desc.setWordWrap(True)
        self.reset_desc.setStyleSheet("color: #888; font-size: 11px;")
        reset_layout.addWidget(self.reset_desc)
        
        self.btn_reset = QPushButton(_("⚠ Reset All Attributes"))
        self.btn_reset.setMouseTracking(True)
        self.btn_reset.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.btn_reset.setStyleSheet("""
            QPushButton { 
                background-color: #c0392b; color: white; border-radius: 4px; padding: 6px; font-weight: bold; border: 1px solid #922B21;
            }
            QPushButton:hover { background-color: #e74c3c; border-color: #C0392B; }
        """)
        self.btn_reset.clicked.connect(self._on_reset_clicked)
        reset_layout.addWidget(self.btn_reset)
        
        layout.addWidget(reset_group)

        layout.addStretch()

    def retranslate_ui(self):
        """Update strings for current language."""
        from src.core.lang_manager import _
        self.header_lbl.setText(_("<b>Special Tools</b>"))
        self.title_lbl.setText(_("🔧 Special Actions"))
        
        self.rebuild_label.setText(_("Manual Rebuild"))
        self.rebuild_desc.setText(_("Clear cache and rescan all folders to ensure data integrity."))
        self.btn_rebuild.setText(_("Run Manual Rebuild"))
        
        self.pool_label.setText(_("UI Performance Settings"))
        self.pool_desc.setText(_("Adjust widget pooling settings."))
        self.size_lbl.setText(_("Pool Size:"))
        self.chk_search_cache.setText(_("Enable Search Result Caching"))
        
        self.port_label.setText(_("Import/Export (Portability)"))
        self.port_desc.setText(_("Export/Import current app settings and images as .dioco files."))
        self.btn_export.setText(_("📤 Export"))
        self.btn_import.setText(_("📥 Import"))
        
        self.size_header.setText(_("📦 Package Size Management"))
        self.size_desc.setText(_("Recalculate disk usage for all packages. Useful for verifying actual size when managing large mods."))
        self.btn_check_sizes.setText(_("Run All Size Checks"))
        # lbl_last_size_check is updated via set_last_check_time
        
        self.ui_header.setText(_("🎨 Display Settings"))
        self.opacity_lbl.setText(_("Deploy Button Opacity:"))
        
        self.reset_label.setText(_("⚠ Reset All Folder Attributes"))
        self.reset_desc.setText(_("Bulk delete all folder settings (type, display, tags) for the current app and reset to initial state."))
        self.btn_reset.setText(_("⚠ Reset All Attributes"))

    def set_last_check_time(self, time_str: str):
        """Update the label showing when the last size check was performed."""
        self.lbl_last_size_check.setText(_("Last check: {time}").format(time=time_str))

    def _create_h_line(self):
        """Helper to create a standard horizontal separator."""
        line = QFrame(self)
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #444; min-height: 1px; max-height: 1px;")
        return line

    def _on_reset_clicked(self):
        from src.core.lang_manager import _
        # Confirmation Dialog
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle(_("Confirm Bulk Reset"))
        msg.setText(_("⚠ Bulk delete all folder attributes for this app?"))
        msg.setInformativeText(
            _("・All folder types will return to default\n"
              "・All display settings and tags will be removed\n"
              "・This action cannot be undone.")
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        apply_common_dialog_style(msg)
        
        if msg.exec() == QMessageBox.StandardButton.Yes:
            self.request_reset_all.emit()
