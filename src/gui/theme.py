"""
Video-Distiller 主题管理
"""

THEMES = {
    "light": {
        "bg": "#f5f5f7",
        "surface": "#ffffff",
        "text": "#1d1d1f",
        "text_secondary": "#86868b",
        "text_label": "#48484a",
        "accent": "#007aff",
        "accent_hover": "#0066d6",
        "accent_pressed": "#0055b3",
        "border": "#d2d2d7",
        "border_group": "#e5e5ea",
        "input_bg": "#f5f5f7",
        "input_focus_bg": "#ffffff",
        "btn_secondary": "#e5e5ea",
        "btn_secondary_text": "#1d1d1f",
        "btn_secondary_hover": "#d2d2d7",
        "progress_bg": "#e5e5ea",
        "scrollbar": "#c7c7cc",
        "scrollbar_hover": "#a1a1a6",
        "disabled": "#c7c7cc",
    },
    "dark": {
        "bg": "#1c1c1e",
        "surface": "#2c2c2e",
        "text": "#f5f5f7",
        "text_secondary": "#98989d",
        "text_label": "#a1a1a6",
        "accent": "#0a84ff",
        "accent_hover": "#409cff",
        "accent_pressed": "#0066d6",
        "border": "#48484a",
        "border_group": "#3a3a3c",
        "input_bg": "#2c2c2e",
        "input_focus_bg": "#3a3a3c",
        "btn_secondary": "#3a3a3c",
        "btn_secondary_text": "#f5f5f7",
        "btn_secondary_hover": "#48484a",
        "progress_bg": "#3a3a3c",
        "scrollbar": "#48484a",
        "scrollbar_hover": "#636366",
        "disabled": "#48484a",
    },
}


