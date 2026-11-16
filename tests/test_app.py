import os, tempfile
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "p.db")
os.environ["SEED_DEMO"] = "1"
import pytest
from fastapi.testclient import TestClient
from app.main import app, db, seed_demo

client = TestClient(app)


def as_(user):
    t = client.post("/api/login", json={"username": user, "password": "demo123"}).json()["token"]
    return {"Authorization": "Bearer " + t}


@pytest.fixture(autouse=True)
def clean():
    with db() as c:
        c.execute("delete from deals")


def add(user="asha", amount=1000):
    return client.post("/api/deals", json={"name": "Deal", "account": "Acme", "amount": amount}, headers=as_(user)).json()


def move(did, stage, user="asha"):
    return client.post(f"/api/deals/{did}/stage", json={"stage": stage}, headers=as_(user))


def test_requires_login():
    assert client.get("/api/deals").status_code == 401


def test_create_sets_owner_and_stage():
    d = add()
    assert d["owner"] == "asha" and d["stage"] == "Prospect"


def test_rep_sees_own_manager_sees_all():
    add("asha")
    add("ravi")
    assert len(client.get("/api/deals", headers=as_("asha")).json()) == 1
    assert len(client.get("/api/deals", headers=as_("meera")).json()) == 2


def test_other_rep_cannot_touch_deal():
    d = add("asha")
    assert move(d["id"], "Qualified", "ravi").status_code == 404


def test_forward_flow_to_won_then_closed():
    d = add()
    for s in ("Qualified", "Proposal", "Won"):
        assert move(d["id"], s).json()["stage"] == s
    assert move(d["id"], "Lost").status_code == 409


def test_cannot_skip_stage_or_use_unknown():
    d = add()
    assert move(d["id"], "Proposal").status_code == 400
    assert move(d["id"], "Banana").status_code == 400


def test_mark_lost_from_open_stage():
    d = add()
    assert move(d["id"], "Lost").json()["stage"] == "Lost"


def test_stats_win_rate_and_pipeline():
    a, b, c3 = add(amount=100), add(amount=200), add(amount=300)
    for s in ("Qualified", "Proposal", "Won"):
        move(a["id"], s)
    move(b["id"], "Lost")
    s = client.get("/api/stats", headers=as_("asha")).json()
    assert s["win_rate"] == 50 and s["won_value"] == 100 and s["pipeline_value"] == 300


def test_stats_empty_and_validation():
    assert client.get("/api/stats", headers=as_("asha")).json()["win_rate"] == 0
    r = client.post("/api/deals", json={"name": "x", "account": "y", "amount": 0}, headers=as_("asha"))
    assert r.status_code == 422


def test_seed_and_index():
    seed_demo()
    seed_demo()
    assert len(client.get("/api/deals", headers=as_("meera")).json()) == 7
    assert "PipelineHQ" in client.get("/").text
