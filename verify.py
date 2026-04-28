#!/usr/bin/env python3
"""验证 Schema 统一 - TradingAction 和 ActionStep 双向转换"""
import sys
sys.path.insert(0, '/Users/zhouhongyuan/Desktop/finer/src')

print("=" * 60)
print("Schema Unification Verification")
print("=" * 60)

# Test 1: Import
try:
    from finer.schemas.event import TradingAction
    from finer.schemas.trade_action import ActionStep, ActionType
    print("\n[PASS] Import successful")
except Exception as e:
    print(f"\n[FAIL] Import error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: Create TradingAction with string action_type
try:
    ta = TradingAction(action_type="long", confidence=0.9, sequence_order=1)
    assert ta.action_type == "long"
    assert ta.sequence_order == 1
    print(f"[PASS] TradingAction created: action_type={ta.action_type}, sequence_order={ta.sequence_order}")
except Exception as e:
    print(f"[FAIL] TradingAction creation: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Create with multiple actions
try:
    ta2 = TradingAction(
        action_type="watch",
        trigger_condition="price < 480",
        target_price_low=450.0,
        target_price_high=480.0,
        sequence_order=2,
        confidence=0.85
    )
    print(f"[PASS] Complex TradingAction: trigger={ta2.trigger_condition}")
except Exception as e:
    print(f"[FAIL] Complex creation: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Convert TradingAction -> ActionStep
try:
    step = ta.to_action_step()
    assert step.sequence == 1
    assert step.action_type == ActionType.LONG
    print(f"[PASS] TradingAction.to_action_step(): sequence={step.sequence}, action_type={step.action_type}")
except Exception as e:
    print(f"[FAIL] to_action_step: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Convert ActionStep -> TradingAction
try:
    step2 = ActionStep(
        sequence=3,
        action_type=ActionType.SHORT,
        trigger_condition="breakout"
    )
    ta3 = TradingAction.from_action_step(step2, confidence=0.75, instrument_type="etf")
    assert ta3.action_type == "short"
    assert ta3.sequence_order == 3
    assert ta3.instrument_type == "etf"
    print(f"[PASS] TradingAction.from_action_step(): action_type={ta3.action_type}, sequence_order={ta3.sequence_order}")
except Exception as e:
    print(f"[FAIL] from_action_step: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 6: EventWithActions compatibility
try:
    from finer.schemas.event import EventWithActions
    event = EventWithActions(
        ticker="AAPL",
        direction="bullish",
        evidence_text="Apple showing strength",
        action_chain=[
            TradingAction(action_type="watch", sequence_order=1, confidence=0.9),
            TradingAction(action_type="long", sequence_order=2, trigger_condition="breakout", confidence=0.8),
        ]
    )
    assert len(event.action_chain) == 2
    print(f"[PASS] EventWithActions with {len(event.action_chain)} actions")
except Exception as e:
    print(f"[FAIL] EventWithActions: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("All tests passed!")
print("=" * 60)
