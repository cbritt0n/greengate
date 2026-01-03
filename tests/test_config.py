from app.core.config import Settings


def test_cohere_provider_config_included():
    cfg = Settings(COHERE_API_KEY="test-key", OPENAI_API_KEY=None, ANTHROPIC_API_KEY=None)
    providers = cfg.provider_configs()
    assert any(provider.name == "cohere" for provider in providers)


def test_azure_provider_config_included():
    cfg = Settings(
        AZURE_OPENAI_API_KEY="test",
        AZURE_OPENAI_ENDPOINT="https://azure.local",
        AZURE_OPENAI_DEPLOYMENT_MAP="gpt-4o=prod-gpt",
        OPENAI_API_KEY=None,
        ANTHROPIC_API_KEY=None,
        COHERE_API_KEY=None,
    )
    providers = cfg.provider_configs()
    azure = next(provider for provider in providers if provider.name == "azure-openai")
    assert azure.extras["deployments"]["gpt-4o"] == "prod-gpt"


def test_otel_headers_parsing():
    cfg = Settings(OTEL_EXPORTER_OTLP_HEADERS="api-key=123, another = value")
    headers = cfg.otel_headers()
    assert headers == {"api-key": "123", "another": "value"}
