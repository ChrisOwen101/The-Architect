"""Tests for the whereami command."""
import pytest
import json
from bot.commands.whereami import (
    whereami_handler,
    _detect_os,
    _detect_kernel,
    _get_hostname,
    _detect_cpu,
    _detect_memory,
    _get_uptime,
    _detect_init,
    _detect_container,
    _detect_virtualization,
    _detect_raspberry_pi
)


@pytest.mark.asyncio
async def test_whereami_returns_valid_json():
    """Test that whereami returns valid JSON output."""
    result = await whereami_handler()

    assert result is not None
    assert "```json" in result
    assert "```" in result

    # Extract JSON from markdown code block
    json_str = result.split("```json\n")[1].split("\n```")[0]
    data = json.loads(json_str)

    # Verify all expected keys are present
    assert "os" in data
    assert "kernel" in data
    assert "arch" in data
    assert "hostname" in data
    assert "cpu" in data
    assert "memory" in data
    assert "uptime_seconds" in data
    assert "init" in data
    assert "container" in data
    assert "virtualization" in data
    assert "raspberry_pi" in data


@pytest.mark.asyncio
async def test_whereami_os_structure():
    """Test that OS detection returns expected structure."""
    result = await whereami_handler()
    json_str = result.split("```json\n")[1].split("\n```")[0]
    data = json.loads(json_str)

    os_data = data["os"]
    assert "name" in os_data
    assert "version" in os_data
    assert "id_like" in os_data


@pytest.mark.asyncio
async def test_whereami_kernel_structure():
    """Test that kernel detection returns expected structure."""
    result = await whereami_handler()
    json_str = result.split("```json\n")[1].split("\n```")[0]
    data = json.loads(json_str)

    kernel_data = data["kernel"]
    assert "release" in kernel_data
    assert "version" in kernel_data


@pytest.mark.asyncio
async def test_whereami_cpu_structure():
    """Test that CPU detection returns expected structure."""
    result = await whereami_handler()
    json_str = result.split("```json\n")[1].split("\n```")[0]
    data = json.loads(json_str)

    cpu_data = data["cpu"]
    assert "model" in cpu_data
    assert "cores" in cpu_data
    assert "flags" in cpu_data
    assert isinstance(cpu_data["flags"], list)


@pytest.mark.asyncio
async def test_whereami_memory_structure():
    """Test that memory detection returns expected structure."""
    result = await whereami_handler()
    json_str = result.split("```json\n")[1].split("\n```")[0]
    data = json.loads(json_str)

    memory_data = data["memory"]
    assert "mem_total_bytes" in memory_data
    assert "mem_available_bytes" in memory_data
    assert "swap_total_bytes" in memory_data
    assert "swap_free_bytes" in memory_data


@pytest.mark.asyncio
async def test_whereami_init_structure():
    """Test that init detection returns expected structure."""
    result = await whereami_handler()
    json_str = result.split("```json\n")[1].split("\n```")[0]
    data = json.loads(json_str)

    init_data = data["init"]
    assert "pid1_comm" in init_data
    assert "pid1_cmdline" in init_data


@pytest.mark.asyncio
async def test_whereami_container_structure():
    """Test that container detection returns expected structure."""
    result = await whereami_handler()
    json_str = result.split("```json\n")[1].split("\n```")[0]
    data = json.loads(json_str)

    container_data = data["container"]
    assert "is_container" in container_data
    assert "engine" in container_data
    assert isinstance(container_data["is_container"], bool)


@pytest.mark.asyncio
async def test_whereami_virtualization_structure():
    """Test that virtualization detection returns expected structure."""
    result = await whereami_handler()
    json_str = result.split("```json\n")[1].split("\n```")[0]
    data = json.loads(json_str)

    virt_data = data["virtualization"]
    assert "detected" in virt_data
    assert "type" in virt_data
    assert "source" in virt_data
    assert isinstance(virt_data["detected"], bool)


@pytest.mark.asyncio
async def test_whereami_raspberry_pi_structure():
    """Test that Raspberry Pi detection returns expected structure."""
    result = await whereami_handler()
    json_str = result.split("```json\n")[1].split("\n```")[0]
    data = json.loads(json_str)

    rpi_data = data["raspberry_pi"]
    assert "is_rpi" in rpi_data
    assert "model" in rpi_data
    assert isinstance(rpi_data["is_rpi"], bool)


@pytest.mark.asyncio
async def test_whereami_with_matrix_context():
    """Test that whereami handler accepts matrix_context parameter."""
    mock_context = {
        "room_id": "!test:example.com",
        "sender": "@user:example.com"
    }

    result = await whereami_handler(matrix_context=mock_context)
    assert result is not None
    assert "```json" in result


def test_detect_os_returns_dict():
    """Test that _detect_os returns a dictionary with expected keys."""
    result = _detect_os()

    assert isinstance(result, dict)
    assert "name" in result
    assert "version" in result
    assert "id_like" in result


def test_detect_kernel_returns_dict():
    """Test that _detect_kernel returns a dictionary with expected keys."""
    result = _detect_kernel()

    assert isinstance(result, dict)
    assert "release" in result
    assert "version" in result
    assert result["release"] is not None
    assert result["version"] is not None


def test_get_hostname_returns_string_or_none():
    """Test that _get_hostname returns a string or None."""
    result = _get_hostname()

    assert result is None or isinstance(result, str)


def test_detect_cpu_returns_dict():
    """Test that _detect_cpu returns a dictionary with expected keys."""
    result = _detect_cpu()

    assert isinstance(result, dict)
    assert "model" in result
    assert "cores" in result
    assert "flags" in result
    assert isinstance(result["flags"], list)


def test_detect_memory_returns_dict():
    """Test that _detect_memory returns a dictionary with expected keys."""
    result = _detect_memory()

    assert isinstance(result, dict)
    assert "mem_total_bytes" in result
    assert "mem_available_bytes" in result
    assert "swap_total_bytes" in result
    assert "swap_free_bytes" in result


def test_get_uptime_returns_float_or_none():
    """Test that _get_uptime returns a float or None."""
    result = _get_uptime()

    assert result is None or isinstance(result, float)
    if result is not None:
        assert result >= 0


def test_detect_init_returns_dict():
    """Test that _detect_init returns a dictionary with expected keys."""
    result = _detect_init()

    assert isinstance(result, dict)
    assert "pid1_comm" in result
    assert "pid1_cmdline" in result


def test_detect_container_returns_dict():
    """Test that _detect_container returns a dictionary with expected keys."""
    result = _detect_container()

    assert isinstance(result, dict)
    assert "is_container" in result
    assert "engine" in result
    assert isinstance(result["is_container"], bool)


def test_detect_virtualization_returns_dict():
    """Test that _detect_virtualization returns a dictionary with expected keys."""
    result = _detect_virtualization()

    assert isinstance(result, dict)
    assert "detected" in result
    assert "type" in result
    assert "source" in result
    assert isinstance(result["detected"], bool)


def test_detect_raspberry_pi_returns_dict():
    """Test that _detect_raspberry_pi returns a dictionary with expected keys."""
    result = _detect_raspberry_pi()

    assert isinstance(result, dict)
    assert "is_rpi" in result
    assert "model" in result
    assert isinstance(result["is_rpi"], bool)


@pytest.mark.asyncio
async def test_whereami_arch_is_not_none():
    """Test that architecture field is populated."""
    result = await whereami_handler()
    json_str = result.split("```json\n")[1].split("\n```")[0]
    data = json.loads(json_str)

    assert data["arch"] is not None
    assert isinstance(data["arch"], str)
