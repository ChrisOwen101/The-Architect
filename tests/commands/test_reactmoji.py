import pytest
from typing import Optional


@pytest.mark.asyncio
async def test_reactmoji_angel_to_devil():
    from reactmoji import reactmoji_handler
    result = await reactmoji_handler("!reactmoji 😇")
    assert result == "😈"


@pytest.mark.asyncio
async def test_reactmoji_devil_to_angel():
    from reactmoji import reactmoji_handler
    result = await reactmoji_handler("!reactmoji 😈")
    assert result == "😇"


@pytest.mark.asyncio
async def test_reactmoji_fire_to_water():
    from reactmoji import reactmoji_handler
    result = await reactmoji_handler("!reactmoji 🔥")
    assert result == "💧"


@pytest.mark.asyncio
async def test_reactmoji_water_to_fire():
    from reactmoji import reactmoji_handler
    result = await reactmoji_handler("!reactmoji 💧")
    assert result == "🔥"


@pytest.mark.asyncio
async def test_reactmoji_sleeping_to_lightning():
    from reactmoji import reactmoji_handler
    result = await reactmoji_handler("!reactmoji 💤")
    assert result == "⚡"


@pytest.mark.asyncio
async def test_reactmoji_lightning_to_sleeping():
    from reactmoji import reactmoji_handler
    result = await reactmoji_handler("!reactmoji ⚡")
    assert result == "💤"


@pytest.mark.asyncio
async def test_reactmoji_sun_to_moon():
    from reactmoji import reactmoji_handler
    result = await reactmoji_handler("!reactmoji ☀️")
    assert result == "🌙"


@pytest.mark.asyncio
async def test_reactmoji_thumbs_up_to_thumbs_down():
    from reactmoji import reactmoji_handler
    result = await reactmoji_handler("!reactmoji 👍")
    assert result == "👎"


@pytest.mark.asyncio
async def test_reactmoji_rocket_to_anchor():
    from reactmoji import reactmoji_handler
    result = await reactmoji_handler("!reactmoji 🚀")
    assert result == "⚓"


@pytest.mark.asyncio
async def test_reactmoji_empty_input():
    from reactmoji import reactmoji_handler
    result = await reactmoji_handler("!reactmoji")
    assert result == "Please provide an emoji! Example: !reactmoji 😇"


@pytest.mark.asyncio
async def test_reactmoji_whitespace_only():
    from reactmoji import reactmoji_handler
    result = await reactmoji_handler("!reactmoji   ")
    assert result == "Please provide an emoji! Example: !reactmoji 😇"


@pytest.mark.asyncio
async def test_reactmoji_unknown_emoji():
    from reactmoji import reactmoji_handler
    result = await reactmoji_handler("!reactmoji 🦄")
    assert result == "I don't know the opposite of 🦄 yet! 🤷"


@pytest.mark.asyncio
async def test_reactmoji_text_instead_of_emoji():
    from reactmoji import reactmoji_handler
    result = await reactmoji_handler("!reactmoji hello")
    assert result == "I don't know the opposite of hello yet! 🤷"


@pytest.mark.asyncio
async def test_reactmoji_invalid_command_format():
    from reactmoji import reactmoji_handler
    result = await reactmoji_handler("reactmoji 😇")
    assert result is None


@pytest.mark.asyncio
async def test_reactmoji_with_extra_whitespace():
    from reactmoji import reactmoji_handler
    result = await reactmoji_handler("!reactmoji    😇   ")
    assert result == "😈"


@pytest.mark.asyncio
async def test_reactmoji_heart_to_broken_heart():
    from reactmoji import reactmoji_handler
    result = await reactmoji_handler("!reactmoji ❤️")
    assert result == "💔"


@pytest.mark.asyncio
async def test_reactmoji_chart_up_to_chart_down():
    from reactmoji import reactmoji_handler
    result = await reactmoji_handler("!reactmoji 📈")
    assert result == "📉"


@pytest.mark.asyncio
async def test_reactmoji_pizza_to_salad():
    from reactmoji import reactmoji_handler
    result = await reactmoji_handler("!reactmoji 🍕")
    assert result == "🥗"


@pytest.mark.asyncio
async def test_reactmoji_volcano_to_ice():
    from reactmoji import reactmoji_handler
    result = await reactmoji_handler("!reactmoji 🌋")
    assert result == "🧊"


@pytest.mark.asyncio
async def test_reactmoji_rainbow_to_storm():
    from reactmoji import reactmoji_handler
    result = await reactmoji_handler("!reactmoji 🌈")
    assert result == "⛈️"


@pytest.mark.asyncio
async def test_reactmoji_party_to_neutral():
    from reactmoji import reactmoji_handler
    result = await reactmoji_handler("!reactmoji 🎉")
    assert result == "😐"


@pytest.mark.asyncio
async def test_reactmoji_multiple_emojis():
    from reactmoji import reactmoji_handler
    result = await reactmoji_handler("!reactmoji 😇😈")
    assert result == "I don't know the opposite of 😇😈 yet! 🤷"


@pytest.mark.asyncio
async def test_reactmoji_emoji_with_text():
    from reactmoji import reactmoji_handler
    result = await reactmoji_handler("!reactmoji 😇 test")
    assert result == "I don't know the opposite of 😇 test yet! 🤷"


@pytest.mark.asyncio
async def test_reactmoji_cold_to_hot():
    from reactmoji import reactmoji_handler
    result = await reactmoji_handler("!reactmoji 🥶")
    assert result == "🥵"


@pytest.mark.asyncio
async def test_reactmoji_hot_to_cold():
    from reactmoji import reactmoji_handler
    result = await reactmoji_handler("!reactmoji 🥵")
    assert result == "🥶"