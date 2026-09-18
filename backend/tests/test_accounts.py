from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.db import SessionLocal
from app.models import User
from test_auctions import create_auction, property_input, add, generate

PASSWORD = "Booklet-test-password-123"


def account(admin, email):
    response = admin.post("/api/admin/users", json={"email": email, "password": PASSWORD})
    assert response.status_code == 201, response.text
    assert response.json()["role"] == "user"
    assert "password_hash" not in response.json()
    return response.json()


def login(email):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200
    assert r.json()["role"] == "user"
    return c


def test_admin_provisioning_and_author_permissions(admin):
    assert admin.get("/api/auth/me").json()["role"] == "admin"
    account(admin, "Author@example.com")
    assert admin.post("/api/admin/users", json={"email": "author@example.com", "password": PASSWORD}).status_code == 409
    assert admin.post("/api/admin/users", json={"email": "next@example.com", "password": PASSWORD, "role": "admin"}).status_code == 422
    with login("author@example.com") as user:
        assert user.get("/api/admin/users").status_code == 403
        assert user.post("/api/admin/users", json={"email": "illegal@example.com", "password": PASSWORD}).status_code == 403
        assert user.put("/api/settings", json={"organization_name": "Changed"}).status_code == 403
        assert user.post("/api/settings/logo", files={"file": ("logo.png", b"bad", "image/png")}).status_code == 403
        assert user.get("/api/settings").status_code == 200
    users = admin.get("/api/admin/users").json()
    system_admin = next(u for u in users if u["role"] == "admin")
    assert admin.patch('/api/admin/users/' + system_admin['id'], json={"is_active": False}).status_code == 403


def test_author_booklet_export_isolation_and_revocation(admin):
    owner = account(admin, "owner@example.com")
    account(admin, "other@example.com")
    with login("owner@example.com") as author, login("other@example.com") as other:
        project = create_auction(author, kind="physical")
        add(author, project, property_input())
        assert author.get(f"/api/projects/{project}/review").json()["valid"]
        booklet = generate(author, project)
        assert booklet["official_booklet"]
        approved = author.post(f"/api/outputs/{booklet['id']}/approve")
        assert approved.status_code == 200
        booklet = approved.json()
        file_id = booklet['files'][0]['id']
        download = author.get(f"/api/files/{file_id}?download=true")
        assert download.status_code == 200 and download.content.startswith(b"%PDF")
        assert other.get("/api/projects").json() == []
        for c in (other, admin):
            assert c.get(f"/api/projects/{project}").status_code == 404
            assert c.get(f"/api/files/{file_id}").status_code == 404
        assert other.patch('/api/admin/users/' + owner['id'], json={"is_active": False}).status_code == 403
        token = author.cookies.get("session")
        assert admin.patch('/api/admin/users/' + owner['id'], json={"is_active": False}).status_code == 200
        assert author.get('/api/projects').status_code == 401
        assert author.post('/api/auth/login', json={"email": owner['email'], "password": PASSWORD}).status_code == 401
        admin.patch('/api/admin/users/' + owner['id'], json={"is_active": True})
        author.cookies.set('session', token)
        assert author.get('/api/projects').status_code == 401
    with login("owner@example.com") as restored:
        assert restored.get(f"/api/projects/{project}").status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(User).where(User.email == "owner@example.com")).role == "user"
