from __future__ import annotations

from tests.conftest import register_and_login


def test_register_then_login(client):
    register_and_login(client, "alice@example.com")

    logout_res = client.post("/api/auth/logout")
    assert logout_res.status_code == 204

    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 401

    login_res = client.post(
        "/api/auth/login", json={"email": "alice@example.com", "password": "password123"}
    )
    assert login_res.status_code == 200
    assert login_res.json()["email"] == "alice@example.com"

    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 200


def test_register_duplicate_email_fails(client):
    register_and_login(client, "bob@example.com")
    res = client.post(
        "/api/auth/register",
        json={"email": "bob@example.com", "display_name": "Bob2", "password": "password123"},
    )
    assert res.status_code == 409
    assert res.json()["code"] == "EMAIL_ALREADY_EXISTS"


def test_login_wrong_password_fails(client):
    register_and_login(client, "carol@example.com")
    client.post("/api/auth/logout")
    res = client.post("/api/auth/login", json={"email": "carol@example.com", "password": "wrongpass"})
    assert res.status_code == 401
    assert res.json()["code"] == "INVALID_CREDENTIALS"
