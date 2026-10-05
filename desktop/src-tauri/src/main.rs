#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod backend;
mod tray;

use backend::Backend;
use tauri::{Emitter, Manager, WindowEvent};
use tauri_plugin_autostart::ManagerExt;
use tauri_plugin_dialog::DialogExt;
use tauri_plugin_updater::UpdaterExt;

#[cfg(windows)]
fn windows_autostart_command(executable: &std::path::Path) -> String {
    format!("\"{}\" --minimized", executable.display())
}

#[cfg(windows)]
fn repair_windows_autostart(app: &tauri::AppHandle) -> Result<(), String> {
    use winreg::{enums::HKEY_CURRENT_USER, RegKey};

    let executable = std::env::current_exe().map_err(|error| error.to_string())?;
    let command = windows_autostart_command(&executable);
    let key = RegKey::predef(HKEY_CURRENT_USER)
        .open_subkey_with_flags(
            "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run",
            winreg::enums::KEY_SET_VALUE,
        )
        .map_err(|error| error.to_string())?;
    key.set_value(&app.package_info().name, &command)
        .map_err(|error| error.to_string())
}

#[tauri::command]
async fn backend_request(
    state: tauri::State<'_, Backend>,
    command: String,
    payload: serde_json::Value,
) -> Result<serde_json::Value, String> {
    state.request(command, payload).await
}

#[tauri::command]
fn show_main_window(app: tauri::AppHandle) -> Result<(), String> {
    let window = app
        .get_webview_window("main")
        .ok_or("Janela principal não encontrada")?;
    window.show().map_err(|e| e.to_string())?;
    window.set_focus().map_err(|e| e.to_string())
}

#[tauri::command]
fn get_autostart(app: tauri::AppHandle) -> Result<bool, String> {
    app.autolaunch().is_enabled().map_err(|e| e.to_string())
}

#[tauri::command]
fn set_autostart(app: tauri::AppHandle, enabled: bool) -> Result<(), String> {
    if enabled {
        app.autolaunch().enable().map_err(|e| e.to_string())?;
        #[cfg(windows)]
        repair_windows_autostart(&app)?;
        Ok(())
    } else {
        app.autolaunch().disable().map_err(|e| e.to_string())
    }
}

#[tauri::command]
fn get_app_version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

#[tauri::command]
fn choose_legacy_folder(app: tauri::AppHandle) -> Option<String> {
    app.dialog()
        .file()
        .blocking_pick_folder()
        .map(|path| path.to_string())
}

#[tauri::command]
fn choose_responder_media(app: tauri::AppHandle) -> Option<String> {
    app.dialog()
        .file()
        .add_filter("Imagens e vídeos", &["jpg", "jpeg", "png", "webp", "mp4"])
        .blocking_pick_file()
        .map(|path| path.to_string())
}

#[tauri::command]
fn choose_responder_backup(app: tauri::AppHandle) -> Option<String> {
    app.dialog().file().add_filter("Backup SQLite", &["db"]).blocking_pick_file().map(|path| path.to_string())
}

#[tauri::command]
fn save_responder_export(app: tauri::AppHandle, contents: String) -> Result<Option<String>, String> {
    if contents.len() > 4_000_000 { return Err("Arquivo JSON muito grande.".into()); }
    let Some(path) = app.dialog().file().add_filter("JSON", &["json"]).blocking_save_file() else { return Ok(None); };
    std::fs::write(path.as_path().ok_or("Caminho de exportação inválido.")?, contents)
        .map_err(|error| error.to_string())?;
    Ok(Some(path.to_string()))
}

#[tauri::command]
async fn quit_app(app: tauri::AppHandle) {
    let backend = app.state::<Backend>();
    let _ = backend
        .request("shutdown".into(), serde_json::json!({}))
        .await;
    backend.kill();
    app.exit(0);
}

#[tauri::command]
async fn check_for_updates(app: tauri::AppHandle) -> Result<bool, String> {
    let updater = app.updater().map_err(|error| error.to_string())?;
    let Some(update) = updater.check().await.map_err(|error| error.to_string())? else {
        return Ok(false);
    };

    app.emit("update-available", &update.version)
        .map_err(|error| error.to_string())?;
    Ok(true)
}

