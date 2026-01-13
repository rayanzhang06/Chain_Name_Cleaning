#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
连锁名称置信度评估脚本
通过在线搜索评估每个连锁名称为总部名称的概率
"""

import pandas as pd
import json
from pathlib import Path
import subprocess
import re

def load_chain_names(file_path):
    """加载连锁名称列表"""
    with open(file_path, 'r', encoding='utf-8') as f:
        all_names = json.load(f)
    return [name for name in all_names if name != '\\N']

def evaluate_confidence(search_result_text):
    """
    根据搜索结果文本评估置信度
    返回0-1之间的浮点数
    """
    if not search_result_text:
        return 0.0

    text = search_result_text.lower()

    # 高置信度指标
    high_confidence_indicators = [
        '连锁', 'chain', '集团', 'group', '有限公司', 'co. ltd',
        '股份有限公司', 'corp', '总部', 'headquarters',
        '上市', 'listed', '门店', 'store', '家门店', '分店'
    ]

    # 中等置信度指标
    medium_confidence_indicators = [
        '药店', '药房', 'pharmacy', '医药', 'medicine',
        '大药房', '医药连锁'
    ]

    # 计算置信度
    score = 0.0

    # 检查高置信度指标
    high_count = sum(1 for indicator in high_confidence_indicators if indicator in text)
    medium_count = sum(1 for indicator in medium_confidence_indicators if indicator in text)

    # 基础分数
    if high_count >= 3:
        score = 0.95
    elif high_count >= 2:
        score = 0.85
    elif high_count >= 1:
        score = 0.70
    elif medium_count >= 2:
        score = 0.60
    elif medium_count >= 1:
        score = 0.40
    else:
        score = 0.20

    # 调整因子
    if '旗舰店' in text or '官方' in text:
        score = min(score + 0.05, 1.0)

    return round(score, 2)

def save_results(results, output_file):
    """保存评估结果到JSON文件"""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

def update_excel_with_confidence(excel_file, results, output_file):
    """更新Excel文件，添加置信度列"""
    # 读取原始Excel
    df = pd.read_excel(excel_file)

    # 创建置信度映射字典
    confidence_map = {result['name']: result['confidence'] for result in results}

    # 添加置信度列
    df['置信度'] = df['连锁名称'].map(confidence_map)

    # 保存到新文件
    df.to_excel(output_file, index=False, engine='openpyxl')
    print(f"\n已保存到: {output_file}")
    print(f"总计处理 {len(results)} 个连锁名称")

if __name__ == "__main__":
    # 文件路径
    base_dir = Path("/Users/ruizhang/Desktop/Projects/连锁名称清洗关联")
    chain_names_file = base_dir / "chain_names.json"
    results_file = base_dir / "confidence_results.json"
    excel_input = base_dir / "O2O连锁名称.xlsx"
    excel_output = base_dir / "O2O连锁名称_带置信度.xlsx"

    # 加载连锁名称
    print("加载连锁名称...")
    chain_names = load_chain_names(chain_names_file)
    print(f"共 {len(chain_names)} 个待评估的连锁名称\n")

    # 这里需要配合搜索工具使用
    # 实际搜索将通过WebSearch工具完成
    print("准备使用WebSearch工具进行批量搜索...")
    print("请使用搜索工具，然后将结果保存到 confidence_results.json")
