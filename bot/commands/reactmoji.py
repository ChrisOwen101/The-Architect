from __future__ import annotations
from typing import Optional
from . import command
import re

@command(
    name="reactmoji",
    description="reply with the canonical opposite energy of the emoji the user just sent (e.g. 😇→😈, 🔥→💧, 💤→⚡, etc.)",
    pattern=r"^!reactmoji\s*(.*)$"
)
async def reactmoji_handler(body: str) -> Optional[str]:
    """
    Reply with the canonical opposite energy of the provided emoji.
    
    Examples:
        !reactmoji 😇 -> 😈
        !reactmoji 🔥 -> 💧
        !reactmoji 💤 -> ⚡
    
    Args:
        body: The full message text containing the command and emoji
        
    Returns:
        The opposite emoji, or an error message if no match found
    """
    match = re.match(r"^!reactmoji\s*(.*)$", body)
    if not match:
        return None
    
    emoji_input = match.group(1).strip()
    
    if not emoji_input:
        return "Please provide an emoji! Example: !reactmoji 😇"
    
    opposite_map = {
        "😇": "😈",
        "😈": "😇",
        "🔥": "💧",
        "💧": "🔥",
        "💤": "⚡",
        "⚡": "💤",
        "☀️": "🌙",
        "🌙": "☀️",
        "🌞": "🌚",
        "🌚": "🌞",
        "❄️": "🔥",
        "🧊": "🔥",
        "🌊": "🔥",
        "💦": "🔥",
        "👼": "👿",
        "👿": "👼",
        "😊": "😢",
        "😢": "😊",
        "😂": "😭",
        "😭": "😂",
        "😍": "🤢",
        "🤢": "😍",
        "😴": "😃",
        "😃": "😴",
        "🥶": "🥵",
        "🥵": "🥶",
        "❤️": "💔",
        "💔": "❤️",
        "💚": "🖤",
        "🖤": "💚",
        "🌱": "🥀",
        "🥀": "🌱",
        "🌸": "🍂",
        "🍂": "🌸",
        "🌈": "⛈️",
        "⛈️": "🌈",
        "🌤️": "⛈️",
        "☁️": "☀️",
        "🌟": "🌑",
        "🌑": "🌟",
        "⭐": "🕳️",
        "✨": "💀",
        "💀": "✨",
        "👆": "👇",
        "👇": "👆",
        "👍": "👎",
        "👎": "👍",
        "🔊": "🔇",
        "🔇": "🔊",
        "📈": "📉",
        "📉": "📈",
        "🏃": "🚶",
        "🚶": "🏃",
        "🌅": "🌇",
        "🌇": "🌅",
        "🌄": "🌆",
        "🌆": "🌄",
        "🎉": "😐",
        "😐": "🎉",
        "🎊": "😑",
        "😑": "🎊",
        "💪": "🦴",
        "🦴": "💪",
        "🧠": "💭",
        "💭": "🧠",
        "🌵": "🌴",
        "🌴": "🌵",
        "🏔️": "🏖️",
        "🏖️": "🏔️",
        "🌋": "🧊",
        "🍕": "🥗",
        "🥗": "🍕",
        "🍰": "🥦",
        "🥦": "🍰",
        "🍺": "☕",
        "☕": "🍺",
        "🌮": "🥙",
        "🥙": "🌮",
        "🎮": "📚",
        "📚": "🎮",
        "🎸": "🎻",
        "🎻": "🎸",
        "🚀": "⚓",
        "⚓": "🚀",
        "✈️": "🚢",
        "🚢": "✈️",
    }
    
    if emoji_input in opposite_map:
        return opposite_map[emoji_input]
    else:
        return f"I don't know the opposite of {emoji_input} yet! 🤷"