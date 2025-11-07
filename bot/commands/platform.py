"""Platform detection command - reports comprehensive host system information."""
from __future__ import annotations
import os
import platform
import re
from pathlib import Path
from typing import Optional
from . import command


@command(
    name="platform",
    description="Detect and report the host platform details: OS name/version, kernel version, architecture, hostname, CPU model/cores (including Raspberry Pi model detection), containerization (Docker/other) via /.dockerenv and cgroups, init system (PID 1), virtualization (systemd-detect-virt if available), uptime, and memory totals from /proc/meminfo."
)
async def platform_handler(matrix_context: Optional[dict] = None) -> Optional[str]:
    """
    Detect and report comprehensive host platform information.

    Gathers information about:
    - OS name and version (from /etc/os-release)
    - Kernel version
    - Architecture
    - Hostname
    - CPU model and core count (including Raspberry Pi model detection from /proc/cpuinfo)
    - Containerization detection (Docker via /.dockerenv, other via cgroups)
    - Init system (PID 1)
    - Virtualization (systemd-detect-virt if available)
    - System uptime
    - Memory information (total from /proc/meminfo)

    Args:
        matrix_context: Optional Matrix context dict (unused)

    Returns:
        Formatted string with platform details, or error message
    """
    info_lines = []

    try:
        # OS Information from /etc/os-release
        os_name = "Unknown"
        os_version = "Unknown"
        try:
            os_release = Path("/etc/os-release")
            if os_release.exists():
                with open(os_release) as f:
                    os_release_data = {}
                    for line in f:
                        line = line.strip()
                        if '=' in line:
                            key, value = line.split('=', 1)
                            os_release_data[key] = value.strip('"')
                    os_name = os_release_data.get('PRETTY_NAME', os_release_data.get('NAME', 'Unknown'))
                    os_version = os_release_data.get('VERSION', os_release_data.get('VERSION_ID', ''))
        except Exception:
            os_name = platform.system()
            os_version = platform.release()

        info_lines.append(f"🖥️  **OS**: {os_name}")
        if os_version and os_version != "Unknown":
            info_lines.append(f"📦 **Version**: {os_version}")

        # Kernel version
        kernel = platform.release()
        info_lines.append(f"🔧 **Kernel**: {kernel}")

        # Architecture
        arch = platform.machine()
        info_lines.append(f"🏗️  **Architecture**: {arch}")

        # Hostname
        hostname = platform.node()
        info_lines.append(f"🌐 **Hostname**: {hostname}")

        # CPU Information (including Raspberry Pi detection)
        cpu_model = "Unknown"
        cpu_cores = os.cpu_count() or 0
        rpi_model = None

        try:
            cpuinfo_path = Path("/proc/cpuinfo")
            if cpuinfo_path.exists():
                with open(cpuinfo_path) as f:
                    cpuinfo_content = f.read()

                    # Detect Raspberry Pi model
                    model_match = re.search(r'^Model\s*:\s*(.+)$', cpuinfo_content, re.MULTILINE)
                    if model_match:
                        rpi_model = model_match.group(1).strip()

                    # Get CPU model name
                    model_name_match = re.search(r'^model name\s*:\s*(.+)$', cpuinfo_content, re.MULTILINE)
                    if model_name_match:
                        cpu_model = model_name_match.group(1).strip()
                    elif rpi_model:
                        # For Raspberry Pi, use the Model line as CPU info
                        cpu_model = rpi_model
        except Exception:
            cpu_model = platform.processor() or "Unknown"

        if rpi_model:
            info_lines.append(f"🍓 **Raspberry Pi Model**: {rpi_model}")

        info_lines.append(f"⚙️  **CPU**: {cpu_model}")
        info_lines.append(f"🔢 **CPU Cores**: {cpu_cores}")

        # Containerization detection
        container_type = None

        # Check for Docker via /.dockerenv
        if Path("/.dockerenv").exists():
            container_type = "Docker"
        else:
            # Check cgroups for other container types
            try:
                cgroup_path = Path("/proc/1/cgroup")
                if cgroup_path.exists():
                    with open(cgroup_path) as f:
                        cgroup_content = f.read()
                        if 'docker' in cgroup_content:
                            container_type = "Docker"
                        elif 'lxc' in cgroup_content:
                            container_type = "LXC"
                        elif 'containerd' in cgroup_content:
                            container_type = "Containerd"
                        elif 'kubepods' in cgroup_content:
                            container_type = "Kubernetes"
            except Exception:
                pass

        if container_type:
            info_lines.append(f"📦 **Container**: {container_type}")
        else:
            info_lines.append(f"📦 **Container**: None detected")

        # Init system (PID 1)
        init_system = "Unknown"
        try:
            init_path = Path("/proc/1/comm")
            if init_path.exists():
                with open(init_path) as f:
                    init_system = f.read().strip()
        except Exception:
            pass

        info_lines.append(f"🚀 **Init System**: {init_system}")

        # Virtualization detection (systemd-detect-virt)
        virt_type = None
        try:
            import subprocess
            result = subprocess.run(
                ['systemd-detect-virt'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                virt_output = result.stdout.strip()
                if virt_output and virt_output != "none":
                    virt_type = virt_output
        except Exception:
            pass

        if virt_type:
            info_lines.append(f"💿 **Virtualization**: {virt_type}")
        else:
            info_lines.append(f"💿 **Virtualization**: None detected")

        # Uptime
        try:
            uptime_path = Path("/proc/uptime")
            if uptime_path.exists():
                with open(uptime_path) as f:
                    uptime_seconds = float(f.read().split()[0])
                    days = int(uptime_seconds // 86400)
                    hours = int((uptime_seconds % 86400) // 3600)
                    minutes = int((uptime_seconds % 3600) // 60)

                    uptime_parts = []
                    if days > 0:
                        uptime_parts.append(f"{days}d")
                    if hours > 0:
                        uptime_parts.append(f"{hours}h")
                    uptime_parts.append(f"{minutes}m")

                    uptime_str = " ".join(uptime_parts)
                    info_lines.append(f"⏱️  **Uptime**: {uptime_str}")
        except Exception:
            pass

        # Memory information
        try:
            meminfo_path = Path("/proc/meminfo")
            if meminfo_path.exists():
                with open(meminfo_path) as f:
                    meminfo_content = f.read()

                    # Extract MemTotal
                    mem_total_match = re.search(r'^MemTotal:\s+(\d+)\s+kB', meminfo_content, re.MULTILINE)
                    if mem_total_match:
                        mem_total_kb = int(mem_total_match.group(1))
                        mem_total_gb = mem_total_kb / (1024 * 1024)
                        info_lines.append(f"💾 **Memory Total**: {mem_total_gb:.2f} GB")

                    # Extract MemAvailable
                    mem_avail_match = re.search(r'^MemAvailable:\s+(\d+)\s+kB', meminfo_content, re.MULTILINE)
                    if mem_avail_match:
                        mem_avail_kb = int(mem_avail_match.group(1))
                        mem_avail_gb = mem_avail_kb / (1024 * 1024)
                        info_lines.append(f"💾 **Memory Available**: {mem_avail_gb:.2f} GB")
        except Exception:
            pass

        return "\n".join(info_lines)

    except Exception as e:
        return f"❌ Error gathering platform information: {str(e)}"
