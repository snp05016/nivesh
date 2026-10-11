"""Authentication-related Pydantic request/response schemas."""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str
    # FINSEC-09 / REG-12: policy version shown with the registration consent
    # checkbox, and the 18+ attestation. Both required: no account without them.
    accepted_policy_version: str = Field(..., max_length=20, description="Privacy Policy / Terms version the user accepted")
    age_confirmed: bool = Field(..., description="User confirmed they are 18 or older")
