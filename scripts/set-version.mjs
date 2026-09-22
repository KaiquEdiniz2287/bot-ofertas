import { readFileSync, writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const version = process.argv[2];
if (!/^\d+\.\d+\.\d+$/.test(version || "")) throw new Error("Use: npm run set-version -- 0.3.0");

function json(relative) {
  const path = join(root, relative);
  const value = JSON.parse(readFileSync(path, "utf8"));
  value.version = version;
  writeFileSync(path, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}
function replace(relative, pattern, replacement) {
  const path = join(root, relative);
  const current = readFileSync(path, "utf8");
  if (!pattern.test(current)) throw new Error(`Versão não encontrada em ${relative}`);
  pattern.lastIndex = 0;
  const next = current.replace(pattern, replacement);
  writeFileSync(path, next, "utf8");
}
function run(command, args, cwd = root) {
  const result = process.platform === "win32"
    ? spawnSync(process.env.ComSpec || "cmd.exe", ["/d", "/s", "/c", [command, ...args].join(" ")], { cwd, stdio: "inherit" })
    : spawnSync(command, args, { cwd, stdio: "inherit" });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}

json("package.json");
json("desktop/package.json");
json("desktop/src-tauri/tauri.conf.json");
replace("pyproject.toml", /(\[project\][\s\S]*?^version = ")[^"]+/m, (_, prefix) => `${prefix}${version}`);
replace("ofertas/__init__.py", /(__version__ = ")[^"]+/, (_, prefix) => `${prefix}${version}`);
replace("desktop/src-tauri/Cargo.toml", /(\[package\][\s\S]*?^version = ")[^"]+/m, (_, prefix) => `${prefix}${version}`);
run("npm", ["install", "--package-lock-only"], join(root, "desktop"));
run("uv", ["lock"]);
run("cargo", ["check", "--manifest-path", "desktop/src-tauri/Cargo.toml"]);
console.log(`Versão sincronizada: ${version}`);
