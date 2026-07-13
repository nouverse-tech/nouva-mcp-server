import os
import subprocess


class NasHelper:
    """Abstraction over local filesystem or SSH-based NAS operations."""

    def __init__(self, archived_memory_dir: str, ssh_host: str = None):
        self.base_dir = archived_memory_dir
        self.ssh_host = ssh_host

    def _path(self, subfolder: str, filename: str = None) -> str:
        if filename:
            return os.path.join(self.base_dir, subfolder, filename)
        return os.path.join(self.base_dir, subfolder)

    def _ssh(self, cmd: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["ssh", self.ssh_host, cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def file_exists(self, subfolder: str, filename: str) -> bool:
        nas_path = self._path(subfolder, filename)
        if self.ssh_host:
            return self._ssh(f'[ -f "{nas_path}" ]').returncode == 0
        return os.path.isfile(nas_path)

    def touch(self, subfolder: str, filename: str):
        nas_path = self._path(subfolder, filename)
        if self.ssh_host:
            self._ssh(f'mkdir -p "$(dirname "{nas_path}")" && touch "{nas_path}"')
        else:
            os.makedirs(os.path.dirname(nas_path), exist_ok=True)
            open(nas_path, "a").close()

    def makedirs(self, subfolder: str):
        nas_path = self._path(subfolder)
        if self.ssh_host:
            self._ssh(f'mkdir -p "{nas_path}"')
        else:
            os.makedirs(nas_path, exist_ok=True)

    def copy_to(self, local_path: str, subfolder: str, filename: str) -> bool:
        nas_path = self._path(subfolder, filename)
        if self.ssh_host:
            self._ssh(f'mkdir -p "$(dirname "{nas_path}")"')
            res = subprocess.run(
                ["scp", local_path, f"{self.ssh_host}:{nas_path}"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            return res.returncode == 0
        else:
            os.makedirs(os.path.dirname(nas_path), exist_ok=True)
            try:
                with open(local_path, "rb") as src:
                    data = src.read()
                with open(nas_path, "wb") as dst:
                    dst.write(data)
                return True
            except Exception as e:
                print(f"❌ Local copy failed: {e}")
                return False

    def copy_from(self, subfolder: str, filename: str, local_path: str) -> bool:
        nas_path = self._path(subfolder, filename)
        if self.ssh_host:
            res = subprocess.run(
                ["scp", f"{self.ssh_host}:{nas_path}", local_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            return res.returncode == 0
        else:
            try:
                with open(nas_path, "rb") as src:
                    data = src.read()
                with open(local_path, "wb") as dst:
                    dst.write(data)
                return True
            except Exception as e:
                print(f"❌ Local copy failed: {e}")
                return False

    def list_dir(self, subfolder: str) -> list:
        nas_path = self._path(subfolder)
        if self.ssh_host:
            res = subprocess.run(
                ["ssh", self.ssh_host, f"ls -1 '{nas_path}' 2>/dev/null"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            if res.returncode == 0:
                return [l.strip() for l in res.stdout.splitlines() if l.strip()]
            return []
        else:
            if os.path.exists(nas_path):
                try:
                    return os.listdir(nas_path)
                except Exception:
                    pass
            return []

    def read_text(self, subfolder: str, filename: str) -> str | None:
        nas_path = self._path(subfolder, filename)
        if self.ssh_host:
            res = subprocess.run(
                ["ssh", self.ssh_host, f"cat '{nas_path}'"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            return res.stdout if res.returncode == 0 else None
        else:
            if os.path.exists(nas_path):
                try:
                    with open(nas_path, "r", encoding="utf-8") as f:
                        return f.read()
                except Exception:
                    pass
            return None
