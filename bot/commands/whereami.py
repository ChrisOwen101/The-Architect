from __future__ import annotations
from typing import Optional
import os
import sys
import platform
import json
import socket
from pathlib import Path
from . import command


@command(
    name="whereami",
    description="Detect and report comprehensive host platform details including OS, kernel, hardware, container, and virtualization information"
)
async def whereami_handler(matrix_context: Optional[dict] = None) -> Optional[str]:
    """
    Safely detect and report host platform details without using subprocess.

    Returns a JSON object with detailed system information including:
    - OS details (name, version, id_like)
    - Kernel information
    - Architecture and hostname
    - CPU details (model, cores, flags)
    - Memory statistics
    - System uptime
    - Init system details
    - Container detection
    - Virtualization detection
    - Raspberry Pi detection

    No external files are modified by this command.
    """
    result = {
        "os": _detect_os(),
        "kernel": _detect_kernel(),
        "arch": platform.machine(),
        "hostname": _get_hostname(),
        "cpu": _detect_cpu(),
        "memory": _detect_memory(),
        "uptime_seconds": _get_uptime(),
        "init": _detect_init(),
        "container": _detect_container(),
        "virtualization": _detect_virtualization(),
        "raspberry_pi": _detect_raspberry_pi()
    }

    # Return formatted JSON
    return "```json\n" + json.dumps(result, indent=2) + "\n```"


