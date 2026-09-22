use crate::backend::Backend;
use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    App, Manager,
};

pub fn build(app: &App) -> tauri::Result<()> {
    let open = MenuItem::with_id(app, "open", "Abrir aplicativo", true, None::<&str>)?;
    let toggle = MenuItem::with_id(app, "toggle", "Iniciar ou parar bot", true, None::<&str>)?;
    let cycle = MenuItem::with_id(app, "cycle", "Executar ciclo agora", true, None::<&str>)?;
    let error = MenuItem::with_id(app, "error", "Mostrar último erro", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Sair completamente", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&open, &toggle, &cycle, &error, &quit])?;
    TrayIconBuilder::new()
        .menu(&menu)
        .on_menu_event(|app, event| match event.id.as_ref() {
            "open" | "error" => show(app),
            "quit" => {
                let handle = app.clone();
                tauri::async_runtime::spawn(async move {
                    let backend = handle.state::<Backend>();
                    let _ = backend
                        .request("shutdown".into(), serde_json::json!({}))
                        .await;
                    backend.kill();
                    handle.exit(0);
                });
            }
            "toggle" => {
                let handle = app.clone();
                tauri::async_runtime::spawn(async move {
                    let backend = handle.state::<Backend>();
                    if let Ok(status) = backend
                        .request("get_status".into(), serde_json::json!({}))
                        .await
                    {
                        let command = if status
                            .get("botRunning")
                            .and_then(|v| v.as_bool())
                            .unwrap_or(false)
                        {
                            "stop_bot"
                        } else {
                            "start_bot"
                        };
                        let _ = backend.request(command.into(), serde_json::json!({})).await;
                    }
                });
            }
            "cycle" => {
                let handle = app.clone();
                tauri::async_runtime::spawn(async move {
                    let _ = handle
                        .state::<Backend>()
                        .request("run_cycle".into(), serde_json::json!({"confirmed":true}))
                        .await;
                });
            }
            _ => {}
        })
        .build(app)?;
    Ok(())
}

fn show(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.set_focus();
    }
}
