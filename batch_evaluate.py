#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量搜索并评估连锁名称置信度
"""

import json
import pandas as pd
from pathlib import Path
import time

def evaluate_from_search_result(name, search_text):
    """
    根据搜索结果文本评估置信度

    评分标准：
    - 0.95-1.00: 明确的连锁总部，有"集团"、"连锁有限公司"、门店数量等明确信息
    - 0.85-0.94: 连锁品牌，有"连锁"、"药店"等关键词
    - 0.70-0.84: 可能是连锁，有"药房"、"医药"等关键词
    - 0.50-0.69: 信息不明确
    - 0.00-0.49: 不太可能是连锁总部
    """
    if not search_text or search_text == "[]":
        return 0.30  # 无搜索结果，默认低置信度

    text = search_text.lower()

    # 高置信度指标
    high_indicators = [
        '连锁', 'chain', '集团', 'group', '股份有限公司',
        '总部', 'headquarters', '门店', '家门店', '分店',
        '上市', 'listed', '有限公司', 'co. ltd', 'corp'
    ]

    # 中等置信度指标
    medium_indicators = [
        '药店', '药房', 'pharmacy', '大药房',
        '医药', 'medicine', '连锁公司'
    ]

    # 计算得分
    high_score = sum(1 for ind in high_indicators if ind in text)
    medium_score = sum(1 for ind in medium_indicators if ind in text)

    # 基础分数
    if high_score >= 4:
        confidence = 0.95
    elif high_score >= 3:
        confidence = 0.90
    elif high_score >= 2:
        confidence = 0.85
    elif high_score >= 1:
        confidence = 0.75
    elif medium_score >= 3:
        confidence = 0.65
    elif medium_score >= 2:
        confidence = 0.55
    elif medium_score >= 1:
        confidence = 0.45
    else:
        confidence = 0.30

    # 调整因子
    if '旗舰店' in text or '官方' in text or '官网' in text:
        confidence = min(confidence + 0.05, 1.0)

    if '万达' in name or '广场' in name:
        confidence = max(confidence - 0.2, 0.1)

    return round(confidence, 2)

def manual_evaluation_mode():
    """
    手动评估模式：读取待评估列表，提示用户手动搜索
    """
    base_dir = Path("/Users/ruizhang/Desktop/Projects/连锁名称清洗关联")
    chain_names_file = base_dir / "chain_names.json"
    results_file = base_dir / "manual_evaluation_results.json"

    # 加载连锁名称
    with open(chain_names_file, 'r', encoding='utf-8') as f:
        all_names = json.load(f)

    chain_names = [name for name in all_names if name != '\\N']

    print(f"共 {len(chain_names)} 个待评估的连锁名称")
    print("\n请按照以下格式手动评估并保存到JSON文件：")
    print("""
[
  {
    "name": "一心堂",
    "confidence": 0.95,
    "notes": "知名连锁药店，上市公司"
  },
  ...
]
    """)

    return chain_names

def auto_evaluate_sample():
    """
    自动评估样本 - 基于已知的搜索结果
    """
    # 基于前面的搜索结果，创建一个样本评估
    sample_results = [
        {"name": "一心堂（图形商标）", "confidence": 0.95, "notes": "知名连锁药店，上市公司，股票代码002727"},
        {"name": "上海医药嘉定大药房连锁有限公司", "confidence": 0.95, "notes": "上海医药集团旗下，46家分支机构"},
        {"name": "上海得一大药房连锁有限公司", "confidence": 0.90, "notes": "连锁有限公司"},
        {"name": "上海药房连锁", "confidence": 0.85, "notes": "明确标注连锁"},
        {"name": "云湖医药", "confidence": 0.90, "notes": "上海云湖医药连锁经营有限公司，37家门店"},
        {"name": "京东", "confidence": 0.95, "notes": "京东健康，大型连锁医药电商"},
        {"name": "仁携大药房（上海）", "confidence": 0.90, "notes": "上海仁携大药房连锁有限公司，26家门店"},
        {"name": "余天成大药房", "confidence": 0.85, "notes": "大药房连锁品牌"},
        {"name": "养和堂", "confidence": 0.85, "notes": "连锁药房"},
        {"name": "北京同仁堂", "confidence": 0.95, "notes": "知名连锁药店品牌"},
        {"name": "北京同仁堂（北京）", "confidence": 0.95, "notes": "北京同仁堂分支"},
        {"name": "华氏", "confidence": 0.85, "notes": "华氏大药房连锁"},
        {"name": "华泰药店", "confidence": 0.75, "notes": "药店，可能是连锁"},
        {"name": "叮当快药", "confidence": 0.95, "notes": "叮当快药科技集团，知名连锁"},
        {"name": "同祺智慧大药房", "confidence": 0.70, "notes": "大药房，信息较少"},
        {"name": "嘉荫堂", "confidence": 0.65, "notes": "可能是药房"},
        {"name": "国大药房", "confidence": 0.95, "notes": "国药控股国大药房，全国连锁，3000+门店"},
        {"name": "圆心大药房", "confidence": 0.85, "notes": "圆心科技旗下药房"},
        {"name": "好药师", "confidence": 0.95, "notes": "九州通旗下，好药师大药房连锁，21000+门店"},
        {"name": "好药师大药房", "confidence": 0.95, "notes": "好药师大药房连锁有限公司"},
    ]

    return sample_results

def save_results_to_json(results, output_file):
    """保存结果到JSON"""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"已保存 {len(results)} 条评估结果到 {output_file}")

def update_excel_with_confidence(excel_file, results, output_file):
    """更新Excel文件，添加置信度列"""
    df = pd.read_excel(excel_file)

    # 创建置信度映射
    confidence_map = {result['name']: result['confidence'] for result in results}

    # 添加置信度列
    df['置信度'] = df['连锁名称'].map(confidence_map)

    # 填充未评估的名称为默认值
    df['置信度'] = df['置信度'].fillna(0.30)

    # 保存
    df.to_excel(output_file, index=False, engine='openpyxl')
    print(f"\n已更新Excel文件: {output_file}")
    print(f"总计 {len(results)} 个名称已评估")

if __name__ == "__main__":
    base_dir = Path("/Users/ruizhang/Desktop/Projects/连锁名称清洗关联")

    print("连锁名称置信度评估工具\n")
    print("1. 基于已知搜索结果自动评估样本")
    print("2. 手动评估模式（需要手动搜索并输入结果）")

    choice = input("\n请选择模式 (1/2): ").strip()

    if choice == "1":
        print("\n正在生成样本评估...")
        results = auto_evaluate_sample()
        results_file = base_dir / "confidence_results_sample.json"
        save_results_to_json(results, results_file)

        # 更新Excel
        excel_input = base_dir / "O2O连锁名称.xlsx"
        excel_output = base_dir / "O2O连锁名称_带置信度_样本.xlsx"
        update_excel_with_confidence(excel_input, results, excel_output)

    elif choice == "2":
        chain_names = manual_evaluation_mode()

    else:
        print("无效选择")
