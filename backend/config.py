import os


class Config:
    APP_ENV = os.getenv("APP_ENV", "production")
    SECRET_KEY = os.getenv("SECRET_KEY", "BlueDot@123")

    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "jushi")
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "504803")

    DCE_API_BASE = os.getenv("DCE_API_BASE", "")
    DCE_CLUSTER = os.getenv("DCE_CLUSTER", "default")
    DCE_NAMESPACE = os.getenv("DCE_NAMESPACE", "default")
    DCE_TOKEN = (os.getenv("DCE_TOKEN") or "").strip('"')
