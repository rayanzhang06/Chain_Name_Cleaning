# 医药连锁名称关联 Agent

一个基于 LLM 的智能医药连锁名称匹配系统，支持连锁简称清洗和全称-简称关联。

## 功能特性

### 阶段二：全称-简称关联 ⭐ 当前可用

- **LLM 智能匹配**：使用 Kimi API 进行语义匹配
- **三层防护机制**：确保所有简称来自数据库，严禁编造
- **反馈学习系统**：记录用户反馈并持续优化
- **批量处理**：支持大批量数据高效处理
- **数据验证**：自动验证数据完整性和准确性

### 阶段一：简称库清洗（即将推出）

- 在线搜索验证
- 置信度评估
- 人工审核界面

## 快速开始

### 1. 安装依赖

#### 使用 Homebrew 的用户（推荐）

如果你使用 Homebrew 管理 Python：

```bash
# 1. 确保使用 brew 的 Python（可选，如果已安装可跳过）
brew install python@3.14

# 2. 创建虚拟环境（在项目目录下）
python3 -m venv venv

# 3. 激活虚拟环境
source venv/bin/activate

# 4. 升级 pip（推荐）
pip install --upgrade pip

# 5. 安装依赖
pip install -r requirements.txt
```

#### 标准 pip 安装

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填入你的 API 密钥：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```
KIMI_API_KEY=your_kimi_api_key_here
```

### 3. 验证环境（可选）

运行环境检查脚本，确保一切配置正确：

```bash
./check_env.sh
```

脚本会检查：
- Python 版本
- 虚拟环境
- 依赖包
- 环境变量配置
- 数据库连接

### 4. 准备数据

将输入文件放入 `data/input/` 目录：
- `KA专员客户关系数据模板【省份】.xlsx`

### 5. 运行阶段二

**方式一：使用启动脚本（推荐）**

```bash
./run.sh stage2 \
    -i data/input/KA专员客户关系数据模板【四川】.xlsx \
    -o data/output/result_sichuan.xlsx \
    -p 四川
```

**方式二：手动运行**

```bash
# 激活虚拟环境（如果未激活）
source venv/bin/activate

# 运行程序
python main.py stage2 \
    -i data/input/KA专员客户关系数据模板【四川】.xlsx \
    -o data/output/result_sichuan.xlsx \
    -p 四川

# 完成后退出虚拟环境
deactivate
```

### 6. 查看结果

结果将保存在 `data/output/` 目录，包含：
- 连锁药店全称
- 匹配的简称
- 置信度
- 匹配方式
- 验证状态

## 命令行参数

```
python main.py stage2 [选项]

选项:
  -i, --input PATH      输入文件路径（必需）
  -o, --output PATH     输出文件路径（必需）
  -p, --province TEXT   省份（可选，默认从文件名提取）
  --interactive         交互式确认模式
  --no-history          不使用历史反馈学习
  --config PATH         配置文件路径（默认: config.yaml）
  --verbose             详细日志输出
```

## 便捷脚本

项目提供了两个便捷脚本，简化日常使用：

### `run.sh` - 启动脚本

自动处理虚拟环境激活和依赖检查，然后运行程序：

```bash
./run.sh stage2 \
    -i data/input/KA专员客户关系数据模板【四川】.xlsx \
    -o data/output/result_sichuan.xlsx \
    -p 四川
```

功能：
- ✓ 自动创建虚拟环境（如果不存在）
- ✓ 自动安装依赖（如果未安装）
- ✓ 检查 .env 文件和 API 密钥
- ✓ 自动激活和退出虚拟环境

### `check_env.sh` - 环境检查脚本

检查项目环境是否正确配置：

```bash
./check_env.sh
```

检查项：
- Python 版本（需要 >= 3.10）
- 虚拟环境状态
- 关键依赖包
- 环境变量配置
- 数据库连接

## 三层防护机制

系统采用严格的三层防护机制，确保数据质量：

### 第一层：Prompt 约束
在提示词中明确要求 LLM 只能从候选库选择

### 第二层：代码验证
验证 LLM 返回的简称是否在数据库中

### 第三层：质量检查
最终输出前对所有匹配进行批量验证

### 违规处理

- 记录警告日志
- 拒绝该匹配
- 字段置空

## 配置说明

配置文件位于 `config.yaml`，主要配置项：

- **LLM 配置**：模型选择、温度参数、Token 限制
- **搜索配置**：搜索策略、并发限制
- **阶段二配置**：批处理大小、历史反馈设置
- **反馈配置**：保留天数、确认次数阈值

## 项目结构

```
Chain_Name_Cleaning/
├── README.md
├── config.yaml
├── main.py
├── requirements.txt
├── .env.example
├── data/
│   ├── input/          # 输入文件
│   ├── output/         # 输出文件
│   └── database/       # SQLite 数据库
├── logs/               # 日志文件
└── src/
    ├── database/       # 数据库模块
    ├── llm/            # LLM 客户端
    ├── search/         # 搜索客户端
    ├── stage1/         # 阶段一模块
    ├── stage2/         # 阶段二模块 ⭐
    └── utils/          # 工具函数
```

## 注意事项

1. **API 密钥**：确保设置了有效的 `KIMI_API_KEY`
2. **数据库初始化**：首次运行会自动创建数据库表
3. **省份匹配**：确保输入文件名包含省份信息
4. **候选库**：阶段二需要先有候选简称数据（需手动导入）

## 技术栈

- Python 3.10+
- Kimi API (Anthropic SDK)
- SQLAlchemy
- pandas + openpyxl
- SQLite

## 开发状态

当前版本专注于**阶段二**功能，阶段一功能即将推出。

## 许可证

MIT License
