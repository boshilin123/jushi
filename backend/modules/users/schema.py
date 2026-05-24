USER_MUTABLE_FIELDS = ("username", "real_name", "role", "status")
USER_ROLES = {"admin", "operator", "user"}
USER_STATUSES = {"active", "disabled"}


def filter_user_payload(payload: dict) -> dict:
    # 过滤用户可写字段，避免前端传入无关字段直接进入数据库。
    return {key: payload[key] for key in USER_MUTABLE_FIELDS if key in payload}


def parse_user_list_query(args) -> dict:
    # 解析用户列表查询参数；默认不按状态过滤，传 status 时才筛选。
    def to_int(value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    page = max(to_int(args.get("page"), 1), 1)
    page_size = min(max(to_int(args.get("page_size"), 20), 1), 100)

    status = str(args.get("status") or "").strip()
    if status not in USER_STATUSES:
        status = ""

    return {
        "keyword": str(args.get("keyword") or "").strip(),
        "role": str(args.get("role") or "").strip(),
        "status": status,
        "page": page,
        "page_size": page_size,
        "offset": (page - 1) * page_size,
    }


def parse_user_id(value) -> tuple[int | None, str | None]:
    # 统一解析用户 ID，避免路由和 service 层重复处理非法数字。
    try:
        user_id = int(value)
    except (TypeError, ValueError):
        return None, "用户 ID 必须是数字"

    if user_id <= 0:
        return None, "用户 ID 必须大于 0"
    return user_id, None


def validate_create_payload(payload: dict) -> tuple[dict | None, str | None]:
    # 创建用户参数校验：一期仍使用明文密码，后续上线前需要升级为哈希存储。
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    real_name = str(payload.get("real_name") or "").strip() or None
    role = str(payload.get("role") or "user").strip()
    status = str(payload.get("status") or "active").strip()

    if not username:
        return None, "用户名不能为空"
    if len(username) > 64:
        return None, "用户名长度不能超过 64"
    if not password:
        return None, "密码不能为空"
    if len(password) > 128:
        return None, "密码长度不能超过 128"
    if role not in USER_ROLES:
        return None, "用户角色不合法"
    if status not in USER_STATUSES:
        return None, "用户状态不合法"

    return {
        "username": username,
        "password": password,
        "real_name": real_name,
        "role": role,
        "status": status,
    }, None


def validate_update_payload(payload: dict) -> tuple[int | None, dict | None, str | None]:
    # 更新用户只允许修改展示名称、角色和状态，不允许通过该接口改用户名和密码。
    user_id, error = parse_user_id(payload.get("id"))
    if error:
        return None, None, error

    data = {}
    if "real_name" in payload:
        data["real_name"] = str(payload.get("real_name") or "").strip() or None
    if "role" in payload:
        role = str(payload.get("role") or "").strip()
        if role not in USER_ROLES:
            return None, None, "用户角色不合法"
        data["role"] = role
    if "status" in payload:
        status = str(payload.get("status") or "").strip()
        if status not in USER_STATUSES:
            return None, None, "用户状态不合法"
        data["status"] = status

    if not data:
        return None, None, "没有可更新的字段"
    return user_id, data, None


def validate_delete_payload(payload: dict) -> tuple[int | None, str | None]:
    # 删除用户采用物理删除，只需要校验用户 ID。
    return parse_user_id(payload.get("id"))


def validate_reset_password_payload(payload: dict) -> tuple[int | None, str | None, str | None]:
    # 重置密码只修改 password 字段；当前阶段仍按 init.sql 约定明文保存。
    user_id, error = parse_user_id(payload.get("id"))
    if error:
        return None, None, error

    password = str(payload.get("password") or "")
    if not password:
        return None, None, "新密码不能为空"
    if len(password) > 128:
        return None, None, "密码长度不能超过 128"
    return user_id, password, None
