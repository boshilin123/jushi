from flask import Flask, request, jsonify
import os
import time
import requests
import logging
import json
import uuid
import socket
import random
from urllib.parse import quote_plus
from dotenv import load_dotenv

# ✅ 并发竞态修复：跨进程文件锁（Linux）
import fcntl
from contextlib import contextmanager

load_dotenv()
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# 端口列表服务配置
PORT_LIST_API_BASE = (os.getenv("PORT_LIST_API_BASE") or "http://0.0.0.0:8091").rstrip("/")
PORT_LIST_RESOLVE_PATH = os.getenv("PORT_LIST_RESOLVE_PATH", "/api/port-list/resolve")
PORT_LIST_TIMEOUT_S = float(os.getenv("PORT_LIST_TIMEOUT_S", "0.5"))


# ----------------------------
# ✅ 车间独立部署模式配置
# ----------------------------
# 车间机器的“请求来源 IP”（用于判断是否走车间固定端口模式）
WORKSHOP_CLIENT_IP = "10.9.100.195"
#WORKSHOP_CLIENT_IP = "10.0.1.8"

# 车间模式固定端口映射：对外固定为 10001/10002（返回给客户的口径）
WORKSHOP_PORT_8018 = 10001  # 对外访问端口：10001 -> 容器 8018
WORKSHOP_PORT_8019 = 10002  # 仍作为 subport 固定返回（不是 listen 端口）


def get_client_ip(req) -> str:
    """
    更稳的 client_ip 获取：优先 X-Forwarded-For，其次 remote_addr
    """
    xff = req.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return req.remote_addr or ""


def is_workshop_request(req) -> bool:
    """
    是否为车间独立部署机器的请求
    """
    return get_client_ip(req) == WORKSHOP_CLIENT_IP


# ----------------------------
# ✅ 并发竞态修复：全局创建锁（跨线程/跨进程）
# ----------------------------
@contextmanager
def global_create_lock(lock_path="/tmp/jushipaasapi-create-default.lock"):
    """
    解决并发竞态的最小改动方案：
    - 用 Linux flock 做互斥，保证「资源校验 → 选端口 → 创建 deployment/service → 读 service nodePort」
      这个关键区段串行化，避免并发穿透校验、端口重复选择等问题。
    - ⚠️ 只对“同一台机器/同一实例(同一文件系统)”生效；如果部署多副本，需要 Redis/DB 分布式锁。
    """
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o666)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


# 配置读取
def get_default_config():
    return {
        "api_base": os.getenv("DCE_API_BASE"),
        "token": (os.getenv("DCE_TOKEN") or "").strip('"'),
        "cluster": os.getenv("DCE_CLUSTER", "default"),
        "namespace": os.getenv("DCE_NAMESPACE", "default")
    }


# 统一响应结构封装
def make_response(content, msg_id, serial, context, http_status_code=200, msg="OK", status=-1):
    return jsonify({
        "msg_id": f"{msg_id}_Resp" if msg_id else "Resp",
        "head_id": 0,
        "context": context,
        "serial": serial,
        "version": "1.0.0.1",
        "status": status,
        "content": content,
        "token": "",
        "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "timestamp": int(time.time() * 1000),
        "http_status_code": http_status_code,
        "msg": msg,
        "is_success": 200 <= http_status_code < 300
    })


def parse_cpu(cpu_str):
    return float(cpu_str.replace("m", "")) if cpu_str.endswith("m") else float(cpu_str) * 1000


def parse_memory(mem_str):
    if not mem_str:
        return 0
    try:
        if mem_str.endswith("Ki"):
            return int(mem_str[:-2]) * 1024
        elif mem_str.endswith("Mi"):
            return int(mem_str[:-2]) * 1024 ** 2
        elif mem_str.endswith("Gi"):
            return int(mem_str[:-2]) * 1024 ** 3
        elif mem_str.endswith("Ti"):
            return int(mem_str[:-2]) * 1024 ** 4
        return int(mem_str)
    except Exception:
        return 0


