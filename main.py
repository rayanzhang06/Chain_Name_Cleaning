#!/usr/bin/env python3
"""
医药连锁名称关联 Agent - 主入口

两个主要功能：
1. 阶段一：简称库清洗（在线验证连锁简称）
2. 阶段二：全称-简称关联（使用 LLM 匹配）
"""

import argparse
import logging
import os
import sys
from pathlib import Path

import pandas as pd
import yaml
from dotenv import load_dotenv

from src.utils.logger import setup_logger
from src.database.manager import DatabaseManager
from src.llm.client import LLMClient
from src.stage2.importer import KADataImporter
from src.stage2.matcher import AbbreviationMatcher
from src.stage2.validator import MatchValidator
from src.stage2.feedback import FeedbackManager, UserChoice


# 加载环境变量
load_dotenv()


def load_config(config_path: str = "config.yaml") -> dict:
    """加载配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config


def setup_database(config: dict) -> DatabaseManager:
    """初始化数据库"""
    db_path = Path(config['paths']['database_dir']) / config['paths']['database_file']
    db_manager = DatabaseManager(str(db_path))

    # 创建表
    db_manager.create_tables()

    return db_manager


def run_stage2(
    input_file: str,
    output_file: str,
    province: str,
    config: dict,
    use_history: bool = True
):
    """
    运行阶段二：全称-简称关联

    Args:
        input_file: 输入文件路径
        output_file: 输出文件路径
        province: 省份
        config: 配置字典
        use_history: 是否使用历史反馈
    """
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("阶段二：全称-简称关联")
    logger.info("=" * 60)

    # 初始化组件
    db_manager = setup_database(config)
    llm_client = LLMClient(
        model=config['llm']['model'],
        temperature=config['llm']['temperature'],
        max_tokens=config['llm']['max_tokens']
    )

    # 导入数据
    importer = KADataImporter(batch_size=config['stage2']['batch_size'])
    df, import_info = importer.import_file(input_file, province)

    logger.info(f"导入完成: {import_info['valid_rows']} 行有效数据")

    # 初始化匹配器
    matcher = AbbreviationMatcher(
        db_manager=db_manager,
        llm_client=llm_client,
        enable_history=config['stage2']['enable_history'],
        history_days=config['stage2']['history_days'],
        min_confirmation_count=config['stage2']['min_confirmation_count']
    )

    # 初始化验证器
    validator = MatchValidator(
        db_manager=db_manager,
        strict_mode=config['stage2']['enable_three_layer_protection'],
        allow_cross_province=config['stage2']['allow_out_of_province'],
        allow_fabricated=config['stage2']['allow_fabricated']
    )

    # 初始化反馈管理器
    feedback_manager = FeedbackManager(
        db_manager=db_manager,
        retention_days=config['feedback']['retention_days'],
        min_confirmation_count=config['feedback']['min_confirmation_count']
    )

    # 批量匹配
    logger.info("开始批量匹配...")
    batches = importer.create_batches(df)

    all_results = []
    for batch_idx, batch_df in enumerate(batches, 1):
        logger.info(f"处理批次 {batch_idx}/{len(batches)} ({len(batch_df)} 行)")

        # 构建匹配项（过滤空值）
        items = []
        for _, row in batch_df.iterrows():
            full_name = row['连锁药店全称']
            # 跳过空值或 NaN
            if pd.notna(full_name) and full_name != '':
                items.append({
                    'full_name': full_name,
                    'province': row['省份']
                })

        # 批量匹配
        results = matcher.batch_match(items, use_history=use_history)

        # 三层防护验证（质量层）
        validated_results = []
        for i, result in enumerate(results):
            abbreviation = result.get('abbreviation')
            prov = items[i]['province']

            validation = validator.validate(
                abbreviation=abbreviation,
                province=prov,
                layer="quality"
            )

            if validation.is_valid():
                validated_results.append({
                    **items[i],
                    '匹配简称': validation.abbreviation,
                    '置信度': result.get('confidence', 'Low'),
                    '匹配方式': result.get('match_method', 'llm'),
                    '验证状态': '通过'
                })
            else:
                # 验证失败，记录为空
                validated_results.append({
                    **items[i],
                    '匹配简称': None,
                    '置信度': 'Low',
                    '匹配方式': 'validation_failed',
                    '验证状态': f"失败: {', '.join(validation.violations)}"
                })

                logger.warning(f"验证失败: {items[i]['full_name']} -> {abbreviation}")

        all_results.extend(validated_results)

        # 保存匹配记录
        for result, validation in zip(results, validated_results):
            db_manager.add_match_record(
                province=result.get('province'),
                full_name=result.get('full_name'),
                match_method=result.get('match_method', 'llm'),
                matched_abbreviation=validation.get('匹配简称'),
                confidence_level=result.get('confidence'),
                validation_passed=(validation['验证状态'] == '通过'),
                validation_notes=validation.get('验证状态')
            )

    # 构建输出 DataFrame
    df_output = pd.DataFrame(all_results)

    # 导出结果
    df_output.to_excel(output_file, index=False)
    logger.info(f"结果已导出: {output_file}")

    # 显示统计
    logger.info("=" * 60)
    logger.info("匹配统计:")
    logger.info(f"  总数: {len(df_output)}")
    logger.info(f"  匹配成功: {sum(1 for r in all_results if r['匹配简称'])}")
    logger.info(f"  匹配失败: {sum(1 for r in all_results if not r['匹配简称'])}")
    logger.info(f"  验证通过: {sum(1 for r in all_results if r['验证状态'] == '通过')}")
    logger.info("=" * 60)


def interactive_confirmation(
    input_file: str,
    output_file: str,
    province: str,
    config: dict
):
    """
    交互式确认界面

    Args:
        input_file: 输入文件路径
        output_file: 输出文件路径
        province: 省份
        config: 配置字典
    """
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("交互式确认模式")
    logger.info("=" * 60)

    # TODO: 实现交互式 TUI 界面
    # 这部分可以使用 prompt_toolkit 或 rich 实现
    logger.info("交互式确认模式即将推出...")
    logger.info("请使用非交互模式运行阶段二")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="医药连锁名称关联 Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:

  # 阶段二：全称-简称关联（非交互）
  python main.py stage2 -i data/input/KA专员客户关系数据模板【四川】.xlsx -o data/output/result.xlsx -p 四川

  # 阶段二：交互式确认
  python main.py stage2 -i data/input/KA专员客户关系数据模板【四川】.xlsx -o data/output/result.xlsx -p 四川 --interactive
        """
    )

    parser.add_argument(
        'stage',
        choices=['stage1', 'stage2'],
        help='运行阶段'
    )

    parser.add_argument(
        '-i', '--input',
        required=True,
        help='输入文件路径'
    )

    parser.add_argument(
        '-o', '--output',
        required=True,
        help='输出文件路径'
    )

    parser.add_argument(
        '-p', '--province',
        help='省份（可选，默认从文件名提取）'
    )

    parser.add_argument(
        '--interactive',
        action='store_true',
        help='交互式确认模式'
    )

    parser.add_argument(
        '--no-history',
        action='store_true',
        help='不使用历史反馈学习'
    )

    parser.add_argument(
        '--config',
        default='config.yaml',
        help='配置文件路径（默认: config.yaml）'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='详细日志输出'
    )

    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)

    # 设置日志
    log_level = "DEBUG" if args.verbose else config['logging']['level']
    logger = setup_logger(
        name="main",
        log_file=config['logging']['file_handler']['filename'],
        level=log_level,
        log_dir=Path(config['paths']['logs_dir']),
        console=True
    )

    # 检查 API 密钥
    if not os.getenv("KIMI_API_KEY"):
        logger.error("未找到 KIMI_API_KEY 环境变量，请设置后再运行")
        sys.exit(1)

    # 提取省份
    province = args.province
    if not province and args.stage == 'stage2':
        from src.utils.province_extractor import extract_province_from_filename
        province = extract_province_from_filename(args.input)
        if not province:
            logger.error("无法从文件名提取省份，请使用 -p 参数指定")
            sys.exit(1)

    # 运行对应阶段
    try:
        if args.stage == 'stage2':
            if args.interactive:
                interactive_confirmation(args.input, args.output, province, config)
            else:
                run_stage2(
                    args.input,
                    args.output,
                    province,
                    config,
                    use_history=not args.no_history
                )
        elif args.stage == 'stage1':
            logger.error("阶段一功能即将推出...")
            sys.exit(1)

        logger.info("✓ 执行完成")

    except Exception as e:
        logger.error(f"✗ 执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
