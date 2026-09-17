import os
import tempfile
from pathlib import Path

import pytest

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "sqlite:///" + str(Path(tempfile.mkdtemp()) / "test.db")
)
if not (
    os.environ["DATABASE_URL"].startswith("sqlite:")
    or os.environ["DATABASE_URL"].rstrip("/").endswith("_test")
):
    raise RuntimeError(
        "TEST_DATABASE_URL must point to a disposable database ending in _test"
    )
os.environ["JWT_SECRET"] = "test-only-secret-not-for-deployment-0000000000"
os.environ["ADMIN_PASSWORD"] = "Test-password-for-suite-123"
os.environ["ADMIN_EMAIL"] = "admin@example.com"
os.environ["STORAGE_DIR"] = tempfile.mkdtemp(prefix="atlas-test-files-")
os.environ["AI_API_KEY"] = ""
from fastapi.testclient import TestClient

from app.auth import attempts
from app.bootstrap import bootstrap
from app.db import Base, engine
from app.main import app


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    bootstrap()
    attempts.clear()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def admin(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": os.environ["ADMIN_PASSWORD"]},
    )
    assert response.status_code == 200
    return client
