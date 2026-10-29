"""
Enterprise AI Security Firewall & Prompt Injection Guard.

Protects against:
- Direct Prompt Injections (Jailbreaks, System Prompt Overrides, Delimiter Hijacks, Token Leaks)
- Indirect Prompt Injections (Malicious payloads hidden inside MCP tool outputs, web scraping, PRs, tickets)
- Destructive Command Injections (rm -rf, fork bombs, reverse shells, mass drop DB)
- Secret & Exfiltration Links (Markdown image exfiltration, webhook token leakage)

Enforces strict Fail-Closed policy and records immutable security audit logs.
"""

import re
import logging
from typing import Dict, Any, Optional, Tuple, List
from pydantic import BaseModel, Field
from fastapi import HTTPException, status
from datetime import datetime

logger = logging.getLogger(__name__)


class InjectionScanResult(BaseModel):
    is_safe: bool = True
    risk_score: float = 0.0  # 0.0 (clean) to 1.0 (critical attack)
    threat_category: Optional[str] = None
    matched_pattern: Optional[str] = None
    sanitized_text: str = ""
    remediation_action: str = "ALLOW"  # ALLOW, SANITIZE, BLOCK


class PromptInjectionDetectedError(HTTPException):
    """Raised when prompt injection or destructive malicious instruction is blocked."""
    def __init__(self, detail: str, threat_category: str = "PROMPT_INJECTION", risk_score: float = 1.0):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "SECURITY_VIOLATION_BLOCKED",
                "message": detail,
                "threat_category": threat_category,
                "risk_score": risk_score,
                "action": "REQUEST_TERMINATED_AND_LOGGED"
            }
        )


