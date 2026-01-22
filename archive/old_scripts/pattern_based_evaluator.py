#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于模式匹配的连锁名称置信度评估器
使用完全不同的评估维度进行交叉验证
"""

import re
from typing import Dict, Tuple, List


class PatternBasedEvaluator:
    """基于模式匹配的第二评估器"""

    def __init__(self):
        # 知名连锁品牌数据库（与第一评估器保持一致）
        self.famous_chains = {
            # 全国性大型连锁药店（上市企业）
            '一心堂': 0.97,
            '益丰': 0.97,
            '老百姓大药房': 0.97,
            '大参林': 0.97,
            '海王星辰': 0.96,
            '国大药房': 0.96,
            '同仁堂': 0.96,
            '漱玉平民': 0.95,

            # 大型医药电商
            '京东': 0.96,
            '阿里健康': 0.96,
            '叮当快药': 0.96,
            '好药师': 0.96,

            # 知名区域连锁
            '华氏': 0.93,
            '雷允上': 0.93,
            '余天成': 0.93,
            '养和堂': 0.91,
            '童涵春堂': 0.91,

            # 常见连锁标识
            '第一医药': 0.94,
        }

        # 企业名称模式（正则表达式 + 得分范围）
        self.enterprise_patterns = {
            'full_corp_name': (
                r'^.+?(股份有限公司|集团有限公司|连锁有限公司)',
                0.93, 0.96
            ),
            'regional_chain': (
                r'^(北京|上海|广东|江苏|浙江|四川|云南|山东).+?连锁',
                0.88, 0.92
            ),
            'chain_with_location': (
                r'.+?(市|省|区).+?(连锁|大药房)',
                0.85, 0.90
            ),
            'brand_with_suffix': (
                r'^[\u4e00-\u9fa5]{2,4}(大药房|医药|药业|堂)$',
                0.72, 0.85
            ),
        }

        # 品牌词汇库
        self.brand_lexicon = {
            'high_freq_brand_chars': [
                '堂', '源', '康', '益', '仁', '济', '和', '春',
                '华', '德', '泰', '丰', '瑞', '恒', '安', '宁',
                '济', '民', '众', '鑫', '天', '同', '普', '德'
            ],
            'chain_keywords': ['大药房', '连锁', '医药', '药业', '药房'],
            'regional_markers': ['京', '沪', '粤', '川', '云', '湘', '鲁', '苏', '浙'],
        }

        # 排除模式
        self.exclude_patterns = [
            r'散店', r'代运营', r'活动组', r'测试',
            r'111', r'运营', r'未对接', r'互医'
        ]

    def evaluate_name(self, name: str) -> float:
        """
        评估单个名称的置信度

        Args:
            name: 连锁名称

        Returns:
            置信度 (0-1之间的浮点数)
        """
        if not name or name == '\\N':
            return 0.0

        # 检查是否为知名品牌（优先级最高）
        for brand, confidence in self.famous_chains.items():
            if brand in name:
                # 知名品牌给予高置信度，但略低于第一评估器（保持一定的独立性）
                return round(confidence - 0.01, 2)

        # 检查排除模式
        if self._check_excluded(name):
            return 0.20

        # 1. 模式匹配得分 (40%)
        pattern_score = self._match_enterprise_patterns(name)

        # 2. 字符特征得分 (30%)
        char_score = self._analyze_character_features(name)

        # 3. 品牌词汇得分 (20%)
        brand_score = self._analyze_brand_lexicon(name)

        # 4. 结构完整性得分 (10%)
        structure_score = self._check_structure_completeness(name)

        # 综合加权
        final_score = (
            pattern_score * 0.40 +
            char_score * 0.30 +
            brand_score * 0.20 +
            structure_score * 0.10
        )

        return round(min(final_score, 0.98), 2)

    def _check_excluded(self, name: str) -> bool:
        """检查是否在排除列表中"""
        for pattern in self.exclude_patterns:
            if re.search(pattern, name):
                return True
        return False

    def _match_enterprise_patterns(self, name: str) -> float:
        """匹配企业名称模式"""
        best_score = 0.40  # 默认基础分

        for pattern_key, (pattern, min_score, max_score) in self.enterprise_patterns.items():
            if re.search(pattern, name):
                # 根据匹配质量给出得分
                match_score = self._calculate_match_quality(name, pattern_key)
                best_score = max(best_score, match_score)

        return best_score

    def _calculate_match_quality(self, name: str, pattern_key: str) -> float:
        """计算匹配质量"""
        if pattern_key == 'full_corp_name':
            # 完整公司名，根据类型调整
            if '股份有限公司' in name:
                return 0.96
            elif '集团有限公司' in name:
                return 0.95
            elif '连锁有限公司' in name:
                return 0.94
            else:
                return 0.93

        elif pattern_key == 'regional_chain':
            # 区域性连锁
            return 0.90

        elif pattern_key == 'chain_with_location':
            # 含地名的连锁
            return 0.87

        elif pattern_key == 'brand_with_suffix':
            # 品牌+后缀，根据品牌长度调整
            brand_match = re.match(r'^[\u4e00-\u9fa5]{2,4}', name)
            if brand_match:
                brand_len = len(brand_match.group())
                # 2-3个字的品牌更可信
                if brand_len <= 3:
                    return 0.82
                else:
                    return 0.78
            return 0.72

        return 0.40

    def _analyze_character_features(self, name: str) -> float:
        """分析字符特征"""
        score = 0.0

        # 特征1: 包含括号（更规范）
        if re.search(r'[()（）]', name):
            score += 0.08

        # 特征2: 名称长度适中（6-18字最佳）
        length = len(name)
        if 6 <= length <= 18:
            score += 0.15
        elif 19 <= length <= 25:
            score += 0.10
        elif 4 <= length <= 5:
            score += 0.08

        # 特征3: 中文字符比例高
        chinese_chars = len(re.findall(r'[\u4e00-\u9fa5]', name))
        chinese_ratio = chinese_chars / length if length > 0 else 0
        if chinese_ratio >= 0.8:
            score += 0.15
        elif chinese_ratio >= 0.6:
            score += 0.10

        # 特征4: 包含企业后缀标识
        if re.search(r'(有限公司|股份|集团|公司)$', name):
            score += 0.20

        # 特征5: 包含地名
        if re.search(r'(北京|上海|广东|江苏|浙江|四川|云南|山东)', name):
            score += 0.12

        return min(score, 1.0)

    def _analyze_brand_lexicon(self, name: str) -> float:
        """分析品牌词汇"""
        score = 0.0

        # 检查高频品牌字
        brand_char_count = sum(
            1 for char in self.brand_lexicon['high_freq_brand_chars']
            if char in name
        )
        score += min(brand_char_count * 0.08, 0.25)

        # 检查连锁关键词
        chain_kw_count = sum(
            1 for kw in self.brand_lexicon['chain_keywords']
            if kw in name
        )
        score += min(chain_kw_count * 0.20, 0.50)

        # 检查地域标记
        regional_count = sum(
            1 for marker in self.brand_lexicon['regional_markers']
            if marker in name
        )
        score += min(regional_count * 0.05, 0.15)

        return min(score, 1.0)

    def _check_structure_completeness(self, name: str) -> float:
        """检查结构完整性"""
        score = 0.0

        # 检查是否有明确的品牌名（2-4个字开头）
        brand_match = re.match(r'^[\u4e00-\u9fa5]{2,4}', name)
        if brand_match:
            score += 0.40

        # 检查是否有业务类型标识
        business_type_patterns = [
            '大药房', '医药', '药业', '连锁', '药房', '药店'
        ]
        if any(pt in name for pt in business_type_patterns):
            score += 0.35

        # 检查是否有组织形式标识
        org_forms = ['有限公司', '股份', '集团', '连锁']
        if any(of in name for of in org_forms):
            score += 0.25

        return min(score, 1.0)


# 测试代码
if __name__ == "__main__":
    evaluator = PatternBasedEvaluator()

    # 测试样本
    test_cases = [
        "一心堂",
        "上海医药嘉定大药房连锁有限公司",
        "老百姓大药房",
        "益丰",
        "国大药房",
        "散店-互医",
        "云湖医药",
        "余天成大药房",
    ]

    print("PatternBasedEvaluator 测试")
    print("=" * 60)
    for name in test_cases:
        confidence = evaluator.evaluate_name(name)
        print(f"{name:<40} {confidence:.2f}")
