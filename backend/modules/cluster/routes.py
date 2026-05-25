from flask import Blueprint, jsonify, request

from . import service


cluster_bp = Blueprint("cluster", __name__)


@cluster_bp.post("/api/cluster")
def retrieve_clusters():
    # 顶层路由保持为 /api/cluster，和历史脚本及接口文档一致，不挂在 /api/deploy 下。
    payload = request.get_json(silent=True) or {}
    result, status_code = service.retrieve_clusters(payload)
    return jsonify(result), status_code
