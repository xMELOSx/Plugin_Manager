from PyQt6.QtWidgets import QWidget, QTextEdit, QVBoxLayout, QMenu, QColorDialog, QApplication
from src.core.lang_manager import _
from PyQt6.QtCore import Qt, QPoint, QRect, QSize, pyqtSignal, QEvent, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPolygon, QPen, QBrush, QPainterPath, QPolygonF, QMouseEvent
import math

class StickyHelpWidget(QWidget):
    """
    ユーザーが自由に配置できる付箋型ヘルプウィジェット。
    """
    closed = pyqtSignal()
    data_changed = pyqtSignal()

    # Phase 1.1.10: Style clipboard for copy/paste
    _style_clipboard = {}

    def __init__(self, element_id, target_widget, parent=None):
        super().__init__(None) # ウィンドウとして独立（親を持つとクリッピングされるため）
        self.element_id = element_id
        self.target_widget = target_widget
        self.parent_window = parent # 座標計算のための参照

        # 基本フラグ
        # WindowStaysOnTopHint ensures stickies are always visible
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 状態管理
        self.is_edit_mode = False
        self.bg_color = QColor(40, 40, 40, 200)
        self.text_color = QColor(255, 255, 255, 255)
        self.text_content = _("Help text here...")
        
        # 幾何学データ (相対座標)
        self.offset = QPoint(50, 50) # ターゲットの中心からの本体のズレ
        self.tail_target_offset = QPoint(0, 0) # 本体中心からのしっぽ先端の相対位置
        
        # ドラッグ用
        self._dragging_body = False
        self._dragging_tail = False
        self._resizing_body = False
        self._forwarding_event = False # ループ防止フラグ
        self._drag_start_pos = QPoint()
        self._start_body_size = QSize()
        
        # アンカーモード: 0=割合(Proportional), 1=固定(Fixed), 2=追従(Full Follow)
        self.anchor_mode = 0
        
        # Phase 1.1.7.3: ウィンドウサイズ変更追跡用
        self._last_win_geo = None  # 直前の親ウィンドウのQRect
        self._screen_pos = QPoint(0, 0)  # 固定モード用: スクリーン上の絶対位置
        self._proportional_pos = (0.5, 0.5) # 割合モード用: (x_ratio, y_ratio)
        
        # Phase 1.1.10: Tail visibility
        self.show_tail = True
        
        # UI
        self._init_ui()
        self.resize(150, 80)
        
    def _init_ui(self):
        # レイアウトは使わず、手動でQTextEditの位置を管理する
        self.text_edit = QTextEdit(self)
        self.text_edit.setPlainText(self.text_content)
        self._update_text_style()
        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.text_edit.textChanged.connect(self._on_text_changed)
        self.text_edit.installEventFilter(self)
        
        # 本体の標準サイズ (to_dict/from_dictで保存される)
        self.body_size = QSize(160, 40)
        self.set_edit_mode(False)

    def _update_text_style(self):
        rgba_str = f"rgba({self.text_color.red()}, {self.text_color.green()}, {self.text_color.blue()}, {self.text_color.alpha()})"
        self.text_edit.setStyleSheet(f"background: transparent; border: none; color: {rgba_str};")

    def set_edit_mode(self, enabled):
        self.is_edit_mode = enabled
        if enabled:
            self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, False)
            self.text_edit.setReadOnly(False)
            # エディットモードでも最初はマウスを透過させ、背後のWidget(自分自身)でドラッグを拾えるようにする
            # ただし、ダブルクリックで入力を有効にする
            self.text_edit.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        else:
            self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, True)
            self.text_edit.setReadOnly(True)
            self.text_edit.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            
        self.update()
        if self.isVisible():
            self.show()

    def update_position(self):
        """Phase 1.1.7.3: 親ウィンドウのサイズ変更に応じて付箋の位置を更新する。"""
        if not self.parent_window:
            return
        
        win_geo = self.parent_window.geometry()
        
        # 初回呼び出し時は現在のウィンドウサイズを記録
        if self._last_win_geo is None:
            self._last_win_geo = win_geo
            # デフォルトの位置を設定 (ターゲットを指すならその近く)
            if self.target_widget and self.target_widget != self.parent_window:
                target_global = self.target_widget.mapToGlobal(QPoint(0, 0))
                self._screen_pos = target_global + self.offset
            else:
                self._screen_pos = win_geo.topLeft() + self.offset
            
            # 割合位置も初期化
            if win_geo.width() > 0 and win_geo.height() > 0:
                rel_x = (self._screen_pos.x() - win_geo.x()) / win_geo.width()
                rel_y = (self._screen_pos.y() - win_geo.y()) / win_geo.height()
                self._proportional_pos = (rel_x, rel_y)
        
        # モード別の位置計算
        if self.anchor_mode == 1:  # 固定: スクリーン上の絶対位置に留まる
            body_center_g = self._screen_pos
            
        elif self.anchor_mode == 0:  # 割合: ウィンドウの割合位置を維持
            new_x = win_geo.x() + int(self._proportional_pos[0] * win_geo.width())
            new_y = win_geo.y() + int(self._proportional_pos[1] * win_geo.height())
            body_center_g = QPoint(new_x, new_y)
            # スクリーン位置も同期
            self._screen_pos = body_center_g
            
        else:  # anchor_mode == 2 追従: ウィンドウサイズの変化量だけ移動
            # サイズ差分を計算
            delta_w = win_geo.width() - self._last_win_geo.width()
            delta_h = win_geo.height() - self._last_win_geo.height()
            # 移動差分も計算
            delta_x = win_geo.x() - self._last_win_geo.x()
            delta_y = win_geo.y() - self._last_win_geo.y()
            
            # スクリーン位置を更新 (ウィンドウの右下リサイズに追従)
            self._screen_pos = QPoint(
                self._screen_pos.x() + delta_x + delta_w,
                self._screen_pos.y() + delta_y + delta_h
            )
            body_center_g = self._screen_pos
            
            # 割合位置も同期
            if win_geo.width() > 0 and win_geo.height() > 0:
                rel_x = (self._screen_pos.x() - win_geo.x()) / win_geo.width()
                rel_y = (self._screen_pos.y() - win_geo.y()) / win_geo.height()
                self._proportional_pos = (rel_x, rel_y)
        
        # anchor_mode == 3: 要素追従 (ターゲットウィジェットの位置に直接追従)
        if self.anchor_mode == 3 and self.target_widget and self.target_widget != self.parent_window:
            target_global = self.target_widget.mapToGlobal(QPoint(0, 0))
            target_center = target_global + QPoint(self.target_widget.width() // 2, self.target_widget.height() // 2)
            body_center_g = target_center + self.offset
            self._screen_pos = body_center_g
            
            # 割合位置も同期
            if win_geo.width() > 0 and win_geo.height() > 0:
                rel_x = (self._screen_pos.x() - win_geo.x()) / win_geo.width()
                rel_y = (self._screen_pos.y() - win_geo.y()) / win_geo.height()
                self._proportional_pos = (rel_x, rel_y)
        
        # ウィンドウサイズを記録
        self._last_win_geo = win_geo
        
        # しっぽの先端（グローバル）を計算
        tail_tip_g = body_center_g + self.tail_target_offset
        
        # 本体の矩形（グローバル）
        body_rect_g = QRect(body_center_g.x() - self.body_size.width() // 2,
                            body_center_g.y() - self.body_size.height() // 2,
                            self.body_size.width(), self.body_size.height())
        
        # ウィンドウ全体の矩形（グローバル）
        margin = 30
        widget_rect_g = body_rect_g.united(QRect(tail_tip_g, QSize(1,1))).adjusted(-margin, -margin, margin, margin)
        
        self.setGeometry(widget_rect_g)
        
        # テキストエディタを本体部分に配置（ローカル座標）
        local_body_topLeft = body_rect_g.topLeft() - widget_rect_g.topLeft()
        body_local = QRect(local_body_topLeft, self.body_size)
        self.text_edit.setGeometry(body_local.adjusted(4, 4, -4, -4))
        self.update()

    def _on_text_changed(self):
        self.text_content = self.text_edit.toPlainText()
        self.data_changed.emit()

    def _get_body_rect(self):
        """Phase 1.1.10: Calculate body rectangle in local coordinates."""
        widget_topLeft = self.geometry().topLeft()
        local_body_center = self._screen_pos - widget_topLeft
        return QRectF(local_body_center.x() - self.body_size.width() / 2,
                           local_body_center.y() - self.body_size.height() / 2,
                           self.body_size.width(), self.body_size.height())

    def _get_shape_path(self):
        """Phase 1.1.10: Calculate the combined shape of the sticky (body + optional tail)."""
        widget_topLeft = self.geometry().topLeft()
        local_body_center = self._screen_pos - widget_topLeft
        body_rect = self._get_body_rect()
        
        path = QPainterPath()
        path.addRoundedRect(body_rect, 8, 8)
        
        if self.show_tail:
            tail_tip = (self._screen_pos + self.tail_target_offset) - widget_topLeft
            
            # Distance from tip to each edge (positive if outside)
            dist_l = body_rect.left() - tail_tip.x()
            dist_r = tail_tip.x() - body_rect.right()
            dist_t = body_rect.top() - tail_tip.y()
            dist_b = tail_tip.y() - body_rect.bottom()
            
            max_d = max(dist_l, dist_r, dist_t, dist_b)
            if max_d <= 0:
                return path # Inside
            
            base_width = 25
            margin_edge = 10
            
            if max_d == dist_l or max_d == dist_r:
                bx = body_rect.left() if max_d == dist_l else body_rect.right()
                by = max(body_rect.top() + margin_edge + base_width/2, 
                         min(body_rect.bottom() - margin_edge - base_width/2, tail_tip.y()))
                p1 = QPointF(bx, by - base_width / 2)
                p2 = QPointF(bx, by + base_width / 2)
            else:
                by = body_rect.top() if max_d == dist_t else body_rect.bottom()
                bx = max(body_rect.left() + margin_edge + base_width/2, 
                         min(body_rect.right() - margin_edge - base_width/2, tail_tip.x()))
                p1 = QPointF(bx - base_width / 2, by)
                p2 = QPointF(bx + base_width / 2, by)

            tail_poly = QPolygonF([p1, p2, QPointF(tail_tip)])
            path.addPolygon(tail_poly)
                
        return path

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Phase 1.1.7.3: Use _screen_pos as the source of truth
        body_center_g = self._screen_pos
        
        # Phase 1.1.10: Use unified path calculation
        merged_path = self._get_shape_path()

        painter.setBrush(QBrush(self.bg_color))
        if self.is_edit_mode:
            painter.setPen(QPen(QColor(255, 255, 255, 180), 2))
        else:
            painter.setPen(Qt.PenStyle.NoPen)
        
        painter.drawPath(merged_path)
        
        if self.is_edit_mode:
            if self.show_tail:
                # 尻尾先端のアンカー
                widget_topLeft = self.geometry().topLeft()
                tail_tip = (body_center_g + self.tail_target_offset) - widget_topLeft
                painter.setBrush(QBrush(QColor(255, 0, 0, 200)))
                painter.setPen(QPen(Qt.GlobalColor.white, 2))
                painter.drawEllipse(tail_tip, 8, 8)
            
            # リサイズハンドル（右下）
            body_rect = self._get_body_rect()
            handle_size = 12
            handle_rect = QRectF(body_rect.right() - handle_size, body_rect.bottom() - handle_size, handle_size, handle_size)
            painter.setBrush(QBrush(QColor(255, 255, 255, 100)))
            painter.setPen(Qt.PenStyle.NoPen)
            # 斜め線の装飾
            for i in range(3):
                offset = i * 4
                painter.drawLine(QPointF(handle_rect.right() - offset, handle_rect.bottom()),
                                 QPointF(handle_rect.right(), handle_rect.bottom() - offset))

    def eventFilter(self, obj, event):
        # ターゲットピッカーモード中は Enterキーで確定（クリックだと要素のハンドラが発火するため）
        if getattr(self, '_picking_target', False) and obj == self.parent_window:
            if event.type() == QEvent.Type.KeyPress:
                from PyQt6.QtCore import Qt as QtKey
                if event.key() in [QtKey.Key.Key_Return, QtKey.Key.Key_Enter, QtKey.Key.Key_Space]:
                    # Phase 1.1.10: Use childAt to avoid sticking hitting the sticky itself
                    from PyQt6.QtGui import QCursor
                    global_pos = QCursor.pos()
                    local_win_pos = self.parent_window.mapFromGlobal(global_pos)
                    # childAt is better than widgetAt for precise matching inside a specific window
                    widget = self.parent_window.childAt(local_win_pos)
                    
                    # If we hit nothing or just a layout spacer, try to find top-most widget
                    if not widget:
                        widget = QApplication.widgetAt(global_pos)
                    
                    # ピッカーモードを終了
                    self._picking_target = False
                    self.parent_window.removeEventFilter(self)
                    self.parent_window.setCursor(Qt.CursorShape.ArrowCursor)
                    
                    # 選択されたウィジェットをターゲットに設定
                    self._on_element_picked(widget)
                    return True  # イベントを消費
                elif event.key() == QtKey.Key.Key_Escape:
                    # Escでキャンセル
                    self._picking_target = False
                    self.parent_window.removeEventFilter(self)
                    self.parent_window.setCursor(Qt.CursorShape.ArrowCursor)
                    return True
        
        if obj == self.text_edit and event.type() == QEvent.Type.FocusOut:
            if self.is_edit_mode:
                self.text_edit.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        if self._forwarding_event:
            return
            
        if not self.is_edit_mode:
            super().mousePressEvent(event)
            return
        
        # Phase 1.1.7.3: Use _screen_pos as the source of truth
        body_center_g = self._screen_pos
        
        widget_topLeft = self.geometry().topLeft()
        local_body_center = body_center_g - widget_topLeft
        tail_tip = (body_center_g + self.tail_target_offset) - widget_topLeft
        local_pos = event.pos()
        
        # 1. アンカー（尻尾先端）チェック
        if self.show_tail and (local_pos - tail_tip).manhattanLength() < 25:
            self._dragging_tail = True
            self._drag_start_pos = event.globalPosition().toPoint()
            event.accept()
            return

        body_rect = QRect(local_body_center.x() - self.body_size.width() // 2,
                          local_body_center.y() - self.body_size.height() // 2,
                          self.body_size.width(), self.body_size.height())
        
        # 2. リサイズハンドル（右下）チェック
        handle_size = 20 # 判定は広めにする
        resize_rect = QRect(body_rect.right() - handle_size, body_rect.bottom() - handle_size, handle_size, handle_size)
        if resize_rect.contains(local_pos):
            self._resizing_body = True
            self._drag_start_pos = event.globalPosition().toPoint()
            self._start_body_size = self.body_size
            event.accept()
            return

        # 3. 本体（中央）チェック
        if body_rect.contains(local_pos):
            if event.button() == Qt.MouseButton.LeftButton:
                # 枠に近いところ（外周15px）を触った場合は移動、内側は編集フォーカス
                edge_margin = 15
                if (local_pos.x() < body_rect.left() + edge_margin or 
                    local_pos.x() > body_rect.right() - edge_margin or
                    local_pos.y() < body_rect.top() + edge_margin or
                    local_pos.y() > body_rect.bottom() - edge_margin):
                    
                    self._dragging_body = True
                    self._drag_start_pos = event.globalPosition().toPoint()
                    event.accept()
                else:
                    # 内側クリック: 即座にテキスト編集を有効にする
                    self.text_edit.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
                    self.text_edit.setFocus()
                    # イベントを自分（text_edit）に振り向ける
                    local_pos_f = QPointF(self.text_edit.mapFromGlobal(event.globalPosition().toPoint()))
                    new_event = QMouseEvent(event.type(), local_pos_f, 
                                            event.button(), event.buttons(), event.modifiers())
                    self._forwarding_event = True
                    try:
                        QApplication.sendEvent(self.text_edit, new_event)
                    finally:
                        self._forwarding_event = False
            elif event.button() == Qt.MouseButton.RightButton:
                self._show_context_menu(event.globalPosition().toPoint())
                event.accept()
            return # Block default
        
        # 4. Phase 1.1.10: Tail body check (for dragging/menu on the tail itself)
        if self.show_tail:
            # Check if mouse is on the tail part (path test)
            path = self._get_shape_path()
            if path.contains(QPointF(local_pos)):
                if event.button() == Qt.MouseButton.LeftButton:
                    self._dragging_body = True
                    self._drag_start_pos = event.globalPosition().toPoint()
                    event.accept()
                elif event.button() == Qt.MouseButton.RightButton:
                    self._show_context_menu(event.globalPosition().toPoint())
                    event.accept()

    def mouseMoveEvent(self, event):
        if not self.is_edit_mode:
            return
            
        if self._resizing_body:
            delta = event.globalPosition().toPoint() - self._drag_start_pos
            new_w = max(80, self._start_body_size.width() + delta.x())
            new_h = max(20, self._start_body_size.height() + delta.y())
            self.body_size = QSize(new_w, new_h)
            self.update_position()
            self.data_changed.emit()
            
        elif self._dragging_body:
            delta = event.globalPosition().toPoint() - self._drag_start_pos
            # Phase 1.1.7.3: Update _screen_pos directly instead of offset
            self._screen_pos += delta
            self._drag_start_pos = event.globalPosition().toPoint()
            
            # Phase 1.1.7.4: For Element Follow mode, also update offset
            if self.anchor_mode == 3 and self.target_widget and self.target_widget != self.parent_window:
                target_global = self.target_widget.mapToGlobal(QPoint(0, 0))
                target_center = target_global + QPoint(self.target_widget.width() // 2, self.target_widget.height() // 2)
                self.offset = self._screen_pos - target_center
            
            # Update proportional position to match new screen position
            if self.parent_window:
                win_geo = self.parent_window.geometry()
                if win_geo.width() > 0 and win_geo.height() > 0:
                    rel_x = (self._screen_pos.x() - win_geo.x()) / win_geo.width()
                    rel_y = (self._screen_pos.y() - win_geo.y()) / win_geo.height()
                    self._proportional_pos = (rel_x, rel_y)
            
            self.update_position()
            self.data_changed.emit()
            
        elif self._dragging_tail:
            # Phase 1.1.7.3: Use _screen_pos as the body center
            body_center_g = self._screen_pos
            
            # New offset = mouse global position - body global center
            self.tail_target_offset = event.globalPosition().toPoint() - body_center_g
            self.update_position()
            self.data_changed.emit()

    def mouseReleaseEvent(self, event):
        self._dragging_body = False
        self._dragging_tail = False
        self._resizing_body = False

    def mouseDoubleClickEvent(self, event):
        """ダブルクリックでも編集モードに入れる（内側シングルクリックでも入れるようになったのでバックアップ的役割）"""
        if self.is_edit_mode:
            self.text_edit.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            self.text_edit.setFocus()
            event.accept()

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        
        reset_anchor_action = menu.addAction(_("Reset Anchor (Jump Out)"))
        
        mode_menu = menu.addMenu(_("Follow Mode"))
        m0 = mode_menu.addAction(_("Proportional (Center)"))
        m0.setCheckable(True)
        m0.setChecked(self.anchor_mode == 0)
        
        m1 = mode_menu.addAction(_("Fixed (Top-Left)"))
        m1.setCheckable(True)
        m1.setChecked(self.anchor_mode == 1)
        
        m2 = mode_menu.addAction(_("Full Follow (Size Delta)"))
        m2.setCheckable(True)
        m2.setChecked(self.anchor_mode == 2)
        
        m3 = mode_menu.addAction(_("Element Follow (Target)"))
        m3.setCheckable(True)
        m3.setChecked(self.anchor_mode == 3)
        
        menu.addSeparator()
        pick_target_action = menu.addAction(_("🎯 Pick Target Element..."))
        show_target_action = menu.addAction(_("👁 Show Current Target"))
        
        change_bg_action = menu.addAction(_("Change Background Color"))
        change_text_action = menu.addAction(_("Change Text Color"))
        
        menu.addSeparator()
        # Phase 1.1.10: Style and Tail Controls
        copy_style_action = menu.addAction(_("Copy Style"))
        paste_style_action = menu.addAction(_("Paste Style"))
        paste_style_action.setEnabled(bool(self._style_clipboard))
        
        toggle_tail_action = menu.addAction(_("Show Tail"))
        toggle_tail_action.setCheckable(True)
        toggle_tail_action.setChecked(self.show_tail)
        
        menu.addSeparator()
        delete_action = menu.addAction(_("Delete (Clear Content)"))
        
        action = menu.exec(pos)
        if action == reset_anchor_action:
            # アンカーを本体の右側に飛ばす
            self.tail_target_offset = QPoint(self.body_size.width() // 2 + 50, 0)
            self.update_position()
            self.data_changed.emit()
        elif action == m0:
            self.anchor_mode = 0
            self._recalc_offset_after_mode_change()
            self.data_changed.emit()
        elif action == m1:
            self.anchor_mode = 1
            self._recalc_offset_after_mode_change()
            self.data_changed.emit()
        elif action == m2:
            self.anchor_mode = 2
            self._recalc_offset_after_mode_change()
            self.data_changed.emit()
        elif action == m3:
            self.anchor_mode = 3
            self._recalc_offset_for_element_mode()
            self.data_changed.emit()
        elif action == pick_target_action:
            self._start_element_picker()
        elif action == show_target_action:
            self._show_current_target()
        elif action == change_bg_action:
            color = QColorDialog.getColor(self.bg_color, self, _("Select Background Color"), QColorDialog.ColorDialogOption.ShowAlphaChannel)
            if color.isValid():
                self.bg_color = color
                self.update()
                self.data_changed.emit()
        elif action == change_text_action:
            color = QColorDialog.getColor(self.text_color, self, _("Select Text Color"), QColorDialog.ColorDialogOption.ShowAlphaChannel)
            if color.isValid():
                self.text_color = color
                self._update_text_style()
                self.data_changed.emit()
        elif action == copy_style_action:
            self._copy_style()
        elif action == paste_style_action:
            self._paste_style()
        elif action == toggle_tail_action:
            self.show_tail = not self.show_tail
            self.update_position()
            self.data_changed.emit()
        elif action == delete_action:
            self.text_edit.clear()

    def _copy_style(self):
        StickyHelpWidget._style_clipboard = {
            "bg_color": self.bg_color,
            "text_color": self.text_color,
            "body_size": QSize(self.body_size),
            "show_tail": self.show_tail
        }

    def _paste_style(self):
        style = StickyHelpWidget._style_clipboard
        if not style: return
        self.bg_color = QColor(style["bg_color"])
        self.text_color = QColor(style["text_color"])
        self.body_size = QSize(style["body_size"])
        self.show_tail = style["show_tail"]
        self._update_text_style()
        self.update_position()
        self.data_changed.emit()

    def _recalc_offset_after_mode_change(self):
        """Phase 1.1.7.3: モード変更時に内部状態を同期。"""
        if not self.parent_window: return
        
        # 現在の本体中心(Global)を取得
        current_rect_g = self.geometry().adjusted(30, 30, -30, -30)
        current_body_center_g = current_rect_g.center()
        
        # スクリーン位置を更新
        self._screen_pos = current_body_center_g
        
        # 割合位置を更新
        win_geo = self.parent_window.geometry()
        if win_geo.width() > 0 and win_geo.height() > 0:
            rel_x = (self._screen_pos.x() - win_geo.x()) / win_geo.width()
            rel_y = (self._screen_pos.y() - win_geo.y()) / win_geo.height()
            self._proportional_pos = (rel_x, rel_y)
        
        self._last_win_geo = win_geo
        self.update_position()

    def _recalc_offset_for_element_mode(self):
        """要素追従モード切替時にオフセットを再計算。"""
        if not self.target_widget or self.target_widget == self.parent_window:
            # ターゲットがない場合は通常モードに戻す
            self.anchor_mode = 0
            self._recalc_offset_after_mode_change()
            return
        
        # 現在の本体中心(Global)を取得
        current_rect_g = self.geometry().adjusted(30, 30, -30, -30)
        current_body_center_g = current_rect_g.center()
        
        # ターゲットの中心を計算
        target_global = self.target_widget.mapToGlobal(QPoint(0, 0))
        target_center = target_global + QPoint(self.target_widget.width() // 2, self.target_widget.height() // 2)
        
        # オフセット = 現在の本体中心 - ターゲット中心
        self.offset = current_body_center_g - target_center
        self._screen_pos = current_body_center_g
        self.update_position()

    def _start_element_picker(self):
        """ターゲット要素を選択するピッカーモードを開始。"""
        from PyQt6.QtWidgets import QMessageBox
        
        if not self.parent_window:
            return
        
        # ユーザーにホバー+Enterで選択を促す
        msg = QMessageBox(self.parent_window)
        msg.setWindowTitle(_("Pick Target Element"))
        msg.setText(_("After closing this dialog:\n\n1. Hover your mouse over the target UI element\n2. Press Enter or Space to confirm\n3. Press Escape to cancel\n\nThis method avoids triggering the element's click action."))
        msg.setIcon(QMessageBox.Icon.Information)
        msg.exec()
        
        # 親ウィンドウにイベントフィルターをインストール
        self._picking_target = True
        self.parent_window.installEventFilter(self)
        
        # カーソルを変更
        from PyQt6.QtGui import QCursor
        self.parent_window.setCursor(Qt.CursorShape.CrossCursor)
    
    def _on_element_picked(self, widget):
        """要素が選択されたときに呼ばれる。"""
        from PyQt6.QtWidgets import QMessageBox
        
        # 無効なターゲットをチェック
        if not widget or widget == self.parent_window:
            QMessageBox.warning(
                self.parent_window,
                _("Invalid Target"),
                _("Cannot target the main window. Please select a specific UI element.")
            )
            return
        
        # 付箋自身や他の付箋をターゲットにしない
        if isinstance(widget, StickyHelpWidget) or widget == self or widget == self.text_edit:
            QMessageBox.warning(
                self.parent_window,
                _("Invalid Target"),
                _("Cannot target a sticky note. Please select a different UI element.")
            )
            return
        
        # 親が付箋の場合も除外
        parent = widget.parent()
        while parent:
            if isinstance(parent, StickyHelpWidget):
                QMessageBox.warning(
                    self.parent_window,
                    _("Invalid Target"),
                    _("Cannot target a sticky note. Please select a different UI element.")
                )
                return
            parent = parent.parent()
        
        self.target_widget = widget
        # 自動的に要素追従モードに設定
        self.anchor_mode = 3
        self._recalc_offset_for_element_mode()
        self.data_changed.emit()
        
        # 通知
        widget_name = widget.objectName() or widget.__class__.__name__
        QMessageBox.information(
            self.parent_window,
            _("Target Set"),
            _("Target element set to: {name}").format(name=widget_name)
            )
    
    def _show_current_target(self):
        """現在のターゲット要素を表示。"""
        from PyQt6.QtWidgets import QMessageBox
        
        if not self.target_widget or self.target_widget == self.parent_window:
            QMessageBox.information(
                self.parent_window,
                _("Current Target"),
                _("No specific target element. (Window)")
            )
        else:
            widget_name = self.target_widget.objectName() or self.target_widget.__class__.__name__
            QMessageBox.information(
                self.parent_window,
                _("Current Target"),
                _("Target: {name}").format(name=widget_name)
            )

    def to_dict(self):
        # target_widgetの識別子を保存（objectName またはクラス名）
        target_name = None
        if self.target_widget and self.target_widget != self.parent_window:
            target_name = self.target_widget.objectName() or self.target_widget.__class__.__name__
        
        return {
            "body_size": [self.body_size.width(), self.body_size.height()],
            "offset": [self.offset.x(), self.offset.y()],
            "tail_target": [self.tail_target_offset.x(), self.tail_target_offset.y()],
            "bg_style": self.bg_color.rgba(),
            "text_style": self.text_color.rgba(),
            "content": self.text_content,
            "anchor_mode": self.anchor_mode,
            "target_widget_name": target_name,  # Phase 1.1.8: ターゲット保存
            "show_tail": self.show_tail # Phase 1.1.10
        }

    def from_dict(self, data):
        if "body_size" in data:
            self.body_size = QSize(data["body_size"][0], data["body_size"][1])
        if "offset" in data:
            self.offset = QPoint(data["offset"][0], data["offset"][1])
        if "tail_target" in data:
            self.tail_target_offset = QPoint(data["tail_target"][0], data["tail_target"][1])
        if "bg_style" in data:
            self.bg_color = QColor.fromRgba(data["bg_style"])
        elif "style" in data: # Legacy support
            self.bg_color = QColor.fromRgba(data["style"])
        if "text_style" in data:
            self.text_color = QColor.fromRgba(data["text_style"])
            self._update_text_style()
        if "content" in data:
            self.text_content = data["content"]
        if "anchor_mode" in data:
            self.anchor_mode = data["anchor_mode"]
        if "show_tail" in data:
            self.show_tail = data["show_tail"]
        
        self.text_edit.setPlainText(self.text_content)
        
        # Phase 1.1.8: target_widgetの復元（要素追従モードの場合）
        if "target_widget_name" in data and data["target_widget_name"] and self.parent_window:
            target_name = data["target_widget_name"]
            # objectNameで検索
            found = self.parent_window.findChild(QWidget, target_name)
            if found:
                self.target_widget = found
            else:
                # objectNameがない場合、クラス名で検索（最初に見つかったもの）
                for child in self.parent_window.findChildren(QWidget):
                    if child.__class__.__name__ == target_name:
                        self.target_widget = child
                        break
        
        # Phase 1.1.7.3: 保存/復元時にスクリーン位置も確定
        if self.parent_window:
            self._last_win_geo = self.parent_window.geometry()
            # offset から復元
            self._screen_pos = self._last_win_geo.topLeft() + self.offset
            
            w = self._last_win_geo.width()
            h = self._last_win_geo.height()
            if w > 0 and h > 0:
                rel_x = (self._screen_pos.x() - self._last_win_geo.x()) / w
                rel_y = (self._screen_pos.y() - self._last_win_geo.y()) / h
                self._proportional_pos = (rel_x, rel_y)
        
        self.update_position()
