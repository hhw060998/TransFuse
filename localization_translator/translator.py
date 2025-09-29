# translator.py (关键部分：translate_json / translate_csv + 辅助翻译函数)
import os
import time
import openai
from google.cloud import translate_v2 as google_translate
import pandas as pd
from utils import read_csv, write_csv, write_json  # 假设 utils 有这些函数

# 语言代码映射（可根据需要补充）
LANG_MAP = {
    '简体中文': 'zh-CN', '繁体中文': 'zh-TW', '英语': 'en', '日语': 'ja', '韩语': 'ko',
    '德语': 'de', '法语': 'fr', '意大利语': 'it', '西班牙语（西班牙）': 'es', '西班牙语（拉美）': 'es',
    '葡萄牙语（葡萄牙）': 'pt', '葡萄牙语（巴西）': 'pt', '俄语': 'ru', '泰语': 'th',
    '越南语': 'vi', '波兰语': 'pl', '土耳其语': 'tr'
}

# Google client 缓存
_g_client = None
def get_google_client():
    global _g_client
    if _g_client is None:
        _g_client = google_translate.Client()
    return _g_client

def google_translate_text(text, target, source=None):
    if not text:
        return '', None
    # 若 target 看起来是中文文字（非 code），尝试映射
    if target in LANG_MAP:
        target_code = LANG_MAP[target]
    else:
        target_code = target
    if source and target_code and source.lower() == target_code.lower():
        return text, None
    client = get_google_client()
    try:
        result = client.translate(text, target_language=target_code, source_language=source)
        return result['translatedText'], None
    except Exception as e:
        return None, str(e)

def openai_translate_text(text, target, source=None, context=None):
    if not text:
        return '', None
    # map target if needed
    if target in LANG_MAP:
        target_code = LANG_MAP[target]
    else:
        target_code = target
    prompt = f"将以下内容从{source or '原文'}翻译为{target_code}。\n上下文：{context or ''}\n原文：{text}\n翻译："
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=2048
        )
        # 兼容旧/new 返回结构
        content = None
        try:
            content = response.choices[0].message.content.strip()
        except Exception:
            # fallback if different shape
            content = str(response)
        return content, None
    except Exception as e:
        return None, str(e)


