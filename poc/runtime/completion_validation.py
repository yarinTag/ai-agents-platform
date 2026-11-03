"""Bounded connector completion recovery; never executes a connector or RPC."""
import hashlib
import json
import os
import re
from .direct_outcomes import WorkflowOutcome, OutcomeFormatError, parse_outcome, outcome_result

FINISH_NAME = 'platform_workflow_finish'
FINISH_TOOL = {'name': FINISH_NAME,
    'description': 'Submit the final workflow outcome after all required work. This only validates the answer; '
        'it does not run external actions. Use blocked for missing input, capability or permissions. '
        'Call it alone, never alongside another tool.',
    'input_schema': WorkflowOutcome.model_json_schema()}
FINISH_PROMPT = ('\nWhen finished, submit status, output and blocker using platform_workflow_finish. '
    'This is the server completion contract, not a connector action. Call it alone. '
    'Set blocker=null only for completed work supported by successful tool results.')
REPAIR_PROMPT = ('The previous final response did not match the server completion contract. '
    'This is one formatting-only pass. Do not repeat any operation or request connector tools. '
    'Use only the work and results already present in this conversation. '
    'Submit platform_workflow_finish with status completed or blocked, output containing the full answer, '
    'and blocker=null or the blocker reason. Preserve missing information and limitations; '
    'do not turn blocked work into success or invent results. If uncertain, report blocked.')


def tool_input(name, arguments):
    # Preserve completion JSON verbatim for duplicate-key/schema validation.
    # Other tools retain their existing parsed-input contract.
    return arguments if name == FINISH_NAME else json.loads(arguments)


def redact_candidate(text):
    """Best-effort diagnostic redaction, not a claim to detect every possible secret."""
    values = [value for key, value in os.environ.items() if len(value) >= 4 and
              re.search(r'(SECRET|TOKEN|PASSWORD|PASSWD|API_?KEY|CREDENTIAL|SIGNING|_DSN$)', key, re.I)]
    for value in sorted(values, key=len, reverse=True):
        text = text.replace(value, '[REDACTED]')
    text = re.sub(r'(?i)\bBearer\s+[^\s"\x27,;]+', 'Bearer [REDACTED]', text)
    text = re.sub(r'(?i)(["\x27]?(?:api[_-]?key|access[_-]?token|token|password|secret|authorization|encrypted_content|signature)["\x27]?\s*[:=]\s*)'
                  r'(?:"[^"\n]*"|\x27[^\x27\n]*\x27|[^\s,;}]+)', r'\1[REDACTED]', text)
    text = re.sub(r'https?://[^/\s:@]+:[^@\s]+@', 'https://[REDACTED]@', text)
    text = re.sub(r'\b\d{6,12}:[A-Za-z0-9_-]{20,}\b', '[REDACTED]', text)
    text = re.sub(r'\b(?:sk-|nvapi-|ghp_|github_pat_|xox[baprs]-)[A-Za-z0-9_-]{8,}', '[REDACTED]', text)
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)


def rejection_event(candidate, error, attempt):
    raw = candidate if isinstance(candidate, str) else json.dumps(candidate, ensure_ascii=False)
    # Never include the response object, encrypted continuation or HTTP metadata.
    safe = redact_candidate(raw)
    return {'type': 'completion_validation', 'status': 'rejected',
        'error_code': getattr(error, 'code', 'INVALID_COMPLETION'), 'message': str(error),
        'attempt': attempt, 'candidate_preview': safe[:4000],
        'candidate_truncated': len(safe) > 4000, 'candidate_characters': len(raw),
        'candidate_sha256': hashlib.sha256(raw.encode()).hexdigest()}


class ConnectorFinalizer:
    """Only one bounded formatting pass, within the worker's existing call limit."""
    def __init__(self):
        self.formatting_only = False
        self.diagnostic = None

    def inventory(self, connector_tools):
        return [FINISH_TOOL] if self.formatting_only else [*connector_tools, FINISH_TOOL]

    def inspect(self, response):
        self.diagnostic = None
        calls = response['calls']
        finish = [call for call in calls if call['name'] == FINISH_NAME]
        if calls and not finish and not self.formatting_only:
            return 'tools', None
        candidate = response['text']
        try:
            if calls:
                if len(calls) != 1 or not finish:
                    raise OutcomeFormatError('MIXED_FINALIZATION', 'Finalization must be separate from connector calls.')
                candidate = finish[0]['input']
            value = parse_outcome(candidate)
        except OutcomeFormatError as exc:
            self.diagnostic = rejection_event(candidate, exc, 2 if self.formatting_only else 1)
            self.diagnostic['recovery_action'] = ('fail_closed' if self.formatting_only or exc.code == 'MIXED_FINALIZATION' else 'formatting_only')
            if self.formatting_only or exc.code == 'MIXED_FINALIZATION':
                return 'failed', str(exc)
            self.formatting_only = True
            return 'repair', str(exc)
        output, blocker = outcome_result(value)
        if blocker is not None:
            return 'blocked', redact_candidate(blocker)
        return 'completed', output
