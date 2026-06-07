from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel


class TisScheduleQueryRequest(BaseModel):
    xn: str = "2025-2026"
    xq: str = "2"
    bs: str = "2"


class TisScheduleCourse(BaseModel):
    course_name: str
    teacher: str = ""
    weekday: str = ""
    weeks: str = ""
    location: str = ""
    time_slots: str = ""


class TisScheduleResponse(BaseModel):
    courses: List[TisScheduleCourse]


class TisGradeResponse(BaseModel):
    GPA: Optional[Union[float, str]] = None
    Rank: Optional[Union[int, str]] = None


class TisCreditResponse(BaseModel):
    total_credit: float = 0.0
    category_credit: Dict[str, float] = {}


class TisInfoQueryRequest(BaseModel):
    page: int = 1
    limit: int = 100
    sort: str = "id"
    order: str = "desc"


class TisInfoResponse(BaseModel):
    data: Union[Dict[str, Any], List[Dict[str, Any]]]


class TisIdResponse(BaseModel):
    tis_id: Optional[str] = None


class TisPhotoResponse(BaseModel):
    base64: str
    filename: str
    size: int
    type: str
    saved_path: Optional[str] = None


class ScheduleEventCreate(BaseModel):
    name: str
    location: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    teacher: Optional[str] = None
    weekday: Optional[int] = None
    description: Optional[str] = None
    schedule_type: Optional[str] = None


class ScheduleEventUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    teacher: Optional[str] = None
    weekday: Optional[int] = None
    description: Optional[str] = None
    schedule_type: Optional[str] = None


class ScheduleEventResponse(BaseModel):
    schedule_id: int
    name: str
    location: str = ""
    start_time: str = ""
    end_time: str = ""
    teacher: str = ""
    weekday: Optional[int] = None
    description: str = ""
    schedule_type: str = ""
