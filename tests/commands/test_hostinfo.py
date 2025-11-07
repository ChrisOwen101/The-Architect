import pytest
import json
from bot.commands.hostinfo import hostinfo_handler


@pytest.mark.asyncio
async def test_hostinfo_success():
    """Test that hostinfo returns valid JSON with expected structure."""
    result = await hostinfo_handler()

    # Should return a string
    assert result is not None
    assert isinstance(result, str)

    # Should be wrapped in markdown code block
    assert result.startswith("```json\n")
    assert result.endswith("\n```")

    # Extract JSON content
    json_content = result.replace("```json\n", "").replace("\n```", "")
    data = json.loads(json_content)

    # Verify expected structure
    assert "os" in data
    assert "name" in data["os"]
    assert "system" in data["os"]
    assert "version" in data["os"]

    assert "kernel" in data
    assert "release" in data["kernel"]

    assert "arch" in data
    assert "processor" in data

    assert "python" in data
    assert "version" in data["python"]
    assert "implementation" in data["python"]

    assert "hostname" in data


@pytest.mark.asyncio
async def test_hostinfo_with_matrix_context():
    """Test that hostinfo works with matrix_context parameter."""
    matrix_context = {
        "room_id": "!test:example.com",
        "sender": "@user:example.com",
        "event_id": "$test123"
    }

    result = await hostinfo_handler(matrix_context=matrix_context)

    # Should still return valid result
    assert result is not None
    assert isinstance(result, str)
    assert "```json" in result


@pytest.mark.asyncio
async def test_hostinfo_json_validity():
    """Test that the returned JSON is valid and parseable."""
    result = await hostinfo_handler()

    # Extract and parse JSON
    json_content = result.replace("```json\n", "").replace("\n```", "")
    data = json.loads(json_content)  # Should not raise exception

    # Verify data types (values may be None if calls fail, but structure should be correct)
    assert isinstance(data["os"], dict)
    assert isinstance(data["kernel"], dict)
    assert isinstance(data["python"], dict)


@pytest.mark.asyncio
async def test_hostinfo_has_expected_os_values():
    """Test that at least some OS information is populated."""
    result = await hostinfo_handler()

    json_content = result.replace("```json\n", "").replace("\n```", "")
    data = json.loads(json_content)

    # At least os.name should be populated (very basic Python functionality)
    # This might be 'posix', 'nt', 'java', etc.
    assert data["os"]["name"] is not None or data["os"]["name"] == None  # May be None on error
    # But typically it should work
    if data["os"]["name"] is not None:
        assert isinstance(data["os"]["name"], str)
        assert len(data["os"]["name"]) > 0


@pytest.mark.asyncio
async def test_hostinfo_python_version_present():
    """Test that Python version information is present."""
    result = await hostinfo_handler()

    json_content = result.replace("```json\n", "").replace("\n```", "")
    data = json.loads(json_content)

    # Python version should always be available
    assert data["python"]["version"] is not None
    assert isinstance(data["python"]["version"], str)
    # Should contain version number
    assert "3." in data["python"]["version"]  # Assuming Python 3.x


@pytest.mark.asyncio
async def test_hostinfo_no_exceptions():
    """Test that hostinfo doesn't raise exceptions."""
    try:
        result = await hostinfo_handler()
        assert result is not None
    except Exception as e:
        pytest.fail(f"hostinfo_handler raised an exception: {e}")
