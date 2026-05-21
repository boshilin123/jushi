def normalize_pod_query(args) -> dict:
    # 规范 Pod 查询参数，后续支持 namespace、deployment_name、phase、node_name。
    return {key: args.get(key) for key in args.keys()}


def normalize_pod_action(payload: dict) -> dict:
    # 规范 Pod 操作参数，至少需要 namespace 和 pod_name。
    return {
        "namespace": payload.get("namespace"),
        "pod_name": payload.get("pod_name"),
    }
