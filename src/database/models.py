"""
数据库模型定义

定义 SQLAlchemy ORM 模型用于连锁名称关联系统。
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Text, Float, Boolean, Index
)
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class ChainAbbreviation(Base):
    """
    连锁简称表 - 存储已验证的连锁简称

    用于阶段一的输出，也是阶段二的输入（候选库）。
    """
    __tablename__ = 'chain_abbreviations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    abbreviation = Column(String(100), nullable=False, unique=True, comment='简称')
    full_name = Column(String(200), nullable=True, comment='全称')
    province = Column(String(50), nullable=False, comment='省份')

    # 在线验证结果
    confidence_level = Column(String(20), nullable=False, comment='置信度等级: High/Medium/Low')
    confidence_score = Column(Float, nullable=True, comment='置信度分数 (0-100)')

    # 搜索证据
    evidence_count = Column(Integer, default=0, comment='搜索结果数量')
    evidence_urls = Column(Text, nullable=True, comment='搜索结果URL (JSON 数组)')
    evidence_summary = Column(Text, nullable=True, comment='搜索结果摘要')

    # 数据质量标记
    is_validated = Column(Boolean, default=False, comment='是否已人工审核')
    is_operating_group = Column(Boolean, default=False, comment='是否为运营分组')
    is_third_party = Column(Boolean, default=False, comment='是否为代运营公司')
    needs_review = Column(Boolean, default=False, comment='是否需要人工审核')

    # 时间戳
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    verified_at = Column(DateTime, nullable=True, comment='验证时间')

    # 审核信息
    reviewed_by = Column(String(50), nullable=True, comment='审核人')
    review_notes = Column(Text, nullable=True, comment='审核备注')

    def __repr__(self):
        return f"<ChainAbbreviation(abbreviation='{self.abbreviation}', province='{self.province}', confidence='{self.confidence_level}')>"

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'abbreviation': self.abbreviation,
            'full_name': self.full_name,
            'province': self.province,
            'confidence_level': self.confidence_level,
            'confidence_score': self.confidence_score,
            'evidence_count': self.evidence_count,
            'evidence_urls': self.evidence_urls,
            'evidence_summary': self.evidence_summary,
            'is_validated': self.is_validated,
            'is_operating_group': self.is_operating_group,
            'is_third_party': self.is_third_party,
            'needs_review': self.needs_review,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
            'reviewed_by': self.reviewed_by,
            'review_notes': self.review_notes,
        }

    __table_args__ = (
        Index('idx_abbreviation', 'abbreviation'),
        Index('idx_province', 'province'),
        Index('idx_confidence', 'confidence_level'),
        Index('idx_validated', 'is_validated'),
        Index('idx_province_abbreviation', 'province', 'abbreviation'),
    )


class UserFeedback(Base):
    """
    用户反馈表 - 存储用户确认/修改记录

    用于反馈学习系统，持续优化匹配效果。
    """
    __tablename__ = 'user_feedback'

    id = Column(Integer, primary_key=True, autoincrement=True)
    province = Column(String(50), nullable=False, comment='省份')
    full_name = Column(String(200), nullable=False, comment='连锁药店全称')
    recommended_abbreviation = Column(String(100), nullable=True, comment='Agent 推荐的简称')

    # 用户选择
    user_choice = Column(String(20), nullable=False, comment='用户选择: accept/reject/modify/empty')
    final_abbreviation = Column(String(100), nullable=True, comment='最终选择的简称')

    # 匹配元数据
    confidence_level = Column(String(20), nullable=True, comment='推荐时的置信度')
    candidate_count = Column(Integer, default=0, comment='候选简称数量')

    # 反馈时间
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')

    # 元数据
    batch_id = Column(String(50), nullable=True, comment='批次ID')
    session_id = Column(String(50), nullable=True, comment='会话ID')

    def __repr__(self):
        return f"<UserFeedback(full_name='{self.full_name}', choice='{self.user_choice}', final='{self.final_abbreviation}')>"

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'province': self.province,
            'full_name': self.full_name,
            'recommended_abbreviation': self.recommended_abbreviation,
            'user_choice': self.user_choice,
            'final_abbreviation': self.final_abbreviation,
            'confidence_level': self.confidence_level,
            'candidate_count': self.candidate_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'batch_id': self.batch_id,
            'session_id': self.session_id,
        }

    __table_args__ = (
        Index('idx_province_feedback', 'province'),
        Index('idx_full_name_feedback', 'full_name'),
        Index('idx_user_choice', 'user_choice'),
        Index('idx_created_at', 'created_at'),
        Index('idx_province_fullname', 'province', 'full_name'),
    )


class MatchRecord(Base):
    """
    匹配记录表 - 存储所有匹配尝试（无论是否被用户接受）

    用于性能分析和 Agent 改进。
    """
    __tablename__ = 'match_records'

    id = Column(Integer, primary_key=True, autoincrement=True)
    province = Column(String(50), nullable=False, comment='省份')
    full_name = Column(String(200), nullable=False, comment='连锁药店全称')
    matched_abbreviation = Column(String(100), nullable=True, comment='匹配的简称')

    # 匹配方法
    match_method = Column(String(50), nullable=False, comment='匹配方法: llm/history/rule/empty')
    match_source = Column(String(100), nullable=True, comment='匹配来源（历史反馈ID等）')

    # 质量指标
    confidence_level = Column(String(20), nullable=True, comment='置信度等级')
    confidence_score = Column(Float, nullable=True, comment='置信度分数')

    # LLM 相关
    llm_model = Column(String(50), nullable=True, comment='LLM 模型')
    llm_prompt_tokens = Column(Integer, nullable=True, comment='提示词 token 数')
    llm_completion_tokens = Column(Integer, nullable=True, comment='完成 token 数')

    # 验证结果
    validation_passed = Column(Boolean, nullable=True, comment='是否通过三层防护验证')
    validation_notes = Column(Text, nullable=True, comment='验证备注')

    # 用户反馈
    user_accepted = Column(Boolean, nullable=True, comment='用户是否接受')
    user_modified = Column(Boolean, nullable=True, comment='用户是否修改')

    # 时间戳
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')

    def __repr__(self):
        return f"<MatchRecord(full_name='{self.full_name}', matched='{self.matched_abbreviation}', method='{self.match_method}')>"

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'province': self.province,
            'full_name': self.full_name,
            'matched_abbreviation': self.matched_abbreviation,
            'match_method': self.match_method,
            'match_source': self.match_source,
            'confidence_level': self.confidence_level,
            'confidence_score': self.confidence_score,
            'llm_model': self.llm_model,
            'llm_prompt_tokens': self.llm_prompt_tokens,
            'llm_completion_tokens': self.llm_completion_tokens,
            'validation_passed': self.validation_passed,
            'validation_notes': self.validation_notes,
            'user_accepted': self.user_accepted,
            'user_modified': self.user_modified,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    __table_args__ = (
        Index('idx_match_province', 'province'),
        Index('idx_match_fullname', 'full_name'),
        Index('idx_match_method', 'match_method'),
        Index('idx_validation_passed', 'validation_passed'),
        Index('idx_user_accepted', 'user_accepted'),
        Index('idx_created_at_match', 'created_at'),
    )
