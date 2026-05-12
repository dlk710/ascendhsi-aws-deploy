import mimetypes
import os
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.google_drive import GoogleDriveClient


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


class S3StorageClient:
    def __init__(self):
        self.bucket = os.environ.get("ASCEND_EVIDENCE_S3_BUCKET", "").strip()
        self.region = os.environ.get("ASCEND_EVIDENCE_S3_REGION", "").strip()
        self.prefix = os.environ.get("ASCEND_EVIDENCE_S3_PREFIX", "").strip().strip("/")
        self.kms_key_id = os.environ.get("ASCEND_EVIDENCE_S3_KMS_KEY_ID", "").strip()
        self.endpoint_url = os.environ.get("ASCEND_EVIDENCE_S3_ENDPOINT_URL", "").strip()

    @property
    def enabled(self) -> bool:
        return bool(self.bucket)

    def _client(self):
        import boto3

        kwargs = {}
        if self.region:
            kwargs["region_name"] = self.region
        if self.endpoint_url:
            kwargs["endpoint_url"] = self.endpoint_url
        return boto3.client("s3", **kwargs)

    def _prefixed_key(self, relative_key: str) -> str:
        cleaned = relative_key.strip("/")
        return f"{self.prefix}/{cleaned}" if self.prefix else cleaned

    def uri_for_key(self, key: str) -> str:
        return f"s3://{self.bucket}/{key.strip('/')}"

    def upload_file(self, relative_key: str, source_path: Path, content_type: str = "") -> str:
        key = self._prefixed_key(relative_key)
        extra_args = {}
        normalized_content_type = (content_type or "").strip() or mimetypes.guess_type(source_path.name)[0] or "application/octet-stream"
        if normalized_content_type:
            extra_args["ContentType"] = normalized_content_type
        if self.kms_key_id:
            extra_args["ServerSideEncryption"] = "aws:kms"
            extra_args["SSEKMSKeyId"] = self.kms_key_id
        self._client().upload_file(str(source_path), self.bucket, key, ExtraArgs=extra_args)
        return self.uri_for_key(key)

    def archive_uri(self, source_uri: str) -> str:
        key = self.key_from_uri(source_uri)
        if key.startswith("archive/"):
            return self.uri_for_key(key)
        return self.uri_for_key(f"archive/{key}")

    def key_from_uri(self, uri: str) -> str:
        prefix = f"s3://{self.bucket}/"
        if uri.startswith(prefix):
            return uri[len(prefix):].strip("/")
        return uri.strip("/")

    def move_to_archive(self, source_uri: str) -> str:
        source_key = self.key_from_uri(source_uri)
        archive_key = self.key_from_uri(self.archive_uri(source_uri))
        if source_key == archive_key:
            return self.uri_for_key(archive_key)
        client = self._client()
        client.copy_object(Bucket=self.bucket, CopySource={"Bucket": self.bucket, "Key": source_key}, Key=archive_key)
        client.delete_object(Bucket=self.bucket, Key=source_key)
        return self.uri_for_key(archive_key)


class EvidenceStorage:
    def __init__(self, upload_root: Path, drive_mirror_root: Path, google_drive: GoogleDriveClient | None = None, s3_client: S3StorageClient | None = None):
        self.upload_root = upload_root
        self.drive_mirror_root = drive_mirror_root
        self.google_drive = google_drive
        self.s3 = s3_client or S3StorageClient()

    def store(self, client_id: str, case_id: str, criterion_code: str, original_name: str, source_path: Path) -> StoredFile:
        evidence_id = f"ev_{uuid.uuid4().hex[:12]}"
        file_name = safe_file_name(original_name)
        path_parts = ["clients", client_id, "cases", case_id, "evidence", criterion_code, evidence_id, "original"]
        drive_path = "/".join(path_parts + [file_name])
        if self.s3.enabled:
            s3_uri = self.s3.upload_file(drive_path, source_path)
            return StoredFile(
                evidence_id=evidence_id,
                file_name=file_name,
                local_path="",
                drive_path=s3_uri,
                drive_file_id="",
                drive_web_url=s3_uri,
            )
        if self.google_drive and self.google_drive.enabled:
            parent_id = self.google_drive.ensure_folder_path(path_parts)
            uploaded = self.google_drive.upload_file(parent_id, source_path, file_name)
            return StoredFile(
                evidence_id=evidence_id,
                file_name=file_name,
                local_path="",
                drive_path=drive_path,
                drive_file_id=uploaded["id"],
                drive_web_url=uploaded.get("webViewLink", ""),
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

    def archive(self, record: dict) -> dict:
        drive_path = str(record.get("drive_path", "")).strip()
        if self.s3.enabled and drive_path.startswith("s3://"):
            archived_uri = self.s3.move_to_archive(drive_path)
            return {
                "archive_path": archived_uri,
                "local_path": "",
                "drive_mirror_path": "",
                "drive_path": archived_uri,
                "drive_web_url": archived_uri,
            }

        local_path = self._archive_local_path(record.get("local_path", ""), self.upload_root)
        mirror_path = self._archive_local_path(record.get("drive_mirror_path", ""), self.drive_mirror_root)
        archive_path = drive_path.strip("/") if drive_path.startswith("archive/") else f"archive/{drive_path.strip('/')}" if drive_path else ""
        if local_path:
            try:
                relative = Path(local_path).resolve().relative_to(self.upload_root.resolve())
                archive_path = relative if relative.parts[:1] == ("archive",) else Path("archive") / relative
            except ValueError:
                pass
        return {
            "archive_path": str(archive_path).replace("\\", "/"),
            "local_path": local_path,
            "drive_mirror_path": mirror_path,
            "drive_path": str(archive_path).replace("\\", "/") if archive_path else drive_path,
            "drive_web_url": str(record.get("drive_web_url", "")).strip(),
        }

    def _archive_local_path(self, raw_path: str, root: Path) -> str:
        cleaned = str(raw_path or "").strip()
        if not cleaned:
            return ""
        source = Path(cleaned)
        if not source.exists():
            return str(source)
        try:
            relative = source.resolve().relative_to(root.resolve())
        except ValueError:
            relative = Path(source.name)
        destination = root / "archive" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        return str(destination)
