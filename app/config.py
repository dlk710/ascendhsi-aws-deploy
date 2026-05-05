import json
import shutil
from dataclasses import dataclass
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class AppConfig:
    app_name: str
    database_path: Path
    upload_root: Path
    drive_mirror_root: Path
    default_client: dict
    database_url: str = ""

    @property
    def database_backend(self) -> str:
        if self.database_url:
            if self.database_url.startswith(("postgres://", "postgresql://")):
                return "postgresql"
            return "external"
        return "sqlite"


def load_json(relative_path: str) -> dict:
    path = ROOT / relative_path
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _env_path(name: str, fallback: Path) -> Path:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return fallback
    candidate = Path(raw)
    return candidate if candidate.is_absolute() else ROOT / candidate


def _env_list(name: str, fallback: list[str]) -> list[str]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return fallback
    return [item.strip() for item in raw.split(",") if item.strip()]


def load_app_config() -> AppConfig:
    raw = load_json("config/app.json")
    database_url = os.environ.get("ASCEND_DATABASE_URL", "").strip()
    database_path = _env_path("ASCEND_DATABASE_PATH", ROOT / raw["database_path"])
    if not database_url:
        legacy_database_paths = [path for path in (ROOT / "data/db").glob("*.sqlite") if path != database_path]
        if not database_path.exists() and legacy_database_paths:
            database_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy_database_paths[0], database_path)
    return AppConfig(
        app_name=os.environ.get("ASCEND_APP_NAME", "").strip() or raw["app_name"],
        database_path=database_path,
        database_url=database_url,
        upload_root=_env_path("ASCEND_UPLOAD_ROOT", ROOT / raw["upload_root"]),
        drive_mirror_root=_env_path("ASCEND_MIRROR_ROOT", ROOT / raw["drive_mirror_root"]),
        default_client=raw["default_client"],
    )


def load_openai_config() -> dict:
    return load_json("config/openai.json")


def load_storage_config() -> dict:
    return load_json("config/storage.json")


def load_cors_origins() -> list[str]:
    defaults = [
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]
    return _env_list("ASCEND_CORS_ORIGINS", defaults)
