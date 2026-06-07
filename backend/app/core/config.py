import os

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
	raw = os.environ.get(name)
	if raw is None:
		return default
	return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
	raw = os.environ.get(name)
	if raw is None:
		return default
	try:
		return float(raw)
	except ValueError:
		return default


SECRET_KEY = os.environ["SUSTECH_ASSISTANT_SECRET_KEY"]
JWT_ENCODE_ALGORITHM = "HS256"

CAS_LOGIN_URL = os.environ.get("CAS_LOGIN_URL", "https://cas.sustech.edu.cn/cas/login")
CAS_USER_AGENT = os.environ.get(
	"CAS_USER_AGENT",
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
	"(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
)
CAS_VERIFY_SSL = _env_bool("CAS_VERIFY_SSL", False)
CAS_TIMEOUT_SECONDS = _env_float("CAS_TIMEOUT_SECONDS", 10.0)

DATABASE_URL = os.environ["SUSTECH_ASSISTANT_DATABASE_URL"]

QQ_MAIL_IMAP_HOST = os.environ.get("QQ_MAIL_IMAP_HOST", "imap.qq.com")
QQ_MAIL_IMAP_PORT = int(os.environ.get("QQ_MAIL_IMAP_PORT", "993"))
QQ_MAIL_SMTP_HOST = os.environ.get("QQ_MAIL_SMTP_HOST", "smtp.qq.com")
QQ_MAIL_SMTP_PORT = int(os.environ.get("QQ_MAIL_SMTP_PORT", "465"))

EXMAIL_IMAP_HOST = os.environ.get("EXMAIL_IMAP_HOST", "imap.exmail.qq.com")
EXMAIL_IMAP_PORT = int(os.environ.get("EXMAIL_IMAP_PORT", "993"))
EXMAIL_SMTP_HOST = os.environ.get("EXMAIL_SMTP_HOST", "smtp.exmail.qq.com")
EXMAIL_SMTP_PORT = int(os.environ.get("EXMAIL_SMTP_PORT", "465"))

QQ_MAIL_FETCH_TIMEOUT_SECONDS = _env_float("QQ_MAIL_FETCH_TIMEOUT_SECONDS", 15.0)
QQ_MAIL_SEND_TIMEOUT_SECONDS = _env_float("QQ_MAIL_SEND_TIMEOUT_SECONDS", QQ_MAIL_FETCH_TIMEOUT_SECONDS)
