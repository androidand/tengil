import os
import re
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional


class SystemDetector:
    """
    Collects hardware and system-level facts for Tengil.
    Used by state_store, recommender, and CLI diagnostics.
    """

    def __init__(self, run_cmd=None):
        self.run_cmd = run_cmd or self._run

    # -----------------------------
    #  Core detection entry point
    # -----------------------------
    def detect_all(self) -> Dict[str, Any]:
        return {
            "cpu": self._detect_cpu(),
            "gpu": self._detect_gpu(),
            "memory": self._detect_memory(),
            "network": self._detect_network(),
            "storage": self._detect_storage(),
            "os": self._detect_os(),
        }

    # -----------------------------
    #  Individual detectors
    # -----------------------------
    def _detect_cpu(self) -> Dict[str, Any]:
        try:
            output = self.run_cmd("lscpu")
            model = re.search(r"Model name:\s+(.+)", output)
            cores = re.search(r"Core\(s\) per socket:\s+(\d+)", output)
            sockets = re.search(r"Socket\(s\):\s+(\d+)", output)
            threads = re.search(r"Thread\(s\) per core:\s+(\d+)", output)

            total_cores = (
                int(cores.group(1)) * int(sockets.group(1)) if cores and sockets else None
            )
            total_threads = (
                total_cores * int(threads.group(1)) if total_cores and threads else None
            )

            return {
                "model": model.group(1).strip() if model else "Unknown CPU",
                "cores": total_cores or 0,
                "threads": total_threads or 0,
            }
        except Exception:
            return {"model": "Unknown", "cores": 0, "threads": 0}

    def _detect_gpu(self) -> List[Dict[str, Any]]:
        gpus = []
        try:
            # NVIDIA
            if self._cmd_exists("nvidia-smi"):
                out = self.run_cmd(
                    "nvidia-smi --query-gpu=name,driver_version --format=csv,noheader"
                )
                for line in out.splitlines():
                    parts = [x.strip() for x in line.split(",")]
                    if len(parts) >= 2:
                        gpus.append({"type": "nvidia", "model": parts[0], "driver": parts[1]})

            # Intel
            intel = self.run_cmd("lspci | grep -i 'vga.*intel' || true").strip()
            if intel:
                gpus.append({"type": "intel", "model": intel.split(":")[-1].strip()})

            # AMD
            amd = self.run_cmd("lspci | grep -i 'vga.*amd' || true").strip()
            if amd:
                gpus.append({"type": "amd", "model": amd.split(":")[-1].strip()})

        except Exception:
            pass

        return gpus

    def _detect_memory(self) -> Dict[str, Any]:
        try:
            meminfo = self.run_cmd("grep MemTotal /proc/meminfo")
            total_kb = int(re.findall(r"\d+", meminfo)[0])
            total_gb = round(total_kb / 1024 / 1024, 1)
            return {"total_gb": total_gb}
        except Exception:
            return {"total_gb": 0}

    def _detect_network(self) -> List[Dict[str, Any]]:
        try:
            output = self.run_cmd("ip -o link show | awk -F': ' '{print $2}'")
            interfaces = [iface for iface in output.splitlines() if iface != "lo"]
            return [{"name": iface, "up": self._iface_up(iface)} for iface in interfaces]
        except Exception:
            return []

    def _detect_storage(self) -> List[Dict[str, Any]]:
        try:
            out = self.run_cmd("zpool list -H -o name,size,alloc,free,health")
            pools = []
            for line in out.splitlines():
                name, size, alloc, free, health = line.split()
                pools.append(
                    {"name": name, "size": size, "alloc": alloc, "free": free, "health": health}
                )
            return pools
        except Exception:
            return []

    def _detect_os(self) -> Dict[str, str]:
        try:
            data = Path("/etc/os-release").read_text()
            name = re.search(r'PRETTY_NAME="(.+)"', data)
            kernel = self.run_cmd("uname -r")
            return {"name": name.group(1) if name else "Unknown", "kernel": kernel.strip()}
        except Exception:
            return {"name": "Unknown", "kernel": "Unknown"}

    # -----------------------------
    #  Utility helpers
    # -----------------------------
    def _iface_up(self, iface: str) -> bool:
        try:
            status = self.run_cmd(f"cat /sys/class/net/{iface}/operstate").strip()
            return status == "up"
        except Exception:
            return False

    def _cmd_exists(self, cmd: str) -> bool:
        return subprocess.call(["which", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0

    def _run(self, cmd: str) -> str:
        return subprocess.getoutput(cmd)

    # -----------------------------
    #  Persistence helpers
    # -----------------------------
    def save_state(self, dest: Optional[Path] = None) -> Path:
        dest = dest or Path.home() / ".tengil" / "system.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        state = self.detect_all()
        with dest.open("w") as f:
            json.dump(state, f, indent=2)
        return dest
