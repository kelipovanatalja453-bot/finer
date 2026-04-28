# DPO 训练数据示例

## 示例 1：标的识别错误

**场景**：模型错误识别了交易标的

### 原文
```
特斯拉在 480 美元附近获得支撑，技术指标显示超卖，建议在 475-485 区间分批建仓，
目标价 550 美元，止损 450 美元。时间周期 2-4 周。
```

### DPO 数据

```json
{
  "prompt": "从以下文本提取 Trade Action:\n\n## 原文\n特斯拉在 480 美元附近获得支撑，技术指标显示超卖，建议在 475-485 区间分批建仓，目标价 550 美元，止损 450 美元。时间周期 2-4 周。\n\n## 提取要求\n1. 准确识别交易标的（ticker）\n2. 判断整体方向：bullish（看多）/ bearish（看空）/ neutral（中性）/ watchlist（观望）/ risk_warning（风险警示）\n3. 提取动作链（action_chain），每个动作包含：\n   - action_type: long/short/close_long/close_short/buy_call/sell_call/buy_put/sell_put/hold/watch/buy_and_hold\n   - instrument_type: stock/option/etf/index_future/unspecified\n   - trigger_condition: 触发条件（自然语言或数值）\n   - target_price_low/target_price_high: 目标价格区间\n   - sequence_order: 执行顺序\n4. 判断时间周期（time_horizon）\n5. 给出提取置信度（0-1）\n\n## 输出格式\n严格按照以下 JSON Schema 输出...",
  "chosen": {
    "ticker": "TSLA",
    "direction": "bullish",
    "action_chain": [
      {
        "action_type": "long",
        "instrument_type": "stock",
        "trigger_condition": "price at 475-485 support zone",
        "target_price_low": 475,
        "target_price_high": 485,
        "sequence_order": 1,
        "confidence": 0.9
      }
    ],
    "time_horizon": "2-4 weeks",
    "rationale": "Technical support at 480, oversold indicators suggest long entry"
  },
  "rejected": {
    "ticker": "特斯拉",
    "direction": "bullish",
    "action_chain": [
      {
        "action_type": "buy_and_hold",
        "instrument_type": "stock",
        "sequence_order": 1,
        "confidence": 0.7
      }
    ],
    "time_horizon": "2-4 weeks"
  }
}
```

**学习点**：
- ticker 必须标准化为英文代码（TSLA 而非特斯拉）
- 目标价格区间需要从原文准确提取
- trigger_condition 应该是可执行的条件

---

## 示例 2：方向判断错误

**场景**：模型误判了市场方向

### 原文
```
NVDA 在 900 美元遇到强阻力，RSI 超买，建议观望或轻仓做空，等待回调至 800 美元支撑位。
如果跌破 800，可能进一步下探至 720。
```

### DPO 数据

```json
{
  "prompt": "从以下文本提取 Trade Action:\n\n## 原文\nNVDA 在 900 美元遇到强阻力，RSI 超买，建议观望或轻仓做空，等待回调至 800 美元支撑位。如果跌破 800，可能进一步下探至 720。\n\n## 提取要求\n...",
  "chosen": {
    "ticker": "NVDA",
    "direction": "bearish",
    "action_chain": [
      {
        "action_type": "watch",
        "instrument_type": "stock",
        "trigger_condition": "waiting for pullback to 800 support",
        "sequence_order": 1,
        "confidence": 0.8
      },
      {
        "action_type": "short",
        "instrument_type": "stock",
        "trigger_condition": "break below 800",
        "target_price_low": 720,
        "target_price_high": 800,
        "sequence_order": 2,
        "confidence": 0.75
      }
    ],
    "time_horizon": "short term",
    "rationale": "Overbought RSI, resistance at 900, potential downside to 720"
  },
  "rejected": {
    "ticker": "NVDA",
    "direction": "neutral",
    "action_chain": [
      {
        "action_type": "hold",
        "instrument_type": "stock",
        "sequence_order": 1,
        "confidence": 0.6
      }
    ]
  }
}
```

**学习点**：
- "做空"明确表示 bearish 方向，而非 neutral
- 多步动作链需要按 sequence_order 排序
- 条件触发的动作应该明确 trigger_condition

---

## 示例 3：期权策略识别

**场景**：涉及期权策略的复杂动作

### 原文
```
AAPL 财报前 IV 较高，建议卖出 150 美元行权价的看涨期权收取权利金，
同时买入 145 美元看跌期权对冲下行风险。财报后 IV crush 可能带来收益。
```