#[tauri::command]
async fn install_update(app: tauri::AppHandle) -> Result<(), String> {
    let updater = app.updater().map_err(|error| error.to_string())?;
    let Some(update) = updater.check().await.map_err(|error| error.to_string())? else {
        return Err("A atualização não está mais disponível.".into());
    };
    let backend = app.state::<Backend>();
    let was_running = backend
        .request("get_status".into(), serde_json::json!({}))
        .await
        .ok()
        .and_then(|status| status.get("botRunning").and_then(|value| value.as_bool()))
        .unwrap_or(false);
    let _ = backend
        .request("stop_bot".into(), serde_json::json!({}))
        .await;

    let progress_app = app.clone();
    let mut downloaded = 0_u64;
    let bytes = update
        .download(
            move |chunk_length, content_length| {
                downloaded += chunk_length as u64;
                let percent = content_length
                    .filter(|total| *total > 0)
                    .map(|total| downloaded.saturating_mul(100) / total)
                    .unwrap_or(0)
                    .min(100);
                let _ = progress_app.emit("update-progress", percent);
            },
            || {},
        )
        .await;
    let bytes = match bytes {
        Ok(bytes) => bytes,
        Err(error) => {
            if was_running {
                let _ = backend
                    .request("start_bot".into(), serde_json::json!({}))
                    .await;
            }
            let message = error.to_string();
            let _ = app.emit("update-error", &message);
            return Err(message);
        }
    };

    let _ = backend
        .request("shutdown".into(), serde_json::json!({}))
        .await;
    backend.kill();

    if let Err(error) = update.install(bytes) {
        let _ = backend.start(&app);
        if was_running {
            let _ = backend
                .request("start_bot".into(), serde_json::json!({}))
                .await;
        }
        let message = error.to_string();
        let _ = app.emit("update-error", &message);
        return Err(message);
    }
    let _ = app.emit("update-downloaded", ());
    Ok(())
}

#[tauri::command]
async fn restart_app(app: tauri::AppHandle) {
    let backend = app.state::<Backend>();
    let _ = backend
        .request("shutdown".into(), serde_json::json!({}))
        .await;
    backend.kill();
    app.restart();
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            let _ = show_main_window(app.clone());
        }))
        .plugin(
            tauri_plugin_autostart::Builder::new()
                .args(["--minimized"])
                .build(),
        )
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(Backend::new())
        .invoke_handler(tauri::generate_handler![
            backend_request,
            show_main_window,
            get_autostart,
            set_autostart,
            get_app_version,
            choose_legacy_folder,
            choose_responder_media,
            choose_responder_backup,
            save_responder_export,
            quit_app,
            check_for_updates,
            install_update,
            restart_app
        ])
        .setup(|app| {
            #[cfg(windows)]
            if app.autolaunch().is_enabled().unwrap_or(false) {
                let _ = repair_windows_autostart(app.handle());
            }
            app.state::<Backend>().start(app.handle())?;
            tray::build(app)?;
            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                let backend = handle.state::<Backend>();
                if let Ok(settings) = backend
                    .request("get_settings".into(), serde_json::json!({}))
                    .await
                {
                    let auto_start = settings
                        .pointer("/preferences/autoStartBot")
                        .and_then(|value| value.as_bool())
                        .unwrap_or(false);
                    if auto_start {
                        let _ = backend
                            .request("start_bot".into(), serde_json::json!({}))
                            .await;
                    }
                }
            });
            if std::env::args().any(|arg| arg == "--minimized") {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.hide();
                }
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .run(tauri::generate_context!())
        .expect("erro ao executar o Bot de Ofertas");
}

#[cfg(all(test, windows))]
mod tests {
    use super::windows_autostart_command;

    #[test]
    fn caminho_do_autostart_fica_entre_aspas() {
        let command = windows_autostart_command(std::path::Path::new(
            r"C:\Users\Kaio Diniz\AppData\Local\Bot de Ofertas\bot-ofertas-desktop.exe",
        ));
        assert_eq!(
            command,
            r#""C:\Users\Kaio Diniz\AppData\Local\Bot de Ofertas\bot-ofertas-desktop.exe" --minimized"#,
        );
    }
}
