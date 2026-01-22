#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交叉验证引擎
协调两个评估器进行交叉验证
"""

import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


class CrossValidationEngine:
    """交叉验证引擎"""

    def __init__(self, evaluator1, evaluator2, config=None):
        """
        初始化交叉验证引擎

        Args:
            evaluator1: 第一评估器（ChainNameEvaluator）
            evaluator2: 第二评估器（PatternBasedEvaluator）
            config: 配置字典（可选）
        """
        self.evaluator1 = evaluator1
        self.evaluator2 = evaluator2
        self.config = config or self._default_config()
        self.results = []

    def _default_config(self) -> Dict[str, Any]:
        """默认配置参数"""
        return {
            'thresholds': {
                'consistent': 0.05,
                'acceptable': 0.15,
                'discrepant': 0.25,
            },
            'manual_review_threshold': 0.15,  # 超过此差异需要人工审核
        }

    def _get_validation_status(self, diff: float) -> str:
        """根据差异返回验证状态"""
        if diff <= self.config['thresholds']['consistent']:
            return 'CONSISTENT'
        elif diff <= self.config['thresholds']['acceptable']:
            return 'ACCEPTABLE'
        elif diff <= self.config['thresholds']['discrepant']:
            return 'DISCREPANT'
        else:
            return 'CONFLICTING'

    def calculate_final_confidence(self, conf1: float, conf2: float,
                                   diff: float, status: str) -> float:
        """
        根据验证状态计算最终置信度

        Args:
            conf1: 第一次评估置信度
            conf2: 第二次评估置信度
            diff: 差异
            status: 验证状态

        Returns:
            最终置信度
        """
        if status == 'CONSISTENT':
            # 高度一致：简单平均
            final = (conf1 + conf2) / 2
        elif status == 'ACCEPTABLE':
            # 可接受差异：加权平均（倾向第二套，更严格）
            final = conf1 * 0.45 + conf2 * 0.55
        elif status == 'DISCREPANT':
            # 明显差异：保守策略，取较低值并降权
            final = min(conf1, conf2) * 0.90
        else:  # CONFLICTING
            # 严重冲突：极保守策略
            final = min(conf1, conf2) * 0.75

        return round(final, 2)

    def evaluate_with_validation(self, name: str) -> Dict[str, Any]:
        """
        对单个名称执行交叉验证

        Args:
            name: 连锁名称

        Returns:
            包含评估结果的字典
        """
        # 两次评估
        conf1 = self.evaluator1.evaluate_name(name)
        conf2 = self.evaluator2.evaluate_name(name)

        # 计算差异
        diff = abs(conf1 - conf2)

        # 确定验证状态
        status = self._get_validation_status(diff)

        # 计算最终置信度
        final_conf = self.calculate_final_confidence(
            conf1, conf2, diff, status
        )

        return {
            'name': name,
            'confidence_1': conf1,
            'confidence_2': conf2,
            'difference': round(diff, 3),
            'validation_status': status,
            'final_confidence': final_conf,
            'needs_review': diff >= self.config['manual_review_threshold']
        }

    def batch_cross_validate(self, names: List[str],
                            progress_file: Optional[Path] = None) -> List[Dict[str, Any]]:
        """
        批量交叉验证

        Args:
            names: 连锁名称列表
            progress_file: 进度文件路径（可选）

        Returns:
            评估结果列表
        """
        results = []

        # 加载已有进度
        if progress_file and progress_file.exists():
            with open(progress_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
            print(f"已加载 {len(results)} 条历史验证结果")

        # 评估新名称
        new_count = 0
        for name in names:
            if not name or name == '\\N':
                continue

            # 检查是否已评估
            if any(r['name'] == name for r in results):
                continue

            # 执行交叉验证
            result = self.evaluate_with_validation(name)
            results.append(result)
            new_count += 1

        print(f"新验证 {new_count} 条")
        print(f"总计 {len(results)} 条验证结果")

        self.results = results
        return results

    def generate_validation_report(self) -> Dict[str, Any]:
        """生成验证报告"""
        if not self.results:
            return {}

        total = len(self.results)

        # 统计各验证状态数量
        status_counts = {}
        for result in self.results:
            status = result['validation_status']
            status_counts[status] = status_counts.get(status, 0) + 1

        # 计算统计指标
        avg_diff = sum(r['difference'] for r in self.results) / total
        max_diff = max(r['difference'] for r in self.results)
        min_diff = min(r['difference'] for r in self.results)

        # 需要人工审核的数量
        needs_review = sum(1 for r in self.results if r['needs_review'])

        # 置信度分布
        high_conf = sum(1 for r in self.results if r['final_confidence'] >= 0.90)
        medium_conf = sum(1 for r in self.results if 0.70 <= r['final_confidence'] < 0.90)
        low_conf = sum(1 for r in self.results if r['final_confidence'] < 0.70)

        # 置信度变化统计
        upgraded = sum(1 for r in self.results if r['final_confidence'] > r['confidence_1'])
        downgraded = sum(1 for r in self.results if r['final_confidence'] < r['confidence_1'])
        unchanged = sum(1 for r in self.results if r['final_confidence'] == r['confidence_1'])

        return {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_evaluated': total,
            'validation_status_distribution': status_counts,
            'average_difference': round(avg_diff, 3),
            'max_difference': round(max_diff, 3),
            'min_difference': round(min_diff, 3),
            'needs_manual_review': needs_review,
            'review_percentage': round(needs_review / total * 100, 1),
            'confidence_distribution': {
                'high_confidence': high_conf,
                'medium_confidence': medium_conf,
                'low_confidence': low_conf
            },
            'confidence_changes': {
                'upgraded': upgraded,
                'downgraded': downgraded,
                'unchanged': unchanged
            },
            'high_discrepancy_cases': self._get_high_discrepancy_cases(threshold=0.20)
        }

    def _get_high_discrepancy_cases(self, threshold: float = 0.20,
                                   limit: int = 20) -> List[Dict[str, Any]]:
        """获取高差异案例"""
        high_diff = [r for r in self.results if r['difference'] >= threshold]
        # 按差异降序排序
        high_diff.sort(key=lambda x: x['difference'], reverse=True)
        return high_diff[:limit]

    def save_results(self, output_file: Path):
        """保存验证结果到JSON"""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        print(f"\n✓ 已保存验证结果到: {output_file}")

    def save_report(self, report_file: Path):
        """保存验证报告到JSON"""
        report = self.generate_validation_report()
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"✓ 已保存验证报告到: {report_file}")

    def export_cross_validation_results(self, excel_path: Path,
                                       original_df: pd.DataFrame):
        """
        导出交叉验证结果到Excel

        Args:
            excel_path: 输出Excel路径
            original_df: 原始数据DataFrame
        """
        # 创建结果DataFrame
        result_df = pd.DataFrame(self.results)

        # 添加状态说明
        status_descriptions = {
            'CONSISTENT': '高度一致',
            'ACCEPTABLE': '可接受差异',
            'DISCREPANT': '明显差异-需审核',
            'CONFLICTING': '严重冲突-必须复核'
        }
        result_df['状态说明'] = result_df['validation_status'].map(status_descriptions)
        result_df['需要审核'] = result_df['needs_review'].map({True: '是', False: '否'})

        # 重命名列（中文）
        result_df.rename(columns={
            'name': '连锁名称',
            'confidence_1': '置信度_原始评估',
            'confidence_2': '置信度_模式评估',
            'difference': '评估差异',
            'validation_status': '验证状态',
            'final_confidence': '最终置信度',
            'needs_review': 'needs_review_flag'
        }, inplace=True)

        # 合并原始数据
        merged_df = original_df.merge(
            result_df,
            on='连锁名称',
            how='left'
        )

        # 保存到Excel
        merged_df.to_excel(excel_path, index=False, engine='openpyxl')
        print(f"✓ 已导出Excel结果到: {excel_path}")

    def export_manual_review_queue(self, excel_path: Path):
        """导出需要人工审核的队列"""
        review_cases = [r for r in self.results if r['needs_review']]

        if not review_cases:
            print("⚠ 没有需要人工审核的记录")
            return

        # 创建DataFrame
        review_df = pd.DataFrame(review_cases)

        # 添加状态说明
        status_descriptions = {
            'CONSISTENT': '高度一致',
            'ACCEPTABLE': '可接受差异',
            'DISCREPANT': '明显差异-需审核',
            'CONFLICTING': '严重冲突-必须复核'
        }
        review_df['状态说明'] = review_df['validation_status'].map(status_descriptions)

        # 按差异降序排序
        review_df = review_df.sort_values('difference', ascending=False)

        # 重命名列
        review_df.rename(columns={
            'name': '连锁名称',
            'confidence_1': '置信度_原始评估',
            'confidence_2': '置信度_模式评估',
            'difference': '评估差异',
            'validation_status': '验证状态',
            'final_confidence': '最终置信度',
        }, inplace=True)

        # 保存
        review_df.to_excel(excel_path, index=False, engine='openpyxl')
        print(f"✓ 已导出人工审核队列到: {excel_path}（共{len(review_cases)}条）")

    def print_summary(self):
        """打印验证摘要"""
        if not self.results:
            print("没有验证结果")
            return

        report = self.generate_validation_report()

        print("\n" + "=" * 70)
        print("交叉验证摘要")
        print("=" * 70)

        print(f"\n验证统计:")
        print(f"  总评估数量: {report['total_evaluated']}")
        print(f"  平均差异: {report['average_difference']}")
        print(f"  最大差异: {report['max_difference']}")
        print(f"  最小差异: {report['min_difference']}")

        print(f"\n验证状态分布:")
        status_names = {
            'CONSISTENT': '高度一致',
            'ACCEPTABLE': '可接受差异',
            'DISCREPANT': '明显差异',
            'CONFLICTING': '严重冲突'
        }
        for status, count in report['validation_status_distribution'].items():
            percentage = count / report['total_evaluated'] * 100
            print(f"  {status_names[status]}: {count} ({percentage:.1f}%)")

        print(f"\n人工审核需求:")
        print(f"  需要审核: {report['needs_manual_review']} 条 ({report['review_percentage']}%)")

        print(f"\n置信度分布:")
        total = report['total_evaluated']
        print(f"  高置信度(≥0.90): {report['confidence_distribution']['high_confidence']} "
              f"({report['confidence_distribution']['high_confidence']/total*100:.1f}%)")
        print(f"  中置信度(0.70-0.89): {report['confidence_distribution']['medium_confidence']} "
              f"({report['confidence_distribution']['medium_confidence']/total*100:.1f}%)")
        print(f"  低置信度(<0.70): {report['confidence_distribution']['low_confidence']} "
              f"({report['confidence_distribution']['low_confidence']/total*100:.1f}%)")

        print(f"\n置信度变化:")
        print(f"  提升: {report['confidence_changes']['upgraded']} 条")
        print(f"  降低: {report['confidence_changes']['downgraded']} 条")
        print(f"  不变: {report['confidence_changes']['unchanged']} 条")

        if report['high_discrepancy_cases']:
            print(f"\n高差异案例（前10个）:")
            for i, case in enumerate(report['high_discrepancy_cases'][:10], 1):
                print(f"  {i}. {case['name']:<30} "
                      f"差异: {case['difference']:.3f} "
                      f"({case['confidence_1']:.2f} vs {case['confidence_2']:.2f})")

        print("=" * 70)
