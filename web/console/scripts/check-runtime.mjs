import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const tempRoot = await mkdtemp(path.join(os.tmpdir(), "gitwarp-console-"));
const viteOut = path.join(tempRoot, "vite");

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: root,
    stdio: "inherit",
    shell: process.platform === "win32",
    ...options,
  });
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    process.exitCode = result.status ?? 1;
    throw new Error(`${command} ${args.join(" ")} failed`);
  }
}

try {
  run("tsc", ["--noEmit"]);
  run("vite", ["build"], {
    env: {
      ...process.env,
      GITWARP_VITE_OUT_DIR: viteOut,
    },
  });
  run("node", ["scripts/write-runtime.mjs", "--check", `--vite-dir=${viteOut}`]);
} finally {
  await rm(tempRoot, { recursive: true, force: true });
}
