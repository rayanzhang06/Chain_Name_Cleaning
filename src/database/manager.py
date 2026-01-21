"""
数据库管理器

提供数据库连接、初始化、CRUD 操作等功能。
"""

import json
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple

from sqlalchemy import create_engine, and_, or_, func, desc
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from .models import Base, ChainAbbreviation, UserFeedback, MatchRecord


logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    数据库管理器 - 核心数据库操作类

    提供所有数据库操作的统一接口，包括：
    - 连接管理
    - 表初始化
    - CRUD 操作
    - 查询和分析
    """

    def __init__(self, db_path: str):
        """
        初始化数据库管理器

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        self.engine = None
        self.SessionLocal = None
        self._initialize_engine()

    def _initialize_engine(self):
        """初始化数据库引擎"""
        # 确保数据库目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # 创建 SQLite 连接字符串
        db_url = f"sqlite:///{self.db_path}"

        # 创建引擎
        self.engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},  # 允许多线程
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # 检查连接有效性
            echo=False,  # 生产环境关闭 SQL 日志
        )

        # 创建 Session 工厂
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

        logger.info(f"数据库引擎初始化完成: {self.db_path}")

    def create_tables(self):
        """创建所有表"""
        Base.metadata.create_all(bind=self.engine)
        logger.info("数据库表创建完成")

    def drop_tables(self):
        """删除所有表（谨慎使用）"""
        Base.metadata.drop_all(bind=self.engine)
        logger.warning("数据库表已删除")

    @contextmanager
    def get_session(self) -> Session:
        """
        获取数据库会话（上下文管理器）

        用法:
            with db_manager.get_session() as session:
                # 使用 session 进行操作
                pass
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            session.close()

    # ============ ChainAbbreviation 操作 ============

    def add_abbreviation(
        self,
        abbreviation: str,
        province: str,
        full_name: Optional[str] = None,
        confidence_level: str = "Low",
        confidence_score: Optional[float] = None,
        **kwargs
    ) -> ChainAbbreviation:
        """
        添加简称记录

        Args:
            abbreviation: 简称
            province: 省份
            full_name: 全称（可选）
            confidence_level: 置信度等级
            confidence_score: 置信度分数
            **kwargs: 其他字段

        Returns:
            ChainAbbreviation 对象
        """
        with self.get_session() as session:
            # 检查是否已存在
            existing = session.query(ChainAbbreviation).filter_by(
                abbreviation=abbreviation,
                province=province
            ).first()

            if existing:
                logger.warning(f"简称 '{abbreviation}' (省份: {province}) 已存在，更新记录")
                # 更新字段
                if full_name:
                    existing.full_name = full_name
                existing.confidence_level = confidence_level
                existing.confidence_score = confidence_score
                existing.updated_at = datetime.now()
                for key, value in kwargs.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
                session.commit()
                return existing

            # 创建新记录
            record = ChainAbbreviation(
                abbreviation=abbreviation,
                province=province,
                full_name=full_name,
                confidence_level=confidence_level,
                confidence_score=confidence_score,
                **kwargs
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            logger.info(f"添加简称: {abbreviation} ({province})")
            return record

    def get_abbreviation(self, abbreviation: str, province: str) -> Optional[ChainAbbreviation]:
        """
        获取简称记录

        Args:
            abbreviation: 简称
            province: 省份

        Returns:
            ChainAbbreviation 对象或 None
        """
        with self.get_session() as session:
            return session.query(ChainAbbreviation).filter_by(
                abbreviation=abbreviation,
                province=province
            ).first()

    def get_abbreviations_by_province(self, province: str, validated_only: bool = False) -> List[ChainAbbreviation]:
        """
        获取省份的所有简称

        Args:
            province: 省份
            validated_only: 是否只返回已验证的简称

        Returns:
            ChainAbbreviation 列表
        """
        with self.get_session() as session:
            query = session.query(ChainAbbreviation).filter_by(province=province)

            if validated_only:
                query = query.filter_by(is_validated=True)

            return query.all()

    def get_all_abbreviations(self, validated_only: bool = False) -> List[ChainAbbreviation]:
        """
        获取所有简称

        Args:
            validated_only: 是否只返回已验证的简称

        Returns:
            ChainAbbreviation 列表
        """
        with self.get_session() as session:
            query = session.query(ChainAbbreviation)

            if validated_only:
                query = query.filter_by(is_validated=True)

            return query.all()

    def update_abbreviation(
        self,
        abbreviation: str,
        province: str,
        **kwargs
    ) -> Optional[ChainAbbreviation]:
        """
        更新简称记录

        Args:
            abbreviation: 简称
            province: 省份
            **kwargs: 要更新的字段

        Returns:
            更新后的 ChainAbbreviation 对象或 None
        """
        with self.get_session() as session:
            record = session.query(ChainAbbreviation).filter_by(
                abbreviation=abbreviation,
                province=province
            ).first()

            if not record:
                logger.warning(f"简称 '{abbreviation}' (省份: {province}) 不存在")
                return None

            for key, value in kwargs.items():
                if hasattr(record, key):
                    setattr(record, key, value)

            record.updated_at = datetime.now()
            session.commit()
            session.refresh(record)
            logger.info(f"更新简称: {abbreviation} ({province})")
            return record

    def delete_abbreviation(self, abbreviation: str, province: str) -> bool:
        """
        删除简称记录

        Args:
            abbreviation: 简称
            province: 省份

        Returns:
            是否删除成功
        """
        with self.get_session() as session:
            record = session.query(ChainAbbreviation).filter_by(
                abbreviation=abbreviation,
                province=province
            ).first()

            if not record:
                logger.warning(f"简称 '{abbreviation}' (省份: {province}) 不存在")
                return False

            session.delete(record)
            session.commit()
            logger.info(f"删除简称: {abbreviation} ({province})")
            return True

    # ============ UserFeedback 操作 ============

    def add_feedback(
        self,
        province: str,
        full_name: str,
        user_choice: str,
        recommended_abbreviation: Optional[str] = None,
        final_abbreviation: Optional[str] = None,
        confidence_level: Optional[str] = None,
        candidate_count: int = 0,
        batch_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> UserFeedback:
        """
        添加用户反馈

        Args:
            province: 省份
            full_name: 连锁药店全称
            user_choice: 用户选择 (accept/reject/modify/empty)
            recommended_abbreviation: 推荐的简称
            final_abbreviation: 最终选择的简称
            confidence_level: 推荐时的置信度
            candidate_count: 候选简称数量
            batch_id: 批次ID
            session_id: 会话ID

        Returns:
            UserFeedback 对象
        """
        with self.get_session() as session:
            feedback = UserFeedback(
                province=province,
                full_name=full_name,
                user_choice=user_choice,
                recommended_abbreviation=recommended_abbreviation,
                final_abbreviation=final_abbreviation,
                confidence_level=confidence_level,
                candidate_count=candidate_count,
                batch_id=batch_id,
                session_id=session_id
            )
            session.add(feedback)
            session.commit()
            session.refresh(feedback)
            logger.info(f"添加反馈: {full_name} -> {final_abbreviation} ({user_choice})")
            return feedback

    def get_recent_feedback(
        self,
        days: int = 30,
        province: Optional[str] = None
    ) -> List[UserFeedback]:
        """
        获取最近的反馈

        Args:
            days: 最近几天
            province: 省份（可选）

        Returns:
            UserFeedback 列表
        """
        with self.get_session() as session:
            cutoff_date = datetime.now() - timedelta(days=days)
            query = session.query(UserFeedback).filter(
                UserFeedback.created_at >= cutoff_date
            )

            if province:
                query = query.filter_by(province=province)

            return query.order_by(desc(UserFeedback.created_at)).all()

    def get_confirmed_mappings(
        self,
        province: str,
        min_count: int = 3,
        days: int = 30
    ) -> Dict[str, Dict[str, Any]]:
        """
        获取确认的映射表（用于反馈学习）

        返回格式:
        {
            "全称": {
                "abbreviation": "简称",
                "confirmation_count": 8,
                "confidence": "High",
                "last_confirmed_at": "2026-01-10"
            }
        }

        Args:
            province: 省份
            min_count: 最小确认次数
            days: 最近几天

        Returns:
            确认映射字典
        """
        with self.get_session() as session:
            cutoff_date = datetime.now() - timedelta(days=days)

            # 查询接受的反馈
            results = session.query(
                UserFeedback.full_name,
                UserFeedback.final_abbreviation,
                func.count(UserFeedback.id).label('count'),
                func.max(UserFeedback.created_at).label('last_confirmed')
            ).filter(
                and_(
                    UserFeedback.province == province,
                    UserFeedback.user_choice == 'accept',
                    UserFeedback.final_abbreviation.isnot(None),
                    UserFeedback.created_at >= cutoff_date
                )
            ).group_by(
                UserFeedback.full_name,
                UserFeedback.final_abbreviation
            ).having(
                func.count(UserFeedback.id) >= min_count
            ).all()

            # 构建映射字典
            mappings = {}
            for full_name, abbreviation, count, last_confirmed in results:
                mappings[full_name] = {
                    "abbreviation": abbreviation,
                    "confirmation_count": count,
                    "confidence": "High" if count >= 5 else "Medium",
                    "last_confirmed_at": last_confirmed.isoformat() if last_confirmed else None
                }

            logger.info(f"加载确认映射: {len(mappings)} 个 (省份: {province})")
            return mappings

    # ============ MatchRecord 操作 ============

    def add_match_record(
        self,
        province: str,
        full_name: str,
        match_method: str,
        matched_abbreviation: Optional[str] = None,
        **kwargs
    ) -> MatchRecord:
        """
        添加匹配记录

        Args:
            province: 省份
            full_name: 连锁药店全称
            match_method: 匹配方法
            matched_abbreviation: 匹配的简称
            **kwargs: 其他字段

        Returns:
            MatchRecord 对象
        """
        with self.get_session() as session:
            record = MatchRecord(
                province=province,
                full_name=full_name,
                match_method=match_method,
                matched_abbreviation=matched_abbreviation,
                **kwargs
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def get_match_statistics(
        self,
        province: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        获取匹配统计信息

        Args:
            province: 省份（可选）
            days: 最近几天

        Returns:
            统计信息字典
        """
        with self.get_session() as session:
            cutoff_date = datetime.now() - timedelta(days=days)
            query = session.query(MatchRecord).filter(
                MatchRecord.created_at >= cutoff_date
            )

            if province:
                query = query.filter_by(province=province)

            records = query.all()

            stats = {
                "total_matches": len(records),
                "matched": sum(1 for r in records if r.matched_abbreviation),
                "empty": sum(1 for r in records if not r.matched_abbreviation),
                "validation_passed": sum(1 for r in records if r.validation_passed),
                "user_accepted": sum(1 for r in records if r.user_accepted),
                "user_modified": sum(1 for r in records if r.user_modified),
                "by_method": {},
                "by_confidence": {}
            }

            # 按方法统计
            for record in records:
                method = record.match_method
                stats["by_method"][method] = stats["by_method"].get(method, 0) + 1

            # 按置信度统计
            for record in records:
                if record.confidence_level:
                    conf = record.confidence_level
                    stats["by_confidence"][conf] = stats["by_confidence"].get(conf, 0) + 1

            return stats

    # ============ 批量操作 ============

    def bulk_add_abbreviations(self, abbreviations: List[Dict[str, Any]]) -> int:
        """
        批量添加简称

        Args:
            abbreviations: 简称字典列表

        Returns:
            添加数量
        """
        count = 0
        for abbr in abbreviations:
            try:
                self.add_abbreviation(**abbr)
                count += 1
            except Exception as e:
                logger.error(f"批量添加失败: {abbr}, 错误: {e}")

        logger.info(f"批量添加简称: {count}/{len(abbreviations)}")
        return count

    # ============ 分析查询 ============

    def get_low_confidence_records(
        self,
        threshold_score: float = 60.0,
        limit: int = 100
    ) -> List[ChainAbbreviation]:
        """
        获取低置信度记录（用于人工审核）

        Args:
            threshold_score: 置信度分数阈值
            limit: 返回数量限制

        Returns:
            ChainAbbreviation 列表
        """
        with self.get_session() as session:
            return session.query(ChainAbbreviation).filter(
                and_(
                    ChainAbbreviation.confidence_score < threshold_score,
                    ChainAbbreviation.needs_review == True
                )
            ).order_by(ChainAbbreviation.confidence_score.asc()).limit(limit).all()

    def get_feedback_acceptance_rate(
        self,
        province: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, float]:
        """
        计算反馈接受率

        Args:
            province: 省份（可选）
            days: 最近几天

        Returns:
            接受率统计
        """
        with self.get_session() as session:
            cutoff_date = datetime.now() - timedelta(days=days)
            query = session.query(UserFeedback).filter(
                UserFeedback.created_at >= cutoff_date
            )

            if province:
                query = query.filter_by(province=province)

            feedbacks = query.all()

            if not feedbacks:
                return {"acceptance_rate": 0.0, "rejection_rate": 0.0}

            accept_count = sum(1 for f in feedbacks if f.user_choice == 'accept')
            reject_count = sum(1 for f in feedbacks if f.user_choice == 'reject')

            total = len(feedbacks)
            return {
                "acceptance_rate": round(accept_count / total * 100, 2),
                "rejection_rate": round(reject_count / total * 100, 2),
                "total": total,
                "accepted": accept_count,
                "rejected": reject_count
            }
