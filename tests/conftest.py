from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import email_service
from app.core.database import Base, get_db, get_settings
from app.main import app

TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(autouse=True)
def disable_email_for_tests(monkeypatch):
    # get_settings()를 직접 사용하는 코드 보호
    settings = get_settings()
    monkeypatch.setattr(settings, "email_enabled", False)

    # email_service가 모듈 수준 settings를 사용해도 실제 SMTP 발송 차단
    monkeypatch.setattr(email_service.settings, "email_enabled", False)

@pytest.fixture()
def db_session():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session, monkeypatch):
    page_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=db_session.get_bind(),
    )
    monkeypatch.setattr("app.routers.pages.SessionLocal", page_session_local)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register_and_login(client: TestClient, email: str, display_name: str = "Tester", password: str = "password123"):
    res = client.post(
        "/api/auth/register",
        json={"email": email, "display_name": display_name, "password": password},
    )
    assert res.status_code == 201
    return res.json()


def login(client: TestClient, email: str, password: str = "password123"):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()
