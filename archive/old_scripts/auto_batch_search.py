#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动化批量搜索并评估连锁名称置信度
分批次处理所有连锁名称
"""

import json
import pandas as pd
from pathlib import Path
import time

def evaluate_confidence(name, search_results):
    """
    根据搜索结果评估置信度

    评分标准：
    - 0.95-1.00: 明确的连锁总部，有公司信息、门店数量
    - 0.85-0.94: 连锁品牌，明确有"连锁"等关键词
    - 0.70-0.84: 可能是连锁，有"药房"、"医药"等
    - 0.50-0.69: 信息不明确
    - 0.30-0.49: 不太可能是连锁总部
    - 0.00-0.29: 无搜索结果
    """
    if not search_results or search_results == "[]":
        # 基于名称本身的特征进行评估
        return evaluate_from_name_only(name)

    # 将搜索结果转为小写
    text = str(search_results).lower()

    # 高置信度关键词
    high_keywords = ['连锁', 'chain', '集团', 'group', '股份有限公司',
                    '总部', 'headquarters', '门店', '家门店', '分店',
                    '上市', '有限公司', 'co. ltd', 'corp', '连锁公司']

    # 中等置信度关键词
    medium_keywords = ['药店', '药房', 'pharmacy', '大药房',
                      '医药', 'medicine', '连锁']

    # 低置信度关键词
    low_keywords = ['店', '商店', '便利店', '超市']

    high_count = sum(1 for kw in high_keywords if kw in text)
    medium_count = sum(1 for kw in medium_keywords if kw in text)
    low_count = sum(1 for kw in low_keywords if kw in text)

    # 计算置信度
    if high_count >= 4:
        confidence = 0.95
    elif high_count >= 3:
        confidence = 0.90
    elif high_count >= 2:
        confidence = 0.85
    elif high_count >= 1 and medium_count >= 2:
        confidence = 0.80
    elif high_count >= 1:
        confidence = 0.75
    elif medium_count >= 3:
        confidence = 0.70
    elif medium_count >= 2:
        confidence = 0.65
    elif medium_count >= 1:
        confidence = 0.60
    elif low_count >= 2:
        confidence = 0.45
    else:
        confidence = 0.40

    # 调整因子
    if any(word in text for word in ['官方', '官网', '旗舰店']):
        confidence = min(confidence + 0.05, 1.0)

    return round(confidence, 2)

def evaluate_from_name_only(name):
    """
    仅基于名称本身评估置信度（用于无搜索结果时）
    """
    if not name or name == '\\N':
        return 0.0

    name_lower = name.lower()

    # 明确的连锁标识
    if any(word in name for word in ['连锁', '集团', '有限公司', '股份']):
        return 0.85

    # 连锁药店常见词
    pharmacy_keywords = ['药房', '药店', '大药房', '医药', '堂']
    if any(kw in name for kw in pharmacy_keywords):
        return 0.70

    # 可能是品牌名
    if len(name) <= 4:
        return 0.60

    return 0.40

def create_batch_search_list():
    """
    创建批量搜索列表
    返回所有需要搜索的连锁名称
    """
    base_dir = Path("/Users/ruizhang/Desktop/Projects/连锁名称清洗关联")
    chain_names_file = base_dir / "chain_names.json"

    with open(chain_names_file, 'r', encoding='utf-8') as f:
        all_names = json.load(f)

    # 过滤掉\N
    chain_names = [name for name in all_names if name != '\\N']

    print(f"总共需要搜索 {len(chain_names)} 个连锁名称")

    return chain_names

def save_progress(results, progress_file):
    """保存进度"""
    with open(progress_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

def load_progress(progress_file):
    """加载进度"""
    if progress_file.exists():
        with open(progress_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def update_excel(excel_file, confidence_map, output_file):
    """更新Excel文件"""
    df = pd.read_excel(excel_file)

    # 添加置信度列
    df['置信度'] = df['连锁名称'].map(confidence_map)

    # 填充未评估的
    df['置信度'] = df['置信度'].fillna(0.30)

    # 保存
    df.to_excel(output_file, index=False, engine='openpyxl')
    print(f"\n✓ 已保存到: {output_file}")
    print(f"  总计评估: {len(confidence_map)} 个连锁名称")

if __name__ == "__main__":
    base_dir = Path("/Users/ruizhang/Desktop/Projects/连锁名称清洗关联")
    progress_file = base_dir / "search_progress.json"
    results_file = base_dir / "confidence_results.json"
    excel_input = base_dir / "O2O连锁名称.xlsx"
    excel_output = base_dir / "O2O连锁名称_带置信度.xlsx"

    print("=" * 60)
    print("连锁名称批量搜索与置信度评估工具")
    print("=" * 60)

    # 加载进度
    progress = load_progress(progress_file)
    print(f"\n已加载进度: {len(progress)} 个已评估")

    # 获取所有需要搜索的名称
    chain_names = create_batch_search_list()

    # 找出待搜索的名称
    pending_names = [name for name in chain_names if name not in progress]

    print(f"待搜索: {len(pending_names)} 个\n")

    if len(pending_names) == 0:
        print("所有名称已评估完毕！")
        print("正在更新Excel文件...")
        update_excel(excel_input, progress, excel_output)
    else:
        print(f"\n准备分批搜索，请使用WebSearch工具进行搜索")
        print(f"建议每批搜索 10-20 个名称\n")

        # 输出待搜索列表（分批）
        batch_size = 20
        for i in range(0, min(len(pending_names), 100), batch_size):
            batch = pending_names[i:i+batch_size]
            print(f"\n批次 {i//batch_size + 1} (索引 {i}-{i+len(batch)-1}):")
            for j, name in enumerate(batch, 1):
                print(f"  {j}. {name}")
