import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class AppConfig:
    app_name: str
    database_path: Path
    upload_root: Path
    drive_mirror_root: Path
    default_client: dict


def load_json(relative_path: str) -> dict:
    path = ROOT / relative_path
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _env_list(name: str, fallback: list[str]) -> list[str]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return fallback
    return [item.strip() for item in raw.split(",") if item.strip()]


def _configured_path(env_name: str, configured: str) -> Path:
    raw_path = os.environ.get(env_name, "").strip() or configured
    path = Path(raw_path).expanduser()
    return path if path.is_absolute() else ROOT / path


def load_app_config() -> AppConfig:
    raw = load_json("config/app.json")
    database_path = _configured_path("ASCEND_DATABASE_PATH", raw["database_path"])
    legacy_database_paths = [path for path in (ROOT / "data/db").glob("*.sqlite") if path != database_path]
    if not database_path.exists() and legacy_database_paths:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy_database_paths[0], database_path)
    return AppConfig(
        app_name=raw["app_name"],
        database_path=database_path,
        upload_root=_configured_path("ASCEND_UPLOAD_ROOT", raw["upload_root"]),
        drive_mirror_root=_configured_path("ASCEND_MIRROR_ROOT", raw["drive_mirror_root"]),
        default_client=raw["default_client"],
    )


def load_openai_config() -> dict:
    return load_json("config/openai.json")


def load_google_drive_config() -> dict:
    return load_json("config/google_drive.json")


def load_cors_origins() -> list[str]:
    defaults = [
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]
    return _env_list("ASCEND_CORS_ORIGINS", defaults)
