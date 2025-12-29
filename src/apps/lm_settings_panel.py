"""
Link Master: Settings Panel Mixin
カードサイズ設定パネルのUIとロジック。

依存するコンポーネント:
- QFrame, QSlider, QSpinBox, QTabWidget等 (PyQt6)

依存する親クラスの属性:
- card_settings, cat_layout, pkg_layout
- cat_display_override, pkg_display_override
- display_mode_locked, btn_card_settings
- btn_cat_text, btn_cat_image, btn_cat_both
- btn_selected_style, btn_no_override_style
"""
import copy
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QSpinBox, QTabWidget, QWidget, QCheckBox
)
from PyQt6.QtCore import Qt


class LMSettingsPanelMixin:
    """カードサイズ設定パネルを担当するMixin。"""
    
    def _show_settings_menu(self):
        """Show/toggle settings panel with size sliders."""
        # Toggle existing panel
        if hasattr(self, '_settings_panel') and self._settings_panel.isVisible():
            self._settings_panel.hide()
            return
        
        # Create panel if not exists
        if not hasattr(self, '_settings_panel'):
            self._settings_panel = QFrame(self)
            self._settings_panel.setStyleSheet("""
                QFrame { background-color: #2b2b2b; border: 2px solid #555; border-radius: 8px; }
                QLabel { color: #ddd; padding: 2px; }
                QSlider::groove:horizontal { height: 8px; background: #444; border-radius: 4px; }
                QSlider::handle:horizontal { background: #3498db; width: 18px; height: 18px; margin: -5px 0; border-radius: 9px; }
                QTabWidget::pane { border: 1px solid #555; background: #333; }
                QTabBar::tab { background: #3a3a3a; color: #ddd; padding: 5px 10px; }
                QTabBar::tab:selected { background: #555; }
            """)
            
            layout = QVBoxLayout(self._settings_panel)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(2)

            # Header with buttons
            header = QHBoxLayout()
            header.setSpacing(5)
            header.addWidget(QLabel("<b>📓 Card Settings</b>"))
            header.addStretch()
            
            save_btn = QPushButton("保存")
            save_btn.setFixedWidth(50)
            save_btn.setStyleSheet("QPushButton { background-color: #27ae60; color: white; border-radius: 4px; padding: 2px; } QPushButton:hover { background-color: #2ecc71; border-color: #fff; }")
            save_btn.clicked.connect(self._settings_panel.hide)
            header.addWidget(save_btn)
            
            cancel_btn = QPushButton("戻す")
            cancel_btn.setFixedWidth(50)
            cancel_btn.setStyleSheet("QPushButton { background-color: #3b3b3b; color: white; border-radius: 4px; padding: 2px; border: 1px solid #555; } QPushButton:hover { background-color: #4a4a4a; border-color: #999; }")
            cancel_btn.clicked.connect(self._cancel_settings)
            header.addWidget(cancel_btn)
            
            close_btn = QPushButton("✕")
            close_btn.setFixedSize(20, 20)
            close_btn.setStyleSheet("QPushButton { border: none; color: #888; } QPushButton:hover { color: #fff; }")
            close_btn.clicked.connect(self._cancel_settings)
            header.addWidget(close_btn)
            layout.addLayout(header)
            
            # Lock View Mode Option
            self._lock_check = QCheckBox("表示モードを固定 (保持) する")
            self._lock_check.setStyleSheet("QCheckBox { color: #ddd; padding: 5px; font-size: 11px; }")
            self._lock_check.setChecked(self.display_mode_locked)
            self._lock_check.toggled.connect(self._on_display_lock_toggled)
            layout.addWidget(self._lock_check)

            # Tab widget for display modes
            self._settings_tabs = QTabWidget()
            self._settings_tabs.setFixedWidth(330)
            
            # Create tabs for each display mode
            for mode_name, mode_icon in [("T", "text_list"), ("🖼", "mini_image"), ("🖼T", "image_text")]:
                tab = QWidget()
                tab_layout = QVBoxLayout(tab)
                tab_layout.setContentsMargins(5, 10, 5, 5)
                
                # Category section
                tab_layout.addWidget(QLabel(f"📁 <b>Category</b>"))
                tab_layout.addLayout(self._create_mode_slider("CardW:", f'cat_{mode_icon}_card_w', 'category', mode_icon, 'card_w', 50, 500))
                h_min = 20 if mode_icon == "text_list" else 50
                tab_layout.addLayout(self._create_mode_slider("CardH:", f'cat_{mode_icon}_card_h', 'category', mode_icon, 'card_h', h_min, 500))
                if mode_icon != "text_list":
                    tab_layout.addLayout(self._create_mode_slider("ImgW:", f'cat_{mode_icon}_img_w', 'category', mode_icon, 'img_w', 0, 500))
                    tab_layout.addLayout(self._create_mode_slider("ImgH:", f'cat_{mode_icon}_img_h', 'category', mode_icon, 'img_h', 0, 500))

                tab_layout.addSpacing(10)
                
                # Package section
                tab_layout.addWidget(QLabel(f"📦 <b>Package</b>"))
                tab_layout.addLayout(self._create_mode_slider("CardW:", f'pkg_{mode_icon}_card_w', 'package', mode_icon, 'card_w', 50, 800))
                tab_layout.addLayout(self._create_mode_slider("CardH:", f'pkg_{mode_icon}_card_h', 'package', mode_icon, 'card_h', h_min, 800))
                if mode_icon != "text_list":
                    tab_layout.addLayout(self._create_mode_slider("ImgW:", f'pkg_{mode_icon}_img_w', 'package', mode_icon, 'img_w', 0, 500))
                    tab_layout.addLayout(self._create_mode_slider("ImgH:", f'pkg_{mode_icon}_img_h', 'package', mode_icon, 'img_h', 0, 500))
                
                # Scale per mode
                tab_layout.addSpacing(5)
                tab_layout.addWidget(QLabel("📐 <b>Scale</b> (Independent)"))
                tab_layout.addLayout(self._create_mode_scale_row("Cat:", f'cat_{mode_icon}_scale', 'category', mode_icon, 25, 400))
                tab_layout.addLayout(self._create_mode_scale_row("Pkg:", f'pkg_{mode_icon}_scale', 'package', mode_icon, 25, 400))

                tab_layout.addStretch()
                self._settings_tabs.addTab(tab, mode_name)
            
            self._settings_tabs.currentChanged.connect(self._on_settings_tab_changed)
            layout.addWidget(self._settings_tabs)
            self._settings_panel.adjustSize()
            
        self._settings_panel.setFixedWidth(350)
        
        # Transactional Backup
        self._settings_backup = copy.deepcopy(self.card_settings)
        self._overrides_backup = (self.cat_display_override, self.pkg_display_override)
        
        # Initial Tab Selection
        cur_mode = self.cat_display_override
        if not cur_mode:
            if self.btn_cat_text.styleSheet() == self.btn_selected_style or self.btn_cat_text.styleSheet() == self.btn_no_override_style:
                cur_mode = "text_list"
            elif self.btn_cat_image.styleSheet() == self.btn_selected_style or self.btn_cat_image.styleSheet() == self.btn_no_override_style:
                cur_mode = "mini_image"
            else:
                cur_mode = "image_text"

        mode_to_tab = {"text_list": 0, "mini_image": 1, "image_text": 2}
        self._settings_tabs.blockSignals(True)
        self._settings_tabs.setCurrentIndex(mode_to_tab.get(cur_mode, 1))
        self._settings_tabs.blockSignals(False)

        # Position near button
        btn_pos = self.btn_card_settings.mapToGlobal(self.btn_card_settings.rect().bottomLeft())
        panel_pos = self.mapFromGlobal(btn_pos)
        
        panel_w = self._settings_panel.width()
        panel_h = self._settings_panel.height()
        window_w = self.width()
        window_h = self.height()
        
        x = panel_pos.x()
        if x + panel_w > window_w - 10:
            x = window_w - panel_w - 10
        if x < 10:
            x = 10
            
        y = panel_pos.y()
        if y + panel_h > window_h - 10:
            y = window_h - panel_h - 10
        if y < 10:
            y = 10
        
        self._settings_panel.move(x, y)
        self._settings_panel.show()
        self._settings_panel.raise_()
        self._settings_panel.activateWindow()

    def _on_settings_tab_changed(self, index):
        """Automatically switch display mode when settings tab is changed."""
        modes = ["text_list", "mini_image", "image_text"]
        target_mode = modes[index]
        self._toggle_cat_display_mode(target_mode, force=True)
        self._toggle_pkg_display_mode(target_mode, force=True)
