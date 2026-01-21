"""
数据验证工具

提供数据验证功能，确保数据质量。
"""

import re
import logging
from typing import Any, List, Dict, Optional, Tuple


logger = logging.getLogger(__name__)


class DataValidator:
    """
    数据验证器

    提供各种数据验证方法。
    """

    @staticmethod
    def is_not_empty(value: Any) -> bool:
        """
        检查值是否非空

        Args:
            value: 待检查的值

        Returns:
            是否非空
        """
        if value is None:
            return False
        if isinstance(value, str) and not value.strip():
            return False
        if isinstance(value, (list, dict)) and len(value) == 0:
            return False
        return True

    @staticmethod
    def is_valid_province(province: str) -> bool:
        """
        验证省份名称是否有效

        Args:
            province: 省份名称

        Returns:
            是否有效
        """
        from .province_extractor import validate_province
        return validate_province(province)

    @staticmethod
    def is_valid_chain_name(name: str) -> bool:
        """
        验证连锁名称是否有效

        Args:
            name: 连锁名称

        Returns:
            是否有效
        """
        if not DataValidator.is_not_empty(name):
            return False

        # 长度检查
        if len(name) < 2 or len(name) > 200:
            return False

        # 排除明显无效的名称
        invalid_patterns = [
            r'^测试.*',
            r'^test.*',
            r'^待定.*',
            r'^无$',
            r'^空白$',
            r'^-+$',
        ]

        name_lower = name.lower()
        for pattern in invalid_patterns:
            if re.match(pattern, name_lower):
                return False

        return True

    @staticmethod
    def is_valid_abbreviation(abbr: str) -> bool:
        """
        验证简称是否有效

        Args:
            abbr: 简称

        Returns:
            是否有效
        """
        if not DataValidator.is_not_empty(abbr):
            return False

        # 长度检查
        if len(abbr) < 2 or len(abbr) > 50:
            return False

        # 排除明显无效的简称
        invalid_patterns = [
            r'^测试.*',
            r'^test.*',
            r'^待定.*',
            r'^无$',
            r'^-+$',
        ]

        abbr_lower = abbr.lower()
        for pattern in invalid_patterns:
            if re.match(pattern, abbr_lower):
                return False

        return True

    @staticmethod
    def validate_full_name(full_name: str) -> Tuple[bool, Optional[str]]:
        """
        验证全称并返回错误信息

        Args:
            full_name: 连锁药店全称

        Returns:
            (是否有效, 错误信息) 元组
        """
        if not DataValidator.is_not_empty(full_name):
            return False, "全称不能为空"

        if len(full_name) < 2:
            return False, "全称长度过短"

        if len(full_name) > 200:
            return False, "全称长度过长"

        if not DataValidator.is_valid_chain_name(full_name):
            return False, "全称格式无效"

        return True, None

    @staticmethod
    def validate_abbreviation(abbr: str) -> Tuple[bool, Optional[str]]:
        """
        验证简称并返回错误信息

        Args:
            abbr: 简称

        Returns:
            (是否有效, 错误信息) 元组
        """
        if not DataValidator.is_not_empty(abbr):
            return False, "简称不能为空"

        if len(abbr) < 2:
            return False, "简称长度过短"

        if len(abbr) > 50:
            return False, "简称长度过长"

        if not DataValidator.is_valid_abbreviation(abbr):
            return False, "简称格式无效"

        return True, None


def validate_dataframe_row(
    row: Dict[str, Any],
    required_fields: List[str]
) -> Tuple[bool, List[str]]:
    """
    验证 DataFrame 行数据

    Args:
        row: 行数据字典
        required_fields: 必填字段列表

    Returns:
        (是否有效, 错误信息列表) 元组
    """
    errors = []

    for field in required_fields:
        value = row.get(field)

        if not DataValidator.is_not_empty(value):
            errors.append(f"缺少必填字段: {field}")

    return len(errors) == 0, errors


def validate_match_result(
    abbreviation: Optional[str],
    province: str,
    candidate_set: set,
    allow_empty: bool = True
) -> Tuple[bool, Optional[str]]:
    """
    验证匹配结果（三层防护核心）

    Args:
        abbreviation: 匹配的简称
        province: 省份
        candidate_set: 该省份的候选简称集合
        allow_empty: 是否允许为空

    Returns:
        (是否有效, 错误信息) 元组
    """
    # 允许为空
    if abbreviation is None or abbreviation == '':
        if allow_empty:
            return True, None
        else:
            return False, "匹配结果不能为空"

    # 检查是否在候选库中
    if abbreviation not in candidate_set:
        return False, f"简称 '{abbreviation}' 不在省份 '{province}' 的候选库中"

    return True, None
