"""Controller-owned Docker resource journal and crash recovery lease."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from fettle.uat.session import _write_bytes_atomic

_ACTIVE: ContextVar[tuple | None] = ContextVar("uat_resource_lease", default=None)
LABEL = "fettle.uat.owner"


def inherited_fds() -> tuple[int, ...]:
    active = _ACTIVE.get()
    return (active[0],) if active else ()


def _persist(path: Path, record: dict) -> None:
    _write_bytes_atomic(path, (json.dumps(record, sort_keys=True) + "\n").encode())


def _backend(context: str) -> dict:
    from fettle.uat.network_controller import _docker

    endpoint = json.loads(_docker(context, ["context", "inspect", context]))[0]["Endpoints"]["docker"]
    if not endpoint["Host"].startswith("unix://") or endpoint.get("SkipTLSVerify"):
        raise ValueError("resource recovery requires a local trusted Docker endpoint")
    return {"endpoint": endpoint, "daemon": _docker(context, ["info", "--format", "{{.ID}}"]).strip()}


def cleanup(record: dict) -> None:
    from fettle.uat.network_controller import _docker

    context, owner = record["context"], record["owner"]
    if any(record["resources"].values()) and record["backend"] != _backend(context):
        raise ValueError("Docker identity changed; preserve journal for original daemon recovery")
    for kind in ("container", "volume", "network"):
        allowed = set(record["resources"][kind])
        if not allowed:
            continue
        arguments = (["ps", "-a"] if kind == "container" else [kind, "ls"])
        names = _docker(context, [*arguments, "--filter", f"label={LABEL}={owner}",
                                  "--format", "{{.Names}}" if kind == "container" else "{{.Name}}"]).splitlines()
        if any(name not in allowed for name in names):
            raise ValueError("recovery found an unrecognized resource; refusing cleanup")
        for name in names:
            _docker(context, ["rm", "--force", name] if kind == "container" else [kind, "rm", name])


def plan_resources(prefix: str) -> list[str]:
    active = _ACTIVE.get()
    if not active:
        raise ValueError("resource creation requires a controller lease")
    _, _, path, record = active
    record["backend"] = _backend(record["context"])
    record["resources"] = {
        "container": [prefix + suffix for suffix in ("-state-keeper", "-seed", "-product", "-observer")],
        "volume": [prefix + suffix for suffix in ("-source", "-state")],
        "network": [prefix + "-network"],
    }
    _persist(path, record)
    return ["--label", f"{LABEL}={record['owner']}"]


def finish_resources() -> None:
    active = _ACTIVE.get()
    if active is None:
        raise ValueError("cleanup requires a controller lease")
    _, _, path, record = active
    cleanup(record)
    record["resources"] = {"container": [], "volume": [], "network": []}
    _persist(path, record)


@contextmanager
def lease(root: str, context: str, on_acquired=None):
    from fettle.uat.controller import _store_root, _unique_object

    identity = (str(Path(root).resolve()), context)
    active = _ACTIVE.get()
    if active:
        if active[1] != identity:
            raise ValueError("nested capture cannot change resource ownership")
        yield
        return
    try:
        import fcntl
    except ImportError as exception:
        raise ValueError("qualified resource recovery requires Unix file locks") from exception
    store = _store_root().resolve() / "resources"
    if store.is_relative_to(Path(root).resolve()):
        raise ValueError("recovery journal must be outside product access")
    store.mkdir(parents=True, mode=0o700, exist_ok=True)
    key = hashlib.sha256(identity[0].encode()).hexdigest()
    path = store / (key + ".json")
    descriptor = os.open(store / (key + ".lock"), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    token = None
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exception:
            raise ValueError("capture or surviving Docker operation is active; wait before recovery") from exception
        if on_acquired is not None:
            on_acquired()
        if path.exists() or path.is_symlink():
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
                raise ValueError("malformed resource journal; refusing recovery")
            previous = json.loads(path.read_bytes(), object_pairs_hook=_unique_object)
            if (not isinstance(previous, dict)
                    or set(previous) != {"schema_version", "root", "context", "owner", "resources", "backend"}
                    or type(previous["schema_version"]) is not int or previous["schema_version"] != 1
                    or (previous["root"], previous["context"]) != identity
                    or not isinstance(previous["owner"], str)
                    or not re.fullmatch(r"[0-9a-f]{32}", previous["owner"])
                    or not isinstance(previous["resources"], dict)
                    or set(previous["resources"]) != {"container", "volume", "network"}
                    or any(not isinstance(names, list) or len(names) > 8
                           or any(not isinstance(name, str) or not re.fullmatch(
                               r"fettle-uat-[0-9a-f]{32}-(state-keeper|seed|product|observer|source|state|network)", name)
                                  for name in names) for names in previous["resources"].values())):
                raise ValueError("invalid resource ownership journal; refusing recovery")
            token = _ACTIVE.set((descriptor, identity, path, previous))
            cleanup(previous)
            path.unlink()
        record = {"schema_version": 1, "root": identity[0], "context": context,
                  "owner": uuid.uuid4().hex, "backend": None,
                  "resources": {"container": [], "volume": [], "network": []}}
        _persist(path, record)
        if token is not None:
            _ACTIVE.reset(token)
        token = _ACTIVE.set((descriptor, identity, path, record))
        try:
            yield
        finally:
            cleanup(record)
            path.unlink()
    finally:
        if token is not None:
            _ACTIVE.reset(token)
        os.close(descriptor)