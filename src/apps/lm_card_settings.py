"""
Link Master: Card Settings Mixin
カード設定パネルのUIとロジック。

依存するコンポーネント:
- ItemCard (set_card_params を呼び出し)

依存する親クラスの属性:
- card_settings: dict
- cat_layout, pkg_layout: FlowLayout
- cat_display_override, pkg_display_override: str | None
- _settings_panel: QWidget
"""
import copy
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QSpinBox, QSlider, QCheckBox
from PyQt6.QtCore import Qt


class LMCardSettingsMixin:
    """カード設定のUI生成と値管理を担当するMixin。"""
    
    def _create_mode_slider(self, label: str, attr: str, type_: str, mode: str, param: str, min_v: int, max_v: int):
        """スライダー + +/- ボタン + SpinBox の行を生成。"""
        row = QHBoxLayout()
        row.setContentsMargins(5, 0, 0, 0)
        
        lbl = QLabel(_(label))
        lbl.setFixedWidth(60)
        row.addWidget(lbl)
        
        init_val = int(getattr(self, attr, 100))
        
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_v, max_v)
        slider.setValue(init_val)
        slider.setFixedWidth(90)
        row.addWidget(slider)
        
        minus_btn = QPushButton("-")
        minus_btn.setFixedSize(22, 22)
        minus_btn.setStyleSheet("QPushButton { background: #333; color: #fff; border: 1px solid #555; font-weight: bold; border-radius: 4px; } QPushButton:hover { background: #444; }")
        row.addWidget(minus_btn)
        
        spin = QSpinBox()
        spin.setRange(min_v, max_v)
        spin.setValue(init_val)
        spin.setFixedWidth(60) # Unified width
        spin.setStyleSheet("""
            QSpinBox { color: #ddd; background: #222; border: 1px solid #555; padding: 2px; border-radius: 4px; }
            QSpinBox:focus { border: 1px solid #27ae60; }
            QSpinBox::up-button, QSpinBox::down-button { width: 0; height: 0; }
        """)
        spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        row.addWidget(spin)
        
        plus_btn = QPushButton("+")
        plus_btn.setFixedSize(22, 22)
        plus_btn.setStyleSheet("QPushButton { background: #333; color: #fff; border: 1px solid #555; font-weight: bold; border-radius: 4px; } QPushButton:hover { background: #444; }")
        row.addWidget(plus_btn)
        
        def update_all(v):
            v = max(min_v, min(max_v, v))
            slider.blockSignals(True)
            spin.blockSignals(True)
            slider.setValue(v)
            spin.setValue(v)
            slider.blockSignals(False)
            spin.blockSignals(False)
            self._set_mode_param(type_, mode, param, v)
        
        slider.valueChanged.connect(lambda v: update_all(v))
        spin.valueChanged.connect(lambda v: update_all(v))
        minus_btn.clicked.connect(lambda: update_all(spin.value() - 1))
        plus_btn.clicked.connect(lambda: update_all(spin.value() + 1))
        
        return row

    def _create_mode_scale_row(self, label: str, attr: str, type_: str, mode: str, min_v: int, max_v: int):
        """スケール用スライダー行 (パーセント表示)。"""
        row = QHBoxLayout()
        row.setContentsMargins(5, 0, 0, 0)
        
        lbl = QLabel(_(label))
        lbl.setFixedWidth(60)
        row.addWidget(lbl)
        
        init_val = int(getattr(self, attr, 1.0) * 100)
        
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_v, max_v)
        slider.setValue(init_val)
        slider.setFixedWidth(90)
        row.addWidget(slider)
        
        minus_btn = QPushButton("-")
        minus_btn.setFixedSize(22, 22)
        minus_btn.setStyleSheet("QPushButton { background: #333; color: #fff; border: 1px solid #555; font-weight: bold; border-radius: 4px; } QPushButton:hover { background: #444; }")
        row.addWidget(minus_btn)
        
        spin = QSpinBox()
        spin.setRange(min_v, max_v)
        spin.setValue(init_val)
        spin.setSuffix("%")
        spin.setFixedWidth(60)
        spin.setStyleSheet("""
            QSpinBox { color: #ddd; background: #222; border: 1px solid #555; padding: 2px; border-radius: 4px; }
            QSpinBox:focus { border: 1px solid #27ae60; }
            QSpinBox::up-button, QSpinBox::down-button { width: 0; height: 0; }
        """)
        spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        row.addWidget(spin)
        
        plus_btn = QPushButton("+")
        plus_btn.setFixedSize(22, 22)
        plus_btn.setStyleSheet("QPushButton { background: #333; color: #fff; border: 1px solid #555; font-weight: bold; border-radius: 4px; } QPushButton:hover { background: #444; }")
        row.addWidget(plus_btn)
        
        def update_all(v):
            v = max(min_v, min(max_v, v))
            slider.blockSignals(True)
            spin.blockSignals(True)
            slider.setValue(v)
            spin.setValue(v)
            slider.blockSignals(False)
            spin.blockSignals(False)
            self._update_mode_scale(type_, mode, v / 100.0)
        
        slider.valueChanged.connect(lambda v: update_all(v))
        spin.valueChanged.connect(lambda v: update_all(v))
        minus_btn.clicked.connect(lambda: update_all(spin.value() - 1))
        plus_btn.clicked.connect(lambda: update_all(spin.value() + 1))
        
        return row

    def _create_mode_check(self, label: str, attr: str, type_: str, mode: str, param: str):
        """表示/非表示を切り替えるチェックボックス行を生成。"""
        row = QHBoxLayout()
        row.setContentsMargins(10, 0, 0, 0)
        
        check = QCheckBox(label)
        init_val = bool(getattr(self, attr, True))
        check.setChecked(init_val)
        check.setStyleSheet("QCheckBox { color: #ddd; font-size: 11px; }")
        
        def update_val(v):
            self._set_mode_check_param(type_, mode, param, v)
            
        check.toggled.connect(update_val)
        row.addWidget(check)
        return row

    def _set_mode_check_param(self, type_: str, mode: str, param: str, value: bool):
        """チェックボックスの設定値を保存。"""
        prefix = 'cat' if type_ == 'category' else 'pkg'
        attr_name = f'{prefix}_{mode}_{param}'
        
        self.card_settings[attr_name] = value
        setattr(self, attr_name, value)
        self._save_card_settings()
        self._apply_card_params_to_layout(type_, mode)

    def _set_mode_param(self, type_: str, mode: str, param: str, value: int):
        """モードごとのカードパラメータを設定し、DBに保存。"""
        prefix = 'cat' if type_ == 'category' else 'pkg'
        attr_name = f'{prefix}_{mode}_{param}'
        
        self.card_settings[attr_name] = value
        setattr(self, attr_name, value)
        self._save_card_settings()
        
        # 編集中のモードに自動切り替え
        current_override = getattr(self, f'{prefix}_display_override', None)
        if current_override != mode:
            if type_ == 'category':
                self._toggle_cat_display_mode(mode)
            else:
                self._toggle_pkg_display_mode(mode)
        
        self._apply_card_params_to_layout(type_, mode)

    def _update_mode_scale(self, type_: str, mode: str, scale: float):
        """モードスケールを更新し、カードに適用。"""
        prefix = 'cat' if type_ == 'category' else 'pkg'
        attr_name = f'{prefix}_{mode}_scale'
        
        self.card_settings[attr_name] = scale
        setattr(self, attr_name, scale)
        self._save_card_settings()
        
        current_override = getattr(self, f'{prefix}_display_override', None)
        if current_override != mode:
            if type_ == 'category':
                self._toggle_cat_display_mode(mode)
            else:
                self._toggle_pkg_display_mode(mode)
        
        self._apply_card_params_to_layout(type_, mode)

    def _apply_card_params_to_layout(self, type_: str, mode: str):
        """現在のモード設定をレイアウト内の全カードに適用。"""
        prefix = 'cat' if type_ == 'category' else 'pkg'
        scale = getattr(self, f'{prefix}_{mode}_scale', 1.0)
        base_w = getattr(self, f'{prefix}_{mode}_card_w', 160)
        base_h = getattr(self, f'{prefix}_{mode}_card_h', 200)
        base_img_w = getattr(self, f'{prefix}_{mode}_img_w', 140)
        base_img_h = getattr(self, f'{prefix}_{mode}_img_h', 120)
        
        # Phase 31: Visibility Toggles
        show_link = getattr(self, f'{prefix}_{mode}_show_link', True)
        show_deploy = getattr(self, f'{prefix}_{mode}_show_deploy', True)
        opacity = getattr(self, 'deploy_button_opacity', 0.8)
        
        layout = self.cat_layout if type_ == 'category' else self.pkg_layout
        
        # ユーザー要望: スケールに合わせて隙間を調整 (Dynamic Spacing & Margin)
        # Base is 10px. Clamp to sensible minimums.
        dyn_spacing = max(2, int(10 * scale))
        dyn_margin = max(4, int(10 * scale))
        
        layout.setSpacing(dyn_spacing)
        layout.setContentsMargins(dyn_margin, dyn_margin, dyn_margin, dyn_margin)
        
        for i in range(layout.count()):
            widget = layout.itemAt(i).widget()
            if hasattr(widget, 'update_data'):
                # Apply visibility triggers immediate update
                widget.update_data(
                    show_link=show_link,
                    show_deploy=show_deploy,
                    deploy_button_opacity=opacity
                )
            if hasattr(widget, 'set_card_params'):
                widget.set_card_params(base_w, base_h, base_img_w, base_img_h, scale)
        
        # Force layout update to apply new spacing/margins immediately
        layout.update()

    def _sync_settings_to_attributes(self):
        """card_settings 辞書をインスタンス属性に同期。"""
        for k, v in self.card_settings.items():
            setattr(self, k, v)

    def _cancel_settings(self):
        """設定パネルを開く前の状態に戻す。"""
        if not hasattr(self, '_settings_backup'):
            self._settings_panel.hide()
            return
        
        self.card_settings = copy.deepcopy(self._settings_backup)
        self.cat_display_override, self.pkg_display_override = self._overrides_backup
        self._sync_settings_to_attributes()
        self._save_card_settings()
        self._refresh_current_view(force=False)
        self._settings_panel.hide()
