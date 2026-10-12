from dotenv import find_dotenv, load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


load_dotenv(dotenv_path=find_dotenv(usecwd=True))


class LoggingSettings(BaseSettings):
    level: str = "INFO"


class RedisRateLimiterSettings(BaseSettings):
    enabled: bool = True
    host: str = "localhost"
    port: str = "6379"
    db: int = 0
    password: str | None = None
    username: str | None = None
    ssl: bool = False


class OptimizationLimitsSettings(BaseSettings):
    max_concurrent_runs: int = 2
    max_steps: int = 500
    rate_limit_requests: int = 20
    rate_limit_window_seconds: int = 60
    max_kmax: int = 100
    max_run_seconds: int = 300  # wall-clock timeout per optimization run
    max_trajectory_rows: int = 500  # rows in uploaded trajectory CSV
    max_trajectory_cols: int = 200  # columns (time steps) per trajectory


class AppSettings(BaseSettings):
    """main application settings with hierarchical configuration."""

    host: str = "0.0.0.0"
    port: int = 8000

    docs_url: str = "/docs"
    static_dir: str | None = None
    allowed_hosts: list[str] = ["*"]

    db_path: str = "degas_sessions.db"
    session_ttl_days: int = 1
    session_cleanup_interval_hours: int = 6

    logging: LoggingSettings = LoggingSettings()
    optimization_rate_limiter: RedisRateLimiterSettings = RedisRateLimiterSettings()
    optimization_limits: OptimizationLimitsSettings = OptimizationLimitsSettings()

    # prefix for environment variables and enable nested delimiter
    model_config = SettingsConfigDict(
        env_prefix="degas_api_",
        env_nested_delimiter="__",
        nested_model_default_partial_update=True,
    )


app_settings = AppSettings()
