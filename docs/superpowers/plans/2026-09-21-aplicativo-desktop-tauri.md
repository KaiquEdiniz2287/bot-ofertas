# Aplicativo Desktop Tauri — Plano de Implementação

> **Para agentes executores:** SUB-SKILL OBRIGATÓRIA: usar `superpowers:executing-plans` para executar este plano tarefa por tarefa. `superpowers:subagent-driven-development` só poderá ser usado se o usuário escolher explicitamente execução com subagentes. Use as caixas `- [ ]` para acompanhar o progresso.

**Objetivo:** Entregar um aplicativo Windows x64 instalável, baseado em Tauri 2 e no backend Python existente, com bandeja, autostart opcional, console operacional integrado e migração segura dos dados atuais.

**Arquitetura:** O Tauri será a janela e o supervisor do processo Python. Um sidecar Python de longa duração receberá comandos JSON tipados por `stdin`, emitirá respostas e logs JSON por `stdout` e reutilizará a lógica atual do bot. Dados mutáveis serão redirecionados para `%LOCALAPPDATA%\BotOfertas`, enquanto a execução de desenvolvimento continuará compatível com a pasta atual.

**Stack:** Python 3.14, biblioteca padrão `unittest`, PyInstaller 6.22.3, Tauri 2.11, Rust 1.96, HTML/CSS/JavaScript puro, Node 24, NSIS e WebView2 Evergreen.

**Especificação:** `docs/superpowers/specs/2026-09-21-aplicativo-desktop-tauri-design.md`

## Restrições globais

- Plataforma desta entrega: Windows 10/11 x64.
- Preservar Telegram, Mercado Livre, Shopee, Amazon, filtros, banco, formatador e CLI existentes.
- Toda entrada e saída textual deve usar UTF-8 e preservar acentos, pontuação, emojis e caracteres especiais.
- Não incluir `.env`, SQLite, cookies, perfil do Mercado Livre, logs ou navegadores locais no instalador.
- Não expor terminal interativo, shell genérico ou comando arbitrário ao frontend.
- “Iniciar com o Windows” e “Ligar o bot automaticamente” devem vir desativados.
- Fechar a janela deve ocultá-la na bandeja; “Sair completamente” deve encerrar backend e tarefas.
- Nenhum teste automatizado pode publicar uma oferta real.
- Não alterar a versão até todos os testes, build e validações locais aplicáveis passarem.
- Quando concluído, aplicar `.skills/semver-versioning` uma única vez: `0.1.0 → 0.2.0`, nível MINOR.
- Não criar commits, tags, releases, pushes ou publicações sem solicitação explícita do usuário.

## Foco da revisão

- Configurações com IDs inválidos, YAML incompleto ou segredo vazio devem gerar erro legível sem apagar o valor anterior; coberto na Tarefa 2.
- Interrupção durante importação não pode ativar dados parciais nem modificar a origem; coberto na Tarefa 5.
- Dois comandos simultâneos que usem o perfil do Mercado Livre não podem executar juntos; coberto na Tarefa 4.
- Encerramento com bot ou ação em andamento deve parar graciosamente e ter limite para encerramento forçado; coberto nas Tarefas 3 e 7.
- Falha ou texto não JSON no backend não pode fechar a interface nem vazar segredos; coberto nas Tarefas 3, 4 e 7.

---

## Mapa de arquivos

### Python

- `ofertas/runtime_paths.py`: resolve caminhos de desenvolvimento e produção.
- `ofertas/settings.py`: lê, valida e grava `.env`, YAML e nichos de forma atômica.
- `ofertas/desktop_protocol.py`: contratos JSON e sanitização de eventos.
- `ofertas/desktop_service.py`: ciclo de vida do bot e despacho das operações desktop.
- `ofertas/migration.py`: importação transacional da instalação anterior.
- `ofertas/frozen_entry.py`: entrada única do executável PyInstaller.
- `ofertas/config.py`: mantém o singleton atual e adiciona recarga segura.
- `ofertas/bot_interativo.py`: separa construção da aplicação e execução gerenciada.
- `ofertas/painel.py`: reutiliza persistência nova sem perder o painel legado.
- `ofertas/main.py`: acrescenta o comando interno `desktop` e instalação compatível do navegador.
- `tests/`: testes Python sem rede e sem credenciais reais.
- `packaging/backend.spec`: receita PyInstaller.
- `scripts/build-backend.ps1`: build reproduzível do sidecar.

### Desktop

- `desktop/package.json`: scripts e dependências Tauri 2.
- `desktop/ui/index.html`: estrutura semântica da janela.
- `desktop/ui/styles.css`: temas, layout e acessibilidade.
- `desktop/ui/state.mjs`: estado puro e testável da interface.
- `desktop/ui/app.js`: integração Tauri, eventos e renderização.
- `desktop/ui/state.test.mjs`: testes com `node:test`.
- `desktop/src-tauri/Cargo.toml`: dependências Rust.
- `desktop/src-tauri/build.rs`: geração Tauri.
- `desktop/src-tauri/tauri.conf.json`: janela, recursos, sidecar e instalador.
- `desktop/src-tauri/capabilities/default.json`: permissões mínimas.
- `desktop/src-tauri/src/main.rs`: composição, comandos, janela e plugins.
- `desktop/src-tauri/src/backend.rs`: supervisão do sidecar e correlação de mensagens.
- `desktop/src-tauri/src/process_state.rs`: máquina de estados pura e testável.
- `desktop/src-tauri/src/tray.rs`: menu e comportamento da bandeja.
- `desktop/src-tauri/icons/`: ícones gerados pelo Tauri.
- `desktop/assets/icon.svg`: fonte vetorial do ícone.

### Documentação e release

- `.gitignore`: artefatos Python, Node, Rust e instalador.
- `README.md`: uso do aplicativo e desenvolvimento.
- `COMECE_AQUI.txt`: instrução principal pelo instalador.
- `RELEASE_NOTES.md`: primeira nota da versão desktop.

---

### Tarefa 1: Caminhos de execução e dados

**Arquivos:**

