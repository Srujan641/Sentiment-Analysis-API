"""Signup, login, logout, current user (ACC-1, ACC-2)."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.platform.deps import SESSION_COOKIE, Principal, auth_rate_limit, get_db, require_user
from app.platform.models import AccountType, Organization, Role, User, WebSession
from app.platform.plans import default_plan
from app.platform.schemas import LoginRequest, MeResponse, OrgOut, SignupRequest, UserOut
from app.platform.security import hash_password, new_session_token, sha256, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _start_session(request: Request, response: Response, db: Session, user: User) -> None:
    settings = request.app.state.settings
    token, token_hash = new_session_token()
    ttl = timedelta(days=settings.session_ttl_days)
    db.add(WebSession(token_hash=token_hash, user_id=user.id, expires_at=datetime.now(UTC) + ttl))
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(ttl.total_seconds()),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def _me(user: User) -> MeResponse:
    return MeResponse(user=UserOut.model_validate(user), organization=OrgOut.model_validate(user.org))


@router.post(
    "/signup",
    response_model=MeResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth_rate_limit)],
)
def signup(body: SignupRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(func.count()).select_from(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    is_org = body.account_type == "organization"
    if is_org and not body.organization_name:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "organization_name is required for organizations"
        )

    org = Organization(
        name=body.organization_name if is_org else f"{body.name} (personal)",
        account_type=AccountType(body.account_type),
        plan=default_plan(body.account_type),
    )
    user = User(
        org=org, email=email, name=body.name, password_hash=hash_password(body.password), role=Role.owner
    )
    db.add_all([org, user])
    db.commit()
    _start_session(request, response, db, user)
    return _me(user)


@router.post("/login", response_model=MeResponse, dependencies=[Depends(auth_rate_limit)])
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not verify_password(user.password_hash if user else None, body.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    is_business = user.org.account_type == AccountType.organization
    if body.portal == "personal" and is_business:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "This is a business account. Please use the business login."
        )
    if body.portal == "business" and not is_business:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "This is a personal account. Please use the personal login."
        )
    _start_session(request, response, db, user)
    return _me(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        db.execute(delete(WebSession).where(WebSession.token_hash == sha256(token)))
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=MeResponse)
def me(principal: Principal = Depends(require_user)):
    return _me(principal.user)
