import { existsSync, mkdirSync, rmSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

const currentDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(currentDir, "..", "..", "..");
const apiDir = resolve(repoRoot, "apps", "api");
const dataDir = resolve(repoRoot, "data", "e2e-playwright");
const pythonPath = resolve(apiDir, ".venv", "Scripts", "python.exe");

if (!existsSync(pythonPath)) {
  process.stderr.write(`Missing API virtual environment python at ${pythonPath}\n`);
  process.exit(1);
}

rmSync(dataDir, { recursive: true, force: true });
mkdirSync(dataDir, { recursive: true });

const child = spawn(
  pythonPath,
  ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8011"],
  {
    cwd: apiDir,
    stdio: "inherit",
    env: {
      ...process.env,
      WORKBENCH_DATA_DIR: dataDir,
      WORKBENCH_QDRANT_URL: ":memory:",
      WORKBENCH_EMBEDDING_MODEL: "",
    },
  },
);

function shutdown(signal = "SIGTERM") {
  if (!child.killed) {
    child.kill(signal);
  }
}

child.on("exit", (code) => {
  process.exit(code ?? 0);
});

process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));
