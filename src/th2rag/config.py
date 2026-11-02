import os
from urllib.parse import quote_plus

from dotenv import load_dotenv
from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings

dotenv_path = os.getenv("WORK_DIR", default=os.getcwd()) + "/.env"
load_dotenv(dotenv_path)



class Settings(BaseSettings):

    # fast api
    root_path: str = Field(
        default="http://localhost:8000",
        description="Backendenpoint"
    )
    # database variables
    db_host: str
    db_port: str
    db_name: str
    db_user: str
    db_password: str
    db_schema: str
    db_schema_demo: str = "th2_llm" 
    bypass_auth: bool = False

    # security variables
    algorithm: str
    access_token_expire_minutes: int
    encrypt_key: str

    # sqlalchemy config
    echo_sql: bool = False

    # Mistral  Config
    mistral_api_key: str
    mistral_api_url: str = Field(
        default="https://api.mistral.ai/v1",
        description="Mistral API base URL (or OVH endpoint)"
    )
    mistral_model_name: str = Field(
        default="mistral-nemo-instruct-2407",
        description="Mistral model to use for generation"
    )
    mistral_max_tokens: int = Field(
        default=512,
        description="Maximum tokens for Mistral generation"
    )
    mistral_temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description="Temperature for generation (0.0-2.0)"
    )
    mistral_top_p: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Top-p sampling parameter"
    )
    mistral_presence_penalty: float = Field(
        default=0.0,
        ge=-2.0,
        le=2.0,
        description="Presence penalty (-2.0 to 2.0)"
    )
    mistral_stream: bool = Field(
        default=True,
        description="Whether to stream responses"
    )
    #Lightllm config
    litellm_provider: str = Field(
        default="mistral",
        description="LLM provider: 'mistral', 'anthropic', etc."
    )
    litellm_model: str = Field(
        default="Mistral-Small-3.2-24B-Instruct-2506",
        description="Model name (without provider prefix)"
    )
    litellm_api_key: str | None = Field(
        default=None,
        description="API key for the LiteLLM provider"
    )


    anthropic_api_key: str | None = Field(
    default=None,
    description="Anthropic API key"
    )
    anthropic_model: str = Field(
        default="claude-3-haiku-20240307",
        description="Anthropic model name"
    )

    # Embedding Model Configuration
    embedding_model_name: str = Field(
        default="sentence-transformers/gtr-t5-large",
        description="Sentence transformer model for embeddings"
    )
    embedding_cache_folder: str = Field(
        default="./models/embeddings",
        description="Local cache folder for embedding models"
    )

    # S3 Storage Configuration
    s3_region: str
    s3_access_key_secret: str
    s3_access_key: str
    s3_endpoint: str
    s3_bucket_name: str
    storage_mode: str = "local"

    # Application Configuration
    working_mode: str = Field(default="development")
    log_level: str = Field(default="INFO")

    # RAG Configuration
    rag_top_k: int = Field(
        default=5,
        description="Default number of chunks to retrieve"
    )
    lancedb_table_name: str = Field(
        default="docling",
        description="LanceDB table name"
    )
    # Mage AI Configuration
    mage_base_url: str = Field(
        default="http://localhost:6789",
        alias="BASE_URL",
        description="Mage AI base URL"
    )
    mage_api_key: str | None = Field(
        default=None,
        alias="API_KEY",
        description="Mage AI API key for authentication"
    )
    mage_oauth_token: str | None = Field(
        default=None,
        alias="OAUTH_TOKEN",
        description="Mage AI OAuth token for authentication"
    )
    mage_pipeline_uuid: str = Field(
        default="process_pdf",
        description="Mage AI pipeline UUID to trigger"
    )
    mage_trigger_name: str = Field(
        default="multi_runner_trigger",
        description="Mage AI trigger name"
    )

    model_config = ConfigDict(extra="ignore")

    # PDF Processing Configuration
    pdf_processing_mode: str = Field(
        default="async",
        description="PDF processing mode: 'async' (background) or 'sync' (wait for completion)"
    )
    pdf_processing_timeout: int = Field(
        default=300,
        gt=0,
        description="Maximum time (seconds) to wait for synchronous PDF processing"
    )
    pdf_max_file_size_mb: int = Field(
        default=30,
        gt=0,
        description="Maximum allowed PDF file size in megabytes"
    )
    pdf_auto_async_threshold_mb: int = Field(
        default=5,
        gt=0,
        description="Auto-switch to async processing if PDF exceeds this size (MB)"
    )
    pdf_enable_auto_mode: bool = Field(
        default=True,
        description="Automatically choose sync/async based on file size"
    )

    # Knowledge Timeout Monitor Configuration
    knowledge_pending_timeout_minutes: int = Field(
        default=60,
        gt=0,
        description="Minutes before a PENDING knowledge document is auto-failed"
    )
    knowledge_timeout_check_interval_seconds: int = Field(
        default=60,
        gt=0,
        description="How often to check for stale PENDING documents"
    )
    knowledge_timeout_monitor_enabled: bool = Field(
        default=True,
        description="Enable/disable the automatic timeout monitor"
    )
    # Webhook Configuration (for notifying th2agent when indexation completes)
    webhook_secret: str = Field(
        default="th2-webhook-default-secret",
        description="HMAC-SHA256 secret used to sign webhook payloads (must match th2agent RAG_WEBHOOK_SECRET)"
    )
    webhook_timeout_seconds: int = Field(
        default=10,
        gt=0,
        description="HTTP timeout for webhook delivery attempts"
    )
    webhook_max_retries: int = Field(
        default=3,
        gt=0,
        description="Maximum number of webhook delivery attempts"
    )

    # PDF heading promotion: numbered statements ("A.1 ...") of two or more
    # lines, set at body size in a face other than the body face, become
    # section headers so the chunker carries them in the heading path of the
    # sub-statements ("A.1.1 ..."). Off by default: it rewrites the document
    # tree, and only reports laid out that way (IPCC summaries) need it.
    pdf_promote_styled_statements: bool = Field(
        default=False,
        description="Promote numbered statements set in a distinct face to PDF section headers",
    )

    #  IMAGE HANDLING SWITCH
    # "extract" (Default).
    # "describe" using a vlm
    handle_img_mode: str = "extract"

    # Webhook Configuration
    webhook_secret: str = Field(
        default="th2-webhook-default-secret",
        description="HMAC-SHA256 secret used to sign webhook payloads (must match th2agent RAG_WEBHOOK_SECRET)"
    )
    webhook_timeout_seconds: int = Field(
        default=30,
        gt=0,
        description="HTTP timeout in seconds for webhook delivery"
    )
    webhook_max_retries: int = Field(
        default=3,
        ge=1,
        description="Maximum number of delivery attempts for a webhook"
    )


    @property
    def database_url(self) -> str:
        encoded_password = quote_plus(self.db_password)
        return f"postgresql+asyncpg://{self.db_user}:{encoded_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def alembic_url(self) -> str:
        encoded_password = quote_plus(self.db_password)
        return f"postgresql+psycopg2://{self.db_user}:{encoded_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def lancedb_url(self) -> str:
        """LanceDB storage path based on working mode"""
        if self.working_mode == "dev":
            return "tempdata/lancedb"
        else:
            return "data/lancedb"

    def get_pdf_processing_mode(self, file_size_mb: float = None) -> str:
        """
        Determine the appropriate PDF processing mode.
        """
        if not self.pdf_enable_auto_mode:
            return self.pdf_processing_mode

        if file_size_mb is None:
            return self.pdf_processing_mode

        # Auto-determine based on file size
        if file_size_mb > self.pdf_auto_async_threshold_mb:
            return "async"

        return "sync"
settings = Settings()
