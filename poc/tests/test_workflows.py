"""Test workflows. Existing cases moved without execution."""
import pytest
import uuid
from datetime import datetime
from fastapi.testclient import TestClient
from persistence import db_manager, Department, Workflow
from backend.main import app
from workflows.parser import WorkflowParser, WorkflowDefinition
from workflows.sandbox import SandboxManager
from workflows.engine import WorkflowEngine, BudgetExceededError


from poc.tests.workflow_test_support import client

def test_workflow_yaml_and_json_parsing_roundtrip():
    """Verify bidirectional YAML <-> JSON conversion of workflow definitions."""
    sample_yaml = """
id: wf-code-review
name: Automated Code Review
description: Multi-agent code review workflow
department_id: dept-eng
steps:
  - key: triage
    name: Ticket Triage
    agent_id: dev-lead
    prompt_template: Triage ticket ${ticket_id} and assess impact
  - key: review
    name: Deep Code Review
    agent_id: backend-dev
    depends_on:
      - triage
    prompt_template: "Review PR based on triage summary: ${triage.output}"
"""
    # 1. Parse YAML
    wf = WorkflowParser.from_yaml(sample_yaml)
    assert wf.id == "wf-code-review"
    assert wf.name == "Automated Code Review"
    assert len(wf.steps) == 2
    assert wf.steps[0].key == "triage"
    assert wf.steps[1].depends_on == ["triage"]

    # 2. Convert to JSON
    json_str = wf.to_json()
    assert '"wf-code-review"' in json_str

    # 3. Parse back from JSON
    wf_from_json = WorkflowParser.from_json(json_str)
    assert wf_from_json.name == wf.name
    assert len(wf_from_json.steps) == 2

    # 4. Helper string converter
    converted_json = WorkflowParser.yaml_to_json(sample_yaml)
    assert "Automated Code Review" in converted_json


def test_workflow_flow_transitions_and_triggers_parsing():
    """Verify parsing industry-standard YAML schema with triggers, conditions, step skills and flow graph."""
    raw_yaml = """
name: Questionnaire Flow Build Failure Investigation
priority: 5
timeoutMs: 2700000

triggers:
  - event: manual
  - event: channel_message
    conditions:
      combinator: and
      rules:
        - field: context.channel.id
          operator: matches
          value: ^(C051G5J4C2W|C083U3EH5TL)$
        - field: context.message.text
          operator: matches
          value: \\b(FAILURE|FAILED)\\b

steps:
  - name: Clone skyscraper
    params:
      agentId: cmv3u8pdc00518bmdaqcrrygx
    stepMaxDurationMinutes: 10

  - name: Investigate failure
    skills:
      - jenkins-mcp
      - github-read
      - jira-read
    instructions: |
      ## Process
      1. Investigate build failure using Jenkins MCP.
      2. Identify culprit commit via GitHub.
    params:
      agentId: cmv3u8pdc00518bmdaqcrrygx
    stepMaxDurationMinutes: 30

flow:
  - from: ""
    to: clone-skyscraper
  - from: clone-skyscraper
    to: investigate-failure
"""
    wf = WorkflowParser.from_yaml(raw_yaml)
    assert wf.name == "Questionnaire Flow Build Failure Investigation"
    assert wf.id == "questionnaire-flow-build-failure-investigation"
    assert wf.priority == 5
    assert wf.timeout_ms == 2700000

    assert len(wf.triggers) == 2
    assert wf.triggers[0]["event"] == "manual"
    assert wf.triggers[1]["conditions"]["combinator"] == "and"

    assert len(wf.steps) == 2
    step1 = wf.steps[0]
    step2 = wf.steps[1]

    assert step1.key == "clone-skyscraper"
    assert step1.agent_id == "cmv3u8pdc00518bmdaqcrrygx"
    assert step1.timeout_seconds == 600

    assert step2.key == "investigate-failure"
    assert step2.agent_id == "cmv3u8pdc00518bmdaqcrrygx"
    assert step2.timeout_seconds == 1800
    assert step2.skills == ["jenkins-mcp", "github-read", "jira-read"]
    assert "Investigate build failure" in step2.prompt_template

    # Check that flow-to-DAG conversion automatically resolved dependency!
    assert "clone-skyscraper" in step2.depends_on

    # Roundtrip conversion
    json_rep = wf.to_json()
    wf_back = WorkflowParser.from_json(json_rep)
    assert wf_back.name == wf.name
    assert wf_back.steps[1].depends_on == ["clone-skyscraper"]
    assert len(wf_back.flow) == 2


def test_trigger_condition_matching_logic():
    """Verify conditional matching logic on incoming trigger payloads."""
    from workflows.engine import evaluate_trigger_conditions

    trigger = {
        "event": "channel_message",
        "conditions": {
            "combinator": "and",
            "rules": [
                {
                    "field": "context.channel.id",
                    "operator": "matches",
                    "value": "^(C051G5J4C2W|C083U3EH5TL)$"
                },
                {
                    "field": "context.message.text",
                    "operator": "matches",
                    "value": "\\b(FAILURE|FAILED)\\b"
                }
            ]
        }
    }

    # 1. Matching payload
    valid_payload = {
        "context": {
            "channel": {"id": "C051G5J4C2W"},
            "message": {"text": "Job #42 status: FAILURE detected on master"}
        }
    }
    assert evaluate_trigger_conditions(trigger, valid_payload) is True

    # 2. Non-matching channel
    wrong_channel_payload = {
        "context": {
            "channel": {"id": "C_OTHER_CHANNEL"},
            "message": {"text": "Job #42 FAILURE"}
        }
    }
    assert evaluate_trigger_conditions(trigger, wrong_channel_payload) is False

    # 3. Non-matching message text
    success_payload = {
        "context": {
            "channel": {"id": "C051G5J4C2W"},
            "message": {"text": "Job #42 SUCCESS"}
        }
    }
    assert evaluate_trigger_conditions(trigger, success_payload) is False

