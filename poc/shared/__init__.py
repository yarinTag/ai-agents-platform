"""
Shared Platform Utilities & Cross-Service Primitives.
Follows the Rule of 2: any logic used by two or more services lives here.
"""

from .validators import (
    normalize_email,
    validate_email_domain,
    parse_allowed_tools,
    slugify_identifier,
)
from .notifications import (
    dispatch_channel_message,
    dispatch_workflow_completion_notification,
    resolve_telegram_target_chat,
)
from .service_registry import (
    ServiceRegistry,
    ServiceSpec,
    ServiceStatusRecord,
    service_registry,
)
from .envelope_crypto import (
    EnvelopeCryptoManager,
    encrypt_secret_config,
    decrypt_secret_config,
    hash_invite_token,
)
from .payload_sanitizer import (
    sanitize_trigger_payload,
    wrap_untrusted_content,
    verify_webhook_hmac,
)

__all__ = [
    "normalize_email",
    "validate_email_domain",
    "parse_allowed_tools",
    "slugify_identifier",
    "dispatch_channel_message",
    "dispatch_workflow_completion_notification",
    "resolve_telegram_target_chat",
    "ServiceRegistry",
    "ServiceSpec",
    "ServiceStatusRecord",
    "service_registry",
    "EnvelopeCryptoManager",
    "encrypt_secret_config",
    "decrypt_secret_config",
    "hash_invite_token",
    "sanitize_trigger_payload",
    "wrap_untrusted_content",
    "verify_webhook_hmac",
]
