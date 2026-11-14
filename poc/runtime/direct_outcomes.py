"""Explicit final outcome contract for governed connector runs."""
import json
import re
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class WorkflowOutcome(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    status: Literal['completed', 'blocked']
    output: str = Field(min_length=1, max_length=60000)
    blocker: Optional[str] = Field(max_length=8000)


class PullRequestOutcome(WorkflowOutcome):
    eligible_pull_numbers: list[int] = Field(max_length=10)


class OutcomeFormatError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate object key')
        result[key] = value
    return result


def parse_outcome(value, schema=WorkflowOutcome):
    """Accept a typed tool input or one whole JSON document, optionally fenced.

    Never search prose for a convenient embedded completed object.
    """
    if isinstance(value, str):
        text = value.strip()
        fence = re.fullmatch(r'```(?:json)?[ \t]*\r?\n(.*?)\r?\n```', text, re.DOTALL | re.IGNORECASE)
        if fence:
            text = fence.group(1)
        try:
            value = json.loads(text, object_pairs_hook=_unique_keys)
        except (ValueError, TypeError):
            raise OutcomeFormatError('INVALID_JSON', 'The model did not return a verifiable completion status.') from None
    try:
        parsed = schema.model_validate(value)
    except ValidationError:
        raise OutcomeFormatError('INVALID_ENVELOPE', 'The model did not return the required status, output and blocker fields.') from None
    if not parsed.output.strip():
        raise OutcomeFormatError('EMPTY_OUTPUT', 'The model returned no task output.')
    return parsed

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
        value = parse_outcome(text)
    except OutcomeFormatError as exc:
        return None, str(exc)
    return outcome_result(value)


def outcome_result(value):
    if value.status == 'blocked':
        return None, str((value.blocker or '').strip() or value.output)[:8000]
    if value.blocker is not None:
        return None, value.blocker.strip() or 'The model returned a non-null blocker; completion is not permitted.'
    return value.output, None
