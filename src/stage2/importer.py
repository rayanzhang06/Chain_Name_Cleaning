"""
阶段二数据导入器

导入 KA 专员客户关系数据，进行验证和预处理。
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import pandas as pd

from ..utils.excel_handler import ExcelHandler
from ..utils.province_extractor import extract_province_from_filename
from ..utils.validators import DataValidator, validate_dataframe_row


logger = logging.getLogger(__name__)


class KADataImporter:
    """
    KA 数据导入器

    功能：
    - 导入 Excel 文件
    - 检测和确认省份
    - 数据验证
    - 分批处理
    """

    def __init__(
        self,
        batch_size: int = 50,
        required_fields: Optional[List[str]] = None
    ):
        """
        初始化导入器

        Args:
            batch_size: 批处理大小
            required_fields: 必填字段列表
        """
        self.batch_size = batch_size
        self.required_fields = required_fields or [
            "连锁药店全称",  # 映射后的标准列名
            "省份"
        ]

        # 列名映射（从实际文件列名到标准列名）
        self.column_mapping = {
            "连锁全称": "连锁药店全称",
            "连锁简称": "连锁简称",
        }

        self.excel_handler = ExcelHandler()
        self.current_province = None
        self.total_rows = 0
        self.valid_rows = 0

        logger.info(f"KA 数据导入器初始化完成 (批大小: {batch_size})")

    def import_file(
        self,
        file_path: str,
        province: Optional[str] = None,
        sheet_name: str = 0
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        导入文件

        Args:
            file_path: 文件路径
            province: 省份（可选，默认从文件名提取）
            sheet_name: 工作表名称或索引

        Returns:
            (DataFrame, 导入信息) 元组
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        logger.info(f"开始导入文件: {file_path}")

        # 提取省份
        if province is None:
            province = extract_province_from_filename(str(file_path))
            if not province:
                raise ValueError(f"无法从文件名提取省份，请手动指定: {file_path.name}")

        self.current_province = province
        logger.info(f"检测到省份: {province}")

        # 读取 Excel
        df = self.excel_handler.read_excel(
            file_path=file_path,
            sheet_name=sheet_name
        )

        self.total_rows = len(df)
        logger.info(f"读取 {self.total_rows} 行数据")

        # 应用列名映射
        df = df.rename(columns=self.column_mapping)
        logger.info(f"列名映射完成")

        # 添加省份列（在验证之前）
        if '省份' not in df.columns:
            df['省份'] = province
        else:
            df['省份'] = df['省份'].fillna(province)
        logger.info(f"省份列已添加: {province}")

        # 预处理
        df_processed = self._preprocess_dataframe(df)

        # 验证
        df_valid, validation_info = self._validate_data(df_processed)

        self.valid_rows = len(df_valid)
        logger.info(f"数据验证完成: {self.valid_rows}/{self.total_rows} 行有效")

        # 添加元数据
        import_info = {
            'file_path': str(file_path),
            'province': province,
            'total_rows': self.total_rows,
            'valid_rows': self.valid_rows,
            'invalid_rows': self.total_rows - self.valid_rows,
            'validation_info': validation_info
        }

        return df_valid, import_info

    def _preprocess_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        预处理 DataFrame

        Args:
            df: 原始 DataFrame

        Returns:
            处理后的 DataFrame
        """
        df_processed = self.excel_handler.preprocess_dataframe(
            df=df,
            drop_duplicates=True,
            drop_empty=True,
            normalize_text=True,
            strip_whitespace=True
        )

        return df_processed

    def _validate_data(
        self,
        df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        验证数据

        Args:
            df: DataFrame

        Returns:
            (有效数据 DataFrame, 验证信息) 元组
        """
        valid_rows = []
        invalid_rows = []
        validation_errors = {}

        for idx, row in df.iterrows():
            # 转换为字典
            row_dict = row.to_dict()

            # 验证必填字段
            is_valid, errors = validate_dataframe_row(
                row=row_dict,
                required_fields=self.required_fields
            )

            if is_valid:
                valid_rows.append(row_dict)
            else:
                invalid_rows.append({
                    'index': idx,
                    'row': row_dict,
                    'errors': errors
                })

                # 记录错误类型
                for error in errors:
                    if error not in validation_errors:
                        validation_errors[error] = 0
                    validation_errors[error] += 1

        # 构建有效数据 DataFrame
        df_valid = pd.DataFrame(valid_rows)

        # 构建验证信息
        validation_info = {
            'total': len(df),
            'valid': len(valid_rows),
            'invalid': len(invalid_rows),
            'error_types': validation_errors
        }

        return df_valid, validation_info

    def create_batches(
        self,
        df: pd.DataFrame
    ) -> List[pd.DataFrame]:
        """
        创建批次

        Args:
            df: DataFrame

        Returns:
            批次列表
        """
        batches = []
        total_rows = len(df)

        for i in range(0, total_rows, self.batch_size):
            batch_df = df.iloc[i:i + self.batch_size].copy()
            batches.append(batch_df)

        logger.info(f"创建 {len(batches)} 个批次 (批大小: {self.batch_size})")
        return batches

    def get_import_summary(self) -> Dict[str, Any]:
        """
        获取导入摘要

        Returns:
            摘要字典
        """
        return {
            'province': self.current_province,
            'total_rows': self.total_rows,
            'valid_rows': self.valid_rows,
            'invalid_rows': self.total_rows - self.valid_rows,
            'batch_size': self.batch_size,
            'batch_count': (self.valid_rows + self.batch_size - 1) // self.batch_size
        }

    def reset(self):
        """重置导入器状态"""
        self.current_province = None
        self.total_rows = 0
        self.valid_rows = 0
        logger.info("导入器状态已重置")


# 便捷函数
def quick_import_file(
    file_path: str,
    province: Optional[str] = None
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    快速导入文件（便捷函数）

    Args:
        file_path: 文件路径
        province: 省份（可选）

    Returns:
        (DataFrame, 导入信息) 元组
    """
    importer = KADataImporter()
    return importer.import_file(file_path, province)
