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
        from PyQt5.QtWidgets import QHBoxLayout
        layout = QVBoxLayout()

        self.label = QLabel('请选择文件（CSV或JSON）：')
        layout.addWidget(self.label)

        self.label.setAcceptDrops(True)
        self.label.installEventFilter(self)

        # 横向布局：选择文件、导出为JSON、导出为CSV
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

        # 新增：进度信息标签
        self.progress_info = QLabel('')
        layout.addWidget(self.progress_info)

        self.progress = QProgressBar()
        self.progress.setAlignment(Qt.AlignCenter)
        self.progress.setFormat("")  # 不显示默认数字（我们用额外标签显示）
        layout.addWidget(self.progress)

        # 新增：进度百分比和预计时间标签
        self.progress_extra = QLabel('')
        layout.addWidget(self.progress_extra)

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
                    self.btn_export_csv.setVisible(self.is_json)
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
            self.btn_export_csv.setVisible(self.is_json)
            
    def export_csv(self):
        import pandas as pd
        import os
        from utils import read_json
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
            # 保留原csv第一行（如有）
            orig_csv_path = os.path.splitext(self.csv_path)[0] + '.csv'
            orig_first_row = None
            if os.path.exists(orig_csv_path):
                import csv
                with open(orig_csv_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.reader(f)
                    try:
                        orig_first_row = next(reader)
                    except StopIteration:
                        orig_first_row = None
            # 组装新csv内容
            all_rows = []
            if orig_first_row:
                all_rows.append(orig_first_row)
            else:
                all_rows.append(['' for _ in columns])
            all_rows.append(field_row)
            all_rows += data_rows
            # 导出到同级目录
            csv_path = os.path.splitext(self.csv_path)[0] + '.csv'
            import csv
            with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                for row in all_rows:
                    writer.writerow(row)
            QMessageBox.information(self, '导出成功', f'已保存为：{csv_path}')
        except Exception as e:
            QMessageBox.critical(self, '错误', f'导出CSV失败：{e}')

    def start_translate(self):
        if not self.csv_path:
            QMessageBox.warning(self, '提示', '请先选择文件')
            return
        engine = self.engine_combo.currentText()
        self.btn_translate.setEnabled(False)
        self.progress.setValue(0)
        threading.Thread(target=self.run_translate, args=(engine,), daemon=True).start()


    def run_translate(self, engine):
        import time
        try:
            # ---------- 进度/ETA 相关状态 ----------
            self._progress_samples = []         # 用于短期平滑的最近 N 个样本（秒）
            self._progress_samples_max = 20
            self._progress_time_sum = 0.0       # 累计所有已记录行的耗时（秒）
            self._progress_done_total = 0       # 累计已完成的行数（基于收到 row_time 的次数）
            self._progress_total_tasks = None   # 估算或明确的总任务数（可为 None）
            # -------------------------------------

            def progress_callback(val, info_text=None, row_time=None):
                """
                val: 期望为百分比 (0-100)，但也尽量兼容其他形式（若 translator 使用不同语义，可能需进一步适配）
                info_text: 可选，显示语言/子任务信息
                row_time: 可选，本次行/任务耗时（秒）
                """
                # 更新进度条显示（主线程）
                try:
                    percent = float(val)
                except Exception:
                    # 保底：如果传入非数字，忽略
                    return

                # 记录 info_text（细粒度显示）
                if info_text is not None:
                    from PyQt5.QtCore import QMetaObject, Qt, Q_ARG
                    QMetaObject.invokeMethod(self.progress_info, "setText", Qt.QueuedConnection, Q_ARG(str, info_text))

                # 记录每行耗时样本（用于平均）
                if row_time is not None:
                    try:
                        rt = float(row_time)
                    except Exception:
                        rt = None
                    if rt is not None and rt >= 0:
                        self._progress_samples.append(rt)
                        if len(self._progress_samples) > self._progress_samples_max:
                            # keep last N samples for smoothing
                            self._progress_samples = self._progress_samples[-self._progress_samples_max:]
                        self._progress_time_sum += rt
                        self._progress_done_total += 1

                # 防护：限制 percent 在 [0,100]
                if percent < 0:
                    percent = 0.0
                if percent > 100:
                    percent = 100.0

                # 估算总任务数（当 percent>0 且已有已完成计数时）
                estimate_total = None
                if percent > 0 and self._progress_done_total > 0 and percent < 100:
                    # 估算：done_total 对应 percent%，则 total ≈ done_total * 100 / percent
                    try:
                        estimate_total = max(self._progress_done_total, int(round(self._progress_done_total * 100.0 / percent)))
                        # 填充 self._progress_total_tasks 以便后续使用（如果还未明确）
                        if self._progress_total_tasks is None:
                            self._progress_total_tasks = estimate_total
                    except Exception:
                        estimate_total = None

                # 计算平均耗时（用累计平均为主，短期样本为次）
                avg_all = None
                if self._progress_done_total > 0:
                    avg_all = self._progress_time_sum / self._progress_done_total

                avg_recent = None
                if len(self._progress_samples) > 0:
                    avg_recent = sum(self._progress_samples) / len(self._progress_samples)

                # 选择用于 ETA 的平均：当样本足够时用 avg_all，否则用 avg_recent
                chosen_avg = None
                if avg_all is not None and self._progress_done_total >= 3:
                    chosen_avg = avg_all
                elif avg_recent is not None:
                    chosen_avg = avg_recent

                # 计算剩余时间（秒）
                eta_text = ''
                if percent >= 100:
                    # 完成：显示总时间（用累积时间）
                    total_time = self._progress_time_sum
                    if total_time < 60:
                        eta_text = f'已完成，用时{int(total_time)}秒'
                    else:
                        eta_text = f'已完成，用时{int(total_time)//60}分{int(total_time)%60}秒'
                else:
                    # 未完成：如果无法估算，显示提示
                    if chosen_avg is None or (estimate_total is None and self._progress_done_total < 3):
                        eta_text = '正在预估完成时间...'
                    else:
                        # 计算剩余任务数
                        total_tasks_to_use = self._progress_total_tasks if self._progress_total_tasks is not None else estimate_total
                        if total_tasks_to_use is None:
                            eta_text = '正在预估完成时间...'
                        else:
                            remain = max(0, total_tasks_to_use - self._progress_done_total)
                            eta_sec = int(chosen_avg * remain)
                            if eta_sec < 60:
                                eta_text = f'预计剩余{eta_sec}秒'
                            else:
                                eta_text = f'预计剩余{eta_sec//60}分{eta_sec%60}秒'

                # 组合显示文本：百分比（保留一位小数） + ETA
                text = f'{percent:.1f}%  {eta_text}'

                # 使用线程安全方式更新 label（主线程）
                from PyQt5.QtCore import QMetaObject, Qt, Q_ARG
                QMetaObject.invokeMethod(self.progress_extra, "setText", Qt.QueuedConnection, Q_ARG(str, text))

                # 最后把进度值发给进度条（主线程）
                try:
                    self.progress_signal.emit(int(round(percent)))
                except Exception:
                    pass

            # 调用实际翻译逻辑（translate_json/translate_csv） —— 它们应在合适时调用 progress_callback
            if self.is_json:
                from utils import read_json, write_json
                data = read_json(self.csv_path)
                from translator import translate_json
                translate_json(data, engine, self.csv_path, progress_callback)
            else:
                translate_csv(self.csv_path, engine, progress_callback)

            # Ensure final state
            self.progress_signal.emit(100)
            self.finish_signal.emit('info', '翻译完成！')
        except Exception as e:
            self.finish_signal.emit('error', str(e))
        finally:
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
