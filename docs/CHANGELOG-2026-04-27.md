# 更新日志 - 2026-04-27

## 主要更改

### 1. ASR (语音识别) 配置

- **新增 FunASR 本地客户端** (`src/finer/parsing/funasr_client.py`)
  - 支持 M2 Mac 本地运行（无需 CUDA）
  - 使用 `paraformer-zh-streaming` 轻量模型
  - 已安装 ffmpeg 和 FunASR 依赖

- **新增 MiMo ASR 客户端** (`src/finer/parsing/mimo_asr_client.py`)
  - 支持 MiMo Open Platform API（远程调用）
  - OpenAI-compatible 格式

- **配置更新** (`src/finer/config.py`)
  - 新增 `FunASRConfig` 数据类
  - 新增 `ASRConfig` 统一配置（支持 `funasr` 和 `mimo_api` 后端）
  - 新增 `load_asr_config()` 函数

- **环境变量** (`.env`)
  - `ASR_BACKEND=funasr` (默认本地)
  - `FUNASR_MODEL=paraformer-zh-streaming`
  - `MIMO_API_KEY` 用于 MiMo TTS/ASR

### 2. API 路由修复

- **streams.py** - 修复 `Path` 导入缺失问题
- **rlhf.py** - 修复空数据时缺少必需字段的问题
- **kol.py** - 新增 KOL Rating API 路由
  - `/api/kol/rating/{kol_id}` - 获取 KOL 评级
  - `/api/kol/list` - 列出所有 KOL

### 3. 前端组件修复

- **hooks.ts** (OpinionTimeline) - 将模拟数据改为真实 API 调用
- **KOLRatingCard.tsx** - 将模拟数据改为真实 API 调用

### 4. MiMo Skills 安装

- 安装 MiMo V2.5 TTS skill（语音合成）
- 位置: `~/Desktop/agentlink/skills/mimo-v2-5-tts`

### 5. 其他新增功能

- **聚合存储** (`src/finer/aggregation/storage.py`)
- **认证中间件** (`src/finer/api/middleware/auth.py`)
- **安全中间件** (`src/finer/api/middleware/security.py`)
- **回测模块** (`src/finer/backtest/`)
- **时间线服务** (`src/finer/timeline/`)
- **情感分析** (`src/finer/ml/sentiment/`)
- **KOL 评分** (`src/finer/ml/kol_scorer.py`)

## 技术说明

### MiMo-V2.5-ASR 无法在 M2 Mac 本地运行

原因：
- 需要 CUDA >= 12.0（M2 Mac 只有 Metal/MPS）
- flash-attn 只支持 CUDA
- 模型约 7-10B 参数，需要 14-20GB VRAM

替代方案：
- FunASR 本地运行（推荐）
- MiMo API 远程调用（需要有效 API key）
- DashScope Paraformer API

### FunASR 安装依赖

```bash
pip install funasr torch torchaudio
brew install ffmpeg
```

模型下载位置: `~/.cache/modelscope/hub/models/iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online/`

## 文件变更统计

- 新增文件: ~50+
- 修改文件: ~40+
- 删除文件: ~10+
