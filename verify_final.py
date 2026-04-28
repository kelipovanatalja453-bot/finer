#!/usr/bin/env python3
"""验证 Schema 统一后的导入和转换"""
import sys
sys.path.insert(0, '/Users/zhouhongyuan/Desktop/finer/src')

print("=" * 60)
print("Schema Unification Verification")
print("=" * 60)

# Test 1: Import
try:
    from finer.schemas.event import TradingAction, ACTION_TYPE_LITERAL
    from finer.schemas.trade_action import ActionStep, ActionType
    print("\n[PASS] Import successful")
except Exception as e:
    print(f"\n[FAIL] Import error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: Create TradingAction
try:
    ta = TradingAction(action_type="long", confidence=0.9, sequence_order=1)
    assert ta.action_type == "long"
    assert ta.sequence_order == 1
    print(f"[PASS] TradingAction: action_type={ta.action_type}, seq={ta.sequence_order}")
except Exception as e:
    print(f"[FAIL] Creation: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Convert TradingAction -> ActionStep
try:
    step = ta.to_action_step()
    assert step.sequence == 1
    assert step.action_type == ActionType.LONG
    print(f"[PASS] to_action_step: seq={step.sequence}, type={step.action_type}")
except Exception as e:
    print(f"[FAIL] to_action_step: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Convert ActionStep -> TradingAction
try:
    step2 = ActionStep(sequence=3, action_type=ActionType.SHORT, trigger_condition="breakout")
    ta2 = TradingAction.from_action_step(step2, confidence=0.75, instrument_type="etf")
    assert ta2.action_type == "short"
    assert ta2.sequence_order == 3
    print(f"[PASS] from_action_step: type={ta2.action_type}, seq={ta2.sequence_order}")
except Exception as e:
    print(f"[FAIL] from_action_step: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: EventWithActions
try:
    from finer.schemas.event import EventWithActions
    event = EventWithActions(
        ticker="AAPL",
        direction="bullish",
        evidence_text="Strong momentum",
        action_chain=[
            TradingAction(action_type="watch", sequence_order=1),
            TradingAction(action_type="long", sequence_order=2, trigger_condition="break"),
        ]
    )
    assert len(event.action_chain) == 2
    print(f"[PASS] EventWithActions: {len(event.action_chain)} actions")
except Exception as e:
    print(f"[FAIL] EventWithActions: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("All tests passed!")
print("=" * 60)