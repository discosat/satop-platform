from fastapi import HTTPException, status
from pydantic import BaseModel


class HttpErrorModel(BaseModel):
    detail: str


class CustomException(HTTPException):
    response: dict

    def __init__(self, status_code, detail=None, headers=None):
        super().__init__(status_code, detail, headers)

        self.response = {
            status_code: {
                "description": detail or "Undescribed error",
                "model": HttpErrorModel,
            }
        }


class InvalidCredentials(CustomException):
    def __init__(self, detail="Invalid authentication credentials", headers=None):
        _headers = {"WWW-Authenticate": "Bearer"}

        if headers:
            _headers.update(headers)

        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers=_headers,
        )


class InsufficientPermissions(CustomException):
    def __init__(self, detail="Insufficient permissions", headers=None):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN, detail=detail, headers=headers
        )


class MissingCredentials(CustomException):
    def __init__(self, detail="Missing credentials", headers=None):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers=headers,
        )


class InvalidUser(CustomException):
    def __init__(
        self,
        detail="Invalid entity. The account does not exist or it has been removed.",
        headers=None,
    ):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers=headers,
        )


class InvalidToken(CustomException):
    def __init__(self, detail="Token could not be validated.", headers=None):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers=headers,
        )


class ExpiredToken(InvalidToken):
    def __init__(
        self, detail="Token has expired and could not be validated.", headers=None
    ):
        super().__init__(detail, headers)


class NotImplemented(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Not Implemented",
        )


class NotFound(CustomException):
    def __init__(self, detail="Resource not found", headers=None):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND, detail=detail, headers=headers
        )
