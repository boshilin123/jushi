from flask import Blueprint, jsonify, request

from . import service
from .schema import normalize_log_query


logs_bp = Blueprint("logs", __name__)


@logs_bp.get("/operations")
def operation_logs():
    # 查询平台操作日志，用于审计用户登录、创建、释放和告警处理等动作。
    return jsonify(service.operation_logs(normalize_log_query(request.args)))


@logs_bp.get("/instance")
def instance_logs():
    # 查询推理实例日志，后续读取 /workspace/Alg/log/<deployment_name>。
    return jsonify(service.instance_logs(normalize_log_query(request.args)))


@logs_bp.get("/pod")
def pod_logs():
    # 查询 Pod 日志，后续对接 Kubernetes logs 或 PaaS 日志接口。
    return jsonify(service.pod_logs(normalize_log_query(request.args)))
