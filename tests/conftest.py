"""Each test gets a fresh database; the developer's data/app.db is never opened."""

import os
import secrets

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Set these before importing the app, independently of a developer's private .env.
os.environ["JWT_SECRET_KEY"] = secrets.token_hex(32)
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ALLOWED_HOSTS"] = '["localhost"]'

from app.database import Base, build_engine, get_db  # noqa: E402
from app.main import create_app  # noqa: E402

PASSWORD = "LearnFastAPI!2026"


@pytest.fixture
def sessions():
    # StaticPool shares the in-memory DB across TestClient's worker threads.
    engine = build_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    try:
        yield sessionmaker(bind=engine, autoflush=False)
    finally:
        engine.dispose()


@pytest.fixture
def client(sessions):
    application = create_app()

    def override_db():
        # Separate sessions per request help detect accidentally uncommitted writes.
        with sessions() as session:
            yield session

    application.dependency_overrides[get_db] = override_db
    with TestClient(application, base_url="http://localhost") as test_client:
        yield test_client
    application.dependency_overrides.clear()


@pytest.fixture
def account_factory(client):
    def create_account(username="alice"):
        response = client.post(
            "/seller",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": PASSWORD,
            },
        )
        assert response.status_code == 201, response.text
        token = client.post("/login", data={"username": username, "password": PASSWORD})
        assert token.status_code == 200, token.text
        headers = {"Authorization": f"Bearer {token.json()['access_token']}"}
        return response.json(), headers

    return create_account


@pytest.fixture
def owner(account_factory):
    return account_factory()
