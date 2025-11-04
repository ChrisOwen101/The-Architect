"""Tests for the eightball command."""

import pytest
from bot.commands.eightball import (
    eightball_handler,
    ALL_ANSWERS,
    AFFIRMATIVE_ANSWERS,
    NON_COMMITTAL_ANSWERS,
    NEGATIVE_ANSWERS,
)


@pytest.mark.asyncio
async def test_eightball_with_question():
    """Test that eightball returns a valid answer when given a question."""
    result = await eightball_handler("!eightball Will it rain today?")

    assert result is not None
    assert result.startswith("🎱 ")

    # Extract the answer portion (remove the emoji and space)
    answer = result[2:].strip()

    # Verify it's one of the valid Magic 8-Ball answers
    assert answer in ALL_ANSWERS


@pytest.mark.asyncio
async def test_eightball_empty_question():
    """Test that eightball prompts user when no question is provided."""
    result = await eightball_handler("!eightball")

    assert result is not None
    assert "Ask me a question" in result
    assert "🎱" in result


@pytest.mark.asyncio
async def test_eightball_whitespace_only():
    """Test that eightball handles whitespace-only input gracefully."""
    result = await eightball_handler("!eightball   ")

    assert result is not None
    assert "Ask me a question" in result


@pytest.mark.asyncio
async def test_eightball_various_questions():
    """Test that eightball works with different question formats."""
    questions = [
        "!eightball Should I do this?",
        "!eightball Is it going to work?",
        "!eightball Will I succeed?",
        "!eightball Can I trust them?",
    ]

    for question in questions:
        result = await eightball_handler(question)
        assert result is not None
        assert result.startswith("🎱 ")

        # Extract answer and verify it's valid
        answer = result[2:].strip()
        assert answer in ALL_ANSWERS


@pytest.mark.asyncio
async def test_eightball_randomness():
    """Test that eightball returns different answers (probabilistic test)."""
    # Run multiple times to check for randomness
    # With 20 answers available, getting the same answer 10 times is very unlikely
    results = []
    for _ in range(10):
        result = await eightball_handler("!eightball Test question?")
        results.append(result)

    # At least 2 different answers should appear in 10 tries
    unique_results = set(results)
    assert len(unique_results) >= 2, "Expected some randomness in answers"


@pytest.mark.asyncio
async def test_eightball_all_answer_categories_exist():
    """Test that all answer categories are properly defined."""
    # Verify we have answers in each category
    assert len(AFFIRMATIVE_ANSWERS) > 0
    assert len(NON_COMMITTAL_ANSWERS) > 0
    assert len(NEGATIVE_ANSWERS) > 0

    # Verify ALL_ANSWERS contains all categories
    assert len(ALL_ANSWERS) == (
        len(AFFIRMATIVE_ANSWERS) +
        len(NON_COMMITTAL_ANSWERS) +
        len(NEGATIVE_ANSWERS)
    )


@pytest.mark.asyncio
async def test_eightball_long_question():
    """Test that eightball handles long questions."""
    long_question = "!eightball " + "Will this work? " * 50
    result = await eightball_handler(long_question)

    assert result is not None
    assert result.startswith("🎱 ")

    # Should still return a valid answer
    answer = result[2:].strip()
    assert answer in ALL_ANSWERS


@pytest.mark.asyncio
async def test_eightball_special_characters():
    """Test that eightball handles questions with special characters."""
    result = await eightball_handler("!eightball Will I find $1,000,000?!?")

    assert result is not None
    assert result.startswith("🎱 ")

    answer = result[2:].strip()
    assert answer in ALL_ANSWERS
