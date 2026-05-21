def normalize_log_query(args) -> dict:
    # 规范日志查询参数，后续支持实例名、Pod 名、时间范围和日志行数。
    return {key: args.get(key) for key in args.keys()}
