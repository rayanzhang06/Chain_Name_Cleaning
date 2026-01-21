"""
反馈管理器 - 反馈学习系统

记录用户反馈并持续优化匹配效果。
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum

from ..database.manager import DatabaseManager


logger = logging.getLogger(__name__)


class UserChoice(Enum):
    """用户选择枚举"""
    ACCEPT = "accept"  # 接受推荐
    REJECT = "reject"  # 拒绝推荐
    MODIFY = "modify"  # 修改为其他简称
    EMPTY = "empty"    # 留空


class FeedbackManager:
    """
    反馈管理器

    功能：
    - 保存用户反馈
    - 加载历史反馈
    - 构建确认映射表
    - 分析反馈模式
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        retention_days: int = 90,
        min_confirmation_count: int = 3
    ):
        """
        初始化反馈管理器

        Args:
            db_manager: 数据库管理器
            retention_days: 反馈保留天数
            min_confirmation_count: 最小确认次数
        """
        self.db_manager = db_manager
        self.retention_days = retention_days
        self.min_confirmation_count = min_confirmation_count

        # 缓存
        self._confirmed_mappings_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._recent_feedback_cache: List[Any] = []

        logger.info("反馈管理器初始化完成")

    def save_feedback(
        self,
        province: str,
        full_name: str,
        recommended_abbreviation: Optional[str],
        user_choice: UserChoice,
        final_abbreviation: Optional[str],
        confidence_level: Optional[str] = None,
        candidate_count: int = 0,
        batch_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> bool:
        """
        保存用户反馈

        Args:
            province: 省份
            full_name: 连锁药店全称
            recommended_abbreviation: 推荐的简称
            user_choice: 用户选择
            final_abbreviation: 最终选择的简称
            confidence_level: 推荐时的置信度
            candidate_count: 候选简称数量
            batch_id: 批次ID
            session_id: 会话ID

        Returns:
            是否保存成功
        """
        try:
            self.db_manager.add_feedback(
                province=province,
                full_name=full_name,
                user_choice=user_choice.value,
                recommended_abbreviation=recommended_abbreviation,
                final_abbreviation=final_abbreviation,
                confidence_level=confidence_level,
                candidate_count=candidate_count,
                batch_id=batch_id,
                session_id=session_id
            )

            # 清空缓存
            self.clear_cache(province)

            logger.info(f"保存反馈: {full_name} -> {final_abbreviation} ({user_choice.value})")
            return True

        except Exception as e:
            logger.error(f"保存反馈失败: {e}")
            return False

    def load_recent_feedback(
        self,
        province: str,
        days: int = 30,
        use_cache: bool = True
    ) -> List[Any]:
        """
        加载最近的反馈

        Args:
            province: 省份
            days: 最近几天
            use_cache: 是否使用缓存

        Returns:
            反馈列表
        """
        if use_cache and self._recent_feedback_cache:
            return self._recent_feedback_cache

        feedbacks = self.db_manager.get_recent_feedback(
            days=days,
            province=province
        )

        self._recent_feedback_cache = feedbacks
        return feedbacks

    def load_confirmed_mappings(
        self,
        province: str,
        use_cache: bool = True
    ) -> Dict[str, Dict[str, Any]]:
        """
        加载确认映射表（用于匹配）

        Args:
            province: 省份
            use_cache: 是否使用缓存

        Returns:
            确认映射字典
        """
        if use_cache and province in self._confirmed_mappings_cache:
            return self._confirmed_mappings_cache[province]

        mappings = self.db_manager.get_confirmed_mappings(
            province=province,
            min_count=self.min_confirmation_count,
            days=self.retention_days
        )

        self._confirmed_mappings_cache[province] = mappings
        return mappings

    def get_mapping_confidence(
        self,
        province: str,
        full_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取特定映射的置信度

        Args:
            province: 省份
            full_name: 全称

        Returns:
            映射信息或 None
        """
        mappings = self.load_confirmed_mappings(province)
        return mappings.get(full_name)

    def is_high_confidence_mapping(
        self,
        province: str,
        full_name: str,
        threshold: int = 5
    ) -> bool:
        """
        检查是否为高置信度映射

        Args:
            province: 省份
            full_name: 全称
            threshold: 确认次数阈值

        Returns:
            是否为高置信度映射
        """
        mapping = self.get_mapping_confidence(province, full_name)
        if not mapping:
            return False

        return mapping.get('confirmation_count', 0) >= threshold

    def batch_save_feedback(
        self,
        feedbacks: List[Dict[str, Any]]
    ) -> int:
        """
        批量保存反馈

        Args:
            feedbacks: 反馈字典列表

        Returns:
            成功保存的数量
        """
        count = 0

        for feedback in feedbacks:
            try:
                self.save_feedback(
                    province=feedback.get('province'),
                    full_name=feedback.get('full_name'),
                    recommended_abbreviation=feedback.get('recommended_abbreviation'),
                    user_choice=UserChoice(feedback.get('user_choice', 'accept')),
                    final_abbreviation=feedback.get('final_abbreviation'),
                    confidence_level=feedback.get('confidence_level'),
                    candidate_count=feedback.get('candidate_count', 0),
                    batch_id=feedback.get('batch_id'),
                    session_id=feedback.get('session_id')
                )
                count += 1
            except Exception as e:
                logger.error(f"批量保存反馈失败: {feedback}, 错误: {e}")

        logger.info(f"批量保存反馈: {count}/{len(feeds)}")
        return count

    def get_feedback_summary(
        self,
        province: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        获取反馈摘要

        Args:
            province: 省份
            days: 最近几天

        Returns:
            摘要字典
        """
        feedbacks = self.load_recent_feedback(province, days)

        if not feedbacks:
            return {
                'total': 0,
                'accepted': 0,
                'rejected': 0,
                'modified': 0,
                'empty': 0,
                'acceptance_rate': 0.0
            }

        total = len(feedbacks)
        accepted = sum(1 for f in feedbacks if f.user_choice == 'accept')
        rejected = sum(1 for f in feedbacks if f.user_choice == 'reject')
        modified = sum(1 for f in feedbacks if f.user_choice == 'modify')
        empty = sum(1 for f in feedbacks if f.user_choice == 'empty')

        return {
            'total': total,
            'accepted': accepted,
            'rejected': rejected,
            'modified': modified,
            'empty': empty,
            'acceptance_rate': round(accepted / total * 100, 2) if total > 0 else 0
        }

    def clear_cache(self, province: Optional[str] = None):
        """
        清空缓存

        Args:
            province: 省份（可选，None 表示清空所有）
        """
        if province:
            if province in self._confirmed_mappings_cache:
                del self._confirmed_mappings_cache[province]
        else:
            self._confirmed_mappings_cache.clear()
            self._recent_feedback_cache.clear()

        logger.info(f"缓存已清空: {province or '全部'}")

    def export_feedback(
        self,
        province: str,
        output_path: str,
        days: int = 30
    ) -> bool:
        """
        导出反馈数据到 Excel

        Args:
            province: 省份
            output_path: 输出路径
            days: 最近几天

        Returns:
            是否导出成功
        """
        try:
            feedbacks = self.load_recent_feedback(province, days)

            # 转换为字典列表
            data = [f.to_dict() for f in feedbacks]

            if not data:
                logger.warning(f"没有反馈数据可导出: {province}")
                return False

            # 使用 pandas 导出
            import pandas as pd
            df = pd.DataFrame(data)
            df.to_excel(output_path, index=False)

            logger.info(f"导出反馈数据: {output_path}, 记录数: {len(data)}")
            return True

        except Exception as e:
            logger.error(f"导出反馈数据失败: {e}")
            return False
