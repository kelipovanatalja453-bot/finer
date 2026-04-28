#!/usr/bin/env python3
"""验证 Schema 统一后的导入和类型兼容性"""

import sys

def test_import():
    """测试基本导入"""
    try:
        from finer.schemas.event import TradingAction
        from finer.schemas.trade_action import ActionStep, ActionType
        print("✓ Import successful")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False

def test_trading_action_creation():
    """测试 TradingAction 创建"""
    try:
        from finer.schemas.event import TradingAction
        from finer.schemas.trade_action import ActionType

        # 测试新方式（使用 action_type 枚举）
        ta1 = TradingAction(
            action_type=ActionType.LONG,
            instrument_type="stock",
            confidence=0.9,
        )
        print(f"✓ TradingAction created with ActionType enum: sequence={ta1.sequence}, sequence_order={ta1.sequence_order}")

        # 测试旧方式（使用 sequence_order）
        ta2 = TradingAction(
            action_type=ActionType.WATCH,
            sequence_order=2,  # 旧字段名
            confidence=0.8,
        )
        print(f"✓ TradingAction created with sequence_order alias: sequence={ta2.sequence}, sequence_order={ta2.sequence_order}")

        # 测试 sequence 属性访问
        assert ta2.sequence == 2, f"Expected sequence=2, got {ta2.sequence}"
        assert ta2.sequence_order == 2, f"Expected sequence_order=2, got {ta2.sequence_order}"
        print("✓ sequence/sequence_order compatibility verified")

        return True
    except Exception as e:
        print(f"✗ TradingAction creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_conversion():
    """测试 TradingAction <-> ActionStep 转换"""
    try:
        from finer.schemas.event import TradingAction
        from finer.schemas.trade_action import ActionStep, ActionType

        # TradingAction -> ActionStep
        ta = TradingAction(
            action_type=ActionType.LONG,
            trigger_condition="price < 480",
            confidence=0.9,
            instrument_type="stock",
        )
        step = ta.to_action_step()
        print(f"✓ TradingAction.to_action_step(): {step.action_type}")

        # ActionStep -> TradingAction
        step2 = ActionStep(
            sequence=1,
            action_type=ActionType.SHORT,
            trigger_condition="breakout",
        )
        ta2 = TradingAction.from_action_step(step2, confidence=0.85, instrument_type="etf")
        print(f"✓ TradingAction.from_action_step(): {ta2.action_type}, confidence={ta2.confidence}")

        return True
    except Exception as e:
        print(f"✗ Conversion failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_event_with_actions():
    """测试 EventWithActions 中的 action_chain"""
    try:
        from finer.schemas.event import EventWithActions, TradingAction
        from finer.schemas.trade_action import ActionType

        event = EventWithActions(
            ticker="AAPL",
            direction="bullish",
            evidence_text="Apple looks strong",
            action_chain=[
                TradingAction(action_type=ActionType.WATCH, sequence=1, confidence=0.9),
                TradingAction(action_type=ActionType.LONG, sequence=2, trigger_condition="breakout", confidence=0.8),
            ]
        )
        print(f"✓ EventWithActions created with {len(event.action_chain)} actions")
        print(f"  - action 1: {event.action_chain[0].action_type}, sequence_order={event.action_chain[0].sequence_order}")
        print(f"  - action 2: {event.action_chain[1].action_type}, sequence={event.action_chain[1].sequence}")

        return True
    except Exception as e:
        print(f"✗ EventWithActions failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=" * 60)
    print("Schema Unification Verification")
    print("=" * 60)

    tests = [
        ("Import", test_import),
        ("TradingAction Creation", test_trading_action_creation),
        ("Conversion", test_conversion),
        ("EventWithActions", test_event_with_actions),
    ]

    results = []
    for name, test_fn in tests:
        print(f"\n{name}:")
        ok = test_fn()
        results.append((name, ok))

    print("\n" + "=" * 60)
    print("Summary:")
    all_ok = True
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        print(f"  {status}: {name}")
        if not ok:
            all_ok = False

    if all_ok:
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