def translate_json(data, engine, filepath, progress_callback=None, cancel_checker=None):
    """
    data: list[dict]
    engine: 'Google' or 'OpenAI'
    filepath: 用于写回（write_json）
    progress_callback: function(percent: float, info: str|None=None, row_time: float|None=None, done: int|None=None, total: int|None=None)
    cancel_checker: callable() -> bool, 返回 True 则中止翻译（协作式）
    """
    total = len(data)
    if total == 0:
        # 仍然写个空文件
        write_json(data, filepath)
        return

    keys = list(data[0].keys())
    # 检测列
    source_col = None
    for k in keys:
        if k and (k.lower().startswith('source') or k == '源语言' or k == 'SourceZH'):
            source_col = k
            break
    context_col = None
    for k in keys:
        if k and ('context' in k.lower() or '语境' in k):
            context_col = k
            break
    notes_col = None
    for k in keys:
        if k and ('notes' in k.lower() or '备注' in k):
            notes_col = k
            break

    # 目标语言列（排除已识别的列）
    exclude = {source_col, context_col, notes_col, 'Tag', 'Plural'}
    lang_cols = [k for k in keys if k not in exclude and k is not None]
    total_langs = len(lang_cols)
    if total_langs == 0:
        write_json(data, filepath)
        return

    total_tasks = total * total_langs
    task_done = 0

    # 让 GUI 先知道总数（可选）
    if progress_callback:
        try:
            progress_callback(0.0, f'准备翻译：{total}行 × {total_langs}语种 = {total_tasks}项', None, 0, total_tasks)
        except Exception:
            pass

    for i, row in enumerate(data):
        if cancel_checker and cancel_checker():
            # 提示取消
            if progress_callback:
                try:
                    progress_callback((task_done / total_tasks) * 100.0, '已取消', None, task_done, total_tasks)
                except Exception:
                    pass
            break

        row_start = time.time()
        src_text = str(row.get(source_col, '') or '')
        context = str(row.get(context_col, '') or '') if context_col else ''
        for lang_idx, lang in enumerate(lang_cols):
            # 每个目标语言都视为一个子任务，无论是否实际调用翻译（保持进度一致）
            # 如果该 cell 有已存在翻译且非空且不等于源文，则视为已完成（跳过调用）
            existing = row.get(lang, None)
            need_translate = (existing is None) or (str(existing).strip() == '') or (str(existing).strip() == src_text)
            trans = None
            err = None

            if need_translate and src_text.strip():
                # 检查取消
                if cancel_checker and cancel_checker():
                    break
                if engine == 'Google':
                    trans, err = google_translate_text(src_text, lang, 'zh-CN')
                else:
                    trans, err = openai_translate_text(src_text, lang, 'zh-CN', context)
                if trans:
                    row[lang] = trans
                else:
                    # 记录失败信息到 notes 列（不覆盖已有备注）
                    if notes_col:
                        old_note = str(row.get(notes_col, '')) if row.get(notes_col) else ''
                        row[notes_col] = (old_note + '; ' if old_note else '') + f"翻译失败({lang}): {err}"
            # 即便跳过翻译，也视为完成子任务
            task_done += 1

            # 细粒度回调：每做完一个语种就回调（不带 row_time）
            if progress_callback:
                short_src = src_text if len(src_text) <= 20 else src_text[:17] + '...'
                info_text = f'正在翻译 {i+1}/{total}：\"{short_src}\" -> {lang} ({lang_idx+1}/{total_langs})'
                try:
                    percent = (task_done / total_tasks) * 100.0
                except Exception:
                    percent = 0.0
                try:
                    progress_callback(percent, info_text, None, task_done, total_tasks)
                except Exception:
                    pass

            # 取消再次检查，尽快退出
            if cancel_checker and cancel_checker():
                break

        # 行级回调，带上该行耗时信息（用于 GUI ETA）
        row_time = time.time() - row_start
        if progress_callback:
            try:
                percent = (task_done / total_tasks) * 100.0
            except Exception:
                percent = 0.0
            try:
                progress_callback(percent, None, row_time, task_done, total_tasks)
            except Exception:
                pass

        # 如果在内层循环因取消跳出，则外层也退出
        if cancel_checker and cancel_checker():
            break

    # 写回文件（覆盖原 filepath）
    write_json(data, filepath)
    # 最后确保回调到 100%
    if progress_callback:
        try:
            progress_callback(100.0, '翻译已完成（或已取消）', None, task_done, total_tasks)
        except Exception:
            pass


def translate_csv(filepath, engine, progress_callback=None, cancel_checker=None):
    """
    解析 CSV -> 调用 translate_json -> 写回 CSV
    注意：callback 和 cancel_checker 直接透传给 translate_json
    """
    import csv
    df = pd.read_csv(filepath, header=None, encoding='utf-8')
    raw_fields = list(df.iloc[1]) if len(df) > 1 else []
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

    # 将 CSV 转换后的 data 传入 translate_json（支持 progress_callback & cancel_checker）
    translate_json(data, engine, filepath, progress_callback=progress_callback, cancel_checker=cancel_checker)

    # 翻译完成后把 data 写回 CSV（保持原第一行 header if present）
    df2 = pd.DataFrame(data)
    columns = list(df2.columns)
    field_row = columns
    data_rows = df2.values.tolist()
    orig_first_row = list(df.iloc[0]) if len(df) > 0 else ['' for _ in columns]
    all_rows = [orig_first_row, field_row] + data_rows
    with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        for row in all_rows:
            writer.writerow(row)
