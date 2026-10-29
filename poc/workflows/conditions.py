"""Pure workflow trigger condition evaluation."""
import re
from typing import Dict, Any

def evaluate_condition_rule(rule: Dict[str, Any], payload: Dict[str, Any]) -> bool:
    """Evaluate a single rule against a nested payload using dot notation."""
    field_path = rule.get("field", "")
    operator = rule.get("operator", "equals").lower()
    target_value = rule.get("value")

    curr = payload
    for part in field_path.split("."):
        if isinstance(curr, dict) and part in curr:
            curr = curr[part]
        else:
            curr = None
            break

    if curr is None:
        return False

    str_curr = str(curr)
    str_target = str(target_value)

    if operator in ("matches", "regex"):
        return bool(re.search(str_target, str_curr))
    elif operator in ("equals", "eq", "=="):
        return str_curr == str_target
    elif operator in ("not_equals", "ne", "!="):
        return str_curr != str_target
    elif operator in ("contains", "has"):
        return str_target in str_curr
    elif operator == "in":
        if isinstance(target_value, (list, tuple)):
            return curr in target_value
        return str_curr in str_target
    return False


def evaluate_trigger_conditions(trigger: Dict[str, Any], payload: Dict[str, Any]) -> bool:
    """Evaluate full trigger conditions with combinator 'and'/'or'."""
    conds = trigger.get("conditions")
    if not conds:
        return True
    combinator = conds.get("combinator", "and").lower()
    rules = conds.get("rules", [])
    if not rules:
        return True

    results = [evaluate_condition_rule(r, payload) for r in rules]
    if combinator == "or":
        return any(results)
    return all(results)

