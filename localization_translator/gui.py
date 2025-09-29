import sys
import time
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QFileDialog, QComboBox, QMessageBox, QProgressBar
)
from PyQt5.QtCore import Qt, QRunnable, QThreadPool, QObject, pyqtSignal

# WorkerSignals: signals emitted by the worker to the GUI
class WorkerSignals(QObject):
    # percent, info_text, row_time, done, total
    progress = pyqtSignal(float, str, float, int, int)
    finished = pyqtSignal(str, str)  # (type, message)


class TranslateWorker(QRunnable):
    """QRunnable worker that runs translate_csv/translate_json in a background thread.

    It wraps the translator's progress_callback so we can convert it into Qt signals,
    and supports cooperative cancellation via the `is_cancelled` attribute.
    """
    def __init__(self, csv_path, engine, is_json=False):
        super().__init__()
        self.csv_path = csv_path
        self.engine = engine
        self.is_json = is_json
        self.signals = WorkerSignals()
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        # Import translator inside worker to avoid importing heavy libs in GUI thread
        try:
            # The translator functions are expected to accept a progress_callback with the signature:
            #   progress_callback(percent: float, info: Optional[str]=None, row_time: Optional[float]=None, done: Optional[int]=None, total: Optional[int]=None)
            # The worker wraps that so it first checks for cancellation and converts parameters into Qt signals.
            from translator import translate_csv, translate_json
        except Exception as e:
            self.signals.finished.emit('error', f'无法导入 translator: {e}')
            return

        def wrapped_callback(percent, info=None, row_time=None, done=None, total=None):
            # If cancellation requested, try to notify translator (cooperative)
            if self.is_cancelled:
                # translator should check for cancellation (see guidance) and stop; we just notify GUI
                # Emit a final progress so UI can update
                self.signals.progress.emit(min(max(float(percent or 0.0), 0.0), 100.0), info or '', float(row_time or 0.0), int(done or 0), int(total or 0))
                return
            try:
                p = float(percent)
            except Exception:
                try:
                    p = float(0)
                except Exception:
                    p = 0.0
            self.signals.progress.emit(min(max(p, 0.0), 100.0), str(info or ''), float(row_time or 0.0), int(done or 0), int(total or 0))

        try:
            if self.is_json:
                translate_json(self.csv_path, self.engine, wrapped_callback, cancel_checker=lambda: self.is_cancelled)
            else:
                translate_csv(self.csv_path, self.engine, wrapped_callback, cancel_checker=lambda: self.is_cancelled)
            # If cancelled, we still reach here if translator exits cooperatively
            if self.is_cancelled:
                self.signals.finished.emit('info', '翻译已取消')
            else:
                self.signals.finished.emit('info', '翻译完成')
        except Exception as e:
            self.signals.finished.emit('error', f'翻译过程出错：{e}')


class TranslatorGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('本地化翻译工具')
        self.setGeometry(300, 200, 520, 260)
        self.csv_path = ''
        self.is_json = False

        # Progress statistics for ETA
        self._progress_samples = []
        self._progress_samples_max = 20
        self._progress_time_sum = 0.0
        self._progress_done_total = 0
        self._progress_total_tasks = None

        self.threadpool = QThreadPool()
        self.current_worker = None

        self.init_ui()

    def init_ui(self):
        from PyQt5.QtWidgets import QHBoxLayout, QLineEdit
        layout = QVBoxLayout()

        self.label = QLabel('请选择文件（CSV或JSON）：')
        layout.addWidget(self.label)

        # File controls
        h_btns = QHBoxLayout()
        self.btn_select = QPushButton('选择文件')
        self.btn_select.clicked.connect(self.select_file)
        h_btns.addWidget(self.btn_select)

        self.btn_export_json = QPushButton('导出为JSON')
        self.btn_export_json.clicked.connect(self.export_json)
        h_btns.addWidget(self.btn_export_json)

        self.btn_export_csv = QPushButton('导出为CSV')
        self.btn_export_csv.clicked.connect(self.export_csv)
        self.btn_export_csv.setVisible(False)
        h_btns.addWidget(self.btn_export_csv)

        layout.addLayout(h_btns)

        default_path = r'D:\RgClient\Assets\Shared\GameRes\Localization\多语言表.csv'
        self.csv_path = default_path
        self.label.setText(f'默认：{default_path}')

        self.engine_combo = QComboBox()
        self.engine_combo.addItems(['Google', 'OpenAI'])
        self.engine_combo.currentTextChanged.connect(self.on_engine_changed)
        layout.addWidget(self.engine_combo)

        # Google API Key 区域
        self.api_key_layout = QHBoxLayout()
        self.api_key_label = QLabel('Google API Key JSON:')
        self.api_key_layout.addWidget(self.api_key_label)
        self.api_key_path = QLineEdit()
        self.api_key_path.setPlaceholderText('拖拽或点击右侧按钮选择JSON')
        self.api_key_path.setReadOnly(True)
        self.api_key_path.setAcceptDrops(True)
        self.api_key_path.installEventFilter(self)
        self.api_key_layout.addWidget(self.api_key_path)
        self.btn_browse_api = QPushButton('浏览')
        self.btn_browse_api.clicked.connect(self.browse_api_key)
        self.api_key_layout.addWidget(self.btn_browse_api)
        layout.addLayout(self.api_key_layout)
        self.api_key_layout_widget = self.api_key_label  # 用于显示/隐藏

        # 默认只在Google时显示
        self.api_key_label.setVisible(True)
        self.api_key_path.setVisible(True)
        self.btn_browse_api.setVisible(True)
        self.on_engine_changed(self.engine_combo.currentText())

        # Control buttons
        h2 = QHBoxLayout()
        self.btn_translate = QPushButton('开始翻译')
        self.btn_translate.clicked.connect(self.start_translate)
        h2.addWidget(self.btn_translate)

        self.btn_cancel = QPushButton('取消')
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.request_cancel)
        h2.addWidget(self.btn_cancel)

        layout.addLayout(h2)

        # Progress area
        self.progress_info = QLabel('')
        layout.addWidget(self.progress_info)

        self.progress = QProgressBar()
        self.progress.setAlignment(Qt.AlignCenter)
        self.progress.setFormat('')
        layout.addWidget(self.progress)

        self.progress_extra = QLabel('')
        layout.addWidget(self.progress_extra)

        self.setLayout(layout)

    def eventFilter(self, obj, event):
        from PyQt5.QtCore import QEvent
        if obj == self.api_key_path:
            if event.type() == QEvent.DragEnter:
                if event.mimeData().hasUrls():
                    urls = event.mimeData().urls()
                    if urls and urls[0].toLocalFile().lower().endswith('.json'):
                        event.acceptProposedAction()
                        return True
            elif event.type() == QEvent.Drop:
                if event.mimeData().hasUrls():
                    urls = event.mimeData().urls()
                    if urls and urls[0].toLocalFile().lower().endswith('.json'):
                        self.api_key_path.setText(urls[0].toLocalFile())
                        return True
        return super().eventFilter(obj, event)

    def browse_api_key(self):
        file_path, _ = QFileDialog.getOpenFileName(self, '选择Google API Key JSON', '', 'JSON Files (*.json)')
        if file_path:
            self.api_key_path.setText(file_path)

    def on_engine_changed(self, text):
        is_google = (text == 'Google')
        self.api_key_label.setVisible(is_google)
        self.api_key_path.setVisible(is_google)
        self.btn_browse_api.setVisible(is_google)

    # ... export_json / export_csv / select_file implementations omitted for brevity ...
    # In practice paste your earlier implementations here (they are unchanged). 
    
    def export_json(self):
        import pandas as pd
        import json
        import os
        from PyQt5.QtWidgets import QMessageBox
        if not self.csv_path:
            QMessageBox.warning(self, '提示', '请先选择CSV文件')
            return
        try:
            # 尝试按常见编码读取（优先 utf-8）
            try:
                df = pd.read_csv(self.csv_path, header=None, encoding='utf-8')
            except Exception:
                df = pd.read_csv(self.csv_path, header=None, encoding='utf-8-sig')

            # 第二行（索引=1）为字段名
            raw_fields = list(df.iloc[1])
            field_names = []
            for idx, name in enumerate(raw_fields):
                name = str(name).strip()
                if name and name.lower() != 'nan' and not name.startswith('Unnamed'):
                    field_names.append((idx, name))

            data = []
            for i in range(2, len(df)):
                row = df.iloc[i]
                item = {}
                for idx, name in field_names:
                    value = row[idx]
                    if pd.isna(value):
                        item[name] = None
                    else:
                        item[name] = str(value).strip()
                if any(v not in [None, ""] for v in item.values()):
                    data.append(item)

            json_path = os.path.splitext(self.csv_path)[0] + '.json'
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            QMessageBox.information(self, '导出成功', f'已保存为：{json_path}')
        except Exception as e:
            QMessageBox.critical(self, '错误', f'导出JSON失败：{e}')


    def export_csv(self):
        import pandas as pd
        import os
        from utils import read_json
        from PyQt5.QtWidgets import QMessageBox
        if not self.csv_path or not self.is_json:
            QMessageBox.warning(self, '提示', '请先选择JSON文件')
            return
        try:
            data = read_json(self.csv_path)
            if not data:
                QMessageBox.warning(self, '提示', 'JSON文件无数据')
                return
            df = pd.DataFrame(data)
            columns = list(df.columns)
            field_row = columns
            data_rows = df.values.tolist()
            # 只写字段名和数据行，不写原csv第一行
            all_rows = [field_row] + data_rows
            csv_path = os.path.splitext(self.csv_path)[0] + '.csv'
            import csv
            with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                for row in all_rows:
                    writer.writerow(row)
            QMessageBox.information(self, '导出成功', f'已保存为：{csv_path}')
        except Exception as e:
            QMessageBox.critical(self, '错误', f'导出CSV失败：{e}')


    def select_file(self):
        from PyQt5.QtWidgets import QFileDialog
        start_dir = os.path.dirname(self.csv_path) if self.csv_path and os.path.exists(os.path.dirname(self.csv_path)) else ''
        file_path, _ = QFileDialog.getOpenFileName(self, '选择文件', start_dir, 'CSV/JSON Files (*.csv *.json)')
        if file_path:
            self.csv_path = file_path
            self.is_json = file_path.lower().endswith('.json')
            self.label.setText(f'已选择：{file_path}')
            self.btn_export_json.setVisible(not self.is_json)
            self.btn_export_csv.setVisible(self.is_json)

    def start_translate(self):
        if not self.csv_path:
            QMessageBox.warning(self, '提示', '请先选择文件')
            return
        engine = self.engine_combo.currentText()
        # Google模式下检查API Key
        if engine == 'Google':
            api_path = self.api_key_path.text().strip()
            if not api_path:
                QMessageBox.warning(self, '提示', '请先导入Google API Key JSON文件')
                return
            # 检查环境变量
            if not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = api_path
        self.btn_translate.setEnabled(False)
        self.btn_cancel.setEnabled(True)

        # reset ETA stats
        self._progress_samples = []
        self._progress_time_sum = 0.0
        self._progress_done_total = 0
        self._progress_total_tasks = None

        worker = TranslateWorker(self.csv_path, engine, is_json=self.is_json)
        worker.signals.progress.connect(self.handle_progress_signal)
        worker.signals.finished.connect(self.handle_finished_signal)
        self.current_worker = worker
        self.threadpool.start(worker)

    def request_cancel(self):
        if self.current_worker:
            self.current_worker.cancel()
            self.progress_info.setText('已请求取消，等待停止...')
            self.btn_cancel.setEnabled(False)

    def handle_progress_signal(self, percent, info_text, row_time, done, total):
        # Update info text
        if info_text:
            self.progress_info.setText(info_text)

        # Record sample
        if row_time and row_time > 0:
            self._progress_samples.append(row_time)
            if len(self._progress_samples) > self._progress_samples_max:
                self._progress_samples = self._progress_samples[-self._progress_samples_max:]
            self._progress_time_sum += row_time
            self._progress_done_total = max(self._progress_done_total, done)

        # If translator supplied total, use it
        if total and total > 0:
            self._progress_total_tasks = total

        # decide avg
        avg_all = None
        if self._progress_done_total > 0:
            avg_all = self._progress_time_sum / max(1, self._progress_done_total)
        avg_recent = None
        if len(self._progress_samples) > 0:
            avg_recent = sum(self._progress_samples) / len(self._progress_samples)
        chosen_avg = avg_all if (avg_all is not None and self._progress_done_total >= 3) else avg_recent

        # ETA calculation
        if percent >= 100:
            total_time = self._progress_time_sum
            if total_time < 60:
                eta_text = f'已完成，用时{int(total_time)}秒'
            else:
                eta_text = f'已完成，用时{int(total_time)//60}分{int(total_time)%60}秒'
        else:
            if chosen_avg is None or self._progress_total_tasks is None:
                eta_text = '正在预估完成时间...'
            else:
                remain = max(0, int(self._progress_total_tasks) - int(self._progress_done_total))
                eta_sec = int(chosen_avg * remain)
                if eta_sec < 60:
                    eta_text = f'预计剩余{eta_sec}秒'
                else:
                    eta_text = f'预计剩余{eta_sec//60}分{eta_sec%60}秒'

        text = f'{percent:.1f}%  {eta_text}'
        self.progress_extra.setText(text)
        self.progress.setValue(int(round(percent)))

    def handle_finished_signal(self, msg_type, msg):
        if msg_type == 'info':
            QMessageBox.information(self, '完成', msg)
        elif msg_type == 'error':
            QMessageBox.critical(self, '错误', msg)
        self.btn_translate.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.current_worker = None


def run_app():
    """
    启动 GUI 的统一入口。main.py 可通过 `from gui import run_app` 调用它。
    如果外部环境已有 QApplication instance（例如被其它进程嵌入），会复用它并**不**调用 sys.exit。
    """
    # 如果已经存在 QApplication 实例（例如被其他模块创建），复用
    app = QApplication.instance()
    created = False
    if app is None:
        app = QApplication(sys.argv)
        created = True

    gui = TranslatorGUI()
    gui.show()

    if created:
        # 只有当我们在此处创建了 QApplication 才调用 exec_ 并退出
        sys.exit(app.exec_())


if __name__ == '__main__':
    # 保持原有直接运行行为
    run_app()
