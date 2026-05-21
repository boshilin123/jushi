from flask import Blueprint, jsonify


system_bp = Blueprint("system", __name__)


@system_bp.get("/api/health")
def health():
    # 健康检查接口，供本地调试、Docker Compose 和部署探针使用。
    return jsonify({"status": "ok"})
