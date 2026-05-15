from datetime import datetime, timedelta, timezone

from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import IntegrityError

from app.databases.models import Quiz, QuizSession
from app.databases.repositories.base_repository import BaseRepository
from app.schemas.quiz import SessionStatus
from app.utils.exceptions import DBHTTPException
from app.utils.logger import logger


class QuizRepository(BaseRepository):
    model = Quiz

    _ACTIVE_SESSION_STATUSES = (
        SessionStatus.CREATED,
        SessionStatus.LOBBY,
        SessionStatus.LIVE,
        SessionStatus.PAUSED,
    )

    def _scoped_active_session_exists(self):
        return exists(
            select(QuizSession.id).where(
                QuizSession.quiz_id == Quiz.id,
                QuizSession.status.in_(self._ACTIVE_SESSION_STATUSES),
            ),
        )

    async def search_quizzes(
        self,
        *,
        page: int,
        page_size: int,
        q: str | None = None,
        status_filter: str | None = None,
        created_within: str | None = None,
        sort: str | None = None,
    ) -> tuple[list[Quiz], int]:
        conditions: list = []
        if q and q.strip():
            pattern = f"%{q.strip()}%"
            conditions.append(
                or_(Quiz.title.ilike(pattern), Quiz.description.ilike(pattern)),
            )

        if created_within and created_within not in ("", "all"):
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            if created_within == "7d":
                cutoff = now - timedelta(days=7)
            elif created_within == "30d":
                cutoff = now - timedelta(days=30)
            elif created_within == "1y":
                cutoff = now - timedelta(days=365)
            else:
                cutoff = None
            if cutoff is not None:
                conditions.append(Quiz.created_at >= cutoff)

        has_active_session = self._scoped_active_session_exists()
        if status_filter == "live":
            conditions.append(has_active_session)
        elif status_filter == "published":
            conditions.append(Quiz.is_published.is_(True))
            conditions.append(~has_active_session)
        elif status_filter == "draft":
            conditions.append(Quiz.is_published.is_(False))

        effective_sort = (sort or "created_desc").lower()
        if effective_sort == "created_asc":
            order_exprs = (Quiz.created_at.asc(), Quiz.id.asc())
        elif effective_sort == "title_asc":
            order_exprs = (Quiz.title.asc(), Quiz.id.asc())
        elif effective_sort == "title_desc":
            order_exprs = (Quiz.title.desc(), Quiz.id.desc())
        else:
            order_exprs = (Quiz.created_at.desc(), Quiz.id.desc())

        stmt = select(Quiz).order_by(*order_exprs)
        if conditions:
            stmt = stmt.where(*conditions)

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        count_stmt = select(func.count()).select_from(Quiz)
        if conditions:
            count_stmt = count_stmt.where(*conditions)

        rows_result = await self.session.scalars(stmt)
        items = list(rows_result.all())
        total = (await self.session.execute(count_stmt)).scalar_one()
        return items, int(total)

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
