import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.s3_storage import S3StorageClient


SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def safe_file_name(name: str) -> str:
    cleaned = SAFE_NAME.sub("-", name.strip()).strip("-")
    return cleaned or "uploaded-file"


@dataclass(frozen=True)
class StoredFile:
    evidence_id: str
    file_name: str
    local_path: str
    drive_path: str
    drive_file_id: str
    drive_web_url: str
    storage_provider: str = "local"
    storage_class: str = ""


class EvidenceStorage:
    def __init__(self, upload_root: Path, drive_mirror_root: Path, object_storage: S3StorageClient | None = None):
        self.upload_root = upload_root
        self.drive_mirror_root = drive_mirror_root
        self.object_storage = object_storage

    def store(self, client_id: str, case_id: str, criterion_code: str, original_name: str, source_path: Path) -> StoredFile:
        evidence_id = f"ev_{uuid.uuid4().hex[:12]}"
        file_name = safe_file_name(original_name)
        path_parts = ["clients", client_id, "cases", case_id, "evidence", criterion_code, evidence_id, "original"]
        drive_path = "/".join(path_parts + [file_name])
        if self.object_storage and self.object_storage.enabled:
            parent_id = self.object_storage.ensure_folder_path(path_parts)
            uploaded = self.object_storage.upload_file(parent_id, source_path, file_name)
            return StoredFile(
                evidence_id=evidence_id,
                file_name=file_name,
                local_path="",
                drive_path=drive_path,
                drive_file_id=uploaded["id"],
                drive_web_url=uploaded.get("webViewLink", ""),
                storage_provider="s3",
                storage_class=uploaded.get("storageClass", ""),
            )

        relative = Path(*path_parts)
        local_dir = self.upload_root / relative
        mirror_dir = self.drive_mirror_root / relative
        local_dir.mkdir(parents=True, exist_ok=True)
        mirror_dir.mkdir(parents=True, exist_ok=True)
        local_path = local_dir / file_name
        mirror_path = mirror_dir / file_name
        shutil.copyfile(source_path, local_path)
        shutil.copyfile(local_path, mirror_path)
        return StoredFile(evidence_id, file_name, str(local_path), str(mirror_path), "", "")
