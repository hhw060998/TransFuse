# 本地化翻译工具（TransFuse）

## 简介

本工具是一款面向本地化团队和开发者的多语言翻译辅助软件，支持CSV/JSON格式互转、AI/Google翻译引擎、进度可视化、拖拽操作、异常处理等功能，极大提升本地化流程的效率和体验。

## 主要功能

- 支持CSV与JSON文件互相转换
- 一键接入Google翻译或OpenAI大模型自动翻译
- 支持导入Google服务账号JSON，自动设置API Key
- 进度条与预计剩余时间实时显示，翻译完成用时统计
- 支持拖拽文件、拖拽API Key JSON到指定区域
- 多线程后台翻译，UI不卡顿
- 取消/停止翻译时可选择是否保存已翻译内容
- 详细异常提示，自动跳过格式错误行
- 导出CSV时自动跳过备注行，避免多余空列

## 使用方法

1. 选择待翻译的CSV或JSON文件（可拖拽或点击选择）
2. 选择翻译引擎（Google或OpenAI）
3. 若选择Google，需导入API Key JSON（支持拖拽或浏览）
4. 点击“开始翻译”，可实时查看进度和预计剩余时间
5. 可随时点击“停止并保存”或“取消”
6. 翻译完成后可导出为CSV或JSON

## 特色亮点

- 兼容多种本地化表结构，自动识别字段
- 进度条、剩余时间、用时统计一目了然
- 支持大文件、长文本批量翻译
- 代码结构清晰，易于二次开发

---

# TransFuse

## Introduction

This tool is a productivity booster for localization teams and developers, supporting CSV/JSON conversion, AI/Google translation, progress visualization, drag-and-drop, robust error handling, and more. It greatly streamlines the localization workflow.

## Main Features

- Convert between CSV and JSON files
- One-click Google Translate or OpenAI GPT translation
- Import Google service account JSON and auto-set API Key
- Real-time progress bar, ETA, and time used statistics
- Drag-and-drop for files and API Key JSON
- Multithreaded background translation, smooth UI
- Cancel/stop translation with or without saving progress
- Detailed error messages, auto-skip malformed lines
- Exported CSV skips comment row, avoids extra empty columns

## Usage

1. Select the CSV or JSON file to translate (drag-and-drop or browse)
2. Choose translation engine (Google or OpenAI)
3. If Google is selected, import API Key JSON (drag-and-drop or browse)
4. Click "Start Translation" to see real-time progress and ETA
5. You can click "Stop and Save" or "Cancel" at any time
6. Export results as CSV or JSON after translation

## Highlights

- Compatible with various localization table structures, auto field recognition
- Clear progress bar, ETA, and time statistics
- Supports large files and batch translation
- Clean codebase, easy for secondary development
