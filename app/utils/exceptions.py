from fastapi import HTTPException
from starlette import status


class UserNotFound(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


class UserAlreadyExists(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


class DBHTTPException(HTTPException):
    def __init__(self, sys_log_name: str = "", message: str = "") -> None:
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{message}")


class InvalidCredentials(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )


class AlreadyInCompanyException(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User is already in company"
        )
