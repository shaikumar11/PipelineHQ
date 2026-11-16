import base64, hashlib, hmac, json, os, time
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

SECRET = os.environ.get("SECRET_KEY", "dev-secret").encode()


def _hash(p):
    return hashlib.pbkdf2_hmac("sha256", p.encode(), b"demo-salt", 20_000).hex()


USERS = {"meera": ("manager", _hash("demo123")), "asha": ("rep", _hash("demo123")),
         "ravi": ("rep", _hash("demo123"))}
router = APIRouter()


class Login(BaseModel):
    username: str
    password: str


def make_token(user, role, ttl=8 * 3600):
    body = base64.urlsafe_b64encode(json.dumps({"u": user, "r": role, "exp": time.time() + ttl}).encode()).decode()
    return body + "." + hmac.new(SECRET, body.encode(), hashlib.sha256).hexdigest()


def read_token(token):
    try:
        body, sig = token.split(".")
        good = hmac.new(SECRET, body.encode(), hashlib.sha256).hexdigest()
        data = json.loads(base64.urlsafe_b64decode(body))
        if hmac.compare_digest(sig, good) and data["exp"] > time.time():
            return {"username": data["u"], "role": data["r"]}
    except Exception:
        pass
    return None


def current_user(authorization: str = Header(None)):
    user = read_token((authorization or "").removeprefix("Bearer "))
    if not user:
        raise HTTPException(401, "please sign in")
    return user


@router.post("/api/login")
def login(l: Login):
    rec = USERS.get(l.username.lower())
    if not rec or not hmac.compare_digest(rec[1], _hash(l.password)):
        raise HTTPException(401, "wrong username or password")
    return {"token": make_token(l.username.lower(), rec[0]), "user": {"username": l.username.lower(), "role": rec[0]}}
