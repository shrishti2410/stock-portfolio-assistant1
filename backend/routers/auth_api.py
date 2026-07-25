"""
auth_api.py — multi-user authentication endpoints (prefix /api/auth).

  POST   /api/auth/login          -> {username, password} -> sets `session` cookie, {user}
  POST   /api/auth/logout         -> clears session + cookie
  GET    /api/auth/me             -> current user (401 if not authenticated)
  POST   /api/auth/password       -> {current_password, new_password} for self
  GET    /api/auth/users          -> admin-only: list users
  POST   /api/auth/users          -> admin-only: create user
  DELETE /api/auth/users/{id}     -> admin-only: delete user

NOTE: this router intentionally does NOT include the legacy Zerodha OAuth
routes (login URL / callback / status / logout) — those now live under
/api/zerodha/* in main.py. This router owns /api/auth/* exclusively.

Auth model: a small dependency (get_current_user) reads `request.state.user`,
which the app-level auth middleware (see main.py) guarantees is populated
for any authenticated request to a protected /api/* path. /api/auth/login
itself is allowlisted in that middleware (you can't be authenticated yet).
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from auth import service

router = APIRouter(prefix="/api/auth", tags=["auth"])

SESSION_COOKIE = "session"
SESSION_DAYS = 30


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_current_user(request: Request) -> dict:
    """
    Return the authenticated user for this request.

    The auth middleware in main.py attaches `request.state.user` for every
    protected /api/* path before the route handler ever runs, so in practice
    this dependency simply surfaces that value — the 401 branch here is a
    defensive fallback in case this dependency is ever reused somewhere the
    middleware didn't run.
    """
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_admin(request: Request) -> dict:
    """Like get_current_user, but additionally requires is_admin=True (else 403)."""
    user = get_current_user(request)
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    username: str
    password: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    display_name: str | None = None
    is_admin: bool = False


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Login / logout / me
# ---------------------------------------------------------------------------


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response):
    """Authenticate + set an HttpOnly session cookie. 401 on bad credentials."""
    user = await service.authenticate(body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = await service.create_session(user["id"], days=SESSION_DAYS)

    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=SESSION_DAYS * 24 * 3600,
        secure=(request.url.scheme == "https"),
    )
    return {"user": user}


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Delete the current session (if any) and clear the cookie."""
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await service.delete_session(token)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"status": "logged out"}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    """Return the current authenticated user, or 401."""
    return {"user": user}


# ---------------------------------------------------------------------------
# Self-service password change
# ---------------------------------------------------------------------------


@router.post("/password")
async def change_password(body: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    """Change the current user's own password (verifies current_password first)."""
    verified = await service.authenticate(user["username"], body.current_password)
    if not verified:
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    await service.change_password(user["id"], body.new_password)
    return {"status": "password changed"}


# ---------------------------------------------------------------------------
# Admin-only user management
# ---------------------------------------------------------------------------


@router.get("/users")
async def list_users(admin: dict = Depends(require_admin)):
    """List all users (admin-only)."""
    return await service.list_users()


@router.post("/users")
async def create_user(body: CreateUserRequest, admin: dict = Depends(require_admin)):
    """Create a new user (admin-only)."""
    try:
        user = await service.create_user(
            username=body.username,
            password=body.password,
            display_name=body.display_name,
            is_admin=body.is_admin,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"user": user}


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, admin: dict = Depends(require_admin)):
    """Delete a user (admin-only). Refuses to delete the last remaining admin."""
    try:
        found = await service.delete_user(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not found:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "deleted"}
