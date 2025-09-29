def translate_json(data, engine, filepath, progress_callback=None):
    # data: list[dict]，每个dict为一条数据，字段名为key
    import pandas as pd
    from utils import write_json
    total = len(data)
    # 识别所有语言字段（排除源语言、Tag、Context、Plural、Notes等）
    if total == 0:
        return
    keys = list(data[0].keys())
    # 源语言字段
    source_col = None
    for k in keys:
        if k.lower().startswith('source') or k == '源语言' or k == 'SourceZH':
            source_col = k
            break
    context_col = None
    for k in keys:
        if 'context' in k.lower() or '语境' in k:
            context_col = k
            break
    notes_col = None
    for k in keys:
        if 'notes' in k.lower() or '备注' in k:
            notes_col = k
            break
    # 目标语言列
    lang_cols = [k for k in keys if k not in [source_col, context_col, notes_col, 'Tag', 'Plural']]
    total_langs = len(lang_cols)
    total_tasks = total * total_langs
    task_idx = 0
    import time
    for i, row in enumerate(data):
        row_start = time.time()
        src_text = str(row.get(source_col, ''))
        context = str(row.get(context_col, '')) if context_col else ''
        for lang_idx, lang in enumerate(lang_cols):
            val = row.get(lang, None)
            if val is None or str(val).strip() == '' or str(val).strip() == src_text:
                target_code = lang
                if engine == 'Google':
                    trans, err = google_translate_text(src_text, target_code, 'zh-CN')
                else:
                    trans, err = openai_translate_text(src_text, target_code, 'zh-CN', context)
                if i < 5:
                    print(f"第{i+1}条，源文: {src_text}，目标: {target_code}，返回: {trans if trans else err}")
                if trans:
                    row[lang] = trans
                else:
                    if notes_col:
                        old_note = str(row.get(notes_col, '')) if row.get(notes_col) else ''
                        row[notes_col] = (old_note + '; ' if old_note else '') + f"翻译失败: {err}"
            # 细粒度进度信息（每个语种）
            if progress_callback:
                short_src = src_text if len(src_text) <= 20 else src_text[:17] + '...'
                info_text = f"正在翻译{i+1}/{total}条：\"{short_src}\"->{lang}({lang_idx+1}/{total_langs})"
                percent = int(((i * total_langs) + (lang_idx + 1)) / total_tasks * 100)
                progress_callback(percent, info_text, None)
        # 行级进度信息（用于时间统计）
        task_idx += total_langs
        if progress_callback:
            row_time = time.time() - row_start
            progress_callback(percent, None, row_time)
    write_json(data, filepath)
import os
import openai
from google.cloud import translate_v2 as google_translate
import pandas as pd
from utils import read_csv, write_csv
import time

# 语言代码映射（可根据需要补充）
LANG_MAP = {
    '简体中文': 'zh-CN', '繁体中文': 'zh-TW', '英语': 'en', '日语': 'ja', '韩语': 'ko',
    '德语': 'de', '法语': 'fr', '意大利语': 'it', '西班牙语（西班牙）': 'es', '西班牙语（拉美）': 'es',
    '葡萄牙语（葡萄牙）': 'pt', '葡萄牙语（巴西）': 'pt', '俄语': 'ru', '泰语': 'th',
    '越南语': 'vi', '波兰语': 'pl', '土耳其语': 'tr'
}

# 获取Google翻译客户端
_g_client = None
def get_google_client():
    global _g_client
    if _g_client is None:
        _g_client = google_translate.Client()
    return _g_client

# 调用Google翻译
def google_translate_text(text, target, source=None):
    # 跳过源语言和目标语言相同的情况
    if source and target and source.lower() == target.lower():
        return text, None
    client = get_google_client()
    try:
        result = client.translate(text, target_language=target, source_language=source)
        return result['translatedText'], None
    except Exception as e:
        return None, str(e)

# 调用OpenAI翻译
def openai_translate_text(text, target, source=None, context=None):
    prompt = f"将以下内容从{source or '原文'}翻译为{target}。\n上下文：{context or ''}\n原文：{text}\n翻译："
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        print("当前使用的OPENAI_API_KEY:", api_key)
        client = openai.OpenAI(api_key=api_key)  # 新版用OpenAI类
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=2048
        )
        return response.choices[0].message.content.strip(), None
    except Exception as e:
        return None, str(e)

def translate_csv(filepath, engine, progress_callback=None):
    # 1. 解析csv为json结构（复用gui.py的export_json逻辑）
    import pandas as pd, json, os
    df = pd.read_csv(filepath, header=None, encoding='utf-8')
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

    # 2. 调用json翻译接口
    translate_json(data, engine, filepath, progress_callback)

    # 3. 翻译后写回csv（复用gui.py的export_csv逻辑）
    import pandas as pd
    df2 = pd.DataFrame(data)
    columns = list(df2.columns)
    field_row = columns
    data_rows = df2.values.tolist()
    # 保留原csv第一行（如有）
    orig_first_row = list(df.iloc[0]) if len(df) > 0 else ['' for _ in columns]
    all_rows = [orig_first_row, field_row] + data_rows
    with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
        import csv
        writer = csv.writer(f)
        for row in all_rows:
            writer.writerow(row)
