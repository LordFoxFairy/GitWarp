import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dist = path.join(root, "dist");
const viteDist = path.join(dist, ".vite");
const packageAssets = path.resolve(root, "../../src/gitwarp/assets/web_console");

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

await mkdir(dist, { recursive: true });
await mkdir(packageAssets, { recursive: true });
await Promise.all([
  writeFile(path.join(dist, "index.html"), html, "utf8"),
  writeFile(path.join(dist, "app.css"), css, "utf8"),
  writeFile(path.join(dist, "app.js"), js, "utf8"),
  writeFile(path.join(packageAssets, "index.html"), html, "utf8"),
  writeFile(path.join(packageAssets, "app.css"), css, "utf8"),
  writeFile(path.join(packageAssets, "app.js"), js, "utf8"),
]);
