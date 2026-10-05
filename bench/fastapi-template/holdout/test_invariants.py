import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from conftest import API, auth, sql
from seed import ITEM_ID, LONG_TITLE, USER_ID, USERS

ep = pytest.mark.endpoints
ALICE, BOB, CAROL, DAN, EVE = (f"{n}@example.com" for n in ("alice", "bob", "carol", "dan", "eve"))
ADMIN = "admin@example.com"


def login(client, email, password):
    return client.post(f"{API}/login/access-token", data={"username": email, "password": password})


# --- signing in -------------------------------------------------------------------------

@ep("POST /login/access-token")
@pytest.mark.parametrize("email", [ADMIN, ALICE, BOB])
def test_existing_users_can_still_log_in(client, email):
    r = login(client, email, USERS[email][0])
    assert r.status_code == 200, r.text


@ep("POST /login/access-token")
def test_wrong_password_and_unknown_email_fail_cleanly(client):
    assert login(client, ALICE, "not-her-password").status_code == 400
    assert login(client, "nobody@example.com", "whatever-123").status_code == 400


@ep("POST /login/access-token")
def test_inactive_user_cannot_log_in(client):
    assert login(client, CAROL, USERS[CAROL][0]).status_code == 400


@ep("POST /login/access-token")
def test_login_does_not_match_an_email_prefix(client):
    # dan@example.co doesn't exist; dan@example.com does
    assert login(client, "dan@example.co", USERS[DAN][0]).status_code == 400


@ep("POST /login/access-token")
def test_access_token_lives_eight_days(client):
    r = login(client, BOB, USERS[BOB][0])
    exp = jwt.decode(r.json()["access_token"], options={"verify_signature": False})["exp"]
    left = datetime.fromtimestamp(exp, UTC) - datetime.now(UTC)
    assert timedelta(days=8, hours=-1) < left < timedelta(days=8, hours=1)


@ep("GET /users/me", "GET /items/")
def test_deactivated_users_token_stops_working(client):
    assert client.get(f"{API}/users/me", headers=auth(CAROL)).status_code != 200
    assert client.get(f"{API}/items/", headers=auth(CAROL)).status_code != 200


# --- who may call what ------------------------------------------------------------------

PROTECTED = [
    ("GET", "/items/"), ("POST", "/items/"), ("GET", "/items/{item}"), ("PUT", "/items/{item}"),
    ("DELETE", "/items/{item}"), ("POST", "/login/test-token"), ("GET", "/users/"), ("POST", "/users/"),
    ("GET", "/users/me"), ("PATCH", "/users/me"), ("DELETE", "/users/me"), ("PATCH", "/users/me/password"),
    ("GET", "/users/{user}"), ("PATCH", "/users/{user}"), ("DELETE", "/users/{user}"),
    ("POST", "/password-recovery-html-content/{email}"), ("POST", "/utils/test-email/"),
]


def fill(path):
    return path.format(item=ITEM_ID["bob-1"], user=USER_ID[BOB], email=BOB, victim=USER_ID["user00@example.com"])


def inventory_ep(method, path):
    path = path.replace("{item}", "{id}").replace("{user}", "{user_id}").replace("{victim}", "{user_id}")
    return f"{method} {path}"


@pytest.mark.parametrize("method,path", [pytest.param(m, p, marks=ep(inventory_ep(m, p)), id=f"{m} {p}")
                                         for m, p in PROTECTED])
def test_anonymous_requests_are_rejected(client, method, path):
    r = client.request(method, f"{API}{fill(path)}", params={"email_to": "x@example.com"}, json={})
    assert r.status_code in (401, 403), r.text


ADMIN_ONLY = [
    ("GET", "/users/", None), ("POST", "/users/", {"email": "new@example.com", "password": "new-pass-123"}),
    ("PATCH", "/users/{user}", {"full_name": "pwned"}), ("DELETE", "/users/{victim}", None),
    ("GET", "/users/{user}", None), ("POST", "/password-recovery-html-content/{email}", None),
    ("POST", "/utils/test-email/", None),
]


@pytest.mark.parametrize("method,path,body", [pytest.param(m, p, b, marks=ep(inventory_ep(m, p)), id=f"{m} {p}")
                                              for m, p, b in ADMIN_ONLY])
def test_normal_users_cannot_use_admin_endpoints(client, method, path, body):
    r = client.request(method, f"{API}{fill(path)}", headers=auth(ALICE),
                       params={"email_to": "x@example.com"}, json=body)
    assert r.status_code == 403, r.text
    assert sql('SELECT full_name FROM "user" WHERE id = %s', USER_ID[BOB]) == [("Bob",)]


@pytest.mark.parametrize("method", [pytest.param(m, marks=ep(f"{m} /items/{{id}}"), id=m)
                                    for m in ("GET", "PUT", "DELETE")])
def test_users_cannot_touch_each_others_items(client, method):
    r = client.request(method, f"{API}/items/{ITEM_ID['bob-1']}", headers=auth(ALICE), json={"title": "mine now"})
    assert r.status_code == 403, r.text
    assert sql("SELECT title FROM item WHERE id = %s", ITEM_ID["bob-1"]) == [("Bob's item",)]


@ep("GET /items/{id}")
def test_superuser_can_read_any_item(client):
    assert client.get(f"{API}/items/{ITEM_ID['alice-1']}", headers=auth(ADMIN)).status_code == 200


@ep("GET /items/")
def test_item_list_and_count_are_scoped_to_the_owner(client):
    body = client.get(f"{API}/items/", headers=auth(ALICE)).json()
    assert body["count"] == 2
    assert {i["owner_id"] for i in body["data"]} == {str(USER_ID[ALICE])}


