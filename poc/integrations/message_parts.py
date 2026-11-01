"""Lossless bounded plain-text delivery parts; no Markdown parsing or truncation."""
from .tool_definitions import ToolAccessError

MAX_MESSAGE_CHARACTERS = 60000


def message_parts(text):
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_MESSAGE_CHARACTERS:
        raise ToolAccessError('Delivery requires nonempty text up to 60,000 characters. No text was sent or truncated.')
    remaining = text
    parts = []
    while remaining:
        units = 0
        end = 0
        for char in remaining:
            width = 2 if ord(char) > 0xFFFF else 1
            if units + width > 3450:
                break
            units += width
            end += 1
        if end < len(remaining):
            boundary = max(remaining.rfind('\n', 0, end), remaining.rfind(' ', 0, end))
            if boundary >= end // 2:
                end = boundary + 1
        parts.append(remaining[:end])
        remaining = remaining[end:]
    if len(parts) == 1:
        return parts
    return [f'[{index}/{len(parts)}]\n{part}' for index, part in enumerate(parts, 1)]
