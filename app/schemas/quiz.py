import enum


class QuestionType(enum.Enum):
    SINGLE_ANSWER = "single_answer"
    MULTIPLE_ANSWER = "multiple_answer"


class SessionStatus(enum.Enum):
    CREATED = "created"
    LOBBY = "lobby"
    LIVE = "live"
    PAUSED = "paused"
    FINISHED = "finished"
    CANCELLED = "cancelled"


class ParticipantStatus(enum.Enum):
    JOINED = "joined"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    FINISHED = "finished"
    DISCONNECTED = "disconnected"


class SessionQuestionStatus(enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    CLOSED = "closed"