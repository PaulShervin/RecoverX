from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Razorpay
    razorpay_key_id: str = "rzp_test_REPLACE_ME"
    razorpay_key_secret: str = "REPLACE_ME"
    razorpay_webhook_secret: str = "REPLACE_ME"
    ngrok_public_url: str = ""

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    # Database
    database_url: str = "sqlite:///./recoverx.db"

    # Guardrails
    max_retries_per_transaction: int = 4
    max_contacts_per_24h: int = 3
    max_auto_approved_amount: float = 50000.0
    stop_retry_probability_threshold: float = 0.15


settings = Settings()
