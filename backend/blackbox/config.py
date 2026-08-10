"""Central configuration. All paths are derived from the repo root so the app
can be launched from anywhere inside the repository."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_repo_root() -> Path:
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / "pyproject.toml").exists() and (parent / "pipeline").exists():
            return parent
    return Path(__file__).resolve().parents[2]


REPO_ROOT = _find_repo_root()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5"

    datahub_gms_url: str = "http://localhost:8080"
    datahub_gms_token: str = ""
    # Eval ablation: when true, the investigator's DataHub tools return errors so we
    # can measure how load-bearing DataHub context is (see evals/).
    blackbox_disable_datahub: bool = False

    blackbox_api_port: int = 8400

    # Fixture / pipeline layout (kept in sync with pipeline/)
    warehouse_path: Path = REPO_ROOT / "data" / "warehouse" / "blackbox.duckdb"
    metric_snapshot_path: Path = REPO_ROOT / "data" / "warehouse" / "metric_snapshot.json"
    transforms_dir: Path = REPO_ROOT / "pipeline" / "transforms"
    baselines_dir: Path = REPO_ROOT / "pipeline" / "baselines"
    incidents_dir: Path = REPO_ROOT / "data" / "incidents"

    # DataHub URN conventions for the demo stack
    datahub_platform: str = "duckdb"
    datahub_env: str = "PROD"


settings = Settings()
