from sqlalchemy.exc import IntegrityError

from app.databases.models import Quiz
from app.databases.repositories.base_repository import BaseRepository
from app.utils.exceptions import DBHTTPException
from app.utils.logger import logger


class QuizRepository(BaseRepository):
    model = Quiz

    async def create_one(self, data: dict) -> Quiz:
        try:
            quiz = await super().create(**data)
            await self.session.refresh(quiz)
            return quiz
        except IntegrityError as e:
            await self.session.rollback()
            logger.error(e)
            raise DBHTTPException(message="Quiz create failed")
        except Exception as e:
            await self.session.rollback()
            logger.error(e)
            raise DBHTTPException(message="Quiz create failed")
