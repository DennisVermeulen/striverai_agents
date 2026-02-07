from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM
    anthropic_api_key: str = ""
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-5-20250929"
    llm_max_tokens: int = 4096

    # Ollama
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "llama3.2-vision"

    # Browser
    browser_width: int = 1920
    browser_height: int = 1080
    screenshot_max_dimension: int = 1568

    # Agent
    agent_max_steps: int = 50
    agent_step_delay: float = 0.5

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Display
    display_num: int = 99

    # Paths
    data_dir: Path = Path("/app/data")
    sessions_dir: Path = Path("/app/data/sessions")
    screenshots_dir: Path = Path("/app/data/screenshots")
    logs_dir: Path = Path("/app/data/logs")
    workflows_dir: Path = Path("/app/data/workflows")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
