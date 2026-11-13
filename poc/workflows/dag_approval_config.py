"""Authoring contract for dashboard approval barriers in a workflow DAG."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DagApprovalPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    approver_roles: list[Literal["OPERATOR", "MANAGER", "ORG_ADMIN"]] = Field(
        default_factory=lambda: ["MANAGER", "ORG_ADMIN"], min_length=1, max_length=3,
    )
    timeout_seconds: int = Field(default=86400, ge=60, le=259200)
    quorum: int = Field(default=1, ge=1, le=10)
    separate_initiator: Literal[True] = True


def dag_approval_policy(step):
    params = step.params or {}
    if "dag_approval" not in params:
        return None
    if set(params) != {"dag_approval"} or step.mcp_servers:
        raise ValueError("DAG approval steps cannot declare execution tools or actions.")
    return DagApprovalPolicy.model_validate(params["dag_approval"])
