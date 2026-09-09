"""Prove installed replay works without OpenAI or a local .env file."""

import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def main() -> None:
    assert importlib.util.find_spec("openai") is None, "Use an environment without discovery extra"
    artifact = Path("evidence/capabilities/open-savings-subaccount.v1.json").resolve()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    env = {k: v for k, v in os.environ.items() if not k.startswith("OPENAI_")}
    env["LEGACYFLOW_BASE_URL"] = base
    with tempfile.TemporaryDirectory(prefix="legacyflow-replay-") as temporary:
        root = Path(temporary)
        policy = root / "policy.json"
        policy.write_text(json.dumps({"allowed_origins": [base]}))
        server = subprocess.Popen(
            [sys.executable, "-m", "legacyflow.cli", "demo", "serve", "--port", str(port)],
            cwd=root,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            for _ in range(100):
                try:
                    with urllib.request.urlopen(base + "/members", timeout=1) as response:
                        assert response.status == 200
                        break
                except urllib.error.URLError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Demo server did not start")
            for member, status in [("23456", "success"), ("99999", "business_outcome")]:
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "legacyflow.cli",
                        "replay",
                        str(artifact),
                        "--input",
                        f"member_id={member}",
                        "--input",
                        "initial_deposit=250",
                        "--headless",
                        "--policy",
                        str(policy),
                        "--root",
                        str(root / status),
                    ],
                    cwd=root,
                    env=env,
                    check=True,
                    capture_output=True,
                    timeout=40,
                )
                result = json.loads(next((root / status).glob("*/result.json")).read_text())
                assert result["status"] == status
                if status == "success":
                    assert result["outputs"]["initial_deposit"] == "250.00"
                else:
                    assert result["outcome"] == "member_not_found"
                print(
                    f"Replay-only environment: {status}; OpenAI absent; no .env; credentials absent"
                )
        finally:
            server.terminate()
            server.wait(timeout=10)


if __name__ == "__main__":
    main()
