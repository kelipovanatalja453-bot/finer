# WeChat Official Account Integration

微信公众号扫码登录与文章同步模块，集成到 Finer OS 后端。

## 功能特性

- **扫码登录**：通过模拟公众号后台编辑文章时的搜索功能获取账号凭证
- **文章列表获取**：列出指定公众号的所有历史文章
- **文章内容下载**：将文章转换为 Markdown 格式保存
- **元数据提取**：提取标题、发布时间、阅读量等信息
- **L0 集成**：文章入库后可触发分类、摘要生成流程

## API 端点

### 登录相关

#### POST `/api/wechat/login`
创建登录会话，返回二维码 URL。

**响应示例**：
```json
{
  "session_id": "abc123...",
  "qr_url": "https://mp.weixin.qq.com/cgi-bin/loginqrcode?token=xxx",
  "qr_base64": "data:image/png;base64,...",
  "expires_in": 300,
  "status": "pending"
}
```

#### GET `/api/wechat/login/status/{session_id}`
检查登录状态。

**响应示例**：
```json
{
  "session_id": "abc123...",
  "status": "confirmed",
  "account_id": "gh_xxxx",
  "account_name": "测试公众号"
}
```

### 账号管理

#### GET `/api/wechat/accounts`
获取已登录账号列表。

#### GET `/api/wechat/accounts/{account_id}`
获取指定账号信息。

#### DELETE `/api/wechat/accounts/{account_id}`
移除已登录账号。

### 文章管理

#### GET `/api/wechat/articles/{account_id}`
获取文章列表。

**参数**：
- `page`: 页码（默认 0）
- `page_size`: 每页数量（默认 10）
- `query`: 搜索关键词（可选）

**响应示例**：
```json
{
  "account_id": "gh_xxxx",
  "articles": [
    {
      "article_id": "article-001",
      "title": "测试文章标题",
      "author": "作者",
      "publish_time": "2026-04-23T10:00:00",
      "read_count": 1234,
      "like_count": 56
    }
  ],
  "total": 100,
  "page": 0,
  "page_size": 10
}
```

#### POST `/api/wechat/sync/{account_id}`
同步账号下所有文章。

**参数**：
- `max_articles`: 最大同步数量（可选）
- `include_images`: 是否下载图片（默认 false）
- `trigger_l0`: 是否触发 L0 流程（默认 true）

**响应示例**：
```json
{
  "account_id": "gh_xxxx",
  "synced_count": 50,
  "articles": [
    "/path/to/article1.md",
    "/path/to/article2.md"
  ],
  "errors": [],
  "l0_triggered": false
}
```

#### POST `/api/wechat/sync-single`
同步单篇文章。

**参数**：
- `account_id`: 账号 ID
- `article_id`: 文章 ID
- `include_images`: 是否下载图片

### 状态查询

#### GET `/api/wechat/status`
获取整体状态。

**响应示例**：
```json
{
  "enabled": true,
  "accounts_count": 2,
  "total_articles_synced": 150,
  "last_sync": "2026-04-23T15:30:00",
  "cache_dir": "data/cache/wechat",
  "output_dir": "data/raw/wechat"
}
```

## 使用流程

### 1. 启动后端服务

```bash
cd /Users/zhouhongyuan/Desktop/finer
python -m src.finer.api.server
```

服务将在 `http://127.0.0.1:8000` 启动。

### 2. 扫码登录

```bash
# 创建登录会话
curl -X POST http://127.0.0.1:8000/api/wechat/login

# 返回 session_id 和 qr_url
# 使用微信扫描 qr_url 对应的二维码
```

### 3. 检查登录状态

```bash
# 轮询登录状态
curl http://127.0.0.1:8000/api/wechat/login/status/{session_id}

# 当 status 变为 "confirmed" 时，登录成功
```

### 4. 获取文章列表

```bash
# 列出文章
curl "http://127.0.0.1:8000/api/wechat/articles/{account_id}?page=0&page_size=20"
```

### 5. 同步文章

```bash
# 同步所有文章
curl -X POST "http://127.0.0.1:8000/api/wechat/sync/{account_id}"

# 或同步单篇
curl -X POST "http://127.0.0.1:8000/api/wechat/sync-single?account_id={account_id}&article_id={article_id}"
```

## 数据存储

### 目录结构

```
data/
├── cache/
│   └── wechat/
│       ├── accounts.json      # 已登录账号缓存
│       └── sessions/          # 会话数据
└── raw/
    └── wechat/
        └── {account_id}/      # 按公众号分目录
            ├── article_001_title.md
            ├── article_001_title.json
            ├── article_002_title.md
            └── ...
```

### 文章格式

**Markdown 文件** (`article_xxx.md`)：
```markdown
# 文章标题

**作者**: 作者名
**发布时间**: 2026-04-23 10:00
**阅读数**: 1234
**点赞数**: 56

---

文章摘要内容...

正文内容...

---

> 文章来源：微信公众号 article_xxx
> 采集时间：2026-04-23 15:30:00
```

**元数据文件** (`article_xxx.json`)：
```json
{
  "article_id": "article_xxx",
  "title": "文章标题",
  "author": "作者",
  "publish_time": "2026-04-23T10:00:00",
  "read_count": 1234,
  "like_count": 56,
  "content_url": "https://mp.weixin.qq.com/s/xxx",
  "synced_at": "2026-04-23T15:30:00"
}
```

## 技术说明

### 登录原理

该模块模拟公众号后台编辑文章时的搜索功能：
1. 调用 `bizlogin` 接口启动登录流程
2. 获取并显示二维码供用户扫描
3. 轮询登录状态直到确认
4. 保存 token 和 cookie 供后续请求使用

### 反爬处理

- 模拟正常浏览器请求头
- 使用有效的 session cookie
- 控制请求频率避免触发限制
- 失败时自动重试

### 图片处理

默认保留图片原始 URL，可选下载到本地：
- 图片保存在 `{article_name}_images/` 目录
- 支持 JPG、PNG 格式
- 自动识别图片类型

## 测试模式

设置环境变量启用测试模式：
```bash
export WECHAT_TEST_MODE=1
```

测试模式下会返回模拟数据，无需真实登录。

## 注意事项

1. **账号安全**：token 和 cookie 保存在本地缓存，请勿泄露
2. **频率限制**：避免频繁请求，建议间隔 1-2 秒
3. **登录有效期**：token 可能过期，需要重新扫码登录
4. **图片防盗链**：部分图片可能有防盗链限制

## 依赖

- `httpx` - HTTP 客户端
- `fastapi` - API 框架
- `pydantic` - 数据验证

## 扩展建议

1. **前端集成**：在 Integrations Hub 添加 WeChat 入口
2. **定时同步**：使用定时任务自动同步新文章
3. **增量同步**：记录同步位置，只获取新文章
4. **内容分析**：对接 L0 流水线进行分类和摘要
