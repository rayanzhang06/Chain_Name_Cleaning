#!/bin/bash
# 环境检查脚本 - 验证项目环境是否正确配置

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}环境检查脚本${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查计数
PASS=0
FAIL=0
WARN=0

# 检查函数
check_pass() {
    echo -e "${GREEN}✓ $1${NC}"
    ((PASS++))
}

check_fail() {
    echo -e "${RED}✗ $1${NC}"
    ((FAIL++))
}

check_warn() {
    echo -e "${YELLOW}⚠ $1${NC}"
    ((WARN++))
}

# 1. 检查 Python 版本
echo -e "${BLUE}[1/8] 检查 Python 版本...${NC}"
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 10 ]; then
    check_pass "Python 版本: $PYTHON_VERSION (>= 3.10)"
else
    check_fail "Python 版本过低: $PYTHON_VERSION (需要 >= 3.10)"
fi

# 2. 检查虚拟环境
echo ""
echo -e "${BLUE}[2/8] 检查虚拟环境...${NC}"
if [ -d "venv" ]; then
    check_pass "虚拟环境目录存在"

    # 检查虚拟环境 Python
    if [ -f "venv/bin/python3" ]; then
        VENV_PYTHON_VERSION=$(venv/bin/python3 --version 2>&1 | awk '{print $2}')
        check_pass "虚拟环境 Python 版本: $VENV_PYTHON_VERSION"
    else
        check_fail "虚拟环境 Python 可执行文件不存在"
    fi
else
    check_warn "虚拟环境不存在（运行: python3 -m venv venv）"
fi

# 3. 检查依赖
echo ""
echo -e "${BLUE}[3/8] 检查关键依赖...${NC}"
if [ -d "venv" ]; then
    source venv/bin/activate

    # 检查关键包（使用导入名）
    DEPS=(
        "anthropic:LLM 客户端"
        "pandas:数据处理"
        "openpyxl:Excel 处理"
        "sqlalchemy:数据库 ORM"
        "dotenv:环境变量"
        "yaml:配置文件"
    )

    for dep in "${DEPS[@]}"; do
        package=$(echo $dep | cut -d: -f1)
        desc=$(echo $dep | cut -d: -f2)

        if python -c "import $package" 2>/dev/null; then
            check_pass "$desc ($package)"
        else
            check_fail "$desc ($package) 未安装"
        fi
    done

    deactivate
else
    check_warn "虚拟环境不存在，跳过依赖检查"
fi

# 4. 检查环境变量文件
echo ""
echo -e "${BLUE}[4/8] 检查环境变量配置...${NC}"
if [ -f ".env" ]; then
    check_pass ".env 文件存在"

    # 检查 KIMI_API_KEY
    if grep -q "KIMI_API_KEY=sk-" .env 2>/dev/null; then
        check_pass "KIMI_API_KEY 已设置"
    else
        check_fail "KIMI_API_KEY 未设置或无效"
    fi
else
    check_fail ".env 文件不存在（复制 .env.example 为 .env）"
fi

# 5. 检查配置文件
echo ""
echo -e "${BLUE}[5/8] 检查配置文件...${NC}"
if [ -f "config.yaml" ]; then
    check_pass "config.yaml 存在"
else
    check_fail "config.yaml 不存在"
fi

# 6. 检查数据目录
echo ""
echo -e "${BLUE}[6/8] 检查数据目录...${NC}"
DIRS=("data" "data/input" "data/output" "data/database" "logs")
for dir in "${DIRS[@]}"; do
    if [ -d "$dir" ]; then
        check_pass "目录存在: $dir"
    else
        check_warn "目录不存在: $dir（将自动创建）"
    fi
done

# 7. 检查源代码
echo ""
echo -e "${BLUE}[7/8] 检查源代码...${NC}"
if [ -f "main.py" ]; then
    check_pass "main.py 存在"
else
    check_fail "main.py 不存在"
fi

if [ -d "src" ]; then
    check_pass "src 目录存在"

    # 检查关键模块
    MODULES=(
        "src/database/manager.py"
        "src/llm/client.py"
        "src/stage2/matcher.py"
        "src/stage2/validator.py"
    )

    for module in "${MODULES[@]}"; do
        if [ -f "$module" ]; then
            check_pass "模块存在: $(basename $module)"
        else
            check_fail "模块不存在: $module"
        fi
    done
else
    check_fail "src 目录不存在"
fi

# 8. 检查数据库
echo ""
echo -e "${BLUE}[8/8] 检查数据库...${NC}"
if [ -d "venv" ]; then
    source venv/bin/activate

    if python -c "
from src.database.manager import DatabaseManager
import sys
try:
    db = DatabaseManager('data/database/check.db')
    db.create_tables()
    print('OK')
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)
" 2>/dev/null | grep -q "OK"; then
        check_pass "数据库可以正常创建和访问"

        # 清理测试数据库
        rm -f data/database/check.db
    else
        check_fail "数据库初始化失败"
    fi

    deactivate
fi

# 总结
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}检查总结${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}通过: $PASS${NC}"
echo -e "${YELLOW}警告: $WARN${NC}"
echo -e "${RED}失败: $FAIL${NC}"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}✓ 环境配置完成！可以运行项目了。${NC}"
    echo ""
    echo -e "使用以下命令运行："
    echo -e "  ${BLUE}./run.sh stage2 -i <输入文件> -o <输出文件> -p <省份>${NC}"
    echo ""
    exit 0
else
    echo -e "${RED}✗ 环境配置存在问题，请修复上述错误后重试。${NC}"
    echo ""
    echo -e "参考安装指南："
    echo -e "  ${BLUE}cat INSTALLATION.md${NC}"
    echo ""
    exit 1
fi
