"""
Video-Distiller 主窗口
PySide6, Apple 风格, Light/Dark 主题, Settings 集成
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QLineEdit,
    QFileDialog, QComboBox, QSlider, QTextEdit,
    QProgressBar, QGroupBox, QGridLayout, QToolBar,
    QToolButton, QSpinBox,
)
from PySide6.QtCore import Qt, QThread, Signal
from src.config import load_settings, Settings, RESOLUTION_SCALES, WHISPER_MODELS
from src.gui.theme import build_stylesheet
from src.gui.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings: Settings = load_settings()
        self._theme = self.settings.theme
        self.setWindowTitle("Video-Distiller")
        self.setMinimumSize(820, 620)
        self.setStyleSheet(build_stylesheet(self._theme))
        self._build_ui()

    # ─── 主题切换 ───

    def _toggle_theme(self):
        self._theme = "dark" if self._theme == "light" else "light"
        self.settings.theme = self._theme
        self.setStyleSheet(build_stylesheet(self._theme))
        self.theme_btn.setText("Light" if self._theme == "dark" else "Dark")
        self._update_dynamic_colors()

    def _update_dynamic_colors(self):
        accent = "#0a84ff" if self._theme == "dark" else "#007aff"
        self.threshold_label.setStyleSheet(f"font-weight: 600; font-size: 13px; color: {accent};")

    def _open_settings(self):
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec() == 1:  # QDialog.Accepted
            self.settings = load_settings()
            if self.settings.theme != self._theme:
                self._theme = self.settings.theme
                self.setStyleSheet(build_stylesheet(self._theme))
                self.theme_btn.setText("Light" if self._theme == "dark" else "Dark")
            self._refresh_from_settings()

    def _refresh_from_settings(self):
        s = self.settings
        idx = self.resolution_combo.findText(s.resolution_scale)
        if idx >= 0:
            self.resolution_combo.setCurrentIndex(idx)
        self.sample_rate_combo.setCurrentText(str(s.sample_rate))
        self._refresh_vocab_combo()
        self._refresh_provider_combo()

    # ─── 构建 UI ───

    def _build_ui(self):
        # 工具栏
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setStyleSheet("border: none; padding: 0 4px;")

        settings_btn = QToolButton()
        settings_btn.setText("Settings")
        settings_btn.clicked.connect(self._open_settings)
        toolbar.addWidget(settings_btn)

        spacer = QWidget()
        spacer.setSizePolicy(
            spacer.sizePolicy().horizontalPolicy().Expanding,
            spacer.sizePolicy().verticalPolicy().Preferred,
        )
        toolbar.addWidget(spacer)
        self.theme_btn = QToolButton()
        self.theme_btn.setText("Dark" if self._theme == "light" else "Light")
        self.theme_btn.clicked.connect(self._toggle_theme)
        toolbar.addWidget(self.theme_btn)
        self.addToolBar(toolbar)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(8)

        layout.addWidget(self._build_path_bar())

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_step1(), "  Step 1  媒体提取  ")
        self.tabs.addTab(self._build_step2(), "  Step 2  图片去重  ")
        self.tabs.addTab(self._build_step3(), "  Step 3  语音转录  ")
        self.tabs.addTab(self._build_step4(), "  Step 4  AI 聚合  ")
        layout.addWidget(self.tabs, stretch=1)

        self.statusBar().showMessage("就绪")

    # ─── 顶部路径栏 ───

    def _build_path_bar(self):
        group = QGroupBox("项目")
        grid = QGridLayout(group)
        grid.setSpacing(6)
        grid.setContentsMargins(12, 14, 12, 8)
        grid.setColumnStretch(1, 1)

        grid.addWidget(self._label("视频路径"), 0, 0)
        self.video_path_edit = QLineEdit()
        self.video_path_edit.setPlaceholderText("选择视频文件...")
        grid.addWidget(self.video_path_edit, 0, 1)
        btn = QPushButton("浏览")
        btn.setProperty("class", "secondary")
        btn.setFixedWidth(72)
        btn.clicked.connect(self._browse_video)
        grid.addWidget(btn, 0, 2)

        grid.addWidget(self._label("输出目录"), 1, 0)
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("选择输出目录...")
        grid.addWidget(self.output_dir_edit, 1, 1)
        btn2 = QPushButton("浏览")
        btn2.setProperty("class", "secondary")
        btn2.setFixedWidth(72)
        btn2.clicked.connect(self._browse_output)
        grid.addWidget(btn2, 1, 2)

        return group

    def _browse_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择视频文件", "",
            "视频文件 (*.mp4 *.mkv *.avi *.mov *.webm);;所有文件 (*)"
        )
        if path:
            self.video_path_edit.setText(path)

    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.output_dir_edit.setText(path)

    # ─── Step 1: 媒体提取 ───

    def _build_step1(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        # 音频
        ag = QGroupBox("音频提取")
        al = QGridLayout(ag)
        al.setSpacing(6)
        al.setContentsMargins(12, 14, 12, 8)
        al.setColumnStretch(1, 1)
        al.addWidget(self._label("采样率"), 0, 0)
        self.sample_rate_combo = QComboBox()
        self.sample_rate_combo.addItems(["8000", "16000", "22050", "44100"])
        self.sample_rate_combo.setCurrentText(str(self.settings.sample_rate))
        al.addWidget(self.sample_rate_combo, 0, 1)
        self.btn_extract_audio = QPushButton("提取 MP3")
        self.btn_extract_audio.setFixedWidth(120)
        self.btn_extract_audio.clicked.connect(self._start_extract_audio)
        al.addWidget(self.btn_extract_audio, 0, 2)
        self.audio_progress = QProgressBar()
        al.addWidget(self.audio_progress, 1, 0, 1, 3)
        self.audio_status = QLabel(" ")
        self.audio_status.setProperty("class", "status")
        al.addWidget(self.audio_status, 2, 0, 1, 3)
        layout.addWidget(ag)

        # 帧
        fg = QGroupBox("帧提取")
        fl = QGridLayout(fg)
        fl.setSpacing(6)
        fl.setContentsMargins(12, 14, 12, 8)
        fl.setColumnStretch(1, 1)

        fl.addWidget(self._label("抽帧间隔"), 0, 0)
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 30)
        self.fps_spin.setValue(1)
        fl.addWidget(self.fps_spin, 0, 1)
        fl.addWidget(self._label("帧/秒"), 0, 2)

        fl.addWidget(self._label("分辨率"), 1, 0)
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["原始"] + RESOLUTION_SCALES)
        ri = self.resolution_combo.findText(self.settings.resolution_scale)
        if ri >= 0:
            self.resolution_combo.setCurrentIndex(ri)
        fl.addWidget(self.resolution_combo, 1, 1, 1, 2)

        self.btn_extract_frames = QPushButton("抽取帧")
        self.btn_extract_frames.setFixedWidth(120)
        self.btn_extract_frames.clicked.connect(self._start_extract_frames)
        fl.addWidget(self.btn_extract_frames, 0, 3, 2, 1)

        self.frame_progress = QProgressBar()
        fl.addWidget(self.frame_progress, 2, 0, 1, 4)
        self.frame_status = QLabel(" ")
        self.frame_status.setProperty("class", "status")
        fl.addWidget(self.frame_status, 3, 0, 1, 4)
        layout.addWidget(fg)

        layout.addStretch()
        return w

    # ─── Step 2: 图片去重 ───

    def _build_step2(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        g = QGroupBox("去重设置")
        grid = QGridLayout(g)
        grid.setSpacing(6)
        grid.setContentsMargins(12, 14, 12, 8)
        grid.setColumnStretch(1, 1)

        grid.addWidget(self._label("算法"), 0, 0)
        self.method_combo = QComboBox()
        self.method_combo.addItems(["SSIM", "pHash"])
        grid.addWidget(self.method_combo, 0, 1)
        self.btn_deduplicate = QPushButton("开始去重")
        self.btn_deduplicate.setFixedWidth(120)
        self.btn_deduplicate.clicked.connect(self._start_deduplicate)
        grid.addWidget(self.btn_deduplicate, 0, 2)

        grid.addWidget(self._label("阈值"), 1, 0)
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(80, 99)
        self.threshold_slider.setValue(int(self.settings.ssim_threshold * 100))
        self.threshold_label = QLabel(f"{self.settings.ssim_threshold:.2f}")
        self.threshold_label.setFixedWidth(36)
        self.threshold_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.threshold_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #007aff;")
        self.threshold_slider.valueChanged.connect(
            lambda v: self.threshold_label.setText(f"{v / 100:.2f}")
        )
        grid.addWidget(self.threshold_slider, 1, 1)
        grid.addWidget(self.threshold_label, 1, 2)

        self.dedup_progress = QProgressBar()
        grid.addWidget(self.dedup_progress, 2, 0, 1, 3)
        self.dedup_status = QLabel(" ")
        self.dedup_status.setProperty("class", "status")
        grid.addWidget(self.dedup_status, 3, 0, 1, 3)

        layout.addWidget(g)

        # 图片理解区
        vg = QGroupBox("图片理解 (本地 Ollama)")
        vgrid = QGridLayout(vg)
        vgrid.setSpacing(6)
        vgrid.setContentsMargins(12, 14, 12, 8)
        vgrid.setColumnStretch(1, 1)

        vgrid.addWidget(self._label("视觉模型"), 0, 0)
        self.vision_model_combo = QComboBox()
        self.vision_model_combo.setEditable(True)
        self.vision_model_combo.addItems([
            "minicpm-v:8b", "llava:7b-v1.6", "llava-llama3:8b",
            "qwen2-vl:7b", "moondream:1.8b",
        ])
        self.vision_model_combo.setCurrentText(self.settings.vision_model)
        vgrid.addWidget(self.vision_model_combo, 0, 1)
        self.btn_analyze = QPushButton("开始分析")
        self.btn_analyze.setFixedWidth(120)
        vgrid.addWidget(self.btn_analyze, 0, 2)

        self.analysis_progress = QProgressBar()
        vgrid.addWidget(self.analysis_progress, 1, 0, 1, 3)
        self.analysis_status = QLabel("需先完成去重，再分析关键帧 → 生成 slides.json")
        self.analysis_status.setProperty("class", "status")
        vgrid.addWidget(self.analysis_status, 2, 0, 1, 3)

        layout.addWidget(vg)
        layout.addStretch()
        return w

    # ─── Step 3: 语音转录 ───

    def _build_step3(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        g = QGroupBox("转录设置")
        grid = QGridLayout(g)
        grid.setSpacing(6)
        grid.setContentsMargins(12, 14, 12, 8)
        grid.setColumnStretch(1, 1)

        grid.addWidget(self._label("模型"), 0, 0)
        self.model_combo = QComboBox()
        self.model_combo.addItems(WHISPER_MODELS)
        self.model_combo.setCurrentText(self.settings.whisper_model)
        grid.addWidget(self.model_combo, 0, 1)
        self.btn_transcribe = QPushButton("开始转录")
        self.btn_transcribe.setFixedWidth(120)
        grid.addWidget(self.btn_transcribe, 0, 2)

        grid.addWidget(self._label("语言"), 1, 0)
        self.language_combo = QComboBox()
        self.language_combo.addItems(["自动检测", "中文", "英文", "日文"])
        grid.addWidget(self.language_combo, 1, 1)

        grid.addWidget(self._label("词表"), 2, 0)
        self.vocab_combo = QComboBox()
        self.vocab_combo.addItem("无")
        self._refresh_vocab_combo()
        grid.addWidget(self.vocab_combo, 2, 1)
        vocab_hint = QLabel("在 Settings > 术语词表 中管理")
        vocab_hint.setProperty("class", "hint")
        grid.addWidget(vocab_hint, 2, 2)

        self.transcribe_progress = QProgressBar()
        grid.addWidget(self.transcribe_progress, 3, 0, 1, 3)
        layout.addWidget(g)

        rg = QGroupBox("转录预览")
        rl = QVBoxLayout(rg)
        rl.setContentsMargins(12, 14, 12, 8)
        self.transcript_preview = QTextEdit()
        self.transcript_preview.setReadOnly(True)
        self.transcript_preview.setPlaceholderText("转录完成后在此显示...")
        rl.addWidget(self.transcript_preview)
        layout.addWidget(rg, stretch=1)

        return w

    # ─── Step 4: AI 聚合 ───

    def _build_step4(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)

        # 唯一的 GroupBox，内部分区
        g = QGroupBox("AI 聚合")
        gl = QVBoxLayout(g)
        gl.setSpacing(4)
        gl.setContentsMargins(12, 14, 12, 8)

        # ── 第一行：数据源 + Provider ──
        top = QGridLayout()
        top.setSpacing(6)
        top.setColumnStretch(1, 1)

        top.addWidget(self._label("图片数据"), 0, 0)
        self.slides_json_edit = QLineEdit()
        self.slides_json_edit.setPlaceholderText("slides.json (图片理解结果)...")
        top.addWidget(self.slides_json_edit, 0, 1)
        btn_slides = QPushButton("浏览")
        btn_slides.setProperty("class", "secondary")
        btn_slides.setFixedWidth(72)
        btn_slides.clicked.connect(lambda: self._browse_file(self.slides_json_edit, "JSON (*.json)"))
        top.addWidget(btn_slides, 0, 2)

        top.addWidget(self._label("转录数据"), 1, 0)
        self.transcript_path_edit = QLineEdit()
        self.transcript_path_edit.setPlaceholderText("transcript.json (语音转录)...")
        top.addWidget(self.transcript_path_edit, 1, 1)
        btn_json = QPushButton("浏览")
        btn_json.setProperty("class", "secondary")
        btn_json.setFixedWidth(72)
        btn_json.clicked.connect(lambda: self._browse_file(self.transcript_path_edit, "JSON (*.json)"))
        top.addWidget(btn_json, 1, 2)

        top.addWidget(self._label("Provider"), 2, 0)
        prov_row = QHBoxLayout()
        prov_row.setSpacing(6)
        self.provider_combo = QComboBox()
        self.provider_combo.addItem("手动模式")
        self._refresh_provider_combo()
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        prov_row.addWidget(self.provider_combo, stretch=1)
        self.btn_generate = QPushButton("生成笔记")
        self.btn_generate.setFixedWidth(120)
        prov_row.addWidget(self.btn_generate)
        self.btn_export = QPushButton("导出数据")
        self.btn_export.setProperty("class", "secondary")
        self.btn_export.setFixedWidth(100)
        prov_row.addWidget(self.btn_export)
        top.addLayout(prov_row, 2, 1, 1, 2)

        gl.addLayout(top)

        # ── 分隔：Prompt（API 模式才显示） ──
        self.prompt_section = QWidget()
        pl = QVBoxLayout(self.prompt_section)
        pl.setContentsMargins(0, 4, 0, 0)
        pl.setSpacing(2)
        prompt_hdr = QLabel("蒸馏 Prompt")
        prompt_hdr.setStyleSheet("font-weight: 500; font-size: 12px;")
        pl.addWidget(prompt_hdr)
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setFixedHeight(90)
        self.prompt_edit.setPlainText(self.settings.default_distill_prompt)
        pl.addWidget(self.prompt_edit)
        self.prompt_section.hide()
        gl.addWidget(self.prompt_section)

        # ── 分隔：结果区 ──
        result_hdr = QHBoxLayout()
        result_hdr.setSpacing(6)
        self.result_label = QLabel("AI 返回结果（可手动粘贴）")
        self.result_label.setStyleSheet("font-weight: 500; font-size: 12px;")
        result_hdr.addWidget(self.result_label)
        result_hdr.addStretch()
        gl.addLayout(result_hdr)

        self.manual_result = QTextEdit()
        self.manual_result.setPlaceholderText("API 自动生成 或 手动粘贴 AI 笔记内容...")
        gl.addWidget(self.manual_result, stretch=1)

        # ── 底部操作栏 ──
        bottom = QHBoxLayout()
        bottom.setSpacing(6)
        bottom.addStretch()
        self.btn_save_md = QPushButton("保存 Markdown (.md)")
        self.btn_save_md.setFixedWidth(180)
        bottom.addWidget(self.btn_save_md)
        gl.addLayout(bottom)

        layout.addWidget(g)
        return w

    def _on_provider_changed(self, index):
        self.prompt_section.setVisible(index != 0)
        # 手动模式时隐藏"生成笔记"按钮，显示"导出数据"
        self.btn_generate.setVisible(index != 0)
        self.btn_export.setVisible(index == 0)

    # ─── 辅助 ───

    def _browse_file(self, edit_widget, filter_str="所有文件 (*)"):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择文件", "", f"{filter_str};;所有文件 (*)"
        )
        if path:
            edit_widget.setText(path)

    def _browse_dir(self, edit_widget):
        path = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if path:
            edit_widget.setText(path)

    def _refresh_vocab_combo(self):
        self.vocab_combo.clear()
        self.vocab_combo.addItem("无")
        for v in self.settings.vocabularies:
            self.vocab_combo.addItem(v["name"])

    def _refresh_provider_combo(self):
        self.provider_combo.clear()
        self.provider_combo.addItem("手动模式")
        for p in self.settings.providers:
            self.provider_combo.addItem(f"{p['name']} ({p['model']})")

    @staticmethod
    def _label(text):
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight: 500; color: #48484a;")
        return lbl

    # ─── 媒体处理: Step 1 按钮连接 ───

    def _start_extract_audio(self):
        video = self.video_path_edit.text().strip()
        output = self.output_dir_edit.text().strip()
        if not video or not output:
            self.audio_status.setText("请先选择视频路径和输出目录")
            return

        self.btn_extract_audio.setEnabled(False)
        self.audio_progress.setValue(0)
        self.audio_status.setText("正在提取音频...")

        self._audio_worker = _FFmpegWorker(
            "audio", video, output,
            sample_rate=int(self.sample_rate_combo.currentText()),
        )
        self._audio_worker.progress.connect(lambda v: self.audio_progress.setValue(int(v * 100)))
        self._audio_worker.finished.connect(self._on_audio_done)
        self._audio_worker.start()

    def _on_audio_done(self, ok, result):
        self.btn_extract_audio.setEnabled(True)
        if ok:
            self.audio_progress.setValue(100)
            self.audio_status.setText(f"完成: {result}")
        else:
            self.audio_status.setText(f"失败: {result}")

    def _start_extract_frames(self):
        video = self.video_path_edit.text().strip()
        output = self.output_dir_edit.text().strip()
        if not video or not output:
            self.frame_status.setText("请先选择视频路径和输出目录")
            return

        resolution = self.resolution_combo.currentText()
        fps = self.fps_spin.value()

        self.btn_extract_frames.setEnabled(False)
        self.frame_progress.setValue(0)
        self.frame_status.setText("正在抽取帧...")

        self._frame_worker = _FFmpegWorker(
            "frames", video, output,
            fps=fps, resolution_scale=resolution if resolution != "原始" else None,
        )
        self._frame_worker.progress.connect(lambda v: self.frame_progress.setValue(int(v * 100)))
        self._frame_worker.finished.connect(self._on_frames_done)
        self._frame_worker.start()

    def _on_frames_done(self, ok, result):
        self.btn_extract_frames.setEnabled(True)
        if ok:
            self.frame_progress.setValue(100)
            count = len([f for f in __import__('os').listdir(result) if f.endswith('.jpg')])
            self.frame_status.setText(f"完成: {count} 帧已保存到 {result}")
        else:
            self.frame_status.setText(f"失败: {result}")

    # ─── 图片去重: Step 2 按钮连接 ───

    def _start_deduplicate(self):
        output = self.output_dir_edit.text().strip()
        if not output:
            self.dedup_status.setText("请先设置输出目录")
            return

        project_dir = Path(output)
        if not project_dir.exists():
            self.dedup_status.setText("输出目录不存在，请先完成帧提取")
            return

        frames_dir = project_dir / "frames"
        if not frames_dir.exists() or not list(frames_dir.glob("*.jpg")):
            self.dedup_status.setText("frames 目录为空，请先完成帧提取")
            return

        method = self.method_combo.currentText().lower()
        threshold = self.threshold_slider.value() / 100.0

        self.btn_deduplicate.setEnabled(False)
        self.dedup_progress.setValue(0)
        self.dedup_status.setText(f"正在去重 ({method}, 阈值 {threshold:.2f})...")

        self._dedup_worker = _DedupWorker(
            str(frames_dir), str(project_dir), method, threshold,
        )
        self._dedup_worker.progress.connect(lambda v: self.dedup_progress.setValue(int(v * 100)))
        self._dedup_worker.finished.connect(self._on_dedup_done)
        self._dedup_worker.start()

    def _on_dedup_done(self, ok, result):
        self.btn_deduplicate.setEnabled(True)
        if ok:
            self.dedup_progress.setValue(100)
            r = self._dedup_worker.result
            self.dedup_status.setText(
                f"完成: {r['total']} 帧 → {r['kept']} 帧已保存到 {r['output']}"
            )
        else:
            self.dedup_status.setText(f"失败: {result}")


class _FFmpegWorker(QThread):
    progress = Signal(float)
    finished = Signal(bool, str)

    def __init__(self, task, video, output, **kwargs):
        super().__init__()
        self.task = task
        self.video = video
        self.output = output
        self.kwargs = kwargs

    def run(self):
        from src.media import extract_audio, extract_frames
        from src.config import get_project_dir
        try:
            project_dir = get_project_dir(self.output, self.video)
            if self.task == "audio":
                path = extract_audio(
                    self.video, str(project_dir / "audio"),
                    sample_rate=self.kwargs.get("sample_rate", 16000),
                    progress_cb=lambda v: self.progress.emit(v),
                )
                self.finished.emit(True, path)
            else:
                res = self.kwargs.get("resolution_scale") or "1/2"
                path = extract_frames(
                    self.video, str(project_dir),
                    fps=self.kwargs.get("fps", 1.0),
                    resolution_scale=res,
                    progress_cb=lambda v: self.progress.emit(v),
                )
                self.finished.emit(True, path)
        except Exception as e:
            self.finished.emit(False, str(e))


class _DedupWorker(QThread):
    progress = Signal(float)
    finished = Signal(bool, str)

    def __init__(self, frames_dir, output_dir, method, threshold):
        super().__init__()
        self.frames_dir = frames_dir
        self.output_dir = output_dir
        self.method = method
        self.threshold = threshold
        self.result = None

    def run(self):
        from src.visual import deduplicate
        try:
            self.result = deduplicate(
                self.frames_dir, self.output_dir,
                method=self.method, threshold=self.threshold,
                progress_cb=lambda v: self.progress.emit(v),
            )
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))
