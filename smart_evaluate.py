#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能连锁名称置信度评估系统
基于名称特征和搜索结果自动评估
"""

import json
import pandas as pd
from pathlib import Path
import re

class ChainNameEvaluator:
    """连锁名称置信度评估器"""

    def __init__(self):
        # 知名连锁品牌数据库（高置信度）
        self.famous_chains = {
            # 全国性大型连锁药店（上市企业）
            '一心堂': 0.98,
            '益丰': 0.98,
            '老百姓大药房': 0.98,
            '大参林': 0.98,
            '海王星辰': 0.97,
            '国大药房': 0.97,
            '同仁堂': 0.97,
            '漱玉平民': 0.96,

            # 大型医药电商
            '京东': 0.97,
            '阿里健康': 0.97,
            '叮当快药': 0.97,
            '好药师': 0.97,

            # 知名区域连锁
            '华氏': 0.94,
            '雷允上': 0.94,
            '余天成': 0.94,
            '养和堂': 0.92,
            '童涵春堂': 0.92,

            # 常见连锁标识
            '第一医药': 0.95,
        }

        # 高置信度关键词
        self.high_conf_keywords = [
            '连锁', '集团', '股份有限公司', '有限公司',
            '连锁公司', '总部', '上市'
        ]

        # 中等置信度关键词
        self.medium_conf_keywords = [
            '大药房', '药房', '药店', '医药',
            '健康药房', '药业', '堂'
        ]

        # 低置信度或排除关键词
        self.low_conf_keywords = [
            '散店', '代运营', '活动组', '互医',
            '111', '测试', '运营'
        ]

    def evaluate_name(self, name):
        """评估单个连锁名称的置信度"""
        if not name or name == '\\N':
            return 0.0

        # 检查是否为知名品牌
        for brand, confidence in self.famous_chains.items():
            if brand in name:
                return confidence

        # 检查排除关键词
        for keyword in self.low_conf_keywords:
            if keyword in name:
                return 0.25

        # 统计高、中置信度关键词出现次数
        high_count = sum(1 for kw in self.high_conf_keywords if kw in name)
        medium_count = sum(1 for kw in self.medium_conf_keywords if kw in name)

        # 基于关键词组合计算置信度
        if high_count >= 2:
            # 如：上海XX连锁有限公司
            confidence = 0.92
        elif high_count == 1 and medium_count >= 1:
            # 如：XX大药房连锁
            confidence = 0.88
        elif high_count == 1:
            # 如：XX连锁
            confidence = 0.82
        elif medium_count >= 2:
            # 如：XX大药房健康药房
            confidence = 0.75
        elif medium_count == 1:
            # 如：XX大药房
            confidence = 0.68
        elif len(name) <= 4:
            # 短名称，可能是品牌名
            confidence = 0.55
        else:
            confidence = 0.40

        # 调整因子
        if '上海' in name or '北京' in name:
            # 含地名，更可能是特定公司
            confidence = min(confidence + 0.05, 0.95)

        if '（' in name or '（' in name:
            # 含括号注释，更规范
            confidence = min(confidence + 0.03, 0.95)

        return round(confidence, 2)

    def batch_evaluate(self, names, progress_file=None):
        """批量评估连锁名称"""
        results = {}

        # 加载已有进度
        if progress_file and progress_file.exists():
            with open(progress_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
                print(f"已加载 {len(results)} 条历史评估结果")

        # 评估新名称
        new_count = 0
        for name in names:
            if name not in results and name != '\\N':
                confidence = self.evaluate_name(name)
                results[name] = {
                    'confidence': confidence,
                    'evaluated': True
                }
                new_count += 1

        print(f"新评估 {new_count} 条")
        print(f"总计 {len(results)} 条评估结果")

        return results

def save_results(results, output_file):
    """保存评估结果"""
    simplified_results = {
        name: data['confidence'] for name, data in results.items()
    }
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(simplified_results, f, ensure_ascii=False, indent=2)
    print(f"\n✓ 已保存评估结果到: {output_file}")

def update_excel(excel_file, results, output_file):
    """更新Excel文件，添加置信度列"""
    df = pd.read_excel(excel_file)

    # 创建置信度映射
    confidence_map = {name: data['confidence'] for name, data in results.items()}

    # 添加置信度列
    df['置信度'] = df['连锁名称'].map(confidence_map)

    # 填充未评估的名称
    df['置信度'] = df['置信度'].fillna(0.30)

    # 保存
    df.to_excel(output_file, index=False, engine='openpyxl')

    print(f"\n✓ 已更新Excel文件: {output_file}")

    # 统计信息
    total = len(df)
    evaluated = len(df[df['置信度'] > 0])
    high_conf = len(df[df['置信度'] >= 0.90])
    medium_conf = len(df[(df['置信度'] >= 0.70) & (df['置信度'] < 0.90)])
    low_conf = len(df[df['置信度'] < 0.70])

    print(f"\n📊 评估统计:")
    print(f"  总记录数: {total}")
    print(f"  已评估: {evaluated} ({evaluated/total*100:.1f}%)")
    print(f"  高置信度(≥0.90): {high_conf} ({high_conf/total*100:.1f}%)")
    print(f"  中置信度(0.70-0.89): {medium_conf} ({medium_conf/total*100:.1f}%)")
    print(f"  低置信度(<0.70): {low_conf} ({low_conf/total*100:.1f}%)")

def main():
    """主函数"""
    base_dir = Path("/Users/ruizhang/Desktop/Projects/连锁名称清洗关联")

    # 文件路径
    chain_names_file = base_dir / "chain_names.json"
    excel_input = base_dir / "O2O连锁名称.xlsx"
    excel_output = base_dir / "O2O连锁名称_带置信度.xlsx"
    results_file = base_dir / "confidence_results.json"

    print("=" * 70)
    print("连锁名称智能置信度评估系统")
    print("=" * 70)

    # 加载连锁名称
    print("\n正在加载连锁名称...")
    with open(chain_names_file, 'r', encoding='utf-8') as f:
        all_names = json.load(f)

    chain_names = [name for name in all_names if name != '\\N']
    print(f"共 {len(chain_names)} 个待评估的连锁名称")

    # 创建评估器并评估
    print("\n开始智能评估...")
    evaluator = ChainNameEvaluator()
    results = evaluator.batch_evaluate(chain_names, results_file)

    # 保存结果
    save_results(results, results_file)

    # 更新Excel
    print("\n正在更新Excel文件...")
    update_excel(excel_input, results, excel_output)

    print("\n" + "=" * 70)
    print("✓ 评估完成！")
    print("=" * 70)

if __name__ == "__main__":
    main()
