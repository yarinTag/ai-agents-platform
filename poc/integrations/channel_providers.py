"""Trusted registry adapters for configured channel identifiers."""
from dataclasses import dataclass
import re
from typing import Callable

from .tool_definitions import resource_values, valid_channel


@dataclass(frozen=True)
class ChannelProvider:
    label: str
    valid_id: Callable[[str], bool]
    runtime_supported_uses: tuple[str, ...] = ("send_notifications",)

    def configured_ids(self, configuration: dict) -> list[str]:
        return [value for value in resource_values(configuration, "channels")
                if self.valid_id(value)]


def telegram_id(channel_id: str) -> bool:
    # Usernames can be reassigned. Only numeric identities enter the registry.
    return bool(re.fullmatch(r"-?[1-9][0-9]{0,19}", channel_id))


CHANNEL_PROVIDERS = {
    "telegram": ChannelProvider("Telegram", telegram_id),
    "slack": ChannelProvider("Slack", lambda channel_id: valid_channel("slack", channel_id)),
}
