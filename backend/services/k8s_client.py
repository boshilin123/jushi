import json
import subprocess

KUBECTL = "/usr/bin/kubectl"


class K8sClient:
    def list_pods(self, namespace: str):
        pods = _kubectl_json(["get", "pods", "-n", namespace, "-o", "json"])
        items = []
        for p in pods.get("items", []):
            meta = p.get("metadata", {})
            status = p.get("status", {})
            spec = p.get("spec", {})
            restart_count = 0
            ready = False
            for cs in status.get("containerStatuses", []) or []:
                restart_count += cs.get("restartCount", 0)
                if cs.get("ready"):
                    ready = True
            items.append({
                "pod_name": meta.get("name"),
                "namespace": meta.get("namespace"),
                "phase": status.get("phase"),
                "node_name": spec.get("nodeName"),
                "pod_ip": status.get("podIP"),
                "restart_count": restart_count,
                "ready": ready,
                "created_at": meta.get("creationTimestamp"),
            })
        return items

    def read_pod(self, namespace: str, pod_name: str) -> dict:
        p = _kubectl_json(["get", "pod", pod_name, "-n", namespace, "-o", "json"])
        meta = p.get("metadata", {})
        status = p.get("status", {})
        spec = p.get("spec", {})

        restart_count = 0
        ready = False
        containers = []
        for cs in status.get("containerStatuses", []) or []:
            restart_count += cs.get("restartCount", 0)
            if cs.get("ready"):
                ready = True
            containers.append({
                "name": cs.get("name"),
                "image": cs.get("image"),
                "ready": cs.get("ready"),
                "restart_count": cs.get("restartCount", 0),
                "state": _container_state(cs.get("state")),
            })

        events = _list_events(namespace, pod_name)

        return {
            "pod_name": meta.get("name"),
            "namespace": meta.get("namespace"),
            "phase": status.get("phase"),
            "node_name": spec.get("nodeName"),
            "pod_ip": status.get("podIP"),
            "host_ip": status.get("hostIP"),
            "restart_count": restart_count,
            "ready": ready,
            "created_at": meta.get("creationTimestamp"),
            "containers": containers,
            "events": events,
        }

    def pod_logs(self, namespace: str, pod_name: str, tail_lines: int = 200):
        try:
            result = _kubectl([
                "logs", pod_name, "-n", namespace,
                "--tail", str(tail_lines),
            ])
            return result.splitlines() if result else []
        except subprocess.CalledProcessError:
            return []

    def delete_pod(self, namespace: str, pod_name: str) -> bool:
        try:
            _kubectl(["delete", "pod", pod_name, "-n", namespace, "--wait=false"])
            return True
        except subprocess.CalledProcessError as exc:
            output = exc.output.decode("utf-8", errors="replace") if exc.output else ""
            if "NotFound" in output:
                return False
            raise


def _container_state(state) -> str:
    if not state:
        return "unknown"
    if "running" in state:
        return "running"
    if "waiting" in state:
        return state["waiting"].get("reason", "waiting")
    if "terminated" in state:
        return state["terminated"].get("reason", "terminated")
    return "unknown"


def _list_events(namespace: str, pod_name: str) -> list[dict]:
    try:
        events = _kubectl_json([
            "get", "events", "-n", namespace,
            "--field-selector", f"involvedObject.name={pod_name}",
            "-o", "json",
        ])
    except subprocess.CalledProcessError:
        return []

    result = []
    for e in events.get("items", []):
        result.append({
            "type": e.get("type"),
            "reason": e.get("reason"),
            "message": e.get("message"),
            "first_timestamp": e.get("firstTimestamp"),
            "last_timestamp": e.get("lastTimestamp"),
        })
    return result


def _kubectl(args: list[str]) -> str:
    return subprocess.check_output(
        [KUBECTL] + args,
        stderr=subprocess.STDOUT,
        timeout=30,
    ).decode("utf-8", errors="replace")


def _kubectl_json(args: list[str]) -> dict:
    out = subprocess.check_output(
        [KUBECTL] + args,
        stderr=subprocess.STDOUT,
        timeout=30,
    )
    return json.loads(out)
