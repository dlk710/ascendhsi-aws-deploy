import json
import mimetypes
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


FOLDER_MIME = "application/vnd.google-apps.folder"


class GoogleDriveConfigError(RuntimeError):
    pass


class GoogleDriveUploadError(RuntimeError):
    pass


class GoogleDriveClient:
    def __init__(self, config: dict):
        self.config = config

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("enabled"))

    def access_token(self) -> str:
        env_name = self.config.get("access_token_env", "GOOGLE_DRIVE_ACCESS_TOKEN")
        return os.environ.get(env_name, "").strip()

    def build_file_url(self, file_id: str) -> str:
        return f"https://drive.google.com/file/d/{file_id}/view"

    def require_token(self) -> str:
        token = self.access_token()
        if not token:
            raise GoogleDriveConfigError(
                f"Google Drive is enabled, but {self.config.get('access_token_env', 'GOOGLE_DRIVE_ACCESS_TOKEN')} is not set."
            )
        return token

    def request_json(self, method: str, url: str, payload: dict | None = None) -> dict:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.require_token()}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise GoogleDriveUploadError(f"Google Drive API failed with HTTP {exc.code}: {details}") from exc
        except urllib.error.URLError as exc:
            raise GoogleDriveUploadError(f"Could not reach Google Drive API: {exc.reason}") from exc

    def find_child_folder(self, parent_id: str, name: str) -> str | None:
        escaped = name.replace("\\", "\\\\").replace("'", "\\'")
        query = (
            f"name = '{escaped}' and mimeType = '{FOLDER_MIME}' "
            f"and '{parent_id}' in parents and trashed = false"
        )
        params = urllib.parse.urlencode({"q": query, "fields": "files(id,name)", "pageSize": "1", "supportsAllDrives": "true"})
        data = self.request_json("GET", f"https://www.googleapis.com/drive/v3/files?{params}")
        files = data.get("files", [])
        return files[0]["id"] if files else None

    def create_folder(self, parent_id: str, name: str) -> str:
        data = self.request_json(
            "POST",
            "https://www.googleapis.com/drive/v3/files?fields=id&supportsAllDrives=true",
            {"name": name, "mimeType": FOLDER_MIME, "parents": [parent_id]},
        )
        return data["id"]

    def ensure_folder_path(self, parts: list[str]) -> str:
        parent_id = self.config["folder_id"]
        for part in parts:
            existing = self.find_child_folder(parent_id, part)
            parent_id = existing or self.create_folder(parent_id, part)
        return parent_id

    def upload_file(self, parent_id: str, source_path: Path, file_name: str) -> dict:
        mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        boundary = f"ascend-{uuid.uuid4().hex}"
        metadata = {"name": file_name, "parents": [parent_id]}
        body = b"".join(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                b"Content-Type: application/json; charset=UTF-8\r\n\r\n",
                json.dumps(metadata).encode("utf-8"),
                b"\r\n",
                f"--{boundary}\r\n".encode("utf-8"),
                f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"),
                source_path.read_bytes(),
                b"\r\n",
                f"--{boundary}--\r\n".encode("utf-8"),
            ]
        )
        req = urllib.request.Request(
            "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name,webViewLink&supportsAllDrives=true",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.require_token()}",
                "Content-Type": f"multipart/related; boundary={boundary}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise GoogleDriveUploadError(f"Google Drive file upload failed with HTTP {exc.code}: {details}") from exc
        except urllib.error.URLError as exc:
            raise GoogleDriveUploadError(f"Could not upload to Google Drive: {exc.reason}") from exc

    def get_file_parents(self, file_id: str) -> list[str]:
        params = urllib.parse.urlencode({"fields": "parents", "supportsAllDrives": "true"})
        data = self.request_json("GET", f"https://www.googleapis.com/drive/v3/files/{file_id}?{params}")
        return data.get("parents", [])

    def move_file_to_folder(self, file_id: str, destination_folder_id: str) -> dict:
        parents = self.get_file_parents(file_id)
        params = {
            "addParents": destination_folder_id,
            "fields": "id,name,webViewLink,parents",
            "supportsAllDrives": "true",
        }
        if parents:
            params["removeParents"] = ",".join(parents)
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?{urllib.parse.urlencode(params)}"
        return self.request_json("PATCH", url, {})
