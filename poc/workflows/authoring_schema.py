"""Strict, governed authoring subset of the existing WorkflowParser YAML fields.

Runtime workflows retain their broader legacy syntax. This schema deliberately rejects
unsupported fields rather than silently dropping them during authoring validation.
"""
from typing import Annotated, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1


class SchemaModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, strict=True)


Identifier = Annotated[str, Field(min_length=1, max_length=200)]
StepKey = Annotated[str, Field(min_length=1, max_length=120, pattern=r'^[a-zA-Z0-9_-]+$')]


class ToolReference(SchemaModel):
    connector_id: Identifier
    tool_name: Identifier


class RepositoryReference(SchemaModel):
    connector_id: Identifier
    repository: str = Field(min_length=1, max_length=500)


class ChannelReference(SchemaModel):
    connector_id: Identifier
    channel_id: Identifier


class ResourceBindings(SchemaModel):
    tools: list[ToolReference] = Field(default_factory=list, max_length=100)
    repositories: list[RepositoryReference] = Field(default_factory=list, max_length=100)
    channels: list[ChannelReference] = Field(default_factory=list, max_length=100)
    requires_approval: bool = False


class AuthoringStep(SchemaModel):
    key: StepKey
    name: str = Field(min_length=1, max_length=200)
    agent_id: Identifier
    prompt_template: str = Field(min_length=1, max_length=16000)
    depends_on: list[StepKey] = Field(default_factory=list, max_length=100)
    timeout_seconds: int = Field(default=180, ge=1, le=300)
    skills: list[Identifier] = Field(default_factory=list, max_length=100)
    mcp_servers: list[Identifier] = Field(default_factory=list, max_length=100)
    params: ResourceBindings = Field(default_factory=ResourceBindings)


class AuthoringTrigger(SchemaModel):
    event: Literal['manual', 'webhook', 'cron', 'channel_message', 'pull_request.opened', 'pull_request.updated', 'push']
    connector_id: Optional[Identifier] = None
    repository: Optional[str] = Field(default=None, min_length=1, max_length=500)
    channel_id: Optional[Identifier] = None


class FlowTransition(SchemaModel):
    source: str = Field(alias='from', max_length=120)
    to: StepKey


class AuthoringMetadata(SchemaModel):
    unresolved_requirements: list[Annotated[str, Field(min_length=1, max_length=2000)]] = Field(default_factory=list, max_length=100)


class WorkflowDocument(SchemaModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=4000)
    triggers: list[AuthoringTrigger] = Field(min_length=1, max_length=1)
    cron_expression: Optional[str] = Field(default=None, max_length=200)
    webhook_enabled: bool = False
    steps: list[AuthoringStep] = Field(min_length=1, max_length=100)
    flow: list[FlowTransition] = Field(default_factory=list, max_length=10000)
    metadata: AuthoringMetadata = Field(default_factory=AuthoringMetadata)
