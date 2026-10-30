"""Interpret structured and textual runtime clarification requests."""

import json
import re
from typing import Any, Dict, Optional

_QUESTION_TOOLS = {"ask_supervisor", "ask_manager", "ask_question", "AskUserQuestion"}


def _tool_question(name: str, inputs: Any) -> Dict[str, Any]:
    question = None
    options = []
    if isinstance(inputs, dict):
        questions = inputs.get("questions")
        if isinstance(questions, list) and questions:
            question = questions[0].get("question")
            options = [
                option.get("label", "") for option in questions[0].get("options", [])
                if isinstance(option, dict)
            ]
        if not question:
            question = inputs.get("question") or inputs.get("prompt")
    return {
        "question": question or str(inputs),
        "context": f"Agent invoked {name}.",
        "suggested_options": options,
    }


def extract_supervisor_question(data: Any) -> Optional[Dict[str, Any]]:
    """
    Detects if an event or model output represents a supervisor clarification question,
    permission request, or waiting input condition.
    Returns dictionary with {"question": ..., "context": ..., "suggested_options": ..., "is_permission": ...} or None.
    """
    if not data:
        return None

    # Case 1: Dict event
    if isinstance(data, dict):
        # 1a. Structured permission denials from Claude Code
        denials = data.get("permission_denials")
        if denials and isinstance(denials, list) and len(denials) > 0:
            tool_names = list({d.get("tool_name") for d in denials if isinstance(d, dict) and d.get("tool_name")})
            tools_str = ", ".join(tool_names) if tool_names else "tools"
            res_text = data.get("result", "")
            q_text = res_text if res_text else f"Permission required to execute tool(s): {tools_str}"
            return {
                "question": q_text,
                "context": f"Runtime sandbox denied permissions for {tools_str}.",
                "suggested_options": ["Grant permission", "Deny"],
                "is_permission": True
            }

        # Direct and nested tool events share the same input interpretation.
        if data.get("type") == "tool_use" and data.get("name") in _QUESTION_TOOLS:
            return _tool_question(data.get("name"), data.get("input", {}))

        # 1c. Tool call nested inside assistant message
        if data.get("type") == "assistant":
            msg = data.get("message", {})
            content = msg.get("content", [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_use":
                        name = item.get("name")
                        if name in _QUESTION_TOOLS:
                            return _tool_question(name, item.get("input", {}))

        # 1e. Check nested content or result fields
        if "result" in data and isinstance(data["result"], str):
            res_q = extract_supervisor_question(data["result"])
            if res_q:
                return res_q
        if "content" in data and isinstance(data["content"], str):
            cnt_q = extract_supervisor_question(data["content"])
            if cnt_q:
                return cnt_q

    # Case 2: String content or result
    if isinstance(data, str):
        text = data.strip()
        text_lower = text.lower()

        if "ask_supervisor" in text or "ask_manager" in text:
            try:
                match = re.search(r'\{.*"question".*\}', text, re.DOTALL)
                if match:
                    parsed = json.loads(match.group(0))
                    if "question" in parsed:
                        return {
                            "question": parsed["question"],
                            "context": parsed.get("context", ""),
                            "suggested_options": parsed.get("suggested_options", [])
                        }
            except Exception:
                pass

        if "[SUPERVISOR_REQUEST]" in text or "[ASK_SUPERVISOR]" in text:
            clean = text.replace("[SUPERVISOR_REQUEST]", "").replace("[ASK_SUPERVISOR]", "").strip()
            return {
                "question": clean,
                "context": "Agent flagged need for supervisor direction.",
                "suggested_options": []
            }

        # Check if this text is actually a completion report describing past actions rather than an active question
        completion_indicators = [
            "task is complete", "task completed", "the task is complete", "completed the task",
            "file has been created", "file was created", "created the file", "i verified",
            "verification result", "i have implemented", "i created the file", "done.", "finished."
        ]
        if any(ci in text_lower for ci in completion_indicators):
            return None

        # If quoting past questions (e.g. 'question asked:', 'i asked my supervisor'), ignore
        if "question asked" in text_lower or "i asked my supervisor" in text_lower or "i asked the supervisor" in text_lower:
            return None

        clarification_markers = [
            "please clarify", "could you clarify", "please specify", "please provide",
            "i need to know", "need more information", "before proceeding", "cannot proceed without",
            "waiting for your response", "waiting for response", "i am waiting for",
            "אנא ספק", "תוכל להבהיר", "נא להבהיר", "חסר מידע", "איזה קובץ", "איזה פורמט", "איזו מחרוזת", "מה המחרוזת"
        ]
        if any(marker in text_lower for marker in clarification_markers):
            return {
                "question": text,
                "context": "Agent indicated missing parameters or needed clarification to proceed.",
                "suggested_options": []
            }

    return None
