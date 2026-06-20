import socket
import ipaddress
import concurrent.futures
import requests
from typing import List, Dict, Optional

WORKER_PORT = 8090
WORKER_API_HEALTH = "/api/health"
WORKER_API_GPU = "/api/gpu"


def get_local_subnet() -> str:
    """Get local machine's subnet in CIDR notation."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
    finally:
        s.close()

    network = ipaddress.ip_network(f"{local_ip}/24", strict=False)
    return str(network)


def check_worker_health(host: str, port: int = WORKER_PORT, timeout: float = 1.0) -> Optional[Dict]:
    """Check if a host is running a PoolGPU Worker."""
    try:
        response = requests.get(
            f"http://{host}:{port}{WORKER_API_HEALTH}",
            timeout=timeout
        )
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None


def check_worker_gpu(host: str, port: int = WORKER_PORT, timeout: float = 1.0) -> Optional[Dict]:
    """Get GPU info from a worker."""
    try:
        response = requests.get(
            f"http://{host}:{port}{WORKER_API_GPU}",
            timeout=timeout
        )
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None


def _scan_host(args):
    """Scan a single host (for thread pool)."""
    host, port, timeout = args
    health = check_worker_health(host, port, timeout)
    if health:
        gpu_info = check_worker_gpu(host, port, timeout)
        return {
            "host": host,
            "port": port,
            "health": health,
            "gpu": gpu_info
        }
    return None


def discover_workers(subnet: str = None, port: int = WORKER_PORT, timeout: float = 1.0) -> List[Dict]:
    """Discover PoolGPU workers on the network."""
    if subnet is None:
        subnet = get_local_subnet()

    network = ipaddress.ip_network(subnet, strict=False)
    targets = [(str(ip), port, timeout) for ip in network.hosts()]

    workers = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        results = executor.map(_scan_host, targets)
        for result in results:
            if result:
                workers.append(result)

    return workers
