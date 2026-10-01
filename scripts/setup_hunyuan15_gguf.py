"""Install HunyuanOCR-1.5 beside the existing HunyuanOCR-1.0 setup.

Downloads the official checkpoint, builds the official GGUF pair, quantizes the
language model for an 8 GB-class GPU, and installs llama.cpp b11103's Windows
CUDA runtime under ``tools/hunyuan15``.  It never modifies ``tools/hunyuan``.
"""
import argparse
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "tools" / "hunyuan15"
HF_DIR = ROOT / "hf"
LLAMA_DIR = ROOT / "llama.cpp"
RUNTIME_DIR = ROOT / "runtime"
BUILD = "b11103"
RUNTIME_URLS = (
    f"https://github.com/ggml-org/llama.cpp/releases/download/{BUILD}/"
    "llama-b11103-bin-win-cuda-12.4-x64.zip",
    f"https://github.com/ggml-org/llama.cpp/releases/download/{BUILD}/"
    "cudart-llama-bin-win-cuda-12.4-x64.zip",
)


def run(command, cwd=None):
    print("+", subprocess.list2cmdline([str(part) for part in command]), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def command(name):
    found = shutil.which(name)
    if not found:
        raise RuntimeError(f"Required command not found: {name}")
    return found


def download_checkpoint():
    if (HF_DIR / "model.safetensors").is_file():
        return
    HF_DIR.mkdir(parents=True, exist_ok=True)
    run([command("hf"), "download", "tencent/HunyuanOCR", "--exclude", "v1.0/*",
         "--local-dir", str(HF_DIR), "--max-workers", "4"])


def clone_llama():
    converter = LLAMA_DIR / "convert_hf_to_gguf.py"
    if converter.is_file():
        return converter
    ROOT.mkdir(parents=True, exist_ok=True)
    run([command("git"), "clone", "--depth", "1", "https://github.com/ggml-org/llama.cpp.git", str(LLAMA_DIR)])
    if not converter.is_file():
        raise RuntimeError("llama.cpp conversion script was not found after clone")
    return converter


def install_runtime():
    server = RUNTIME_DIR / "llama-server.exe"
    if server.is_file():
        return
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    for url in RUNTIME_URLS:
        archive = ROOT / url.rsplit("/", 1)[-1]
        if not archive.is_file():
            print(f"Downloading {archive.name}", flush=True)
            urllib.request.urlretrieve(url, archive)
        with zipfile.ZipFile(archive) as bundle:
            for name in bundle.namelist():
                target = (RUNTIME_DIR / name).resolve()
                if not target.is_relative_to(RUNTIME_DIR.resolve()):
                    raise RuntimeError(f"Unsafe archive member: {name}")
            bundle.extractall(RUNTIME_DIR)
    if not server.is_file():
        raise RuntimeError("llama-server.exe was not extracted")


def convert(converter):
    f16 = ROOT / "hyocr-f16.gguf"
    projector = ROOT / "mmproj-hyocr-f16.gguf"
    if not f16.is_file():
        run([sys.executable, str(converter), "--outfile", str(f16), "--outtype", "f16", str(HF_DIR)])
    if not projector.is_file():
        run([sys.executable, str(converter), "--outfile", str(projector), "--outtype", "f16", "--mmproj", str(HF_DIR)])
    model = ROOT / "hyocr-q4_k_m.gguf"
    if not model.is_file():
        quantizer = RUNTIME_DIR / "llama-quantize.exe"
        if not quantizer.is_file():
            raise RuntimeError("llama-quantize.exe is missing from the installed runtime")
        run([str(quantizer), str(f16), str(model), "Q4_K_M"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-only", action="store_true", help="Fetch the official checkpoint only.")
    args = parser.parse_args()
    download_checkpoint()
    if args.download_only:
        print(f"Official HunyuanOCR-1.5 checkpoint ready: {HF_DIR}")
        return
    converter = clone_llama()
    install_runtime()
    convert(converter)
    print(f"HunyuanOCR-1.5 GGUF runtime ready: {ROOT}")


if __name__ == "__main__":
    main()
