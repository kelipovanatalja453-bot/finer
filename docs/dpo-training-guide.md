# DPO 微调配置指南

## 概述

Direct Preference Optimization (DPO) 是一种高效的 LLM 对齐方法，无需训练独立的 reward model。本模块实现从 RLHF 反馈数据导出 DPO 训练格式的完整流程。

## 数据格式

### DPO 训练数据结构

```json
{
  "prompt": "从以下文本提取 Trade Action:\n\n## 原文\nAAPL 在 150 美元附近形成支撑，建议逢低建仓...\n\n## 提取要求\n...",
  "chosen": "{\"ticker\": \"AAPL\", \"direction\": \"bullish\", \"action_chain\": [{\"action_type\": \"long\", \"target_price_low\": 148, \"target_price_high\": 152}]}",
  "rejected": "{\"ticker\": \"AAPL\", \"direction\": \"neutral\", \"action_chain\": []}"
}
```

### 数据筛选策略

| 条件 | 行为 |
|------|------|
| `rating >= 3` | 包含在训练集 |
| `is_original_correct = True` | 跳过（无学习信号） |
| `is_original_correct = False` + 有修正 | chosen=修正, rejected=原始 |
| 缺少 preference | 跳过 |

## Prompt Template 设计

### System Prompt

```
你是一位专业的金融分析师助手，擅长从文本中提取结构化的交易观点。

你的任务是从给定的文本中识别并提取交易信号，包括：
1. 交易标的（股票代码）
2. 方向（看多/看空/中性/观望/风险警示）
3. 具体的交易动作链
4. 触发条件和目标价格区间
5. 时间周期

输出必须严格遵循指定的 JSON Schema 格式。
```

### User Prompt 结构

```
从以下文本提取 TradeAction：

## 原文
{evidence_text}

## 提取要求
1. 准确识别交易标的（ticker）
2. 判断整体方向：bullish/bearish/neutral/watchlist/risk_warning
3. 提取动作链（action_chain）
4. 判断时间周期（time_horizon）
5. 给出提取置信度（0-1）

## 输出格式
[JSON Schema]
```

## DPO 超参数配置

### 推荐配置

```python
from finer.ml import DPOConfig

config = DPOConfig(
    # DPO-specific
    beta=0.01,          # KL penalty — 较低值适合结构化输出
    loss_type="sigmoid", # 标准损失函数

    # Training
    learning_rate=5e-7,  # 保守学习率防止灾难性遗忘
    num_train_epochs=1,  # 单 epoch 通常足够
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,

    # Model
    model_name_or_path="Qwen/Qwen2.5-14B-Instruct",
    use_peft=True,       # 使用 LoRA 高效微调
    lora_r=16,
    lora_alpha=32,

    # Data
    min_rating=3,        # 只使用高质量反馈
)
```

### 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `beta` | 0.01 | KL 散度惩罚系数。较低值适合 JSON 等结构化输出 |
| `learning_rate` | 5e-7 | 学习率。过低会导致欠拟合，过高会破坏预训练知识 |
| `num_train_epochs` | 1 | 训练轮数。DPO 通常 1-3 轮足够 |
| `lora_r` | 16 | LoRA 秩。影响可训练参数数量 |
| `min_rating` | 3 | 最小反馈评分阈值 |

### 为什么 beta=0.01？

- 标准推荐值 0.1 对开放式生成任务有效
- 结构化输出（如 JSON）对格式敏感，低 beta 减少格式偏离风险
- 金融领域需要精确的实体提取，低 beta 保持稳定性

## 使用示例

### 1. 导出完整数据集

```python
from finer.ml import DPOExporter

exporter = DPOExporter()
items = exporter.export_dataset(min_rating=3)

# 保存为 HuggingFace 格式
exporter.save_huggingface_format(items, Path("data/dpo"))
```

### 2. 导出增量数据

```python
# 只导出 2026-04-01 后的新反馈
new_items = exporter.export_incremental(since="2026-04-01")

# 合并到现有数据集
exporter.save_jsonl(new_items, Path("data/dpo/incremental.jsonl"))
```

### 3. 验证数据质量

```python
from finer.ml import validate_dpo_data

item = {
    "prompt": "...",
    "chosen": '{"ticker": "AAPL", ...}',
    "rejected": '{"ticker": "AAPL", ...}'
}

is_valid, error = validate_dpo_data(item)
if not is_valid:
    print(f"Validation failed: {error}")
```

### 4. 启动训练

```bash
# 使用 HuggingFace TRL
python -m finer.ml.train_dpo \
    --data_dir ./data/dpo \
    --output_dir ./models/dpo_finetuned \
    --beta 0.01 \
    --lr 5e-7
```

## 训练脚本

完整的训练脚本已集成在 `DPO_TRAIN_SCRIPT` 常量中，使用方法：

```python
from finer.ml.dpo_trainer import DPO_TRAIN_SCRIPT

# 保存脚本
Path("scripts/train_dpo.py").write_text(DPO_TRAIN_SCRIPT)
```

## 数据统计

导出后查看数据集统计：

```python
stats = exporter.compute_stats(items)
print(f"总样本数: {stats.total_items}")
print(f"唯一标的: {stats.unique_tickers}")
print(f"平均评分: {stats.avg_rating:.2f}")
print(f"评分分布: {stats.rating_distribution}")
```

## 与现有系统集成

### 数据流

```
RLHF 反馈 (data/rlhf/feedbacks/*.json)
    ↓
DPOExporter.export_dataset()
    ↓
DPO Training Items (prompt, chosen, rejected)
    ↓
save_huggingface_format()
    ↓
HuggingFace DPO Trainer
```

### API 端点

现有的 `/api/rlhf/export` 端点提供基础的 DPO 导出功能，`DPOExporter` 提供更完整的：

- 增量导出
- 数据验证
- 统计计算
- HuggingFace 格式输出

## 最佳实践

1. **数据质量优先**
   - 只使用 rating >= 3 的反馈
   - 确保 chosen 和 rejected 有明确差异
   - 验证 JSON 格式正确性

2. **增量训练**
   - 定期导出新反馈（如每周）
   - 合并到训练集后重新微调
   - 监控验证集性能

3. **超参数调优**
   - beta: 0.01 → 0.05 → 0.1 逐步尝试
   - learning_rate: 5e-7 → 1e-6 → 5e-6
   - 观察训练 loss 和验证集性能

4. **评估指标**
   - 结构化输出准确率（字段正确性）
   - 实体提取 F1 分数
   - 方向预测准确率
