use std::{
    collections::HashMap,
    io::{BufRead, BufReader, Write},
    process::{Child, ChildStdin, Command, Stdio},
    sync::Mutex,
    time::Duration,
};
use tauri::{AppHandle, Emitter, Manager};
use tokio::sync::oneshot;

pub struct Backend {
    stdin: Mutex<Option<ChildStdin>>,
    child: Mutex<Option<Child>>,
    pending: Mutex<HashMap<String, oneshot::Sender<serde_json::Value>>>,
}

impl Backend {
    pub fn new() -> Self {
        Self {
            stdin: Mutex::new(None),
            child: Mutex::new(None),
            pending: Mutex::new(HashMap::new()),
        }
    }

    pub fn start(&self, app: &AppHandle) -> Result<(), String> {
        let resource = app
            .path()
            .resource_dir()
            .map_err(|e| e.to_string())?
            .join("bot-ofertas-backend.exe");
        let mut command = if resource.exists() {
            let mut cmd = Command::new(resource);
            cmd.arg("desktop");
            cmd
        } else {
            let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
            let mut cmd = Command::new("uv");
            cmd.args(["run", "python", "-m", "ofertas", "desktop"])
                .current_dir(root);
            cmd
        };
        let data_dir = app.path().app_local_data_dir().map_err(|e| e.to_string())?;
        std::fs::create_dir_all(&data_dir).map_err(|e| e.to_string())?;
        command
            .env("BOT_OFERTAS_HOME", data_dir)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x08000000);
        }
        let mut child = command
            .spawn()
            .map_err(|e| format!("Não foi possível iniciar o backend: {e}"))?;
        *self.stdin.lock().unwrap() = child.stdin.take();
        let stdout = child.stdout.take().ok_or("Backend sem stdout")?;
        let stderr = child.stderr.take().ok_or("Backend sem stderr")?;
        *self.child.lock().unwrap() = Some(child);

        let app_out = app.clone();
        std::thread::spawn(move || {
            for line in BufReader::new(stdout).lines().map_while(Result::ok) {
                match serde_json::from_str::<serde_json::Value>(&line) {
                    Ok(value) => {
                        if value.get("type").and_then(|v| v.as_str()) == Some("response") {
                            if let Some(id) = value.get("id").and_then(|v| v.as_str()) {
                                if let Some(sender) = app_out
                                    .state::<Backend>()
                                    .pending
                                    .lock()
                                    .unwrap()
                                    .remove(id)
                                {
                                    let _ = sender.send(value);
                                    continue;
                                }
                            }
                        }
                        let event = match value.get("type").and_then(|v| v.as_str()) {
                            Some("log") => "backend://log",
                            Some("state") | Some("ready") => "backend://state",
                            _ => "backend://event",
                        };
                        let _ = app_out.emit(event, value);
                    }
                    Err(_) => {
                        let _ = app_out.emit(
                            "backend://log",
                            serde_json::json!({"level":"ERROR","source":"protocol","message":line}),
                        );
                    }
                }
            }

            let backend = app_out.state::<Backend>();
            let pending = std::mem::take(&mut *backend.pending.lock().unwrap());
            for (_, sender) in pending {
                let _ = sender.send(serde_json::json!({
                    "type": "response",
                    "ok": false,
                    "error": "Backend desconectado."
                }));
            }
            let _ = app_out.emit(
                "backend://state",
                serde_json::json!({
                    "connected": false,
                    "ready": false,
                    "botRunning": false,
                    "actionRunning": false
                }),
            );
        });
        let app_err = app.clone();
        std::thread::spawn(move || {
            for line in BufReader::new(stderr).lines().map_while(Result::ok) {
                let _ = app_err.emit(
                    "backend://log",
                    serde_json::json!({"level":"ERROR","source":"backend","message":line}),
                );
            }
        });
        Ok(())
    }

    pub async fn request(
        &self,
        command: String,
        payload: serde_json::Value,
    ) -> Result<serde_json::Value, String> {
        const ALLOWED: &[&str] = &[
            "get_status",
            "get_settings",
            "save_settings",
            "start_bot",
            "stop_bot",
            "run_cycle",
            "test_source",
            "install_browser",
            "start_ml_login",
            "get_history",
            "import_legacy_data",
            "shutdown",
        ];
        if !ALLOWED.contains(&command.as_str()) {
            return Err("Operação não permitida.".into());
        }
        let id = uuid::Uuid::new_v4().to_string();
        let (sender, receiver) = oneshot::channel();
        self.pending.lock().unwrap().insert(id.clone(), sender);
        let line =
            serde_json::json!({"id":id,"command":command,"payload":payload}).to_string() + "\n";
        if let Some(stdin) = self.stdin.lock().unwrap().as_mut() {
            if let Err(error) = stdin.write_all(line.as_bytes()).and_then(|_| stdin.flush()) {
                self.pending.lock().unwrap().remove(&id);
                return Err(error.to_string());
            }
        } else {
            self.pending.lock().unwrap().remove(&id);
            return Err("Backend desconectado.".into());
        }
        let long_running = [
            "run_cycle",
            "test_source",
            "install_browser",
            "start_ml_login",
            "import_legacy_data",
        ];
        let timeout = if long_running.contains(&command.as_str()) {
            Duration::from_secs(1800)
        } else {
            Duration::from_secs(60)
        };
        let response = match tokio::time::timeout(timeout, receiver).await {
            Ok(result) => result.map_err(|_| "Backend desconectado.".to_string())?,
            Err(_) => {
                self.pending.lock().unwrap().remove(&id);
                return Err("A operação excedeu o tempo limite.".to_string());
            }
        };
        if response.get("ok").and_then(|v| v.as_bool()) == Some(true) {
            Ok(response
                .get("result")
                .cloned()
                .unwrap_or(serde_json::Value::Null))
        } else {
            Err(response
                .get("error")
                .and_then(|v| v.as_str())
                .unwrap_or("A operação falhou.")
                .to_string())
        }
    }

    pub fn kill(&self) {
        if let Some(child) = self.child.lock().unwrap().as_mut() {
            let _ = child.kill();
        }
    }
}

impl Drop for Backend {
    fn drop(&mut self) {
        self.kill();
    }
}
