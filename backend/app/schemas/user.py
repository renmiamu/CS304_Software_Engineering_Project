from pydantic import BaseModel, ConfigDict


class UserInterestResponse(BaseModel):
    user_id: int
    interest: str | None = None


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    name: str
    pinyin_name: str | None = None
    photo: str | None = None
    gender: str | None = None
    birth_date: str | None = None
    college: str | None = None
    dormitory: str | None = None
    phone: str | None = None
    email: str
    gpa: float | None = None
    rank: str | None = None
    department: str | None = None
    interest: str | None = None


class UserInterestCreateRequest(BaseModel):
    interest: str


class UserInterestUpdateRequest(BaseModel):
    interest: str
