"""Source-only relationship contracts; no providers, scanners or application startup."""
import json

from plugins.connections import enrich_skill_connections


def skill(sid, content=""):
    return {"id": sid, "path": f"/skills/{sid}/SKILL.md", "_raw_content": content}


def project(*skills, documents=None):
    packages = {"core": {"skills": list(skills)}}
    enrich_skill_connections(packages, documents)
    return {entry["id"]: entry for entry in packages["core"]["skills"]}


def test_engineering_handoffs_do_not_promote_storage_protocol_reference():
    review = """---
name: product-eng-review
---
## Storage
Read [storage](../product-idea-to-blueprint/references/google-docs-storage-protocol.md).
## Handoffs
- If unverified technology is required: trigger `product-tech-spike-evaluator`.
- If an architectural trade-off requires evaluation: trigger `product-adr-decision-maker`.
- If all checks pass, hand off to `product-architecture-designer`.
"""
    result = project(skill("product-eng-review", review), skill("product-idea-to-blueprint"),
                     skill("product-tech-spike-evaluator"), skill("product-adr-decision-maker"),
                     skill("product-architecture-designer"))["product-eng-review"]
    flow = [edge for edge in result["skill_connections"] if edge["kind"] != "reference"]
    assert {edge["target"] for edge in flow} == {
        "product-tech-spike-evaluator", "product-adr-decision-maker", "product-architecture-designer",
    }
    assert all(edge["kind"] == "conditional_handoff" for edge in flow)
    storage = next(edge for edge in result["skill_connections"] if edge["target"] == "product-idea-to-blueprint")
    assert storage["kind"] == "reference"
    assert storage["evidence"]["line"] == 5
    assert storage["evidence"]["path"] == "/skills/product-eng-review/SKILL.md"
    assert "_raw_content" not in result


def test_negation_code_frontmatter_scripts_and_non_goals_are_not_handoffs():
    content = """---
description: invoke product-target
---
Never invoke `product-target`.
Do not run `product-target`.
Run `../product-target/scripts/check.js`.
```sh
invoke product-target
```
## When Not to Use
Use `product-target` instead.
## Handoff
Invoke `product-target`.
"""
    result = project(skill("source", content), skill("product-target"))["source"]
    flow = [edge for edge in result["skill_connections"] if edge["kind"] != "reference"]
    assert len(flow) == 1
    assert flow[0]["evidence"]["line"] == 13


def test_conditional_verdict_is_retained_across_sentence_boundary():
    result = project(skill("source", "If PASS: emit report. Hand off to `product-target`."),
                     skill("product-target"))["source"]
    assert result["skill_connections"][0]["kind"] == "conditional_handoff"


def test_alias_collision_never_picks_first_discovered_target():
    result = project(skill("source", "Invoke `shared-name`."), skill("product-shared-name"), skill("meta-shared-name"))
    assert result["source"]["skill_connections"] == []


def test_duplicate_ids_do_not_create_ambiguous_edges():
    packages = {"a": {"skills": [skill("duplicate"), skill("source", "Invoke `duplicate`.")]},
                "b": {"skills": [skill("duplicate")]}}
    enrich_skill_connections(packages)
    assert packages["a"]["skills"][1]["skill_connections"] == []
    assert packages["a"]["skills"][0]["connection_warnings"]


def test_no_flow_is_inferred_from_truncated_preview():
    entry = skill("source", None)
    entry["content_preview"] = "Invoke `product-target`."
    result = project(entry, skill("product-target"))["source"]
    assert result["skill_connections"] == []
    assert result["connection_warnings"]


def test_declared_dag_preserves_direction_optional_nodes_and_unresolved_groups():
    dag = {"nodes": [
        {"id": "publish", "skill": "publisher", "nextNodes": ["review"]},
        {"id": "review", "skill": "reviewer", "optional": True, "nextNodes": ["implementation"]},
        {"id": "implementation", "skill": "frontend / backend", "nextNodes": []},
    ]}
    result = project(skill("publisher"), skill("reviewer"), documents={"/refs/skill-dependency-dag.json": json.dumps(dag)})
    edge = result["publisher"]["skill_connections"][0]
    assert (edge["source"], edge["target"], edge["kind"]) == ("publisher", "reviewer", "declared_transition")
    assert edge["conditional"] is True
    assert edge["evidence"]["node_id"] == "publish"
    assert json.loads(edge["evidence"]["text"])["to"]["optional"] is True
    assert result["reviewer"]["skill_connections"] == []
    assert "Unresolved declared transition" in result["reviewer"]["connection_warnings"][0]


def test_malformed_dags_and_unknown_nodes_do_not_fabricate_edges():
    for document in ["bad json", "null", '{"nodes": null}', '{"nodes": [{"id": "x"}, {"id": "x"}]}']:
        assert project(skill("source"), documents={"dag": document})["source"]["skill_connections"] == []


def test_declared_routing_table_is_conditional_but_boundary_matrix_is_reference():
    content = """## Routing table
| Signals | Skill | Path |
| Forecasting | financial-analyst | `skills/financial-analyst/` |
## Skill Boundaries
| financial-analyst | Valuation belongs here |
"""
    result = project(skill("router", content), skill("financial-analyst"))["router"]
    assert [(edge["kind"], edge["evidence"]["line"]) for edge in result["skill_connections"]] == [
        ("conditional_handoff", 3), ("reference", 3), ("reference", 5),
    ]


def test_coordinated_handoff_targets_preserve_purpose_and_condition():
    result = project(skill("writer", "Once aligned, hand off to `product-eng-review` for feasibility and `architecture-designer` for modeling."),
                     skill("product-eng-review"), skill("product-architecture-designer"))["writer"]
    assert [(edge["target"], edge["kind"]) for edge in result["skill_connections"]] == [
        ("product-eng-review", "conditional_handoff"), ("product-architecture-designer", "conditional_handoff"),
    ]
