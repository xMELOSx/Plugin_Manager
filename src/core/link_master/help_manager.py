import os
import json
import logging
from PyQt6.QtCore import QObject, QPoint, QEvent
from PyQt6.QtWidgets import QApplication
from src.ui.link_master.help_sticky import StickyHelpWidget

class StickyHelpManager(QObject):
    """
    複数の StickyHelpWidget を管理し、データの永続化と親ウィンドウへの追従を行う。
    """
    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.stickies = {} # element_id -> StickyHelpWidget
        self.is_help_visible = False
        self.is_edit_mode = False
        self._edit_start_state = {} # 編集開始時の状態を保持するバッファ
        
        # 親ウィンドウにイベントフィルターをインストール
        self.parent_window.installEventFilter(self)
        self._was_minimized = False
        
        # Connect to language change signal
        from src.core.lang_manager import get_lang_manager
        get_lang_manager().language_changed.connect(self._on_language_changed)
        self._needs_reload = False

    def register_sticky(self, element_id, target_widget):
        """特定のUI要素に紐づくヘルプ付箋を登録する。"""
        if element_id in self.stickies:
            return
            
        sticky = StickyHelpWidget(element_id, target_widget, self.parent_window)
        # リアルタイム保存を廃止（トグル時のみ保存にする）
        # sticky.data_changed.connect(self.save_all)
        self.stickies[element_id] = sticky
        
        # 保存されたデータがあればロード
        self.load_single(element_id)

    def toggle_help(self, edit_mode=False):
        """ヘルプの表示/非表示を切り替える。"""
        self.parent_window.logger.info(f"[HelpProfile] manager.toggle_help: current_visible={self.is_help_visible}, target_edit={edit_mode}")
        # 編集モードに入る直前にスナップショットを保存
        if edit_mode and not self.is_edit_mode:
            self._capture_snapshot()

        # すでに表示中かつ同じモードなら閉じる
        if self.is_help_visible and self.is_edit_mode == edit_mode:
            if self.is_edit_mode:
                self.save_all() # 編集モードから抜けるタイミングで保存
            self.hide_all()
            return

        # 編集モードから通常表示に戻るタイミングで保存
        if self.is_edit_mode and not edit_mode:
            self.save_all()

        # 言語変更があった場合は再読み込み（フラグのみで制御）
        if self._needs_reload:
            self.parent_window.logger.info(f"[HelpProfile] toggle_help: cleaning up before open")
            self._needs_reload = False

        self.is_help_visible = True
        self.is_edit_mode = edit_mode
        self.show_all()

    def _capture_snapshot(self):
        """現在の全付箋の状態をメモリに保存する。"""
        self._edit_start_state = {eid: sticky.to_dict() for eid, sticky in self.stickies.items()}

    def cancel_all_edits(self):
        """編集を破棄して、最後に保存された（または編集開始時の）状態に戻す。"""
        if not self.is_edit_mode:
            return

        # スナップショットから復元
        for eid, state in self._edit_start_state.items():
            if eid in self.stickies:
                self.stickies[eid].from_dict(state)
        
        # 編集モードを抜ける（保存せずに）
        self.is_edit_mode = False
        self.show_all()

    def show_all(self):
        self.parent_window.logger.info(f"[HelpProfile] show_all: preparing {len(self.stickies)} stickies")
        
        # 1. Prepare positions while invisible
        for eid, sticky in self.stickies.items():
            sticky.set_edit_mode(self.is_edit_mode)
            sticky.update_position()
            # Set transparent to avoid flash at old/defualt position
            sticky.setWindowOpacity(0.0)
            sticky.show()
            
        # 2. Force layout to settle
        QApplication.processEvents()
        
        # 3. Final positioning and show
        for eid, sticky in self.stickies.items():
            # Recalculate now that parent is definitely laid out
            sticky.update_position()
            sticky.setWindowOpacity(1.0)
            
            # Log for verification
            if eid in ["target_app", "tag_bar"]:
                self.parent_window.logger.info(f"[HelpProfile] show_all check: eid={eid}, textlen={len(sticky.text_content)}")
        self.is_help_visible = True

    def hide_all(self):
        for sticky in self.stickies.values():
            sticky.hide()
        self.is_help_visible = False
        # toggle_help側で必要に応じてsave_allを呼ぶため、ここでは呼ばない

    def eventFilter(self, obj, event):
        # 親ウィンドウの移動やリサイズを検知
        if obj == self.parent_window:
            if event.type() == QEvent.Type.WindowStateChange:
                is_minimized = self.parent_window.isMinimized()
                if is_minimized != self._was_minimized:
                    self._was_minimized = is_minimized
                    if is_minimized:
                        # 最小化されたら一時的に隠す
                        for sticky in self.stickies.values():
                            sticky.hide()
                    elif self.is_help_visible:
                        # 復元されたら、ヘルプが有効だった場合のみ再表示
                        self.show_all()

            elif event.type() in [QEvent.Type.Move, QEvent.Type.Resize]:
                if self.is_help_visible:
                    # 全ての付箋の位置を更新
                    for sticky in self.stickies.values():
                        sticky.update_position()
        return super().eventFilter(obj, event)

    def add_free_sticky(self):
        """アンカーを持たない自由な付箋を追加する。"""
        import uuid
        element_id = f"free_{uuid.uuid4().hex[:8]}"
        # 親ウィンドウをターゲットにすることで、ウィンドウ全体に追従させる
        self.register_sticky(element_id, self.parent_window)
        
        # 編集モードで表示
        self.is_help_visible = True
        self.is_edit_mode = True
        sticky = self.stickies[element_id]
        sticky.set_edit_mode(True)
        sticky.show()
        return sticky

    def save_all(self):
        """全付箋のデータをYAMLに保存（言語毎）。"""
        from src.core.lang_manager import get_lang_manager
        lang_manager = get_lang_manager()
        
        for eid, sticky in self.stickies.items():
            # テキストが空でデフォルト値の場合は保存しないなどのロジックも検討可能
            note_data = sticky.to_dict()
            lang_manager.set_help_data(eid, note_data)

    def load_all(self):
        """全付箋のデータをYAMLからロード（言語毎）。"""
        from src.core.lang_manager import get_lang_manager
        lang_manager = get_lang_manager()
        
        for eid in self.stickies:
            sticky_data = lang_manager.get_help_data(eid)
            self.parent_window.logger.info(f"[HelpProfile] load_all: eid={eid}, data_found={bool(sticky_data)}")
            # Always call from_dict to handle default string translation fallback
            self.stickies[eid].from_dict(sticky_data or {})

    def load_single(self, element_id):
        """単一の付箋のデータをYAMLからロード（言語毎）。"""
        from src.core.lang_manager import get_lang_manager
        lang_manager = get_lang_manager()
        
        sticky_data = lang_manager.get_help_data(element_id)
        if element_id in self.stickies:
            self.stickies[element_id].from_dict(sticky_data or {})
    
    def _on_language_changed(self, lang_code):
        """言語が変更されたときにヘル普データを即座に再読み込みし、表示位置を更新。"""
        self.parent_window.logger.info(f"[HelpProfile] _on_language_changed: lang={lang_code}, visible={self.is_help_visible}")
        
        # 内部データを再読み込み
        self.load_all()
        
        if self.is_help_visible:
            # 表示中の場合は即座に位置を更新
            for sticky in self.stickies.values():
                sticky.update_position()
            self._needs_reload = False
        else:
            # 非表示中の場合は、開く時に再配置するようにフラグを立てる
            self._needs_reload = True
