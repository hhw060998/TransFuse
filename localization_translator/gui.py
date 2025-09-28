import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QFileDialog, QComboBox, QMessageBox, QProgressBar
)
from PyQt5.QtCore import Qt

import threading
from PyQt5.QtCore import pyqtSignal
from translator import translate_csv


class TranslatorGUI(QWidget):
    progress_signal = pyqtSignal(int)
    finish_signal = pyqtSignal(str, str)  # (类型, 消息)

    def __init__(self):
        super().__init__()
        self.setWindowTitle('本地化翻译工具')
        self.setGeometry(300, 200, 400, 200)
        self.csv_path = ''
        self.init_ui()
        self.progress_signal.connect(self.progress.setValue)
        self.finish_signal.connect(self.show_message)

    def init_ui(self):
        layout = QVBoxLayout()

        self.label = QLabel('请选择CSV文件：')
        layout.addWidget(self.label)

        self.btn_select = QPushButton('选择文件')
        self.btn_select.clicked.connect(self.select_file)
        layout.addWidget(self.btn_select)

        # 默认文件路径
        default_path = r'D:\RgClient\Assets\Shared\GameRes\Localization\多语言表.csv'
        self.csv_path = default_path
        self.label.setText(f'默认：{default_path}')

        self.engine_label = QLabel('选择翻译引擎：')
        layout.addWidget(self.engine_label)
        self.engine_combo = QComboBox()
        self.engine_combo.addItems(['Google', 'OpenAI'])
        layout.addWidget(self.engine_combo)

        self.btn_translate = QPushButton('开始翻译')
        self.btn_translate.clicked.connect(self.start_translate)
        layout.addWidget(self.btn_translate)

        self.progress = QProgressBar()
        self.progress.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.progress)

        self.setLayout(layout)

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, '选择CSV文件', '', 'CSV Files (*.csv)')
        if file_path:
            self.csv_path = file_path
            self.label.setText(f'已选择：{file_path}')

    def start_translate(self):
        if not self.csv_path:
            QMessageBox.warning(self, '提示', '请先选择CSV文件')
            return
        engine = self.engine_combo.currentText()
        self.btn_translate.setEnabled(False)
        self.progress.setValue(0)
        threading.Thread(target=self.run_translate, args=(engine,), daemon=True).start()


    def run_translate(self, engine):
        try:
            def progress_callback(val):
                self.progress_signal.emit(val)
            translate_csv(self.csv_path, engine, progress_callback)
            self.progress_signal.emit(100)
            self.finish_signal.emit('info', '翻译完成！')
        except Exception as e:
            self.finish_signal.emit('error', str(e))
        finally:
            # 需要在主线程恢复按钮
            self.progress_signal.emit(100)
            self.finish_signal.emit('enable_btn', '')

    def show_message(self, msg_type, msg):
        if msg_type == 'info':
            QMessageBox.information(self, '完成', msg)
            self.btn_translate.setEnabled(True)
        elif msg_type == 'error':
            QMessageBox.critical(self, '错误', msg)
            self.btn_translate.setEnabled(True)
        elif msg_type == 'enable_btn':
            self.btn_translate.setEnabled(True)

def run_app():
    app = QApplication(sys.argv)
    gui = TranslatorGUI()
    gui.show()
    sys.exit(app.exec_())
