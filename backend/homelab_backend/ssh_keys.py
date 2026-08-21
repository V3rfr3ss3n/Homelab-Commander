"""Persistent backend-managed SSH identity."""

import asyncio
import subprocess
from pathlib import Path


class SshKeyStore:
    """Generate one ED25519 identity and expose only its public half."""

    def __init__(self, private_key_path: Path) -> None:
        self._private_key_path = private_key_path
        self._lock = asyncio.Lock()

    async def async_ensure(self) -> None:
        """Create the key exactly once and enforce private permissions."""
        async with self._lock:
            await asyncio.to_thread(self._ensure)

    async def async_public_key(self) -> str:
        """Return the OpenSSH public key without reading it into logs."""
        await self.async_ensure()
        return await asyncio.to_thread(self._public_key)

    def _ensure(self) -> None:
        path = self._private_key_path
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not path.exists():
            result = subprocess.run(
                [
                    "ssh-keygen",
                    "-q",
                    "-t",
                    "ed25519",
                    "-N",
                    "",
                    "-C",
                    "homelab-updates",
                    "-f",
                    str(path),
                ],
                check=False,
                capture_output=True,
            )
            if result.returncode != 0 or not path.exists():
                raise ValueError("Could not generate the managed ED25519 key")
        path.chmod(0o600)

    def _public_key(self) -> str:
        result = subprocess.run(
            ["ssh-keygen", "-y", "-f", str(self._private_key_path)],
            check=False,
            capture_output=True,
        )
        public_key = result.stdout.decode("ascii", errors="strict").strip()
        if result.returncode != 0 or not public_key.startswith("ssh-ed25519 "):
            raise ValueError("The managed SSH key is not ED25519")
        return public_key
