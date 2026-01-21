"""
省份提取工具

从文件名、路径或文本中提取省份信息。
"""

import re
import logging
from pathlib import Path
from typing import Optional, List


# 中国省份列表（包括自治区、直辖市、特别行政区）
PROVINCES = [
    '北京', '天津', '上海', '重庆',
    '河北', '山西', '辽宁', '吉林', '黑龙江',
    '江苏', '浙江', '安徽', '福建', '江西', '山东',
    '河南', '湖北', '湖南', '广东', '海南',
    '四川', '贵州', '云南', '陕西', '甘肃', '青海', '台湾',
    '内蒙古', '广西', '西藏', '宁夏', '新疆',
    '香港', '澳门'
]

# 省份别名映射
PROVINCE_ALIASES = {
    '内蒙古': '内蒙古',
    '内蒙古自治区': '内蒙古',
    '广西': '广西',
    '广西壮族自治区': '广西',
    '西藏': '西藏',
    '西藏自治区': '西藏',
    '宁夏': '宁夏',
    '宁夏回族自治区': '宁夏',
    '新疆': '新疆',
    '新疆维吾尔自治区': '新疆',
    '黑龙江': '黑龙江',
    '辽宁': '辽宁',
    '吉林': '吉林',
    '河北': '河北',
    '山西': '山西',
    '陕西': '陕西',
    '甘肃': '甘肃',
    '青海': '青海',
    '山东': '山东',
    '河南': '河南',
    '江苏': '江苏',
    '浙江': '浙江',
    '安徽': '安徽',
    '福建': '福建',
    '江西': '江西',
    '湖南': '湖南',
    '湖北': '湖北',
    '广东': '广东',
    '海南': '海南',
    '四川': '四川',
    '贵州': '贵州',
    '云南': '云南',
    '北京': '北京',
    '北京市': '北京',
    '天津': '天津',
    '天津市': '天津',
    '上海': '上海',
    '上海市': '上海',
    '重庆': '重庆',
    '重庆市': '重庆',
    '台湾': '台湾',
    '台湾省': '台湾',
    '香港': '香港',
    '香港特别行政区': '香港',
    '澳门': '澳门',
    '澳门特别行政区': '澳门',
}

logger = logging.getLogger(__name__)


def extract_province_from_filename(file_path: str) -> Optional[str]:
    """
    从文件名中提取省份

    Args:
        file_path: 文件路径

    Returns:
        省份名称或 None
    """
    filename = Path(file_path).name

    # 尝试匹配模式：KA专员客户关系数据模板【省份】.xlsx
    pattern = r'【(.*?)】'
    match = re.search(pattern, filename)
    if match:
        province = match.group(1)
        # 标准化省份名
        return normalize_province_name(province)

    # 尝试直接匹配省份名
    for province in PROVINCES:
        if province in filename:
            return province

    # 尝试匹配别名
    for alias, standard in PROVINCE_ALIASES.items():
        if alias in filename:
            return standard

    logger.warning(f"无法从文件名提取省份: {filename}")
    return None


def extract_province_from_text(text: str) -> Optional[str]:
    """
    从文本中提取省份

    Args:
        text: 文本内容

    Returns:
        省份名称或 None
    """
    if not text:
        return None

    # 尝试直接匹配省份名
    for province in PROVINCES:
        if province in text:
            return province

    # 尝试匹配别名
    for alias, standard in PROVINCE_ALIASES.items():
        if alias in text:
            return standard

    return None


def normalize_province_name(province: str) -> Optional[str]:
    """
    标准化省份名称

    Args:
        province: 省份名称

    Returns:
        标准化的省份名称或 None
    """
    if not province:
        return None

    # 去除空格
    province = province.strip()

    # 查找别名映射
    if province in PROVINCE_ALIASES:
        return PROVINCE_ALIASES[province]

    # 检查是否在标准列表中
    if province in PROVINCES:
        return province

    logger.warning(f"未知的省份名称: {province}")
    return None


def validate_province(province: str) -> bool:
    """
    验证省份名称是否有效

    Args:
        province: 省份名称

    Returns:
        是否有效
    """
    normalized = normalize_province_name(province)
    return normalized is not None


def get_all_provinces() -> List[str]:
    """
    获取所有省份列表

    Returns:
        省份列表
    """
    return PROVINCES.copy()


def find_province_in_text(text: str) -> List[str]:
    """
    在文本中查找所有可能的省份

    Args:
        text: 文本内容

    Returns:
        找到的省份列表
    """
    found = []

    for province in PROVINCES:
        if province in text:
            found.append(province)

    for alias, standard in PROVINCE_ALIASES.items():
        if alias in text and standard not in found:
            found.append(standard)

    return found
