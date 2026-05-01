"""
Demo: PySide6 空窗口测试
运行: py -3.12 tests/demo_pyside6.py
"""

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import Qt

app = QApplication(sys.argv)

window = QMainWindow()
window.setWindowTitle("Video-Distiller - PySide6 测试")
window.resize(600, 400)

label = QLabel("PySide6 工作正常! 可以关闭此窗口。")
label.setAlignment(Qt.AlignmentFlag.AlignCenter)

layout = QVBoxLayout()
layout.addWidget(label)

container = QWidget()
container.setLayout(layout)
window.setCentralWidget(container)

window.show()

print("PySide6 窗口已打开，请关闭窗口以退出...")
sys.exit(app.exec())
