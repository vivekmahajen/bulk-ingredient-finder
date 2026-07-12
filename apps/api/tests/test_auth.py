"""Authentication: register/login/refresh/logout, reuse detection, lockout,
magic-link, invites, password reset, CSRF, rate limit."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.cookies import ACCESS_COOKIE, CSRF_COOKIE, CSRF_HEADER, REFRESH_COOKIE
from app.models.org import Org

REG = {
    "org_name": "Hari Om",
    "email": "owner@hariom.example",
    "password": "correct horse battery",  # ≥10 chars
    "display_name": "Owner",
}


@pytest.fixture()
def multi_tenant():
    prev = settings.multi_tenant
    settings.multi_tenant = True
    yield
    settings.multi_tenant = prev


@pytest.mark.asyncio
async def test_register_login_refresh_logout(
    db_session: AsyncSession, app, client: AsyncClient, multi_tenant
) -> None:
    # Register bootstraps an org + owner and sets the auth cookies.
    resp = await client.post("/api/v1/auth/register", json=REG)
    assert resp.status_code == 201, resp.text
    assert ACCESS_COOKIE in resp.cookies and REFRESH_COOKIE in resp.cookies
    # No token in the response body — cookies only (no JWT in JS-reachable storage).
    assert "access" not in resp.text.lower() or resp.json() == {"ok": True, "dev_token": None}

    # The access JWT drives the request context end-to-end.
    me = await client.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["email"] == REG["email"]
    assert me.json()["role"] == "owner"

    # Refresh rotates the tokens.
    old_refresh = client.cookies.get(REFRESH_COOKIE)
    r = await client.post("/api/v1/auth/refresh")
    assert r.status_code == 200
    assert client.cookies.get(REFRESH_COOKIE) != old_refresh
    assert (await client.get("/api/v1/me")).status_code == 200

    # Logout clears cookies; the session no longer resolves.
    assert (await client.post("/api/v1/auth/logout")).status_code == 200
    assert (await client.get("/api/v1/me")).status_code == 401


@pytest.mark.asyncio
async def test_login_wrong_password(
    db_session: AsyncSession, app, client: AsyncClient, multi_tenant
) -> None:
    await client.post("/api/v1/auth/register", json=REG)
    await client.post("/api/v1/auth/logout")
    resp = await client.post(
        "/api/v1/auth/login", json={"email": REG["email"], "password": "wrong-password-xx"}
    )
    assert resp.status_code == 401
    assert resp.json()["title"] == "Invalid credentials"


@pytest.mark.asyncio
async def test_login_unknown_email_uniform(
    db_session: AsyncSession, app, client: AsyncClient
) -> None:
    # Unknown email must look like a wrong password, not a distinct error.
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@x.example", "password": "whatever-123"}
    )
    assert resp.status_code == 401
    assert resp.json()["title"] == "Invalid credentials"


@pytest.mark.asyncio
async def test_refresh_reuse_revokes_family(
    db_session: AsyncSession, app, client: AsyncClient, multi_tenant
) -> None:
    await client.post("/api/v1/auth/register", json=REG)
    stolen = client.cookies.get(REFRESH_COOKIE)

    # Legitimate rotation.
    assert (await client.post("/api/v1/auth/refresh")).status_code == 200

    # Replaying the old (already-rotated) refresh token is reuse → rejected, and
    # it revokes the whole family, so the current valid token is also burned.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as attacker:
        attacker.cookies.set(REFRESH_COOKIE, stolen)
        assert (await attacker.post("/api/v1/auth/refresh")).status_code == 401

    # The legitimate client's next refresh now also fails (family revoked).
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


@pytest.mark.asyncio
async def test_lockout_after_failures(db_session: AsyncSession) -> None:
    from app.core.errors import ProblemException
    from app.core.security import hash_password
    from app.models.user import User
    from app.services import auth as auth_service

    org = Org(name="Hari Om")
    db_session.add(org)
    await db_session.flush()
    db_session.add(
        User(
            org_id=org.id,
            email="u@x.example",
            password_hash=hash_password("the-real-password"),
            display_name="U",
        )
    )
    await db_session.commit()

    for _ in range(10):
        with pytest.raises(ProblemException) as exc:
            await auth_service.login(db_session, email="u@x.example", password="bad-guess-xx")
        assert exc.value.status_code == 401

    # Now locked — even the correct password is refused with a lock error.
    with pytest.raises(ProblemException) as exc:
        await auth_service.login(db_session, email="u@x.example", password="the-real-password")
    assert exc.value.status_code == 403
    assert exc.value.title == "Account locked"


@pytest.mark.asyncio
async def test_magic_link_single_use(
    db_session: AsyncSession, app, client: AsyncClient, multi_tenant
) -> None:
    await client.post("/api/v1/auth/register", json=REG)
    await client.post("/api/v1/auth/logout")

    resp = await client.post("/api/v1/auth/magic-link", json={"email": REG["email"]})
    assert resp.status_code == 200
    token = resp.json()["dev_token"]
    assert token

    # First use logs in.
    first = await client.get("/api/v1/auth/magic/callback", params={"token": token})
    assert first.status_code == 200
    assert (await client.get("/api/v1/me")).status_code == 200

    # Second use of the same token fails (single-use).
    await client.post("/api/v1/auth/logout")
    second = await client.get("/api/v1/auth/magic/callback", params={"token": token})
    assert second.status_code == 400


@pytest.mark.asyncio
async def test_magic_link_unknown_email_uniform(
    db_session: AsyncSession, app, client: AsyncClient
) -> None:
    # Uniform 200 with no token when the email doesn't exist (no enumeration).
    resp = await client.post("/api/v1/auth/magic-link", json={"email": "ghost@x.example"})
    assert resp.status_code == 200
    assert resp.json()["dev_token"] is None


@pytest.mark.asyncio
async def test_invite_flow_role_assignment(
    db_session: AsyncSession, app, client: AsyncClient, multi_tenant
) -> None:
    await client.post("/api/v1/auth/register", json=REG)  # owner logged in

    invite = await client.post(
        "/api/v1/auth/invites", json={"email": "manager@hariom.example", "role": "manager"}
    )
    assert invite.status_code == 201, invite.text
    token = invite.json()["token"]
    assert token

    # Accept from a clean client → the new user gets the assigned role.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as invitee:
        accept = await invitee.post(
            "/api/v1/auth/invites/accept",
            json={
                "token": token,
                "password": "manager-password-1",
                "display_name": "Manager",
                "locale": "en",
            },
        )
        assert accept.status_code == 200, accept.text
        me = await invitee.get("/api/v1/me")
        assert me.json()["role"] == "manager"
        assert me.json()["email"] == "manager@hariom.example"


@pytest.mark.asyncio
async def test_invite_requires_privileged_role(
    db_session: AsyncSession, app, client: AsyncClient, multi_tenant
) -> None:
    # A staff user cannot create invites.
    from app.core.security import hash_password
    from app.models.user import User

    org = Org(name="Hari Om")
    db_session.add(org)
    await db_session.flush()
    db_session.add(
        User(
            org_id=org.id,
            email="staff@x.example",
            password_hash=hash_password("staff-password-1"),
            display_name="Staff",
            role="staff",
        )
    )
    await db_session.commit()

    await client.post(
        "/api/v1/auth/login", json={"email": "staff@x.example", "password": "staff-password-1"}
    )
    resp = await client.post("/api/v1/auth/invites", json={"email": "x@y.example", "role": "staff"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_password_reset_flow(
    db_session: AsyncSession, app, client: AsyncClient, multi_tenant
) -> None:
    await client.post("/api/v1/auth/register", json=REG)
    await client.post("/api/v1/auth/logout")

    forgot = await client.post("/api/v1/auth/password/forgot", json={"email": REG["email"]})
    token = forgot.json()["dev_token"]
    assert token

    reset = await client.post(
        "/api/v1/auth/password/reset", json={"token": token, "password": "brand-new-password-9"}
    )
    assert reset.status_code == 200

    # Old password no longer works; new one does.
    assert (
        await client.post(
            "/api/v1/auth/login", json={"email": REG["email"], "password": REG["password"]}
        )
    ).status_code == 401
    assert (
        await client.post(
            "/api/v1/auth/login",
            json={"email": REG["email"], "password": "brand-new-password-9"},
        )
    ).status_code == 200


@pytest.mark.asyncio
async def test_csrf_required_on_mutating_request(
    db_session: AsyncSession, app, client: AsyncClient, multi_tenant
) -> None:
    await client.post("/api/v1/auth/register", json=REG)
    # A mutating non-auth request with a session cookie but no CSRF header → 403.
    body = {
        "display_name": "हल्दी",
        "source_lang": "hi",
        "category": "spice",
        "default_unit": "kg",
        "purchase_frequency": "monthly",
    }
    no_csrf = await client.post("/api/v1/ingredients", json=body)
    assert no_csrf.status_code == 403
    assert no_csrf.json()["title"] == "CSRF check failed"

    # With the matching X-CSRF-Token header it passes the CSRF gate.
    csrf = client.cookies.get(CSRF_COOKIE)
    ok = await client.post("/api/v1/ingredients", json=body, headers={CSRF_HEADER: csrf})
    assert ok.status_code == 201, ok.text


@pytest.mark.asyncio
async def test_password_policy_min_length(
    db_session: AsyncSession, app, client: AsyncClient, multi_tenant
) -> None:
    resp = await client.post("/api/v1/auth/register", json={**REG, "password": "short"})
    assert resp.status_code == 422  # < 10 chars rejected


@pytest.mark.asyncio
async def test_login_rate_limited(
    db_session: AsyncSession, app, client: AsyncClient, multi_tenant
) -> None:
    from app.core.limiter import limiter

    limiter.reset()
    limiter.enabled = True
    try:
        codes = []
        for _ in range(7):
            r = await client.post(
                "/api/v1/auth/login", json={"email": "x@y.example", "password": "nope-123456"}
            )
            codes.append(r.status_code)
        assert 429 in codes  # 5/min limit trips
    finally:
        limiter.enabled = False


@pytest.mark.asyncio
async def test_register_disabled_without_multi_tenant(
    db_session: AsyncSession, app, client: AsyncClient
) -> None:
    # settings.multi_tenant is False here (no fixture) → registration forbidden.
    resp = await client.post("/api/v1/auth/register", json=REG)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_no_jwt_in_body(
    db_session: AsyncSession, app, client: AsyncClient, multi_tenant
) -> None:
    resp = await client.post("/api/v1/auth/register", json=REG)
    body = resp.json()
    # Only {ok, dev_token} — never the access/refresh token material.
    assert set(body.keys()) <= {"ok", "dev_token"}
    assert str(uuid.UUID(int=0)) not in resp.text  # sanity: no obvious token leak
