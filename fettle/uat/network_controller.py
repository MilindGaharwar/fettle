"""Bounded API observations from a separate, isolated trusted runtime."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from fettle.uat.session import _digest, _file_digest, _redact_secrets

MODE = "isolated-api-v1"
IMAGE = "docker.io/library/python@sha256:c4634f578a412db396771b61b064c6e546c9d6414c7fb5b1b05d5871f1885f7b"
BROWSER_IMAGE = "sha256:0b5a9b1dd96db0948671a77d0dee1fd17653c51c7bfc8133a6e6f343164e8e54"
BROWSER_PROFILE = "fe3f122e31547eebf303b60472c5a08db0f8d1d53e576d3881d2a68a76878b8c"
LIMIT = 65536
SOURCE_LIMIT = 16 * 1048576
OPTIONS = ["--read-only", "--user", "65534:65534", "--cap-drop", "ALL",
           "--security-opt", "no-new-privileges:true", "--pids-limit", "64",
           "--memory", "128m", "--memory-swap", "128m", "--cpus", "1",
           "--dns", "127.0.0.1", "--log-driver", "none", "--pull", "never",
           "--entrypoint", "/usr/local/bin/python3"]

SEED = """
import base64,json,pathlib,sys
for name,encoded in json.load(sys.stdin).items():
    path=pathlib.Path('/source')/name
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(base64.b64decode(encoded,validate=True))
    path.chmod(0o444)
"""

COLLECT = """
import http.client,json,socket,sys,time
payload=json.load(sys.stdin)
deadline=time.monotonic()+payload['timeout_s']
while True:
    try:
        with socket.create_connection(('product',payload['port']),timeout=1):
            break
    except OSError:
        if time.monotonic()>=deadline:
            raise RuntimeError('product readiness timed out')
        time.sleep(0.05)
observations=[]
for step in payload['steps']:
    remaining=deadline-time.monotonic()
    if remaining<=0:
        raise RuntimeError('scenario timed out')
    connection=http.client.HTTPConnection('product',payload['port'],timeout=remaining)
    connection.request(step['method'],step['path'],body=step['body'].encode('utf-8'),
                       headers={'Content-Type':'application/json'})
    response=connection.getresponse()
    body=response.read(65537)
    if len(body)>65536:
        raise RuntimeError('response output limit exceeded')
    observations.append({'status_code':response.status,'body':body.decode('utf-8')})
    connection.close()
print(json.dumps(observations,sort_keys=True,separators=(',',':')))
"""

BROWSE = r"""
import base64,hashlib,json,pathlib,socket,sys,time
from playwright.sync_api import sync_playwright
payload=json.load(sys.stdin)
observations=[]
artifacts=[]
sensitive=[]
events={name:[] for name in ('page_errors','console_errors','failed_requests','http_errors')}
def record(kind,value):
    if len(events[kind])>=100 or len(str(value).encode())>4096:
        raise RuntimeError('browser diagnostics exceed capture budget')
    events[kind].append(value)
deadline=time.monotonic()+payload['timeout_s']
while True:
    try:
        with socket.create_connection(('product',payload['port']),timeout=1):
            break
    except OSError:
        if time.monotonic()>=deadline:
            raise RuntimeError('product readiness timed out')
        time.sleep(0.05)
