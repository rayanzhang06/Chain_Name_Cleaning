"""
匹配验证器 - 三层防护机制

确保所有匹配的简称都来自数据库，严禁编造或跨省份使用。
"""

import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass

from ..database.manager import DatabaseManager


logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """
    验证结果
    """
    passed: bool
    abbreviation: Optional[str]
    province: str
    violations: List[str]
    warnings: List[str]

    def __post_init__(self):
        """初始化后处理"""
        if not self.violations:
            self.violations = []
        if not self.warnings:
            self.warnings = []

    def is_valid(self) -> bool:
        """是否通过验证"""
        return self.passed and len(self.violations) == 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'passed': self.passed,
            'abbreviation': self.abbreviation,
            'province': self.province,
            'violations': self.violations,
            'warnings': self.warnings,
            'is_valid': self.is_valid()
        }


class MatchValidator:
    """
    匹配验证器 - 三层防护核心

    三层防护机制：
    1. Prompt 层：在提示词中明确约束
    2. 代码层：验证 LLM 返回结果
    3. 质量层：最终输出前检查

    数据来源唯一性原则：
    - 所有简称必须来自数据库
    - 简称必须属于对应省份
    - 严禁编造或跨省份使用简称
    - 找不到匹配时必须留空
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        strict_mode: bool = True,
        allow_cross_province: bool = False,
        allow_fabricated: bool = False
    ):
        """
        初始化验证器

        Args:
            db_manager: 数据库管理器
            strict_mode: 严格模式（任何违规都拒绝）
            allow_cross_province: 是否允许跨省份简称（默认 False）
            allow_fabricated: 是否允许编造简称（默认 False）
        """
        self.db_manager = db_manager
        self.strict_mode = strict_mode
        self.allow_cross_province = allow_cross_province
        self.allow_fabricated = allow_fabricated

        # 缓存候选简称库
        self._candidate_cache: Dict[str, Set[str]] = {}
        self._validation_stats = {
            'total_validations': 0,
            'passed': 0,
            'violations': 0,
            'by_type': {}
        }

        logger.info("匹配验证器初始化完成 (三层防护)")

    def load_candidates(self, province: str, refresh: bool = False) -> Set[str]:
        """
        加载省份的候选简称库

        Args:
            province: 省份
            refresh: 是否强制刷新缓存

        Returns:
            候选简称集合
        """
        if not refresh and province in self._candidate_cache:
            return self._candidate_cache[province]

        # 从数据库加载
        abbreviations = self.db_manager.get_abbreviations_by_province(
            province=province,
            validated_only=True
        )

        candidate_set = {abbr.abbreviation for abbr in abbreviations}
        self._candidate_cache[province] = candidate_set

        return candidate_set

    def validate(
        self,
        abbreviation: Optional[str],
        province: str,
        candidates: Optional[Set[str]] = None,
        layer: str = "code"
    ) -> ValidationResult:
        """
        验证匹配结果

        Args:
            abbreviation: 匹配的简称
            province: 省份
            candidates: 候选简称集合（可选，默认从数据库加载）
            layer: 验证层 (prompt/code/quality)

        Returns:
            ValidationResult 对象
        """
        self._validation_stats['total_validations'] += 1

        # 允许为空
        if abbreviation is None or abbreviation == '':
            return ValidationResult(
                passed=True,
                abbreviation=None,
                province=province,
                violations=[],
                warnings=[]
            )

        violations = []
        warnings = []

        # 加载候选库
        if candidates is None:
            candidates = self.load_candidates(province)

        # === 第一层：检查是否在数据库中 ===
        if abbreviation not in candidates:
            violation = f"简称 '{abbreviation}' 不在省份 '{province}' 的候选库中"
            violations.append(violation)
            self._record_violation('not_in_database')
            logger.warning(f"验证失败: {violation}")

        # === 第二层：检查是否跨省份 ===
        if not self.allow_cross_province:
            # 检查是否在其他省份的候选库中
            found_in_other_province = False
            for other_province, other_candidates in self._candidate_cache.items():
                if other_province != province and abbreviation in other_candidates:
                    found_in_other_province = True
                    warning = f"简称 '{abbreviation}' 属于省份 '{other_province}'，而非 '{province}'"
                    warnings.append(warning)
                    logger.warning(f"跨省份警告: {warning}")
                    break

            # 如果在其他省份但不在当前省份，记录违规
            if found_in_other_province and len(violations) > 0:
                self._record_violation('cross_province')

        # === 第三层：检查是否编造 ===
        if not self.allow_fabricated:
            # 检查是否在任何省份的数据库中
            found_anywhere = False
            for prov_candidates in self._candidate_cache.values():
                if abbreviation in prov_candidates:
                    found_anywhere = True
                    break

            if not found_anywhere:
                violation = f"简称 '{abbreviation}' 不在任何省份的数据库中（疑似编造）"
                violations.append(violation)
                self._record_violation('fabricated')
                logger.warning(f"编造警告: {violation}")

        # 判断是否通过
        passed = len(violations) == 0 or (not self.strict_mode and len(warnings) == 0)

        if passed:
            self._validation_stats['passed'] += 1
        else:
            self._validation_stats['violations'] += 1

        return ValidationResult(
            passed=passed,
            abbreviation=abbreviation if passed else None,
            province=province,
            violations=violations,
            warnings=warnings
        )

    def batch_validate(
        self,
        items: List[Dict[str, Any]],
        layer: str = "quality"
    ) -> Tuple[List[ValidationResult], Dict[str, Any]]:
        """
        批量验证

        Args:
            items: 待验证项列表，每项包含 abbreviation 和 province
            layer: 验证层

        Returns:
            (验证结果列表, 统计信息) 元组
        """
        results = []

        for item in items:
            abbreviation = item.get('abbreviation')
            province = item.get('province')

            if not province:
                logger.warning(f"缺少省份信息: {item}")
                results.append(ValidationResult(
                    passed=False,
                    abbreviation=None,
                    province="",
                    violations=["缺少省份信息"],
                    warnings=[]
                ))
                continue

            result = self.validate(abbreviation, province, layer=layer)
            results.append(result)

        # 生成统计
        stats = self._generate_batch_stats(results)

        return results, stats

    def _record_violation(self, violation_type: str):
        """记录违规类型"""
        if violation_type not in self._validation_stats['by_type']:
            self._validation_stats['by_type'][violation_type] = 0
        self._validation_stats['by_type'][violation_type] += 1

    def _generate_batch_stats(self, results: List[ValidationResult]) -> Dict[str, Any]:
        """生成批量验证统计"""
        total = len(results)
        passed = sum(1 for r in results if r.is_valid())
        failed = total - passed

        violation_types = {}
        for result in results:
            for violation in result.violations:
                # 提取违规类型
                if '不在候选库中' in violation:
                    vtype = 'not_in_database'
                elif '跨省份' in violation:
                    vtype = 'cross_province'
                elif '编造' in violation:
                    vtype = 'fabricated'
                else:
                    vtype = 'other'

                if vtype not in violation_types:
                    violation_types[vtype] = 0
                violation_types[vtype] += 1

        return {
            'total': total,
            'passed': passed,
            'failed': failed,
            'pass_rate': round(passed / total * 100, 2) if total > 0 else 0,
            'violation_types': violation_types
        }

    def get_validation_stats(self) -> Dict[str, Any]:
        """
        获取验证统计信息

        Returns:
            统计信息字典
        """
        return self._validation_stats.copy()

    def reset_stats(self):
        """重置统计信息"""
        self._validation_stats = {
            'total_validations': 0,
            'passed': 0,
            'violations': 0,
            'by_type': {}
        }
        logger.info("验证统计已重置")

    def clear_cache(self):
        """清空缓存"""
        self._candidate_cache.clear()
        logger.info("验证器缓存已清空")

    # === 便捷方法 ===

    def is_valid_match(
        self,
        abbreviation: Optional[str],
        province: str
    ) -> bool:
        """
        快速验证匹配是否有效

        Args:
            abbreviation: 匹配的简称
            province: 省份

        Returns:
            是否有效
        """
        result = self.validate(abbreviation, province)
        return result.is_valid()

    def filter_valid_matches(
        self,
        items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        过滤出有效的匹配

        Args:
            items: 待过滤项列表

        Returns:
            有效项列表
        """
        valid_items = []

        for item in items:
            abbreviation = item.get('abbreviation')
            province = item.get('province')

            if not province:
                continue

            result = self.validate(abbreviation, province)
            if result.is_valid():
                valid_items.append(item)

        return valid_items


# 便捷函数
def quick_validate(
    abbreviation: Optional[str],
    province: str,
    db_manager: DatabaseManager
) -> ValidationResult:
    """
    快速验证（便捷函数）

    Args:
        abbreviation: 匹配的简称
        province: 省份
        db_manager: 数据库管理器

    Returns:
        ValidationResult 对象
    """
    validator = MatchValidator(db_manager)
    return validator.validate(abbreviation, province)
