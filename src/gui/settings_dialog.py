"""
Video-Distiller Settings 对话框
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit,
    QGroupBox, QGridLayout, QListWidget, QListWidgetItem,
    QDialogButtonBox, QSpinBox, QDoubleSpinBox, QMessageBox,
    QScrollArea,
)
from PySide6.QtCore import Qt
from src.config import (
    Settings, save_settings, RESOLUTION_SCALES, WHISPER_MODELS,
    VISION_MODELS_OLLAMA, VISION_MODELS_CLOUD, CLOUD_API_PRESETS,
    ASR_CLOUD_MODELS, ASR_CLOUD_PRESETS,
)


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Settings")
        self.setMinimumSize(560, 560)
        if parent:
            self.setStyleSheet(parent.styleSheet())
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        tabs = QTabWidget()
        tabs.addTab(self._build_general_tab(), "通用")
        tabs.addTab(self._build_providers_tab(), "AI Provider")
        tabs.addTab(self._build_vocab_tab(), "术语词表")
        layout.addWidget(tabs)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    # ─── 通用 Tab ───

    def _build_general_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        scroll.viewport().setStyleSheet("background: transparent;")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setSpacing(6)
        layout.setContentsMargins(0, 0, 4, 0)

        # 默认参数
        g = QGroupBox("默认参数")
        grid = QGridLayout(g)
        grid.setSpacing(6)

        grid.addWidget(QLabel("主题:"), 0, 0)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["light", "dark"])
        grid.addWidget(self.theme_combo, 0, 1)

        grid.addWidget(QLabel("抽帧分辨率:"), 1, 0)
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(RESOLUTION_SCALES)
        grid.addWidget(self.resolution_combo, 1, 1)

        grid.addWidget(QLabel("采样率:"), 2, 0)
        self.sample_rate_spin = QSpinBox()
        self.sample_rate_spin.setRange(8000, 48000)
        self.sample_rate_spin.setSingleStep(1000)
        grid.addWidget(self.sample_rate_spin, 2, 1)

        grid.addWidget(QLabel("抽帧间隔 (fps):"), 3, 0)
        self.fps_spin = QDoubleSpinBox()
        self.fps_spin.setRange(0.1, 10.0)
        self.fps_spin.setSingleStep(0.5)
        self.fps_spin.setValue(1.0)
        grid.addWidget(self.fps_spin, 3, 1)

        grid.addWidget(QLabel("SSIM 阈值:"), 4, 0)
        self.ssim_spin = QDoubleSpinBox()
        self.ssim_spin.setRange(0.80, 0.99)
        self.ssim_spin.setSingleStep(0.01)
        self.ssim_spin.setDecimals(2)
        grid.addWidget(self.ssim_spin, 4, 1)

        grid.addWidget(QLabel("Whisper 模型:"), 5, 0)
        self.whisper_combo = QComboBox()
        self.whisper_combo.addItems(WHISPER_MODELS)
        grid.addWidget(self.whisper_combo, 5, 1)

        grid.addWidget(QLabel("转录分段 (秒):"), 6, 0)
        self.segment_spin = QSpinBox()
        self.segment_spin.setRange(30, 600)
        self.segment_spin.setSingleStep(30)
        self.segment_spin.setValue(180)
        grid.addWidget(self.segment_spin, 6, 1)

        layout.addWidget(g)

        # 语音识别设置
        ag = QGroupBox("语音识别设置")
        agrid = QGridLayout(ag)
        agrid.setSpacing(6)

        agrid.addWidget(QLabel("模式:"), 0, 0)
        self.asr_type_combo = QComboBox()
        self.asr_type_combo.addItems(["本地 faster-whisper", "云端 API"])
        self.asr_type_combo.currentIndexChanged.connect(self._on_asr_type_changed)
        agrid.addWidget(self.asr_type_combo, 0, 1)

        agrid.addWidget(QLabel("API 地址:"), 1, 0)
        self.asr_api_url_edit = QLineEdit()
        self.asr_api_url_edit.setPlaceholderText("https://api.groq.com/openai/v1")
        agrid.addWidget(self.asr_api_url_edit, 1, 1)

        agrid.addWidget(QLabel("API Key:"), 2, 0)
        self.asr_api_key_edit = QLineEdit()
        self.asr_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.asr_api_key_edit.setPlaceholderText("sk-...")
        agrid.addWidget(self.asr_api_key_edit, 2, 1)

        agrid.addWidget(QLabel("云端模型:"), 3, 0)
        self.asr_cloud_model_combo = QComboBox()
        self.asr_cloud_model_combo.setEditable(True)
        self.asr_cloud_model_combo.addItems(ASR_CLOUD_MODELS)
        agrid.addWidget(self.asr_cloud_model_combo, 3, 1)

        layout.addWidget(ag)

        # 图片理解模型
        vg = QGroupBox("图片理解模型")
        vgrid = QGridLayout(vg)
        vgrid.setSpacing(6)

        vgrid.addWidget(QLabel("模式:"), 0, 0)
        self.vision_type_combo = QComboBox()
        self.vision_type_combo.addItems(["Ollama 本地", "云端 API"])
        self.vision_type_combo.currentIndexChanged.connect(self._on_vision_type_changed)
        vgrid.addWidget(self.vision_type_combo, 0, 1)

        vgrid.addWidget(QLabel("模型:"), 1, 0)
        self.vision_model_edit = QLineEdit()
        self.vision_model_edit.setPlaceholderText("minicpm-v:8b")
        vgrid.addWidget(self.vision_model_edit, 1, 1)

        # Ollama 专属行
        vgrid.addWidget(QLabel("Ollama 地址:"), 2, 0)
        self.ollama_url_edit = QLineEdit()
        self.ollama_url_edit.setPlaceholderText("http://localhost:11434")
        vgrid.addWidget(self.ollama_url_edit, 2, 1)

        # 云端 API 专属行
        vgrid.addWidget(QLabel("API 地址:"), 3, 0)
        self.vision_api_url_edit = QLineEdit()
        self.vision_api_url_edit.setPlaceholderText("https://open.bigmodel.cn/api/paas/v4")
        vgrid.addWidget(self.vision_api_url_edit, 3, 1)

        vgrid.addWidget(QLabel("API Key:"), 4, 0)
        self.vision_api_key_edit = QLineEdit()
        self.vision_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.vision_api_key_edit.setPlaceholderText("sk-...")
        vgrid.addWidget(self.vision_api_key_edit, 4, 1)

        layout.addWidget(vg)

        # 视觉分析 Prompt
        vpg = QGroupBox("视觉分析 Prompt (逐张分析图片时使用)")
        vpl = QVBoxLayout(vpg)
        vpl.setSpacing(4)

        vpl.addWidget(QLabel("文字提取 Prompt:"))
        self.vision_ocr_edit = QTextEdit()
        self.vision_ocr_edit.setMaximumHeight(60)
        vpl.addWidget(self.vision_ocr_edit)

        vpl.addWidget(QLabel("图表描述 Prompt:"))
        self.vision_diagram_edit = QTextEdit()
        self.vision_diagram_edit.setMaximumHeight(60)
        vpl.addWidget(self.vision_diagram_edit)

        vpl.addWidget(QLabel("标题概括 Prompt:"))
        self.vision_title_edit = QTextEdit()
        self.vision_title_edit.setMaximumHeight(40)
        vpl.addWidget(self.vision_title_edit)

        layout.addWidget(vpg)

        # 默认蒸馏 Prompt
        pg = QGroupBox("默认蒸馏 Prompt (最终 AI 聚合时使用)")
        pl = QVBoxLayout(pg)
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setMaximumHeight(100)
        pl.addWidget(self.prompt_edit)
        layout.addWidget(pg)

        layout.addStretch()
        scroll.setWidget(content)
        return scroll

    # ─── AI Provider Tab ───

    def _build_providers_tab(self):
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setSpacing(8)

        # 左侧列表
        left = QVBoxLayout()
        left.setSpacing(4)
        left.addWidget(QLabel("已配置的 Provider:"))
        self.provider_list = QListWidget()
        self.provider_list.currentRowChanged.connect(self._on_provider_selected)
        left.addWidget(self.provider_list)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ 新增")
        btn_add.clicked.connect(self._add_provider)
        btn_del = QPushButton("- 删除")
        btn_del.clicked.connect(self._del_provider)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_del)
        left.addLayout(btn_row)
        layout.addLayout(left, stretch=1)

        # 右侧编辑
        right = QVBoxLayout()
        right.setSpacing(6)
        right.addWidget(QLabel("编辑 Provider:"))

        form = QGridLayout()
        form.setSpacing(6)
        form.addWidget(QLabel("名称:"), 0, 0)
        self.prov_name_edit = QLineEdit()
        form.addWidget(self.prov_name_edit, 0, 1)

        form.addWidget(QLabel("Base URL:"), 1, 0)
        self.prov_url_edit = QLineEdit()
        self.prov_url_edit.setPlaceholderText("https://api.example.com")
        form.addWidget(self.prov_url_edit, 1, 1)

        form.addWidget(QLabel("API Key:"), 2, 0)
        self.prov_key_edit = QLineEdit()
        self.prov_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.prov_key_edit.setPlaceholderText("sk-...")
        form.addWidget(self.prov_key_edit, 2, 1)

        form.addWidget(QLabel("Model:"), 3, 0)
        self.prov_model_edit = QLineEdit()
        self.prov_model_edit.setPlaceholderText("gpt-4o / gemini-1.5-pro / ...")
        form.addWidget(self.prov_model_edit, 3, 1)

        right.addLayout(form)
        right.addStretch()
        layout.addLayout(right, stretch=2)

        return w

    # ─── 术语词表 Tab ───

    def _build_vocab_tab(self):
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setSpacing(8)

        # 左侧列表
        left = QVBoxLayout()
        left.setSpacing(4)
        left.addWidget(QLabel("词表列表:"))
        self.vocab_list = QListWidget()
        self.vocab_list.currentRowChanged.connect(self._on_vocab_selected)
        left.addWidget(self.vocab_list)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ 新增")
        btn_add.clicked.connect(self._add_vocab)
        btn_del = QPushButton("- 删除")
        btn_del.clicked.connect(self._del_vocab)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_del)
        left.addLayout(btn_row)
        layout.addLayout(left, stretch=1)

        # 右侧编辑
        right = QVBoxLayout()
        right.setSpacing(6)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("名称:"))
        self.vocab_name_edit = QLineEdit()
        name_row.addWidget(self.vocab_name_edit)
        right.addLayout(name_row)

        right.addWidget(QLabel("术语 (逗号或换行分隔):"))
        self.vocab_terms_edit = QTextEdit()
        self.vocab_terms_edit.setPlaceholderText("Nanite, Lumen, PBR, ECS, ...")
        right.addWidget(self.vocab_terms_edit, stretch=1)

        layout.addLayout(right, stretch=2)

        return w

    # ─── 加载 / 保存 ───

    def _load(self):
        s = self.settings
        self.theme_combo.setCurrentText(s.theme)
        self.resolution_combo.setCurrentText(s.resolution_scale)
        self.sample_rate_spin.setValue(s.sample_rate)
        self.fps_spin.setValue(s.fps)
        self.ssim_spin.setValue(s.ssim_threshold)
        self.whisper_combo.setCurrentText(s.whisper_model)
        self.segment_spin.setValue(s.segment_length)
        self.prompt_edit.setPlainText(s.default_distill_prompt)
        # ASR
        self.asr_type_combo.setCurrentIndex(0 if s.asr_type == "local" else 1)
        self.asr_api_url_edit.setText(s.asr_api_url)
        self.asr_api_key_edit.setText(s.asr_api_key)
        self.asr_cloud_model_combo.setCurrentText(s.asr_cloud_model)
        self._on_asr_type_changed(self.asr_type_combo.currentIndex())
        # Vision
        self.ollama_url_edit.setText(s.ollama_url)
        self.vision_model_edit.setText(s.vision_model)
        self.vision_api_url_edit.setText(s.vision_api_url)
        self.vision_api_key_edit.setText(s.vision_api_key)
        self.vision_type_combo.setCurrentIndex(0 if s.vision_type == "ollama" else 1)
        self._on_vision_type_changed(self.vision_type_combo.currentIndex())
        self.vision_ocr_edit.setPlainText(s.vision_prompt_ocr)
        self.vision_diagram_edit.setPlainText(s.vision_prompt_diagram)
        self.vision_title_edit.setPlainText(s.vision_prompt_title)

        self._providers_data = [dict(p) for p in s.providers]
        self._refresh_provider_list()

        self._vocabs_data = [dict(v) for v in s.vocabularies]
        self._refresh_vocab_list()

    def _save(self):
        self._save_current_provider()
        self._save_current_vocab()

        s = self.settings
        s.theme = self.theme_combo.currentText()
        s.resolution_scale = self.resolution_combo.currentText()
        s.sample_rate = self.sample_rate_spin.value()
        s.fps = self.fps_spin.value()
        s.ssim_threshold = self.ssim_spin.value()
        s.whisper_model = self.whisper_combo.currentText()
        s.segment_length = self.segment_spin.value()
        s.default_distill_prompt = self.prompt_edit.toPlainText()
        # ASR
        s.asr_type = "local" if self.asr_type_combo.currentIndex() == 0 else "cloud"
        s.asr_api_url = self.asr_api_url_edit.text()
        s.asr_api_key = self.asr_api_key_edit.text()
        s.asr_cloud_model = self.asr_cloud_model_combo.currentText()
        # Vision
        s.ollama_url = self.ollama_url_edit.text()
        s.vision_type = "ollama" if self.vision_type_combo.currentIndex() == 0 else "cloud"
        s.vision_model = self.vision_model_edit.text()
        s.vision_api_url = self.vision_api_url_edit.text()
        s.vision_api_key = self.vision_api_key_edit.text()
        s.vision_prompt_ocr = self.vision_ocr_edit.toPlainText()
        s.vision_prompt_diagram = self.vision_diagram_edit.toPlainText()
        s.vision_prompt_title = self.vision_title_edit.toPlainText()
        s.providers = self._providers_data
        s.vocabularies = self._vocabs_data

        save_settings(s)
        self.accept()

    # ─── ASR 模式切换 ───

    def _on_asr_type_changed(self, index):
        is_local = (index == 0)
        agrid = self.asr_api_url_edit.parent().layout()
        for i in range(agrid.count()):
            item = agrid.itemAt(i)
            if item and item.widget():
                row, _, _, _ = agrid.getItemPosition(i)
                if row in (1, 2, 3):
                    item.widget().setVisible(not is_local)

    # ─── 视觉模型模式切换 ───

    def _on_vision_type_changed(self, index):
        is_ollama = (index == 0)
        # Ollama 行: row 2
        self.ollama_url_edit.setVisible(is_ollama)
        # 找到对应 label 并隐藏/显示
        vgrid = self.ollama_url_edit.parent().layout()
        for i in range(vgrid.count()):
            item = vgrid.itemAt(i)
            if item and item.widget():
                row, _, _, _ = vgrid.getItemPosition(i)
                if row == 2:
                    item.widget().setVisible(is_ollama)
                elif row in (3, 4):
                    item.widget().setVisible(not is_ollama)

        # 更新 placeholder
        if is_ollama:
            self.vision_model_edit.setPlaceholderText("minicpm-v:8b")
        else:
            self.vision_model_edit.setPlaceholderText("glm-4v-plus")

    # ─── Provider 管理 ───

    def _refresh_provider_list(self):
        self.provider_list.clear()
        for p in self._providers_data:
            self.provider_list.addItem(p["name"])

    def _on_provider_selected(self, row):
        if row < 0:
            return
        self._save_current_provider()
        p = self._providers_data[row]
        self.prov_name_edit.setText(p.get("name", ""))
        self.prov_url_edit.setText(p.get("base_url", ""))
        self.prov_key_edit.setText(p.get("api_key", ""))
        self.prov_model_edit.setText(p.get("model", ""))

    def _save_current_provider(self):
        row = self.provider_list.currentRow()
        if 0 <= row < len(self._providers_data):
            self._providers_data[row]["name"] = self.prov_name_edit.text()
            self._providers_data[row]["base_url"] = self.prov_url_edit.text()
            self._providers_data[row]["api_key"] = self.prov_key_edit.text()
            self._providers_data[row]["model"] = self.prov_model_edit.text()

    def _add_provider(self):
        self._providers_data.append({"name": "New Provider", "base_url": "", "api_key": "", "model": ""})
        self._refresh_provider_list()
        self.provider_list.setCurrentRow(len(self._providers_data) - 1)

    def _del_provider(self):
        row = self.provider_list.currentRow()
        if 0 <= row < len(self._providers_data):
            self._providers_data.pop(row)
            self._refresh_provider_list()

    # ─── 词表管理 ───

    def _refresh_vocab_list(self):
        self.vocab_list.clear()
        for v in self._vocabs_data:
            self.vocab_list.addItem(v["name"])

    def _on_vocab_selected(self, row):
        if row < 0:
            return
        self._save_current_vocab()
        v = self._vocabs_data[row]
        self.vocab_name_edit.setText(v.get("name", ""))
        self.vocab_terms_edit.setPlainText(v.get("terms", ""))

    def _save_current_vocab(self):
        row = self.vocab_list.currentRow()
        if 0 <= row < len(self._vocabs_data):
            self._vocabs_data[row]["name"] = self.vocab_name_edit.text()
            self._vocabs_data[row]["terms"] = self.vocab_terms_edit.toPlainText()

    def _add_vocab(self):
        self._vocabs_data.append({"name": "新词表", "terms": ""})
        self._refresh_vocab_list()
        self.vocab_list.setCurrentRow(len(self._vocabs_data) - 1)

    def _del_vocab(self):
        row = self.vocab_list.currentRow()
        if 0 <= row < len(self._vocabs_data):
            self._vocabs_data.pop(row)
            self._refresh_vocab_list()
