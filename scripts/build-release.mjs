import { copyFileSync, existsSync, readFileSync, unlinkSync, writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const installedGitHubCli = join(process.env.ProgramFiles || "C:\\Program Files", "GitHub CLI", "gh.exe");
const githubCli = process.platform === "win32" && existsSync(installedGitHubCli) ? installedGitHubCli : "gh";

function parseVersion(value) {
  const match = String(value ?? "").trim().match(/^v?(\d+)\.(\d+)\.(\d+)$/);
  return match ? match.slice(1).map(Number) : null;
}

function compareVersions(left, right) {
  for (let index = 0; index < 3; index += 1) {
    if (left[index] !== right[index]) return left[index] - right[index];
  }
  return 0;
}

export function repositoryFromRemote(remote) {
  const match = String(remote ?? "")
    .trim()
    .match(/github\.com[/:]([^/\s]+)\/([^/\s]+?)(?:\.git)?$/i);
  if (!match) throw new Error("O repositório GitHub não pôde ser identificado pelo remote origin.");
  return `${match[1]}/${match[2]}`;
}

export function releaseNotesFromMarkdown(markdown, currentVersion, previousTag = "") {
  const current = parseVersion(currentVersion);
  if (!current) throw new Error(`Versão inválida: ${currentVersion}`);

  const previous = previousTag ? parseVersion(previousTag) : null;
  const text = String(markdown);
  const headings = [...text.matchAll(/^# (\d+\.\d+\.\d+)\s+[—-]\s+.*$/gm)];
  const sections = headings.map((heading, index) => ({
    version: heading[1],
    body: text
      .slice(heading.index, headings[index + 1]?.index ?? text.length)
      .replace(/\s*---\s*$/, "")
      .trim()
  }));

  const selected = sections.filter((section) => {
    const version = parseVersion(section.version);
    if (!version || compareVersions(version, current) > 0) return false;
    return previous ? compareVersions(version, previous) > 0 : compareVersions(version, current) === 0;
  });

  if (!selected.some((section) => section.version === currentVersion)) {
    throw new Error(`A seção da versão ${currentVersion} não foi encontrada em RELEASE_NOTES.md.`);
  }
  return selected.map((section) => section.body).join("\n\n---\n\n");
}

export function previousReleaseTag(releases, currentTag) {
  return releases.find((release) => release.tagName !== currentTag)?.tagName || "";
}

function command(commandName, args, { allowFailure = false, inherit = false, env = process.env } = {}) {
  const result = spawnSync(commandName, args, {
    cwd: root,
    encoding: "utf8",
    env,
    stdio: inherit ? "inherit" : ["ignore", "pipe", "pipe"]
  });
  if (result.error) throw result.error;
  if (!allowFailure && result.status !== 0) {
    const details = String(result.stderr || result.stdout || "").trim();
    throw new Error(details || `${commandName} terminou com código ${result.status}.`);
  }
  return result;
}

function output(commandName, args) {
  return String(command(commandName, args).stdout).trim();
}

function ensureGitHubCli() {
  const check = spawnSync(githubCli, ["--version"], { cwd: root, encoding: "utf8" });
  if (check.error?.code === "ENOENT") {
    throw new Error(
      "GitHub CLI não encontrado. Instale com 'winget install --id GitHub.cli' e autentique com 'gh auth login'."
    );
  }
  if (check.error) throw check.error;
  if (check.status !== 0) throw new Error("Não foi possível executar o GitHub CLI (gh).");

  const authentication = command(githubCli, ["auth", "status", "--hostname", "github.com"], { allowFailure: true });
  if (authentication.status !== 0) {
    throw new Error("O GitHub CLI não está autenticado. Execute 'gh auth login' e tente novamente.");
  }
}

function releasePreflight(version) {
  ensureGitHubCli();

  const repository = repositoryFromRemote(output("git", ["remote", "get-url", "origin"]));
  const tag = `v${version}`;
  const existingRelease = command(
    githubCli,
    ["release", "view", tag, "--repo", repository, "--json", "isDraft"],
    { allowFailure: true }
  );
  const existingDraft = existingRelease.status === 0 && JSON.parse(existingRelease.stdout).isDraft;
  if (existingRelease.status === 0 && !existingDraft) throw new Error(`A release ${tag} já foi publicada no GitHub.`);
  if (!existingDraft && output("git", ["ls-remote", "--tags", "origin", `refs/tags/${tag}`])) {
    throw new Error(`A tag ${tag} já existe no GitHub, mas não há uma release correspondente.`);
  }

  const releases = JSON.parse(
    output(githubCli, ["release", "list", "--repo", repository, "--limit", "100", "--json", "tagName"])
  );
  const previousTag = previousReleaseTag(releases, tag);
  const notes = releaseNotesFromMarkdown(
    readFileSync(join(root, "RELEASE_NOTES.md"), "utf8"),
    version,
    previousTag
  );
  return { existingDraft, notes, repository, tag };
}

function main() {
  const version = JSON.parse(readFileSync(join(root, "desktop", "package.json"), "utf8")).version;
  const key = join(root, "desktop", "src-tauri", "tauri.key");
  if (!existsSync(key)) throw new Error("Chave privada ausente. Restaure desktop/src-tauri/tauri.key do seu backup.");

  const release = releasePreflight(version);
  command(process.execPath, ["--test", join(root, "scripts", "build-release.test.mjs")], { inherit: true });

  const env = { ...process.env };
  env.BOT_OFERTAS_RELEASE = "1";
  env.TAURI_SIGNING_PRIVATE_KEY ||= key;
  env.TAURI_SIGNING_PRIVATE_KEY_PASSWORD ??= "";
  command(
    "powershell",
    ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", join(root, "scripts", "build-desktop.ps1")],
    { env, inherit: true }
  );

  const nsis = join(root, "desktop", "src-tauri", "target", "release", "bundle", "nsis");
  const source = join(nsis, `Bot de Ofertas_${version}_x64-setup.exe`);
  const sourceSignature = `${source}.sig`;
  if (!existsSync(source) || !existsSync(sourceSignature)) {
    throw new Error("Instalador ou assinatura do updater não encontrado.");
  }

  const name = `BotDeOfertas_${version}_x64-setup.exe`;
  const installer = join(nsis, name);
  const signatureFile = `${installer}.sig`;
  const latestFile = join(nsis, "latest.json");
  const notesFile = join(nsis, `.release-notes-${version}.md`);
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
        url: `https://github.com/${release.repository}/releases/download/${release.tag}/${name}`
      }
    }
  };
  writeFileSync(latestFile, `${JSON.stringify(latest, null, 2)}\n`, "utf8");
  writeFileSync(notesFile, `${release.notes}\n`, "utf8");

  try {
    const action = release.existingDraft ? "edit" : "create";
    command(
      githubCli,
      [
        "release",
        action,
        release.tag,
        "--repo",
        release.repository,
        "--title",
        release.tag,
        "--notes-file",
        notesFile,
        "--draft"
      ],
      { inherit: true }
    );
  } finally {
    if (existsSync(notesFile)) unlinkSync(notesFile);
  }

  console.log(`\nRascunho da release ${release.tag} ${release.existingDraft ? "atualizado" : "criado"} no GitHub.`);
  console.log("Anexe estes arquivos ao rascunho e publique quando estiver pronto:");
  console.log(`- ${installer}`);
  console.log(`- ${signatureFile}`);
  console.log(`- ${latestFile}`);
}

const invokedPath = process.argv[1] ? resolve(process.argv[1]) : "";
if (invokedPath === fileURLToPath(import.meta.url)) main();
