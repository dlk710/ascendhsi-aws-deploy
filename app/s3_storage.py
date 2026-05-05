import os
from pathlib import Path


class S3ConfigError(RuntimeError):
    pass


class S3StorageError(RuntimeError):
    pass


class S3StorageClient:
    def __init__(self, config: dict):
        self.config = config
        self._client = None

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("enabled")) and bool(self.bucket_name())

    def bucket_name(self) -> str:
        env_name = self.config.get("bucket_env", "ASCEND_STORAGE_BUCKET")
        return os.environ.get(env_name, "").strip() or str(self.config.get("bucket", "")).strip()

    def archive_bucket_name(self) -> str:
        env_name = self.config.get("archive_bucket_env", "ASCEND_ARCHIVE_BUCKET")
        return os.environ.get(env_name, "").strip() or str(self.config.get("archive_bucket", "")).strip() or self.bucket_name()

    def region_name(self) -> str:
        env_name = self.config.get("region_env", "AWS_REGION")
        return os.environ.get(env_name, "").strip() or str(self.config.get("region", "")).strip()

    def endpoint_url(self) -> str:
        env_name = self.config.get("endpoint_url_env", "AWS_S3_ENDPOINT_URL")
        return os.environ.get(env_name, "").strip() or str(self.config.get("endpoint_url", "")).strip()

    def public_base_url(self) -> str:
        env_name = self.config.get("public_base_url_env", "ASCEND_STORAGE_PUBLIC_BASE_URL")
        return os.environ.get(env_name, "").strip().rstrip("/") or str(self.config.get("public_base_url", "")).strip().rstrip("/")

    def active_prefix(self) -> str:
        return str(self.config.get("key_prefix", "active")).strip().strip("/")

    def archive_prefix(self) -> str:
        return str(self.config.get("archive_prefix", "archive")).strip().strip("/")

    def active_storage_class(self) -> str:
        return str(self.config.get("active_storage_class", "INTELLIGENT_TIERING")).strip() or "INTELLIGENT_TIERING"

    def archive_storage_class(self) -> str:
        return str(self.config.get("archive_storage_class", "GLACIER_IR")).strip() or "GLACIER_IR"

    def url_ttl_seconds(self) -> int:
        try:
            return max(60, int(self.config.get("url_ttl_seconds", 3600)))
        except (TypeError, ValueError):
            return 3600

    def server_side_encryption(self) -> str:
        env_name = self.config.get("server_side_encryption_env", "ASCEND_S3_SERVER_SIDE_ENCRYPTION")
        return os.environ.get(env_name, "").strip() or str(self.config.get("server_side_encryption", "AES256")).strip() or "AES256"

    def kms_key_id(self) -> str:
        env_name = self.config.get("kms_key_id_env", "ASCEND_S3_KMS_KEY_ID")
        return os.environ.get(env_name, "").strip() or str(self.config.get("kms_key_id", "")).strip()

    def require_bucket(self) -> str:
        bucket = self.bucket_name()
        if not bucket:
            raise S3ConfigError(
                f"S3 storage is enabled, but {self.config.get('bucket_env', 'ASCEND_STORAGE_BUCKET')} is not set."
            )
        return bucket

    def _build_client(self):
        try:
            import boto3
        except ImportError as exc:
            raise S3ConfigError("boto3 is required for S3-backed storage. Install the Python requirements for deployment.") from exc

        kwargs = {}
        if self.region_name():
            kwargs["region_name"] = self.region_name()
        if self.endpoint_url():
            kwargs["endpoint_url"] = self.endpoint_url()
        return boto3.client("s3", **kwargs)

    def client(self):
        if self._client is None:
            self._client = self._build_client()
        return self._client

    def _normalize_prefix(self, prefix: str) -> str:
        cleaned = str(prefix or "").strip().strip("/")
        if not cleaned:
            return self.active_prefix()
        if cleaned.startswith(f"{self.active_prefix()}/") or cleaned == self.active_prefix():
            return cleaned
        if cleaned.startswith(f"{self.archive_prefix()}/") or cleaned == self.archive_prefix():
            return cleaned
        base = self.archive_prefix() if cleaned.startswith("archive/") else self.active_prefix()
        return f"{base}/{cleaned}" if base else cleaned

    def ensure_folder_path(self, parts: list[str]) -> str:
        joined = "/".join(part.strip("/") for part in parts if str(part).strip("/"))
        return self._normalize_prefix(joined)

    def build_file_url(self, file_id: str, bucket: str | None = None) -> str:
        object_key = str(file_id or "").strip()
        if not object_key:
            return ""
        base = self.public_base_url()
        if base:
            return f"{base}/{object_key}"
        try:
            return self.client().generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket or self.require_bucket(), "Key": object_key},
                ExpiresIn=self.url_ttl_seconds(),
            )
        except Exception as exc:
            raise S3StorageError(f"Could not create an S3 download URL: {exc}") from exc

    def _extra_args(self, content_type: str = "", storage_class: str = "") -> dict:
        args: dict[str, str] = {"StorageClass": storage_class or self.active_storage_class()}
        if content_type:
            args["ContentType"] = content_type
        encryption = self.server_side_encryption()
        if encryption:
            args["ServerSideEncryption"] = encryption
        kms_key_id = self.kms_key_id()
        if kms_key_id:
            args["ServerSideEncryption"] = "aws:kms"
            args["SSEKMSKeyId"] = kms_key_id
        return args

    def upload_file(self, parent_id: str, source_path: Path, file_name: str, content_type: str = "") -> dict:
        bucket = self.require_bucket()
        object_key = f"{self._normalize_prefix(parent_id)}/{file_name}".strip("/")
        try:
            self.client().upload_file(
                str(source_path),
                bucket,
                object_key,
                ExtraArgs=self._extra_args(content_type, self.active_storage_class()),
            )
        except Exception as exc:
            raise S3StorageError(f"Could not upload to Amazon S3: {exc}") from exc
        return {
            "id": object_key,
            "bucket": bucket,
            "webViewLink": self.build_file_url(object_key, bucket=bucket),
            "storageClass": self.active_storage_class(),
        }

    def upload_bytes(self, parent_id: str, file_name: str, payload: bytes, content_type: str = "") -> dict:
        bucket = self.require_bucket()
        object_key = f"{self._normalize_prefix(parent_id)}/{file_name}".strip("/")
        try:
            self.client().put_object(
                Bucket=bucket,
                Key=object_key,
                Body=payload,
                **self._extra_args(content_type, self.active_storage_class()),
            )
        except Exception as exc:
            raise S3StorageError(f"Could not upload bytes to Amazon S3: {exc}") from exc
        return {
            "id": object_key,
            "bucket": bucket,
            "webViewLink": self.build_file_url(object_key, bucket=bucket),
            "storageClass": self.active_storage_class(),
        }

    def move_file_to_folder(self, file_id: str, destination_prefix: str) -> dict:
        bucket = self.require_bucket()
        archive_bucket = self.archive_bucket_name()
        source_key = str(file_id or "").strip().strip("/")
        if not source_key:
            raise S3StorageError("Storage key is required for archive move.")
        destination_key = f"{self._normalize_prefix(destination_prefix)}/{Path(source_key).name}".strip("/")
        try:
            extra_args = {
                key: value
                for key, value in self._extra_args(storage_class=self.archive_storage_class()).items()
                if key not in {"ContentType", "StorageClass"}
            }
            self.client().copy_object(
                Bucket=archive_bucket,
                Key=destination_key,
                CopySource={"Bucket": bucket, "Key": source_key},
                StorageClass=self.archive_storage_class(),
                MetadataDirective="COPY",
                **extra_args,
            )
            self.client().delete_object(Bucket=bucket, Key=source_key)
        except Exception as exc:
            raise S3StorageError(f"Could not archive an Amazon S3 object: {exc}") from exc
        return {
            "id": destination_key,
            "bucket": archive_bucket,
            "webViewLink": self.build_file_url(destination_key, bucket=archive_bucket),
            "storageClass": self.archive_storage_class(),
        }

    def healthcheck(self) -> dict:
        bucket = self.require_bucket()
        try:
            self.client().head_bucket(Bucket=bucket)
        except Exception as exc:
            raise S3StorageError(f"Amazon S3 health check failed: {exc}") from exc
        return {"bucket": bucket, "archive_bucket": self.archive_bucket_name(), "region": self.region_name()}
