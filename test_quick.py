#!/usr/bin/env python3
"""简化版验证脚本"""
import sys
sys.path.insert(0, '/Users/zhouhongyuan/Desktop/finer/src')

print("Testing schema unification...")

# Test 1: Import
try:
    from finer.schemas.event import TradingAction
    from finer.schemas.trade_action import ActionStep, ActionType
    print("OK: Import successful")
except Exception as e:
    print(f"FAILED: Import error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: Create with ActionType enum
try:
    ta = TradingAction(action_type=ActionType.LONG, confidence=0.9)
    print(f"OK: Created TradingAction, sequence={ta.sequence}")
except Exception as e:
    print(f"FAILED: Creation: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Backward compat
try:
    ta2 = TradingAction(action_type=ActionType.WATCH, sequence_order=3)
    assert ta2.sequence == 3
    print(f"OK: sequence_order alias works (sequence={ta2.sequence})")
except Exception as e:
    print(f"FAILED: Backward compat: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Conversion
try:
    step = ta.to_action_step()
    ta3 = TradingAction.from_action_step(step, confidence=0.95)
    print(f"OK: Conversion works")
except Exception as e:
    print(f"FAILED: Conversion: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nAll tests passed!")