class PromptInjectionFirewall:
    """
    Multi-Layered AI Security Firewall for User Prompts and MCP Tool Outputs.
    """

    # 1. Direct Prompt Injection & Jailbreak Patterns
    JAILBREAK_PATTERNS = [
        (r"(?i)(?:ignore|disregard|forget|override|bypass)\s+(?:all\s+)?(?:previous|prior|above|system)\s+(?:instructions|rules|prompts|directives)", "SYSTEM_OVERRIDE"),
        (r"(?i)(?:you\s+are\s+now|act\s+as|pretend\s+to\s+be)\s+(?:DAN|unfiltered|jailbroken|root|developer\s+mode|chaos\s+gpt)", "JAILBREAK_PERSONA"),
        (r"(?i)new\s+system\s+(?:prompt|instructions?)\s*:\s*", "SYSTEM_PROMPT_INJECTION"),
        (r"(?i)do\s+anything\s+now", "JAILBREAK_PERSONA"),
        (r"(?i)(?:reveal|print|output|display|show|leak|repeat)\s+(?:all\s+)?(?:your\s+)?(?:system\s+prompt|initial\s+prompt|secret\s+instructions|hidden\s+rules)", "SYSTEM_LEAK_ATTEMPT"),
        (r"(?i)repeat\s+everything\s+above\s+(?:verbatim|word\s+for\s+word)", "PROMPT_THEFT"),
    ]

    # 2. Delimiter & Control Token Manipulation
    DELIMITER_PATTERNS = [
        (r"<\|im_start\|>", "CONTROL_TOKEN_HIJACK"),
        (r"<\|im_end\|>", "CONTROL_TOKEN_HIJACK"),
        (r"<\|system\|>", "CONTROL_TOKEN_HIJACK"),
        (r"\[INST\]\s*<<SYS>>", "CONTROL_TOKEN_HIJACK"),
        (r"(?i)---+\s*(?:END|BEGIN)\s+(?:OF\s+)?(?:SYSTEM|PROMPT|INSTRUCTIONS|SYSTEM\s+INSTRUCTIONS)\b\s*---+", "DELIMITER_HIJACK"),
        (r"###\s*System\s*:\s*", "DELIMITER_HIJACK"),
    ]

    # 3. Destructive Command Injections (OS / Bash / Database)
    DESTRUCTIVE_COMMAND_PATTERNS = [
        (r"(?i)\brm\s+-[rRfF]{1,3}\s+(?:/|~|\$HOME|\.\.)", "DESTRUCTIVE_OS_COMMAND"),
        (r"(?i)\b(?:mkfs|fdisk|dd\s+if=/dev/zero)\b", "DESTRUCTIVE_DISK_COMMAND"),
        (r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", "FORK_BOMB_COMMAND"),
        (r"(?i)curl\s+[^\n|]+\|\s*(?:bash|sh|zsh)", "REMOTE_CODE_EXECUTION"),
        (r"(?i)wget\s+[^\n|]+\|\s*(?:bash|sh|zsh)", "REMOTE_CODE_EXECUTION"),
        (r"(?i)(?:nc|ncat|netcat)\s+.*-e\s+/bin/(?:bash|sh)", "REVERSE_SHELL"),
        (r"/dev/tcp/\d+\.\d+\.\d+\.\d+/\d+", "REVERSE_SHELL"),
        (r"(?i)\bDROP\s+DATABASE\b", "DESTRUCTIVE_SQL_COMMAND"),
        (r"(?i)\bDROP\s+TABLE\s+(?:users|organizations|departments|audit_logs|task_runs)\b", "DESTRUCTIVE_SQL_COMMAND"),
    ]

    # 4. Indirect Prompt Injection & Exfiltration (Found in MCP / Web / Ticket outputs)
    INDIRECT_INJECTION_PATTERNS = [
        (r"(?i)<instruction>.*?</instruction>", "XML_EMBEDDED_INSTRUCTION"),
        (r"(?i)<system>.*?</system>", "XML_EMBEDDED_SYSTEM"),
        (r"(?i)\[\s*system_override\s*\]", "INDIRECT_INSTRUCTION_TAG"),
        (r"(?i)!\[.*?\]\(https?://[^\s)]+(?:\?|&)(?:token|key|secret|cookie|auth|pwd)=.*?\)", "MARKDOWN_EXFILTRATION_IMAGE"),
        (r"(?i)<img\s+src=[\"']https?://[^\s\"']+(?:\?|&)(?:token|key|secret|cookie|auth)=.*?[\"']", "HTML_EXFILTRATION_IMAGE"),
    ]

    def scan_text(self, text: Optional[str], source: str = "direct_input") -> InjectionScanResult:
        """
        Scans input string for prompt injection, jailbreaks, or destructive patterns.
        """
        if not text or not isinstance(text, str):
            return InjectionScanResult(is_safe=True, risk_score=0.0, sanitized_text=text or "")

        clean_text = text.strip()

        # Check Direct Jailbreaks
        for pattern, category in self.JAILBREAK_PATTERNS:
            match = re.search(pattern, clean_text)
            if match:
                logger.warning(f"SECURITY ALERT [{source}]: Prompt injection detected ({category}) - Matched: '{match.group(0)}'")
                return InjectionScanResult(
                    is_safe=False,
                    risk_score=0.95,
                    threat_category=category,
                    matched_pattern=match.group(0),
                    sanitized_text=clean_text,
                    remediation_action="BLOCK"
                )

        # Check Delimiter Manipulations
        for pattern, category in self.DELIMITER_PATTERNS:
            match = re.search(pattern, clean_text)
            if match:
                logger.warning(f"SECURITY ALERT [{source}]: Delimiter hijack detected ({category}) - Matched: '{match.group(0)}'")
                return InjectionScanResult(
                    is_safe=False,
                    risk_score=0.90,
                    threat_category=category,
                    matched_pattern=match.group(0),
                    sanitized_text=clean_text,
                    remediation_action="BLOCK"
                )

        # Check Destructive Commands
        for pattern, category in self.DESTRUCTIVE_COMMAND_PATTERNS:
            match = re.search(pattern, clean_text)
            if match:
                logger.error(f"CRITICAL SECURITY ALERT [{source}]: Destructive command injection detected ({category}) - Matched: '{match.group(0)}'")
                return InjectionScanResult(
                    is_safe=False,
                    risk_score=1.0,
                    threat_category=category,
                    matched_pattern=match.group(0),
                    sanitized_text=clean_text,
                    remediation_action="BLOCK"
                )

        # Check Indirect Injections & Exfiltration (especially relevant for tool outputs)
        for pattern, category in self.INDIRECT_INJECTION_PATTERNS:
            match = re.search(pattern, clean_text)
            if match:
                logger.warning(f"SECURITY ALERT [{source}]: Indirect injection / data exfiltration link detected ({category}) - Matched: '{match.group(0)}'")
                return InjectionScanResult(
                    is_safe=False,
                    risk_score=0.88,
                    threat_category=category,
                    matched_pattern=match.group(0),
                    sanitized_text=clean_text,
                    remediation_action="BLOCK"
                )

        return InjectionScanResult(
            is_safe=True,
            risk_score=0.0,
            sanitized_text=clean_text,
            remediation_action="ALLOW"
        )

    def sanitize_mcp_output(self, tool_name: str, raw_output: Any) -> Any:
        """
        Inspects output received from an MCP tool before it is delivered to agent memory.
        Blocks or defangs indirect prompt injections.
        """
        if raw_output is None:
            return raw_output

        text_to_scan = ""
        if isinstance(raw_output, str):
            text_to_scan = raw_output
        elif isinstance(raw_output, dict):
            import json
            text_to_scan = json.dumps(raw_output)
        elif isinstance(raw_output, list):
            import json
            text_to_scan = json.dumps(raw_output)

        scan = self.scan_text(text_to_scan, source=f"mcp_tool:{tool_name}")
        if not scan.is_safe:
            logger.error(
                f"MCP SECURITY FIREWALL: Blocked indirect prompt injection from tool '{tool_name}'! "
                f"Threat: {scan.threat_category}, Matched: {scan.matched_pattern}"
            )
            raise PromptInjectionDetectedError(
                detail=f"Indirect Prompt Injection detected in output of MCP tool '{tool_name}' ({scan.threat_category}). Output blocked.",
                threat_category=scan.threat_category or "INDIRECT_PROMPT_INJECTION",
                risk_score=scan.risk_score
            )

        return raw_output

    def assert_clean_prompt(
        self,
        text: Optional[str],
        source: str = "direct_input",
        db_manager: Optional[Any] = None,
        org_id: Optional[str] = None,
        actor: str = "user"
    ):
        """
        Scans prompt and raises PromptInjectionDetectedError immediately if unsafe,
        logging the incident to the audit trail.
        """
        scan = self.scan_text(text, source=source)
        if not scan.is_safe:
            # Record security incident in audit log
            if db_manager and hasattr(db_manager, "save_audit_log"):
                try:
                    db_manager.save_audit_log({
                        "organization_id": org_id or "default",
                        "actor": actor,
                        "action": "PROMPT_INJECTION_BLOCKED",
                        "resource_type": "security_firewall",
                        "resource_id": scan.threat_category,
                        "payload": {
                            "threat_category": scan.threat_category,
                            "matched_pattern": scan.matched_pattern,
                            "risk_score": scan.risk_score,
                            "source": source,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    })
                except Exception as audit_err:
                    logger.debug(f"Could not record prompt injection audit log: {audit_err}")

            raise PromptInjectionDetectedError(
                detail=f"Prompt injection or malicious instruction detected ({scan.threat_category}). Request blocked by AI Security Firewall.",
                threat_category=scan.threat_category or "PROMPT_INJECTION",
                risk_score=scan.risk_score
            )


# Global firewall singleton
_firewall_instance: Optional[PromptInjectionFirewall] = None


def get_prompt_firewall() -> PromptInjectionFirewall:
    global _firewall_instance
    if _firewall_instance is None:
        _firewall_instance = PromptInjectionFirewall()
    return _firewall_instance
