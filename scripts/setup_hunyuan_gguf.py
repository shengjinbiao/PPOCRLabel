"""Install pinned Windows CUDA llama.cpp and HunyuanOCR weights locally."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1] / "tools" / "hunyuan"
GITHUB = "https://github.com/ggml-org/llama.cpp/releases/download/b10809/"
HF = "https://huggingface.co/ggml-org/HunyuanOCR-GGUF/resolve/8e070c9ad79e4ca97a9b4daa2f1ce17e8759afb1/"
FILES = [
    (GITHUB, "llama-b10809-bin-win-cuda-12.4-x64.zip", 253938543,
     "c77bfcd9ed8d91e8721a2d6a290b907fddd4fa5412a47b21c6fa1709116b85f9"),
    (GITHUB, "cudart-llama-bin-win-cuda-12.4-x64.zip", 391443627,
     "8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6"),
    (HF, "HunyuanOCR-Q8_0.gguf", 577949408,
     "cdafc794cafeae377868d7a40a70e282a737e39abe77c0d8b73614447b364a21"),
    (HF, "mmproj-HunyuanOCR-bf16.gguf", 997235840,
     "46401739a91d0778d86369bb952db685b215512d61a941c3b859f337f6014fcd"),
]


def install_file(spec):
    base, name, size, digest = spec
    target = ROOT / name
    partial = ROOT / (name + ".part")
    if not target.exists():
        for attempt in range(12):
            offset = partial.stat().st_size if partial.exists() else 0
            if offset == size:
                break
            print(f"Downloading {name}: {offset}/{size}", flush=True)
            try:
                request = urllib.request.Request(base + name, headers={"Range": f"bytes={offset}-"})
                with urllib.request.urlopen(request, timeout=30) as response:
                    append = offset and response.status == 206
                    if append and not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-"):
                        raise RuntimeError("Unexpected download range")
                    with partial.open("ab" if append else "wb") as output:
                        while True:
                            data = response.read(1024 * 1024)
                            if not data:
                                break
                            output.write(data)
            except Exception as exc:
                print(f"Retry {name}: {exc}", flush=True)
                time.sleep(2)
        if not partial.exists() or partial.stat().st_size != size:
            raise RuntimeError(f"Incomplete download: {name}; rerun this script to resume")
        path = partial
    else:
        path = target
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    if h.hexdigest() != digest:
        raise RuntimeError(f"SHA256 mismatch: {name}; remove the corrupt download and retry")
    if path == partial:
        partial.rename(target)
    print(f"Verified {name}", flush=True)
    return target


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        paths = list(pool.map(install_file, FILES))
    destination = (ROOT / "runtime").resolve()
    destination.mkdir(exist_ok=True)
    for path in paths:
        if path.suffix == ".zip":
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    if not (destination / name).resolve().is_relative_to(destination):
                        raise RuntimeError("Unsafe archive path")
                archive.extractall(destination)
    print("HunyuanOCR runtime ready", flush=True)


if __name__ == "__main__":
    main()
