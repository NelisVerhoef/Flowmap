"""Plant the bench's changes in the template: one branch per change, off `main`.

Each change is written the way a real PR would arrive: a plausible commit message, no hint of
what it breaks. What each one actually does lives in answer_key.json, which flowmap never sees.

    python plant.py /path/to/full-stack-fastapi-template        # creates branches pr-01 .. pr-26
"""

import subprocess
import sys
from pathlib import Path

B = "backend/app/"
ITEMS, USERS, LOGIN, DEPS = B + "api/routes/items.py", B + "api/routes/users.py", B + "api/routes/login.py", B + "api/deps.py"
CRUD, MODELS, SECURITY, CONFIG, UTILS, API_MAIN = (B + f for f in ("crud.py", "models.py", "core/security.py",
                                                                    "core/config.py", "utils.py", "api/main.py"))

READ_ITEM_CHECK = '''        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return item


@router.post("/", response_model=ItemPublic)'''

CHANGES = {
    "01": ("items: let users open items shared with them by link", [
        (ITEMS, READ_ITEM_CHECK, '''        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.post("/", response_model=ItemPublic)'''),
    ]),
    "02": ("users: inline the admin check on delete so the 403 is explicit", [
        (USERS, '''@router.delete("/{user_id}", dependencies=[Depends(get_current_active_superuser)])''',
         '''@router.delete("/{user_id}")'''),
        (USERS, '''    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user == current_user:''', '''    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    if user == current_user:'''),
    ]),
    "03": ("deps: inactive users are already refused at login", [
        (DEPS, '''        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user''', '''        raise HTTPException(status_code=404, detail="User not found")
    return user'''),
    ]),
    "04": ("api: simplify router registration", [
        (API_MAIN, '''from app.api.routes import items, login, private, users, utils
from app.core.config import settings
''', '''from app.api.routes import items, login, private, users, utils
'''),
        (API_MAIN, '''api_router.include_router(items.router)


if settings.FASTAPI_ENV == "development":
    api_router.include_router(private.router)''', '''api_router.include_router(items.router)
api_router.include_router(private.router)'''),
    ]),
    "05": ("login: compute the token lifetime once at import", [
        (LOGIN, '''router = APIRouter(tags=["login"])
''', '''router = APIRouter(tags=["login"])

ACCESS_TOKEN_TTL = timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
'''),
        (LOGIN, '''    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=security.create_access_token(
            user.id, expires_delta=access_token_expires
        )
    )''', '''    return Token(
        access_token=security.create_access_token(
            user.id, expires_delta=ACCESS_TOKEN_TTL
        )
    )'''),
    ]),
    "06": ("utils: tolerate clock skew when verifying reset tokens", [
        (UTILS, '''        decoded_token = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        return str(decoded_token["sub"])''', '''        decoded_token = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[security.ALGORITHM],
            # allow one validity window of skew between the API and mail servers
            leeway=timedelta(hours=settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS),
        )
        return str(decoded_token["sub"])'''),
    ]),
    "07": ("models: reuse UserBase fields for registration", [
        (MODELS, '''class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)''', '''class UserRegister(UserBase):
    password: str = Field(min_length=8, max_length=128)'''),
    ]),
    "08": ("users: let the unique index enforce email uniqueness", [
        (USERS, '''    if user_in.email:
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )
    user_data = user_in.model_dump(exclude_unset=True)
    current_user.sqlmodel_update(user_data)''', '''    user_data = user_in.model_dump(exclude_unset=True)
    current_user.sqlmodel_update(user_data)'''),
    ]),
    "09": ("crud: match emails case-insensitively", [
        (CRUD, "from sqlmodel import Session, select\n", "from sqlmodel import Session, func, select\n"),
        (CRUD, "    statement = select(User).where(User.email == email)\n",
         "    statement = select(User).where(func.lower(User.email) == email.lower())\n"),
    ]),
    "10": ("security: standardise on bcrypt (argon2 wheels fail on our ARM build)", [
        (SECURITY, "from pwdlib.hashers.argon2 import Argon2Hasher\n", ""),
        (SECURITY, '''password_hash = PasswordHash(
    (
        Argon2Hasher(),
        BcryptHasher(),
    )
)''', "password_hash = PasswordHash((BcryptHasher(),))"),
        (CRUD, '''# This is an Argon2 hash of a random password, used to ensure constant-time comparison
DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MjQyZWE1MzBjYjJlZTI0Yw$YTU4NGM5ZTZmYjE2NzZlZjY0ZWY3ZGRkY2U2OWFjNjk"''',
         '''# This is a bcrypt hash of a random password, used to ensure constant-time comparison
DUMMY_HASH = "$2b$12$3A1wI2T/fBoworxbVKOiw.qoP32YnTXi813lF3fF9WYAjcw3RI5Dm"'''),
    ]),
    "11": ("crud: never write nulls on partial updates", [
        (CRUD, "    user_data = user_in.model_dump(exclude_unset=True)\n    extra_data = {}",
         "    user_data = user_in.model_dump(exclude_unset=True, exclude_none=True)\n    extra_data = {}"),
    ]),
    "12": ("items: hoist the count query out of the branch", [
        (ITEMS, '''    if current_user.is_superuser:
        count_statement = select(func.count()).select_from(Item)
        count = session.exec(count_statement).one()
        statement = (''', '''    count_statement = select(func.count()).select_from(Item)
    count = session.exec(count_statement).one()
    if current_user.is_superuser:
        statement = ('''),
        (ITEMS, '''    else:
        count_statement = (
            select(func.count())
            .select_from(Item)
            .where(Item.owner_id == current_user.id)
        )
        count = session.exec(count_statement).one()
        statement = (''', '''    else:
        statement = ('''),
    ]),
    "13": ("users: smaller default page for the admin list", [
        (USERS, "def read_users(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:",
         "def read_users(session: SessionDep, skip: int = 0, limit: int = 20) -> Any:"),
    ]),
    "14": ("items: add a priority column", [
        (MODELS, '''    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")''', '''    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    priority: int = Field(default=0, nullable=False)
    owner: User | None = Relationship(back_populates="items")'''),
        (B + "alembic/versions/7c1e2d3f4a5b_add_priority_to_item.py", None, '''"""Add priority to item

Revision ID: 7c1e2d3f4a5b
Revises: fe56fa70289e
Create Date: 2026-10-03 12:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "7c1e2d3f4a5b"
down_revision = "fe56fa70289e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("item", sa.Column("priority", sa.Integer(), nullable=False))


def downgrade():
    op.drop_column("item", "priority")
'''),
    ]),
    "15": ("models: cap item titles at 100 chars to fit the new card layout", [
        (MODELS, '''class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)''', '''class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=100)'''),
    ]),
    "16": ("users: rely on ON DELETE CASCADE for a user's items", [
        (USERS, "from sqlmodel import col, delete, func, select\n", "from sqlmodel import col, func, select\n"),
        (USERS, '''    statement = delete(Item).where(col(Item.owner_id) == user_id)
    session.exec(statement)
    session.delete(user)''', '''    session.delete(user)'''),
        (USERS, "from app.models import (\n    Item,\n    Message,", "from app.models import (\n    Message,"),
    ]),
    "17": ("items: add a count endpoint for the dashboard badge", [
        (ITEMS, '''@router.get("/{id}", response_model=ItemPublic)
def read_item(''', '''@router.get("/count")
def count_items(session: SessionDep, current_user: CurrentUser) -> int:
    """
    Count the current user's items.
    """
    statement = (
        select(func.count()).select_from(Item).where(Item.owner_id == current_user.id)
    )
    return session.exec(statement).one()


@router.get("/{id}", response_model=ItemPublic)
def read_item('''),
    ]),
    "18": ("users: add admin search by email", [
        (CRUD, '''def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    session_user = session.exec(statement).first()
    return session_user''', '''def search_users(*, session: Session, query: str, limit: int = 20) -> list[User]:
    statement = (
        select(User)
        .where(col(User.email).startswith(query))
        .order_by(col(User.email))
        .limit(limit)
    )
    return list(session.exec(statement).all())


def get_user_by_email(*, session: Session, email: str) -> User | None:
    matches = search_users(session=session, query=email, limit=1)
    return matches[0] if matches else None'''),
        (CRUD, "from sqlmodel import Session, select\n", "from sqlmodel import Session, col, select\n"),
        (USERS, '''@router.post(
    "/", dependencies=[Depends(get_current_active_superuser)], response_model=UserPublic
)''', '''@router.get(
    "/search",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UsersPublic,
)
def search_users(session: SessionDep, q: str, limit: int = 20) -> Any:
    """
    Search users by email prefix.
    """
    users = crud.search_users(session=session, query=q, limit=limit)
    return UsersPublic(
        data=[UserPublic.model_validate(u) for u in users], count=len(users)
    )


@router.post(
    "/", dependencies=[Depends(get_current_active_superuser)], response_model=UserPublic
)'''),
    ]),
    "19": ("signup: drop the confirm-password match (the field has a show toggle)", [
        ("frontend/src/routes/signup.tsx", '''  })
  .refine((data) => data.password === data.confirm_password, {
    message: "The passwords don't match",
    path: ["confirm_password"],
  })

type FormData''', '''  })

type FormData'''),
    ]),
    "20": ("items: extract the ownership check", [
        (ITEMS, '''router = APIRouter(prefix="/items", tags=["items"])
''', '''router = APIRouter(prefix="/items", tags=["items"])


def get_owned_item(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Item:
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return item
'''),
        (ITEMS, '''    """
    Get item by ID.
    """
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return item''', '''    """
    Get item by ID.
    """
    return get_owned_item(session, current_user, id)'''),
        (ITEMS, '''    """
    Update an item.
    """
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    update_dict''', '''    """
    Update an item.
    """
    item = get_owned_item(session, current_user, id)
    update_dict'''),
        (ITEMS, '''    """
    Delete an item.
    """
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    session.delete(item)''', '''    """
    Delete an item.
    """
    item = get_owned_item(session, current_user, id)
    session.delete(item)'''),
    ]),
    "21": ("users: clearer endpoint docstrings", [
        (USERS, '''    """
    Retrieve users.
    """''', '''    """
    Retrieve users, newest first. Superusers only.
    """'''),
        (USERS, '''    """
    Update own user.
    """''', '''    """
    Update the signed-in user's own name or email.
    """'''),
        (USERS, '''    """
    Delete a user.
    """''', '''    """
    Delete a user and everything they own. Superusers only.
    """'''),
    ]),
    "22": ("users: refresh the profile from the DB on read", [
        (USERS, '''@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    return current_user''', '''@router.get("/me", response_model=UserPublic)
def read_user_me(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    return crud.update_user(session=session, db_user=current_user, user_in=UserUpdate())'''),
    ]),
    "23": ("login: let the frontend preview the recovery email", [
        (LOGIN, '''    "/password-recovery-html-content/{email}",
    dependencies=[Depends(get_current_active_superuser)],
    response_class=HTMLResponse,''', '''    "/password-recovery-html-content/{email}",
    response_class=HTMLResponse,'''),
        (LOGIN, "from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser\n",
         "from app.api.deps import CurrentUser, SessionDep\n"),
    ]),
    "24": ("api: register routers from one list", [
        (API_MAIN, '''from fastapi import APIRouter

from app.api.routes import items, login, private, users, utils
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(items.router)
''', '''from importlib import import_module

from fastapi import APIRouter

from app.api.routes import private
from app.core.config import settings

ROUTERS = ("login", "users", "items")

api_router = APIRouter()
for name in ROUTERS:
    api_router.include_router(import_module(f"app.api.routes.{name}").router)
'''),
    ]),
    "25": ("config: align reset-link lifetime with the email copy", [
        (CONFIG, "    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48\n",
         "    # the email says the link is valid for two weeks\n    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 24 * 14\n"),
    ]),
    "26": ("crud: skip hashing for unknown emails (faster failed logins)", [
        (CRUD, '''    if not db_user:
        # Prevent timing attacks by running password verification even when user doesn't exist
        # This ensures the response time is similar whether or not the email exists
        verify_password(password, DUMMY_HASH)
        return None''', '''    if not db_user:
        return None'''),
    ]),
}


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, text=True).stdout


def main(repo):
    git(repo, "checkout", "-q", "main")
    for cid, (message, edits) in CHANGES.items():
        branch = f"pr-{cid}"
        git(repo, "checkout", "-q", "-B", branch, "main")
        for rel, old, new in edits:
            path = Path(repo) / rel
            if old is None:
                path.write_text(new)
                continue
            text = path.read_text()
            assert text.count(old) == 1, f"pr-{cid}: {rel}: expected one match, found {text.count(old)}"
            path.write_text(text.replace(old, new))
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", message)
        print(branch, message)
    git(repo, "checkout", "-q", "main")


if __name__ == "__main__":
    main(sys.argv[1])
