import json
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


def load_app_config() -> AppConfig:
    raw = load_json("config/app.json")
    database_path = ROOT / raw["database_path"]
    legacy_database_paths = [path for path in (ROOT / "data/db").glob("*.sqlite") if path != database_path]
    if not database_path.exists() and legacy_database_paths:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy_database_paths[0], database_path)
    return AppConfig(
        app_name=raw["app_name"],
        database_path=database_path,
        upload_root=ROOT / raw["upload_root"],
        drive_mirror_root=ROOT / raw["drive_mirror_root"],
        default_client=raw["default_client"],
    )


def load_openai_config() -> dict:
    return load_json("config/openai.json")


def load_google_drive_config() -> dict:
    return load_json("config/google_drive.json")
