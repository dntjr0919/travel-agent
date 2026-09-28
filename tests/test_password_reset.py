from __future__ import annotations

from app.routers import auth
from tests.conftest import login, register_and_login


def extract_reset_token(reset_url: str) -> str:
    return reset_url.rstrip("/").split("/")[-1]


def test_password_reset_flow(client, monkeypatch):
    sent_messages: list[tuple[str, str]] = []

    def fake_send_password_reset_email(to_email: str, reset_url: str) -> None:
        sent_messages.append((to_email, reset_url))

    monkeypatch.setattr(
        auth,
        "send_password_reset_email",
        fake_send_password_reset_email,
    )

    register_and_login(client, "reset1@example.com", password="OldPassword1")
    client.post("/api/auth/logout")

    req_res = client.post(
        "/api/auth/password-reset/request",
        json={"email": "reset1@example.com"},
    )

    assert req_res.status_code == 200

    data = req_res.json()
    assert data["reset_url"] is None
    assert "재설정 링크를 발송했습니다" in data["detail"]

    assert len(sent_messages) == 1
    sent_to, reset_url = sent_messages[0]
    assert sent_to == "reset1@example.com"

    token = extract_reset_token(reset_url)

    confirm_res = client.post(
        "/api/auth/password-reset/confirm",
        json={"token": token, "new_password": "NewPassword1"},
    )
    assert confirm_res.status_code == 200

    login_res = client.post(
        "/api/auth/login",
        json={"email": "reset1@example.com", "password": "NewPassword1"},
    )
    assert login_res.status_code == 200


def test_password_reset_request_hides_unknown_email(client, monkeypatch):
    sent_messages: list[tuple[str, str]] = []

    def fake_send_password_reset_email(to_email: str, reset_url: str) -> None:
        sent_messages.append((to_email, reset_url))

    monkeypatch.setattr(
        auth,
        "send_password_reset_email",
        fake_send_password_reset_email,
    )

    res = client.post(
        "/api/auth/password-reset/request",
        json={"email": "unknown@example.com"},
    )

    assert res.status_code == 200
    assert res.json()["reset_url"] is None
    assert "재설정 링크를 발송했습니다" in res.json()["detail"]
    assert sent_messages == []


def test_password_reset_token_cannot_be_reused(client, monkeypatch):
    sent_messages: list[tuple[str, str]] = []

    def fake_send_password_reset_email(to_email: str, reset_url: str) -> None:
        sent_messages.append((to_email, reset_url))

    monkeypatch.setattr(
        auth,
        "send_password_reset_email",
        fake_send_password_reset_email,
    )

    register_and_login(client, "reset2@example.com", password="OldPassword1")
    client.post("/api/auth/logout")

    req_res = client.post(
        "/api/auth/password-reset/request",
        json={"email": "reset2@example.com"},
    )

    assert req_res.status_code == 200
    assert req_res.json()["reset_url"] is None
    assert len(sent_messages) == 1

    _, reset_url = sent_messages[0]
    token = extract_reset_token(reset_url)

    first_res = client.post(
        "/api/auth/password-reset/confirm",
        json={"token": token, "new_password": "NewPassword1"},
    )
    assert first_res.status_code == 200

    second_res = client.post(
        "/api/auth/password-reset/confirm",
        json={"token": token, "new_password": "AnotherPassword1"},
    )
    assert second_res.status_code == 410
    assert second_res.json()["code"] == "PASSWORD_RESET_TOKEN_EXPIRED"