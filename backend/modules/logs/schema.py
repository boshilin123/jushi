def normalize_log_query(args) -> dict:
    return {
        "namespace": args.get("namespace", "algorithm"),
        "pod_name": args.get("pod_name"),
        "deployment_name": args.get("deployment_name"),
        "tail_lines": int(args.get("tail_lines", 200)),
    }
