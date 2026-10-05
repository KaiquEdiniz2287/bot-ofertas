import assert from "node:assert/strict";
import test from "node:test";

import { previousReleaseTag, releaseNotesFromMarkdown, repositoryFromRemote } from "./build-release.mjs";

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
