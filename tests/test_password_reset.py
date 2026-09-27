from __future__ import annotations

from tests.conftest import login, register_and_login


def extract_reset_token(reset_url: str) -> str:
    return reset_url.rstrip("/").split("/")[-1]


def test_password_reset_flow(client):
    register_and_login(client, "reset1@example.com", password="OldPassword1")
    client.post("/api/auth/logout")

    req_res = client.post("/api/auth/password-reset/request", json={"email": "reset1@example.com"})
    assert req_res.status_code == 200
    reset_url = req_res.json()["reset_url"]
    assert reset_url is not None
    token = extract_reset_token(reset_url)

    confirm_res = client.post(
        "/api/auth/password-reset/confirm", json={"token": token, "new_password": "NewPassword1"}
    )
    assert confirm_res.status_code == 200

    old_login = client.post("/api/auth/login", json={"email": "reset1@example.com", "password": "OldPassword1"})
    assert old_login.status_code == 401

    new_login = login(client, "reset1@example.com", password="NewPassword1")
    assert new_login["email"] == "reset1@example.com"


def test_password_reset_request_unknown_email_returns_no_url(client):
    res = client.post("/api/auth/password-reset/request", json={"email": "nobody@example.com"})
    assert res.status_code == 200
    assert res.json()["reset_url"] is None


def test_password_reset_token_cannot_be_reused(client):
    register_and_login(client, "reset2@example.com", password="OldPassword1")
    client.post("/api/auth/logout")

    req_res = client.post("/api/auth/password-reset/request", json={"email": "reset2@example.com"})
    token = extract_reset_token(req_res.json()["reset_url"])

    first = client.post("/api/auth/password-reset/confirm", json={"token": token, "new_password": "NewPassword1"})
    assert first.status_code == 200

    second = client.post("/api/auth/password-reset/confirm", json={"token": token, "new_password": "AnotherPass1"})
    assert second.status_code == 410
    assert second.json()["code"] == "PASSWORD_RESET_TOKEN_EXPIRED"


def test_password_reset_invalid_token_rejected(client):
    res = client.post(
        "/api/auth/password-reset/confirm", json={"token": "not-a-real-token", "new_password": "NewPassword1"}
    )
    assert res.status_code == 404
    assert res.json()["code"] == "PASSWORD_RESET_TOKEN_INVALID"
