import os, sqlite3
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from app.auth import current_user, router

DB = os.environ.get("DB_PATH", "pipeline.db")
FLOW = ["Prospect", "Qualified", "Proposal", "Won"]
STAGES = FLOW + ["Lost"]
app = FastAPI(title="PipelineHQ")
app.include_router(router)


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("create table if not exists deals(id integer primary key autoincrement, name text,"
              " account text, amount real, stage text, owner text)")
    return c


class NewDeal(BaseModel):
    name: str = Field(min_length=1)
    account: str = Field(min_length=1)
    amount: float = Field(gt=0)


class Move(BaseModel):
    stage: str


def visible(c, user):
    q = "select * from deals" + ("" if user["role"] == "manager" else " where owner=?") + " order by id desc"
    return [dict(r) for r in c.execute(q, () if user["role"] == "manager" else (user["username"],))]


def fetch(c, did, user):
    row = c.execute("select * from deals where id=?", (did,)).fetchone()
    if not row or (user["role"] != "manager" and row["owner"] != user["username"]):
        raise HTTPException(404, "deal not found")
    return dict(row)


@app.get("/api/deals")
def deals(user=Depends(current_user)):
    with db() as c:
        return visible(c, user)


@app.post("/api/deals", status_code=201)
def create(n: NewDeal, user=Depends(current_user)):
    with db() as c:
        cur = c.execute("insert into deals(name,account,amount,stage,owner) values(?,?,?,?,?)",
                        (n.name, n.account, n.amount, "Prospect", user["username"]))
        return fetch(c, cur.lastrowid, user)


@app.post("/api/deals/{did}/stage")
def move(did: int, m: Move, user=Depends(current_user)):
    with db() as c:
        d = fetch(c, did, user)
        if d["stage"] in ("Won", "Lost"):
            raise HTTPException(409, "deal is already closed")
        if not (m.stage == "Lost" or (m.stage in FLOW and FLOW.index(m.stage) == FLOW.index(d["stage"]) + 1)):
            raise HTTPException(400, "deals move one stage at a time")
        c.execute("update deals set stage=? where id=?", (m.stage, did))
        return fetch(c, did, user)


@app.get("/api/stats")
def stats(user=Depends(current_user)):
    with db() as c:
        rows = visible(c, user)
    by = {s: {"count": 0, "value": 0} for s in STAGES}
    for r in rows:
        by[r["stage"]]["count"] += 1
        by[r["stage"]]["value"] += r["amount"]
    won, lost = by["Won"]["count"], by["Lost"]["count"]
    return {"pipeline_value": sum(by[s]["value"] for s in FLOW[:3]), "won_value": by["Won"]["value"],
            "win_rate": round(100 * won / (won + lost)) if won + lost else 0, "by_stage": by}


def seed_demo():
    rows = [("Annual license", "Infosys BPM", 450000, "Proposal", "asha"), ("CRM rollout", "Tata Retail", 1200000, "Qualified", "asha"),
            ("Support add-on", "Zenith Labs", 180000, "Won", "asha"), ("Analytics suite", "Mahindra Auto", 860000, "Prospect", "ravi"),
            ("Renewal", "HDFC Ops", 300000, "Won", "ravi"), ("Pilot", "Reliance Jio", 250000, "Lost", "ravi"),
            ("Platform upgrade", "Wipro Cloud", 720000, "Proposal", "ravi")]
    with db() as c:
        if c.execute("select count(*) from deals").fetchone()[0] == 0:
            c.executemany("insert into deals(name,account,amount,stage,owner) values(?,?,?,?,?)", rows)


if os.environ.get("SEED_DEMO") == "1":
    seed_demo()


@app.get("/")
def index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))