with sync_playwright() as runtime:
    browser=runtime.chromium.launch(headless=True,chromium_sandbox=True)
    context=browser.new_context(service_workers='block',accept_downloads=False,
                                viewport=payload['viewport'])
    page=context.new_page()
    page.on('pageerror',lambda error:record('page_errors',str(error)))
    page.on('console',lambda message:record('console_errors',message.text) if message.type=='error' else None)
    page.on('requestfailed',lambda request:record('failed_requests',request.url))
    page.on('response',lambda response:record('http_errors',{'url':response.url,'status':response.status})
            if response.status>=400 else None)
    page.set_default_timeout(payload['timeout_s']*1000)
    base='http://product:'+str(payload['port'])
    context.route('**/*',lambda route: route.continue_() if route.request.url.startswith(base+'/') else route.abort())
    for step in payload['steps']:
        remaining=deadline-time.monotonic()
        if remaining<=0:
            raise RuntimeError('browser scenario timed out')
        page.set_default_timeout(remaining*1000)
        operation=step['op']
        if operation=='goto':
            page.goto(base+step['path'],wait_until='domcontentloaded')
        elif operation=='fill':
            page.get_by_label(step['label'],exact=True).fill(step['value'])
        elif operation=='click':
            page.get_by_role(step['role'],name=step['name'],exact=True).click()
        elif operation=='text':
            text=page.get_by_role(step['role'],name=step['name'],exact=True).inner_text()
            if len(text.encode())>65536:
                raise RuntimeError('browser output exceeds limit')
            observations.append({'text':text})
        elif operation=='audit':
            page.wait_for_load_state('networkidle')
            if len(page.frames)!=1:
                raise RuntimeError('audit requires a single frame; frame coverage unavailable')
            protocol=context.new_cdp_session(page)
            frame=protocol.send('Page.getFrameTree')['frameTree']['frame']['id']
            world=protocol.send('Page.createIsolatedWorld',{'frameId':frame,'worldName':'fettle-audit'})
            def evaluate(expression):
                result=protocol.send('Runtime.evaluate',{'expression':expression,
                    'contextId':world['executionContextId'],'returnByValue':True,'awaitPromise':True})
                if 'exceptionDetails' in result:
                    raise RuntimeError('isolated accessibility collection failed')
                return result['result'].get('value')
            source=pathlib.Path('/opt/fettle-axe/axe.min.js').read_text()
            evaluate(source)
            audit=evaluate("axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']}}).then(result=>({accessibility_violations:result.violations.map(item=>item.id).sort(),accessibility_incomplete:result.incomplete.map(item=>item.id).sort()}))")
            visible=evaluate("document.body.innerText+'\\n'+Array.from(document.querySelectorAll('input,textarea')).map(item=>item.value).join('\\n')")
            if not isinstance(visible,str) or len(visible.encode())>65536:
                raise RuntimeError('visible text exceeds secret-screening budget')
            sensitive.append(visible)
            screenshot=page.screenshot(type='png',full_page=False,animations='disabled',timeout=max(1,int((deadline-time.monotonic())*1000)))
            if len(screenshot)>524288:
                raise RuntimeError('screenshot exceeds capture budget')
            artifacts.append({'kind':'viewport-png','sha256':hashlib.sha256(screenshot).hexdigest(),
                              'data':base64.b64encode(screenshot).decode()})
            observations.append({'audit':{**events,**audit}})
            protocol.detach()
    browser.close()
