#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/zhouhongyuan/Desktop/finer/src')

# Test 1: Basic import
try:
    from finer.schemas.event import TradingAction
    from finer.schemas.trade_action import ActionStep, ActionType
    print("PASS: Import successful")
except Exception as e:
    print(f"FAIL: Import failed: {e}")
    sys.exit(1)

# Test 2: Create TradingAction
try:
    ta = TradingAction(
        action_type=ActionType.LONG,
        confidence=0.9,
    )
    print(f"PASS: TradingAction created, sequence={ta.sequence}, sequence_order={ta.sequence_order}")
except Exception as e:
    print(f"FAIL: TradingAction creation: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Backward compat with sequence_order
try:
    ta2 = TradingAction(
        action_type=ActionType.WATCH,
        sequence_order=3,
        confidence=0.8,
    )
    assert ta2.sequence == 3, f"Expected sequence=3, got {ta2.sequence}"
    print(f"PASS: sequence_order alias works, sequence={ta2.sequence}")
except Exception as e:
    print(f"FAIL: sequence_order alias: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Conversion
try:
    step = ta.to_action_step()
    ta3 = TradingAction.from_action_step(step, confidence=0.95)
    print(f"PASS: Conversion works")
except Exception as e:
    print(f"FAIL: Conversion: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nAll tests passed!")
