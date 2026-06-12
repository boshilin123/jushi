from flask import Blueprint, jsonify, request

from . import service
from .schema import normalize_pod_action, normalize_pod_query


pods_bp = Blueprint("pods", __name__)


@pods_bp.get("/list")
def list_pods():
    # 查询 Pod 列表，支持后续按命名空间、部署名、状态和节点筛选。
    return jsonify(service.list_pods(normalize_pod_query(request.args)))


@pods_bp.get("/detail")
def pod_detail():
    # 查询 Pod 详情，包括容器状态、事件和调度节点。
    return jsonify(service.pod_detail(normalize_pod_query(request.args)))


@pods_bp.get("/logs")
def pod_logs():
    # 查询 Pod 最近日志，一期先返回最近 N 行，不做实时流式输出。
    return jsonify(service.pod_logs(normalize_pod_query(request.args)))


@pods_bp.post("/delete")
def delete_pod():
    # 删除指定 Pod，通常用于触发控制器重新拉起实例。
    payload = request.get_json(silent=True) or {}
    return jsonify(service.delete_pod(normalize_pod_action(payload)))


@pods_bp.post("/restart")
def restart_pod():
    # 重启 Pod，后续可通过删除 Pod 或调用平台接口实现。
    payload = request.get_json(silent=True) or {}
    return jsonify(service.restart_pod(normalize_pod_action(payload)))