- Criar: `ofertas/runtime_paths.py`
- Criar: `tests/__init__.py`
- Criar: `tests/test_runtime_paths.py`
- Modificar: `ofertas/config.py`
- Modificar: `ofertas/db.py`

**Interfaces:**

- Produz: `RuntimePaths.for_environment(project_root: Path | None = None, environ: Mapping[str, str] | None = None) -> RuntimePaths`.
- Produz: `PATHS`, com `project_root`, `user_root`, `config_dir`, `data_dir` e `logs_dir`.
- Consome depois: settings, migração, fontes e bridge desktop.

- [ ] **Passo 1: escrever os testes de caminhos**

```python
# tests/test_runtime_paths.py
import tempfile
import unittest
from pathlib import Path

from ofertas.runtime_paths import RuntimePaths


class RuntimePathsTests(unittest.TestCase):
    def test_desenvolvimento_preserva_layout_atual(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = RuntimePaths.for_environment(root, {})
            self.assertEqual(paths.config_dir, root)
            self.assertEqual(paths.data_dir, root / "data")

    def test_desktop_usa_diretorio_externo(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "BotOfertas"
            paths = RuntimePaths.for_environment(Path(tmp), {"BOT_OFERTAS_HOME": str(home)})
            self.assertEqual(paths.config_dir, home / "config")
            self.assertEqual(paths.data_dir, home / "data")
            self.assertEqual(paths.logs_dir, home / "logs")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Passo 2: comprovar que o teste falha antes da implementação**

Executar: `uv run python -m unittest tests.test_runtime_paths -v`  
Esperado: falha de importação de `ofertas.runtime_paths`.

- [ ] **Passo 3: implementar o resolvedor mínimo de caminhos**

```python
# ofertas/runtime_paths.py
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
import os


@dataclass(frozen=True)
class RuntimePaths:
    project_root: Path
    user_root: Path
    config_dir: Path
    data_dir: Path
    logs_dir: Path

    @classmethod
    def for_environment(cls, project_root=None, environ=None):
        root = Path(project_root or Path(__file__).resolve().parent.parent)
        env = environ if environ is not None else os.environ
        desktop_home = env.get("BOT_OFERTAS_HOME", "").strip()
        if desktop_home:
            user_root = Path(desktop_home)
            return cls(root, user_root, user_root / "config", user_root / "data", user_root / "logs")
        return cls(root, root, root, root / "data", root / "logs")

    def ensure(self):
        for path in (self.config_dir, self.data_dir, self.logs_dir):
            path.mkdir(parents=True, exist_ok=True)


PATHS = RuntimePaths.for_environment()
PATHS.ensure()
```

- [ ] **Passo 4: fazer configuração e banco consumirem `PATHS`**

Em `ofertas/config.py`, manter `BASE_DIR` para compatibilidade e trocar o diretório mutável:

```python
from .runtime_paths import PATHS

BASE_DIR = PATHS.project_root
CONFIG_DIR = PATHS.config_dir
DATA_DIR = PATHS.data_dir
```

Ler `.env` e `config.yaml` de `CONFIG_DIR`. Se o desktop ainda não tiver `config.yaml`, copiar o padrão de `BASE_DIR / "config.yaml"` antes da leitura. `ofertas/db.py` continua importando `DATA_DIR`, portanto não precisa duplicar lógica.

- [ ] **Passo 5: executar regressão local**

Executar:

```powershell
uv run python -m unittest tests.test_runtime_paths -v
uv run python -m compileall -q ofertas tests
uv run python -c "from ofertas.config import DATA_DIR; print(DATA_DIR)"
```

Esperado: testes aprovados e o terceiro comando ainda aponta para `data` dentro do checkout quando `BOT_OFERTAS_HOME` não está definido.

---

### Tarefa 2: Persistência validada e atômica das configurações

**Arquivos:**

- Criar: `ofertas/settings.py`
- Criar: `tests/test_settings.py`
- Modificar: `ofertas/config.py`
- Modificar: `ofertas/painel.py`

**Interfaces:**

- Produz: `read_settings(mask_secrets: bool = True) -> dict`, incluindo preferências desktop em `config/app.json`.
- Produz: `write_settings(payload: dict) -> None`.
- Produz: `reload_config() -> Config` mantendo a identidade do singleton `config`.
- Produz: `SettingsError`, com mensagem segura para a interface.

- [ ] **Passo 1: testar segredo preservado, ID inválido e gravação UTF-8**

```python
# tests/test_settings.py
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ofertas.settings import SECRET_SET, SettingsError, read_env, write_env


