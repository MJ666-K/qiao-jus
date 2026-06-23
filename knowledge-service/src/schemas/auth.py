from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    tenant_name: str = Field(default="default", max_length=200)
    display_name: str | None = Field(default=None, max_length=100)
    captcha_key: str
    captcha_code: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    captcha_key: str
    captcha_code: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    email: EmailStr
    role: str = "user"
    display_name: str | None = None
    scopes: list[str] = []


class UserUpdate(BaseModel):
    role: str | None = None
    display_name: str | None = None


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str


class CaptchaResponse(BaseModel):
    captcha_key: str
    image: str
