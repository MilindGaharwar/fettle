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
      const { execSync } = require("child_process");
      const resolved = execSync(`command -v ${candidate} 2>/dev/null`, {
        encoding: "utf-8",
      }).trim();
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
    documentSelector: [
      { scheme: "file", language: "python" },
      { scheme: "file", language: "typescript" },
      { scheme: "file", language: "typescriptreact" },
      { scheme: "file", language: "javascript" },
      { scheme: "file", language: "javascriptreact" },
      { scheme: "file", language: "go" },
      { scheme: "file", language: "rust" },
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
      terminal.sendText(
        `python3 ${path.join(pluginRoot, "scripts", "quality_scan.py")} --root "${workspaceRoot}"`
      );
      terminal.show();
    })
  );

  context.subscriptions.push(
    commands.registerCommand("fettle.showReport", async () => {
      const terminal = window.createTerminal("Fettle Report");
      const workspaceRoot =
        workspace.workspaceFolders?.[0]?.uri.fsPath || ".";
      terminal.sendText(
        `bash ${path.join(pluginRoot, "scripts", "run.sh")} report.py --root "${workspaceRoot}"`
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
