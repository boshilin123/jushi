import os

LOGO_CONFIG_KEY = "logo_path"
LOGO_UPLOAD_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "static", "logos")
)
LOGO_MAX_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB
LOGO_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg", ".gif"}
LOGO_ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/svg+xml",
    "image/gif",
}


def validate_logo_file(file_storage) -> tuple[str | None, str | None]:
    """校验上传的 logo 文件，返回 (错误信息, 文件扩展名)。"""
    if not file_storage or not file_storage.filename:
        return "未选择文件", None

    original = file_storage.filename
    _, ext = os.path.splitext(original)
    ext = ext.lower()
    if ext not in LOGO_ALLOWED_EXTENSIONS:
        return f"不支持的文件格式，仅支持：{', '.join(sorted(LOGO_ALLOWED_EXTENSIONS))}", None

    if file_storage.mimetype and file_storage.mimetype not in LOGO_ALLOWED_MIME_TYPES:
        return f"不支持的文件类型：{file_storage.mimetype}", None

    return None, ext
