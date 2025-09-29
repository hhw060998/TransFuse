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

        self.label = QLabel('请选择文件（CSV或JSON）：')
        layout.addWidget(self.label)

        self.label.setAcceptDrops(True)
        self.label.installEventFilter(self)

        self.btn_select = QPushButton('选择文件')
        self.btn_select.clicked.connect(self.select_file)
        layout.addWidget(self.btn_select)

        # 默认文件路径
        default_path = r'D:\RgClient\Assets\Shared\GameRes\Localization\多语言表.csv'
        self.csv_path = default_path
        self.is_json = False
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

        # 新增：导出为JSON按钮
        self.btn_export_json = QPushButton('导出为JSON')
        self.btn_export_json.clicked.connect(self.export_json)
        layout.addWidget(self.btn_export_json)

        self.setLayout(layout)

    def eventFilter(self, obj, event):
        # 拖拽文件到label区域
        if obj == self.label:
            if event.type() == event.DragEnter:
                if event.mimeData().hasUrls():
                    event.accept()
                    return True
            elif event.type() == event.Drop:
                urls = event.mimeData().urls()
                if urls:
                    file_path = urls[0].toLocalFile()
                    self.csv_path = file_path
                    self.is_json = file_path.lower().endswith('.json')
                    self.label.setText(f'已选择：{file_path}')
                    self.btn_export_json.setVisible(not self.is_json)
                    return True
        return super().eventFilter(obj, event)

    def export_json(self):
        import pandas as pd
        import json
        import os
        if not self.csv_path:
            QMessageBox.warning(self, '提示', '请先选择CSV文件')
            return
        try:
            df = pd.read_csv(self.csv_path, header=None, encoding='utf-8')

            # ✅ 第二行（索引=1）为字段名
            raw_fields = list(df.iloc[1])
            field_names = []
            for idx, name in enumerate(raw_fields):
                name = str(name).strip()
                if name and name.lower() != 'nan' and not name.startswith('Unnamed'):
                    field_names.append((idx, name))

            data = []
            # ✅ 从第三行（索引=2）开始读取数据
            for i in range(2, len(df)):
                row = df.iloc[i]
                item = {}
                for idx, name in field_names:
                    value = row[idx]
                    # ✅ 转换 NaN 为 None（导出为 null）
                    if pd.isna(value):
                        item[name] = None
                    else:
                        item[name] = str(value).strip()
                # ✅ 跳过完全无内容的行
                if any(v not in [None, ""] for v in item.values()):
                    data.append(item)

            json_path = os.path.splitext(self.csv_path)[0] + '.json'
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            QMessageBox.information(self, '导出成功', f'已保存为：{json_path}')
        except Exception as e:
            QMessageBox.critical(self, '错误', f'导出JSON失败：{e}')


    def select_file(self):
        import os
        # 打开当前路径
        start_dir = os.path.dirname(self.csv_path) if self.csv_path and os.path.exists(os.path.dirname(self.csv_path)) else ''
        file_path, _ = QFileDialog.getOpenFileName(self, '选择文件', start_dir, 'CSV/JSON Files (*.csv *.json)')
        if file_path:
            self.csv_path = file_path
            self.is_json = file_path.lower().endswith('.json')
            self.label.setText(f'已选择：{file_path}')
            self.btn_export_json.setVisible(not self.is_json)

    def start_translate(self):
        if not self.csv_path:
            QMessageBox.warning(self, '提示', '请先选择文件')
            return
        engine = self.engine_combo.currentText()
        self.btn_translate.setEnabled(False)
        self.progress.setValue(0)
        threading.Thread(target=self.run_translate, args=(engine,), daemon=True).start()


    def run_translate(self, engine):
        try:
            def progress_callback(val):
                self.progress_signal.emit(val)
            if self.is_json:
                from utils import read_json, write_json
                data = read_json(self.csv_path)
                from translator import translate_json
                translate_json(data, engine, self.csv_path, progress_callback)
            else:
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