@ep("POST /users/signup")
def test_signup_cannot_grant_superuser(client):
    r = client.post(f"{API}/users/signup", json={"email": "mallory@example.com", "password": "mallory-pass",
                                                 "full_name": "Mallory", "is_superuser": True})
    assert r.status_code == 200, r.text
    assert sql('SELECT is_superuser FROM "user" WHERE email = %s', "mallory@example.com") == [(False,)]


@ep("POST /private/users/")
def test_private_api_is_not_mounted_in_production():
    # Settings also reads ../.env (FASTAPI_ENV=development), so run from a dir where that misses
    env = {k: v for k, v in os.environ.items() if k != "FASTAPI_ENV"}
    env.update(SECRET_KEY="prod-secret-key", FIRST_SUPERUSER_PASSWORD="prod-admin-pass",
               DATABASE_URL="postgresql://postgres:prod-db-pass@localhost:5432/app_prod",
               PYTHONPATH=os.getcwd())
    # the API router, not app.main: outside development app.main also needs a built frontend
    code = ("from app.api.main import api_router as r; "
            "print(sorted(p for x in r.routes for p in (getattr(getattr(x, 'original_router', None), 'prefix', ''),"
            " getattr(x, 'path', '')) if '/private' in p))")
    out = subprocess.run([sys.executable, "-c", code], env=env, cwd="/", capture_output=True, text=True)
    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.strip() == "[]"


# --- existing data and API contracts --------------------------------------------------------

@ep("GET /items/", "GET /items/{id}")
def test_existing_items_with_long_titles_stay_readable(client):
    assert client.get(f"{API}/items/", headers=auth(ALICE)).status_code == 200
    r = client.get(f"{API}/items/{ITEM_ID['alice-long']}", headers=auth(ALICE))
    assert r.status_code == 200 and r.json()["title"] == LONG_TITLE


@ep("GET /users/me", "GET /items/")
def test_response_shapes_are_unchanged(client):
    me = client.get(f"{API}/users/me", headers=auth(ALICE)).json()
    assert set(me) == {"email", "is_active", "is_superuser", "full_name", "id", "created_at"}
    item = client.get(f"{API}/items/", headers=auth(ALICE)).json()["data"][0]
    assert set(item) == {"title", "description", "id", "owner_id", "created_at"}


@ep("GET /users/")
def test_admin_user_list_default_page_returns_everyone(client):
    body = client.get(f"{API}/users/", headers=auth(ADMIN)).json()
    assert body["count"] >= len(USERS) and len(body["data"]) == body["count"]


@ep("PATCH /users/me")
def test_cannot_take_another_users_email(client):
    r = client.patch(f"{API}/users/me", headers=auth(ALICE), json={"email": BOB})
    assert r.status_code == 409, r.text


@ep("PATCH /users/{user_id}")
def test_admin_can_clear_a_users_full_name(client):
    r = client.patch(f"{API}/users/{USER_ID[BOB]}", headers=auth(ADMIN), json={"full_name": None})
    assert r.status_code == 200 and r.json()["full_name"] is None
    sql('UPDATE "user" SET full_name = %s WHERE id = %s RETURNING id', "Bob", USER_ID[BOB])


@ep("DELETE /users/{user_id}")
def test_admin_delete_removes_the_users_items(client):
    r = client.delete(f"{API}/users/{USER_ID[EVE]}", headers=auth(ADMIN))
    assert r.status_code == 200, r.text
    assert sql("SELECT count(*) FROM item WHERE owner_id = %s", USER_ID[EVE]) == [(0,)]


@ep("POST /users/signup", "POST /login/access-token")
def test_new_signups_can_log_in(client):
    r = client.post(f"{API}/users/signup", json={"email": "newbie@example.com", "password": "newbie-pass-1"})
    assert r.status_code == 200, r.text
    assert login(client, "newbie@example.com", "newbie-pass-1").status_code == 200


@ep("GET /utils/health-check/")
def test_health_check(client):
    r = client.get(f"{API}/utils/health-check/")
    assert r.status_code == 200 and r.json() is True


# --- password recovery ---------------------------------------------------------------------

def reset_token(email, **delta):
    now = datetime.now(UTC)
    return jwt.encode({"exp": (now + timedelta(**delta)).timestamp(), "nbf": now - timedelta(minutes=1), "sub": email},
                      os.environ["SECRET_KEY"], algorithm="HS256")


@ep("POST /reset-password/")
def test_expired_reset_token_is_rejected(client):
    before = sql('SELECT hashed_password FROM "user" WHERE email = %s', ALICE)
    r = client.post(f"{API}/reset-password/", json={"token": reset_token(ALICE, hours=-1), "new_password": "hijacked-1"})
    assert r.status_code == 400
    assert sql('SELECT hashed_password FROM "user" WHERE email = %s', ALICE) == before


@ep("POST /reset-password/")
def test_reset_token_for_unknown_email_changes_nobody(client):
    before = sql('SELECT hashed_password FROM "user" WHERE email = %s', DAN)
    r = client.post(f"{API}/reset-password/", json={"token": reset_token("dan@example.co", hours=1),
                                                     "new_password": "hijacked-1"})
    assert r.status_code == 400
    assert sql('SELECT hashed_password FROM "user" WHERE email = %s', DAN) == before


@ep("POST /password-recovery/{email}")
def test_reset_links_live_48_hours():
    # upstream bug: POST /password-recovery-html-content/{email} sends a header named "subject:",
    # which the HTTP stack rejects, so read the token the recovery flow would email instead
    from app.utils import generate_password_reset_token
    exp = jwt.decode(generate_password_reset_token(BOB), options={"verify_signature": False})["exp"]
    left = datetime.fromtimestamp(exp, UTC) - datetime.now(UTC)
    assert timedelta(hours=47) < left < timedelta(hours=49)
