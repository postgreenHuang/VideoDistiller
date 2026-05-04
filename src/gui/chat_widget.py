"""
Video-Distiller AI 对话界面
- 左侧：session 列表（按时间排序，显示关联文件状态）
- 右侧：消息气泡 + 模型切换 + 齿轮配置 + 新建对话
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QScrollArea, QSizePolicy, QListWidget,
    QListWidgetItem, QFrame, QComboBox, QFileDialog, QMenu,
    QDialog, QGridLayout, QLineEdit, QDialogButtonBox,
    QSplitter,
)

from src.chat import ChatSession, create_empty_session, list_sessions


_THINKING_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class MessageBubble(QLabel):
    _font_family = ""
    _font_scale = 100

    def __init__(self, role: str, text: str):
        super().__init__()
        self.setProperty("class", f"msg-{role}")
        self.setWordWrap(True)
        self._raw_text = text
        self.setText(self._render_md(text, self._font_family, self._font_scale))
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self._sync_widget_font()

    @staticmethod
    def _render_md(text: str, font_family: str, font_scale: int) -> str:
        import re
        from PySide6.QtGui import QTextDocument, QFont

        doc = QTextDocument()

        base_px = 14.0 * font_scale / 100.0
        family = font_family if font_family else ("PingFang SC" if sys.platform == "darwin" else "Microsoft YaHei UI")
        font = QFont(family)
        font.setPixelSize(int(base_px))
        doc.setDefaultFont(font)

        doc.setMarkdown(text)
        html = doc.toHtml()

        def _patch(tag, top, bottom):
            nonlocal html
            html = re.sub(
                rf'(<{tag}\s[^>]*?)margin-top:\s*\d+px;(\s*)margin-bottom:\s*\d+px',
                rf'\g<1>margin-top:{top}px;\2margin-bottom:{bottom}px',
                html,
            )

        _patch('h1', 20, 8)
        _patch('h2', 18, 6)
        _patch('h3', 14, 4)
        _patch('p',  4,  4)
        _patch('li', 2,  2)
        return html

    def _apply_font(self):
        self.setText(self._render_md(self._raw_text, self._font_family, self._font_scale))
        self._sync_widget_font()

    def _sync_widget_font(self):
        """确保 QLabel 基线字体与渲染时一致，使 HTML 相对字号正确解析"""
        base_px = 14.0 * self._font_scale / 100.0
        family = f'"{self._font_family}"' if self._font_family else "inherit"
        self.setStyleSheet(f"font-family: {family}; font-size: {base_px}px;")

    @classmethod
    def set_chat_font(cls, family: str, scale: int):
        cls._font_family = family
        cls._font_scale = scale


class _ChatWorker(QThread):
    finished = Signal(str, int)
    error = Signal(str)

    def __init__(self, session: ChatSession, message: str):
        super().__init__()
        self.session = session
        self.message = message

    def run(self):
        try:
            reply = self.session.chat(self.message)
            total = sum(len(m["content"]) for m in self.session.messages)
            self.finished.emit(reply, total)
        except Exception as e:
            self.error.emit(str(e))


class _SessionConfigDialog(QDialog):
    """对话配置：3 个文件路径"""

    def __init__(self, session: ChatSession, parent=None):
        super().__init__(parent)
        self.setWindowTitle("对话配置")
        self.setMinimumWidth(480)
        self.session = session

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        grid = QGridLayout()
        grid.setSpacing(8)
        grid.setColumnStretch(1, 1)

        # Notes
        grid.addWidget(QLabel("笔记 (notes.md):"), 0, 0)
        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("选择笔记文件...")
        self.notes_edit.setText(session.notes_path)
        grid.addWidget(self.notes_edit, 0, 1)
        btn_notes = QPushButton("浏览")
        btn_notes.setProperty("class", "secondary")
        btn_notes.setFixedWidth(56)
        btn_notes.clicked.connect(lambda: self._browse(self.notes_edit, "笔记文件", "Markdown (*.md);;所有文件 (*)"))
        grid.addWidget(btn_notes, 0, 2)

        # Slides
        grid.addWidget(QLabel("幻灯片 (slides.json):"), 1, 0)
        self.slides_edit = QLineEdit()
        self.slides_edit.setPlaceholderText("选择幻灯片文件...")
        self.slides_edit.setText(session.slides_path)
        grid.addWidget(self.slides_edit, 1, 1)
        btn_slides = QPushButton("浏览")
        btn_slides.setProperty("class", "secondary")
        btn_slides.setFixedWidth(56)
        btn_slides.clicked.connect(lambda: self._browse(self.slides_edit, "幻灯片文件", "JSON (*.json)"))
        grid.addWidget(btn_slides, 1, 2)

        # Transcript
        grid.addWidget(QLabel("转录 (transcript.json):"), 2, 0)
        self.transcript_edit = QLineEdit()
        self.transcript_edit.setPlaceholderText("选择转录文件...")
        self.transcript_edit.setText(session.transcript_path)
        grid.addWidget(self.transcript_edit, 2, 1)
        btn_trans = QPushButton("浏览")
        btn_trans.setProperty("class", "secondary")
        btn_trans.setFixedWidth(56)
        btn_trans.clicked.connect(lambda: self._browse(self.transcript_edit, "转录文件", "JSON (*.json)"))
        grid.addWidget(btn_trans, 2, 2)

        layout.addLayout(grid)

        hint = QLabel("文件路径可以为空，有笔记时笔记内容将作为对话首条消息显示。")
        hint.setProperty("class", "hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bbox.accepted.connect(self.accept)
        bbox.rejected.connect(self.reject)
        layout.addWidget(bbox)

    def _browse(self, edit: QLineEdit, title: str, filter: str):
        path, _ = QFileDialog.getOpenFileName(self, title, "", filter)
        if path:
            edit.setText(path)

    def get_paths(self) -> tuple:
        return (
            self.notes_edit.text().strip(),
            self.slides_edit.text().strip(),
            self.transcript_edit.text().strip(),
        )


class ChatWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.session: Optional[ChatSession] = None
        self._worker: Optional[_ChatWorker] = None
        self._provider_config: dict = {}
        self._all_providers: list = []
        self._output_dir: str = ""
        self._thinking_timer = QTimer(self)
        self._thinking_timer.setInterval(150)
        self._thinking_timer.timeout.connect(self._tick_thinking)
        self._thinking_frame = 0
        self._thinking_start = 0.0
        self._thinking_bubble: Optional[MessageBubble] = None
        self._build_ui()

    def _build_ui(self):
        # ─── 左侧：session 列表 ───
        left_panel = QWidget()
        left_panel.setProperty("class", "chat-sidebar")
        left_panel.setMinimumWidth(140)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # 顶部按钮行
        top_bar = QWidget()
        top_bar.setProperty("class", "chat-sidebar-top")
        top_bar.setFixedHeight(36)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(8, 4, 8, 4)

        title = QLabel("对话历史")
        title.setProperty("class", "sidebar-title")
        top_layout.addWidget(title)
        top_layout.addStretch()

        self.btn_new_chat = QPushButton("＋")
        self.btn_new_chat.setFixedSize(32, 28)
        self.btn_new_chat.setProperty("class", "secondary")
        self.btn_new_chat.setToolTip("新建对话")
        self.btn_new_chat.clicked.connect(self._on_new_chat)
        top_layout.addWidget(self.btn_new_chat)

        left_layout.addWidget(top_bar)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setProperty("class", "chat-sep")
        sep.setFixedHeight(1)
        left_layout.addWidget(sep)

        self.project_list = QListWidget()
        self.project_list.setProperty("class", "project-list")
        self.project_list.currentRowChanged.connect(self._on_session_selected)
        self.project_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.project_list.customContextMenuRequested.connect(self._on_session_context_menu)
        left_layout.addWidget(self.project_list, 1)

        # ─── 右侧：聊天区 ───
        right_panel = QWidget()
        right_panel.setProperty("class", "chat-right")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # 状态栏：session 名 + 齿轮按钮
        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)

        self.status_label = QLabel("选择或新建一个对话")
        self.status_label.setProperty("class", "chat-status")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFixedHeight(32)
        status_row.addWidget(self.status_label, 1)

        self.btn_config = QPushButton("⚙")
        self.btn_config.setFixedSize(28, 28)
        self.btn_config.setProperty("class", "secondary")
        self.btn_config.setToolTip("配置关联文件")
        self.btn_config.clicked.connect(self._on_config)
        status_row.addWidget(self.btn_config)

        right_layout.addLayout(status_row)

        # 关联文件指示
        self.files_label = QLabel("")
        self.files_label.setProperty("class", "hint")
        self.files_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.files_label.setFixedHeight(22)
        right_layout.addWidget(self.files_label)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setProperty("class", "chat-sep")
        sep2.setFixedHeight(1)
        right_layout.addWidget(sep2)

        # 消息列表
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.messages_widget = QWidget()
        self.messages_widget.setProperty("class", "chat-messages")
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.messages_layout.setSpacing(16)
        self.messages_layout.setContentsMargins(20, 16, 20, 16)
        self.messages_layout.addStretch()

        self.scroll.setWidget(self.messages_widget)
        right_layout.addWidget(self.scroll, 1)

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setProperty("class", "chat-sep")
        sep3.setFixedHeight(1)
        right_layout.addWidget(sep3)

        # 输入区域
        input_bar = QWidget()
        input_bar.setProperty("class", "chat-input-bar")
        input_layout = QVBoxLayout(input_bar)
        input_layout.setContentsMargins(16, 10, 16, 10)
        input_layout.setSpacing(8)

        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("输入你的问题...")
        self.input_edit.setFixedHeight(72)
        self.input_edit.setMaximumHeight(100)
        input_layout.addWidget(self.input_edit)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        self.token_label = QLabel("")
        self.token_label.setProperty("class", "hint")
        bottom_row.addWidget(self.token_label)
        bottom_row.addStretch()

        self.model_combo = QComboBox()
        self.model_combo.setProperty("class", "chat-model-combo")
        self.model_combo.setFixedWidth(160)
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        bottom_row.addWidget(self.model_combo)

        self.send_btn = QPushButton("发送")
        self.send_btn.setFixedWidth(80)
        self.send_btn.clicked.connect(self._on_send)
        bottom_row.addWidget(self.send_btn)

        input_layout.addLayout(bottom_row)
        right_layout.addWidget(input_bar)

        # 用 Splitter 支持拖拽调整侧边栏宽度
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(3)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([220, 600])
        splitter.setStretchFactor(1, 1)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(splitter)

    # ─── 模型切换 ───

    def set_providers(self, providers: list):
        self._all_providers = [dict(p) for p in providers if p.get("api_key")]
        self._refresh_model_combo()

    def apply_font_settings(self, family: str, scale: int):
        MessageBubble.set_chat_font(family, scale)
        # 刷新已有气泡的字体
        for i in range(self.messages_layout.count()):
            item = self.messages_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), MessageBubble):
                item.widget()._apply_font()

    def _refresh_model_combo(self):
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for p in self._all_providers:
            self.model_combo.addItem(f"{p.get('name','')}: {p.get('model','')}", p)
        if self._provider_config:
            for i in range(self.model_combo.count()):
                if self.model_combo.itemData(i).get("base_url") == self._provider_config.get("base_url") \
                   and self.model_combo.itemData(i).get("model") == self._provider_config.get("model"):
                    self.model_combo.setCurrentIndex(i)
                    break
        self.model_combo.blockSignals(False)

    def _on_model_changed(self, index: int):
        if index < 0:
            return
        config = self.model_combo.itemData(index)
        if config:
            self._provider_config = config
            if self.session:
                self.session.provider = config
                self.session.base_url = config.get("base_url", "").rstrip("/")
                self.session.api_key = config.get("api_key", "")
                self.session.model = config.get("model", "")

    # ─── Session 列表 ───

    def refresh_session_list(self, provider_config: dict):
        self._provider_config = provider_config
        self.project_list.clear()

        sessions = list_sessions()
        for s in sessions:
            rounds_str = f" ({s['rounds']}轮)" if s["rounds"] > 0 else ""
            label = f"{s['name']}{rounds_str}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, s)
            self.project_list.addItem(item)

    def _on_session_selected(self, row: int):
        if row < 0:
            return
        item = self.project_list.item(row)
        info = item.data(Qt.ItemDataRole.UserRole)
        if not info:
            return

        session_dir = info["session_dir"]
        self.session = ChatSession(session_dir, self._provider_config)
        self.session._load_history()

        # 更新状态
        n_msgs = sum(1 for m in self.session.messages if m.get("role") == "user")
        self.status_label.setText(f"{self.session.name} | {self.session.model} | {n_msgs} 轮")
        self._update_files_label()
        self._restore_history()

    def _update_files_label(self):
        parts = []
        if self.session:
            if self.session.notes_path and os.path.exists(self.session.notes_path):
                parts.append("notes ✓")
            else:
                parts.append("notes ✗")
            if self.session.slides_path and os.path.exists(self.session.slides_path):
                parts.append("slides ✓")
            else:
                parts.append("slides ✗")
            if self.session.transcript_path and os.path.exists(self.session.transcript_path):
                parts.append("transcript ✓")
            else:
                parts.append("transcript ✗")
        self.files_label.setText("  |  ".join(parts))

    def _on_session_context_menu(self, pos):
        item = self.project_list.itemAt(pos)
        if not item:
            return
        info = item.data(Qt.ItemDataRole.UserRole)
        session_dir = info.get("session_dir", "")
        hfile = os.path.join(session_dir, "chat_history.json")

        menu = QMenu(self)
        if os.path.isfile(hfile):
            del_action = menu.addAction("删除此对话")
        else:
            return

        action = menu.exec(self.project_list.mapToGlobal(pos))
        if action == del_action:
            if self.session and self.session.session_dir == session_dir:
                self.session = None
                self._clear_messages()
                self.status_label.setText("选择或新建一个对话")
                self.files_label.setText("")
            import shutil
            shutil.rmtree(session_dir, ignore_errors=True)
            row = self.project_list.row(item)
            self.project_list.takeItem(row)

    # ─── 新建对话 ───

    def _on_new_chat(self):
        session = create_empty_session(self._provider_config)
        self.session = session

        # 刷新列表并选中新 session
        self.refresh_session_list(self._provider_config)
        for i in range(self.project_list.count()):
            item = self.project_list.item(i)
            info = item.data(Qt.ItemDataRole.UserRole)
            if info and info["session_dir"] == session.session_dir:
                self.project_list.setCurrentRow(i)
                break

        self.status_label.setText(f"{session.name} | 点击 ⚙ 配置文件")
        self.files_label.setText("notes ✗  |  slides ✗  |  transcript ✗")
        self._clear_messages()

    # ─── 齿轮配置 ───

    def _on_config(self):
        if not self.session:
            self.status_label.setText("请先选择或新建一个对话")
            return

        dlg = _SessionConfigDialog(self.session, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        notes_path, slides_path, transcript_path = dlg.get_paths()
        self.session.update_files(notes_path, slides_path, transcript_path)

        # 刷新 UI
        self._update_files_label()
        self._restore_history()
        self._refresh_session_name()

        n_msgs = sum(1 for m in self.session.messages if m.get("role") == "user")
        self.status_label.setText(f"{self.session.name} | {self.session.model} | {n_msgs} 轮")

    def _refresh_session_name(self):
        row = self.project_list.currentRow()
        if row < 0:
            return
        item = self.project_list.item(row)
        info = item.data(Qt.ItemDataRole.UserRole)
        if not info:
            return
        rounds = sum(1 for m in self.session.messages if m.get("role") == "user") if self.session else 0
        name = self.session.name if self.session else info.get("name", "")
        label = f"{name} ({rounds}轮)" if rounds > 0 else name
        item.setText(label)
        # 更新 data
        info["name"] = name
        if self.session:
            info["notes_path"] = self.session.notes_path
            info["slides_path"] = self.session.slides_path
            info["transcript_path"] = self.session.transcript_path
        item.setData(Qt.ItemDataRole.UserRole, info)

    # ─── 外部接口（Step 5 跳转） ───

    def init_session(self, project_dir: str, provider_config: dict,
                     notes_path: str = "", slides_path: str = "",
                     transcript_path: str = ""):
        from src.chat import create_session
        self._provider_config = provider_config
        output_dir = str(Path(project_dir).parent)
        self._output_dir = output_dir

        video_name = os.path.basename(project_dir)
        session = create_session(
            project_dir, video_name, notes_path, provider_config,
        )
        self.session = session

        self.refresh_session_list(provider_config)
        for i in range(self.project_list.count()):
            item = self.project_list.item(i)
            info = item.data(Qt.ItemDataRole.UserRole)
            if info and info["session_dir"] == session.session_dir:
                self.project_list.setCurrentRow(i)
                break

    # ─── 消息 ───

    def _restore_history(self):
        self._clear_messages()
        if not self.session:
            return
        for msg in self.session.messages:
            self._add_bubble(msg["role"], msg["content"])

    def _on_send(self):
        if not self.session:
            return
        text = self.input_edit.toPlainText().strip()
        if not text:
            return

        self.input_edit.clear()
        self._add_bubble("user", text)

        self.send_btn.setEnabled(False)
        self.input_edit.setEnabled(False)
        self.model_combo.setEnabled(False)

        self._thinking_bubble = MessageBubble("assistant", "")
        self._insert_widget(self._thinking_bubble)
        self._thinking_start = __import__("time").time()
        self._thinking_frame = 0
        self._thinking_timer.start()

        self._worker = _ChatWorker(self.session, text)
        self._worker.finished.connect(self._on_reply)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _tick_thinking(self):
        if not self._thinking_bubble:
            return
        import time
        elapsed = time.time() - self._thinking_start
        s = int(elapsed)
        t = f"{s // 60}m{s % 60:02d}s" if s >= 60 else f"{s}s"
        frame = _THINKING_FRAMES[self._thinking_frame % len(_THINKING_FRAMES)]
        self._thinking_frame += 1
        self._thinking_bubble.setText(f"{frame} 思考中... {t}")
        self._scroll_to_bottom()

    def _stop_thinking(self):
        self._thinking_timer.stop()
        if self._thinking_bubble:
            idx = self.messages_layout.indexOf(self._thinking_bubble)
            if idx >= 0:
                self.messages_layout.takeAt(idx)
            self._thinking_bubble.setParent(None)
            self._thinking_bubble.deleteLater()
            self._thinking_bubble = None

    def _on_reply(self, reply: str, total_chars: int):
        self._stop_thinking()
        self._add_bubble("assistant", reply)
        self.send_btn.setEnabled(True)
        self.input_edit.setEnabled(True)
        self.model_combo.setEnabled(True)
        self.input_edit.setFocus()

        import time
        elapsed = time.time() - self._thinking_start
        n_msgs = sum(1 for m in self.session.messages if m.get("role") == "user")
        self.status_label.setText(
            f"{self.session.name} | {self.session.model} | {n_msgs} 轮"
        )
        self.token_label.setText(f"~{total_chars} chars | {elapsed:.1f}s")
        self._update_current_item_rounds(n_msgs)

    def _on_error(self, err: str):
        self._stop_thinking()
        self._add_bubble("assistant", f"[错误] {err}")
        self.send_btn.setEnabled(True)
        self.input_edit.setEnabled(True)
        self.model_combo.setEnabled(True)
        self.status_label.setText(f"请求失败: {err[:60]}")

    def _update_current_item_rounds(self, rounds: int):
        row = self.project_list.currentRow()
        if row < 0:
            return
        item = self.project_list.item(row)
        info = item.data(Qt.ItemDataRole.UserRole)
        if not info:
            return
        base = info.get("name", "")
        label = f"{base} ({rounds}轮)" if rounds > 0 else base
        item.setText(label)

    # ─── UI 工具 ───

    def _get_bubble_max_width(self) -> int:
        viewport_w = self.scroll.viewport().width()
        return max(viewport_w - 32, 200)

    def _insert_widget(self, widget):
        if isinstance(widget, MessageBubble):
            widget.setMaximumWidth(self._get_bubble_max_width())
        idx = self.messages_layout.count() - 1
        self.messages_layout.insertWidget(idx, widget)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _add_bubble(self, role: str, text: str):
        bubble = MessageBubble(role, text)
        self._insert_widget(bubble)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        max_w = self._get_bubble_max_width()
        for i in range(self.messages_layout.count()):
            item = self.messages_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), MessageBubble):
                item.widget().setMaximumWidth(max_w)

    def _scroll_to_bottom(self):
        sb = self.scroll.verticalScrollBar()
        # 只在用户接近底部时自动滚动，避免抢夺滚动控制权
        at_bottom = sb.value() >= sb.maximum() - 60
        if at_bottom:
            sb.setValue(sb.maximum())

    def _clear_messages(self):
        while self.messages_layout.count() > 1:
            item = self.messages_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
