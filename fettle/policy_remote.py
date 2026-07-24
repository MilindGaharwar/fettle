"""WP-144 — Central policy distribution.

`[extends]` in .fettle.toml points to an org policy file, cryptographically
pinned by content digest:

    [extends]
    url = "https://raw.githubusercontent.com/acme/policy/<commit>/fettle-org.toml"
    sha256 = "9f2c...<64 hex chars>"

Resolution model (content-addressed, so a cached policy never goes stale):

- Hooks (`config.load_config`)   -> CACHE-ONLY. Never any network in the hook
  path (audit D6). A configured-but-uncached policy warns once via doctor.
- `fettle policy sync`           -> fetches over HTTPS, verifies the digest,
  writes the cache atomically.
- Offline-safe: fetch failures warn and leave local config authoritative —
  enforcement never breaks because a policy server is down.

Security (v1.0 plan credential requirements): HTTPS only, 1 MiB size cap,
digest verified before parse, cache re-verified on every read (a tampered
cache file is discarded), no redirect-following beyond urllib defaults for
GET of public content, no credentials supported by design — policies are
public-readable, content-addressed artifacts.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
import tomllib
import urllib.request
from pathlib import Path
from typing import Any

MAX_POLICY_BYTES = 1024 * 1024  # 1 MiB
FETCH_TIMEOUT_S = 10

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class PolicyError(Exception):
    """Raised for invalid [extends] declarations or failed verification."""


def cache_dir() -> Path:
    base = os.environ.get("FETTLE_POLICY_CACHE_DIR")
    if base:
        return Path(base)
    xdg = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return Path(xdg) / "fettle" / "policy"


def parse_extends(raw_cfg: dict[str, Any]) -> dict[str, str] | None:
    """Validate and return the [extends] declaration, or None if absent.

    Raises PolicyError on a malformed declaration — a mis-pinned org policy
    must be loud, not silently skipped.
    """
    extends = raw_cfg.get("extends")
    if not extends:
        return None
    if not isinstance(extends, dict):
        raise PolicyError("[extends] must be a table with url and sha256")
    url = extends.get("url", "")
    sha256 = str(extends.get("sha256", "")).lower()
    if not isinstance(url, str) or not url:
        raise PolicyError("[extends].url is required")
    if not url.startswith("https://"):
        raise PolicyError(f"[extends].url must be https:// (got {url[:32]!r})")
    if not _SHA256_RE.match(sha256):
        raise PolicyError(
            "[extends].sha256 must be a 64-char hex digest — the pin is what "
            "makes remote policy safe; compute it with: shasum -a 256 <file>"
        )
    return {"url": url, "sha256": sha256}


def _cache_path(sha256: str) -> Path:
    return cache_dir() / f"{sha256}.toml"


def load_cached(extends: dict[str, str]) -> dict[str, Any] | None:
    """Return the cached org policy, re-verifying its digest. None on miss.

    A cache file that no longer matches its digest is deleted (tamper or
    corruption) — never trusted.
    """
    path = _cache_path(extends["sha256"])
    try:
        blob = path.read_bytes()
    except OSError:
        return None
    if hashlib.sha256(blob).hexdigest() != extends["sha256"]:
        try:
            path.unlink()
        except OSError:
            pass
        print(f"fettle: cached policy failed digest re-verification — discarded ({path})",
              file=sys.stderr)
        return None
    try:
        return tomllib.loads(blob.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        print(f"fettle: cached policy is not valid TOML ({exc}) — ignoring", file=sys.stderr)
        return None


def fetch_and_cache(extends: dict[str, str], timeout: float = FETCH_TIMEOUT_S) -> dict[str, Any]:
    """Fetch the org policy over HTTPS, verify the digest, cache atomically.

    Raises PolicyError on any failure — callers (CLI only, never hooks)
    surface the message.
    """
    req = urllib.request.Request(extends["url"], headers={"User-Agent": "fettle-policy-sync"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — https enforced in parse_extends
            blob = resp.read(MAX_POLICY_BYTES + 1)
    except OSError as exc:
        raise PolicyError(f"could not fetch {extends['url']}: {exc}") from exc
    if len(blob) > MAX_POLICY_BYTES:
        raise PolicyError(f"policy exceeds {MAX_POLICY_BYTES} bytes — refusing")
    digest = hashlib.sha256(blob).hexdigest()
    if digest != extends["sha256"]:
        raise PolicyError(
            f"digest mismatch: expected {extends['sha256'][:16]}…, got {digest[:16]}… — "
            "the remote content changed; update the pin deliberately or investigate"
        )
    try:
        policy = tomllib.loads(blob.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise PolicyError(f"fetched policy is not valid TOML: {exc}") from exc

    path = _cache_path(extends["sha256"])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(blob)
    os.replace(tmp, path)
    return policy


def resolve_cached_policy(raw_cfg: dict[str, Any]) -> dict[str, Any] | None:
    """Hook-path resolution: parse [extends] and return the CACHED policy only.

    Never touches the network. Malformed declarations warn (fail-open);
    doctor reports uncached-but-configured policies.
    """
    try:
        extends = parse_extends(raw_cfg)
    except PolicyError as exc:
        print(f"fettle: {exc} — org policy skipped", file=sys.stderr)
        return None
    if extends is None:
        return None
    policy = load_cached(extends)
    if policy is not None:
        policy.pop("extends", None)  # no transitive extends — one hop by design
    return policy
