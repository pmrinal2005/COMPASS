"""Central configuration. Every external service is optional: when a key is
missing COMPASS degrades gracefully to a zero-cost local fallback so the
whole pipeline still runs (Demo Mode)."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Core search layer -------------------------------------------------
    serpapi_key: str = ""
    serpapi_base: str = "https://serpapi.com"
    serp_concurrency: int = 4            # semaphore: max in-flight SerpApi calls per session
    serp_poll_interval: float = 1.2      # seconds between async archive polls
    serp_poll_timeout: float = 45.0      # give up on a queued async search after this
    serp_max_retries: int = 3            # exponential backoff retries on 429 (throughput) / 5xx
    serp_sync_timeout: float = 70.0      # HTTP timeout for a blocking (non-async) search
    serp_async: bool = True              # use async=true + Search Archive for non-fresh searches
    serpapi_zero_trace: bool = False     # Enterprise only: ZeroTrace (no search files stored => forces sync mode)
    account_cache_seconds: int = 60      # Account API is free, but still cache it
    cache_ttl_seconds: int = 900         # dedupe window (15 min)

    # --- Demo / safety -----------------------------------------------------
    demo_mode: bool | None = None        # None => auto (on when no SERPAPI_KEY)
    session_credit_budget: int = 30      # visible credit meter per session
    expensive_fanout_threshold: int = 8  # fan-outs above this need one-click confirm
    max_replans: int = 2                 # hard cap on re-planning loops
    confidence_threshold: float = 0.62
    corroboration_min_sources: int = 2

    # --- LLM / embeddings (free tiers) -------------------------------------
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_embed_model: str = "gemini-embedding-001"
    embed_dim: int = 768

    # --- Supabase (Postgres + pgvector + auth + storage) -------------------
    supabase_url: str = ""
    supabase_service_key: str = ""

    # --- Upstash Redis (REST) ----------------------------------------------
    upstash_redis_rest_url: str = ""
    upstash_redis_rest_token: str = ""

    # --- Langfuse Cloud ----------------------------------------------------
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # --- Notifications -----------------------------------------------------
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    resend_api_key: str = ""
    resend_from: str = "COMPASS <onboarding@resend.dev>"
    notify_email_to: str = ""

    # --- Actor -------------------------------------------------------------
    playwright_enabled: bool = True

    # --- HTTP --------------------------------------------------------------
    frontend_origins: str = "*"
    cron_secret: str = "change-me"

    @property
    def is_demo(self) -> bool:
        if self.demo_mode is not None:
            return self.demo_mode
        return not bool(self.serpapi_key)

    @property
    def has_supabase(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_key)

    @property
    def has_redis(self) -> bool:
        return bool(self.upstash_redis_rest_url and self.upstash_redis_rest_token)

    @property
    def has_langfuse(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)

    def integrations(self) -> dict:
        return {
            "serpapi": "live" if not self.is_demo else "demo",
            "serpapi_async": bool(self.serp_async and not self.serpapi_zero_trace),
            "groq": bool(self.groq_api_key),
            "gemini": bool(self.gemini_api_key),
            "supabase_pgvector": self.has_supabase,
            "upstash_redis": self.has_redis,
            "langfuse": self.has_langfuse,
            "telegram": bool(self.telegram_bot_token and self.telegram_chat_id),
            "resend": bool(self.resend_api_key),
            "playwright": self.playwright_enabled,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
