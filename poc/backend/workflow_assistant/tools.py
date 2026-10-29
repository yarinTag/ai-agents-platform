"""Transport-independent authoring tools for platform and future authenticated MCP adapters.

No external MCP transport or OAuth is implied here. Both adapters must supply
verified identity/scopes to WorkflowAssistantService; tool results never grant access.
"""
import json

from .service import AssistantError
from .yaml_contract import load_workflow_yaml, document_to_proposal, proposal_artifact, workflow_schema


class WorkflowAuthoringTools:
    def __init__(self, policy):
        self.policy = policy

    def catalog(self, department_id):
        result = self.policy.catalog(department_id)
        if len(json.dumps(result, ensure_ascii=False)) > 120000:
            raise AssistantError("AUTHORING_CONTEXT_TOO_LARGE", "The approved resource catalog exceeds the authoring context limit.", 422)
        return result

    def schema(self):
        self.policy.context()
        return workflow_schema()

    def validate_document(self, department_id, document):
        proposal = document_to_proposal(document)
        return {'proposal': proposal.model_dump(),
            'validation': self.policy.validate(department_id, proposal), **proposal_artifact(proposal)}

    def validate_yaml(self, department_id, content):
        self.policy._workspace(department_id)
        return self.validate_document(department_id, load_workflow_yaml(content))
