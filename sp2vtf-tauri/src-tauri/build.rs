use std::path::PathBuf;

fn main() {
    tauri_build::build();

    println!("cargo:rerun-if-changed=resources/python-embed");

    // OUT_DIR = target/<profile>/build/<pkg>/out → 起始向上升到 target/<profile>（exe 所在目录）
    let out_dir = PathBuf::from(std::env::var("OUT_DIR").unwrap());
    let exe_dir = out_dir.parent().unwrap()  // build/<pkg>/out → build/<pkg>
        .parent().unwrap()                   // build/<pkg> → build
        .parent().unwrap()                   // build → target/<profile>
        .to_path_buf();
    let src = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap())
        .join("resources")
        .join("python-embed");

    for f in ["python310.dll", "python3.dll", "vcruntime140.dll", "vcruntime140_1.dll"] {
        let from = src.join(f);
        if from.exists() {
            let _ = std::fs::copy(&from, exe_dir.join(f));
        }
    }
}
