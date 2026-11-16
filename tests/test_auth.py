import os, tempfile
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "a.db")
from fastapi.testclient import TestClient
from app.auth import make_token, read_token
from app.main import app

c = TestClient(app)


def test_login_ok():
    r = c.post("/api/login", json={"username": "asha", "password": "demo123"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "rep"


def test_bad_password():
    assert c.post("/api/login", json={"username": "asha", "password": "nope"}).status_code == 401


def test_token_tamper_and_expiry():
    t = make_token("asha", "rep")
    assert read_token(t)["username"] == "asha"
    assert read_token(t[:-2] + "xx") is None
    assert read_token(make_token("a", "rep", ttl=-1)) is None
    assert read_token("garbage") is None
