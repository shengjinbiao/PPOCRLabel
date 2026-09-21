"""DjVuLibre conversion, independent of the GUI and OCR models."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid


class ImportCancelled(RuntimeError):
    pass


def find_tools():
    roots = [Path(__file__).resolve().parents[1] / "tools" / "djvulibre"]
    if os.environ.get("DJVULIBRE_BIN"):
        roots.insert(0, Path(os.environ["DJVULIBRE_BIN"]))
    for name in ("ProgramFiles", "ProgramFiles(x86)"):
        if os.environ.get(name):
            roots.append(Path(os.environ[name]) / "DjVuLibre")
    result = []
    for name in ("ddjvu", "djvused"):
        executable = shutil.which(name)
        if not executable:
            suffix = ".exe" if os.name == "nt" else ""
            executable = next((str(p) for root in roots
                               for p in (root / (name + suffix), root / "bin" / (name + suffix))
                               if p.is_file()), None)
        if not executable:
            raise FileNotFoundError("DjVuLibre: ddjvu / djvused")
        result.append(executable)
    return result


def run_tool(args, cwd, tick):
    # Files avoid pipe deadlocks; polling keeps cancellation responsive.
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        with subprocess.Popen(args, cwd=cwd, stdout=stdout, stderr=stderr,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)) as proc:
            try:
                while True:
                    tick()
                    try:
                        proc.wait(timeout=0.05)
                        break
                    except subprocess.TimeoutExpired:
                        pass
                tick()
                if proc.returncode:
                    stderr.seek(0)
                    raise RuntimeError(stderr.read().decode("utf-8", errors="replace")[-2000:])
                stdout.seek(0)
                return stdout.read().decode("utf-8", errors="replace").strip()
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()


def convert_documents(paths, output_dir, tools, tick, update):
    from PIL import Image

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    converted = []
    ddjvu, djvused = tools
    with tempfile.TemporaryDirectory(prefix="ppocr_djvu_") as temp:
        for source in paths:
            tick()
            # Relative ASCII names also work with older Windows DjVuLibre builds.
            local_source = Path(temp) / "input.djvu"
            shutil.copyfile(source, local_source)
            count = int(run_tool([djvused, "input.djvu", "-e", "n"], temp, tick))
            if count < 1:
                raise RuntimeError("DjVu document contains no pages")
            stem = Path(source).stem[:80]
            for number in range(1, count + 1):
                tick()
                update(Path(source).name, number - 1, count)
                run_tool([ddjvu, "-format=ppm", f"-page={number}",
                          "input.djvu", "page.ppm"], temp, tick)
                target = output / f"{stem}_p{number:04d}.png"
                if target.exists():
                    target = output / f"{stem}_{uuid.uuid4().hex}_p{number:04d}.png"
                with Image.open(Path(temp) / "page.ppm") as page:
                    page.save(Path(temp) / "page.png")
                tick()
                shutil.copyfile(Path(temp) / "page.png", target)
                converted.append(str(target))
                update(Path(source).name, number, count)
    return converted
