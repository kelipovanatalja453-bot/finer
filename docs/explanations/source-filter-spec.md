# SPEC: 文件导入来源分类与刷新功能优化

## 需求概述

优化文件呈现方式，支持：
1. 按来源分类（飞书、NotebookLM、本地导入）
2. 来源子分类（飞书按群组、NLM按笔记本）
3. 按文件时间戳排序（非上传时间）
4. 已配置来源的增量刷新

---

## 一、数据模型扩展

### 1.1 AssetFile Schema 扩展

```python
# src/finer/schemas/contract.py

class AssetFile(BaseModel):
    # 现有字段...
    id: str
    name: str
    # ...

    # 新增字段
    source_type: Literal["feishu", "notebooklm", "local", "unknown"] = "unknown"
    source_group_id: Optional[str] = None  # chat_id 或 notebook_id
    source_group_name: Optional[str] = None  # 群组名或笔记本名
    file_timestamp: Optional[str] = None  # 文件自身时间戳 (ISO格式)
```

### 1.2 来源分组信息结构

```typescript
// 前端类型定义
type SourceFilter = {
  type: "feishu" | "notebooklm" | "local" | "all";
  groupId?: string;  // 子分类ID
  groupName?: string;
};

type SourceGroup = {
  id: string;
  name: string;
  type: "feishu" | "notebooklm";
  fileCount: number;
  lastSync?: string;
};
```

---

## 二、后端 API 变更

### 2.1 扩展 `/api/files` 端点

**新增查询参数：**
- `source_type`: 按来源类型过滤
- `source_group_id`: 按来源子分类过滤
- `sort_by`: 排序字段 (`file_timestamp` | `upload_time`)

**响应扩展：**
```json
{
  "files": [...],
  "sourceGroups": [
    {
      "id": "oc_29eb19dc...",
      "name": "20269友沟通群",
      "type": "feishu",
      "fileCount": 15,
      "lastSync": "2026-04-15T10:30:00Z"
    }
  ],
  "totalBySource": {
    "feishu": 45,
    "notebooklm": 12,
    "local": 8
  }
}
```

### 2.2 新增 `/api/sources/groups` 端点

返回所有已配置的来源分组信息，供前端下拉栏使用。

### 2.3 新增 `/api/sources/refresh` 端点

增量刷新指定来源：
```json
// POST /api/sources/refresh
{
  "source_type": "feishu",
  "group_id": "oc_29eb19dc..."  // 可选，不传则刷新全部
}
```

---

## 三、前端组件变更

### 3.1 MainBoard 组件扩展

新增两个下拉选择器：

```
┌─────────────────────────────────────────────────────────────┐
│  [来源: 全部 ▼]  [子分类: 全部群组 ▼]  [排序: 文件时间 ▼]   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  文件网格...                                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 来源选择器组件

```tsx
// components/layout/source-filter.tsx

type SourceFilterProps = {
  sourceType: string;
  groups: SourceGroup[];
  selectedGroup: string | null;
  onSourceChange: (type: string) => void;
  onGroupChange: (groupId: string | null) => void;
};
```

### 3.3 刷新按钮组件

在来源选择器旁添加刷新按钮，点击后调用增量同步 API。

---

## 四、时间戳提取逻辑

### 4.1 飞书文件

从 `manifest.metadata.feishu_message_id` 关联的消息时间，或文件名前缀 `20260415_0859_...` 解析。

### 4.2 NotebookLM 文件

从 NLM source 元数据中提取创建时间。

### 4.3 本地文件

从文件系统 mtime 或 manifest.published_at 获取。

---

## 五、实施步骤

### Phase 1: 后端扩展 (Day 1)
1. 扩展 `AssetFile` schema
2. 修改 `build_workflow_assets()` 提取来源信息
3. 新增 `/api/sources/groups` 端点
4. 新增 `/api/sources/refresh` 端点

### Phase 2: 前端组件 (Day 2)
1. 创建 `SourceFilter` 组件
2. 修改 `MainBoard` 集成过滤器
3. 添加刷新按钮逻辑

### Phase 3: 排序优化 (Day 3)
1. 实现时间戳提取逻辑
2. 修改排序算法
3. 前端适配

---

## 六、技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 飞书文件名格式不一致 | 时间戳解析失败 | 多格式匹配 + 回退到 mtime |
| NLM API 限流 | 刷新失败 | 添加重试机制 + 错误提示 |
| 大量文件时性能 | 加载缓慢 | 分页 + 虚拟滚动 |

---

## 七、验收标准

- [ ] 来源下拉栏显示飞书、NotebookLM、本地、全部四个选项
- [ ] 选择飞书后，子分类下拉显示所有已配置群组
- [ ] 选择群组后，文件列表正确过滤
- [ ] 文件按时间戳降序排列
- [ ] 点击刷新按钮后，增量拉取新内容并更新列表
- [ ] 新群组自动出现在子分类下拉中
