from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from datetime import datetime, timedelta

from .config import settings

ALGORITHM = "HS256"
oauth2_scheme = HTTPBearer()

async def verify_supabase_token(token: HTTPAuthorizationCredentials = Security(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token.credentials,
            settings.supabase_jwt_secret,
            algorithms=[ALGORITHM]
        )
        
        # Check for expiration (exp claim)
        exp = payload.get("exp")
        if exp is None:
            raise credentials_exception # No expiration time
        if datetime.utcfromtimestamp(exp) < datetime.utcnow():
            raise credentials_exception # Token expired
            
        # You can add more checks here if needed, e.g., specific roles or claims
        # user_id: str = payload.get("sub")
        # if user_id is None:
        #     raise credentials_exception

    except JWTError:
        raise credentials_exception
    
    return payload # Or specific parts of the payload like user_id
