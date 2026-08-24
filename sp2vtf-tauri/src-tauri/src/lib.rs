mod python_bridge;

use tauri::Manager;

#[tauri::command]
fn py_diag(app: tauri::AppHandle) -> Result<String, String> {
    python_bridge::diag(&app)
}

#[tauri::command]
fn get_config_path(app: tauri::AppHandle) -> Result<String, String> {
    let path = app.path()
        .app_data_dir()
        .map_err(|e| e.to_string())?
        .join("config.json");
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    Ok(path.to_string_lossy().to_string())
}

#[tauri::command]
fn load_config(app: tauri::AppHandle, config_path: String) -> Result<serde_json::Value, String> {
    python_bridge::init_python(&app)?;
    python_bridge::call_core("load_config", &[serde_json::Value::String(config_path)], None)
}

#[tauri::command]
fn save_config(app: tauri::AppHandle, config_path: String, data: serde_json::Value) -> Result<serde_json::Value, String> {
    python_bridge::init_python(&app)?;
    python_bridge::call_core("save_config", &[serde_json::Value::String(config_path), data], None)
}

#[tauri::command]
fn scan_vmts(app: tauri::AppHandle, vmt_dir: String, png_dir: String, default_w: u32, default_h: u32) -> Result<serde_json::Value, String> {
    python_bridge::init_python(&app)?;
    python_bridge::call_core(
        "scan_vmts",
        &[
            serde_json::Value::String(vmt_dir),
            serde_json::Value::String(png_dir),
            serde_json::Value::Number(default_w.into()),
            serde_json::Value::Number(default_h.into()),
        ],
        None,
    )
}

#[tauri::command]
fn convert_items(app: tauri::AppHandle, items: serde_json::Value, settings: serde_json::Value) -> Result<serde_json::Value, String> {
    python_bridge::init_python(&app)?;
    python_bridge::call_core("convert_items", &[items, settings], None)
}

#[tauri::command]
fn export_vtf_to_tga(app: tauri::AppHandle, queue: serde_json::Value, vtfcmd: String, output_dir: String) -> Result<serde_json::Value, String> {
    python_bridge::init_python(&app)?;
    python_bridge::call_core(
        "export_vtf_to_tga",
        &[
            queue,
            serde_json::Value::String(vtfcmd),
            serde_json::Value::String(output_dir),
        ],
        None,
    )
}

/// 显示 Windows 原生错误对话框（不依赖 GUI 框架）
fn show_error_dialog(msg: &str) {
    use std::ptr::null_mut;
    #[link(name = "user32")]
    extern "system" {
        fn MessageBoxW(
            hWnd: *mut core::ffi::c_void,
            lpText: *const u16,
            lpCaption: *const u16,
            uType: u32,
        ) -> i32;
    }
    let title: Vec<u16> = "SP2VTF - 启动失败\0".encode_utf16().collect();
    let text: Vec<u16> = msg.encode_utf16().chain(std::iter::once(0)).collect();
    unsafe {
        // MB_ICONERROR (0x10) | MB_TOPMOST (0x40000)
        MessageBoxW(null_mut(), text.as_ptr(), title.as_ptr(), 0x10 | 0x40000);
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // ── panic 钩子：写文件 + 弹框，确保任何 panic 都有可见错误 ──
    std::panic::set_hook(Box::new(|info| {
        let msg = if let Some(s) = info.payload().downcast_ref::<String>() {
            s.as_str()
        } else if let Some(s) = info.payload().downcast_ref::<&str>() {
            *s
        } else {
            "未知错误"
        };
        let loc = info.location()
            .map(|l| format!("  位置: {}:{}", l.file(), l.line()))
            .unwrap_or_default();
        let backtrace = std::backtrace::Backtrace::force_capture();
        let log_path = python_bridge::crash_log_path();
        let full = format!(
            "SP2VTF 崩溃日志\n{sep}\npanic: {msg}\n{loc}\n\n调用栈:\n{bt}",
            sep = "=".repeat(40),
            bt = backtrace,
        );
        let _ = std::fs::write(&log_path, &full);
        show_error_dialog(&format!(
            "SP2VTF 崩溃：\n\n{msg}\n{loc}\n\n详细日志已写入:\n{log_path}"
        ));
    }));

    let result = tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let handle = app.handle().clone();

            // 在第一次 Python::attach 之前，把 python-embed 加入 PATH，
            // 使 PyO3 raw-dylib 能找到 python310.dll。
            match python_bridge::locate_python_dir(&handle) {
                Some(python_dir) => {
                    let current = std::env::var("PATH").unwrap_or_default();
                    std::env::set_var("PATH", format!("{};{}", python_dir.display(), current));
                    eprintln!("[setup] added to PATH: {python_dir:?}");
                }
                None => {
                    eprintln!("[setup] 未找到 python-embed 目录（所有回退路径均未命中）");
                }
            }

            if let Err(e) = python_bridge::init_python(&handle) {
                eprintln!("[python] init error: {e}");
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            py_diag,
            get_config_path,
            load_config,
            save_config,
            scan_vmts,
            convert_items,
            export_vtf_to_tga,
        ])
        .run(tauri::generate_context!());

    if let Err(e) = result {
        let msg = format!(
            "SP2VTF 启动失败：\n\n\
             {e}\n\n\
             ──────────────────────\n\
             最常见原因：未安装 WebView2 Runtime\n\
             请下载安装后重试：\n\
             https://go.microsoft.com/fwlink/p/?LinkId=2124703"
        );
        show_error_dialog(&msg);
        std::process::exit(1);
    }
}
