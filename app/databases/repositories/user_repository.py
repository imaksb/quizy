from sqlalchemy.exc import IntegrityError

from app.databases.models.user import User
from app.databases.repositories.base_repository import BaseRepository
from app.utils.exceptions import DBHTTPException
from app.utils.logger import logger


class UserRepository(BaseRepository):
    model = User

    async def create_one(self, data: dict) -> User:
        try:
            user = await super().create(**data)
            await self.session.commit()
            return user
        except IntegrityError as e:
            logger.error(e)
            raise DBHTTPException(message="User already exists")
        except Exception as e:
            logger.error(e)
            raise DBHTTPException(message="Signup failed")