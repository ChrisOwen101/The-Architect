"""Tests for code validator."""
from bot.code_validator import validate_command_code, validate_test_code


def test_validate_valid_command():
    """Test validation of valid command code."""
    code = '''
from __future__ import annotations
from typing import Optional
from bot.commands import command

@command(
    name="test",
    description="Test command",
    pattern=r"^!test$"
)
async def test_handler(body: str) -> Optional[str]:
    return "test"
'''
    is_valid, error = validate_command_code(code, "test")
    if not is_valid:
        print(f"Validation error: {error}")
    assert is_valid
    assert error is None


def test_validate_syntax_error():
    """Test validation catches syntax errors."""
    code = "this is not valid python code {"
    is_valid, error = validate_command_code(code, "test")
    assert not is_valid
    assert "Syntax error" in error


def test_validate_missing_handler():
    """Test validation catches missing handler function."""
    code = '''
from bot.commands import command

async def wrong_name(body: str):
    return "test"
'''
    is_valid, error = validate_command_code(code, "test")
    assert not is_valid
    assert "Handler function" in error


def test_validate_test_code():
    """Test validation of test code."""
    code = '''
import pytest

@pytest.mark.asyncio
async def test_example():
    assert True
'''
    is_valid, error = validate_test_code(code)
    assert is_valid
    assert error is None
