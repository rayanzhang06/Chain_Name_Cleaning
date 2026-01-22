# Archive - 归档文件

此文件夹包含与主线逻辑无关的旧文件、实验性代码和临时数据。

## 目录结构

### `old_scripts/` - 旧的脚本文件
这些是早期版本的实验性脚本，已被新的模块化架构取代：
- `auto_batch_search.py` - 自动批量搜索（旧版）
- `batch_evaluate.py` - 批量评估（旧版）
- `cross_validation_engine.py` - 交叉验证引擎（旧版）
- `pattern_based_evaluator.py` - 基于模式的评估器（旧版）
- `run_cross_validation.py` - 运行交叉验证（旧版）
- `search_and_evaluate.py` - 搜索和评估（旧版）
- `smart_evaluate.py` - 智能评估（旧版）

### `old_data/` - 旧的数据文件
包含早期的测试数据和输出结果：
- `chain_names.json` - 连锁名称数据（JSON 格式）
- `confidence_results.json` - 置信度结果
- `cross_validation_report.json` - 交叉验证报告
- `cross_validation_results.json` - 交叉验证结果
- `O2O连锁名称.xlsx` - O2O 连锁名称数据
- `O2O连锁名称_交叉验证.xlsx` - O2O 交叉验证结果
- `O2O连锁名称_带置信度.xlsx` - O2O 带置信度结果
- `人工审核队列.xlsx` - 人工审核队列
- `全国连锁简称.xlsx` - 全国连锁简称（原始数据）

### `old_docs/` - 旧的文档
- `README_交叉验证系统.md` - 交叉验证系统文档（旧版）
- `prompt.md` - 提示词文档（旧版）
- `prompt_v2.md` - 提示词文档 v2（旧版）

### `cache/` - 缓存和临时文件
- `.DS_Store` - macOS 系统文件
- `__pycache__/` - Python 缓存文件
- `2216` - 临时文件

## 注意事项

这些文件仅供历史参考，不应在主线开发中使用。新的项目架构位于：
- `src/` - 源代码
- `main.py` - 主入口
- `config.yaml` - 配置文件

如需访问这些文件，请确保了解其用途和局限性。
