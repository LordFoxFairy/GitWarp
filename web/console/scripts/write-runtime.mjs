import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dist = path.join(root, "dist");
const viteDirArg = process.argv.find((value) => value.startsWith("--vite-dir="));
const viteDist = viteDirArg ? path.resolve(root, viteDirArg.slice("--vite-dir=".length)) : path.join(dist, ".vite");
const packageAssets = path.resolve(root, "../../src/gitwarp/assets/web_console");
const checkOnly = process.argv.includes("--check");

const [css, js] = await Promise.all([
  readFile(path.join(viteDist, "app.css"), "utf8"),
  readFile(path.join(viteDist, "app.js"), "utf8"),
]);

const html = `<!doctype html>
<html lang="en" data-gitwarp-token="__TOKEN__">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GitWarp Manager</title>
  <style>__CSS__</style>
</head>
<body>
  <div id="root"></div>
  <script type="module">__JS__</script>
</body>
</html>
`;

const artifacts = {
  "index.html": html,
  "app.css": css,
  "app.js": js,
};

async function assertDirectoryMatches(directory) {
  const actual = (await readdir(directory)).filter((name) => !name.startsWith(".")).sort();
  const expected = Object.keys(artifacts).sort();
  if (actual.join("\n") !== expected.join("\n")) {
    throw new Error(`runtime asset file set drifted in ${directory}: expected ${expected.join(", ")}, found ${actual.join(", ")}`);
  }
  for (const [filename, expectedContent] of Object.entries(artifacts)) {
    const actualContent = await readFile(path.join(directory, filename), "utf8");
    if (actualContent !== expectedContent) {
      throw new Error(`runtime asset drifted: ${path.join(directory, filename)}`);
    }
  }
}

if (checkOnly) {
  await Promise.all([assertDirectoryMatches(dist), assertDirectoryMatches(packageAssets)]);
} else {
  await mkdir(dist, { recursive: true });
  await mkdir(packageAssets, { recursive: true });
  await Promise.all(
    Object.entries(artifacts).flatMap(([filename, content]) => [
      writeFile(path.join(dist, filename), content, "utf8"),
      writeFile(path.join(packageAssets, filename), content, "utf8"),
    ]),
  );
}
