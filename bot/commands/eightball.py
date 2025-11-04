from __future__ import annotations
from typing import Optional
import random
from . import command


# Classic Magic 8-Ball responses categorized by type
AFFIRMATIVE_ANSWERS = [
    "It is certain.",
    "It is decidedly so.",
    "Without a doubt.",
    "Yes - definitely.",
    "You may rely on it.",
    "As I see it, yes.",
    "Most likely.",
    "Outlook good.",
    "Yes.",
    "Signs point to yes.",
]

NON_COMMITTAL_ANSWERS = [
    "Reply hazy, try again.",
    "Ask again later.",
    "Better not tell you now.",
    "Cannot predict now.",
    "Concentrate and ask again.",
]

NEGATIVE_ANSWERS = [
    "Don't count on it.",
    "My reply is no.",
    "My sources say no.",
    "Outlook not so good.",
    "Very doubtful.",
]

ALL_ANSWERS = AFFIRMATIVE_ANSWERS + NON_COMMITTAL_ANSWERS + NEGATIVE_ANSWERS


@command(
    name="eightball",
    description="return a classic magic eight ball style answer to the user's question",
    pattern=r"^!eightball\s*(.*)$"
)
async def eightball_handler(body: str) -> Optional[str]:
    """
    Magic 8-Ball command that returns a random fortune-telling style answer.

    Usage: !eightball <your question>

    Returns a random response from the classic Magic 8-Ball answer set,
    which includes affirmative, non-committal, and negative answers.

    Args:
        body: The full message text (e.g., "!eightball Will it rain today?")

    Returns:
        A random Magic 8-Ball answer string, or None if no question provided.
    """
    # Extract the question from the command
    import re
    match = re.match(r"^!eightball\s*(.*)$", body.strip())

    if not match:
        return None

    question = match.group(1).strip()

    # If no question provided, prompt the user
    if not question:
        return "🎱 Ask me a question and I'll consult the Magic 8-Ball!"

    # Select a random answer from all possible answers
    answer = random.choice(ALL_ANSWERS)

    return f"🎱 {answer}"
