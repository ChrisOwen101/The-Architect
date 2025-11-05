from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

CONFIG_FILE = "config.toml"


@dataclass
class ConcurrencyConfig:
    """Concurrency control configuration."""
    max_concurrent_conversations: int = 10
    max_conversations_per_user: int = 3
    conversation_idle_timeout: int = 300  # seconds
    conversation_max_duration: int = 600  # seconds


@dataclass
class RateLimitingConfig:
    """Rate limiting configuration."""
    openai_requests_per_second: int = 5
    openai_burst_limit: int = 10


@dataclass
class BotConfig:
    homeserver: str
    user_id: str
    device_id: str = "DEV1"
    display_name: Optional[str] = None
    log_level: str = "INFO"
    allowed_rooms: list[str] = None  # List of allowed room IDs
    enable_auto_commit: bool = True  # Auto-commit code changes to git
    concurrency: ConcurrencyConfig = None
    rate_limiting: RateLimitingConfig = None

    def __post_init__(self):
        """Initialize default values for mutable fields."""
        if self.allowed_rooms is None:
            self.allowed_rooms = []
        if self.concurrency is None:
            self.concurrency = ConcurrencyConfig()
        if self.rate_limiting is None:
            self.rate_limiting = RateLimitingConfig()

    @property
    def access_token(self) -> str:
        token = os.getenv("MATRIX_ACCESS_TOKEN")
        if not token:
            raise RuntimeError(
                "MATRIX_ACCESS_TOKEN not set in environment or .env file")
        return token

    @property
    def anthropic_api_key(self) -> str:
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set in environment or .env file")
        return key

    @property
    def openai_api_key(self) -> str:
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError(
                "OPENAI_API_KEY not set in environment or .env file")
        return key


def load_config(path: str = CONFIG_FILE) -> BotConfig:
    load_dotenv()
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Config file '{path}' not found. Create it from config.example.toml")
    with open(path, "rb") as f:
        data = tomllib.load(f)
    bot = data.get("bot", {})
    required = ["homeserver", "user_id"]
    for r in required:
        if r not in bot:
            raise ValueError(f"Missing required config key: bot.{r}")

    # Handle allowed_rooms - ensure it's a list
    if "allowed_rooms" in bot and not isinstance(bot["allowed_rooms"], list):
        bot["allowed_rooms"] = [bot["allowed_rooms"]]

    # Load concurrency config (optional, has defaults)
    concurrency_data = data.get("concurrency", {})
    concurrency = ConcurrencyConfig(**concurrency_data) if concurrency_data else ConcurrencyConfig()

    # Load rate limiting config (optional, has defaults)
    rate_limiting_data = data.get("rate_limiting", {})
    rate_limiting = RateLimitingConfig(**rate_limiting_data) if rate_limiting_data else RateLimitingConfig()

    # Add to bot config
    bot["concurrency"] = concurrency
    bot["rate_limiting"] = rate_limiting

    return BotConfig(**bot)
