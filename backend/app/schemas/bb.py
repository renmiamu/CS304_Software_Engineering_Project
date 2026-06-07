from typing import Dict, List, Optional

from pydantic import BaseModel


class BBCourse(BaseModel):
    title: str
    course_id: str
    url: str


class BBCoursesResponse(BaseModel):
    courses: List[BBCourse]


class BBCalendarEvent(BaseModel):
    completed: Optional[bool] = None
    color: Optional[str] = None
    userCreated: Optional[bool] = None
    calendarName: Optional[str] = None
    end: Optional[str] = None
    title: Optional[str] = None
    eventType: Optional[str] = None


class BBCalendarResponse(BaseModel):
    events: List[BBCalendarEvent]


class BBCalendarItem(BBCalendarEvent):
    id: int


class BBCalendarItemsResponse(BaseModel):
    events: List[BBCalendarItem]


class BBCalendarCreateRequest(BaseModel):
    title: str
    end: str
    completed: bool = False
    color: Optional[str] = None
    calendarName: Optional[str] = None
    eventType: Optional[str] = None
    userCreated: bool = True


class BBCalendarUpdateRequest(BaseModel):
    title: Optional[str] = None
    end: Optional[str] = None
    completed: Optional[bool] = None
    color: Optional[str] = None
    calendarName: Optional[str] = None
    eventType: Optional[str] = None
    userCreated: Optional[bool] = None


class BBGradeItem(BaseModel):
    course_id: str
    course_name: str
    item_name: str
    full_grade: str


class BBGradesResponse(BaseModel):
    grades: List[BBGradeItem]


class BBFileItem(BaseModel):
    course: str
    content: str
    file_url: str
    file_name: str


class BBFilesResponse(BaseModel):
    files: List[BBFileItem]


class BBQueryRequest(BaseModel):
    term_filter: Optional[str] = "2026春"


class BBCalendarQueryRequest(BaseModel):
    start_timestamp: Optional[int] = None
    end_timestamp: Optional[int] = None
