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
    client = get_google_client()
    try:
        result = client.translate(text, target_language=target, source_language=source)
        return result['translatedText']
    except Exception as e:
        return None, str(e)

# 调用OpenAI翻译
openai.api_key = os.getenv('OPENAI_API_KEY')
def openai_translate_text(text, target, source=None, context=None):
    prompt = f"将以下内容从{source or '原文'}翻译为{target}。\n上下文：{context or ''}\n原文：{text}\n翻译："
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=2048
        )
        return response.choices[0].message.content.strip(), None
    except Exception as e:
        return None, str(e)

def translate_csv(filepath, engine, progress_callback=None):
    df = read_csv(filepath)
    # 找到语言列（以第二行为语言代码/名称）
    lang_row = df.iloc[1]
    lang_cols = {}
    for idx, col in enumerate(df.columns):
        lang = str(lang_row[col]).strip()
        if lang in LANG_MAP.values() or lang in LANG_MAP.keys():
            lang_cols[lang] = col
    # 源语言
    source_col = df.columns[0]
    context_col = None
    notes_col = None
    for col in df.columns:
        if 'Context' in col or '语境' in col:
            context_col = col
        if 'Notes' in col or '备注' in col:
            notes_col = col
    # 逐行翻译（从第3行到最后一个非空行）
    last_row = len(df)
    # 找到最后一个非空行（以源语言列为准）
    for idx in range(len(df)-1, 1, -1):
        if str(df.iloc[idx][source_col]).strip():
            last_row = idx + 1
            break
    for i in range(2, last_row):
        row = df.iloc[i]
        src_text = str(row[source_col])
        context = str(row[context_col]) if context_col else ''
        for lang, col in lang_cols.items():
            # 只翻译空单元格或内容与源语言相同的单元格
            if pd.isna(row[col]) or not str(row[col]).strip() or str(row[col]).strip() == src_text:
                target_code = LANG_MAP.get(lang, lang)
                if engine == 'Google':
                    trans, err = google_translate_text(src_text, target_code, 'zh-CN')
                else:
                    trans, err = openai_translate_text(src_text, target_code, 'zh-CN', context)
                if trans:
                    df.at[i, col] = trans
                else:
                    if notes_col:
                        old_note = str(df.at[i, notes_col]) if not pd.isna(df.at[i, notes_col]) else ''
                        df.at[i, notes_col] = (old_note + '; ' if old_note else '') + f"翻译失败: {err}"
        if progress_callback:
            progress_callback(int((i-1)/(last_row-2)*100))
        time.sleep(0.2)
    write_csv(df, filepath)
