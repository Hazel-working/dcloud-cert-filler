# -*- coding: utf-8 -*-
"""DCloud 应用签名信息自动填写工具。

分层：parser（纯解析） -> config（清单 + 目录自动发现）
      -> filler / console_gen（填表通道）
      -> cli（编排与人工确认） -> report（留痕）
"""
__version__ = "0.2.0"
