from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import register_and_login
from tests.test_trips import create_trip


def invite_member(client: TestClient, trip_id: int, email: str, role: str) -> dict:
    res = client.post(f"/api/trips/{trip_id}/invitations", json={"email": email, "role": role})
    assert res.status_code == 201
    return res.json()


def extract_token(invite_url: str) -> str:
    return invite_url.rstrip("/").split("/")[-1]


def test_owner_can_create_editor_invitation(client):
    register_and_login(client, "owner@example.com")
    trip = create_trip(client)
    invitation = invite_member(client, trip["id"], "editor@example.com", "editor")
    assert invitation["role"] == "editor"
    assert "invite_url" in invitation


def test_invitation_schedules_email_task(client, monkeypatch):
    calls = []
    monkeypatch.setattr("app.routers.collaborations.send_invitation_email", lambda **kw: calls.append(kw))
    register_and_login(client, "owner-mail@example.com", display_name="Owner")
    trip = create_trip(client)
    invitation = invite_member(client, trip["id"], "guest-mail@example.com", "viewer")

    assert invitation["invite_url"]
    assert len(calls) == 1
    assert calls[0]["to_email"] == "guest-mail@example.com"
    assert calls[0]["invite_url"] == invitation["invite_url"]
    assert calls[0]["trip_title"] == trip["title"]
    assert calls[0]["inviter_name"] == "Owner"
    assert calls[0]["role"] == "viewer"


def test_invitation_works_when_email_disabled(client, monkeypatch):
    monkeypatch.setattr("app.services.email_service.settings.email_enabled", False)
    register_and_login(client, "owner-off@example.com")
    trip = create_trip(client)
    invitation = invite_member(client, trip["id"], "guest-off@example.com", "editor")
    assert "invite_url" in invitation


def test_invitation_email_smtp_failure_does_not_raise(monkeypatch):
    from app.services import email_service

    def boom(*args, **kwargs):
        raise OSError("smtp down")

    monkeypatch.setattr(email_service.settings, "email_enabled", True)
    monkeypatch.setattr(email_service.settings, "smtp_host", "smtp.invalid")
    monkeypatch.setattr(email_service.settings, "smtp_from_email", "from@example.com")
    monkeypatch.setattr(email_service.settings, "smtp_username", "")
    monkeypatch.setattr(email_service.smtplib, "SMTP", boom)

    email_service.send_invitation_email("to@example.com", "http://x/invitations/t", "Trip", "Owner", "editor")


def test_wrong_email_cannot_accept_invitation(client):
    register_and_login(client, "owner2@example.com")
    trip = create_trip(client)
    invitation = invite_member(client, trip["id"], "editor2@example.com", "editor")
    token = extract_token(invitation["invite_url"])
    client.post("/api/auth/logout")

    register_and_login(client, "someone-else@example.com")
    res = client.post(f"/api/invitations/{token}/accept")
    assert res.status_code == 403
    assert res.json()["code"] == "INVITATION_EMAIL_MISMATCH"


def test_matching_email_can_accept_invitation(client):
    register_and_login(client, "owner3@example.com")
    trip = create_trip(client)
    invitation = invite_member(client, trip["id"], "editor3@example.com", "editor")
    token = extract_token(invitation["invite_url"])
    client.post("/api/auth/logout")

    register_and_login(client, "editor3@example.com")
    res = client.post(f"/api/invitations/{token}/accept")
    assert res.status_code == 200
    assert res.json()["role"] == "editor"

    trip_res = client.get(f"/api/trips/{trip['id']}")
    assert trip_res.status_code == 200
    assert trip_res.json()["my_role"] == "editor"


def test_non_owner_cannot_change_member_role(client):
    register_and_login(client, "owner4@example.com")
    trip = create_trip(client)
    invitation = invite_member(client, trip["id"], "editor4@example.com", "editor")
    token = extract_token(invitation["invite_url"])
    client.post("/api/auth/logout")

    register_and_login(client, "editor4@example.com")
    client.post(f"/api/invitations/{token}/accept")

    me_res = client.get("/api/auth/me")
    editor_id = me_res.json()["id"]

    res = client.patch(f"/api/trips/{trip['id']}/members/{editor_id}", json={"role": "viewer"})
    assert res.status_code == 403
    assert res.json()["code"] == "FORBIDDEN"
