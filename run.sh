#!/bin/bash
# 医药连锁名称关联 Agent - 启动脚本

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}医药连锁名称关联 Agent${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查虚拟环境
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}⚠ 虚拟环境不存在，正在创建...${NC}"
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}✓ 虚拟环境创建完成${NC}"
fi

# 激活虚拟环境
echo -e "${BLUE}→ 激活虚拟环境...${NC}"
source "$VENV_DIR/bin/activate"

# 检查依赖
if ! python -c "import anthropic" 2>/dev/null; then
    echo -e "${YELLOW}⚠ 依赖未安装，正在安装...${NC}"
    pip install --upgrade pip
    pip install -r requirements.txt
    echo -e "${GREEN}✓ 依赖安装完成${NC}"
fi

# 检查 .env 文件
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${RED}✗ 错误：.env 文件不存在${NC}"
    echo -e "${YELLOW}请复制 .env.example 为 .env 并填入你的 API 密钥：${NC}"
    echo -e "  cp .env.example .env"
    echo -e "  nano .env"
    exit 1
fi

# 检查 KIMI_API_KEY
if ! grep -q "KIMI_API_KEY=sk-" "$PROJECT_DIR/.env"; then
    echo -e "${RED}✗ 错误：未设置有效的 KIMI_API_KEY${NC}"
    echo -e "${YELLOW}请编辑 .env 文件并填入你的 API 密钥${NC}"
    exit 1
fi

# 运行程序
echo ""
echo -e "${GREEN}✓ 环境检查完成，开始运行程序...${NC}"
echo ""

python main.py "$@"

echo ""
echo -e "${GREEN}✓ 程序执行完成${NC}"
echo -e "${BLUE}→ 退出虚拟环境${NC}"
deactivate
