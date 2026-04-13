from fastapi.params import Depends
import httpx
from fastapi import HTTPException
from jwt import InvalidTokenError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.google_oauth import GOOGLE_TOKEN_URL, GOOGLE_USERINFO_URL
from app.core.security import get_pair_tokens, get_new_access_token_with_refresh
from app.core.settings import settings
from app.databases.models import User
from app.databases.repositories.user_repository import UserRepository

from app.dependencies.database import get_session
from app.dependencies.token import TokenDep
from app.schemas.auth import JWTTokens
from app.schemas.user import UserDetail, UserInfo, UserRole
from app.core.security import decode_auth_jwt_token

from app.schemas.auth import AuthState, OriginType
from app.utils.exceptions import InvalidCredentials


class AuthService:
    def __init__(self, session: AsyncSession):
        self.user_repository = UserRepository(session=session, model=User)

    async def _get_user_by_email(self, email: str) -> User | None:
        return await self.user_repository.get_one(email=email)

    @staticmethod
    async def _get_user_access_token(code: str):
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if token_resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to fetch access token")

            token_data = token_resp.json()
            print("token_data", token_data)
            access_token = token_data.get("access_token")

            return access_token

    @staticmethod
    async def _get_userinfo_by_access_token(access_token: str) -> UserInfo:
        async with httpx.AsyncClient() as client:
            userinfo_resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if userinfo_resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to fetch user info")

            userinfo = userinfo_resp.json()
            return UserInfo.model_validate(userinfo)

    @staticmethod
    def _issue_redirect(state: str, role: UserRole):
        auth_state = AuthState.decode(state)
        # redirect_url = None

        match auth_state.origin:
            case OriginType.ADMIN:
                if role != UserRole.ADMIN:
                    return HTTPException(status_code=401, detail="Something pishlo ne tak.")
                # redirect_url = settings.FRONTEND_ADMIN_URL
            case OriginType.GAME:
                if not auth_state.game_id:
                    raise HTTPException(status_code=400, detail="Missing game_id for game origin")
                # redirect_url = f"{settings.FRONTEND_CLIENT_URL}/games/{auth_state.game_id}"
            case _:
                raise HTTPException(status_code=400, detail="Invalid origin type")

        # response = RedirectResponse(url=redirect_url)

        # response.set_cookie("ACCESS_TOKEN", tokens.access_token)
        # response.set_cookie("REFRESH_TOKEN", tokens.refresh_token)
        #
        # return response

    async def login(self, code: str) -> JWTTokens:
        access_token = await self._get_user_access_token(code)
        google_payload = await self._get_userinfo_by_access_token(access_token)

        user = await self._get_user_by_email(email=google_payload.email)

        if not user:
            user_data = google_payload.model_dump()

            user = await self.user_repository.create_one(
                user_data,
            )

        tokens = get_pair_tokens(email=user.email, role=user.role)
        # self._issue_redirect(role=user.role)
        return tokens

    @staticmethod
    async def get_current_user(
        token: TokenDep, # noqa
        session: AsyncSession = Depends(get_session),
    ) -> UserDetail:
        try:
            payload = decode_auth_jwt_token(token.credentials)
        except (InvalidTokenError, ValidationError) as e:
            raise InvalidCredentials() from e
    
        user_service = AuthService(session=session)
        user = await user_service._get_user_by_email(email=payload.email)
    
        if not user:
            raise InvalidCredentials()
    
        return UserDetail.model_validate(user)

    @staticmethod
    async def refresh(
        refresh_token: str,
    ) -> JWTTokens:
        refresh_payload = decode_auth_jwt_token(refresh_token, settings.AUTH_SECRET_KEY)
        tokens = get_new_access_token_with_refresh(refresh_payload)

        return tokens
