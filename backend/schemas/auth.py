"""Authentication-related Pydantic request/response schemas."""

import re

from pydantic import BaseModel, Field, field_validator

# AUTH-23: one normalisation (strip + lower) for register and login, so an account
# can always log in with the name it registered.
_USERNAME_RE = re.compile(r"^[a-z0-9_.-]{3,32}$")


def _normalise_username(v: str) -> str:
    return v.strip().lower()


class LoginRequest(BaseModel):
    username: str = Field(..., max_length=64)
    password: str = Field(..., max_length=128)

    @field_validator("username")
    @classmethod
    def _norm_username(cls, v: str) -> str:
        return _normalise_username(v)


class RegisterRequest(BaseModel):
    username: str
    # Length rules stay in services/auth_service.register_user (400 with a plain detail, UX-14).
    password: str
    display_name: str = Field(..., max_length=100)
    # FINSEC-09 / REG-12: policy version shown with the registration consent
    # checkbox, and the 18+ attestation. Both required: no account without them.
    accepted_policy_version: str = Field(..., max_length=20, description="Privacy Policy / Terms version the user accepted")
    age_confirmed: bool = Field(..., description="User confirmed they are 18 or older")

    @field_validator("username")
    @classmethod
    def _valid_username(cls, v: str) -> str:
        v = _normalise_username(v)
        if not _USERNAME_RE.match(v):
            raise ValueError("Username must be 3-32 characters: letters, digits, '.', '_' or '-'.")
        return v
