#!/bin/bash
# Finer OS GitHub 发布脚本
# 用于更新 GitHub 项目，包括文档、截图等

set -e

echo "🚀 Finer OS GitHub 发布脚本"
echo "============================"

# 检查 git 状态
echo ""
echo "📋 检查 Git 状态..."
git status --short

# 添加所有更改
echo ""
echo "📦 添加更改到暂存区..."
git add -A

# 显示将要提交的文件
echo ""
echo "📝 将要提交的文件:"
git diff --cached --stat

# 生成提交信息
echo ""
echo "✍️  生成提交信息..."

# 获取当前日期
DATE=$(date +"%Y-%m-%d")

# 统计更改
CHANGED_FILES=$(git diff --cached --numstat | wc -l | tr -d ' ')
ADDED_LINES=$(git diff --cached --numstat | awk '{sum+=$1} END {print sum}')
DELETED_LINES=$(git diff --cached --numstat | awk '{sum+=$2} END {print sum}')

COMMIT_MSG="docs: comprehensive project documentation and multi-agent implementation

- Added complete README with architecture diagrams and feature overview
- Added API reference documentation for all endpoints
- Added getting started guide with configuration examples
- Added architecture documentation explaining 6-layer pipeline
- Added features documentation with detailed explanations
- Added visual tour HTML for interactive project introduction
- Added screenshot guide for GitHub presentation

Implementation highlights:
- Trade Action Schema with full validation and helper methods
- L0 summary generator with caching and timestamp extraction
- WeChat official account adapter with QR code login
- Bilibili video transcription with Paraformer ASR
- Trade Action extractor with GLM-5.1 + Finance-Skills hybrid strategy
- RLHF review panel with Chinese UI and keyboard shortcuts
- KOL rating engine with 5-dimension scoring system
- DPO trainer with modern alignment methods
- Opinion timeline visualization
- Data source configuration UI

Stats: $CHANGED_FILES files changed, +$ADDED_LINES -$DELETED_LINES lines"

# 确认提交
echo ""
echo "提交信息预览:"
echo "------------------------"
echo "$COMMIT_MSG"
echo "------------------------"
echo ""
read -p "确认提交? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]
then
    # 提交
    echo ""
    echo "💾 提交更改..."
    git commit -m "$COMMIT_MSG"

    # 推送
    echo ""
    echo "🌐 推送到 GitHub..."
    git push origin main

    echo ""
    echo "✅ 发布完成!"
    echo ""
    echo "GitHub 仓库: https://github.com/kelipovanatalja453-bot/finer"
    echo "可视化教程: docs/visual-tour/index.html"
    echo ""
else
    echo "❌ 取消发布"
fi
