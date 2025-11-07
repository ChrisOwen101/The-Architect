"""Tests for platform detection command."""
from __future__ import annotations
import pytest
from bot.commands.platform import platform_handler


@pytest.mark.asyncio
async def test_platform_success():
    """Test that platform returns comprehensive system information."""
    result = await platform_handler()

    assert result is not None
    assert isinstance(result, str)

    # Check for key sections that should always be present
    assert "OS" in result
    assert "Kernel" in result
    assert "Architecture" in result
    assert "Hostname" in result
    assert "CPU" in result
    assert "CPU Cores" in result
    assert "Container" in result
    assert "Init System" in result
    assert "Virtualization" in result


@pytest.mark.asyncio
async def test_platform_contains_valid_data():
    """Test that platform returns valid non-empty data."""
    result = await platform_handler()

    assert result is not None
    assert len(result) > 100  # Should have substantial content

    # Should not contain "Unknown" for basic fields
    lines = result.split('\n')
    assert len(lines) >= 8  # At minimum should have 8+ info lines


@pytest.mark.asyncio
async def test_platform_with_matrix_context():
    """Test that platform works with matrix_context parameter."""
    matrix_context = {
        "room_id": "!test:example.com",
        "event_id": "$test123",
        "sender": "@user:example.com"
    }

    result = await platform_handler(matrix_context=matrix_context)

    assert result is not None
    assert isinstance(result, str)
    assert "OS" in result
    assert "Kernel" in result


@pytest.mark.asyncio
async def test_platform_format():
    """Test that platform output is properly formatted with emojis."""
    result = await platform_handler()

    assert result is not None

    # Check for emoji markers that indicate proper formatting
    assert "🖥️" in result or "**OS**" in result
    assert "🔧" in result or "**Kernel**" in result
    assert "🏗️" in result or "**Architecture**" in result
    assert "🌐" in result or "**Hostname**" in result
    assert "⚙️" in result or "**CPU**" in result
    assert "🔢" in result or "**CPU Cores**" in result


@pytest.mark.asyncio
async def test_platform_no_exception():
    """Test that platform doesn't raise exceptions even if some data is unavailable."""
    # This should handle missing files gracefully
    result = await platform_handler()

    assert result is not None
    assert isinstance(result, str)
    # Should not start with error message in normal circumstances
    # (unless there's a catastrophic failure, but that's unlikely)


@pytest.mark.asyncio
async def test_platform_cpu_cores_positive():
    """Test that CPU cores is reported as a positive number."""
    result = await platform_handler()

    assert result is not None

    # Find the CPU Cores line
    for line in result.split('\n'):
        if "CPU Cores" in line:
            # Extract the number
            parts = line.split(':')
            if len(parts) >= 2:
                cores_str = parts[-1].strip()
                # Should be a positive integer
                cores = int(cores_str)
                assert cores > 0
                break


@pytest.mark.asyncio
async def test_platform_memory_format():
    """Test that memory information (if present) is properly formatted."""
    result = await platform_handler()

    assert result is not None

    # Check if memory info is present and properly formatted
    if "Memory Total" in result:
        for line in result.split('\n'):
            if "Memory Total" in line:
                assert "GB" in line
                # Extract the number part
                parts = line.split(':')
                if len(parts) >= 2:
                    mem_str = parts[-1].strip().replace("GB", "").strip()
                    mem_val = float(mem_str)
                    assert mem_val > 0


@pytest.mark.asyncio
async def test_platform_uptime_format():
    """Test that uptime information (if present) is properly formatted."""
    result = await platform_handler()

    assert result is not None

    # Check if uptime is present and properly formatted
    if "Uptime" in result:
        for line in result.split('\n'):
            if "Uptime" in line:
                # Should contain time units (d, h, or m)
                assert any(unit in line for unit in ['d', 'h', 'm'])
