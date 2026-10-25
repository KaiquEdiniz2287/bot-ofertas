import assert from "node:assert/strict";
import test from "node:test";
import { copyFileSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

import { previousReleaseTag, releaseNotesFromMarkdown, repositoryFromRemote } from "./build-release.mjs";

for (const stage of ["python", "interface", "rust", "sucesso"]) {
  test(stage === "sucesso" ? "encaminha --locked ao Cargo pelo Tauri e conclui as etapas" : `interrompe o build na falha de ${stage}, sem tentar gerar o instalador`, { skip: process.platform !== "win32" }, () => {
    const root = mkdtempSync(join(tmpdir(), "bot-release-failure-"));
    try {
      const scripts = join(root, "scripts"), bin = join(root, "bin");
      mkdirSync(scripts); mkdirSync(bin); mkdirSync(join(root, "desktop", "src-tauri"), { recursive: true });
      const bundle = join(root, "desktop", "src-tauri", "target", "release", "bundle", "nsis");
      mkdirSync(bundle, { recursive: true });
      writeFileSync(join(bundle, "fixture.exe"), "");
      copyFileSync(new URL("./build-desktop.ps1", import.meta.url), join(scripts, "build-desktop.ps1"));
      for (const name of ["build-whatsapp.ps1", "build-backend.ps1"]) writeFileSync(join(scripts, name), "$global:LASTEXITCODE = 0\n");
      for (const [name, failure] of [["uv", stage === "python"], ["npm", stage === "interface"], ["cargo", stage === "rust"]]) {
        writeFileSync(join(bin, `${name}.cmd`), `@echo off\r\necho NATIVE:${name} %*\r\nexit /b ${failure ? 42 : 0}\r\n`);
      }
      const result = spawnSync("powershell", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", join(scripts, "build-desktop.ps1")], {
        encoding: "utf8", env: { ...process.env, BOT_OFERTAS_RELEASE: "1", TAURI_SIGNING_PRIVATE_KEY: "fixture", PATH: `${bin};${process.env.PATH}` }, timeout: 15000,
      });
      assert.ifError(result.error);
      if (stage === "sucesso") {
        assert.equal(result.status, 0, result.stderr);
        assert.match(result.stdout, /NATIVE:npm run tauri -- build -- --locked/);
        return;
      }
      assert.notEqual(result.status, 0);
      assert.match(result.stderr, /42/);
      assert.doesNotMatch(result.stdout, /NATIVE:npm run tauri|NATIVE:tauri/);
      if (stage === "python") assert.doesNotMatch(result.stdout, /NATIVE:npm|NATIVE:cargo/);
      if (stage === "interface") assert.doesNotMatch(result.stdout, /NATIVE:cargo/);
    } finally { rmSync(root, { recursive: true, force: true }); }
  });
}

test("falha do PyInstaller encerra o empacotamento antes de testar um backend antigo", { skip: process.platform !== "win32" }, () => {
  const root = mkdtempSync(join(tmpdir(), "bot-backend-failure-"));
  try {
    mkdirSync(join(root, "scripts")); mkdirSync(join(root, "bin"));
    copyFileSync(new URL("./build-backend.ps1", import.meta.url), join(root, "scripts", "build-backend.ps1"));
    writeFileSync(join(root, "bin", "uv.cmd"), '@echo off\r\nif "%1"=="sync" exit /b 0\r\nexit /b 43\r\n');
    const result = spawnSync("powershell", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", join(root, "scripts", "build-backend.ps1")], {
      encoding: "utf8", env: { ...process.env, PATH: `${join(root, "bin")};${process.env.PATH}` }, timeout: 15000,
    });
    assert.ifError(result.error);
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /43/);
    assert.doesNotMatch(result.stderr, /Smoke test|CommandNotFound/);
  } finally { rmSync(root, { recursive: true, force: true }); }
});

test("identifica o repositório em remotes HTTPS e SSH", () => {
  assert.equal(repositoryFromRemote("https://github.com/Kaio/projeto.git"), "Kaio/projeto");
  assert.equal(repositoryFromRemote("git@github.com:Kaio/projeto.git"), "Kaio/projeto");
});

test("reúne todas as notas posteriores à última release", () => {
  const markdown = `# 0.12.0 — Novidades com acentuação 🚀

- Conexão automática e descrição correta.

---

# 0.11.1 — Correção

- Grupo e Canal sincronizados.

---

# 0.11.0 — Versão anterior

- Conteúdo já publicado.
`;
  const notes = releaseNotesFromMarkdown(markdown, "0.12.0", "v0.11.0");
  assert.match(notes, /0\.12\.0 — Novidades com acentuação 🚀/);
  assert.match(notes, /0\.11\.1 — Correção/);
  assert.doesNotMatch(notes, /0\.11\.0 — Versão anterior/);
});

test("inclui somente a versão atual quando ainda não existe release", () => {
  const markdown = `# 0.12.0 — Atual

- Alteração atual.

---

# 0.11.1 — Antiga

- Alteração antiga.
`;
  const notes = releaseNotesFromMarkdown(markdown, "0.12.0");
  assert.match(notes, /0\.12\.0 — Atual/);
  assert.doesNotMatch(notes, /0\.11\.1 — Antiga/);
});

test("exige uma seção de notas para a versão publicada", () => {
  assert.throws(
    () => releaseNotesFromMarkdown("# 0.11.0 — Antiga\n", "0.12.0", "v0.11.0"),
    /não foi encontrada/
  );
});

test("usa a execução anterior, incluindo rascunhos, como início das notas", () => {
  const releases = [{ tagName: "v0.12.0" }, { tagName: "v0.11.1" }, { tagName: "v0.11.0" }];
  assert.equal(previousReleaseTag(releases, "v0.12.0"), "v0.11.1");
  assert.equal(previousReleaseTag(releases, "v0.12.1"), "v0.12.0");
});
