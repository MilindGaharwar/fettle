import * as path from "path";
import * as fs from "fs";
import * as os from "os";
import {
  ExtensionContext,
  workspace,
  window,
  commands,
  OutputChannel,
} from "vscode";
import {
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
  TransportKind,
} from "vscode-languageclient/node";

let client: LanguageClient | undefined;
let outputChannel: OutputChannel;

/** POSIX single-quote escaping for values sent to a shell terminal. */
function shellQuote(value: string): string {
  return `'${value.replace(/'/g, `'\\''`)}'`;
}

function findPython(): string | undefined {
  const configured = workspace
    .getConfiguration("fettle")
    .get<string>("pythonPath");
  if (configured && fs.existsSync(configured)) return configured;

  const candidates = [
    process.env.FETTLE_PYTHON,
    "python3",
    path.join(os.homedir(), ".local", "share", "uv", "python", "cpython-3.14.5-macos-aarch64-none", "bin", "python3"),
    path.join(os.homedir(), ".local", "share", "uv", "python", "cpython-3.13.5-macos-aarch64-none", "bin", "python3"),
  ].filter(Boolean) as string[];

  for (const candidate of candidates) {
    try {
      if (fs.existsSync(candidate)) return candidate;
      const { execFileSync } = require("child_process");
      // argv-array + positional parameter: candidate is never interpolated
      // into shell syntax (audit M-02).
      const resolved = execFileSync(
        "/bin/sh",
        ["-c", 'command -v "$1" 2>/dev/null', "sh", candidate],
        { encoding: "utf-8" }
      ).trim();
      if (resolved) return resolved;
    } catch {
      continue;
    }
  }
  return undefined;
}

function findPluginRoot(): string {
  const configured = workspace
    .getConfiguration("fettle")
    .get<string>("pluginPath");
  if (configured && fs.existsSync(configured)) return configured;

  const defaultPath = path.join(
    os.homedir(),
    ".claude",
    "plugins",
    "fettle"
  );
  if (fs.existsSync(defaultPath)) return defaultPath;

  return "";
}

function createClient(
  context: ExtensionContext,
  pythonPath: string,
  pluginRoot: string
): LanguageClient {
  const lspScript = path.join(pluginRoot, "scripts", "lsp_server.py");

  const serverOptions: ServerOptions = {
    command: pythonPath,
    args: [lspScript],
    transport: TransportKind.stdio,
    options: {
      env: {
        ...process.env,
        FETTLE_PLUGIN_ROOT: pluginRoot,
        PATH: `${path.join(os.homedir(), ".local", "bin")}:${process.env.PATH}`,
      },
    },
  };

  const clientOptions: LanguageClientOptions = {
    // The LSP server lints Python only (lsp_server.py skips non-.py files) —
    // advertising other languages was audit finding M-12.
    documentSelector: [
      { scheme: "file", language: "python" },
    ],
    outputChannel,
    synchronize: {
      fileEvents: workspace.createFileSystemWatcher("**/.fettle.toml"),
    },
  };

  return new LanguageClient(
    "fettle",
    "Fettle Language Server",
    serverOptions,
    clientOptions
  );
}

export async function activate(context: ExtensionContext): Promise<void> {
  outputChannel = window.createOutputChannel("Fettle");

  const enabled = workspace.getConfiguration("fettle").get<boolean>("enable", true);
  if (!enabled) {
    outputChannel.appendLine("Fettle: disabled via settings");
    return;
  }

  const pluginRoot = findPluginRoot();
  if (!pluginRoot) {
    outputChannel.appendLine(
      "Fettle: plugin not found at ~/.claude/plugins/fettle — install it first"
    );
    return;
  }

  const pythonPath = findPython();
  if (!pythonPath) {
    window.showWarningMessage(
      "Fettle: no Python >= 3.11 found. Set fettle.pythonPath in settings."
    );
    return;
  }

  const lspScript = path.join(pluginRoot, "scripts", "lsp_server.py");
  if (!fs.existsSync(lspScript)) {
    outputChannel.appendLine(`Fettle: LSP server not found at ${lspScript}`);
    return;
  }

  outputChannel.appendLine(`Fettle: starting LSP (python: ${pythonPath})`);
  outputChannel.appendLine(`Fettle: plugin root: ${pluginRoot}`);

  client = createClient(context, pythonPath, pluginRoot);

  // Register commands
  context.subscriptions.push(
    commands.registerCommand("fettle.restart", async () => {
      if (client) {
        await client.stop();
        client.start();
        outputChannel.appendLine("Fettle: server restarted");
      }
    })
  );

  context.subscriptions.push(
    commands.registerCommand("fettle.runQualityScan", async () => {
      const terminal = window.createTerminal("Fettle Scan");
      const workspaceRoot =
        workspace.workspaceFolders?.[0]?.uri.fsPath || ".";
      const script = path.join(pluginRoot, "scripts", "quality_scan.py");
      terminal.sendText(
        `${shellQuote(pythonPath)} ${shellQuote(script)} --root ${shellQuote(workspaceRoot)}`
      );
      terminal.show();
    })
  );

  context.subscriptions.push(
    commands.registerCommand("fettle.showReport", async () => {
      const terminal = window.createTerminal("Fettle Report");
      const workspaceRoot =
        workspace.workspaceFolders?.[0]?.uri.fsPath || ".";
      const runner = path.join(pluginRoot, "scripts", "run.sh");
      terminal.sendText(
        `bash ${shellQuote(runner)} report.py --root ${shellQuote(workspaceRoot)}`
      );
      terminal.show();
    })
  );

  await client.start();
  outputChannel.appendLine("Fettle: LSP server started");
}

export async function deactivate(): Promise<void> {
  if (client) {
    await client.stop();
  }
}