def build_stylesheet(theme_name: str) -> str:
    c = THEMES[theme_name]
    return f"""
    QMainWindow {{
        background-color: {c['bg']};
    }}

    QWidget {{
        font-family: "Segoe UI", "SF Pro Display", "Helvetica Neue", sans-serif;
        font-size: 13px;
        color: {c['text']};
    }}

    QDialog {{
        background-color: {c['bg']};
    }}

    /* ─── ListWidget ─── */
    QListWidget {{
        background: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 2px;
        color: {c['text']};
        outline: none;
    }}
    QListWidget::item {{
        padding: 6px 8px;
        border-radius: 4px;
    }}
    QListWidget::item:selected {{
        background: {c['accent']};
        color: #ffffff;
    }}
    QListWidget::item:hover:!selected {{
        background: {c['btn_secondary']};
    }}

    /* ─── SpinBox ─── */
    QSpinBox, QDoubleSpinBox {{
        background: {c['input_bg']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 5px 8px;
        min-height: 18px;
        color: {c['text']};
    }}
    QSpinBox:focus, QDoubleSpinBox:focus {{
        border: 1.5px solid {c['accent']};
    }}
    QSpinBox::up-button, QDoubleSpinBox::up-button,
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        width: 16px;
        border: none;
        background: transparent;
    }}

    /* ─── DialogButtonBox ─── */
    QDialogButtonBox QPushButton {{
        min-width: 80px;
    }}

    /* ─── ToolBox (Settings Tab) ─── */
    QToolBox {{
        background: {c['bg']};
        border: none;
    }}

    /* ─── Tab 栏 ─── */
    QTabWidget::pane {{
        border: none;
        background: {c['surface']};
        border-radius: 10px;
        padding: 12px;
    }}
    QTabBar::tab {{
        background: transparent;
        color: {c['text_secondary']};
        padding: 8px 16px;
        margin-right: 2px;
        border: none;
        border-bottom: 2px solid transparent;
        font-size: 13px;
        font-weight: 500;
    }}
    QTabBar::tab:selected {{
        color: {c['accent']};
        border-bottom: 2px solid {c['accent']};
    }}
    QTabBar::tab:hover:!selected {{
        color: {c['text']};
    }}

    /* ─── GroupBox ─── */
    QGroupBox {{
        background: {c['surface']};
        border: 1px solid {c['border_group']};
        border-radius: 8px;
        margin-top: 16px;
        padding: 14px 12px 8px 12px;
        font-weight: 600;
        font-size: 13px;
        color: {c['text']};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 12px;
        top: 6px;
        padding: 0 4px;
        background: {c['surface']};
        color: {c['text']};
    }}

    /* ─── LineEdit ─── */
    QLineEdit {{
        background: {c['input_bg']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 6px 10px;
        min-height: 18px;
        color: {c['text']};
        selection-background-color: {c['accent']};
        selection-color: #ffffff;
    }}
    QLineEdit:focus {{
        border: 1.5px solid {c['accent']};
        background: {c['input_focus_bg']};
    }}

    /* ─── ComboBox ─── */
    QComboBox {{
        background: {c['input_bg']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 5px 10px;
        min-width: 110px;
        min-height: 18px;
        color: {c['text']};
    }}
    QComboBox:focus {{
        border: 1.5px solid {c['accent']};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 22px;
    }}
    QComboBox QAbstractItemView {{
        background: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        selection-background-color: {c['accent']};
        selection-color: #ffffff;
        padding: 2px;
        outline: none;
    }}

    /* ─── Buttons ─── */
    QPushButton {{
        background: {c['accent']};
        color: #ffffff;
        border: none;
        border-radius: 6px;
        padding: 7px 16px;
        font-weight: 600;
        font-size: 13px;
        min-height: 28px;
    }}
    QPushButton:hover {{
        background: {c['accent_hover']};
    }}
    QPushButton:pressed {{
        background: {c['accent_pressed']};
    }}
    QPushButton:disabled {{
        background: {c['disabled']};
        color: #ffffff;
    }}

    /* 次要按钮 */
    QPushButton[class="secondary"] {{
        background: {c['btn_secondary']};
        color: {c['btn_secondary_text']};
    }}
    QPushButton[class="secondary"]:hover {{
        background: {c['btn_secondary_hover']};
    }}

    /* ─── Slider ─── */
    QSlider::groove:horizontal {{
        background: {c['progress_bg']};
        height: 4px;
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: {c['surface']};
        border: 2px solid {c['accent']};
        width: 16px;
        height: 16px;
        margin: -6px 0;
        border-radius: 8px;
    }}
    QSlider::sub-page:horizontal {{
        background: {c['accent']};
        border-radius: 2px;
    }}

    /* ─── ProgressBar ─── */
    QProgressBar {{
        background: {c['progress_bg']};
        border: none;
        border-radius: 3px;
        height: 5px;
        text-align: center;
        color: transparent;
    }}
    QProgressBar::chunk {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {c['accent']}, stop:1 #5ac8fa);
        border-radius: 3px;
    }}

    /* ─── TextEdit ─── */
    QTextEdit {{
        background: {c['input_bg']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 8px 10px;
        color: {c['text']};
        selection-background-color: {c['accent']};
        selection-color: #ffffff;
    }}
    QTextEdit:focus {{
        border: 1.5px solid {c['accent']};
        background: {c['input_focus_bg']};
    }}

    /* ─── Label ─── */
    QLabel {{
        color: {c['text']};
    }}
    QLabel[class="hint"] {{
        color: {c['text_secondary']};
        font-size: 12px;
    }}
    QLabel[class="status"] {{
        color: {c['text_secondary']};
        font-size: 12px;
        padding: 2px 0;
    }}

    /* ─── ScrollArea ─── */
    QScrollArea {{
        background: transparent;
        border: none;
    }}

    /* ─── ScrollBar ─── */
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {c['scrollbar']};
        border-radius: 4px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {c['scrollbar_hover']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}

    /* ─── StatusBar ─── */
    QStatusBar {{
        background: {c['bg']};
        color: {c['text_secondary']};
        border-top: 1px solid {c['border_group']};
        font-size: 12px;
        padding: 3px 10px;
    }}

    /* ─── ToolButton (主题切换) ─── */
    QToolButton {{
        background: transparent;
        border: none;
        border-radius: 4px;
        padding: 4px 8px;
        color: {c['text_secondary']};
        font-size: 12px;
    }}
    QToolButton:hover {{
        background: {c['btn_secondary']};
        color: {c['text']};
    }}
    """
