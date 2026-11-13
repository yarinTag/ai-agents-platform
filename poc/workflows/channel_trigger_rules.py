"""Pure validation and matching shared by channel dispatch and preview."""
import re
import unicodedata
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_TEXT = 2048
InputField = Literal["channel_id", "event_type", "message_id", "sender_id", "text"]
Matcher = Literal["event_type", "command", "mention", "keyword", "regex"]
Parameter = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")]
_EVENT_TYPE = re.compile(r"[A-Z][A-Z0-9_]{0,63}")
_COMMAND = re.compile(r"/[A-Za-z][A-Za-z0-9_-]{0,63}")
_MENTION = re.compile(r"(?:@[A-Za-z][A-Za-z0-9_]{0,63}|<@[A-Z0-9]{2,32}>)")
# Flat regex subset: escaped metacharacters, literals, dot, and edge anchors.
# No quantifiers, alternation, groups, character classes or backreferences.
_REGEX = re.compile(r"\^?(?:\\[.\\^$]|[^\\^$*+?{}()\[\]|\r\n])+\$?")


def sanitize_text(value: str) -> str:
    """Bound text before matching or passing it through the data projection."""
    return "".join(
        char for char in value[:MAX_TEXT]
        if char in "\n\t" or unicodedata.category(char) not in {"Cc", "Cf", "Cs"}
    )


class TriggerRule(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    binding_id: Annotated[str, Field(pattern=r"^chb_[a-f0-9]{32}$")]
    enabled: bool = False
    matcher: Matcher
    pattern: Annotated[str, Field(min_length=1, max_length=160)]
    parameters: dict[Parameter, InputField] = Field(default_factory=dict, max_length=16)

    @model_validator(mode="after")
    def validate_pattern(self):
        validators = {
            "event_type": _EVENT_TYPE,
            "command": _COMMAND,
            "mention": _MENTION,
            "regex": _REGEX,
        }
        validator = validators.get(self.matcher)
        if self.pattern != sanitize_text(self.pattern) or (validator and not validator.fullmatch(self.pattern)):
            raise ValueError("Invalid trigger pattern for the selected matcher.")
        if not self.pattern.strip():
            raise ValueError("Trigger pattern cannot be blank.")
        return self


class ChannelTriggerInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    event_type: Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{0,63}$")]
    channel_id: Annotated[str, Field(min_length=1, max_length=150)]
    message_id: Annotated[str, Field(min_length=1, max_length=150)]
    sender_id: Annotated[str, Field(min_length=1, max_length=150)] | None = None
    text: Annotated[str, Field(max_length=MAX_TEXT)] = ""


def match_trigger(rule: TriggerRule, event: ChannelTriggerInput) -> dict[str, str | None] | None:
    """Return only allowlisted mapped values. None means no match."""
    text = sanitize_text(event.text)
    pattern = rule.pattern
    if rule.matcher == "event_type":
        matches = event.event_type == pattern
    elif rule.matcher in ("command", "mention"):
        tokens = text.split(maxsplit=1)
        matches = bool(tokens and tokens[0] == pattern)
    elif rule.matcher == "keyword":
        matches = pattern.casefold() in text.casefold()
    else:
        matches = re.search(pattern, text) is not None
    if not matches:
        return None
    values = event.model_dump()
    values["text"] = text
    return {name: values[field] for name, field in rule.parameters.items()}
