import { copyFileSync, existsSync, readFileSync, writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const version = JSON.parse(readFileSync(join(root, "desktop", "package.json"), "utf8")).version;
const key = join(root, "desktop", "src-tauri", "tauri.key");
if (!existsSync(key)) throw new Error("Chave privada ausente. Restaure desktop/src-tauri/tauri.key do seu backup.");

const env = { ...process.env };
env.BOT_OFERTAS_RELEASE = "1";
env.TAURI_SIGNING_PRIVATE_KEY ||= key;
const build = spawnSync("powershell", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", join(root, "scripts", "build-desktop.ps1")], { cwd: root, env, stdio: "inherit" });
if (build.status !== 0) process.exit(build.status ?? 1);

const nsis = join(root, "desktop", "src-tauri", "target", "release", "bundle", "nsis");
const source = join(nsis, `Bot de Ofertas_${version}_x64-setup.exe`);
const sourceSignature = `${source}.sig`;
if (!existsSync(source) || !existsSync(sourceSignature)) throw new Error("Instalador ou assinatura do updater não encontrado.");

const name = `BotDeOfertas_${version}_x64-setup.exe`;
const installer = join(nsis, name);
const signatureFile = `${installer}.sig`;
copyFileSync(source, installer);
copyFileSync(sourceSignature, signatureFile);
const signature = readFileSync(signatureFile, "utf8").trim();
const latest = {
  version,
  notes: `Bot de Ofertas ${version}`,
  pub_date: new Date().toISOString(),
  platforms: {
    "windows-x86_64": {
      signature,
      url: `https://github.com/KaiquEdiniz2287/bot-ofertas/releases/download/v${version}/${name}`
    }
  }
};
writeFileSync(join(nsis, "latest.json"), `${JSON.stringify(latest, null, 2)}\n`, "utf8");

console.log(`\nRelease v${version} pronta. Publique na tag v${version}:`);
console.log(`- ${installer}`);
console.log(`- ${signatureFile}`);
console.log(`- ${join(nsis, "latest.json")}`);
