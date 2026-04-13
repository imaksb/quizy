from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
 
security_bearer = HTTPBearer()

TokenDep = Annotated[HTTPAuthorizationCredentials, Depends(security_bearer)]
    