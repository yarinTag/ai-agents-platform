"""Small, strict model-only chat contract for creating inactive workflows."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class ResourceRef(StrictModel):
    connector_id: str = Field(min_length=1, max_length=200)
    repository: str | None = Field(default=None, max_length=500)
    channel_id: str | None = Field(default=None, max_length=200)
    tool_name: str | None = Field(default=None, max_length=200)

    @model_validator(mode='after')
    def nonempty(self):
        if not any((self.repository, self.channel_id, self.tool_name)):
            raise ValueError('A resource reference must specify a repository, channel or tool.')
        return self


class ChatStep(StrictModel):
    key: str = Field(pattern=r'^[a-zA-Z][a-zA-Z0-9_-]{0,79}$')
    name: str = Field(min_length=1, max_length=200)
    agent_id: str = Field(min_length=1, max_length=200)
    prompt_template: str = Field(min_length=1, max_length=8000)
    depends_on: list[str] = Field(default_factory=list, max_length=40)
    resources: list[ResourceRef] = Field(default_factory=list, max_length=40)
    timeout_seconds: int = Field(default=300, ge=10, le=1800)
    skills: list[str] = Field(default_factory=list, max_length=20)
    send_output_of: str | None = Field(default=None, min_length=1, max_length=80)


class Destination(StrictModel):
    connector_id: str = Field(min_length=1, max_length=200)
    channel_id: str = Field(min_length=1, max_length=200)


class ChatWorkflow(StrictModel):
    name: str = Field(min_length=1, max_length=150)
    description: str = Field(default='', max_length=4000)
    steps: list[ChatStep] = Field(min_length=1, max_length=40)
    skills: list[str] = Field(default_factory=list, max_length=20)
    destination: Destination | None = None
    cron_expression: str | None = Field(default=None, max_length=100)


class ChatReply(StrictModel):
    message: str = Field(min_length=1, max_length=8000)
    workflow: ChatWorkflow | None = None


class ChatMessage(StrictModel):
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=8000)


class ChatRequest(StrictModel):
    request_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{16,80}$')
    department_id: str = Field(min_length=1, max_length=200)
    messages: list[ChatMessage] = Field(min_length=1, max_length=20)
    previous_workflow: ChatWorkflow | None = None
    locale: Literal['en', 'he'] = 'en'

    @model_validator(mode='after')
    def bounded(self):
        if self.messages[-1].role != 'user' or sum(len(m.content) for m in self.messages) > 40000:
            raise ValueError('End with a user message and keep the conversation below 40,000 characters.')
        return self
