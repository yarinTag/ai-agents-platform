"""Ownership of custom catalog records whose legacy tables lack tenant columns."""
import re
import hashlib
from fastapi import HTTPException


def tenant_identifier(actor, name):
    original = name.strip()
    normalized = original.lower().replace(" ", "-").replace("_", "-")
    slug = re.sub(r"[^a-z0-9-]+", "-", normalized).strip("-")[:80]
    if not slug or slug != normalized:
        slug = (slug or "catalog") + "-" + hashlib.sha256(original.encode()).hexdigest()[:12]
    return f"{actor.organization_id}--{slug}"



def register_owner(db, actor, kind, identifier):
    with db._get_connection() as conn:
        owner = conn.execute("SELECT organization_id FROM access_resource_owners WHERE resource_type=? AND resource_id=?", (kind, identifier)).fetchone()
        existing = getattr(db, "get_skill" if kind == "skill" else "get_template")(identifier)
        if existing and (not owner or owner["organization_id"] != actor.organization_id):
            raise HTTPException(409, "An existing catalog record requires explicit ownership migration.")
        conn.execute("INSERT INTO access_resource_owners(resource_type,resource_id,organization_id) VALUES(?,?,?) "
                     "ON CONFLICT(resource_type,resource_id) DO NOTHING", (kind, identifier, actor.organization_id))
        row = conn.execute("SELECT organization_id FROM access_resource_owners WHERE resource_type=? AND resource_id=?", (kind, identifier)).fetchone()
        if not row or row["organization_id"] != actor.organization_id:
            raise HTTPException(409, "Catalog ownership conflicts with an existing record.")
