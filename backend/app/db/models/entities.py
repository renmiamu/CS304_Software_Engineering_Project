from datetime import datetime, timedelta, timezone

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, Table, Text, Time
from sqlalchemy.orm import relationship

from app.core.database import Base
from sqlalchemy import Column, Integer, String, TIMESTAMP
from sqlalchemy.sql import func


BEIJING_TZ = timezone(timedelta(hours=8))


def beijing_now() -> datetime:
	# Store as naive local datetime (UTC+8) to match existing DateTime columns.
	return datetime.now(BEIJING_TZ).replace(tzinfo=None)


# Many-to-many mapping between users and schedules.
user_schedule_association = Table(
	"user_schedule_association",
	Base.metadata,
	Column("user_id", Integer, ForeignKey("users.user_id"), primary_key=True),
	Column("schedule_id", Integer, ForeignKey("schedules.schedule_id"), primary_key=True),
)


class User(Base):
	"""Core student profile."""

	__tablename__ = "users"

	user_id = Column(Integer, primary_key=True, index=True)
	name = Column(String(100), nullable=False)
	pinyin_name = Column(String(100), nullable=True)
	photo = Column(Text, nullable=True)  # Base64-encoded avatar.
	gender = Column(String(10), nullable=True)
	birth_date = Column(String(20), nullable=True)
	college = Column(String(100), nullable=True)
	dormitory = Column(String(100), nullable=True)
	phone = Column(String(20), unique=True, nullable=True)
	email = Column(String(100), unique=True, nullable=False)
	gpa = Column(Float, nullable=True)
	rank = Column(String(50), nullable=True)
	department = Column(String(100), nullable=True)
	interest = Column(Text, nullable=True)
	created_at = Column(DateTime, default=beijing_now, nullable=False)
	updated_at = Column(DateTime, default=beijing_now, onupdate=beijing_now, nullable=False)

	credits = relationship("Credits", back_populates="user", uselist=False)
	deadlines = relationship("Deadline", back_populates="user", cascade="all, delete-orphan")
	schedules = relationship(
		"Schedule",
		secondary=user_schedule_association,
		back_populates="users",
	)


class Schedule(Base):
	__tablename__ = "schedules"

	schedule_id = Column(Integer, primary_key=True, index=True)
	name = Column(String(100), nullable=False)
	location = Column(String(100), nullable=True)
	start_time = Column(Time, nullable=True)
	end_time = Column(Time, nullable=True)
	teacher = Column(String(100), nullable=True)
	weekday = Column(Integer, nullable=True)  # 1-7 means Monday-Sunday.
	description = Column(String(500), nullable=True)
	schedule_type = Column(String(50), nullable=True)

	users = relationship(
		"User",
		secondary=user_schedule_association,
		back_populates="schedules",
	)


class Credits(Base):
	__tablename__ = "credits"

	id = Column(Integer, primary_key=True, autoincrement=True)
	user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, unique=True)
	total_credit = Column(Float, default=0.0, nullable=False)
	category_credit = Column(JSON, nullable=True)
	updated_at = Column(DateTime, default=beijing_now, onupdate=beijing_now, nullable=False)

	user = relationship("User", back_populates="credits")


class Deadline(Base):
	__tablename__ = "deadlines"

	id = Column(Integer, primary_key=True, autoincrement=True)
	is_user_created = Column(Integer, default=0, nullable=False)  # 0: no, 1: yes
	is_completed = Column(Integer, default=0, nullable=False)  # 0: no, 1: yes
	calendar_name = Column(String(200), nullable=True)
	end_time = Column(String(50), nullable=False)
	title = Column(String(200), nullable=False)
	event_type = Column(String(50), nullable=True)
	color = Column(String(30), nullable=True)
	user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)

	user = relationship("User", back_populates="deadlines")


class BBFile(Base):
	__tablename__ = "bb_files"

	id = Column(Integer, primary_key=True, autoincrement=True)
	user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
	course = Column(String(200), nullable=False)
	content = Column(String(200), nullable=True)
	file_url = Column(Text, nullable=False)
	file_name = Column(String(500), nullable=False)
	created_at = Column(DateTime, default=beijing_now, nullable=False)


class BBGrade(Base):
	__tablename__ = "bb_grades"

	id = Column(Integer, primary_key=True, autoincrement=True)
	user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
	course_id = Column(String(200), nullable=False)
	course_name = Column(String(500), nullable=True)
	item_name = Column(String(500), nullable=False)
	full_grade = Column(String(100), nullable=False)
	synced_at = Column(DateTime, default=beijing_now, nullable=False)