print(json.dumps({'observations':observations,'artifacts':artifacts,'sensitive':sensitive},sort_keys=True,separators=(',',':')))
"""

AUDIT_EXPECTATION: dict[str, list] = {name: [] for name in ("page_errors", "console_errors", "failed_requests", "http_errors",
                                          "accessibility_violations", "accessibility_incomplete")}


def validate_artifacts(contract: dict, action: dict, observed: dict) -> None:
    artifacts = observed.get("artifacts")
    count = sum(step.get("op") == "audit" for step in action["steps"])
    if (not isinstance(artifacts, list) or len(artifacts) != (0 if observed["error"] else count)):
        raise ValueError("browser artifact coverage is incomplete")
    for artifact in artifacts:
        if (not isinstance(artifact, dict) or set(artifact) != {"kind", "sha256", "data"}
                or artifact["kind"] != "viewport-png" or not isinstance(artifact["data"], str)
                or len(artifact["data"]) > 700000):
            raise ValueError("invalid bounded screenshot")
        image = base64.b64decode(artifact["data"], validate=True)
        viewport = contract["browser"]["viewport"]
        if (len(image) > 524288 or not image.startswith(b"\x89PNG\r\n\x1a\n")
                or image[12:16] != b"IHDR"
                or int.from_bytes(image[16:20], "big") != viewport["width"]
                or int.from_bytes(image[20:24], "big") != viewport["height"]
                or hashlib.sha256(image).hexdigest() != artifact["sha256"]):
            raise ValueError("screenshot identity or viewport differs from capture")


def _browser_settings(contract: dict) -> dict:
    browser = contract.get("browser")
    if (not isinstance(browser, dict) or set(browser) != {"image", "seccomp_path", "viewport"}
            or browser["image"] != BROWSER_IMAGE or not isinstance(browser["seccomp_path"], str)):
        raise ValueError("browser requires the qualified pinned image and seccomp profile")
    profile = Path(browser["seccomp_path"])
    if (not profile.is_absolute() or not profile.is_file() or profile.stat().st_size > 1048576
            or hashlib.sha256(profile.read_bytes()).hexdigest() != BROWSER_PROFILE):
        raise ValueError("browser seccomp profile is missing or differs from the qualified identity")
    viewport = browser["viewport"]
    if (not isinstance(viewport, dict) or set(viewport) != {"width", "height"}
            or any(type(value) is not int or not 320 <= value <= 2560 for value in viewport.values())):
        raise ValueError("browser viewport dimensions must be integers from 320 to 2560")
    return browser


def _validate_browser_step(step: dict) -> None:
    if step.get("op") == "audit":
        if set(step) != {"op", "expect"} or step["expect"] != AUDIT_EXPECTATION:
            raise ValueError("browser audit requires all diagnostics empty, including incomplete checks")
        return
    fields = {"goto": {"op", "path"}, "fill": {"op", "label", "value"},
              "click": {"op", "role", "name"}, "text": {"op", "role", "name", "expect"}}
    operation = step.get("op")
    if not isinstance(operation, str) or operation not in fields or set(step) != fields[operation]:
        raise ValueError("unsupported browser step; use goto/fill/click/text/audit")
    if any(not isinstance(value, str) or len(value.encode()) > 4096 or "\0" in value
           for value in step.values()):
        raise ValueError("browser steps require bounded string fields")
    if operation == "goto" and (not step["path"].startswith("/") or step["path"].startswith("//")
                                or any(ord(char) < 33 or ord(char) > 126 for char in step["path"])):
        raise ValueError("browser navigation must be product-local")
    if operation in ("click", "text") and step["role"] not in ("button", "link", "heading", "status", "alert", "cell"):
        raise ValueError("unsupported browser role")


def validate_contract(contract: dict, scenarios: list[dict]) -> None:
    keys = {"schema_version", "scenario_digest", "surface", "runtime_image", "context", "product", "actions"}
    web = contract.get("surface") == "web"
    if web:
        keys.add("browser")
    if (set(contract) != keys
            or type(contract["schema_version"]) is not int or contract["schema_version"] != 2
            or contract["scenario_digest"] != _digest(scenarios)
            or contract["surface"] not in ("api", "web") or contract["runtime_image"] != IMAGE
            or not isinstance(contract["context"], str)
            or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}", contract["context"])):
        raise ValueError("invalid version-2 API contract or unqualified runtime image")
    if web:
        _browser_settings(contract)
    product = contract["product"]
    if (not isinstance(product, dict) or set(product) != {"argv", "port"}
            or type(product["port"]) is not int or not 1024 <= product["port"] <= 65535
            or not isinstance(product["argv"], list) or not 1 <= len(product["argv"]) <= 100
            or any(not isinstance(value, str) or "\0" in value for value in product["argv"])
            or not product["argv"][0].startswith("/product/")
            or ".." in Path(product["argv"][0]).parts):
        raise ValueError("product requires a /product/ Python script, bounded arguments and port")
    actions = contract["actions"]
    if not isinstance(actions, list) or not 1 <= len(actions) <= 30:
        raise ValueError("API contract requires 1-30 scenario actions")
    for action in actions:
        if (not isinstance(action, dict) or set(action) != {"scenario_id", "timeout_s", "steps"}
                or not isinstance(action["scenario_id"], str)
                or type(action["timeout_s"]) is not int or not 1 <= action["timeout_s"] <= 60
                or not isinstance(action["steps"], list) or not 1 <= len(action["steps"]) <= 10):
            raise ValueError("invalid API scenario action")
        for step in action["steps"]:
            if isinstance(step, dict) and set(step) == {"restart"} and step["restart"] is True:
                continue
            if web:
                if not isinstance(step, dict):
                    raise ValueError("browser step must be an object")
                _validate_browser_step(step)
                continue
            if (not isinstance(step, dict) or set(step) != {"method", "path", "body", "expect"}
                    or step["method"] not in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD")
                    or not isinstance(step["path"], str) or not step["path"].startswith("/")
                    or step["path"].startswith("//") or len(step["path"]) > 4096
                    or any(ord(char) < 33 or ord(char) > 126 for char in step["path"])
                    or not isinstance(step["body"], str) or len(step["body"].encode()) > LIMIT):
                raise ValueError("invalid bounded local HTTP request")
            expected = step["expect"]
            if (not isinstance(expected, dict) or set(expected) != {"status_code", "body"}
                    or type(expected["status_code"]) is not int
                    or not 100 <= expected["status_code"] <= 599
                    or not isinstance(expected["body"], str) or len(expected["body"].encode()) > LIMIT):
                raise ValueError("HTTP oracle requires an exact status_code and bounded UTF-8 body")
        if web and not any(step.get("op") == "text" for step in action["steps"]):
            raise ValueError("browser scenario needs an observed text assertion")
        if not web and not any("method" in step for step in action["steps"]):
            raise ValueError("API scenario needs an observed response assertion")
        if web and sum(step.get("op") == "audit" for step in action["steps"]) > 1:
            raise ValueError("at most one audit per browser scenario")
    if sorted(action["scenario_id"] for action in actions) != sorted(item["id"] for item in scenarios):
        raise ValueError("API contract must cover every active scenario exactly once")
    if web and sum(step.get("op") == "audit" for action in actions for step in action["steps"]) > 8:
        raise ValueError("at most eight browser audits per bounded receipt")
    if not web and any(sum(len(step["expect"]["body"].encode()) for step in action["steps"] if "expect" in step) > LIMIT // 2
           for action in actions):
        raise ValueError("scenario expected response total exceeds capture budget")


def expected(action: dict) -> dict:
    values = []
    for step in action["steps"]:
        if "restart" in step:
            values.append({"restart": True})
        elif step.get("op") == "text":
            values.append({"text": step["expect"]})
        elif step.get("op") == "audit":
            values.append({"audit": step["expect"]})
        elif "method" in step:
            values.append(step["expect"])
    return {"exit_code": 0, "stdout": json.dumps(values,
                                                sort_keys=True, separators=(",", ":")) + "\n",
            "stderr": ""}


def _docker(context: str, arguments: list[str], *, data: str | None = None,
            timeout: int = 30) -> str:
    from fettle.uat.recovery import inherited_fds

    executable = shutil.which("docker")
    if not executable:
        raise ValueError("Docker CLI unavailable; install and start the qualified isolated runtime")
    try:
        result = subprocess.run([executable, "--context", context, *arguments], input=data,
                                capture_output=True, text=True, timeout=timeout, pass_fds=inherited_fds())
    except subprocess.TimeoutExpired as exception:
        raise ValueError("isolated operation timed out; rerun the approved contract") from exception
    if result.returncode:
        message = _redact_secrets(result.stderr[:4096])[0]
        raise ValueError("isolated Docker operation failed: " + message)
    if len(result.stdout.encode()) > SOURCE_LIMIT:
        raise ValueError("Docker response exceeds capture budget")
    return result.stdout


def runtime(contract: dict) -> dict:
    context = contract["context"]
    endpoint = json.loads(_docker(context, ["context", "inspect", context]))[0]["Endpoints"]["docker"]
    if not endpoint["Host"].startswith("unix://") or endpoint.get("SkipTLSVerify"):
        raise ValueError("API capture requires a local Unix-socket Docker context")
    image = json.loads(_docker(context, ["image", "inspect", IMAGE]))[0]
    if image["Config"].get("Volumes"):
        raise ValueError("runtime declares unapproved image volumes")
    server = json.loads(_docker(context, ["info", "--format", "{{json .}}"] ))
    browser_runtime = {}
    if contract["surface"] == "web":
        browser = _browser_settings(contract)
        browser_image = json.loads(_docker(context, ["image", "inspect", browser["image"]]))[0]
        if browser_image["Config"].get("Volumes"):
            raise ValueError("browser image declares unexpected volumes")
        browser_runtime = {"image": browser_image["Id"], "seccomp": BROWSER_PROFILE}
    return {"controller": _file_digest(Path(__file__)),
            "recovery": _file_digest(Path(__file__).with_name("recovery.py")),
            "capture": _file_digest(Path(__file__).with_name("controller.py")),
            "image": image["Id"], "browser": browser_runtime,
            "endpoint": endpoint, "server": {name: server[name] for name in
                                             ("ID", "ServerVersion", "KernelVersion", "OSType")}}


def execute(root: str, contract: dict, entries: dict) -> list[dict]:
    from fettle.uat.recovery import finish_resources, lease

    with lease(root, contract["context"]):
        observations = _execute_owned(root, contract, entries)
        finish_resources()
        return observations


def _execute_owned(root: str, contract: dict, entries: dict) -> list[dict]:
    from fettle.uat.recovery import plan_resources

    context = contract["context"]
    prefix = "fettle-uat-" + uuid.uuid4().hex
    network, volume, product = prefix + "-network", prefix + "-source", prefix + "-product"
    state_volume = prefix + "-state"
    keeper = prefix + "-state-keeper"
    seed, observer = prefix + "-seed", prefix + "-observer"
    payload = {}
    total = 0
    for name in entries:
        path = Path(root) / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > SOURCE_LIMIT:
            raise ValueError("unsupported or oversized product input")
        with path.open("rb") as handle:
            content = handle.read(SOURCE_LIMIT + 1)
        if hashlib.sha256(content).hexdigest() != entries[name].get("content_sha"):
            raise ValueError("product bytes differ from the frozen source inventory")
        total += len(content)
        if total > SOURCE_LIMIT:
            raise ValueError("product source exceeds 16 MiB capture budget")
        payload[name] = base64.b64encode(content).decode("ascii")
    script = contract["product"]["argv"][0].removeprefix("/product/")
    if script not in payload:
        raise ValueError("startup script is outside the frozen source inventory")
    ownership = plan_resources(prefix)
    observations = []
    created_network = created_volume = created_state = False
    containers = []
    try:
        _docker(context, ["network", "create", *ownership, "--internal", "--opt",
                          "com.docker.network.bridge.gateway_mode_ipv4=isolated", network])
        created_network = True
        network_info = json.loads(_docker(context, ["network", "inspect", network]))[0]
        if (not network_info["Internal"] or network_info["EnableIPv6"]
                or any(item.get("Gateway") for item in network_info["IPAM"]["Config"])):
            raise ValueError("isolated network has an unexpected gateway or IPv6 configuration")
        _docker(context, ["volume", "create", *ownership, volume])
        created_volume = True
        _docker(context, ["volume", "create", *ownership, "--driver", "local", "--opt", "type=tmpfs",
                  "--opt", "device=tmpfs", "--opt", "o=size=16m,uid=65534,gid=65534,mode=0700", state_volume])
        created_state = True
        containers.append(keeper)
        _docker(context, ["run", *ownership, "--detach", "--name", keeper, "--network", "none", *OPTIONS,
                  "--mount", f"type=volume,src={state_volume},dst=/state,readonly",
                  IMAGE, "-I", "-c", "import signal; signal.pause()"])
        containers.append(seed)
        _docker(context, ["run", *ownership, "--name", seed, "--network", "none", *OPTIONS,
                          "--user", "0:0", "--mount", f"type=volume,src={volume},dst=/source",
                          "-i", IMAGE, "-I", "-c", SEED], data=json.dumps(payload))
        containers.append(product)
        _docker(context, ["run", *ownership, "--detach", "--name", product, "--network", network,
                          "--network-alias", "product", *OPTIONS,
                          "--mount", f"type=volume,src={volume},dst=/product,readonly",
                          "--mount", f"type=volume,src={state_volume},dst=/state",
                          "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777",
                          "--workdir", "/product", IMAGE, "-I", "-B", *contract["product"]["argv"]])
        for action in contract["actions"]:
            deadline = time.monotonic() + action["timeout_s"]
            error = ""
            stdout = ""
            artifacts = []
            try:
                observed = []
                group: list[dict] = []
                groups: list[list[dict]] = []
                for step in action["steps"]:
                    if "restart" in step:
                        if group:
                            groups.append(group)
                        groups.append([step])
                        group = []
                    else:
                        group.append(step)
                if group:
                    groups.append(group)
                for steps in groups:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ValueError("scenario deadline exceeded")
                    if "restart" in steps[0]:
                        before = json.loads(_docker(context, ["inspect", product]))[0]["State"]
                        _docker(context, ["restart", "--time", "1", product], timeout=max(1, int(remaining)))
                        after = json.loads(_docker(context, ["inspect", product]))[0]["State"]
                        if not after["Running"] or before["StartedAt"] == after["StartedAt"]:
                            raise ValueError("required product restart did not complete")
                        observed.append({"restart": True})
                        continue
                    containers.append(observer)
                    web = contract["surface"] == "web"
                    browser_options = []
                    if web:
                        browser = _browser_settings(contract)
                        browser_options = ["--entrypoint", "/usr/bin/python3", "--memory", "1g",
                                           "--memory-swap", "1g", "--pids-limit", "128",
                                           "--security-opt", "seccomp=" + browser["seccomp_path"],
                                           "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=128m,mode=1777"]
                    raw = _docker(context, ["run", *ownership, "--name", observer, "--network", network,
                                           *OPTIONS, *browser_options, "-i", BROWSER_IMAGE if web else IMAGE,
                                           "-I", "-c", BROWSE if web else COLLECT],
                                  data=json.dumps({"port": contract["product"]["port"],
                                                   "timeout_s": remaining,
                                                   "viewport": contract.get("browser", {}).get("viewport"),
                                                   "steps": [{key: value for key, value in step.items() if key != "expect"}
                                                             for step in steps]}),
                                  timeout=max(1, int(remaining)))
                    decoded = json.loads(raw)
                    if web:
                        if (not isinstance(decoded, dict) or set(decoded) != {"observations", "artifacts", "sensitive"}
                                or _redact_secrets(json.dumps(decoded["sensitive"]))[1]):
                            raise ValueError("malformed or possible secret browser output suppressed")
                        artifacts.extend(decoded["artifacts"])
                        decoded = decoded["observations"]
                    if not isinstance(decoded, list):
                        raise ValueError("collector returned malformed observations")
                    observed.extend(decoded)
                    _docker(context, ["rm", "--force", observer])
                    containers.remove(observer)
                stdout = json.dumps(observed, sort_keys=True, separators=(",", ":")) + "\n"
                if len(stdout.encode()) > LIMIT or _redact_secrets(stdout)[1]:
                    stdout = ""
                    raise ValueError("oversized or possible secret response suppressed")
            except (OSError, ValueError, subprocess.SubprocessError) as exception:
                error = ("collector interrupted; rerun the approved contract"
                         if isinstance(exception, subprocess.TimeoutExpired)
                         else _redact_secrets(str(exception)[:4096])[0])
                stdout = ""
            finally:
                if observer in containers:
                    _docker(context, ["rm", "--force", observer])
                    containers.remove(observer)
            observations.append({"scenario_id": action["scenario_id"], "attempt": 1,
                                 "exit_code": 1 if error else 0, "stdout": stdout,
                                 "stderr": "", "error": error,
                                 **({"artifacts": [] if error else artifacts} if contract["surface"] == "web" else {})})
            if contract["surface"] == "web":
                validate_artifacts(contract, action, observations[-1])
        state = json.loads(_docker(context, ["inspect", product]))[0]["State"]
        if not state["Running"] or state["OOMKilled"] or state["Error"]:
            raise ValueError("product exited or exceeded runtime resources during capture")
    finally:
        errors = []
        operations = [["rm", "--force", name] for name in reversed(containers)]
        if created_volume:
            operations.append(["volume", "rm", volume])
        if created_state:
            operations.append(["volume", "rm", state_volume])
        if created_network:
            operations.append(["network", "rm", network])
        for arguments in operations:
            try:
                _docker(context, arguments)
            except (OSError, ValueError, subprocess.SubprocessError) as exception:
                errors.append(str(exception))
        if errors:
            raise ValueError("container cleanup incomplete: " + "; ".join(errors))
    return observations