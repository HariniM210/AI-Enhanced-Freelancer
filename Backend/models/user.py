"""Request/response models for registration, login, and public users.

The frontend sends exactly these field names (see Frontend(2)/js/auth.js):

    freelancer: name, email, password, role, headline, years_experience
    client:     name, email, password, role, company_name

``confirm_password`` is accepted when present but the current frontend
validates it locally and does not send it.
"""

from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Same practical rule as the frontend, kept intentionally simple.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")

# bcrypt only considers the first 72 bytes of a password.
MAX_PASSWORD_BYTES = 72


class RegisterRequest(BaseModel):
    """One model for both roles, with role-specific validation."""

    model_config = ConfigDict(
        validate_default=True,
        extra="ignore",
        str_strip_whitespace=True,
    )

    name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=MAX_PASSWORD_BYTES)
    role: Literal["freelancer", "client"]

    # Freelancer fields
    headline: Optional[str] = Field(default=None, max_length=80)
    years_experience: Optional[int] = Field(default=None, ge=0, le=60)

    # Client field
    company_name: Optional[str] = Field(default=None, max_length=120)

    # Optional because the frontend does not currently send it.
    confirm_password: Optional[str] = Field(default=None, max_length=MAX_PASSWORD_BYTES)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_RE.fullmatch(value):
            raise ValueError("Enter a valid email address.")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError("Password must be at most 72 bytes long.")
        if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
            raise ValueError("Password must contain at least one letter and one number.")
        return value

    @field_validator("headline")
    @classmethod
    def validate_headline(cls, value: Optional[str], info) -> Optional[str]:
        # `role` is declared before `headline`, so it is available in info.data.
        if info.data.get("role") == "freelancer" and (value is None or len(value.strip()) < 3):
            raise ValueError(
                "Professional title is required for freelancer accounts "
                "(at least 3 characters)."
            )
        return value.strip() if value else value

    @field_validator("years_experience")
    @classmethod
    def validate_years_experience(cls, value: Optional[int], info) -> Optional[int]:
        if info.data.get("role") == "freelancer" and value is None:
            raise ValueError("Years of experience is required for freelancer accounts.")
        return value

    @field_validator("company_name")
    @classmethod
    def validate_company_name(cls, value: Optional[str], info) -> Optional[str]:
        if info.data.get("role") == "client" and (value is None or len(value.strip()) < 2):
            raise ValueError("Company or organisation is required for client accounts.")
        return value.strip() if value else value

    @model_validator(mode="after")
    def validate_confirm_password(self):
        if self.confirm_password is not None and self.confirm_password != self.password:
            raise ValueError("Passwords do not match.")
        return self


class LoginRequest(BaseModel):
    """Email + password login payload."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_BYTES)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        # No format error here: bad credentials always return the same 401.
        return value.strip().lower()


class UserPublic(BaseModel):
    """The only user fields ever returned to clients (never the hash)."""

    id: str
    name: str
    email: str
    role: Literal["freelancer", "client"]
    company_name: Optional[str] = None
    headline: Optional[str] = None
    years_experience: Optional[int] = None


class AuthResponse(BaseModel):
    """Shape expected by Frontend(2)/js/ui.js -> UI.Auth.save()."""

    access_token: str
    token_type: str = "bearer"
    user: UserPublic
