# 本地化翻译工具

## 功能简介

- 支持读取指定格式的CSV表格，自动识别源语言和目标语言列
- 支持Google翻译和OpenAI大模型两种翻译方式（可下拉选择）
- 支持根据上下文（Context列）辅助翻译
- 翻译异常会在Notes列备注
- 翻译结果自动写回原表格
- 提供简洁易用的GUI界面

## 环境依赖

```bash
pip install -r requirements.txt
```

## API配置

### Google翻译API

1. 注册Google Cloud账号，启用Cloud Translation API。
2. 获取API密钥或服务账号JSON文件。
3. 设置环境变量：
   - API Key方式：`GOOGLE_API_KEY=你的key`
   - 服务账号方式：`GOOGLE_APPLICATION_CREDENTIALS=你的json路径`

### OpenAI API

1. 注册OpenAI账号，获取API Key。
2. 设置环境变量：`OPENAI_API_KEY=你的key`

## 启动方法

```bash
python main.py
```

## 目录结构

- main.py         # 程序入口，启动GUI
- gui.py          # GUI界面
- translator.py   # 翻译逻辑
- utils.py        # CSV处理
- requirements.txt
- README.md
