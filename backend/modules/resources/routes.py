from flask import Blueprint, jsonify, request

from . import service
from .schema import normalize_resource_query


resources_bp = Blueprint("resources", __name__)


@resources_bp.get("/summary")
def summary():
    # 首页 / 资源中心顶部资源总览。
    return jsonify(service.summary(normalize_resource_query(request.args)))


@resources_bp.get("/nodes")
def nodes():
    # 节点资源列表。
    return jsonify(service.nodes(normalize_resource_query(request.args)))


@resources_bp.get("/gpus")
def gpus():
    # GPU / vGPU / 显存 / 算力资源统计。
    return jsonify(service.gpus(normalize_resource_query(request.args)))


@resources_bp.get("/quotas")
def quotas():
    # 命名空间资源配额。
    return jsonify(service.quotas(normalize_resource_query(request.args)))


@resources_bp.get("/cards")
def cards():
    # 显卡 / vGPU 卡片列表。
    return jsonify(service.cards(normalize_resource_query(request.args)))


@resources_bp.get("/trend")
def trend():
    # 资源趋势数据。
    return jsonify(service.trend(normalize_resource_query(request.args)))


@resources_bp.get("/recommendation")
def recommendation():
    # 首页资源推荐策略。
    return jsonify(service.recommendation(normalize_resource_query(request.args)))
