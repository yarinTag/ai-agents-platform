"""Explicit final outcome contract for governed connector runs."""
import json

OUTCOME_PROMPT = '''
For your final answer, return exactly one JSON object with these fields:
{"status":"completed" or "blocked", "output":"human-readable answer", "blocker":null or "reason"}.
Use blocked if any requested deliverable cannot be produced, a required capability
is unavailable, or you need additional permissions/input. Reading repository
activity is not completion of a request to change code or open a pull request.
Never claim a branch, commit, pull request or delivery exists without a real tool
receipt. Do not ask the user to retry inside a completed result. Keep using tools
normally until you can produce this final outcome. Do not wrap JSON in markdown.
'''


def final_outcome(text):
    try:
        value = json.loads(text)
    except (ValueError, TypeError):
        return None, 'The model did not return a verifiable completion status.'
    if not isinstance(value, dict) or value.get('status') not in ('completed', 'blocked'):
        return None, 'The model did not return a verifiable completion status.'
    output, blocker = value.get('output'), value.get('blocker')
    if not isinstance(output, str) or not output.strip():
        return None, 'The model returned no task output.'
    if value['status'] == 'blocked' or blocker:
        return None, str(blocker or output)[:8000]
    return output, None