class SettingsTests(unittest.TestCase):
    def test_segredo_vazio_preserva_valor_anterior(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("TELEGRAM_BOT_TOKEN=segredo\nTELEGRAM_OWNER_ID=123\n", encoding="utf-8")
            write_env(env_path, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_OWNER_ID": "456"})
            values = read_env(env_path)
            self.assertEqual(values["TELEGRAM_BOT_TOKEN"], "segredo")
            self.assertEqual(values["TELEGRAM_OWNER_ID"], "456")

    def test_owner_invalido_nao_substitui_arquivo(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("TELEGRAM_OWNER_ID=123\n", encoding="utf-8")
            with self.assertRaises(SettingsError):
                write_env(env_path, {"TELEGRAM_OWNER_ID": "abc"})
            self.assertEqual(read_env(env_path)["TELEGRAM_OWNER_ID"], "123")

    def test_leitura_mascarada_nao_devolve_segredo(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("SHOPEE_APP_SECRET=ação-secreta\n", encoding="utf-8")
            self.assertEqual(read_env(env_path, mask_secrets=True)["SHOPEE_APP_SECRET"], SECRET_SET)
```

- [ ] **Passo 2: executar e observar a falha inicial**

Executar: `uv run python -m unittest tests.test_settings -v`  
Esperado: falha porque `ofertas.settings` ainda não existe.

- [ ] **Passo 3: implementar escrita atômica e validação**

O módulo deve usar `tempfile.NamedTemporaryFile` no mesmo diretório, `flush`, `os.fsync` e `Path.replace`. As chaves permitidas serão as nove já declaradas no painel. `TELEGRAM_OWNER_ID` deve aceitar vazio ou inteiro; `TELEGRAM_CHAT_ID` deve aceitar vazio, `@canal` ou inteiro com sinal. Segredos serão `TELEGRAM_BOT_TOKEN`, `AMAZON_CREDENTIAL_SECRET` e `SHOPEE_APP_SECRET`.

```python
SECRET_SET = "__CONFIGURED__"


class SettingsError(ValueError):
    pass


def validate_env(values):
    owner = values.get("TELEGRAM_OWNER_ID", "").strip()
    if owner and not owner.isdigit():
        raise SettingsError("Seu user ID do Telegram deve conter apenas números.")
    chat = values.get("TELEGRAM_CHAT_ID", "").strip()
    if chat and not (chat.startswith("@") or chat.lstrip("-").isdigit()):
        raise SettingsError("O ID do canal deve ser @canal ou um número, normalmente iniciado por -100.")
```

`write_settings` deve mesclar apenas campos conhecidos no YAML atual, validar limites numéricos, gravar `nichos.json` e `app.json` com `ensure_ascii=False` e chamar `reload_config()` somente após todas as substituições concluírem. O sentinel `SECRET_SET` e um campo secreto vazio preservam o segredo; remoção exige a lista explícita `removeSecrets`.

- [ ] **Passo 4: recarregar o singleton sem invalidar imports existentes**

```python
# ofertas/config.py
def reload_config() -> Config:
    atualizado = Config()
    config.__dict__.clear()
    config.__dict__.update(atualizado.__dict__)
    return config
```

Antes de criar `Config()`, recarregar `.env` com `load_dotenv(CONFIG_DIR / ".env", override=True)`. O escritor deve manter todas as chaves conhecidas no arquivo, inclusive as vazias, para que a remoção explícita também limpe o valor do ambiente no reload.

- [ ] **Passo 5: remover a duplicação do painel legado**

`ofertas/painel.py` deve importar `read_env` e `write_env` de `ofertas.settings`, mantendo as funções `ler_env` e `salvar_env` como aliases compatíveis para o restante do arquivo.

- [ ] **Passo 6: executar testes e verificar que o `.env` real não mudou**

Executar:

```powershell
$before = (Get-FileHash -Algorithm SHA256 .env).Hash
uv run python -m unittest tests.test_settings -v
$after = (Get-FileHash -Algorithm SHA256 .env).Hash
if ($before -ne $after) { throw '.env foi alterado pelos testes' }
```

Esperado: testes aprovados e hashes iguais.

---

### Tarefa 3: Ciclo de vida gerenciado do bot

**Arquivos:**

- Criar: `tests/test_bot_runtime.py`
- Modificar: `ofertas/bot_interativo.py`

**Interfaces:**

- Produz: `criar_aplicacao() -> telegram.ext.Application`.
- Produz: `BotRuntime.start()`, `BotRuntime.stop()` e `BotRuntime.running`.
- Mantém: `rodar()` para a CLI atual.

- [ ] **Passo 1: testar a ordem de início e parada sem Telegram real**

```python
# tests/test_bot_runtime.py
import asyncio
import unittest

from ofertas.bot_interativo import BotRuntime


class FakeUpdater:
    def __init__(self, calls): self.calls = calls
    async def start_polling(self, **_): self.calls.append("updater.start")
    async def stop(self): self.calls.append("updater.stop")


class FakeApplication:
    def __init__(self):
        self.calls = []
        self.updater = FakeUpdater(self.calls)
    async def initialize(self): self.calls.append("app.initialize")
    async def start(self): self.calls.append("app.start")
    async def stop(self): self.calls.append("app.stop")
    async def shutdown(self): self.calls.append("app.shutdown")


class BotRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_stop_gracioso(self):
        app = FakeApplication()
        runtime = BotRuntime(lambda: app)
        await runtime.start()
        await runtime.stop()
        self.assertEqual(app.calls, [
            "app.initialize", "updater.start", "app.start",
            "updater.stop", "app.stop", "app.shutdown",
        ])
```

- [ ] **Passo 2: executar e confirmar falha por ausência de `BotRuntime`**

Executar: `uv run python -m unittest tests.test_bot_runtime -v`.

- [ ] **Passo 3: extrair a construção da aplicação existente**

Mover a montagem de handlers e job queue hoje dentro de `rodar()` para `criar_aplicacao()`. `rodar()` deverá apenas validar token, obter a aplicação e executar `run_polling` como antes.

- [ ] **Passo 4: implementar o runtime assíncrono idempotente**

```python
class BotRuntime:
    def __init__(self, factory=criar_aplicacao):
        self._factory = factory
        self._app = None
        self._lock = asyncio.Lock()

    @property
    def running(self):
        return self._app is not None

    async def start(self):
        async with self._lock:
            if self._app is not None:
                return False
            app = self._factory()
            await app.initialize()
            await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            await app.start()
            self._app = app
            return True

    async def stop(self):
        async with self._lock:
            if self._app is None:
                return False
            app, self._app = self._app, None
            await app.updater.stop()
            await app.stop()
            await app.shutdown()
            return True
```

Se uma etapa de `start()` falhar, executar as etapas de limpeza que já tiverem sido inicializadas e deixar `_app` como `None`.

- [ ] **Passo 5: testar idempotência e falha parcial**

Adicionar testes que chamem `start()` e `stop()` duas vezes e um fake que falhe em `app.start`. Confirmar uma única sequência de limpeza e `running == False`.

- [ ] **Passo 6: executar regressão**

Executar:

```powershell
uv run python -m unittest tests.test_bot_runtime -v
uv run python -m compileall -q ofertas tests
```

---

### Tarefa 4: Protocolo desktop, logs e ações permitidas

**Arquivos:**

- Criar: `ofertas/desktop_protocol.py`
- Criar: `ofertas/desktop_service.py`
- Criar: `tests/test_desktop_protocol.py`
- Criar: `tests/test_desktop_service.py`
- Modificar: `ofertas/main.py`

**Interfaces:**

- Consome: `BotRuntime`, `read_settings`, `write_settings` e `reload_config`.
- Produz protocolo NDJSON com `request`, `response`, `event`, `log` e `state`.
- Produz: `DesktopService.handle(request: dict) -> dict`.
- Produz: comando interno `python -m ofertas desktop`.

- [ ] **Passo 1: testar parsing, correlação e sanitização**

```python
# tests/test_desktop_protocol.py
import unittest

from ofertas.desktop_protocol import ProtocolError, parse_request, sanitize


class ProtocolTests(unittest.TestCase):
    def test_rejeita_comando_desconhecido(self):
        with self.assertRaises(ProtocolError):
            parse_request('{"id":"1","command":"powershell","payload":{}}')

    def test_remove_token_e_cookie(self):
        value = sanitize("token=123456789:ABC cookie=session-secret")
        self.assertNotIn("123456789:ABC", value)
        self.assertNotIn("session-secret", value)
```

- [ ] **Passo 2: implementar envelope e lista fixa de comandos**

```python
class ProtocolError(ValueError):
    pass


class PublicError(RuntimeError):
    """Erro seguro para ser apresentado diretamente ao usuário."""
    pass


ALLOWED_COMMANDS = {
    "get_status", "get_settings", "save_settings", "start_bot", "stop_bot",
    "run_cycle", "test_source", "install_browser", "start_ml_login",
    "get_history", "import_legacy_data", "shutdown",
}


def parse_request(line):
    try:
        request = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ProtocolError("Mensagem JSON inválida.") from exc
    if request.get("command") not in ALLOWED_COMMANDS:
        raise ProtocolError("Operação não permitida.")
    if not isinstance(request.get("payload", {}), dict):
        raise ProtocolError("O conteúdo da operação deve ser um objeto.")
    return request
```

Toda saída deve ser uma linha UTF-8 gerada por `json.dumps(..., ensure_ascii=False)`. Respostas devem repetir `id`. Logs devem conter `timestamp`, `level`, `source` e `message`.

- [ ] **Passo 3: testar exclusão mútua e erro seguro**

`tests/test_desktop_service.py` deve criar fontes falsas e provar que:

- um segundo `test_source` recebe estado ocupado;
- `start_ml_login` é recusado enquanto outra ação de perfil ML está ativa;
- exceção interna vira resposta `ok: false` sem traceback nem segredo na mensagem pública;
- o traceback sanitizado aparece somente no evento de log técnico.

- [ ] **Passo 4: implementar `DesktopService`**

Usar `asyncio.Lock` para o bot, um lock de ação geral e um lock específico do perfil ML. Ações bloqueantes existentes devem rodar com `asyncio.to_thread`. `run_cycle` só poderá postar quando disparado explicitamente pela interface; testes usarão um bot falso.

```python
async def handle(self, request):
    command = request["command"]
    handler = self._handlers[command]
    try:
        result = await handler(request.get("payload") or {})
        return {"type": "response", "id": request.get("id"), "ok": True, "result": result}
    except PublicError as exc:
        return {"type": "response", "id": request.get("id"), "ok": False, "error": str(exc)}
    except Exception:
        self.emit_log("ERROR", "backend", sanitize(traceback.format_exc()))
        return {"type": "response", "id": request.get("id"), "ok": False,
                "error": "A operação falhou. Consulte o console para detalhes."}
```

- [ ] **Passo 5: criar o loop NDJSON e redirecionar `print`**

O comando `desktop` deve reservar `stdout` exclusivamente ao protocolo. `print` e logging de bibliotecas devem ser encaminhados como eventos sanitizados. Leitura de `stdin` deve usar `asyncio.to_thread(sys.stdin.readline)` para não bloquear bot e ações.

- [ ] **Passo 6: executar o smoke test do protocolo sem credenciais**

Executar:

```powershell
'{"id":"1","command":"get_status","payload":{}}' | uv run python -m ofertas desktop
```

Esperado: apenas linhas JSON válidas; pelo menos uma resposta com `id` igual a `1`; nenhum valor real do `.env`.

- [ ] **Passo 7: executar a suíte Python acumulada**

Executar: `uv run python -m unittest discover -s tests -v`  
Esperado: todos os testes aprovados sem acesso de rede.

---

### Tarefa 5: Histórico e migração transacional

**Arquivos:**

- Criar: `ofertas/migration.py`
- Criar: `tests/test_migration.py`
- Modificar: `ofertas/db.py`
- Modificar: `ofertas/desktop_service.py`

**Interfaces:**

- Produz: `db.listar(limit: int = 100, offset: int = 0) -> list[dict]`.
- Produz: `inspect_legacy(source: Path) -> MigrationReport`.
- Produz: `import_legacy(source: Path, destination: RuntimePaths) -> MigrationReport`.

- [ ] **Passo 1: testar paginação de histórico sem alterar o banco real**

Criar um SQLite temporário, registrar três ofertas com datas controladas e confirmar ordenação decrescente e paginação `limit/offset`.

- [ ] **Passo 2: implementar consulta parametrizada**

```python
def listar(limit=100, offset=0):
    limit = min(max(int(limit), 1), 500)
    offset = max(int(offset), 0)
    with _conn() as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT uid, plataforma, titulo, preco, postada_em "
            "FROM postadas ORDER BY postada_em DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [dict(row) for row in rows]
```

- [ ] **Passo 3: testar migração válida e integridade**

O teste deve criar origem com `.env`, YAML contendo “Eletrônicos”, JSON, SQLite com 99 linhas falsas e diretório `ml_profile`. Depois deve confirmar cópia, `PRAGMA integrity_check == "ok"`, contagem 99 e origem inalterada.

Definir o relatório usado pelas duas operações:

```python
@dataclass(frozen=True)
class MigrationReport:
    source: str
    offers: int
    has_ml_profile: bool
    browser_reinstall_required: bool
    copied: tuple[str, ...]
    warnings: tuple[str, ...]
```

- [ ] **Passo 4: testar falha e interrupção**

Adicionar casos com YAML inválido, SQLite corrompido e função de cópia que lança exceção no meio. Em todos, o diretório ativo de destino deve permanecer igual ao estado anterior e a origem deve manter o mesmo hash.

- [ ] **Passo 5: implementar staging e ativação atômica**

A importação deve criar staging dentro do diretório pai do destino, copiar apenas a lista autorizada, validar e então substituir cada arquivo/diretório. Para diretórios, renomear o destino antigo para uma pasta de backup da própria operação, ativar o novo e apagar o backup somente após sucesso. Se houver falha, restaurar o backup.

Não seguir links simbólicos nem caminhos que escapem da origem selecionada. `pw-browsers` só será aceito quando contiver o marcador de versão esperado pelo Playwright instalado; caso contrário, o relatório retornará `browser_reinstall_required: true`.

- [ ] **Passo 6: integrar `get_history` e `import_legacy_data`**

O serviço deve emitir progresso com etapas `inspecting`, `copying`, `validating` e `activating`. A resposta final deve incluir contagens e avisos, nunca valores de credenciais.

- [ ] **Passo 7: executar testes**

Executar:

```powershell
uv run python -m unittest tests.test_migration -v
uv run python -m unittest discover -s tests -v
```

---

### Tarefa 6: Executável Python e Playwright sob demanda

**Arquivos:**

- Criar: `ofertas/frozen_entry.py`
- Criar: `packaging/backend.spec`
- Criar: `scripts/build-backend.ps1`
- Modificar: `pyproject.toml`
- Modificar: `ofertas/main.py`
- Modificar: `ofertas/sources/mercadolivre.py`
- Modificar: `.gitignore`

**Interfaces:**

- Produz: `dist/backend/bot-ofertas-backend.exe`.
- Consome: `BOT_OFERTAS_HOME` definido pelo Tauri.
- Mantém: `python -m ofertas ...` em desenvolvimento.

- [ ] **Passo 1: adicionar PyInstaller somente ao grupo de desenvolvimento**

```toml
[dependency-groups]
dev = [
    "pyinstaller==6.22.3",
]
```

Executar `uv lock` e `uv sync --dev`.

- [ ] **Passo 2: criar a entrada congelada**

```python
# ofertas/frozen_entry.py
import multiprocessing

from .main import main


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
```

- [ ] **Passo 3: criar a receita `onedir`**

`packaging/backend.spec` deve usar `collect_all("playwright")`, incluir `config.yaml` e `.env.example` como padrões, excluir `data`, `.env` e caches, produzir um executável de console chamado `bot-ofertas-backend` e uma pasta `dist/backend`. O modo console é necessário para o protocolo por pipes; quem evita a janela é o supervisor Tauri. O diretório inteiro, inclusive `_internal`, será preservado no bundle Tauri.

- [ ] **Passo 4: tornar a instalação do Chromium compatível com executável congelado**

Substituir a chamada `sys.executable -m playwright install chromium` por uma função que localize o driver empacotado pelo Playwright e execute o comando oficial com `PLAYWRIGHT_BROWSERS_PATH` apontando para `PATHS.data_dir / "pw-browsers"`. Manter o comando CLI `instalar-navegador` chamando a mesma função.

- [ ] **Passo 5: criar build PowerShell reproduzível**

```powershell
# scripts/build-backend.ps1
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    uv sync --dev --frozen
    uv run pyinstaller --noconfirm --clean packaging/backend.spec
    & .\dist\backend\bot-ofertas-backend.exe check
    if ($LASTEXITCODE -ne 0) { throw 'Smoke test do backend falhou.' }
} finally {
    Pop-Location
}
```

O smoke `check` poderá retornar pendências de configuração, mas precisa finalizar sem falha de importação ou arquivo ausente; ajustar o comando para separar pendência operacional de erro técnico.

- [ ] **Passo 6: impedir rastreamento de artefatos**

Adicionar a `.gitignore`:

```gitignore
build/
dist/
*.spec.bak
desktop/node_modules/
desktop/src-tauri/target/
desktop/src-tauri/binaries/
```

- [ ] **Passo 7: construir e validar ausência de dados privados**

Executar:

```powershell
.\scripts\build-backend.ps1
rg -a -l 'TELEGRAM_BOT_TOKEN=.+|SHOPEE_APP_SECRET=.+|AMAZON_CREDENTIAL_SECRET=.+' dist\backend
```

Esperado: build concluído e `rg` sem correspondência preenchida. Iniciar `bot-ofertas-backend.exe desktop`, enviar `get_status` e confirmar JSON UTF-8 válido.

---

### Tarefa 7: Shell Tauri e supervisor do sidecar

**Arquivos:**

- Criar: `desktop/package.json`
- Criar: `desktop/src-tauri/Cargo.toml`
- Criar: `desktop/src-tauri/build.rs`
- Criar: `desktop/src-tauri/tauri.conf.json`
- Criar: `desktop/src-tauri/capabilities/default.json`
- Criar: `desktop/src-tauri/src/main.rs`
- Criar: `desktop/src-tauri/src/backend.rs`
- Criar: `desktop/src-tauri/src/process_state.rs`
- Criar: `desktop/ui/index.html`

**Interfaces:**

- Produz comandos Tauri: `backend_request`, `backend_status`, `show_main_window`, `quit_app`.
- Produz eventos: `backend://log`, `backend://state`, `backend://progress`.
- Consome sidecar `binaries/bot-ofertas-backend-x86_64-pc-windows-msvc.exe`.

- [ ] **Passo 1: criar o projeto mínimo sem framework frontend**

`desktop/package.json`:

```json
{
  "name": "bot-ofertas-desktop",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "tauri": "tauri",
    "test": "node --test ui/*.test.mjs"
  },
  "dependencies": {
    "@tauri-apps/api": "2.11.1",
    "@tauri-apps/plugin-dialog": "2.7.3"
  },
  "devDependencies": {
    "@tauri-apps/cli": "2.11.5"
  }
}
```

- [ ] **Passo 2: fixar Tauri 2 estável no Cargo**

Usar `tauri = { version = "2.11.6", features = ["tray-icon"] }`, `tauri-build = "2.6.3"`, `tauri-plugin-shell = "2.3.6"`, `serde`, `serde_json`, `tokio` e `uuid`. Não usar Tauri 3 alpha.

- [ ] **Passo 3: configurar janela, CSP e sidecar**

`tauri.conf.json` deve definir `productName`, identificador `br.com.kaiodiniz.botofertas`, janela inicial 1180×760 com mínimo 900×620, `frontendDist: "../ui"`, CSP sem `unsafe-eval`, `externalBin: ["binaries/backend/bot-ofertas-backend"]`, recursos para `binaries/backend/_internal/**` e `bundle.targets: ["nsis"]`. Nesta tarefa, usar ícones temporários gerados pelo CLI; a fonte definitiva entra na Tarefa 9.

- [ ] **Passo 4: testar a máquina de estados pura**

```rust
#[test]
fn falha_repetida_para_no_limite() {
    let mut state = ProcessState::default();
    assert!(state.record_crash().should_restart);
    assert!(state.record_crash().should_restart);
    assert!(!state.record_crash().should_restart);
    assert_eq!(state.status, BackendStatus::Failed);
}
```

Também testar transições `Stopped -> Starting -> Running -> Stopping -> Stopped` e rejeição de transição duplicada.

Os tipos compartilhados serão definidos em `process_state.rs`:

```rust
#[derive(Clone, Debug, Default, PartialEq)]
pub enum BackendStatus { Starting, Running, Stopping, Failed, #[default] Stopped }

#[derive(Default)]
pub struct ProcessState {
    pub status: BackendStatus,
    pub crash_times: std::collections::VecDeque<std::time::Instant>,
}

pub struct RestartDecision { pub should_restart: bool }
```

- [ ] **Passo 5: implementar supervisor e correlação**

`backend.rs` deve:

- iniciar o sidecar com `BOT_OFERTAS_HOME` apontando para o diretório local do app;
- guardar o canal de escrita do filho;
- atribuir UUID a cada pedido;
- manter `HashMap<Uuid, oneshot::Sender<Response>>`;
- parsear cada linha de stdout;
- resolver respostas pelo ID;
- emitir logs, progresso e estado à janela;
- transformar linha inválida em log técnico, sem encerrar a aplicação;
- aguardar no máximo dez segundos por resposta comum;
- aguardar até sessenta segundos no encerramento antes de matar o sidecar;
- permitir no máximo dois reinícios automáticos em cinco minutos.

Definir `BackendSupervisor` com `Mutex<ProcessState>`, canal de escrita do filho e `HashMap<Uuid, oneshot::Sender<Result<serde_json::Value, BackendError>>>`. `BackendError` terá apenas `Unavailable`, `Timeout` e `Protocol`; `public_message()` mapeará cada variante para uma mensagem em português sem detalhes internos.

- [ ] **Passo 6: expor comandos Rust restritos**

```rust
#[tauri::command]
async fn backend_request(
    state: tauri::State<'_, BackendSupervisor>,
    command: String,
    payload: serde_json::Value,
) -> Result<serde_json::Value, String> {
    state.request(&command, payload).await.map_err(|error| error.public_message())
}
```

O supervisor deve validar `command` contra a mesma lista permitida antes de escrever no sidecar. Não expor `tauri-plugin-shell` diretamente ao JavaScript.

- [ ] **Passo 7: executar testes e abrir a janela vazia**

Executar:

```powershell
New-Item -ItemType Directory -Force desktop\src-tauri\binaries\backend | Out-Null
Copy-Item -Recurse -Force dist\backend\* desktop\src-tauri\binaries\backend
Rename-Item desktop\src-tauri\binaries\backend\bot-ofertas-backend.exe bot-ofertas-backend-x86_64-pc-windows-msvc.exe
Set-Location desktop\src-tauri
cargo test
Set-Location ..
npm install
npm run tauri dev
```

Esperado: testes Rust aprovados, janela aberta sem console externo adicional e backend emitindo estado conectado.

---

### Tarefa 8: Interface, navegação e console operacional

**Arquivos:**

- Criar: `desktop/ui/styles.css`
- Criar: `desktop/ui/state.mjs`
- Criar: `desktop/ui/state.test.mjs`
- Criar: `desktop/ui/app.js`
- Modificar: `desktop/ui/index.html`

**Interfaces:**

- Consome comandos e eventos da Tarefa 7.
- Produz cinco telas: Visão geral, Operação, Configurações, Histórico e Console.
- Produz painel inferior de console recolhível.

- [ ] **Passo 1: testar estado da interface com `node:test`**

```javascript
// desktop/ui/state.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { createState, appendLog, applyBackendState } from "./state.mjs";

test("limita o console às 1000 linhas mais recentes", () => {
  let state = createState();
  for (let i = 0; i < 1005; i++) state = appendLog(state, { message: `linha ${i}` });
  assert.equal(state.logs.length, 1000);
  assert.equal(state.logs[0].message, "linha 5");
});

test("estado desconectado desabilita ações", () => {
  const state = applyBackendState(createState(), { connected: false, botRunning: false });
  assert.equal(state.canStartBot, false);
});
```

- [ ] **Passo 2: implementar estado puro**

`state.mjs` não deve acessar DOM nem APIs Tauri. Ele deve normalizar status, limitar logs, aplicar filtros e calcular habilitação dos botões. Isso permite testar toda regra de apresentação sem WebView.

- [ ] **Passo 3: criar HTML semântico e acessível**

Usar `nav`, `main`, `section`, `form`, `label`, `button` e uma região `aria-live="polite"` para estado. O console deve usar `role="log"` e `aria-live="off"` para não ler centenas de mensagens automaticamente. Todos os botões de ícone precisam de texto acessível.

- [ ] **Passo 4: implementar temas e layout responsivo**

Usar variáveis CSS, `prefers-color-scheme`, foco visível, contraste de erro/sucesso que inclua ícone e texto, sidebar recolhível abaixo de 980 px e altura mínima funcional de 620 px.

- [ ] **Passo 5: conectar comandos e eventos**

`app.js` deve usar apenas `invoke` e `listen` de `@tauri-apps/api`. Ao carregar:

1. assinar eventos;
2. buscar estado;
3. buscar configurações mascaradas;
4. buscar primeira página do histórico;
5. renderizar;
6. mostrar erro recuperável se o backend estiver indisponível.

- [ ] **Passo 6: implementar formulários e ações**

Incluir:

- salvar e salvar/reiniciar;
- iniciar/parar bot;
- ciclo manual com confirmação de que pode publicar;
- teste individual de fonte;
- instalação de navegador;
- login ML com instruções;
- paginação do histórico;
- filtros, busca, limpeza visual e exportação do console.

Segredo mascarado usa `SECRET_SET`; campo intocado não é enviado como substituição. Remoção exige botão e confirmação específicos.

- [ ] **Passo 7: executar testes e inspeção visual local**

Executar:

```powershell
Set-Location desktop
npm test
npm run tauri dev
```

Verificar teclado, foco, textos com “Configuração”, “Eletrônicos”, “Próxima execução” e emojis. Confirmar ausência de mojibake visual.

---

### Tarefa 9: Bandeja, instância única e autostart

**Arquivos:**

- Criar: `desktop/src-tauri/src/tray.rs`
- Criar: `desktop/assets/icon.svg`
- Modificar: `desktop/src-tauri/src/main.rs`
- Modificar: `desktop/src-tauri/Cargo.toml`
- Modificar: `desktop/src-tauri/tauri.conf.json`
- Modificar: `desktop/ui/app.js`

**Interfaces:**

- Produz comandos: `get_preferences`, `set_preferences`.
- Preferências: `startWithWindows: bool`, `autoStartBot: bool`, ambas `false` por padrão.

- [ ] **Passo 1: adicionar plugins estáveis**

Adicionar `tauri-plugin-autostart = "2.5.1"` e `tauri-plugin-single-instance = "2.4.5"` ao Cargo. Inicializar single-instance antes dos demais plugins; a segunda abertura deve mostrar e focar a janela existente.

- [ ] **Passo 2: criar ícone vetorial simples**

`desktop/assets/icon.svg` deve usar fundo laranja, etiqueta branca e chama estilizada, sem texto pequeno. Gerar tamanhos Tauri com:

```powershell
Set-Location desktop
npm run tauri icon assets/icon.svg
```

- [ ] **Passo 3: implementar menu da bandeja**

Itens exatos: “Abrir aplicativo”, “Iniciar bot” ou “Parar bot”, “Executar ciclo agora”, “Mostrar último erro” e “Sair completamente”. Atualizar rótulo de iniciar/parar quando o estado mudar.

- [ ] **Passo 4: interceptar fechamento da janela**

No evento de fechamento, impedir saída e ocultar a janela, exceto quando uma flag interna `quitting` estiver ativa. Na primeira vez, emitir notificação interna “O Bot de Ofertas continua na bandeja”.

- [ ] **Passo 5: implementar saída completa**

Definir `quitting`, desabilitar ações novas, enviar `shutdown`, aguardar confirmação por até sessenta segundos, matar o sidecar somente após timeout e então encerrar o Tauri.

- [ ] **Passo 6: implementar preferências independentes**

`startWithWindows` chama o plugin autostart. `autoStartBot` é persistido nas configurações do aplicativo e só inicia o bot depois que o backend informar pronto. Passar `--minimized` no autostart para iniciar diretamente na bandeja.

- [ ] **Passo 7: validar ciclo de vida real**

Executar `npm run tauri dev` e verificar:

- segunda instância foca a primeira;
- X oculta sem encerrar;
- menu reabre;
- iniciar/parar funciona pela bandeja;
- sair não deixa `bot-ofertas-backend.exe` ativo;
- as duas preferências começam desmarcadas.

---

### Tarefa 10: Assistente de primeiro uso e importação

**Arquivos:**

- Modificar: `desktop/ui/index.html`
- Modificar: `desktop/ui/styles.css`
- Modificar: `desktop/ui/app.js`
- Modificar: `desktop/src-tauri/src/main.rs`
- Modificar: `desktop/src-tauri/Cargo.toml`
- Modificar: `desktop/src-tauri/capabilities/default.json`
- Modificar: `desktop/package.json`

**Interfaces:**

- Consome: `inspect_legacy` e `import_legacy_data` da Tarefa 5.
- Produz: seleção nativa de diretório somente para o fluxo de importação.

- [ ] **Passo 1: adicionar seletor de diretório restrito**

Adicionar `tauri-plugin-dialog = "2.7.3"` ao Rust e `@tauri-apps/plugin-dialog = "2.7.3"` ao frontend. Autorizar somente abertura de diretório na capability. O frontend recebe apenas o caminho escolhido e o encaminha para `import_legacy_data`; não recebe acesso geral ao sistema de arquivos.

- [ ] **Passo 2: criar o assistente de primeira execução**

Etapas:

1. apresentação;
2. “Começar limpo” ou “Importar instalação existente”;
3. inspeção e resumo sem segredos;
4. confirmação;
5. progresso;
6. resultado e próximo passo.

O resumo desta máquina deve poder mostrar “99 ofertas no histórico”, presença da sessão ML e necessidade ou não de reinstalar o navegador.

- [ ] **Passo 3: impedir navegação durante ativação**

Enquanto a etapa `activating` estiver ativa, desabilitar fechar assistente e iniciar operações. Se o aplicativo for encerrado externamente, a próxima abertura deve detectar staging incompleto, removê-lo com segurança e preservar a instalação ativa anterior.

- [ ] **Passo 4: validar com uma cópia temporária, nunca com a origem real primeiro**

Copiar a estrutura atual para um diretório temporário excluindo os 701 MB de `pw-browsers`, apontar o assistente para a cópia e confirmar configuração, 99 registros e sessão. Só após esse ensaio usar a pasta real como origem, permanecendo uma operação de leitura/cópia.

---

### Tarefa 11: Instalador NSIS e documentação

**Arquivos:**

- Criar: `scripts/build-desktop.ps1`
- Modificar: `desktop/src-tauri/tauri.conf.json`
- Modificar: `README.md`
- Modificar: `COMECE_AQUI.txt`
- Modificar: `.gitignore`

**Interfaces:**

- Produz: instalador x64 em `desktop/src-tauri/target/release/bundle/nsis/`.

- [ ] **Passo 1: configurar o bundle Windows**

Definir NSIS x64, idioma `PortugueseBR`, instalação por usuário, atalho no Menu Iniciar e `webviewInstallMode` como `embedBootstrapper`. Não exigir privilégios administrativos para a instalação padrão.

- [ ] **Passo 2: criar pipeline local de build**

`scripts/build-desktop.ps1` deve:

1. validar `rustc`, `node`, `npm` e `uv`;
2. executar testes Python;
3. construir backend;
4. copiar sidecar para o nome com target triple exigido pelo Tauri;
5. executar `npm ci` quando houver lockfile;
6. executar testes JS;
7. executar `cargo test`;
8. executar `npm run tauri build`;
9. localizar e imprimir o caminho do instalador;
10. falhar imediatamente em qualquer etapa.

- [ ] **Passo 3: atualizar documentação para o aplicativo**

O README deve colocar o instalador como caminho recomendado, documentar bandeja, autostart, migração, localização dos dados, login ML, console e desinstalação. Manter uma seção separada “Desenvolvimento e CLI”.

`COMECE_AQUI.txt` deve preservar UTF-8 e orientar primeiro a instalar/abrir o aplicativo, removendo a recomendação de desativar globalmente o Smart App Control. Explicar SmartScreen sem instruir o usuário a enfraquecer a segurança do Windows.

- [ ] **Passo 4: construir o instalador**

Executar: `.\scripts\build-desktop.ps1`  
Esperado: instalador NSIS x64 criado e caminho exibido.

- [ ] **Passo 5: inspecionar conteúdo do bundle**

Extrair o instalador em diretório temporário ou listar seu conteúdo e procurar `.env`, `ofertas.db`, `ml_profile`, tokens conhecidos e `pw-browsers`. Nenhum deles pode estar presente. Confirmar que o backend, WebView2 bootstrapper e recursos estáticos estão presentes.

---

### Tarefa 12: Validação real, SemVer e notas da versão

**Arquivos:**

- Criar: `RELEASE_NOTES.md`
- Modificar: `pyproject.toml`
- Modificar: `ofertas/__init__.py`
- Modificar: `desktop/package.json`
- Modificar: `desktop/src-tauri/Cargo.toml`
- Modificar: `desktop/src-tauri/tauri.conf.json`
- Atualizar mecanicamente: `uv.lock`, `desktop/package-lock.json`, `desktop/src-tauri/Cargo.lock`

**Interfaces:**

- Produz uma única versão coerente em todos os artefatos.

- [ ] **Passo 1: executar toda a verificação automatizada antes do bump**

```powershell
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q ofertas tests
Set-Location desktop
npm test
Set-Location src-tauri
cargo test
Set-Location ..\..
.\scripts\build-desktop.ps1
```

Todos devem passar antes de editar qualquer versão.

- [ ] **Passo 2: instalar e exercitar o aplicativo real**

Validar em Windows x64:

- instalação e abertura sem console externo;
- importação dos dados atuais com 99 registros;
- dashboard e histórico;
- minimizar/restaurar pela bandeja;
- preferência de autostart do app;
- preferência independente de autostart do bot;
- teste de ML, Shopee e Amazon sem publicação;
- login ML no Chrome real;
- encerramento completo sem processo órfão;
- desinstalação preservando dados.

Registrar como não verificado qualquer fluxo externo que não possa ser exercitado. Não executar ciclo que possa publicar sem autorização explícita.

- [ ] **Passo 3: aplicar SemVer uma única vez**

Somente após os passos anteriores passarem, trocar exatamente:

```text
0.1.0 → 0.2.0
```

Atualizar os cinco arquivos de versão, regenerar locks e confirmar com:

```powershell
rg -n 'version.*0\.2\.0|"version": "0\.2\.0"|__version__ = "0\.2\.0"' pyproject.toml ofertas desktop
```

- [ ] **Passo 4: escrever notas da versão**

`RELEASE_NOTES.md` deve registrar:

```markdown
# 0.2.0 — Aplicativo desktop

- Aplicativo Tauri para Windows x64 com instalador NSIS.
- Console operacional e logs ao vivo dentro do aplicativo.
- Bandeja, inicialização com o Windows e início automático do bot configuráveis.
- Migração segura de configurações, histórico e sessão do Mercado Livre.
- Backend Python e CLI existentes preservados.

## Versionamento

Versão: 0.1.0 → 0.2.0  
Tipo: MINOR  
Motivo: adição do aplicativo desktop, instalador e gerenciamento operacional sem remoção intencional das funcionalidades existentes.
```

- [ ] **Passo 5: reconstruir depois do bump e conferir metadados**

Executar novamente `.\scripts\build-desktop.ps1`. Confirmar versão `0.2.0` nas propriedades do executável, metadados do instalador, backend `__version__` e tela “Sobre”.

- [ ] **Passo 6: produzir relatório final honesto**

Informar:

- instalador gerado e caminho;
- testes executados e resultados;
- fluxos externos verificados e não verificados;
- dados migrados e contagens;
- confirmação de ausência de segredos no bundle;
- versão anterior, nova versão, nível e motivo;
- que nenhum commit, push, tag ou publicação foi realizado.

---

## Ordem obrigatória

Executar as tarefas de 1 a 12 na ordem. Não iniciar Tauri antes de os caminhos, settings, ciclo de vida e protocolo Python estarem cobertos. Não executar importação contra os dados reais antes do ensaio com cópia temporária. Não incrementar a versão antes da validação real aplicável e do build do instalador.
