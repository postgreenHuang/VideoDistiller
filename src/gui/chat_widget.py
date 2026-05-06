"""
Video-Distiller AI 对话界面
- 左侧：session 列表（按时间排序，显示关联文件状态）
- 右侧：消息气泡 + 模型切换 + 齿轮配置 + 新建对话
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QSize, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QFontDatabase, QTextDocument
from PySide6.QtWidgets import (
    QTreeWidgetItemIterator,
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QTextBrowser, QScrollArea, QSizePolicy,
    QTreeWidget, QTreeWidgetItem, QFrame, QComboBox, QFileDialog,
    QMenu, QDialog, QGridLayout, QLineEdit, QDialogButtonBox,
    QInputDialog, QSplitter, QHeaderView,
)

from src.chat import ChatSession, create_empty_session, list_sessions


_THINKING_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class _ImageViewerDialog(QDialog):
    """点击图片后弹出的大图查看器"""
    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(os.path.basename(image_path))
        from PySide6.QtGui import QPixmap
        from PySide6.QtWidgets import QApplication

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        pixmap = QPixmap(image_path)
        screen = QApplication.primaryScreen().availableGeometry()
        max_w = int(screen.width() * 0.85)
        max_h = int(screen.height() * 0.85)
        if pixmap.width() > max_w or pixmap.height() > max_h:
            pixmap = pixmap.scaled(max_w, max_h,
                                   Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)

        label = QLabel()
        label.setPixmap(pixmap)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("background: #1a1a1a;")
        layout.addWidget(label)
        self.resize(pixmap.size())


class MessageBubble(QTextBrowser):
    _font_family = ""
    _font_scale = 100
    _base_dir = ""
    _img_paths: dict = {}  # src_name → abs_path

    def __init__(self, role: str, text: str):
        super().__init__()
        self.setProperty("class", f"msg-{role}")
        self.setReadOnly(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setOpenExternalLinks(False)
        self.setOpenLinks(False)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self._raw_text = text

        html, img_map = self._render_md(text, self._font_family, self._font_scale)
        # 预加载图片到文档资源缓存（在 setHtml 之前）
        self._preload_images(img_map)
        self.setHtml(html)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self._sync_widget_font()
        self.document().documentLayout().documentSizeChanged.connect(self._adjust_size)
        self.anchorClicked.connect(self._on_anchor_clicked)

    # ─── 尺寸自适应 ───

    def _adjust_size(self):
        doc_h = int(self.document().documentLayout().documentSize().height())
        target = doc_h + 26
        if abs(self.height() - target) > 2:
            self.setFixedHeight(target)
            self.updateGeometry()

    # ─── 图片预加载到文档资源缓存 ───

    def _preload_images(self, img_map: dict):
        """在 setHtml 之前，把图片作为 ImageResource 注入文档缓存"""
        from PySide6.QtGui import QPixmap
        from PySide6.QtCore import QUrl

        doc = self.document()
        for src_key, abs_path in img_map.items():
            pix = QPixmap(abs_path)
            if not pix.isNull():
                url = QUrl(src_key)
                doc.addResource(QTextDocument.ResourceType.ImageResource, url, pix)

    # ─── 图片点击查看大图 ───

    def _on_anchor_clicked(self, url):
        path = url.toLocalFile()
        if not path and url.scheme() == "imgview":
            path = url.path()
            if sys.platform == "win32" and path.startswith("/"):
                path = path[1:]
        if path and os.path.isfile(path):
            dlg = _ImageViewerDialog(path, self.window())
            dlg.exec()

    # ─── Markdown → HTML 渲染 ───

    @staticmethod
    def _find_image(src: str) -> str:
        """在 base_dir 的 frames/ 和 key_frames/ 子目录中搜索图片，返回绝对路径或空串"""
        if not MessageBubble._base_dir:
            return ""
        for subdir in ("frames", "key_frames", ""):
            full = os.path.join(MessageBubble._base_dir, subdir, src) if subdir else os.path.join(MessageBubble._base_dir, src)
            if os.path.isfile(full):
                return full
        return ""

    @staticmethod
    def _render_md(text: str, font_family: str, font_scale: int) -> tuple:
        """返回 (html, img_map)，img_map = {src_key: abs_path}"""
        import re
        from PySide6.QtGui import QFont

        base_px = 14.0 * font_scale / 100.0
        family = font_family if font_family else ("PingFang SC" if sys.platform == "darwin" else "Microsoft YaHei UI")
        font = QFont(family)
        font.setPixelSize(int(base_px))

        # 预处理：把 "XX_XX_frame.jpg (描述)" 转为 "![描述](XX_XX_frame.jpg)"
        text = re.sub(
            r'(\d{2}_\d{2}_frame\.(?:jpg|jpeg|png))\s*\(([^)]+)\)',
            r'![\2](\1)',
            text,
        )

        # 收集图片路径，生成唯一 src key
        img_map = {}  # src_key → abs_path
        img_counter = [0]

        def _resolve_md_img(m):
            alt, src = m.group(1), m.group(2)
            if src.startswith(("http://", "https://", "data:")):
                return m.group(0)
            # file:/// 绝对路径：提取本地路径
            if src.startswith("file:///"):
                local = src[8:]
                if os.path.isfile(local):
                    key = f"img_{img_counter[0]}"
                    img_counter[0] += 1
                    img_map[key] = local
                    return f"![{alt}]({key})"
                return m.group(0)
            # 相对路径：搜索 frames/ 和 key_frames/
            abs_path = MessageBubble._find_image(src)
            if abs_path:
                key = f"img_{img_counter[0]}"
                img_counter[0] += 1
                img_map[key] = abs_path
                return f"![{alt}]({key})"
            return m.group(0)

        text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _resolve_md_img, text)

        doc = QTextDocument()
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

        # 把连续的 <p><img/></p> 合并为横向可点击的图片行
        html = MessageBubble._group_consecutive_images(html, img_map)
        return html, img_map

    @staticmethod
    def _group_consecutive_images(html: str, img_map: dict) -> str:
        import re
        img_p = re.compile(r'<p\s[^>]*>(?:\s*<img\s[^>]*>\s*)+</p>')

        last_end = 0
        chunks = []
        for m in img_p.finditer(html):
            if m.start() > last_end:
                chunks.append(('text', html[last_end:m.start()]))
            srcs = re.findall(r'<img\s[^>]*?src="([^"]*)"', m.group(0))
            chunks.append(('imgs', srcs))
            last_end = m.end()
        if last_end < len(html):
            chunks.append(('text', html[last_end:]))

        result_parts = []
        img_buf = []
        for typ, content in chunks:
            if typ == 'imgs':
                img_buf.extend(content)
            else:
                if not content.strip() and img_buf:
                    continue
                if img_buf:
                    result_parts.append(MessageBubble._make_img_row(img_buf, img_map))
                    img_buf = []
                result_parts.append(content)
        if img_buf:
            result_parts.append(MessageBubble._make_img_row(img_buf, img_map))
        return ''.join(result_parts)

    @staticmethod
    def _make_img_row(srcs: list, img_map: dict) -> str:
        items = []
        for src in srcs:
            abs_path = img_map.get(src, "")
            if abs_path:
                href = "imgview:///" + abs_path.replace(os.sep, "/")
            else:
                href = src
            items.append(
                f'<a href="{href}">'
                f'<img src="{src}" width="200" />'
                f'</a> '
            )
        return '<p style="margin-top:4px; margin-bottom:4px;">' + ''.join(items) + '</p>'

    def _apply_font(self):
        html, img_map = self._render_md(self._raw_text, self._font_family, self._font_scale)
        self._preload_images(img_map)
        self.setHtml(html)
        self._sync_widget_font()

    def _sync_widget_font(self):
        base_px = 14.0 * self._font_scale / 100.0
        family = self._font_family if self._font_family else ("PingFang SC" if sys.platform == "darwin" else "Microsoft YaHei UI")
        font = QFont(family)
        font.setPixelSize(int(base_px))
        self.document().setDefaultFont(font)

    @classmethod
    def set_chat_font(cls, family: str, scale: int):
        cls._font_family = family
        cls._font_scale = scale

    @classmethod
    def set_base_dir(cls, base_dir: str):
        cls._base_dir = base_dir


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
    """对话配置：笔记 + 数据文件"""

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

        # Data JSON (统一 JSON 或 slides.json)
        grid.addWidget(QLabel("数据文件 (JSON):"), 1, 0)
        self.data_edit = QLineEdit()
        self.data_edit.setPlaceholderText("统一 JSON 或 slides.json...")
        self.data_edit.setText(session.slides_path)
        grid.addWidget(self.data_edit, 1, 1)
        btn_data = QPushButton("浏览")
        btn_data.setProperty("class", "secondary")
        btn_data.setFixedWidth(56)
        btn_data.clicked.connect(lambda: self._browse(self.data_edit, "数据文件", "JSON (*.json)"))
        grid.addWidget(btn_data, 1, 2)

        layout.addLayout(grid)

        hint = QLabel("数据文件可包含幻灯片和转录内容。有笔记时笔记将作为对话首条消息显示。")
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
            self.data_edit.text().strip(),
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

        self.btn_new_folder = QPushButton("📁")
        self.btn_new_folder.setFixedSize(28, 28)
        self.btn_new_folder.setProperty("class", "secondary")
        self.btn_new_folder.setToolTip("新建文件夹")
        self.btn_new_folder.clicked.connect(self._on_new_folder)
        top_layout.addWidget(self.btn_new_folder)

        self.btn_new_chat = QPushButton("＋")
        self.btn_new_chat.setFixedSize(28, 28)
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

        self.session_tree = QTreeWidget()
        self.session_tree.setProperty("class", "session-tree")
        self.session_tree.setHeaderHidden(True)
        self.session_tree.setIndentation(16)
        self.session_tree.setAnimated(True)
        self.session_tree.setSelectionMode(
            QTreeWidget.SelectionMode.ExtendedSelection
        )
        self.session_tree.currentItemChanged.connect(self._on_tree_item_changed)
        self.session_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.session_tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        left_layout.addWidget(self.session_tree, 1)

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
        self.input_edit.installEventFilter(self)
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
        self._build_session_tree()

    def _build_session_tree(self):
        """重建侧边栏树：文件夹 → 对话"""
        self.session_tree.clear()
        from src.chat import load_folders
        folders = load_folders()
        sessions = list_sessions()

        # 按 folder_id 分组
        grouped: dict[str, list] = {}
        ungrouped: list = []
        for s in sessions:
            fid = s.get("folder_id", "")
            if fid:
                grouped.setdefault(fid, []).append(s)
            else:
                ungrouped.append(s)

        # 创建文件夹节点
        for f in folders:
            fid = f["id"]
            folder_item = QTreeWidgetItem(self.session_tree, [f["name"]])
            folder_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "folder", "folder_id": fid})
            folder_item.setExpanded(True)
            font = folder_item.font(0)
            font.setBold(True)
            folder_item.setFont(0, font)
            for s in grouped.get(fid, []):
                self._add_session_item(folder_item, s)

        # 未分组
        if ungrouped or not folders:
            ungrouped_item = QTreeWidgetItem(self.session_tree, ["未分组"])
            ungrouped_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "folder", "folder_id": ""})
            ungrouped_item.setExpanded(True)
            font = ungrouped_item.font(0)
            font.setBold(True)
            ungrouped_item.setFont(0, font)
            for s in ungrouped:
                self._add_session_item(ungrouped_item, s)

    def _add_session_item(self, parent: QTreeWidgetItem, s: dict):
        rounds_str = f" ({s['rounds']}轮)" if s["rounds"] > 0 else ""
        label = f"{s['name']}{rounds_str}"
        item = QTreeWidgetItem(parent, [label])
        item.setData(0, Qt.ItemDataRole.UserRole, {"type": "session", **s})

    def _on_tree_item_changed(self, current: QTreeWidgetItem, _prev):
        if not current:
            return
        data = current.data(0, Qt.ItemDataRole.UserRole)
        if not data or data.get("type") != "session":
            return
        info = data
        session_dir = info["session_dir"]
        self.session = ChatSession(session_dir, self._provider_config)
        self.session._load_history()

        # 推导项目目录作为图片解析的 base_dir
        base_dir = ""
        if self.session.notes_path and os.path.exists(self.session.notes_path):
            base_dir = str(Path(self.session.notes_path).parent.parent)
        elif self.session.slides_path and os.path.exists(self.session.slides_path):
            base_dir = str(Path(self.session.slides_path).parent)
        MessageBubble.set_base_dir(base_dir)

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
                parts.append("数据 ✓")
            else:
                parts.append("数据 ✗")
        self.files_label.setText("  |  ".join(parts))

    def _on_tree_context_menu(self, pos):
        item = self.session_tree.itemAt(pos)
        menu = QMenu(self)

        if not item:
            # 空白处：新建文件夹
            menu.addAction("新建文件夹", self._on_new_folder)
            menu.exec(self.session_tree.mapToGlobal(pos))
            return

        data = item.data(0, Qt.ItemDataRole.UserRole)

        if data.get("type") == "folder":
            folder_id = data.get("folder_id", "")
            if folder_id:  # 非默认"未分组"
                menu.addAction("重命名", lambda: self._rename_folder(folder_id, item))
                menu.addAction("删除文件夹", lambda: self._delete_folder(folder_id))
            else:
                menu.addAction("新建文件夹", self._on_new_folder)
            menu.exec(self.session_tree.mapToGlobal(pos))
            return

        # Session 项（支持多选）
        selected = self.session_tree.selectedItems()
        session_items = [si for si in selected
                         if si.data(0, Qt.ItemDataRole.UserRole).get("type") == "session"]

        if not session_items:
            return

        # 移动到子菜单
        from src.chat import load_folders
        folders = load_folders()
        if folders:
            move_menu = menu.addMenu("移动到")
            for f in folders:
                move_menu.addAction(f["name"],
                                    lambda checked=False, fid=f["id"]: self._move_to_folder(session_items, fid))
            move_menu.addAction("未分组",
                                lambda checked=False: self._move_to_folder(session_items, ""))

        # 批量删除
        n = len(session_items)
        label = f"删除选中的 {n} 个对话" if n > 1 else "删除此对话"
        menu.addAction(label, lambda: self._delete_sessions(session_items))

        menu.exec(self.session_tree.mapToGlobal(pos))

    def _on_new_folder(self):
        name, ok = QInputDialog.getText(self, "新建文件夹", "文件夹名称：")
        if not ok or not name.strip():
            return
        from src.chat import load_folders, save_folders
        folders = load_folders()
        fid = f"f{len(folders) + 1}_{int(datetime.now().timestamp())}"
        folders.append({"id": fid, "name": name.strip(), "order": len(folders)})
        save_folders(folders)
        self._build_session_tree()

    def _rename_folder(self, folder_id: str, item: QTreeWidgetItem):
        old_name = item.text(0)
        name, ok = QInputDialog.getText(self, "重命名文件夹", "新名称：", text=old_name)
        if not ok or not name.strip():
            return
        from src.chat import load_folders, save_folders
        folders = load_folders()
        for f in folders:
            if f["id"] == folder_id:
                f["name"] = name.strip()
                break
        save_folders(folders)
        self._build_session_tree()

    def _delete_folder(self, folder_id: str):
        """删除文件夹，对话移回未分组"""
        from src.chat import load_folders, save_folders
        folders = load_folders()
        folders = [f for f in folders if f["id"] != folder_id]
        save_folders(folders)
        # 将该文件夹下所有 session 的 folder_id 清空
        sessions = list_sessions()
        for s in sessions:
            if s.get("folder_id") == folder_id:
                sdir = s["session_dir"]
                hfile = os.path.join(sdir, "chat_history.json")
                try:
                    d = json.loads(Path(hfile).read_text(encoding="utf-8"))
                    d["folder_id"] = ""
                    Path(hfile).write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
                except Exception:
                    pass
        self._build_session_tree()

    def _move_to_folder(self, items: list, folder_id: str):
        for item in items:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data.get("type") != "session":
                continue
            sdir = data["session_dir"]
            hfile = os.path.join(sdir, "chat_history.json")
            try:
                d = json.loads(Path(hfile).read_text(encoding="utf-8"))
                d["folder_id"] = folder_id
                Path(hfile).write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
        self._build_session_tree()

    def _delete_sessions(self, items: list):
        import shutil
        for item in items:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data.get("type") != "session":
                continue
            session_dir = data["session_dir"]
            if self.session and self.session.session_dir == session_dir:
                self.session = None
                self._clear_messages()
                self.status_label.setText("选择或新建一个对话")
                self.files_label.setText("")
            shutil.rmtree(session_dir, ignore_errors=True)
        self._build_session_tree()

    # ─── 新建对话 ───

    def _on_new_chat(self):
        session = create_empty_session(self._provider_config)
        self.session = session

        self._build_session_tree()
        self._select_session_in_tree(session.session_dir)

        self.status_label.setText(f"{session.name} | 点击 ⚙ 配置文件")
        self.files_label.setText("notes ✗  |  数据 ✗")
        self._clear_messages()

    def _select_session_in_tree(self, session_dir: str):
        """在树中选中指定 session"""
        it = QTreeWidgetItemIterator(self.session_tree)
        while it.value():
            item = it.value()
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data and data.get("type") == "session" and data.get("session_dir") == session_dir:
                self.session_tree.setCurrentItem(item)
                return
            it.__next__()

    def _select_first_session(self):
        """选中树中第一个 session"""
        it = QTreeWidgetItemIterator(self.session_tree)
        while it.value():
            item = it.value()
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data and data.get("type") == "session":
                self.session_tree.setCurrentItem(item)
                return
            it.__next__()

    # ─── 齿轮配置 ───

    def _on_config(self):
        if not self.session:
            self.status_label.setText("请先选择或新建一个对话")
            return

        dlg = _SessionConfigDialog(self.session, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        notes_path, data_path = dlg.get_paths()
        self.session.update_files(notes_path, data_path)

        # 刷新 UI
        self._update_files_label()
        self._restore_history()
        self._refresh_session_name()

        n_msgs = sum(1 for m in self.session.messages if m.get("role") == "user")
        self.status_label.setText(f"{self.session.name} | {self.session.model} | {n_msgs} 轮")

    def _refresh_session_name(self):
        item = self.session_tree.currentItem()
        if not item:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data or data.get("type") != "session":
            return
        rounds = sum(1 for m in self.session.messages if m.get("role") == "user") if self.session else 0
        name = self.session.name if self.session else data.get("name", "")
        label = f"{name} ({rounds}轮)" if rounds > 0 else name
        item.setText(0, label)
        data["name"] = name
        if self.session:
            data["notes_path"] = self.session.notes_path
            data["slides_path"] = self.session.slides_path
        item.setData(0, Qt.ItemDataRole.UserRole, data)

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

        self._build_session_tree()
        self._select_session_in_tree(session.session_dir)

    # ─── 消息 ───

    def _restore_history(self):
        self._clear_messages()
        if not self.session:
            return
        for msg in self.session.messages:
            self._add_bubble(msg["role"], msg["content"])

    def eventFilter(self, obj, event):
        if obj is self.input_edit and event.type() == event.Type.KeyPress:
            key = event.key()
            mod = event.modifiers()
            if key == Qt.Key.Key_Return and not (mod & Qt.KeyboardModifier.ShiftModifier or mod & Qt.KeyboardModifier.ControlModifier):
                self._on_send()
                return True
        return super().eventFilter(obj, event)

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
        self.session_tree.setEnabled(False)

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
        self.session_tree.setEnabled(True)
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
        self.session_tree.setEnabled(True)
        self.status_label.setText(f"请求失败: {err[:60]}")

    def _update_current_item_rounds(self, rounds: int):
        item = self.session_tree.currentItem()
        if not item:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data or data.get("type") != "session":
            return
        base = data.get("name", "")
        label = f"{base} ({rounds}轮)" if rounds > 0 else base
        item.setText(0, label)

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
