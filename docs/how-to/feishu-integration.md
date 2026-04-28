# 飞书与 NotebookLM 集成指南 | Feishu & NotebookLM Integration Guide

本指南介绍如何配置 `finer` 以自动从飞书群聊拉取文件并同步至 NotebookLM。
This guide explains how to configure `finer` to automatically pull files from Feishu chats and sync them to NotebookLM.

## 1. 环境准备 | Prerequisites

### 飞书 CLI (lark-cli)
系统依赖 [lark-cli](https://github.com/lark-suite/lark-cli) 进行消息拉取。
The system relies on [lark-cli](https://github.com/lark-suite/lark-cli) for message pulling.

```bash
# 安装 | Install
brew install lark-cli  # macOS

# 登录与授权 | Login & Auth
lark-cli auth login --scope "im:message.group,im:chat,im:message,im:message.send_as_user"
```

### NotebookLM CLI (nlm)
如果需要同步至 NotebookLM，请确保已安装对应的 CLI 工具。
For NotebookLM synchronization, ensure the corresponding CLI tool is installed.

## 2. 配置说明 | Configuration

1. **复制模板 | Copy Template**:
   ```bash
   cp configs/feishu.yaml.example configs/feishu.yaml
   ```

2. **核心参数 | Key Parameters**:
   - `lark_cli_path`: `lark-cli` 的二进制文件路径。
   - `watched_chats`: 需要监听的群组 ID 列表。
   - `notebook_id`: 对应的 NotebookLM 笔记本 ID。
   - `classification.rules`: 定义文件归档的正则表达式规则。

## 3. 运行同步 | Running Sync

### 手动同步 | Manual Sync
```bash
finer feishu-sync
```

### 守护模式 | Daemon Mode
```bash
finer feishu-watch --interval 600
```

## 4. 隐私保护 | Privacy Note
请确保 **不将** 包含真实 Chat ID 的 `feishu.yaml` 提交至 Git。项目已默认在 `.gitignore` 中忽略此文件。
Ensure you **do not** commit `feishu.yaml` containing real Chat IDs to Git. The project ignores this file by default via `.gitignore`.
