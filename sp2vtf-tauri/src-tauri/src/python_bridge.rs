//! Python 嵌入桥接：初始化 embeddable Python，配置 sys.path / DLL 目录，
//! 并封装调用 sp2vtf_core 的函数。

use std::path::PathBuf;

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyTuple};
use tauri::Manager;
use tauri::path::BaseDirectory;

/// 定位捆绑的 python-embed 目录（dev: src-tauri/resources，prod: 安装目录 resources）。
pub fn locate_python_dir(app: &tauri::AppHandle) -> Option<PathBuf> {
    let dev = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("resources")
        .join("python-embed");
    if dev.join("python310._pth").is_file() {
        return Some(dev);
    }
    if let Ok(r) = app.path().resolve("resources/python-embed", BaseDirectory::Resource) {
        if r.join("python310._pth").is_file() {
            return Some(r);
        }
    }
    None
}

/// 应用启动时调用：初始化嵌入式 Python，验证 numpy/PIL 可导入。
pub fn init_python(app: &tauri::AppHandle) -> Result<(), String> {
    let python_dir = locate_python_dir(app).ok_or("未找到 python-embed 目录")?;
    let site_packages = python_dir.join("site-packages");
    if !site_packages.is_dir() {
        return Err(format!("site-packages 不存在: {}", site_packages.display()));
    }

    Python::attach(|py| -> PyResult<()> {
        let sys = py.import("sys")?;
        let path = sys.getattr("path")?;
        path.call_method1("insert", (0, site_packages.to_string_lossy().as_ref()))?;
        path.call_method1("insert", (0, python_dir.to_string_lossy().as_ref()))?;

        // numpy/Pillow 的原生 DLL 目录
        let os = py.import("os")?;
        for sub in ["numpy.libs", "numpy/.libs", "Pillow.libs"] {
            let d = site_packages.join(sub);
            if d.is_dir() {
                let _ = os.call_method1("add_dll_directory", (d.to_string_lossy().as_ref(),));
            }
        }

        let np = py.import("numpy")?;
        let pil = py.import("PIL")?;
        let np_ver: String = np.getattr("__version__")?.extract()?;
        let pil_ver: String = pil.getattr("__version__")?.extract()?;
        eprintln!("[python] numpy {np_ver}, Pillow {pil_ver}, embed={}", python_dir.display());
        Ok(())
    })
    .map_err(|e: PyErr| format!("Python 初始化失败: {e}"))
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
