"""Exercise a pinned container boundary before enabling networked UAT drivers."""

from __future__ import annotations

import argparse
import json
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path

IMAGE = "docker.io/library/alpine@sha256:85fe1e81d6758c208f3e1eed4338a1997e19d4be002d4dd32d3100c9a8c010a0"


def qualify(docker: str, context: str) -> dict:
    prefix = "fettle-boundary-" + uuid.uuid4().hex
    network = prefix + "-network"
    product = prefix + "-product"
    observer = prefix + "-observer"
    observations = []
    cleanup = []

    def invoke(arguments: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
        return subprocess.run([docker, "--context", context, *arguments],
                              text=True, capture_output=True, timeout=timeout)

    def require(arguments: list[str]) -> subprocess.CompletedProcess:
        result = invoke(arguments)
        if result.returncode:
            raise RuntimeError(result.stderr[:4096])
        return result

    def probe(name: str, container: str, command: list[str], expected: str) -> None:
        result = invoke(["exec", container, *command])
        observations.append({"name": name, "exit_code": result.returncode,
                             "stdout": result.stdout[:8192], "stderr": result.stderr[:8192],
                             "passed": result.returncode == 0 and result.stdout == expected})

    options = ["--read-only", "--user", "65534:65534", "--cap-drop", "ALL",
               "--security-opt", "no-new-privileges:true", "--pids-limit", "32",
               "--memory", "64m", "--memory-swap", "64m", "--cpus", "0.5",
               "--dns", "127.0.0.1", "--log-driver", "none", "--pull", "never",
               "--label", "fettle.qualification=" + prefix]
    error = ""
    identity = {}
    try:
        identity = json.loads(require(["image", "inspect", IMAGE]).stdout)[0]
        require(["network", "create", "--internal", "--opt",
             "com.docker.network.bridge.gateway_mode_ipv4=isolated", "--label",
                 "fettle.qualification=" + prefix, network])
        require(["run", "--detach", "--name", product, "--network", network,
                 "--network-alias", "product", *options,
                 "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=1m,mode=1777",
                 IMAGE, "sh", "-c",
                 "while true; do printf 'HTTP/1.0 200 OK\\r\\nContent-Length: 12\\r\\n\\r\\nboundary-ok\\n' "
                 "| nc -l -p 8080 -w 2; done"])
        require(["run", "--detach", "--name", observer, "--network", network,
                 *options, IMAGE, "tail", "-f", "/dev/null"])
        inspected = json.loads(require(["inspect", product, observer]).stdout)
        for container in inspected:
            host = container["HostConfig"]
            restricted = (
                container["Config"]["User"] == "65534:65534"
                and host["ReadonlyRootfs"] is True
                and host["Privileged"] is False
                and host["CapDrop"] == ["ALL"]
                and "no-new-privileges:true" in host["SecurityOpt"]
                and host["PidsLimit"] == 32
                and host["Memory"] == host["MemorySwap"] == 67108864
                and host["NanoCpus"] == 500000000
                and not host["Binds"] and not host["PortBindings"]
                and not container["Mounts"]
                and len(container["NetworkSettings"]["Networks"]) == 1
            )
            observations.append({"name": container["Name"].rsplit("-", 1)[-1] + "-configuration",
                                 "passed": restricted})
        network_info = json.loads(require(["network", "inspect", network]).stdout)[0]
        observations.append({"name": "internal-network", "passed": network_info["Internal"] is True})
        observations.append({"name": "no-bridge-gateway", "passed":
                     network_info["Options"].get("com.docker.network.bridge.gateway_mode_ipv4") == "isolated"
                     and all(not item.get("Gateway") for item in network_info["IPAM"]["Config"])})
        probe("local-product-http", observer,
              ["wget", "-q", "-T", "3", "-O", "-", "http://product:8080/"], "boundary-ok\n")
        for container, role in ((product, "product"), (observer, "observer")):
            probe(role + "-identity", container, ["id", "-u"], "65534\n")
            probe(role + "-root-write-denied", container,
                  ["sh", "-c", "if touch /unexpected-write 2>/dev/null; then exit 1; fi; printf denied"], "denied")
            probe(role + "-no-host-or-evidence", container,
                  ["sh", "-c", "test ! -e /Users && test ! -e /var/run/docker.sock && "
                   "test ! -e /root/.local/state/fettle/uat-capture && printf absent"], "absent")
            probe(role + "-kernel-restrictions", container,
                  ["sh", "-c", "grep -E '^(CapEff|NoNewPrivs|Seccomp):' /proc/self/status"],
                  "CapEff:\t0000000000000000\nNoNewPrivs:\t1\nSeccomp:\t2\n")
            probe(role + "-memory-bound", container,
                  ["cat", "/sys/fs/cgroup/memory.max"], "67108864\n")
            probe(role + "-process-bound", container,
                  ["cat", "/sys/fs/cgroup/pids.max"], "32\n")
            probe(role + "-no-default-route", container,
                ["awk", '$2 == "00000000" {print}', "/proc/net/route"], "")
            probe(role + "-external-tcp-denied", container,
                  ["sh", "-c", "if nc -z -w 2 1.1.1.1 443; then exit 1; fi; printf denied"], "denied")
            probe(role + "-external-dns-denied", container,
                  ["sh", "-c", "if timeout 3 nslookup example.com >/dev/null 2>&1; "
                   "then exit 1; fi; printf denied"], "denied")
        probe("bounded-product-write", product,
              ["sh", "-c", "printf state > /tmp/state; cat /tmp/state"], "state")
        probe("observer-write-denied", observer,
              ["sh", "-c", "if touch /tmp/state 2>/dev/null; then exit 1; fi; printf denied"], "denied")
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exception:
        error = str(exception)[:4096]
    finally:
        for arguments in (["rm", "--force", product, observer], ["network", "rm", network]):
            try:
                result = invoke(arguments)
                cleanup.append({"operation": arguments[0], "exit_code": result.returncode,
                                "stderr": result.stderr[:4096]})
            except (OSError, subprocess.TimeoutExpired) as exception:
                cleanup.append({"operation": arguments[0], "exit_code": -1, "stderr": str(exception)})
    return {"schema_version": 1, "recorded_at": datetime.now(UTC).isoformat(),
            "context": context, "image": IMAGE, "image_id": identity.get("Id"),
            "observations": observations, "error": error, "cleanup": cleanup,
            "passed": bool(observations) and not error
            and all(item["passed"] for item in observations)
            and all(item["exit_code"] == 0 for item in cleanup),
            "limits": ["single pinned Alpine image on named local Docker VM",
                       "trusted Docker daemon and VM kernel; not a VM escape proof",
                       "isolated bridge has no gateway; arbitrary daemon/network reconfiguration is outside scope",
                       "not API/browser acceptance or unrestricted-agent qualification"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker", default="/opt/homebrew/bin/docker")
    parser.add_argument("--context", default="colima-fettle-uat")
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = qualify(arguments.docker, arguments.context)
    arguments.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()