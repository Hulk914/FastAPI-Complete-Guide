"""Configuration and safe HTTP behavior at the application boundary."""

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.database import get_db


@pytest.mark.parametrize("secret", ["short", "replace-with-a-generated-secret-key"])
def test_weak_or_placeholder_signing_secret_is_rejected(secret):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, jwt_secret_key=secret)


@pytest.mark.parametrize("hosts", [[], ["*"]])
def test_host_configuration_requires_explicit_hosts(hosts):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, jwt_secret_key="x" * 64, allowed_hosts=hosts)


def test_health_checks_database_and_untrusted_host_is_rejected(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/health", headers={"Host": "attacker.example"}).status_code == 400


def test_database_error_does_not_expose_internal_details(client):
    def unavailable_db():
        raise OperationalError("SELECT sensitive_table", {}, Exception("private database error"))

    client.app.dependency_overrides[get_db] = unavailable_db
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert "sensitive_table" not in response.text


def test_openapi_describes_bearer_authentication(client):
    schema = client.get("/openapi.json").json()
    scheme = schema["components"]["securitySchemes"]["OAuth2PasswordBearer"]
    assert scheme["flows"]["password"]["tokenUrl"] == "login"
    assert schema["paths"]["/product"]["post"]["security"] == [{"OAuth2PasswordBearer": []}]
