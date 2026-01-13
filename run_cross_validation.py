#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
连锁名称置信度交叉验证主程序
执行完整的交叉验证流程
"""

import sys
import pandas as pd
import json
from pathlib import Path

# 导入评估器
from smart_evaluate import ChainNameEvaluator
from pattern_based_evaluator import PatternBasedEvaluator
from cross_validation_engine import CrossValidationEngine


def main():
    """主函数：执行完整的交叉验证流程"""
    base_dir = Path("/Users/ruizhang/Desktop/Projects/连锁名称清洗关联")

    print("=" * 80)
    print("连锁名称置信度交叉验证系统")
    print("=" * 80)

    # ==================== 步骤1: 加载数据 ====================
    print("\n[步骤 1/6] 加载数据...")
    excel_file = base_dir / "O2O连锁名称.xlsx"
    results_file = base_dir / "confidence_results.json"

    # 读取原始Excel
    df = pd.read_excel(excel_file)
    print(f"  ✓ 加载原始Excel: {len(df)} 条记录")

    # 读取原始评估结果
    with open(results_file, 'r', encoding='utf-8') as f:
        original_results = json.load(f)
    print(f"  ✓ 加载原始评估结果: {len(original_results)} 条")

    # 获取唯一名称列表
    unique_names = df['连锁名称'].dropna().unique().tolist()
    unique_names = [name for name in unique_names if name != '\\N']
    print(f"  ✓ 唯一连锁名称: {len(unique_names)} 个")

    # ==================== 步骤2: 初始化评估器 ====================
    print("\n[步骤 2/6] 初始化评估器...")
    evaluator1 = ChainNameEvaluator()
    evaluator2 = PatternBasedEvaluator()
    print(f"  ✓ 第一评估器（关键词匹配）: ChainNameEvaluator")
    print(f"  ✓ 第二评估器（模式匹配）: PatternBasedEvaluator")

    # ==================== 步骤3: 初始化交叉验证引擎 ====================
    print("\n[步骤 3/6] 初始化交叉验证引擎...")
    progress_file = base_dir / "cross_validation_progress.json"
    cv_engine = CrossValidationEngine(evaluator1, evaluator2)
    print(f"  ✓ 交叉验证引擎已就绪")
    print(f"  ✓ 进度文件: {progress_file.name}")

    # ==================== 步骤4: 执行交叉验证 ====================
    print("\n[步骤 4/6] 执行交叉验证...")
    print(f"  开始处理 {len(unique_names)} 个唯一名称...")
    cv_results = cv_engine.batch_cross_validate(unique_names, progress_file)
    print(f"  ✓ 完成 {len(cv_results)} 条记录的交叉验证")

    # ==================== 步骤5: 生成报告 ====================
    print("\n[步骤 5/6] 生成验证报告...")

    # 保存验证结果
    cv_results_file = base_dir / "cross_validation_results.json"
    cv_engine.save_results(cv_results_file)

    # 生成并保存报告
    report_file = base_dir / "cross_validation_report.json"
    cv_engine.save_report(report_file)

    # 打印摘要
    cv_engine.print_summary()

    # ==================== 步骤6: 导出结果 ====================
    print("\n[步骤 6/6] 导出结果...")

    # 导出完整交叉验证结果Excel
    output_excel = base_dir / "O2O连锁名称_交叉验证.xlsx"
    cv_engine.export_cross_validation_results(output_excel, df)

    # 导出人工审核队列
    review_queue_file = base_dir / "人工审核队列.xlsx"
    cv_engine.export_manual_review_queue(review_queue_file)

    # ==================== 完成 ====================
    print("\n" + "=" * 80)
    print("✓ 交叉验证完成！")
    print("=" * 80)
    print(f"\n生成的文件:")
    print(f"  1. {output_excel.name} - 完整交叉验证结果")
    print(f"  2. {report_file.name} - 验证报告（JSON）")
    print(f"  3. {cv_results_file.name} - 验证结果数据（JSON）")
    print(f"  4. {review_queue_file.name} - 人工审核队列")
    print(f"  5. {progress_file.name} - 进度文件（支持断点续传）")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ 程序被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
