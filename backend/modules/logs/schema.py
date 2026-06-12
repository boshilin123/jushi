def normalize_log_query(args) -> dict:
    page = max(int(args.get("page", 1) or 1), 1)
    page_size = max(min(int(args.get("page_size", 20) or 20), 100), 1)
    return {
        "namespace": args.get("namespace"),
        "pod_name": args.get("pod_name"),
        "deployment_name": args.get("deployment_name"),
        "tail_lines": int(args.get("tail_lines", 200)),
        "operator": args.get("operator", ""),
        "operation_type": args.get("operation_type", ""),
        "keyword": args.get("keyword", ""),
        "page": page,
        "page_size": page_size,
    }
