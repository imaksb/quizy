from app.core.settings import settings
from app.dependencies.token import TokenDep
from app.core.security import decode_auth_jwt_token

from app.schemas.auth import JWTPayload



class UserValidationService:
    @staticmethod
    async def validate_user_data(token: TokenDep) -> JWTPayload:
        return decode_auth_jwt_token(token=token.credentials, secret_key=settings.AUTH_SECRET_KEY)