def _detect_os() -> dict:
    """Parse /etc/os-release for OS information."""
    os_info = {
        "name": None,
        "version": None,
        "id_like": None
    }

    try:
        os_release_path = Path("/etc/os-release")
        if os_release_path.exists():
            with open(os_release_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("NAME="):
                        os_info["name"] = line.split("=", 1)[1].strip('"')
                    elif line.startswith("VERSION="):
                        os_info["version"] = line.split("=", 1)[1].strip('"')
                    elif line.startswith("ID_LIKE="):
                        os_info["id_like"] = line.split("=", 1)[1].strip('"')
    except Exception:
        pass

    # Fallback to platform module
    if not os_info["name"]:
        os_info["name"] = platform.system()
    if not os_info["version"]:
        os_info["version"] = platform.version()

    return os_info


def _detect_kernel() -> dict:
    """Get kernel release and version."""
    return {
        "release": platform.release(),
        "version": platform.version()
    }


def _get_hostname() -> str:
    """Get system hostname."""
    try:
        return socket.gethostname()
    except Exception:
        return None


def _detect_cpu() -> dict:
    """Read CPU information from /proc/cpuinfo."""
    cpu_info = {
        "model": None,
        "cores": os.cpu_count(),
        "flags": []
    }

    try:
        cpuinfo_path = Path("/proc/cpuinfo")
        if cpuinfo_path.exists():
            with open(cpuinfo_path, "r") as f:
                for line in f:
                    line = line.strip()

                    # x86/x64 model name
                    if line.startswith("model name"):
                        if not cpu_info["model"]:
                            cpu_info["model"] = line.split(":", 1)[1].strip()

                    # ARM/other architectures
                    elif line.startswith("model") and ":" in line and not cpu_info["model"]:
                        cpu_info["model"] = line.split(":", 1)[1].strip()
                    elif line.startswith("Hardware") and ":" in line and not cpu_info["model"]:
                        cpu_info["model"] = line.split(":", 1)[1].strip()
                    elif line.startswith("Processor") and ":" in line and not cpu_info["model"]:
                        cpu_info["model"] = line.split(":", 1)[1].strip()

                    # CPU flags (x86/x64)
                    elif line.startswith("flags") and ":" in line:
                        if not cpu_info["flags"]:
                            flags_str = line.split(":", 1)[1].strip()
                            cpu_info["flags"] = flags_str.split()

                    # CPU features (ARM)
                    elif line.startswith("Features") and ":" in line:
                        if not cpu_info["flags"]:
                            flags_str = line.split(":", 1)[1].strip()
                            cpu_info["flags"] = flags_str.split()
    except Exception:
        pass

    return cpu_info


def _detect_memory() -> dict:
    """Parse /proc/meminfo for memory statistics."""
    memory_info = {
        "mem_total_bytes": None,
        "mem_available_bytes": None,
        "swap_total_bytes": None,
        "swap_free_bytes": None
    }

    try:
        meminfo_path = Path("/proc/meminfo")
        if meminfo_path.exists():
            with open(meminfo_path, "r") as f:
                for line in f:
                    line = line.strip()
                    parts = line.split()

                    if len(parts) >= 2:
                        key = parts[0].rstrip(":")
                        value_kb = int(parts[1])
                        value_bytes = value_kb * 1024

                        if key == "MemTotal":
                            memory_info["mem_total_bytes"] = value_bytes
                        elif key == "MemAvailable":
                            memory_info["mem_available_bytes"] = value_bytes
                        elif key == "SwapTotal":
                            memory_info["swap_total_bytes"] = value_bytes
                        elif key == "SwapFree":
                            memory_info["swap_free_bytes"] = value_bytes
    except Exception:
        pass

    return memory_info


def _get_uptime() -> float:
    """Read system uptime from /proc/uptime."""
    try:
        uptime_path = Path("/proc/uptime")
        if uptime_path.exists():
            with open(uptime_path, "r") as f:
                uptime_str = f.read().strip().split()[0]
                return float(uptime_str)
    except Exception:
        pass

    return None


def _detect_init() -> dict:
    """Detect init system from /proc/1/comm and /proc/1/cmdline."""
    init_info = {
        "pid1_comm": None,
        "pid1_cmdline": None
    }

    try:
        comm_path = Path("/proc/1/comm")
        if comm_path.exists():
            with open(comm_path, "r") as f:
                init_info["pid1_comm"] = f.read().strip()
    except Exception:
        pass

    try:
        cmdline_path = Path("/proc/1/cmdline")
        if cmdline_path.exists():
            with open(cmdline_path, "rb") as f:
                cmdline_bytes = f.read()
                # Replace NULL bytes with spaces
                cmdline_str = cmdline_bytes.decode("utf-8", errors="replace").replace("\x00", " ").strip()
                init_info["pid1_cmdline"] = cmdline_str
    except Exception:
        pass

    return init_info


def _detect_container() -> dict:
    """Detect container environment from /.dockerenv and cgroups."""
    container_info = {
        "is_container": False,
        "engine": None
    }

    # Check for /.dockerenv
    if Path("/.dockerenv").exists():
        container_info["is_container"] = True
        container_info["engine"] = "docker"
        return container_info

    # Check cgroups
    try:
        cgroup_paths = [Path("/proc/self/cgroup"), Path("/proc/1/cgroup")]

        for cgroup_path in cgroup_paths:
            if cgroup_path.exists():
                with open(cgroup_path, "r") as f:
                    for line in f:
                        line_lower = line.lower()

                        if "docker" in line_lower:
                            container_info["is_container"] = True
                            if not container_info["engine"]:
                                container_info["engine"] = "docker"
                        elif "kubepods" in line_lower or "kubernetes" in line_lower:
                            container_info["is_container"] = True
                            if not container_info["engine"]:
                                container_info["engine"] = "kubernetes"
                        elif "libpod" in line_lower or "podman" in line_lower:
                            container_info["is_container"] = True
                            if not container_info["engine"]:
                                container_info["engine"] = "libpod"

                if container_info["is_container"] and not container_info["engine"]:
                    container_info["engine"] = "unknown"
    except Exception:
        pass

    return container_info


def _detect_virtualization() -> dict:
    """Detect virtualization from DMI info and CPU flags."""
    virt_info = {
        "detected": False,
        "type": None,
        "source": None
    }

    # Check DMI information
    dmi_paths = {
        "product_name": Path("/sys/class/dmi/id/product_name"),
        "sys_vendor": Path("/sys/class/dmi/id/sys_vendor")
    }

    dmi_values = {}
    for key, path in dmi_paths.items():
        try:
            if path.exists():
                with open(path, "r") as f:
                    dmi_values[key] = f.read().strip().lower()
        except Exception:
            pass

    # Map common virtualization strings
    virt_mappings = {
        "kvm": "KVM",
        "qemu": "QEMU",
        "virtualbox": "VirtualBox",
        "vmware": "VMware",
        "microsoft": "Hyper-V",
        "xen": "Xen",
        "bochs": "Bochs",
        "parallels": "Parallels"
    }

    for dmi_key, dmi_value in dmi_values.items():
        for search_str, virt_type in virt_mappings.items():
            if search_str in dmi_value:
                virt_info["detected"] = True
                virt_info["type"] = virt_type
                virt_info["source"] = f"dmi_{dmi_key}"
                return virt_info

    # Check CPU flags for hypervisor flag
    cpu_info = _detect_cpu()
    if "hypervisor" in cpu_info.get("flags", []):
        virt_info["detected"] = True
        if not virt_info["type"]:
            virt_info["type"] = "unknown"
        virt_info["source"] = "cpu_flags"

    return virt_info


def _detect_raspberry_pi() -> dict:
    """Detect Raspberry Pi from device tree or cpuinfo."""
    rpi_info = {
        "is_rpi": False,
        "model": None
    }

    # Try device tree model files
    dt_paths = [
        Path("/proc/device-tree/model"),
        Path("/sys/firmware/devicetree/base/model")
    ]

    for dt_path in dt_paths:
        try:
            if dt_path.exists():
                with open(dt_path, "rb") as f:
                    model_bytes = f.read()
                    # Strip null bytes
                    model_str = model_bytes.decode("utf-8", errors="replace").replace("\x00", "").strip()

                    if "raspberry pi" in model_str.lower():
                        rpi_info["is_rpi"] = True
                        rpi_info["model"] = model_str
                        return rpi_info
        except Exception:
            pass

    # Fallback to /proc/cpuinfo
    try:
        cpuinfo_path = Path("/proc/cpuinfo")
        if cpuinfo_path.exists():
            with open(cpuinfo_path, "r") as f:
                for line in f:
                    if "raspberry pi" in line.lower():
                        rpi_info["is_rpi"] = True
                        # Extract model from the line
                        if ":" in line:
                            rpi_info["model"] = line.split(":", 1)[1].strip()
                        else:
                            rpi_info["model"] = line.strip()
                        return rpi_info
    except Exception:
        pass

    return rpi_info
