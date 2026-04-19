from typing import Literal, NotRequired, TypedDict


class CookieKwargs(TypedDict):
    path: str
    secure: bool
    samesite: Literal["lax", "none"]
    domain: NotRequired[str]
