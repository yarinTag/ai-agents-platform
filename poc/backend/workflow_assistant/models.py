"""Strict, transport-independent authoring inputs; these are not executable workflows."""

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator
from workflows.authoring_schema import ToolReference, RepositoryReference, ChannelReference


class AuthoringModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProposalTrigger(AuthoringModel):
    kind: Literal["manual", "webhook", "cron", "channel", "repository"] = "manual"
    connector_id: Optional[str] = Field(None, min_length=1, max_length=200)
    channel_id: Optional[str] = Field(None, min_length=1, max_length=200)
    repository: Optional[str] = Field(None, min_length=1, max_length=500)
    cron_expression: Optional[str] = Field(None, max_length=200)
    event: Optional[str] = Field(None, max_length=200)


class ProposalStep(AuthoringModel):
    key: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=200)
    agent_id: str = Field(min_length=1, max_length=200)
    prompt_template: str = Field(min_length=1, max_length=16000)
    depends_on: list[Annotated[str, Field(min_length=1, max_length=120)]] = Field(default_factory=list, max_length=100)
    tools: list[ToolReference] = Field(default_factory=list, max_length=100)
    repositories: list[RepositoryReference] = Field(default_factory=list, max_length=100)
    channels: list[ChannelReference] = Field(default_factory=list, max_length=100)
    skills: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(default_factory=list, max_length=100)
    requires_approval: bool = False
    timeout_seconds: int = Field(180, ge=1, le=300)


class WorkflowProposal(AuthoringModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field("", max_length=4000)
    trigger: ProposalTrigger = Field(default_factory=ProposalTrigger)
    steps: list[ProposalStep] = Field(min_length=1, max_length=100)
    unresolved_requirements: list[Annotated[str, Field(min_length=1, max_length=2000)]] = Field(default_factory=list, max_length=100)


class ValidationRequest(AuthoringModel):
    department_id: str = Field(min_length=1, max_length=200)
    proposal: WorkflowProposal


class DraftCreate(ValidationRequest):
    intent_text: str = Field("", max_length=16000)
    save_blocked: bool = False


class DraftUpdate(AuthoringModel):
    expected_revision: int = Field(ge=1)
    proposal: WorkflowProposal
    intent_text: Optional[str] = Field(None, max_length=16000)
    save_blocked: bool = False


class AuthoringMessage(AuthoringModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class GenerationRequest(AuthoringModel):
    department_id: str = Field(min_length=1, max_length=200)
    model_id: str = Field(min_length=1, max_length=200)
    provider_id: str = Field(min_length=1, max_length=100)
    locale: Literal["en", "he"] = "en"
    messages: list[AuthoringMessage] = Field(min_length=1, max_length=20)
    intent_text: str = Field("", max_length=16000)
    previous_proposal: Optional[WorkflowProposal] = None
    draft_id: Optional[str] = Field(None, max_length=200)
    expected_draft_revision: Optional[int] = Field(None, ge=1)

    @model_validator(mode="after")
    def validate_history(self):
        if (self.draft_id is None) != (self.expected_draft_revision is None):
            raise ValueError("draft_id and expected_draft_revision must be supplied together")
        if self.messages[-1].role != "user":
            raise ValueError("The last message must be a user request")
        if sum(len(message.content) for message in self.messages) > 40000:
            raise ValueError("Conversation context exceeds 40000 characters")
        return self


class AuthoringReply(AuthoringModel):
    assistant_message: str = Field(min_length=1, max_length=8000)
    questions: list[Annotated[str, Field(min_length=1, max_length=2000)]] = Field(default_factory=list, max_length=10)
    proposal: Optional[WorkflowProposal] = None


class SaveGenerationRequest(AuthoringModel):
    save_blocked: bool = False


class ModelAuthoringReply(AuthoringModel):
    assistant_message: str = Field(min_length=1, max_length=8000)
    questions: list[Annotated[str, Field(min_length=1, max_length=2000)]] = Field(default_factory=list, max_length=10)
    validation_id: Optional[str] = Field(None, pattern=r"^wfc_[a-f0-9]{32}$")


class YamlValidationRequest(AuthoringModel):
    department_id: str = Field(min_length=1, max_length=200)
    yaml_content: str = Field(min_length=1, max_length=200000)
