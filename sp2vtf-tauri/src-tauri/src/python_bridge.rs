//! Python 嵌入桥接：初始化 embeddable Python，配置 sys.path / DLL 目录，
//! 并封装调用 sp2vtf_core 的函数。

use std::io::Write;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::path::PathBuf;

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyTuple};
use tauri::Manager;
use tauri::path::BaseDirectory;

/// 诊断日志写入文件（追加模式）。
fn diag_log(msg: &str) {
    let log_path = crash_log_path();
    if let Ok(mut f) = std::fs::OpenOptions::new().create(true).append(true).open(&log_path) {
        let _ = writeln!(f, "{msg}");
    }
}

/// 崩溃日志文件路径。
pub fn crash_log_path() -> String {
    if let Ok(temp) = std::env::var("TEMP") {
        format!("{}\\sp2vtf-crash.log", temp)
    } else if let Ok(exe) = std::env::current_exe() {
        exe.parent()
            .map(|p| p.join("sp2vtf-crash.log").to_string_lossy().to_string())
            .unwrap_or_else(|| "sp2vtf-crash.log".to_string())
    } else {
        "sp2vtf-crash.log".to_string()
    }
}

/// 定位捆绑的 python-embed 目录（多级回退）。
pub fn locate_python_dir(app: &tauri::AppHandle) -> Option<PathBuf> {
    // 1. 开发环境
    let dev = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("resources")
        .join("python-embed");
    if dev.join("python310._pth").is_file() {
        diag_log(&format!("[locate] dev 路径命中: {}", dev.display()));
        return Some(dev);
    }

    // 2. exe 同级目录回退
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            for sub in ["resources/python-embed", "python-embed"] {
                let p = dir.join(sub);
                if p.join("python310._pth").is_file() {
                    diag_log(&format!("[locate] exe 回退命中: {}", p.display()));
                    return Some(p);
                }
            }
        }
    }

    // 3. Tauri BaseDirectory::Resource 回退
    for sub in ["resources/python-embed", "python-embed"] {
        if let Ok(r) = app.path().resolve(sub, BaseDirectory::Resource) {
            if r.join("python310._pth").is_file() {
                diag_log(&format!("[locate] Resource 回退命中: {}", r.display()));
                return Some(r);
            }
        }
    }

    diag_log("[locate] 所有路径均未找到 python-embed");
    None
}

/// 应用启动时调用：初始化嵌入式 Python，验证 numpy/PIL 可导入。
/// 用 catch_unwind 包裹 Python::attach，防止 auto-initialize panic 崩溃。
pub fn init_python(app: &tauri::AppHandle) -> Result<(), String> {
    let python_dir = locate_python_dir(app).ok_or("未找到 python-embed 目录")?;
    let site_packages = python_dir.join("site-packages");
    if !site_packages.is_dir() {
        diag_log(&format!("[init] site-packages 不存在: {}", site_packages.display()));
        return Err(format!("site-packages 不存在: {}", site_packages.display()));
    }

    let py_dir = python_dir.to_string_lossy().to_string();
    let sp_dir = site_packages.to_string_lossy().to_string();

    let result = catch_unwind(AssertUnwindSafe(|| {
        Python::attach(|py| -> PyResult<()> {
            let sys = py.import("sys")?;
            let path = sys.getattr("path")?;
            path.call_method1("insert", (0, sp_dir.as_str()))?;
            path.call_method1("insert", (0, py_dir.as_str()))?;

            let os = py.import("os")?;
            for sub in ["numpy.libs", "numpy/.libs", "Pillow.libs"] {
                let d = PathBuf::from(&sp_dir).join(sub);
                if d.is_dir() {
                    let _ = os.call_method1("add_dll_directory", (d.to_string_lossy().as_ref(),));
                }
            }

            let np = py.import("numpy")?;
            let pil = py.import("PIL")?;
            let np_ver: String = np.getattr("__version__")?.extract()?;
            let pil_ver: String = pil.getattr("__version__")?.extract()?;
            eprintln!("[python] numpy {np_ver}, Pillow {pil_ver}, embed={py_dir}");
            diag_log(&format!("[init] 成功: numpy {np_ver}, Pillow {pil_ver}, embed={py_dir}"));
            Ok(())
        })
    }));

    match result {
        Ok(Ok(())) => Ok(()),
        Ok(Err(py_err)) => {
            diag_log(&format!("[init] Python 错误: {py_err}"));
            Err(format!("Python 初始化失败: {py_err}"))
        }
        Err(panic_err) => {
            let msg = if let Some(s) = panic_err.downcast_ref::<String>() {
                s.clone()
            } else if let Some(s) = panic_err.downcast_ref::<&str>() {
                s.to_string()
            } else {
                format!("{:?}", panic_err)
            };
            diag_log(&format!("[init] PANIC: {msg}"));
            Err(format!("Python 初始化 panic: {msg}"))
        }
    }
}

/// 将 serde 值转换为 Python 对象（通过 json 中间层，保证类型安全）。
fn json_to_py<'py>(py: Python<'py>, value: &serde_json::Value) -> PyResult<Bound<'py, pyo3::PyAny>> {
    let json_mod = py.import("json")?;
    let json_str = serde_json::to_string(value)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    json_mod.call_method1("loads", (json_str,))
}

/// 调用 sp2vtf_core 中 `sp2vtf_core.<func_name>`，参数经 JSON 序列化传递。
pub fn call_core(
    func_name: &str,
    args: &[serde_json::Value],
    kwargs: Option<serde_json::Map<String, serde_json::Value>>,
) -> Result<serde_json::Value, String> {
    let result_json: String = Python::attach(|py| -> PyResult<String> {
        let core = py.import("sp2vtf_core")?;
        let func = core.getattr(func_name)?;
        let py_args: Vec<Bound<'_, pyo3::PyAny>> = args
            .iter()
            .map(|v| json_to_py(py, v))
            .collect::<PyResult<_>>()?;
        let tuple_args = PyTuple::new(py, &py_args)?;

        let result = if let Some(kw) = kwargs {
            let dict = PyDict::new(py);
            for (k, v) in kw.iter() {
                dict.set_item(k.as_str(), json_to_py(py, v)?)?;
            }
            func.call(tuple_args, Some(&dict))?
        } else {
            func.call(tuple_args, None)?
        };

        let json_mod = py.import("json")?;
        json_mod.call_method1("dumps", (result,))?.extract()
    })
    .map_err(|e: PyErr| format!("Python 调用失败: {e}"))?;

    serde_json::from_str(&result_json).map_err(|e| format!("JSON 解析失败: {e}"))
}

/// 诊断信息（验证嵌入环境）。
pub fn diag(_app: &tauri::AppHandle) -> Result<String, String> {
    Python::attach(|py| -> PyResult<String> {
        let sys = py.import("sys")?;
        let ver: String = sys.getattr("version")?.extract()?;
        let exe: String = sys.getattr("executable")?.extract()?;
        let path: Vec<String> = sys.getattr("path")?.extract()?;
        Ok(format!("{ver}\nexecutable: {exe}\npath: {path:?}"))
    })
    .map_err(|e: PyErr| e.to_string())
}
