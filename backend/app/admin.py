"""Admin panel (starlette-admin) at /api/admin.

Off unless ADMIN_EMAILS is set. There is no separate admin login: you log in on the site as
usual, and the panel lets you in if your email is on ADMIN_EMAILS. It lives under /api/ so the
frontend dev server and nginx proxy it like the rest of the API, and the session cookie reaches it.

Edits made here go straight to the database and skip the services: no validation beyond the
database's own constraints, and deleting a photo row leaves its file on disk until the next
startup sweep (image_service.sweep_orphans).
"""
from __future__ import annotations
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import PlainTextResponse, RedirectResponse, Response
from starlette.routing import Route
from starlette.status import HTTP_303_SEE_OTHER
from starlette.templating import Jinja2Templates
from starlette_admin.auth import AdminUser, BaseAuthProvider, login_not_required
from starlette_admin.contrib.sqla import Admin, ModelView
from app.config import settings
from app.database import async_session_factory
from app.models import (AuthEvent, CompareGroup, CompareMember, Home, HomePhoto, Invite, Membership, OtpCode,
                        QuestionnaireResponse, Room, Session, StagedPhoto, User, UserContact)
from app.utils.session import get_current_session

BASE_URL = "/api/admin"


async def _site_user(request: Request) -> User | None:
    """The user logged in on the site (same cookie as the API), or None."""
    async with async_session_factory() as db:
        session = await get_current_session(db, request)
        if session is None:
            return None
        user = await db.get(User, session.user_id)
        # Same rules as require_user: off BETA_EMAILS counts as logged out.
        if user is None or user.deleted_at is not None or not settings.beta_allows(user.email):
            return None
        return user


class SiteSessionAuth(BaseAuthProvider):
    async def authenticate(self, request: Request) -> AdminUser | None:
        user = await _site_user(request)
        if user is None or user.email not in settings.admin_allowlist:
            return None
        return AdminUser(username=f"{user.first_name} {user.last_name} · {user.email}")

    @login_not_required
    async def render_login(self, request: Request) -> Response:
        # Logged in but not an admin: say so instead of looping through the site's login page.
        if await _site_user(request) is not None:
            return PlainTextResponse("Your account is not on ADMIN_EMAILS.", status_code=403)
        return RedirectResponse("/login", status_code=HTTP_303_SEE_OTHER)

    async def render_logout(self, request: Request) -> Response:
        # The admin has no session of its own; leaving it means going back to the site.
        return RedirectResponse("/", status_code=HTTP_303_SEE_OTHER)

    def get_routes(self, templates: Jinja2Templates) -> list[Route]:
        return [
            Route(self.login_path, self.render_login, methods=["GET"], name="login"),
            Route(self.logout_path, self.render_logout, methods=["GET", "POST"], name="logout"),
        ]


# Never shown anywhere in the panel: not in lists, details, forms, the column picker or exports.
# Hashes of session tokens, login codes and invite links, and the dorm room number, which
# never leaves the server.
HIDDEN = {"token_hash", "code_hash", "room_label"}


class View(ModelView):
    def _init_fields(self) -> None:
        # Hiding with exclude_fields_from_* still offers the field in "Columns" and exports.
        self.fields = [f for f in self.fields if f.name not in HIDDEN]
        super()._init_fields()


class UserView(View):
    fields = ["id", "email", "first_name", "last_name", "language", "gender", "faculty", "is_adult", "intent",
              "bio", "avatar_file", "privacy_version", "privacy_accepted_at", "created_at", "deleted_at", "contacts"]
    exclude_fields_from_list = ["bio", "avatar_file", "privacy_version", "privacy_accepted_at", "contacts"]
    searchable_fields = ["email", "first_name", "last_name"]
    sortable_fields = ["email", "first_name", "last_name", "created_at", "deleted_at"]
    fields_default_sort = [("created_at", True)]


class HomeView(View):
    exclude_fields_from_list = ["description", "lat", "lon", "radius_m", "photos"]
    fields_default_sort = [("created_at", True)]


class RoomView(View):
    exclude_fields_from_list = ["description", "emoji_key", "photos"]
    searchable_fields = ["name", "emoji"]


class ReadOnlyView(View):
    """Auth plumbing: useful to look at, never edited by hand."""
    fields_default_sort = [("created_at", True)]

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False


class InviteView(ReadOnlyView):
    def can_delete(self, request: Request) -> bool:
        return True  # revoking an invite = deleting its row


def mount_admin(app: FastAPI) -> None:
    if not settings.admin_allowlist:
        return
    admin = Admin(async_session_factory, title="nsusosed admin", base_url=BASE_URL,
                  auth_provider=SiteSessionAuth(), secret_key=settings.admin_secret_key or None)
    admin.add_view(UserView(User, icon="fa fa-user"))
    admin.add_view(View(UserContact, icon="fa fa-address-book"))
    admin.add_view(View(QuestionnaireResponse, icon="fa fa-list-check"))
    admin.add_view(HomeView(Home, icon="fa fa-house"))
    admin.add_view(RoomView(Room, icon="fa fa-door-open"))
    admin.add_view(View(Membership, icon="fa fa-users"))
    admin.add_view(View(HomePhoto, icon="fa fa-image"))
    admin.add_view(InviteView(Invite, icon="fa fa-envelope-open-text"))
    admin.add_view(View(CompareGroup, icon="fa fa-scale-balanced"))
    admin.add_view(View(CompareMember, icon="fa fa-user-group"))
    admin.add_view(ReadOnlyView(Session, icon="fa fa-key"))
    admin.add_view(ReadOnlyView(OtpCode, icon="fa fa-hashtag"))
    admin.add_view(ReadOnlyView(AuthEvent, icon="fa fa-clock-rotate-left"))
    admin.add_view(ReadOnlyView(StagedPhoto, icon="fa fa-hourglass-half"))
    admin.mount_to(app)