### DPO 数据

```json
{
  "prompt": "从以下文本提取 Trade Action:\n\n## 原文\nAAPL 财报前 IV 较高，建议卖出 150 美元行权价的看涨期权收取权利金，同时买入 145 美元看跌期权对冲下行风险。财报后 IV crush 可能带来收益。\n\n## 提取要求\n...",
  "chosen": {
    "ticker": "AAPL",
    "direction": "neutral",
    "action_chain": [
      {
        "action_type": "sell_call",
        "instrument_type": "option",
        "trigger_condition": "pre-earnings high IV",
        "target_price_low": 150,
        "target_price_high": 150,
        "sequence_order": 1,
        "confidence": 0.85
      },
      {
        "action_type": "buy_put",
        "instrument_type": "option",
        "trigger_condition": "downside hedge",
        "target_price_low": 145,
        "target_price_high": 145,
        "sequence_order": 2,
        "confidence": 0.85
      }
    ],
    "time_horizon": "earnings event",
    "rationale": "IV crush strategy with downside hedge"
  },
  "rejected": {
    "ticker": "AAPL",
    "direction": "bullish",
    "action_chain": [
      {
        "action_type": "sell_call",
        "instrument_type": "stock",
        "sequence_order": 1
      }
    ]
  }
}
```

**学习点**：
- instrument_type 应正确识别为 option
- 卖出看涨期权不代表 bullish，此处是波动率策略
- 目标价格应填写行权价

---

## 示例 4：止损设置

**场景**：提取止损条件

### 原文
```
AMD 在 120 美元附近形成双底，突破 130 确认后可做多，目标 150，
止损设在 115 下方。突破确认需要放量。
```

### DPO 数据

```json
{
  "prompt": "从以下文本提取 Trade Action:\n\n## 原文\nAMD 在 120 美元附近形成双底，突破 130 确认后可做多，目标 150，止损设在 115 下方。突破确认需要放量。\n\n## 提取要求\n...",
  "chosen": {
    "ticker": "AMD",
    "direction": "bullish",
    "action_chain": [
      {
        "action_type": "watch",
        "instrument_type": "stock",
        "trigger_condition": "waiting for breakout confirmation at 130 with volume",
        "sequence_order": 1,
        "confidence": 0.7
      },
      {
        "action_type": "long",
        "instrument_type": "stock",
        "trigger_condition": "breakout above 130 with volume",
        "target_price_low": 130,
        "target_price_high": 150,
        "sequence_order": 2,
        "confidence": 0.8
      },
      {
        "action_type": "close_long",
        "instrument_type": "stock",
        "trigger_condition": "stop loss at 115",
        "target_price_low": 115,
        "target_price_high": 115,
        "sequence_order": 3,
        "confidence": 0.9
      }
    ],
    "time_horizon": "medium term",
    "rationale": "Double bottom pattern, breakout entry with stop loss"
  },
  "rejected": {
    "ticker": "AMD",
    "direction": "bullish",
    "action_chain": [
      {
        "action_type": "long",
        "target_price_high": 150
      }
    ]
  }
}
```

**学习点**：
- 止损条件应该作为 close_long 动作
- 多条件触发需要拆分为多个 action
- trigger_condition 应包含"放量"等确认条件

---

## 数据质量检查清单

### 必须满足

- [ ] `ticker` 是标准化英文代码（如 AAPL, TSLA, NVDA）
- [ ] `direction` 是五个选项之一：bullish/bearish/neutral/watchlist/risk_warning
- [ ] `action_type` 是有效动作类型
- [ ] `chosen` 与 `rejected` 有明确差异（至少一个字段不同）
- [ ] `chosen` 是有效 JSON

### 建议满足

- [ ] `time_horizon` 已提取
- [ ] `rationale` 提供了解释
- [ ] `confidence` 在 0-1 范围内
- [ ] `trigger_condition` 具体可执行
- [ ] 价格数值正确（无单位错误）

### 常见问题

| 问题 | 示例 | 修正 |
|------|------|------|
| Ticker 未标准化 | "特斯拉" | → "TSLA" |
| 方向错误 | 看空却标 bullish | → bearish |
| 缺少触发条件 | 无 trigger_condition | → 添加 "price < 480" |
| 价格单位错误 | 48000（分） | → 480 |
| 动作链顺序错乱 | sequence_order 不连续 | → 重新编号 |
