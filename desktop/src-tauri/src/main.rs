#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod backend;
mod tray;

use backend::Backend;
use tauri::{Manager, WindowEvent};
use tauri_plugin_autostart::ManagerExt;
use tauri_plugin_dialog::DialogExt;

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
        app.autolaunch().enable()
    } else {
        app.autolaunch().disable()
    }
    .map_err(|e| e.to_string())
}

#[tauri::command]
fn choose_legacy_folder(app: tauri::AppHandle) -> Option<String> {
    app.dialog()
        .file()
        .blocking_pick_folder()
        .map(|path| path.to_string())
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
        .manage(Backend::new())
        .invoke_handler(tauri::generate_handler![
            backend_request,
            show_main_window,
            get_autostart,
            set_autostart,
            choose_legacy_folder,
            quit_app
        ])
        .setup(|app| {
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
