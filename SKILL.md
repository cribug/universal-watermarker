---
name: Universal Watermarker
slug: universal-watermarker
version: 1.1.0
author: Cribug
tags: [pdf, image, tool, security, watermark]
---

# Universal Watermarker Skill

该技能可以为 PDF 文件和主流图片格式（JPG, PNG, BMP）添加自定义文本水印。支持智能跨平台中文字体识别，以及企业级防伪平铺模式。

## 运行环境
- **Language**: Python 3.8+
- **Dependencies**: pypdf, reportlab, Pillow
- **OS Support**: Windows, macOS, Linux (无系统级底层 GUI 依赖)

## 参数定义 (Parameters)

| 参数名 | 类型 | 必填 | 默认值 | 描述 |
| :--- | :--- | :--- | :--- | :--- |
| `files` | list/string | 是 | 无 | 需要处理的文件绝对或相对路径（支持单个路径字符串或路径列表）。 |
| `text` | string | 是 | 无 | 水印文字内容（如 "内部机密"）。 |
| `opacity` | float | 否 | `0.3` | 水印不透明度，范围 0.0 到 1.0。 |
| `font_size` | int | 否 | `50` | 水印字体大小。 |
| `mode` | string | 否 | `"center"` | 排版模式：`"center"` (居中单水印) 或 `"tile"` (全图平铺防伪网格)。 |
| `angle` | int | 否 | `30` | 水印倾斜角度（仅在 `mode="tile"` 时生效）。 |
| `auto_adjust` | bool | 否 | `True` | **[新]** 开启后自动根据背景亮度切换黑/白水印，建议开启。 |

## 输入与输出规范 (I/O)
- **存储位置**: 处理后的文件直接保存在原文件所在目录下。
- **命名约定**: 输出文件名为 `wm_` 前缀加上原文件名。

## AI 调用指令参考 (Instructions for LLM)
1. **语义推断**：如果用户要求“防伪”、“机密保护”、“铺满”，请自动设置 `mode="tile"`。如果用户要求“淡一点”，请将 `opacity` 调低至 0.1-0.2。
2. **确认闭环**：执行 `process_files` 完毕后，必须向用户明确播报输出文件的确切路径和名称，不要让用户自己去寻找。
