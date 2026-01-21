"""
简称匹配器 - 阶段二核心模块

使用 LLM 将连锁药店全称匹配到正确的简称。
"""

import logging
from typing import List, Dict, Any, Optional, Set

from ..llm.client import LLMClient
from ..database.manager import DatabaseManager
from ..utils.validators import DataValidator


logger = logging.getLogger(__name__)


class AbbreviationMatcher:
    """
    简称匹配器 - 核心匹配逻辑

    功能：
    - 加载候选简称库
    - 使用 LLM 进行匹配
    - 应用三层防护验证
    - 支持历史反馈学习
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        llm_client: LLMClient,
        enable_history: bool = True,
        history_days: int = 30,
        min_confirmation_count: int = 3
    ):
        """
        初始化匹配器

        Args:
            db_manager: 数据库管理器
            llm_client: LLM 客户端
            enable_history: 是否启用历史反馈学习
            history_days: 历史反馈天数
            min_confirmation_count: 最小确认次数
        """
        self.db_manager = db_manager
        self.llm_client = llm_client
        self.enable_history = enable_history
        self.history_days = history_days
        self.min_confirmation_count = min_confirmation_count

        # 缓存候选简称库
        self._candidate_cache: Dict[str, Set[str]] = {}
        self._history_mappings_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}

        logger.info("简称匹配器初始化完成")

    def load_candidates_by_province(self, province: str, refresh: bool = False) -> Set[str]:
        """
        加载省份的候选简称库

        Args:
            province: 省份
            refresh: 是否强制刷新缓存

        Returns:
            候选简称集合
        """
        # 检查缓存
        if not refresh and province in self._candidate_cache:
            return self._candidate_cache[province]

        # 从数据库加载（在会话内提取数据）
        with self.db_manager.get_session() as session:
            from src.database.models import ChainAbbreviation
            abbreviations = session.query(ChainAbbreviation).filter_by(
                province=province,
                is_validated=True
            ).all()

            # 在会话内提取简称（避免 DetachedInstanceError）
            candidate_set = {abbr.abbreviation for abbr in abbreviations}

        # 缓存
        self._candidate_cache[province] = candidate_set

        logger.info(f"加载候选简称库: {province}, 数量: {len(candidate_set)}")
        return candidate_set

    def load_history_mappings(self, province: str, refresh: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        加载历史确认映射

        Args:
            province: 省份
            refresh: 是否强制刷新缓存

        Returns:
            确认映射字典
        """
        if not self.enable_history:
            return {}

        # 检查缓存
        if not refresh and province in self._history_mappings_cache:
            return self._history_mappings_cache[province]

        # 从数据库加载
        mappings = self.db_manager.get_confirmed_mappings(
            province=province,
            min_count=self.min_confirmation_count,
            days=self.history_days
        )

        # 缓存
        self._history_mappings_cache[province] = mappings

        logger.info(f"加载历史映射: {province}, 数量: {len(mappings)}")
        return mappings

    def match(
        self,
        full_name: str,
        province: str,
        candidates: Optional[Set[str]] = None,
        use_history: bool = True
    ) -> Dict[str, Any]:
        """
        匹配简称

        Args:
            full_name: 连锁药店全称
            province: 省份
            candidates: 候选简称集合（可选，默认从数据库加载）
            use_history: 是否使用历史映射

        Returns:
            匹配结果字典
        """
        # 验证输入
        is_valid, error = DataValidator.validate_full_name(full_name)
        if not is_valid:
            return {
                'success': False,
                'full_name': full_name,
                'abbreviation': None,
                'error': error
            }

        # 加载候选简称库
        if candidates is None:
            candidates = self.load_candidates_by_province(province)

        if not candidates:
            logger.warning(f"省份 [{province}] 没有候选简称")
            return {
                'success': False,
                'full_name': full_name,
                'province': province,
                'abbreviation': None,
                'error': '该省份没有候选简称'
            }

        # 检查历史映射
        if use_history and self.enable_history:
            history_mappings = self.load_history_mappings(province)
            if full_name in history_mappings:
                mapping = history_mappings[full_name]
                logger.info(f"使用历史映射: {full_name} -> {mapping['abbreviation']}")
                return {
                    'success': True,
                    'full_name': full_name,
                    'province': province,
                    'abbreviation': mapping['abbreviation'],
                    'confidence': mapping.get('confidence', 'High'),
                    'match_method': 'history',
                    'reasoning': '使用历史确认映射'
                }

        # 调用 LLM 匹配
        candidate_list = sorted(list(candidates))  # 转为排序的列表

        history_examples = None
        if use_history and self.enable_history:
            history_mappings = self.load_history_mappings(province)
            history_examples = self._prepare_history_examples(history_mappings)

        result = self.llm_client.match_abbreviation(
            full_name=full_name,
            province=province,
            candidate_abbreviations=candidate_list,
            history_examples=history_examples
        )

        if result['success']:
            # 三层防护验证：代码层
            abbreviation = result.get('abbreviation')
            if abbreviation:
                is_valid, error = self._validate_match(
                    abbreviation=abbreviation,
                    province=province,
                    candidates=candidates
                )
                if not is_valid:
                    logger.warning(f"匹配未通过验证: {full_name} -> {abbreviation}, 原因: {error}")
                    return {
                        'success': False,
                        'full_name': full_name,
                        'province': province,
                        'abbreviation': None,
                        'error': f"三层防护验证失败: {error}",
                        'llm_result': result
                    }

            result['province'] = province
            result['match_method'] = 'llm'

        return result

    def batch_match(
        self,
        items: List[Dict[str, Any]],
        use_history: bool = True
    ) -> List[Dict[str, Any]]:
        """
        批量匹配

        Args:
            items: 待匹配项列表，每项包含 full_name 和 province
            use_history: 是否使用历史映射

        Returns:
            匹配结果列表
        """
        results = []

        # 按省份分组
        province_groups: Dict[str, List[Dict[str, Any]]] = {}
        for item in items:
            province = item.get('province')
            if province:
                if province not in province_groups:
                    province_groups[province] = []
                province_groups[province].append(item)

        # 为每个省份加载候选库
        province_candidates: Dict[str, Set[str]] = {}
        for province in province_groups.keys():
            province_candidates[province] = self.load_candidates_by_province(province)

        # 匹配
        for item in items:
            full_name = item.get('full_name')
            province = item.get('province')

            if not full_name or not province:
                logger.warning(f"缺少必填字段: {item}")
                results.append({
                    'success': False,
                    'full_name': full_name,
                    'abbreviation': None,
                    'error': '缺少必填字段'
                })
                continue

            result = self.match(
                full_name=full_name,
                province=province,
                candidates=province_candidates.get(province),
                use_history=use_history
            )

            results.append(result)

        logger.info(f"批量匹配完成: {len(results)} 条")
        return results

    def _validate_match(
        self,
        abbreviation: str,
        province: str,
        candidates: Set[str]
    ) -> tuple[bool, Optional[str]]:
        """
        验证匹配结果（三层防护 - 代码层）

        Args:
            abbreviation: 匹配的简称
            province: 省份
            candidates: 候选简称集合

        Returns:
            (是否有效, 错误信息) 元组
        """
        # 检查是否在候选库中
        if abbreviation not in candidates:
            return False, f"简称 '{abbreviation}' 不在省份 '{province}' 的候选库中"

        return True, None

    def _prepare_history_examples(
        self,
        history_mappings: Dict[str, Dict[str, Any]],
        max_count: int = 5
    ) -> Optional[List[Dict[str, str]]]:
        """
        准备历史案例

        Args:
            history_mappings: 历史映射字典
            max_count: 最大案例数

        Returns:
            历史案例列表或 None
        """
        if not history_mappings:
            return None

        examples = []
        for full_name, mapping in history_mappings.items():
            if mapping.get('confirmation_count', 0) >= self.min_confirmation_count:
                examples.append({
                    'full_name': full_name,
                    'abbreviation': mapping['abbreviation'],
                    'count': mapping['confirmation_count']
                })

            if len(examples) >= max_count:
                break

        return examples if examples else None

    def clear_cache(self):
        """清空缓存"""
        self._candidate_cache.clear()
        self._history_mappings_cache.clear()
        logger.info("缓存已清空")
