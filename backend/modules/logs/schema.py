TIME_RANGES = {"all", "1h", "1d", "7d", "30d"}


def _bounded_int(value, default, minimum, maximum):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(min(parsed, maximum), minimum)


def normalize_operation_result(value):
    normalized = str(value or "").strip().lower()
    if normalized in {"success", "true", "1", "成功", "通过"}:
        return 1
    if normalized in {"failure", "failed", "false", "0", "失败"}:
        return 0
    return None


def normalize_time_range(value, default="all"):
    normalized = str(value or default).strip().lower()
    return normalized if normalized in TIME_RANGES else default


def normalize_log_query(args) -> dict:
    page = _bounded_int(args.get("page", 1), 1, 1, 1_000_000)
    page_size = _bounded_int(args.get("page_size", 100), 100, 1, 100)
    return {
        "namespace": args.get("namespace"),
        "pod_name": args.get("pod_name"),
        "deployment_name": args.get("deployment_name"),
        "tail_lines": _bounded_int(args.get("tail_lines", 200), 200, 1, 5000),
        "operator": args.get("operator", ""),
        "operation_type": args.get("operation_type", ""),
        "keyword": args.get("keyword", ""),
        "operation_result": normalize_operation_result(args.get("operation_result")),
        "time_range": normalize_time_range(args.get("time_range")),
        "page": page,
        "page_size": page_size,
    }
