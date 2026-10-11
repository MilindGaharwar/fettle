"""Qualify an installed read-only UAT controller; never uses checkout imports."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

SPEC = """---
fettle-spec: v1
id: greeter
status: active
scope:
  - "app.py"
---

## Requirements

- R1. Greet the supplied name.

## Scenarios

### S1. Named greeting (traces R1)

- Given the CLI is installed
- When the user requests a greeting for Ada
- Then stdout is Hello, Ada followed by a newline
"""


def digest(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def invoke(command: list[str], root: Path, environment: dict) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=root, env=environment, text=True,
                          capture_output=True, timeout=40)


def native_proposal(actions: dict) -> tuple[dict, dict]:
    prompt = ("Return ONLY the action-only JSON object below, without markdown or added fields. "
              "You are an isolated action proposer, not an acceptance judge. These are operator-approved "
              "action metadata, not expected-output oracles. Do not execute anything or read files, "
              "credentials, source, configuration, or network. Never add expected outputs or claim a pass. "
              "The controller independently checks and executes approved actions.\n" + json.dumps(actions))
    return _native_json(prompt)


def _unique_json(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate native JSON field")
        result[key] = value
    return result


def _native_json(prompt: str) -> tuple[dict, dict]:
    command = ["limactl", "shell", "--workdir", "/tmp", "fettle-native", "--", "sh", "-c",
               'export CODEX_HOME="$HOME/native-state" SSL_CERT_FILE="$HOME/native-runtime/public-ca.pem"; '
               'cd "$HOME/native-work" && timeout --signal=TERM --kill-after=5s 180s '
               '"$HOME/native-runtime/bin/codex" --ask-for-approval on-request --sandbox read-only '
               'exec --skip-git-repo-check --ephemeral --json -']
    result = subprocess.run(command, input=prompt, capture_output=True, text=True, timeout=200)
    if result.returncode or len(result.stdout.encode()) > 1048576:
        raise ValueError("native proposal unavailable or output exceeds budget; no controller execution")
    events = [json.loads(line, object_pairs_hook=_unique_json)
              for line in result.stdout.splitlines() if line.strip()]
    if (not events or any(not isinstance(event, dict) for event in events)
            or events[-1].get("type") != "turn.completed"
            or any(event.get("type") in ("error", "turn.failed") for event in events)):
        raise ValueError("native proposal has no successful terminal event")
    if any(event.get("type") in ("item.started", "item.completed")
           and (not isinstance(event.get("item"), dict)
                or event["item"].get("type") not in ("agent_message", "reasoning")) for event in events):
        raise ValueError("native proposer attempted a tool action; no controller execution")
    messages = [event["item"]["text"] for event in events if event.get("type") == "item.completed"
                and event.get("item", {}).get("type") == "agent_message"]
    if not messages:
        raise ValueError("native proposal missing final JSON")
    proposal = json.loads(messages[-1], object_pairs_hook=_unique_json)
    return proposal, {"transport_exit": result.returncode, "terminal_event": events[-1]["type"],
                      "events_digest": digest(result.stdout.encode()),
                      "proposal_digest": digest(messages[-1].encode()),
                      "role": "untrusted action proposal; never acceptance evidence"}


def discovery_inputs(proposal: dict) -> list[str]:
    if (not isinstance(proposal, dict) or set(proposal) != {"inputs"}
            or not isinstance(proposal["inputs"], list)
            or not 1 <= len(proposal["inputs"]) <= 12
            or any(not isinstance(value, str) or "\0" in value or len(value.encode()) > 64
                   for value in proposal["inputs"])):
        raise ValueError("discovery requires only 1-12 input strings, at most 64 UTF-8 bytes each")
    if len(set(proposal["inputs"])) != len(proposal["inputs"]):
        raise ValueError("duplicate discovered inputs")
    return proposal["inputs"]


def native_discovery(requirements: str) -> tuple[list[str], dict]:
    prompt = (
        "Design black-box acceptance probes from the synthetic requirements below. "
        "The CLI takes exactly one string argument and prints a classification. "
        "Choose at most 12 distinct inputs to expose plausible behavioral defects, "
        "including boundaries and invalid inputs. Each input is at most 64 UTF-8 bytes, "
        "without NUL. Return ONLY JSON of the form {\"inputs\":[\"...\"]}. "
        "Do not add expected outputs, verdicts or other fields. Do not execute tools "
        "or read source, files, credentials, configuration or network. "
        "An independent controller executes your probes against an approved oracle.\n"
        "Requirements:\n" + requirements)
    proposal, record = _native_json(prompt)
    return discovery_inputs(proposal), record


def range_oracle(policy: dict, value: str) -> dict:
    if re.fullmatch(r"[+-]?[0-9]+", value) is None:
        output = policy["invalid"]
    else:
        output = (policy["inside"] if policy["minimum"] <= int(value) <= policy["maximum"]
                  else policy["outside"])
    return {"exit_code": 0, "stdout": output + "\n", "stderr": ""}


def load_discovery_corpus(path: Path, approval: str) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1048576:
        raise ValueError("discovery corpus must be a bounded regular file")
    content = path.read_bytes()
    if len(content) > 1048576 or digest(content) != approval:
        raise ValueError("discovery corpus differs from approved digest")
    corpus = json.loads(content, object_pairs_hook=_unique_json)
    if (not isinstance(corpus, dict) or set(corpus) != {"schema_version", "suites"}
            or type(corpus["schema_version"]) is not int or corpus["schema_version"] != 1
            or not isinstance(corpus["suites"], list) or not 1 <= len(corpus["suites"]) <= 8):
        raise ValueError("invalid discovery corpus")
    names: set[str] = set()
    for suite in corpus["suites"]:
        if (not isinstance(suite, dict) or set(suite) != {"id", "requirements", "oracle", "cases"}
                or not isinstance(suite["id"], str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,39}", suite["id"])
                or suite["id"] in names or not isinstance(suite["requirements"], str)
                or not 1 <= len(suite["requirements"].encode()) <= 8192):
            raise ValueError("invalid discovery suite identity or requirements")
        names.add(suite["id"])
        policy = suite["oracle"]
        if (not isinstance(policy, dict)
                or set(policy) != {"minimum", "maximum", "inside", "outside", "invalid"}
                or any(type(policy[key]) is not int or abs(policy[key]) > 10**9
                       for key in ("minimum", "maximum"))
                or policy["minimum"] > policy["maximum"]
                or any(not isinstance(policy[key], str)
                       or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,31}", policy[key])
                       for key in ("inside", "outside", "invalid"))
                or len({policy[key] for key in ("inside", "outside", "invalid")}) != 3):
            raise ValueError("invalid independent range oracle")
        cases = suite["cases"]
        if not isinstance(cases, list) or not 2 <= len(cases) <= 12:
            raise ValueError("discovery needs 2-12 product variants")
        case_ids: set[str] = set()
        for case in cases:
            if (not isinstance(case, dict) or set(case) != {"id", "source", "expected_state"}
                    or not isinstance(case["id"], str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,39}", case["id"])
                    or case["id"] in case_ids or not isinstance(case["source"], str)
                    or not 1 <= len(case["source"].encode()) <= 16384
                    or case["expected_state"] not in ("pass", "violation", "unknown")):
                raise ValueError("invalid discovery product variant")
            case_ids.add(case["id"])
        if not {"pass", "violation"} <= {case["expected_state"] for case in cases}:
            raise ValueError("discovery suite needs healthy and defective controls")
    return corpus


def discovery_metrics(cases: list[dict]) -> dict:
    return {
        "cases": len(cases),
        "matched": sum(case["state"] == case["expected_state"] for case in cases),
        "defects": sum(case["expected_state"] == "violation" for case in cases),
        "discovered": sum(case["expected_state"] == "violation" and case["state"] == "violation" for case in cases),
        "missed_defects": sum(case["expected_state"] == "violation" and case["state"] != "violation" for case in cases),
        "false_passes": sum(case["state"] == "pass" and case["expected_state"] != "pass" for case in cases),
        "false_alarms": sum(case["state"] == "violation" and case["expected_state"] == "pass" for case in cases),
        "blocked": sum(case["state"] == "unknown" for case in cases),
    }


def _discovery_case(python: str, runtime: str, root: Path, environment: dict,
                    suite: dict, case: dict, inputs: list[str]) -> dict:
    root.mkdir()
    for arguments in (["init", "-b", "main"], ["config", "user.name", "UAT fixture"],
                      ["config", "user.email", "uat@example.invalid"]):
        invoke(["git", *arguments], root, environment).check_returncode()
    (root / "app.py").write_text(case["source"])
    (root / "specs").mkdir()
    spec = ("---\nfettle-spec: v1\nid: classifier\nstatus: active\nscope:\n"
            "  - \"app.py\"\n---\n\n## Requirements\n\n"
            "- R1. Classify each input according to the independently approved range policy.\n\n## Scenarios\n")
    for index in range(len(inputs)):
        spec += (f"\n### S{index + 1}. Discovered probe {index + 1} (traces R1)\n\n"
                 "- Given the classifier is installed\n"
                 f"- When the user supplies discovered input {index + 1}\n"
                 "- Then the output matches the independently approved classification\n")
    (root / "specs/classifier.md").write_text(spec)
    invoke(["git", "add", "."], root, environment).check_returncode()
    invoke(["git", "commit", "-m", "fixture"], root, environment).check_returncode()
    scenario = invoke([python, "-I", "-c", "from fettle.uat.session import collect_scenarios,_digest; "
                       "print(_digest(collect_scenarios('.')))"], root, environment)
    scenario.check_returncode()
    contract = {"schema_version": 1, "scenario_digest": scenario.stdout.strip(), "actions": [
        {"scenario_id": f"classifier/S{index + 1}", "argv": [runtime, "-I", str(root / "app.py"), value],
         "timeout_s": 2, "expect": range_oracle(suite["oracle"], value)}
        for index, value in enumerate(inputs)]}
    contract_path = root / "contract.json"
    contract_path.write_text(json.dumps(contract))
    arguments = ["--contract", str(contract_path), "--approve-contract", digest(contract_path.read_bytes())]
    doctor = invoke([python, "-I", "-m", "fettle", "uat", "doctor", *arguments], root, environment)
    run = invoke([python, "-I", "-m", "fettle", "uat", "run", *arguments, "--yes", "--json"], root, environment)
    report = invoke([python, "-I", "-m", "fettle", "uat", "report", "--worktree", str(root), "--json"], root, environment)
    response = json.loads(run.stdout)
    replay = json.loads(report.stdout)
    validation = invoke([python, "-I", "-c", "import json; from pathlib import Path; "
                         "from fettle.uat.reconcile import validate_canonical_evidence; "
                         "result=validate_canonical_evidence('.',json.loads(Path('.fettle/uat-report.json').read_text())); "
                         "print(json.dumps({'validity':result.validity.value,'state':result.result_state.value}))"],
                        root, environment)
    validation.check_returncode()
    canonical = json.loads(validation.stdout)
    receipt = Path(environment["HOME"]) / ".local/state/fettle/uat-capture" / (response["session_id"] + ".json")
    observations = json.loads(receipt.read_bytes())["observations"] if receipt.is_file() else []
    state = canonical["state"]
    expected_exit = 0 if state == "pass" else 1
    consistent = (doctor.returncode == 0 and run.returncode == report.returncode == expected_exit
                  and response["acceptance_complete"] == replay["acceptance_complete"] == (state == "pass")
                  and len(observations) == len(inputs) and canonical["validity"] == "valid")
    return {"suite": suite["id"], "case": case["id"], "expected_state": case["expected_state"],
            "state": state if consistent else "unknown", "canonical": canonical,
            "consistent": consistent, "observations": observations,
            "contract_digest": digest(contract_path.read_bytes())}


def qualify_discovery(python: str, wheel: Path, corpus: dict, record: dict, output: Path) -> dict:
    cases: list[dict] = []
    proposals: list[dict] = []
    record.update(cases=cases, proposals=proposals)
    with tempfile.TemporaryDirectory(prefix="fettle-native-discovery-") as temporary:
        base = Path(temporary)
        home = base / "controller-home"
        home.mkdir()
        environment = {"PATH": os.environ["PATH"], "HOME": str(home), "TMPDIR": str(base)}
        origin = invoke([python, "-I", "-c", "import json,sys,hashlib; from pathlib import Path; import fettle; "
                         "root=Path(fettle.__file__).parent; assert root.is_relative_to(sys.prefix); "
                         "print(json.dumps({'runtime':str(Path(sys.executable).resolve()),'files':"
                         "{str(path.relative_to(root.parent)):hashlib.sha256(path.read_bytes()).hexdigest() "
                         "for path in root.rglob('*.py')}}))"], base, environment)
        origin.check_returncode()
        identity = json.loads(origin.stdout)
        with zipfile.ZipFile(wheel) as archive:
            expected = {name: hashlib.sha256(archive.read(name)).hexdigest()
                        for name in archive.namelist() if name.startswith("fettle/") and name.endswith(".py")}
        if not expected or expected != identity["files"]:
            raise ValueError("installed package does not match candidate wheel")
        for suite in corpus["suites"]:
            inputs, native = native_discovery(suite["requirements"])
            proposals.append({"suite": suite["id"], "inputs": inputs, "native": native})
            output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
            for case in suite["cases"]:
                cases.append(_discovery_case(python, identity["runtime"], base / (suite["id"] + "-" + case["id"]),
                                             environment, suite, case, inputs))
                output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    metrics = discovery_metrics(cases)
    return {"schema_version": 1, "recorded_at": datetime.now(UTC).isoformat(),
            "wheel_digest": digest(wheel.read_bytes()), "proposals": proposals, "cases": cases,
            "metrics": metrics, "passed": bool(cases) and metrics["matched"] == metrics["cases"]
            and all(case["consistent"] for case in cases), "graduation_passed": False,
            "limits": ["synthetic integer-range CLI input discovery only; not adaptive exploration",
                       "independently supplied approved policy is the oracle, never agent prose",
                       "sanitized retained observations are not portable canonical authority",
                       "no human parity, broad UAT completion or permission-enforcement promotion"]}


def qualify(python: str, wheel: Path, native: bool = False) -> dict:
    results = []
    identity: dict = {}
    with tempfile.TemporaryDirectory(prefix="fettle-installed-uat-") as temporary:
        base = Path(temporary)
        home = base / "controller-home"
        home.mkdir()
        environment = {"PATH": os.environ["PATH"], "HOME": str(home), "TMPDIR": str(base)}
        origin = invoke([python, "-I", "-c",
                         "import json,sys,hashlib; from pathlib import Path; "
                         "import fettle.uat.controller as module; "
                         "path=Path(module.__file__); "
                         "assert path.is_relative_to(sys.prefix); "
                         "print(json.dumps({'installed':True,'python':sys.version.split()[0],"
                         "'controller_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),"
                         "'executable':str(Path(sys.executable).resolve())}))"], base, environment)
        if origin.returncode:
            raise RuntimeError("isolated installed-controller import failed: " + origin.stderr)
        identity = json.loads(origin.stdout)
        runtime = identity.pop("executable")
        for case in ("success", "seeded-defect", "write-denied"):
            root = base / case
            root.mkdir()
            for arguments in (["init", "-b", "main"], ["config", "user.name", "UAT fixture"],
                              ["config", "user.email", "uat@example.invalid"]):
                initialized = invoke(["git", *arguments], root, environment)
                if initialized.returncode:
                    raise RuntimeError(initialized.stderr)
            (root / "specs").mkdir()
            (root / "specs" / "greeter.md").write_text(SPEC)
            code = "import sys\nprint('Hello, ' + sys.argv[1])\n"
            if case == "seeded-defect":
                code = "print('Hello, wrong person')\n"
            if case == "write-denied":
                code = "open('unexpected-write', 'w').write('bad')\nprint('Hello, Ada')\n"
            (root / "app.py").write_text(code)
            invoke(["git", "add", "."], root, environment).check_returncode()
            invoke(["git", "commit", "-m", "fixture"], root, environment).check_returncode()
            scenario = invoke([python, "-I", "-c",
                               "from fettle.uat.session import collect_scenarios,_digest; "
                               "print(_digest(collect_scenarios('.')))"], root, environment)
            scenario.check_returncode()
            contract = {
                "schema_version": 1, "scenario_digest": scenario.stdout.strip(),
                "actions": [{"scenario_id": "greeter/S1",
                             "argv": [runtime, "-I", str(root / "app.py"), "Ada"],
                             "timeout_s": 3,
                             "expect": {"exit_code": 0, "stdout": "Hello, Ada\n", "stderr": ""}}],
            }
            path = root / "contract.json"
            path.write_text(json.dumps(contract))
            approval = digest(path.read_bytes())
            arguments = ["--contract", str(path), "--approve-contract", approval]
            doctor = invoke([python, "-I", "-m", "fettle", "uat", "doctor", *arguments], root, environment)
            native_record: dict = {}
            if native:
                proposed_actions = {"schema_version": 1, "scenario_digest": contract["scenario_digest"],
                                    "actions": [{key: value for key, value in action.items() if key != "expect"}
                                                for action in contract["actions"]]}
                proposal, native_record = native_proposal(proposed_actions)
                proposal_path = base / (case + "-proposal.json")
                proposal_path.write_text(json.dumps(proposal))
                bad_path = base / (case + "-injected.json")
                bad = json.loads(json.dumps(proposal))
                bad["actions"][0]["expect"] = {"exit_code": 0, "stdout": "invented", "stderr": ""}
                bad_path.write_text(json.dumps(bad))
                rejected = invoke([python, "-I", "-m", "fettle", "uat", "run", *arguments,
                                   "--proposal", str(bad_path), "--yes", "--json"], root, environment)
                rejected_json = json.loads(rejected.stdout)
                native_record["oracle_injection_rejected"] = (
                    rejected.returncode == 1 and not rejected_json["session_id"]
                    and not rejected_json["acceptance_complete"])
                arguments += ["--proposal", str(proposal_path)]
            run = invoke([python, "-I", "-m", "fettle", "uat", "run", *arguments, "--yes", "--json"], root, environment)
            replay = invoke([python, "-I", "-m", "fettle", "uat", "report", "--worktree", str(root), "--json"], root, environment)
            response = json.loads(run.stdout)
            report = json.loads(replay.stdout)
            validation = invoke([python, "-I", "-c",
                                 "import json; from pathlib import Path; "
                                 "from fettle.uat.reconcile import validate_canonical_evidence; "
                                 "report=json.loads(Path('.fettle/uat-report.json').read_text()); "
                                 "result=validate_canonical_evidence('.',report); "
                                 "print(json.dumps({'validity':result.validity.value,'state':result.result_state.value}))"], root, environment)
            validation.check_returncode()
            canonical = json.loads(validation.stdout)
            receipt_path = home / ".local/state/fettle/uat-capture" / (response["session_id"] + ".json")
            observation = json.loads(receipt_path.read_bytes())["observations"][0]
            forged = json.loads((root / ".fettle/uat-report.json").read_text())
            forged["verdicts"][0]["observed"] = "forged independent observation"
            (root / ".fettle/uat-report.json").write_text(json.dumps(forged))
            rejection = invoke([python, "-I", "-c",
                                "import json; from pathlib import Path; "
                                "from fettle.uat.reconcile import validate_canonical_evidence; "
                                "report=json.loads(Path('.fettle/uat-report.json').read_text()); "
                                "print(validate_canonical_evidence('.',report).result_state.value)"], root, environment)
            rejection.check_returncode()
            expected_success = case == "success"
            passed = (doctor.returncode == 0 and run.returncode == (0 if expected_success else 1)
                      and replay.returncode == run.returncode
                      and response["acceptance_complete"] == expected_success
                      and report["acceptance_complete"] == expected_success
                      and (canonical["state"] == "pass") == expected_success
                      and rejection.stdout.strip() != "pass"
                      and (not native or native_record.get("oracle_injection_rejected") is True)
                      and not (root / "unexpected-write").exists())
            results.append({"case": case, "passed": passed, "doctor_exit": doctor.returncode,
                            "run_exit": run.returncode, "report_exit": replay.returncode,
                            "canonical": canonical, "forged_report_state": rejection.stdout.strip(),
                            "native_proposal": native_record,
                            "observation": observation, "scenario_digest": contract["scenario_digest"]})
    return {"schema_version": 1, "recorded_at": datetime.now(UTC).isoformat(),
            "platform": platform.platform(), "wheel_digest": digest(wheel.read_bytes()),
            "installed_identity": identity, "cases": results,
            "passed": all(result["passed"] for result in results),
            "limits": ["macOS read-only CLI only", "trusted controller and system runtime",
                       "no unrestricted same-user explorer", "not human parity or enforcement graduation"]}


NETWORK_APP = """
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
import time
state=Path('/state/value')
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path=='/form':
            body=b'<html lang="en"><title>Greeting</title><main><form method="post"><label>Name<input name="name"></label><button>Greet</button></form></main></html>'
        elif self.path=='/state':
            body=(state.read_text() if state.exists() else 'missing').encode()
        else:
            body=b'Hello, Ada'
        self.send_response(200)
        self.end_headers()
        self.wfile.write(body)
    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length','0')))
        state.write_text('Ada')
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'<html lang="en"><title>Result</title><main><p role="status">Hello, Ada</p></main></html>')
HTTPServer(('0.0.0.0',8080),Handler).serve_forever()
"""

NETWORK_CASES = (
    ("api-success", "api", "pass"), ("api-wrong-body", "api", "violation"),
    ("api-server-error", "api", "violation"), ("api-redirect", "api", "violation"),
    ("api-overflow", "api", "unknown"), ("api-timeout", "api", "unknown"),
    ("state-restart", "api", "pass"), ("state-loss", "api", "violation"),
    ("web-desktop", "web", "pass"), ("web-mobile", "web", "pass"),
    ("web-wrong-body", "web", "violation"), ("web-missing-control", "web", "unknown"),
)


def qualify_network(python: str, wheel: Path, seccomp_source: Path, heldout: Path | None = None) -> dict:
    corpus = None
    if heldout is not None:
        content = heldout.read_bytes()
        if hashlib.sha256(content).hexdigest() != "c0109c3d8994fc9028cf955c2cc2857bff724f321c184215111bfd4570db484f":
            raise ValueError("held-out corpus differs from independently frozen identity")
        corpus = json.loads(content)
    network_cases = (tuple((case["seed_id"], "api", case["expected_state"]) for case in corpus["cases"])
                     if corpus else NETWORK_CASES)
    manifest = [{"id": name, "surface": surface, "expected_state": state}
                for name, surface, state in network_cases]
    cases = []
    calibration_runs = []
    with tempfile.TemporaryDirectory(prefix="fettle-installed-network-") as temporary:
        base = Path(temporary)
        environment = {"PATH": os.environ["PATH"], "HOME": str(base / "controller-home"),
                       "DOCKER_CONFIG": str(Path.home() / ".docker"), "TMPDIR": str(base)}
        identity_result = invoke([python, "-I", "-c",
                                  "import json,sys; from pathlib import Path; "
                                  "from fettle.uat import network_controller as module; "
                                  "assert Path(module.__file__).is_relative_to(sys.prefix); "
                                  "print(json.dumps({'image':module.IMAGE,'browser':module.BROWSER_IMAGE}))"],
                                 base, environment)
        identity_result.check_returncode()
        identity = json.loads(identity_result.stdout)
        content = seccomp_source.read_bytes()
        if hashlib.sha256(content).hexdigest() != "cc3e61cabda6bbc1e53e54d27ba4d55a9d3be829b6dd1a596f4a7b31b1cc7849":
            raise ValueError("unexpected upstream seccomp source")
        profile = json.loads(content)
        profile["syscalls"].append({"names": ["chroot"], "action": "SCMP_ACT_ALLOW"})
        profile_path = base / "browser-seccomp.json"
        profile_path.write_text(json.dumps(profile, sort_keys=True))
        for case_index, (name, surface, expected_state) in enumerate(network_cases):
            frozen = corpus["cases"][case_index] if corpus else None
            root = base / name
            root.mkdir()
            for arguments in (["init", "-b", "main"], ["config", "user.name", "UAT fixture"],
                              ["config", "user.email", "uat@example.invalid"]):
                invoke(["git", *arguments], root, environment).check_returncode()
            (root / "specs").mkdir()
            (root / "specs/greeter.md").write_text(SPEC)
            code = NETWORK_APP
            if frozen:
                code = frozen["app_source"]
                (root / "specs/greeter.md").write_text(SPEC.replace("Hello, Ada", frozen["requirement"]))
            if name.endswith("wrong-body"):
                code = code.replace("Hello, Ada", "wrong output")
            if name == "api-server-error":
                code = code.replace("send_response(200)", "send_response(500)")
            if name == "api-redirect":
                code = code.replace("send_response(200)", "send_response(302)")
            if name == "api-overflow":
                code = code.replace("body=b'Hello, Ada'", "body=b'x'*65537")
            if name == "api-timeout":
                code = code.replace("self.send_response(200)", "time.sleep(10); self.send_response(200)")
            if name == "state-loss":
                code = code.replace("class Handler", "state.unlink(missing_ok=True)\nclass Handler")
            if name == "web-missing-control":
                code = code.replace("<button>Greet</button>", "<button>Other</button>")
            (root / "app.py").write_text(code)
            invoke(["git", "add", "."], root, environment).check_returncode()
            invoke(["git", "commit", "-m", "fixture"], root, environment).check_returncode()
            scenario = invoke([python, "-I", "-c", "from fettle.uat.session import collect_scenarios,_digest; "
                               "print(_digest(collect_scenarios('.')))"], root, environment)
            scenario.check_returncode()
            steps: list[dict] = [{"method": "GET", "path": "/", "body": "",
                      "expect": {"status_code": 200, "body": "Hello, Ada"}}]
            if name.startswith("state-"):
                post_body = '<html lang="en"><title>Result</title><main><p role="status">Hello, Ada</p></main></html>'
                steps = [{"method": "POST", "path": "/", "body": "",
                          "expect": {"status_code": 200, "body": post_body}},
                         {"restart": True}, {"method": "GET", "path": "/state", "body": "",
                                             "expect": {"status_code": 200, "body": "Ada"}}]
            if surface == "web":
                steps = [{"op": "goto", "path": "/form"}, {"op": "fill", "label": "Name", "value": "Ada"},
                         {"op": "click", "role": "button", "name": "Greet"},
                         {"op": "text", "role": "status", "name": "", "expect": "Hello, Ada"}]
            if frozen:
                steps = frozen["steps"]
            contract = {"schema_version": 2, "surface": surface, "runtime_image": identity["image"],
                        "context": "colima-fettle-uat", "product": {"argv": ["/product/app.py"], "port": 8080},
                        "scenario_digest": scenario.stdout.strip(),
                        "actions": [{"scenario_id": "greeter/S1", "timeout_s": 60 if frozen else 5, "steps": steps}]}
            if surface == "web":
                contract["browser"] = {"image": identity["browser"], "seccomp_path": str(profile_path),
                                       "viewport": {"width": 375 if name == "web-mobile" else 1280, "height": 720}}
            path = root / "contract.json"
            path.write_text(json.dumps(contract))
            approval = digest(path.read_bytes())
            arguments = ["--contract", str(path), "--approve-contract", approval]
            doctor = invoke([python, "-I", "-m", "fettle", "uat", "doctor", *arguments, "--json"], root, environment)
            run = invoke([python, "-I", "-m", "fettle", "uat", "run", "--surface", surface,
                          *arguments, "--yes", "--json"], root, environment)
            replay = invoke([python, "-I", "-m", "fettle", "uat", "report", "--worktree", str(root), "--json"], root, environment)
            response, report = json.loads(run.stdout), json.loads(replay.stdout)
            check = invoke([python, "-I", "-c", "import json; from pathlib import Path; "
                            "from fettle.uat.reconcile import validate_canonical_evidence; "
                            "report=json.loads(Path('.fettle/uat-report.json').read_text()); "
                            "print(validate_canonical_evidence('.',report).result_state.value)"], root, environment)
            check.check_returncode()
            receipt = Path(environment["HOME"]) / ".local/state/fettle/uat-capture" / (response["session_id"] + ".json")
            observations = json.loads(receipt.read_bytes())["observations"] if receipt.is_file() else []
            state = check.stdout.strip()
            passed = (doctor.returncode == 0 and state == expected_state
                      and run.returncode == replay.returncode == (0 if expected_state == "pass" else 1)
                      and response["acceptance_complete"] == report["acceptance_complete"] == (expected_state == "pass")
                      and len(observations) == 1)
            cases.append({"id": name, "surface": surface, "expected_state": expected_state,
                          "state": state, "passed": passed, "doctor_exit": doctor.returncode,
                          "run_exit": run.returncode, "report_exit": replay.returncode,
                          "observations": observations, "contract_digest": approval})
            calibration_runs.append({"seed_id": name, "product_root": str(root),
                                     "report_digest": digest((root / ".fettle/uat-report.json").read_bytes())})
        manifest_payload = {"seeds": manifest, "discovery_threshold": None}
        manifest_path = base / "calibration-manifest.json"
        manifest_path.write_text(json.dumps(manifest_payload))
        manifest_digest = digest(json.dumps(manifest_payload, ensure_ascii=False, sort_keys=True,
                                           separators=(",", ":"), allow_nan=False).encode())
        evidence_path = base / "calibration-evidence.json"
        evidence_path.write_text(json.dumps({"schema_version": 2, "manifest_digest": manifest_digest,
                                            "runs": calibration_runs}))
        calibration_result = invoke([python, "-I", "-m", "fettle", "uat", "benchmark",
                                     "--manifest", str(manifest_path), "--evidence", str(evidence_path), "--json"],
                                    root, environment)
        calibration = json.loads(calibration_result.stdout)
        if not corpus and (calibration_result.returncode != 1 or not calibration.get("expected_states_matched")):
            raise RuntimeError("canonical calibration failed: " + calibration_result.stdout + calibration_result.stderr)
    defects = [case for case in cases if case["expected_state"] == "violation"]
    return {"schema_version": 1, "recorded_at": datetime.now(UTC).isoformat(),
            "wheel_digest": digest(wheel.read_bytes()), "runtime": identity,
            "manifest": manifest, "manifest_digest": digest(json.dumps(manifest, sort_keys=True).encode()),
            "cases": cases, "passed": all(case["passed"] for case in cases) and (
                not corpus or calibration.get("calibration_passed") is True),
            "heldout_corpus_digest": digest(heldout.read_bytes()) if heldout else None,
            "heldout_criteria": corpus["criteria"] if corpus else None,
            "canonical_calibration": calibration,
            "metrics": {"cases": len(cases), "matched_expected_states": sum(case["passed"] for case in cases),
                        "false_passes": sum(case["state"] == "pass" and case["expected_state"] != "pass" for case in cases),
                        "seeded_defects": len(defects), "contradicted_defects": sum(case["state"] == "violation" for case in defects),
                        "observed_scenarios": sum(bool(case["observations"]) for case in cases)},
            "limits": ["local installed deterministic controller qualification, not agent discovery",
                       "independently authored frozen API corpus; no tuning or retries" if corpus else
                       "fixture manifest frozen before execution; not an independently held-out parity study",
                       "no human baseline, native explorer qualification or enforcement graduation",
                       "sanitized observations are reproducibility evidence, not portable authority"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", required=True)
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--network-seccomp-source", type=Path)
    parser.add_argument("--heldout-corpus", type=Path)
    parser.add_argument("--native-proposals", action="store_true")
    parser.add_argument("--native-discovery-corpus", type=Path)
    parser.add_argument("--approve-discovery-corpus")
    arguments = parser.parse_args()
    if arguments.native_discovery_corpus:
        if arguments.native_proposals or arguments.network_seccomp_source or arguments.heldout_corpus:
            parser.error("discovery is a separate sequential study")
        corpus = load_discovery_corpus(arguments.native_discovery_corpus, arguments.approve_discovery_corpus)
        record = {"passed": False, "status": "started", "corpus_digest": digest(arguments.native_discovery_corpus.read_bytes()),
                  "wheel_digest": digest(arguments.wheel.read_bytes()),
                  "evaluator_digest": digest(Path(__file__).read_bytes())}
        with arguments.output.open("x") as handle:
            handle.write(json.dumps(record) + "\n")
        try:
            result = qualify_discovery(str(Path(arguments.python).absolute()), arguments.wheel, corpus,
                                       record, arguments.output)
            record.update(result)
            record["status"] = "completed"
        except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as error:
            record.update(status="blocked", error_type=type(error).__name__,
                          recovery="Preserve this non-pass trial. Inspect runtime and approved corpus; "
                          "do not retry a consumed held-out study or treat partial cases as acceptance.")
        arguments.output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
        print(json.dumps(record, indent=2))
        raise SystemExit(0 if record["passed"] else 1)
    if arguments.approve_discovery_corpus:
        parser.error("--approve-discovery-corpus requires --native-discovery-corpus")
    if arguments.native_proposals and arguments.network_seccomp_source:
        parser.error("native proposal qualification currently uses the CLI controller fixtures")
    if arguments.heldout_corpus and not arguments.network_seccomp_source:
        parser.error("held-out qualification requires the isolated network runtime")
    if arguments.heldout_corpus and arguments.output.exists():
        parser.error("held-out output already exists; preserve the original trial instead of rerunning")
    python = str(Path(arguments.python).absolute())
    result = (qualify_network(python, arguments.wheel, arguments.network_seccomp_source, arguments.heldout_corpus)
              if arguments.network_seccomp_source else qualify(python, arguments.wheel, arguments.native_proposals))
    arguments.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()