# 通用 API 调用函数
def call_dce_api(method, url, token, data=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    logging.info(f"[Request] {method} {url}")
    try:
        if method in ['GET', 'DELETE']:
            resp = requests.request(method, url, headers=headers, verify=False)
        else:
            resp = requests.request(method, url, headers=headers, json=data, verify=False)

        logging.info(f"[Response] Status {resp.status_code}, Body: {resp.text}")
        try:
            return resp.status_code, resp.json()
        except Exception:
            return resp.status_code, {"raw": resp.text}
    except Exception as e:
        logging.error(f"Exception in API call: {e}")
        return 500, {"error": str(e)}

# 端口列表服务不可用异常
class PortListUnavailableError(RuntimeError):
    pass

# 从端口列表服务获取已封闭的端口列表
def fetch_blocked_ports_from_port_list():
    url = f"{PORT_LIST_API_BASE}{PORT_LIST_RESOLVE_PATH}"
    try:
        resp = requests.get(url, timeout=PORT_LIST_TIMEOUT_S)
    except requests.RequestException as e:
        raise PortListUnavailableError(f"port-list request failed: {e}")

    if resp.status_code != 200:
        raise PortListUnavailableError(f"port-list http {resp.status_code}, body={resp.text}")

    try:
        body = resp.json()
    except Exception as e:
        raise PortListUnavailableError(f"port-list response not json: {e}")

    content = body.get("content", {}) if isinstance(body, dict) else {}
    blocked = content.get("blocked_ports")
    if blocked is None:
        blocked = content.get("blocked_singles")  # 兼容字段
    if not isinstance(blocked, list):
        raise PortListUnavailableError("port-list payload missing content.blocked_ports")

    result = set()
    for p in blocked:
        try:
            pi = int(p)
            if 30000 <= pi <= 59999:
                result.add(pi)
        except Exception:
            continue
    return result


# ---------- 资源名映射 ----------
RESOURCE_NAME_MAP = {
    "NVIDIA/GPU": "nvidia.com/gpu"
}


def parse_optional_subport(content):
    raw = content.get("subport")
    if raw is None:
        return None, None
    if isinstance(raw, str):
        raw = raw.strip()
        if raw == "":
            return None, None
        if not raw.isdigit():
            return None, "content.subport must be an integer in [30000, 59999]"
        port = int(raw)
    elif isinstance(raw, bool):
        return None, "content.subport must be an integer in [30000, 59999]"
    elif isinstance(raw, int):
        port = raw
    else:
        return None, "content.subport must be an integer in [30000, 59999]"

    if not 30000 <= port <= 59999:
        return None, "content.subport must be in [30000, 59999]"
    return port, None


def check_resources_sufficient(api_base, token, cluster, devices,
                               min_cpu_m=2000, min_mem_bytes=4 * 1024 ** 3):
    """
    返回 (can_create, detail_dict)
    GPU 暴力模式：每个 deployment 占用 1 张 GPU 卡
    """
    namespace = "algorithm"
    gpu_resource_name = "nvidia.com/gpu"  # 默认 GPU 类型

    # Step 1: 获取集群资源信息
    cluster_url = f"{api_base}/clusters/{cluster}"
    status_code, resp = call_dce_api("GET", cluster_url, token)
    if status_code != 200 or not isinstance(resp, dict):
        return False, {
            "reason": "无法获取资源汇总",
            "http_status_code": status_code,
            "response": resp
        }

    alloc = resp.get("status", {}).get("resourceSummary", {}).get("allocatable", {}) or {}

    # Step 2: 获取 Deployment 列表（用数量代表占卡）
    deploy_url = f"{api_base}/clusters/{cluster}/namespaces/{namespace}/deployments"
    deploy_status, deploy_result = call_dce_api("GET", deploy_url, token)
    if deploy_status != 200:
        return False, {
            "reason": "获取部署列表失败",
            "http_status_code": deploy_status,
            "response": deploy_result
        }

    deployments = deploy_result.get("items", []) if isinstance(deploy_result, dict) else []
    gpu_used = len(deployments)  # 每个 Deployment 占用一张卡
    gpu_total = int(alloc.get(gpu_resource_name, 0))
    gpu_available = gpu_total - gpu_used

    # Step 3: GPU 请求判断
    gpu_ok = True
    gpu_details = {}
    for dev, req_count in (devices or {}).items():
        try:
            req_count_int = int(req_count)
        except Exception:
            req_count_int = 0

        k8s_dev = RESOURCE_NAME_MAP.get(dev, dev)
        gpu_details[k8s_dev] = {
            "requested": req_count_int,
            "available": gpu_available,
            "total": gpu_total,
            "used": gpu_used
        }
        if gpu_available < req_count_int:
            gpu_ok = False

    # Step 4: CPU / 内存判断
    used = resp.get("status", {}).get("resourceSummary", {}).get("allocated", {}) or {}
    cpu_available = parse_cpu(alloc.get("cpu", "0")) - parse_cpu(used.get("cpu", "0"))
    mem_available = parse_memory(alloc.get("memory", "0")) - parse_memory(used.get("memory", "0"))

    reasons = []
    if cpu_available < min_cpu_m:
        reasons.append(f"CPU不足（可用{cpu_available}m，需≥{min_cpu_m}m）")
    if mem_available < min_mem_bytes:
        reasons.append(f"内存不足（可用{mem_available}B，需≥{min_mem_bytes}B）")
    if not gpu_ok:
        reasons.append("GPU 卡数量不足")

    can_create = len(reasons) == 0
    detail = {
        "can_create": can_create,
        "reason": "；".join(reasons) if reasons else "资源充足",
        "cpu_available_m": cpu_available,
        "mem_available_bytes": mem_available,
        "gpu_details": gpu_details,
        "total_deployments": gpu_used
    }
    return can_create, detail


# 端口查找：避开已有 nodePort + 避开宿主机占用
def find_free_port_safe(api_base, cluster, namespace, token,
                        start=30000, end=59999, max_attempts=300):
    """
    更健壮的端口查找逻辑：
    - 查找指定范围内的随机端口；
    - 避免占用 nodePort（已存在的 service 端口）；
    - 避免宿主机已被绑定的端口。
    """
    url = f"{api_base}/clusters/{cluster}/namespaces/{namespace}/services"
    status_code, resp = call_dce_api("GET", url, token)
    existing_ports = set()

    blocked_ports = fetch_blocked_ports_from_port_list()  # 失败会抛 PortListUnavailableError
    existing_ports.update(blocked_ports)

    if status_code == 200 and isinstance(resp, dict):
        for svc in resp.get("items", []):
            for port_obj in svc.get("spec", {}).get("ports", []):
                node_port = port_obj.get("nodePort")
                if isinstance(node_port, int):
                    existing_ports.add(node_port)

    attempts = 0
    while attempts < max_attempts:
        port = random.randint(start, end)
        if port in existing_ports:
            attempts += 1
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                attempts += 1
                continue

    raise RuntimeError(f"No free port found after {max_attempts} attempts in range {start}-{end}")


# ✅ Service nodePort 读取重试（避免刚创建就拿不到 nodePort）
def get_service_nodeports_with_retry(api_base, token, cluster, namespace, name, retries=10, sleep_s=0.3):
    svc_get_url = f"{api_base}/clusters/{cluster}/namespaces/{namespace}/services/{name}"
    last = None
    for _ in range(retries):
        svc_detail_status, svc_detail = call_dce_api("GET", svc_get_url, token)
        last = (svc_detail_status, svc_detail)

        if svc_detail_status == 200 and isinstance(svc_detail, dict):
            ports = (svc_detail.get("spec", {}) or {}).get("ports", []) or []
            node_ports = [
                {"name": p.get("name", ""), "port": p.get("nodePort")}
                for p in ports
                if isinstance(p, dict) and p.get("nodePort")
            ]
            if node_ports:
                return node_ports

        time.sleep(sleep_s)

    logging.warning(f"[nodePort not ready] service={name}, last={last}")
    return []


# -----------------------------
# 1. 集群查询接口
# -----------------------------
@app.route("/api/cluster", methods=["POST"])
def cluster_retrieve():
    data = request.get_json() or {}
    msg_id = data.get("msg_id")
    serial = data.get("serial")
    context = data.get("context")
    try:
        cfg = get_default_config()
        api_base, token = cfg["api_base"], cfg["token"]
        status_code, result = call_dce_api("GET", f"{api_base}/clusters", token)
        return make_response(result, msg_id, serial, context, http_status_code=status_code, status=0 if status_code == 200 else -1)
    except Exception as e:
        return make_response({"error": str(e)}, msg_id, serial, context, http_status_code=500, msg="集群查询异常", status=-1)


# -----------------------------
# 2. Deploy 查询接口（增强：追加 Pod 状态）
# -----------------------------
@app.route("/api/deploy/retrieve", methods=["POST"])
def deploy_retrieve():
    data = request.get_json() or {}
    msg_id = data.get("msg_id")
    serial = data.get("serial")
    context = data.get("context")
    content = data.get("content", {}) or {}
    name = content.get("name", "")

    if not name:
        return make_response(
            {"error": "缺少必填字段：content.name"},
            msg_id, serial, context,
            http_status_code=400, msg="Bad Request", status=-1
        )

    try:
        cfg = get_default_config()
        api_base, token, cluster, namespace = (
            cfg["api_base"], cfg["token"], cfg["cluster"], cfg["namespace"]
        )

        dep_url = f"{api_base}/clusters/{cluster}/namespaces/{namespace}/deployments/{name}"
        dep_status, dep_result = call_dce_api("GET", dep_url, token)
        if dep_status != 200:
            return make_response(dep_result, msg_id, serial, context, http_status_code=dep_status, msg="Deploy 查询失败", status=-1)

        label_selector = f"app={name}"
        pod_url = (
            f"{api_base}/clusters/{cluster}/namespaces/{namespace}/pods"
            f"?labelSelector={quote_plus(label_selector)}"
        )
        pod_status, pod_result = call_dce_api("GET", pod_url, token)

        pod_states = []
        if pod_status == 200 and isinstance(pod_result, dict):
            for pod in pod_result.get("items", []):
                status_obj = pod.get("status", {}) or {}
                spec_obj = pod.get("spec", {}) or {}
                cs_list = status_obj.get("containerStatuses", []) or []
                containers = []
                for cs in cs_list:
                    st = cs.get("state") or {}
                    containers.append({
                        "name": cs.get("name"),
                        "ready": cs.get("ready"),
                        "restart_count": cs.get("restartCount"),
                        "state": list(st.keys())[0] if isinstance(st, dict) and st else None
                    })

                pod_states.append({
                    "pod_name": (pod.get("metadata", {}) or {}).get("name"),
                    "phase": status_obj.get("phase"),
                    "node_name": spec_obj.get("nodeName"),
                    "start_time": status_obj.get("startTime"),
                    "ip": status_obj.get("podIP"),
                    "containers": containers
                })

        summary = {
            "total_pods": len(pod_states),
            "running_pods": sum(1 for p in pod_states if p.get("phase") == "Running")
        }

        merged = {
            "deployment": dep_result,
            "pods": pod_states,
            "summary": summary
        }

        return make_response(merged, msg_id, serial, context, http_status_code=200, status=0)

    except Exception as e:
        logging.exception("Deploy 查询异常")
        return make_response(
            {"error": str(e)},
            msg_id, serial, context,
            http_status_code=500, msg="Deploy 查询异常", status=-1
        )


# -----------------------------
# 3. Deploy 创建接口（分支合并：普通模式 vs 车间固定端口模式）
# -----------------------------
@app.route("/api/deploy/create-default", methods=["POST"])
def create_deploy():
    data = request.get_json() or {}
    msg_id = data.get("msg_id")
    serial = data.get("serial")
    context = data.get("context")
    content = data.get("content", {}) or {}
    devices = content.get("devices", {}) or {}
    deploy_type = content.get("deployType", "")
    specified_subport, subport_error = parse_optional_subport(content)
    if subport_error:
        return make_response(
            {"error": subport_error},
            msg_id, serial, context,
            http_status_code=400, msg=subport_error, status=-1
        )

    try:
        cfg = get_default_config()
        api_base, token, cluster, namespace = cfg["api_base"], cfg["token"], cfg["cluster"], cfg["namespace"]

        creator = (content.get("creator")
                   or request.headers.get("X-User")
                   or request.headers.get("X-Forwarded-User")
                   or "unknown")

        client_ip = get_client_ip(request)
        workshop_mode = is_workshop_request(request)
        created_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        with global_create_lock():
            ok, detail = check_resources_sufficient(
                api_base=api_base,
                token=token,
                cluster=cluster,
                devices=devices,
                min_cpu_m=2000,
                min_mem_bytes=4 * 1024 ** 3
            )
            if not ok:
                return make_response(
                    {"can_create": False, **detail, "devices": devices},
                    msg_id, serial, context, http_status_code=400,
                    msg=detail.get("reason", "资源不足或卡不匹配"), status=-1
                )

            name = f"nvidia-cuda-{uuid.uuid4().hex[:6]}"

            limits = {"cpu": "8", "memory": "16Gi"}
            requests_ = {"cpu": "1", "memory": "2Gi"}
            for gpu_type, count in (devices or {}).items():
                k8s_gpu_type = RESOURCE_NAME_MAP.get(gpu_type, gpu_type)
                limits[k8s_gpu_type] = str(count)
                requests_[k8s_gpu_type] = str(count)

            log_host_path = f"/workspace/Alg/log/{name}"
            os.makedirs(log_host_path, exist_ok=True)

            # ✅ subport：普通模式动态；车间模式固定 10002（保持“最新方案”）
            if specified_subport is not None:
                free_port = specified_subport
            elif workshop_mode:
                free_port = WORKSHOP_PORT_8019
            else:
                try:
                    free_port = find_free_port_safe(
                        api_base=api_base, cluster=cluster, namespace=namespace, token=token,start=30000,end=59999,max_attempts=3
                    )
                except PortListUnavailableError as e:
                    return make_response(
                        content={"error": "port-list unavailable", "reason": str(e)},
                        msg_id=msg_id, serial=serial, context=context,
                        http_status_code=503, msg="端口封闭服务不可用，创建已拒绝", status=-1
                    )


            # ✅ 显示 creator/ip
            creator_display = f"{creator}/{client_ip}" if client_ip else creator

            # ✨ 在 Deployment / PodTemplate / Service 写入 creator 等标记
            alias_name = f"{creator_display}"


            # ✅ 容器端口：
            # - 算法容器内部实际监听：8018（保持事实与旧逻辑）
            # - 车间模式对外固定端口：用 hostPort 10001 -> containerPort 8018
            if workshop_mode:
                container_ports = [{
                    "containerPort": 8018,
                    "hostPort": WORKSHOP_PORT_8018,
                    "protocol": "TCP"
                }]
            else:
                container_ports = [{"containerPort": 8018, "protocol": "TCP"}]

            deployment = {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {
                    "name": name,
                    "namespace": namespace,
                    "labels": {
                        "app": name,
                        "creator": creator
                    },
                    "annotations": {
                        "kpanda.io/alias-name": alias_name,
                        "createdAt": created_at,
                        "creatorIp": client_ip,
                        "deployType": deploy_type or "",
                        "workshopMode": "true" if workshop_mode else "false"
                    }
                },
                "spec": {
                    "replicas": 1,
                    "selector": {"matchLabels": {"app": name}},
                    "template": {
                        "metadata": {
                            "labels": {
                                "app": name,
                                "creator": creator
                            }
                        },
                        "spec": {
                            "initContainers": [{
                                "name": "init-copy-unzip",
                                "image": "busybox",
                                "imagePullPolicy": "IfNotPresent",
                                "command": ["sh", "-c"],
                                "args": [
                                    f"cp /zip/mtworkflow_x86.zip /workspace/Alg/ && "
                                    f"unzip -o /workspace/Alg/mtworkflow_x86.zip -d /workspace/Alg/ && "
                                    f"sed -i '88s/\\\"subip\\\": *\\\"[^\\\"]*\\\"/\\\"subip\\\":\\\"{client_ip}\\\"/;"
                                    f"89s/\\\"subport\\\": *[0-9]\\+/\\\"subport\\\":{free_port}/' "
                                    f"/workspace/Alg/mtworkflow_x86/cfg/runmode.cfg"
                                ],
                                "volumeMounts": [
                                    {"name": "volume-alg", "mountPath": "/workspace/Alg/"},
                                    {"name": "volume-zip", "mountPath": "/zip"}
                                ]
                            }],
                            "containers": [{
                                "name": name,
                                "image": "nvidia/cuda:11.6.2-cudnn8-devel-ubuntu20.04_v1",
                                "imagePullPolicy": "IfNotPresent",
                                "command": ["sh", "-c"],
                                "args": ["cd /workspace/Alg/mtworkflow_x86/; chmod +x mtworkflow*;stdbuf -o0 sh mtworkflow.sh;"],
                                "ports": container_ports,
                                "resources": {"limits": limits, "requests": requests_},
                                "volumeMounts": [
                                    {"mountPath": "/workspace/Alg/", "name": "volume-alg"},
                                    {"mountPath": "/dev/shm", "name": "volume-memory"},
                                    {"mountPath": "/workspace/Alg/mtworkflow_arm/log/", "name": "volume-log"},
                                    {"mountPath": "/root/ADCShared/", "name": "volume-root"}
                                ]
                            }],
                            "volumes": [
                                {"emptyDir": {}, "name": "volume-alg"},
                                {"hostPath": {"path": "/opt", "type": ""}, "name": "volume-zip"},
                                {"emptyDir": {"medium": "Memory", "sizeLimit": "16Gi"}, "name": "volume-memory"},
                                {"hostPath": {"path": log_host_path, "type": ""}, "name": "volume-log"},
                                {"hostPath": {"path": "/disks/sda/jx5000/", "type": ""}, "name": "volume-root"}
                            ]
                        }
                    }
                }
            }

            # ✅ Service：
            # - 普通模式：保留 NodePort（旧逻辑不变）
            # - 车间模式：不创建 Service（对外访问走 节点IP:10001）
            create_service = not workshop_mode

            if create_service:
                service = {
                    "apiVersion": "v1",
                    "kind": "Service",
                    "metadata": {
                        "name": name,
                        "namespace": namespace,
                        "labels": {
                            "app": name,
                            "creator": creator
                        },
                        "annotations": {
                            "createdAt": created_at,
                            "creatorIp": client_ip,
                            "deployType": deploy_type or "",
                            "workshopMode": "false"
                        }
                    },
                    "spec": {
                        "type": "NodePort",
                        "selector": {"app": name},
                        "ports": [
                            {"name": "tcp-8018", "port": 8018, "targetPort": 8018, "protocol": "TCP"}
                        ]
                    }
                }

            deployment_data = {
                "cluster": cluster,
                "namespace": namespace,
                "kind": "deployments",
                "data": json.dumps(deployment, separators=(',', ':'))
            }
            deploy_url = f"{api_base}/clusters/{cluster}/namespaces/{namespace}/deployments/json"
            dep_create_status, dep_create_result = call_dce_api("POST", deploy_url, token, data=deployment_data)
            if not (200 <= dep_create_status < 300):
                return make_response(
                    {"error": "Deployment 创建失败", "response": dep_create_result},
                    msg_id, serial, context,
                    http_status_code=dep_create_status, msg="创建失败", status=-1
                )

            node_ports = []

            if create_service:
                service_data = {
                    "cluster": cluster,
                    "namespace": namespace,
                    "data": json.dumps(service, separators=(',', ':'))
                }
                service_url = f"{api_base}/clusters/{cluster}/namespaces/{namespace}/services"
                svc_create_status, svc_create_result = call_dce_api("POST", service_url, token, data=service_data)
                if not (200 <= svc_create_status < 300):
                    # 回滚 deployment（best-effort）
                    try:
                        call_dce_api("DELETE",
                                     f"{api_base}/clusters/{cluster}/namespaces/{namespace}/deployments/{name}",
                                     token)
                    except Exception:
                        logging.exception("Service 创建失败后的回滚 Deployment 异常（忽略）")

                    return make_response(
                        {"error": "Service 创建失败", "response": svc_create_result},
                        msg_id, serial, context,
                        http_status_code=svc_create_status, msg="创建失败", status=-1
                    )

                node_ports = get_service_nodeports_with_retry(api_base, token, cluster, namespace, name)
                # 保持旧逻辑：把 subport 也返回给上层
                node_ports.append({"name": "tcp-8019", "port": free_port})
            else:
                # ✅ 车间模式固定返回：对外访问 10001；subport 固定 10002
                node_ports = [
                    {"name": "tcp-8018", "port": WORKSHOP_PORT_8018},
                    {"name": "tcp-8019", "port": WORKSHOP_PORT_8019}
                ]

            return make_response(
                content={
                    "deployment_name": name,
                    "node_ports": node_ports,
                    "devices": devices,
                    "gpu_type": list(devices.keys())[0] if devices else None,
                    "deployType": deploy_type,
                    "log_path": log_host_path,
                    "workshop_mode": workshop_mode,
                    "client_ip": client_ip
                },
                msg_id=msg_id, serial=serial, context=context,
                http_status_code=200, status=0
            )

    except Exception as e:
        logging.exception("创建失败：")
        return make_response(
            content={"error": str(e)},
            msg_id=msg_id, serial=serial, context=context,
            http_status_code=500, msg="创建失败", status=-1
        )


# -----------------------------
# 4. Deploy 删除接口
# -----------------------------
@app.route("/api/deploy/release", methods=["POST"])
def deploy_release():
    data = request.get_json() or {}
    msg_id = data.get("msg_id")
    serial = data.get("serial")
    context = data.get("context")
    content = data.get("content", {}) or {}
    name = content.get("name")

    if not name:
        return make_response({"error": "缺少必填字段：content.name"}, msg_id, serial, context, http_status_code=400, msg="Bad Request", status=-1)

    try:
        cfg = get_default_config()
        api_base, token, cluster, namespace = cfg["api_base"], cfg["token"], cfg["cluster"], cfg["namespace"]

        deploy_url = f"{api_base}/clusters/{cluster}/namespaces/{namespace}/deployments/{name}"
        deploy_status, deploy_result = call_dce_api("DELETE", deploy_url, token)

        svc_url = f"{api_base}/clusters/{cluster}/namespaces/{namespace}/services/{name}"
        svc_status, svc_result = call_dce_api("DELETE", svc_url, token)

        log_host_path = f"/workspace/Alg/log/{name}"

        response_content = {
            "deployment_delete": deploy_result,
            "service_delete": svc_result,
            "log_path": log_host_path
        }

        if 200 <= deploy_status < 300 and (svc_status == 404 or 200 <= svc_status < 300):
            # ✅ 车间模式可能没有 Service，这里允许 404
            return make_response(response_content, msg_id, serial, context, http_status_code=200, status=0)
        else:
            return make_response(response_content, msg_id, serial, context, http_status_code=max(deploy_status, svc_status), status=-1, msg="部分资源释放失败")

    except Exception as e:
        logging.exception("Deploy 释放异常")
        return make_response({"error": str(e)}, msg_id, serial, context, http_status_code=500, msg="Deploy 释放异常", status=-1)


# -----------------------------
# 5. Deploy 重启接口
# -----------------------------
@app.route("/api/deploy/reset", methods=["POST"])
def deploy_reset():
    data = request.get_json() or {}
    msg_id = data.get("msg_id")
    serial = data.get("serial")
    context = data.get("context")
    content = data.get("content", {}) or {}
    name = content.get("name")

    if not name:
        return make_response({"error": "缺少必填字段：content.name"}, msg_id, serial, context, http_status_code=400, msg="Bad Request", status=-1)

    try:
        cfg = get_default_config()
        api_base = cfg["api_base"]
        token = cfg["token"]
        url = f"{api_base}/clusters/{cfg['cluster']}/namespaces/{cfg['namespace']}/deployments/{name}:restart"
        status_code, result = call_dce_api("POST", url, token)
        return make_response(result, msg_id, serial, context, http_status_code=status_code, status=0 if 200 <= status_code < 300 else -1)
    except Exception as e:
        logging.exception("Deploy 重启异常")
        return make_response({"error": str(e)}, msg_id, serial, context, http_status_code=500, msg="Deploy 重启异常", status=-1)


# -----------------------------
# 6. 检查是否可创建
# -----------------------------
@app.route("/api/deploy/check-available", methods=["POST"])
def check_deploy_available():
    data = request.get_json() or {}
    msg_id = data.get("msg_id")
    serial = data.get("serial")
    context = data.get("context")
    content = data.get("content", {}) or {}
    devices = content.get("devices", {}) or {}

    try:
        cfg = get_default_config()
        ok, detail = check_resources_sufficient(
            api_base=cfg["api_base"],
            token=cfg["token"],
            cluster=cfg["cluster"],
            devices=devices,
            min_cpu_m=2000,
            min_mem_bytes=4 * 1024 ** 3
        )
        http_code = 200 if ok else 400
        return make_response({**detail, "devices": devices}, msg_id, serial, context, http_status_code=http_code, msg=detail.get("reason", "OK"), status=0 if ok else -1)
    except Exception as e:
        logging.exception("校验异常")
        return make_response({"error": str(e)}, msg_id, serial, context, http_status_code=500, msg="校验异常", status=-1)


# -----------------------------
# 7. Deploy列表
# -----------------------------
@app.route("/api/deploy/list", methods=["POST"])
def list_deployments():
    data = request.get_json() or {}
    msg_id, serial, context = data.get("msg_id"), data.get("serial"), data.get("context")
    try:
        cfg = get_default_config()
        url = f"{cfg['api_base']}/clusters/{cfg['cluster']}/namespaces/{cfg['namespace']}/deployments"
        status_code, result = call_dce_api("GET", url, cfg["token"])
        return make_response(result, msg_id, serial, context, http_status_code=status_code, status=0 if status_code == 200 else -1)
    except Exception as e:
        logging.exception("查询异常")
        return make_response({"error": str(e)}, msg_id, serial, context, http_status_code=500, msg="查询异常", status=-1)


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080, debug=True)
