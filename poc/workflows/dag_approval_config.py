"""Authoring contract for dashboard approval barriers in a workflow DAG."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DagApprovalPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    approver_roles: list[Literal["OPERATOR", "MANAGER", "ORG_ADMIN"]] = Field(
        default_factory=lambda: ["MANAGER", "ORG_ADMIN"], min_length=1, max_length=3,
    )
    timeout_seconds: int = Field(default=86400, ge=60, le=259200)
    quorum: int = Field(default=1, ge=1, le=10)
    mode: Literal["CONTINUATION", "INDEPENDENT"] = "INDEPENDENT"
    # Accepted for old definitions; False never becomes a second opt-out switch.
    separate_initiator: Literal[True] | None = None
    channel_binding_id: str | None = Field(default=None, pattern=r"^chb_[a-f0-9]{32}$")
    summary_step: str | None = Field(default=None, min_length=1, max_length=80)

    @model_validator(mode="after")
    def legacy_separation(self):
        if self.separate_initiator and self.mode != "INDEPENDENT":
            raise ValueError("Legacy separate_initiator requires INDEPENDENT approval.")
        return self


def approval_mode(policy):
    """Old frozen policies remain independent; invalid modes never grant authority."""
    mode = policy.get("mode", "INDEPENDENT")
    if mode not in ("CONTINUATION", "INDEPENDENT"):
        raise ValueError("Invalid approval mode.")
    legacy = policy.get("separate_initiator")
    if (legacy is not None and legacy is not True) or (legacy is True and mode != "INDEPENDENT"):
        raise ValueError("Invalid legacy approval separation.")
    return mode


def dag_approval_policy(step):
    params = step.params or {}
    if "dag_approval" not in params:
        return None
    if set(params) != {"dag_approval"} or step.mcp_servers:
        raise ValueError("DAG approval steps cannot declare execution tools or actions.")
    policy = DagApprovalPolicy.model_validate(params["dag_approval"])
    if policy.summary_step and (not policy.channel_binding_id or policy.summary_step not in step.depends_on):
        raise ValueError("Approval summary must reference a direct dependency and a channel binding.")
    return policy
