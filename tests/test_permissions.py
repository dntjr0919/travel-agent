from __future__ import annotations

from tests.conftest import login, register_and_login
from tests.test_invitations import extract_token, invite_member
from tests.test_trips import create_trip


def test_viewer_cannot_access_member_management_mutations(client):
    register_and_login(client, "owner@example.com")
    trip = create_trip(client)
    invitation = invite_member(client, trip["id"], "viewer@example.com", "viewer")
    token = extract_token(invitation["invite_url"])
    client.post("/api/auth/logout")

    register_and_login(client, "viewer@example.com")
    client.post(f"/api/invitations/{token}/accept")

    res = client.patch(f"/api/trips/{trip['id']}", json={"title": "Renamed"})
    assert res.status_code == 403
    assert res.json()["code"] == "FORBIDDEN"

    invite_res = client.post(f"/api/trips/{trip['id']}/invitations", json={"email": "x@example.com", "role": "editor"})
    assert invite_res.status_code == 403


def test_editor_cannot_delete_trip_or_invite(client):
    register_and_login(client, "owner2@example.com")
    trip = create_trip(client)
    invitation = invite_member(client, trip["id"], "editor@example.com", "editor")
    token = extract_token(invitation["invite_url"])
    client.post("/api/auth/logout")

    register_and_login(client, "editor@example.com")
    client.post(f"/api/invitations/{token}/accept")

    delete_res = client.delete(f"/api/trips/{trip['id']}")
    assert delete_res.status_code == 403
    assert delete_res.json()["code"] == "FORBIDDEN"

    invite_res = client.post(f"/api/trips/{trip['id']}/invitations", json={"email": "y@example.com", "role": "viewer"})
    assert invite_res.status_code == 403


def test_owner_can_remove_member(client):
    register_and_login(client, "owner3@example.com")
    trip = create_trip(client)
    invitation = invite_member(client, trip["id"], "editor2@example.com", "editor")
    token = extract_token(invitation["invite_url"])
    client.post("/api/auth/logout")

    register_and_login(client, "editor2@example.com")
    client.post(f"/api/invitations/{token}/accept")
    me = client.get("/api/auth/me").json()
    client.post("/api/auth/logout")

    login(client, "owner3@example.com")
    remove_res = client.delete(f"/api/trips/{trip['id']}/members/{me['id']}")
    assert remove_res.status_code == 204

    members = client.get(f"/api/trips/{trip['id']}/members").json()
    assert all(m["user_id"] != me["id"] for m in members)
