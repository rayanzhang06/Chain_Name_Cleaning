# 安装指南 - Homebrew 用户

本指南专门针对使用 Homebrew 管理 Python 的用户。

## 系统要求

- macOS（基于 Apple Silicon 或 Intel）
- Python 3.10+（推荐 3.14）
- Homebrew

## 检查当前环境

### 1. 检查 Python 版本

```bash
# 查看当前 Python 版本
python3 --version

# 查看 brew 安装的 Python 版本
brew list --versions python@3.10 python@3.11 python@3.12 python@3.13 python@3.14
```

你的系统当前使用：**Python 3.14.2** ✓

### 2. 验证 Python 路径

```bash
# 查看 Python 可执行文件路径
which python3

# 应该显示：/opt/homebrew/bin/python3 (Apple Silicon) 或 /usr/local/bin/python3 (Intel)
```

## 安装步骤

### 步骤 1：克隆或进入项目目录

```bash
cd /Users/ruizhang/Desktop/Projects/Chain_Name_Cleaning
```

### 步骤 2：创建虚拟环境

**强烈推荐使用虚拟环境**，避免污染系统 Python 环境：

```bash
# 在项目目录下创建虚拟环境
python3 -m venv venv

# 验证虚拟环境创建成功
ls -la venv/
```

虚拟环境创建后，你会看到以下结构：
```
venv/
├── bin/
├── include/
├── lib/
└── pyvenv.cfg
```

### 步骤 3：激活虚拟环境

```bash
# 激活虚拟环境
source venv/bin/activate

# 激活后，命令提示符会显示 (venv)
# 例如：(venv) ruizhang@MacBook-Pro Chain_Name_Cleaning %
```

### 步骤 4：升级 pip

```bash
# 升级 pip 到最新版本（推荐）
pip install --upgrade pip

# 验证 pip 版本
pip --version
```

### 步骤 5：安装项目依赖

```bash
# 安装所有依赖
pip install -r requirements.txt

# 验证安装
pip list
```

你应该看到以下关键包已安装：
- anthropic
- pandas
- openpyxl
- sqlalchemy
- python-dotenv
- pyyaml
- 等等...

### 步骤 6：配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 使用你喜欢的编辑器编辑 .env 文件
nano .env
# 或
vim .env
# 或
open -e .env
```

在 `.env` 文件中填入你的 Kimi API 密钥：

```bash
# API 密钥配置
KIMI_API_KEY=sk-your-actual-api-key-here
```

### 步骤 7：验证安装

```bash
# 验证 Python 能找到项目模块
python3 -c "import src.database.manager; print('✓ 模块导入成功')"

# 验证数据库初始化
python3 -c "
from src.database.manager import DatabaseManager
db = DatabaseManager('data/database/test.db')
db.create_tables()
print('✓ 数据库初始化成功')
"

# 清理测试数据库（可选）
rm data/database/test.db
```

## 常用命令

### 虚拟环境管理

```bash
# 激活虚拟环境
source venv/bin/activate

# 退出虚拟环境
deactivate

# 查看已安装的包
pip list

# 查看已安装的包（带版本号）
pip freeze

# 导出依赖列表
pip freeze > requirements-freeze.txt

# 安装单个包
pip install package-name

# 卸载单个包
pip uninstall package-name
```

### 运行项目

```bash
# 确保虚拟环境已激活
source venv/bin/activate

# 运行阶段二
python main.py stage2 \
    -i data/input/KA专员客户关系数据模板【四川】.xlsx \
    -o data/output/result_sichuan.xlsx \
    -p四川

# 查看日志
tail -f logs/chain_agent.log
```

## 常见问题

### Q1: 如何确认我正在使用虚拟环境中的 Python？

```bash
# 激活虚拟环境后运行
which python3

# 应该显示：/Users/ruizhang/Desktop/Projects/Chain_Name_Cleaning/venv/bin/python3
# 而不是：/opt/homebrew/bin/python3
```

### Q2: pip install 报错 "No matching distribution"

**解决方案**：

```bash
# 1. 确保 pip 是最新版本
pip install --upgrade pip

# 2. 如果仍然失败，尝试指定包版本
pip install package-name==version

# 3. 清理 pip 缓存
pip cache purge
```

### Q3: 模块导入错误 "ModuleNotFoundError"

**可能原因**：
1. 虚拟环境未激活
2. 依赖未安装

**解决方案**：

```bash
# 1. 确认虚拟环境已激活
# 命令提示符应显示 (venv)

# 2. 重新安装依赖
pip install -r requirements.txt

# 3. 验证 PYTHONPATH
echo $PYTHONPATH
# 应该为空或包含项目根目录
```

### Q4: Python 3.14 兼容性问题

**问题**：pandas 2.1.4 及更早版本与 Python 3.14 不兼容，会报编译错误。

**错误示例**：
```
error: too few arguments to function call, expected 6, have 5
```

**解决方案**（已应用）：

项目的 `requirements.txt` 已更新为使用兼容 Python 3.14 的版本：
- `pandas>=2.2.0` (支持 Python 3.14)
- 所有其他依赖使用 `>=` 而非 `==` 以确保获取兼容版本

如果你仍然遇到兼容性问题：

```bash
# 方案 1: 确保使用最新的 requirements.txt
pip install -r requirements.txt

# 方案 2: 升级特定包
pip install --upgrade pandas numpy

# 方案 3: 切换到 Python 3.12 或 3.13（如果方案 1、2 失败）
brew install python@3.12
/opt/homebrew/bin/python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Q5: 如何重置虚拟环境？

```bash
# 1. 退出虚拟环境（如果已激活）
deactivate

# 2. 删除虚拟环境目录
rm -rf venv/

# 3. 重新创建虚拟环境
python3 -m venv venv

# 4. 激活并安装依赖
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 推荐工作流

```bash
# 1. 进入项目目录
cd /Users/ruizhang/Desktop/Projects/Chain_Name_Cleaning

# 2. 激活虚拟环境
source venv/bin/activate

# 3. 运行项目
python main.py stage2 [选项...]

# 4. 完成后退出虚拟环境
deactivate
```

## 下一步

安装完成后，请参考 [README.md](README.md) 了解如何使用项目。

## 需要帮助？

如果遇到问题，请检查：
1. ✓ 虚拟环境是否已激活
2. ✓ Python 版本是否 >= 3.10
3. ✓ 所有依赖是否已安装
4. ✓ .env 文件是否正确配置
