import pandas as pd

def read_csv(filepath):
    return pd.read_csv(filepath, encoding='utf-8')

def write_csv(df, filepath):
    df.to_csv(filepath, index=False, encoding='utf-8-sig')
