from __future__ import annotations
from typing import Optional
import os
import sys
import platform
import socket
import json
from . import command


@command(
    name="hostinfo",
    description="Report basic host platform details using only safe Python standard library calls"
)
async def hostinfo_handler(matrix_context: Optional[dict] = None) -> Optional[str]:
    """
    Report basic host platform details using only safe Python standard library calls.

    Returns a JSON object with system information including:
    - os: Operating system details (name, system, version)
    - kernel: Kernel release information
    - arch: Machine architecture
    - processor: Processor information
    - python: Python version and implementation
    - hostname: System hostname

    All exceptions are handled gracefully by setting fields to null.

    **No external file modifications required for this command.**

    Returns:
        JSON-formatted string with host information
    """
    def safe_call(func, *args):
        """Safely call a function and return None on exception."""
        try:
            return func(*args)
        except Exception:
            return None

    # Gather host information with exception handling
    host_info = {
        "os": {
            "name": safe_call(lambda: os.name),
            "system": safe_call(platform.system),
            "version": safe_call(platform.version)
        },
        "kernel": {
            "release": safe_call(platform.release)
        },
        "arch": safe_call(platform.machine),
        "processor": safe_call(platform.processor),
        "python": {
            "version": safe_call(lambda: sys.version),
            "implementation": safe_call(platform.python_implementation)
        },
        "hostname": safe_call(socket.gethostname)
    }

    # Format as compact but readable JSON
    try:
        json_output = json.dumps(host_info, indent=2)
        return f"```json\n{json_output}\n```"
    except Exception as e:
        return f"Error formatting host info: {str(e)}"
