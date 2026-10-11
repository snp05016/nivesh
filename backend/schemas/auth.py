"""Authentication-related Pydantic request/response schemas."""

from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str
    # FINSEC-09: policy version shown with the registration consent checkbox.
    accepted_policy_version: Optional[str] = Field(None, max_length=20, description="Privacy Policy / Terms version the user accepted")
