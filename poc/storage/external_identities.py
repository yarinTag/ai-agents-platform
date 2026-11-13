"""Atomic challenge and identity lifecycle scoped to a connector and tenant."""
import hashlib
import json
import secrets
import time
from uuid import uuid4

from integrations.identity_proofs import configuration, InvalidProof


def initialize(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS identity_challenges (
        id TEXT PRIMARY KEY, digest TEXT UNIQUE NOT NULL,
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        connector_id TEXT NOT NULL REFERENCES mcp_connectors(id) ON DELETE CASCADE,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        version TEXT NOT NULL, created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
        subject TEXT, consumed INTEGER NOT NULL DEFAULT 0
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_identity_challenge_owner ON identity_challenges(user_id, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_identity_challenge_expiry ON identity_challenges(expires_at)")
    conn.execute("""CREATE TABLE IF NOT EXISTS external_identity_links (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        connector_id TEXT NOT NULL REFERENCES mcp_connectors(id) ON DELETE CASCADE,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        provider TEXT NOT NULL, account TEXT NOT NULL, subject TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        UNIQUE(organization_id, provider, account, subject),
        UNIQUE(organization_id, provider, account, user_id)
    )""")


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def connector_settings(conn, connector_id, organization_id=None):
    row = conn.execute("SELECT * FROM mcp_connectors WHERE id = ? AND status = 'CONNECTED'", (connector_id,)).fetchone()
    if row is None or not row["organization_id"] or (organization_id is not None and row["organization_id"] != organization_id):
        raise InvalidProof("CONNECTOR_UNAVAILABLE")
    provider = row["provider"].lower()
    settings = configuration(provider, json.loads(row["configuration"] or "{}"))
    version = digest(json.dumps((provider, settings)))
    return row["organization_id"], provider, settings, version


def _active(conn, organization_id, user_id):
    if not conn.execute("SELECT 1 FROM users WHERE id=? AND organization_id=? AND status='ACTIVE'",
                        (user_id, organization_id)).fetchone():
        raise InvalidProof("USER_UNAVAILABLE")


def _require_connector_access(conn, organization_id, user_id, connector_id, department_id=None):
    allowed = conn.execute("""SELECT 1 FROM users u
        WHERE u.id=? AND u.organization_id=? AND u.status='ACTIVE'
        AND (u.role='ORG_ADMIN' OR (u.role IN ('MANAGER','OPERATOR','MEMBER') AND EXISTS (
            SELECT 1 FROM department_members m
            JOIN departments d ON d.id=m.department_id AND d.organization_id=u.organization_id
            JOIN department_mcp_access g ON g.department_id=d.id AND g.connector_id=?
            WHERE m.user_id=u.id AND m.role IN ('MEMBER','OPERATOR','MANAGER','ORG_ADMIN') AND g.is_active=1
            AND (? IS NULL OR d.id=?)
            AND (g.organization_id IS NULL OR g.organization_id=u.organization_id)
        )))""", (user_id, organization_id, connector_id, department_id, department_id)).fetchone()
    if not allowed:
        raise InvalidProof("CONNECTOR_UNAVAILABLE")


def _audit(conn, action, organization_id, connector_id, user_id, identifier, now):
    conn.execute("""INSERT INTO audit_logs (id, action, actor, entity_type, entity_id, details, timestamp)
        VALUES (?, ?, ?, 'external_identity', ?, ?, datetime(?, 'unixepoch'))""",
        (f"audit_{uuid4().hex}", action, user_id, identifier,
         json.dumps({"organization_id": organization_id, "connector_id": connector_id}), now))


def issue(db, organization_id, user_id, connector_id, department_id=None):
    now = int(time.time())
    code = secrets.token_urlsafe(32)
    identifier = f"idc_{uuid4().hex}"
    with db._get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _active(conn, organization_id, user_id)
        _require_connector_access(conn, organization_id, user_id, connector_id, department_id)
        _, provider, _, version = connector_settings(conn, connector_id, organization_id)
        conn.execute("DELETE FROM identity_challenges WHERE expires_at <= ?", (now - 600,))
        count = conn.execute("SELECT count(*) FROM identity_challenges WHERE user_id=? AND created_at>?",
                             (user_id, now - 600)).fetchone()[0]
        if count >= 5:
            raise InvalidProof("RATE_LIMITED")
        conn.execute("UPDATE identity_challenges SET consumed=1 WHERE user_id=? AND connector_id=?", (user_id, connector_id))
        conn.execute("""INSERT INTO identity_challenges
            (id,digest,organization_id,connector_id,user_id,version,created_at,expires_at)
            VALUES (?,?,?,?,?,?,?,?)""", (identifier, digest(code), organization_id, connector_id, user_id, version, now, now + 300))
    return {"id": identifier, "code": code, "provider": provider, "expires_at": now + 300}


def _pending(row, version, now):
    if row is None:
        raise InvalidProof("CHALLENGE_UNAVAILABLE")
    if row["consumed"]:
        raise InvalidProof("CHALLENGE_REPLAY")
    if row["expires_at"] <= now:
        raise InvalidProof("CHALLENGE_EXPIRED")
    if row["version"] != version:
        raise InvalidProof("PROVIDER_ROTATED")


def record_proof(db, connector_id, verified_version, subject, code):
    with db._get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        now = int(time.time())
        org, _, _, version = connector_settings(conn, connector_id)
        if verified_version != version:
            raise InvalidProof("PROVIDER_ROTATED")
        row = conn.execute("""SELECT * FROM identity_challenges
            WHERE connector_id=? AND organization_id=? AND digest=?""", (connector_id, org, digest(code))).fetchone()
        _pending(row, version, now)
        if row["subject"] is not None:
            raise InvalidProof("CHALLENGE_REPLAY")
        _require_connector_access(conn, org, row["user_id"], connector_id)
        conn.execute("UPDATE identity_challenges SET subject=? WHERE id=?", (subject, row["id"]))


def confirm(db, organization_id, user_id, identifier, expected_subject):
    with db._get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        now = int(time.time())
        _active(conn, organization_id, user_id)
        row = conn.execute("""SELECT * FROM identity_challenges
            WHERE id=? AND organization_id=? AND user_id=?""", (identifier, organization_id, user_id)).fetchone()
        if row is None:
            raise InvalidProof("CHALLENGE_UNAVAILABLE")
        connector_id = row["connector_id"]
        _require_connector_access(conn, organization_id, user_id, connector_id)
        _, provider, (_, account, _), version = connector_settings(conn, connector_id, organization_id)
        _pending(row, version, now)
        if row["subject"] is None or row["subject"] != expected_subject:
            raise InvalidProof("PROOF_MISMATCH")
        existing = conn.execute("""SELECT 1 FROM external_identity_links
            WHERE organization_id=? AND provider=? AND account=? AND (subject=? OR user_id=?)""",
            (organization_id, provider, account, expected_subject, user_id)).fetchone()
        if existing:
            raise InvalidProof("IDENTITY_CONFLICT")
        link_id = f"idl_{uuid4().hex}"
        conn.execute("""INSERT INTO external_identity_links
            (id,organization_id,connector_id,user_id,provider,account,subject,created_at)
            VALUES (?,?,?,?,?,?,?,?)""",
            (link_id, organization_id, connector_id, user_id, provider, account, expected_subject, now))
        conn.execute("UPDATE identity_challenges SET consumed=1 WHERE id=?", (identifier,))
        _audit(conn, "EXTERNAL_IDENTITY_LINKED", organization_id, connector_id, user_id, link_id, now)
    return {"id": link_id, "connector_id": connector_id, "provider": provider, "subject": expected_subject}


def list_for_user(db, organization_id, user_id):
    with db._get_connection() as conn:
        return [dict(row) for row in conn.execute("""SELECT id,connector_id,provider,subject,created_at
            FROM external_identity_links WHERE organization_id=? AND user_id=? ORDER BY created_at,id""",
            (organization_id, user_id))]


def _department_manager(conn, organization_id, actor_id, department_id):
    if not conn.execute("""SELECT 1 FROM users u JOIN departments d ON d.organization_id=u.organization_id
        WHERE u.id=? AND u.organization_id=? AND u.status='ACTIVE' AND d.id=?
        AND (u.role='ORG_ADMIN' OR (u.role='MANAGER' AND EXISTS (
            SELECT 1 FROM department_members m WHERE m.department_id=d.id AND m.user_id=u.id
            AND m.role IN ('MANAGER','ORG_ADMIN')
        )))""", (actor_id, organization_id, department_id)).fetchone():
        raise PermissionError("Department manager required.")


_MANAGED_LINKS = """FROM external_identity_links l
    JOIN users u ON u.id=l.user_id AND u.organization_id=l.organization_id
    JOIN department_members m ON m.user_id=l.user_id AND m.department_id=?
    JOIN mcp_connectors c ON c.id=l.connector_id AND c.organization_id=l.organization_id
    JOIN department_mcp_access g ON g.department_id=m.department_id AND g.connector_id=l.connector_id
    WHERE l.organization_id=? AND g.is_active=1 AND (g.organization_id IS NULL OR g.organization_id=l.organization_id)"""

_SHARED_LINK = """EXISTS (
    SELECT 1 FROM department_members other
    JOIN departments d ON d.id=other.department_id AND d.organization_id=l.organization_id
    JOIN department_mcp_access grant ON grant.department_id=d.id AND grant.connector_id=l.connector_id
    WHERE other.user_id=l.user_id AND other.department_id<>m.department_id
    AND grant.is_active=1 AND (grant.organization_id IS NULL OR grant.organization_id=l.organization_id)
) OR u.role='ORG_ADMIN'"""


def list_managed(db, organization_id, actor_id, department_id, after, limit):
    with db._get_connection() as conn:
        conn.execute("BEGIN")
        _department_manager(conn, organization_id, actor_id, department_id)
        return [dict(row) for row in conn.execute(
            """SELECT l.id,l.connector_id,l.provider,l.subject,l.created_at,u.full_name AS member_name,
            (? OR NOT (""" + _SHARED_LINK + """)) AS can_revoke """
            + _MANAGED_LINKS + " AND l.id>? ORDER BY l.id LIMIT ?",
            (_is_admin(conn, organization_id, actor_id), department_id, organization_id, after, limit))]


def revoke_managed(db, organization_id, actor_id, department_id, identifier):
    with db._get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _department_manager(conn, organization_id, actor_id, department_id)
        link = conn.execute("SELECT l.connector_id,l.user_id,(" + _SHARED_LINK + ") AS shared "
                            + _MANAGED_LINKS + " AND l.id=?",
                            (department_id, organization_id, identifier)).fetchone()
        if link is None:
            raise InvalidProof("LINK_UNAVAILABLE")
        if link["shared"] and not _is_admin(conn, organization_id, actor_id):
            raise PermissionError("Shared links require an organization administrator.")
        conn.execute("DELETE FROM external_identity_links WHERE id=?", (identifier,))
        conn.execute("UPDATE identity_challenges SET consumed=1 WHERE user_id=? AND connector_id=?",
                     (link["user_id"], link["connector_id"]))
        _audit(conn, "EXTERNAL_IDENTITY_REVOKED", organization_id, link["connector_id"],
               actor_id, identifier, int(time.time()))


def _is_admin(conn, organization_id, actor_id):
    return conn.execute("SELECT 1 FROM users WHERE id=? AND organization_id=? AND status='ACTIVE' AND role='ORG_ADMIN'",
                        (actor_id, organization_id)).fetchone() is not None


def status(db, organization_id, user_id, identifier):
    with db._get_connection() as conn:
        row = conn.execute("""SELECT * FROM identity_challenges WHERE id=? AND organization_id=? AND user_id=?""",
                           (identifier, organization_id, user_id)).fetchone()
        if row is None:
            raise InvalidProof("CHALLENGE_UNAVAILABLE")
        _require_connector_access(conn, organization_id, user_id, row["connector_id"])
        _, _, _, version = connector_settings(conn, row["connector_id"], organization_id)
        _pending(row, version, int(time.time()))
        return {"id": identifier, "subject": row["subject"], "expires_at": row["expires_at"]}


def rotate_secret(db, organization_id, user_id, connector_id, secret, team_id, app_id):
    with db._get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if not _is_admin(conn, organization_id, user_id):
            raise PermissionError("Organization administrator required.")
        row = conn.execute("SELECT provider,configuration FROM mcp_connectors WHERE id=? AND organization_id=?",
                           (connector_id, organization_id)).fetchone()
        if row is None:
            raise InvalidProof("CONNECTOR_UNAVAILABLE")
        provider = row["provider"].lower()
        config = json.loads(row["configuration"] or "{}")
        if provider == "telegram":
            config["identity_webhook_secret"] = secret
        elif provider == "slack":
            config.update(identity_signing_secret=secret, identity_team_id=team_id, identity_app_id=app_id)
        configuration(provider, config)
        conn.execute("UPDATE mcp_connectors SET configuration=? WHERE id=?", (json.dumps(config), connector_id))
        conn.execute("UPDATE identity_challenges SET consumed=1 WHERE connector_id=?", (connector_id,))
        _audit(conn, "EXTERNAL_IDENTITY_SECRET_ROTATED", organization_id, connector_id, user_id, connector_id, int(time.time()))


def unlink(db, organization_id, user_id, identifier):
    with db._get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _active(conn, organization_id, user_id)
        row = conn.execute("""DELETE FROM external_identity_links WHERE id=? AND organization_id=? AND user_id=?
            RETURNING connector_id""", (identifier, organization_id, user_id)).fetchone()
        if row is None:
            raise InvalidProof("LINK_UNAVAILABLE")
        conn.execute("UPDATE identity_challenges SET consumed=1 WHERE user_id=? AND connector_id=?",
                     (user_id, row["connector_id"]))
        _audit(conn, "EXTERNAL_IDENTITY_UNLINKED", organization_id, row["connector_id"], user_id, identifier, int(time.time()))


def resolve_user(db, organization_id, connector_id, verified_subject):
    """Resolve a verified subject to a current user. Callers must authorize the action."""
    with db._get_connection() as conn:
        _, provider, (_, account, _), _ = connector_settings(conn, connector_id, organization_id)
        row = conn.execute("""SELECT users.id FROM external_identity_links AS links
            JOIN users ON users.id=links.user_id AND users.organization_id=links.organization_id
            WHERE links.organization_id=? AND links.connector_id=? AND links.provider=? AND links.account=?
            AND links.subject=? AND users.status='ACTIVE'""",
            (organization_id, connector_id, provider, account, verified_subject)).fetchone()
        if row:
            _require_connector_access(conn, organization_id, row["id"], connector_id)
            return row["id"]
        return None
