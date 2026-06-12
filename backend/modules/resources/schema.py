def normalize_resource_query(args) -> dict:
    # 规范资源查询参数，后续可支持 namespace、node_name、gpu_vendor 等条件。
    return {key: args.get(key) for key in args.keys()}
