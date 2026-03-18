#!/usr/bin/env python3
"""
zip2pdf — ZIP-to-PDF Conversion Utility v1.0.0

Extracts a ZIP archive, converts all supported files to PDF, and produces
a new ZIP containing only PDFs plus a structured conversion manifest.

Requirements:
    - Windows 10/11
    - Microsoft Office 2016+ (Word, Excel, PowerPoint)
    - Python 3.9+
    - pip install comtypes Pillow reportlab charset-normalizer

Usage:
    python zip2pdf.py input.zip [-o output.zip] [--batch-size 50]
"""

from __future__ import annotations

import argparse
import atexit
import csv
import io
import json
import logging
import os
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
__version__ = "1.0.0"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TOOL_VERSION = __version__

# Pillow decompression bomb guard (§3d)
MAX_IMAGE_PIXELS = 200_000_000

# ReportLab text rendering defaults (§3e)
TEXT_FONT_NAME = "Courier"
TEXT_FONT_SIZE = 9
TEXT_LEFT_MARGIN = 50
TEXT_RIGHT_MARGIN = 50
TEXT_TOP_MARGIN = 50
TEXT_BOTTOM_MARGIN = 50
TEXT_LINE_SPACING = 12

# CSV rendering (§3f)
CSV_MAX_COL_WIDTH = 150
CSV_LANDSCAPE_COL_THRESHOLD = 6

# COM batch restart cadence (§3a-c)
DEFAULT_BATCH_SIZE = 50

# Disk space multiplier (§0)
DISK_SPACE_MULTIPLIER = 2.5

# Stale temp dir age in seconds (24 hours)
STALE_TEMP_AGE_SECONDS = 86400

# Extension → handler group mapping (§2)
EXTENSION_MAP: Dict[str, str] = {
    ".docx": "word", ".doc": "word", ".docm": "word",
    ".xlsx": "excel", ".xls": "excel", ".xlsm": "excel",
    ".pptx": "powerpoint", ".ppt": "powerpoint", ".pptm": "powerpoint",
    ".png": "image", ".jpg": "image", ".jpeg": "image",
    ".bmp": "image", ".tiff": "image", ".tif": "image",
    ".txt": "text",
    ".csv": "csv",
    ".pdf": "passthrough",
}

# COM ProgIDs
COM_PROGIDS = {
    "word": "Word.Application",
    "excel": "Excel.Application",
    "powerpoint": "PowerPoint.Application",
}

# ---------------------------------------------------------------------------
# Logging setup (§6)
# ---------------------------------------------------------------------------
log = logging.getLogger("zip2pdf")


def setup_logging(log_file: Path) -> None:
    """Configure console (INFO) and file (DEBUG) logging."""
    log.setLevel(logging.DEBUG)

    fmt_console = logging.Formatter("%(message)s")
    fmt_file = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(message)s", datefmt="%Y-%m-%dT%H:%M:%S"
    )

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt_console)
    log.addHandler(ch)

    fh = logging.FileHandler(str(log_file), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt_file)
    log.addHandler(fh)


# ---------------------------------------------------------------------------
# Platform guard
# ---------------------------------------------------------------------------
def assert_windows() -> None:
    if platform.system() != "Windows":
        print("ERROR: zip2pdf requires Windows 10/11 with Microsoft Office.")
        print("macOS and Linux are not supported in v1.")
        sys.exit(2)


# ---------------------------------------------------------------------------
# Tracked PIDs for cleanup (§5 orphaned process cleanup)
# ---------------------------------------------------------------------------
_tracked_pids: List[int] = []


def _kill_tracked_pids() -> None:
    """Force-kill any tracked Office PIDs still running."""
    for pid in _tracked_pids:
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True, timeout=10,
            )
            log.debug("Killed tracked PID %d", pid)
        except Exception:
            pass


atexit.register(_kill_tracked_pids)


def _sigint_handler(signum, frame):
    log.warning("Interrupted (Ctrl+C). Cleaning up tracked Office processes...")
    _kill_tracked_pids()
    sys.exit(2)


signal.signal(signal.SIGINT, _sigint_handler)


# ---------------------------------------------------------------------------
# Preflight checks (§0)
# ---------------------------------------------------------------------------
def _get_running_office_pids() -> Dict[str, List[int]]:
    """Return dict of office process names → list of PIDs currently running."""
    result: Dict[str, List[int]] = {}
    try:
        out = subprocess.check_output(
            ["tasklist", "/FO", "CSV", "/NH"], text=True, timeout=10
        )
        for line in out.strip().splitlines():
            parts = line.replace('"', "").split(",")
            if len(parts) >= 2:
                name = parts[0].upper()
                pid = int(parts[1]) if parts[1].isdigit() else 0
                if name in ("WINWORD.EXE", "EXCEL.EXE", "POWERPNT.EXE") and pid:
                    result.setdefault(name, []).append(pid)
    except Exception:
        pass
    return result


def _get_process_pids(exe_name: str) -> set:
    """Return set of PIDs for a given exe name."""
    pids = set()
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", f"IMAGENAME eq {exe_name}", "/FO", "CSV", "/NH"],
            text=True, timeout=10,
        )
        for line in out.strip().splitlines():
            parts = line.replace('"', "").split(",")
            if len(parts) >= 2 and parts[1].isdigit():
                pids.add(int(parts[1]))
    except Exception:
        pass
    return pids


def probe_com_progids() -> Dict[str, bool]:
    """Probe each Office COM ProgID and return availability flags.
    Initializes COM once, tests all ProgIDs, then uninitializes."""
    import comtypes

    availability: Dict[str, bool] = {}
    comtypes.CoInitialize()
    try:
        for group, progid in COM_PROGIDS.items():
            try:
                app = comtypes.CreateObject(progid)
                try:
                    app.Quit()
                except Exception:
                    pass
                availability[group] = True
            except Exception as exc:
                log.debug("COM probe failed for %s: %s", progid, exc)
                availability[group] = False
    finally:
        comtypes.CoUninitialize()
    return availability


def check_disk_space(zip_path: Path, temp_root: Path) -> Tuple[float, float]:
    """Return (available_gb, needed_gb). Raises SystemExit if insufficient."""
    zip_size = zip_path.stat().st_size
    needed = zip_size * DISK_SPACE_MULTIPLIER
    needed_gb = needed / (1024 ** 3)

    usage = shutil.disk_usage(str(temp_root))
    avail_gb = usage.free / (1024 ** 3)
    return avail_gb, needed_gb


def sweep_stale_temp_dirs() -> int:
    """Remove zip2pdf_* temp dirs older than 24h. Returns count removed."""
    count = 0
    tmp = Path(tempfile.gettempdir())
    now = time.time()
    for d in tmp.glob("zip2pdf_*"):
        if d.is_dir():
            try:
                age = now - d.stat().st_mtime
                if age > STALE_TEMP_AGE_SECONDS:
                    shutil.rmtree(str(d), ignore_errors=True)
                    count += 1
            except Exception:
                pass
    return count


def warn_orphaned_office_processes() -> None:
    procs = _get_running_office_pids()
    if procs:
        names = ", ".join(procs.keys())
        log.warning(
            "[Preflight] Existing Office processes detected: %s. "
            "These may interfere with COM automation.",
            names,
        )


def run_preflight(zip_path: Path) -> Dict[str, bool]:
    """Run all preflight checks. Returns COM availability dict."""
    # 1. Probe COM
    com_avail = probe_com_progids()
    for group, ok in com_avail.items():
        status = "available" if ok else "UNAVAILABLE"
        log.info("[Preflight] %s: %s", group.capitalize(), status)

    if not any(com_avail.values()):
        log.error(
            "[Preflight] No Office COM applications available. "
            "Only images, text, CSV, and pass-through PDFs will be processed."
        )

    # 2. Disk space
    temp_root = Path(tempfile.gettempdir())
    avail_gb, needed_gb = check_disk_space(zip_path, temp_root)
    if avail_gb < needed_gb:
        log.error(
            "[Preflight] Insufficient disk space: %.1f GB available, ~%.1f GB needed. Aborting.",
            avail_gb, needed_gb,
        )
        sys.exit(2)
    log.info(
        "[Preflight] Disk space: %.1f GB available, ~%.1f GB needed — OK",
        avail_gb, needed_gb,
    )

    # 3. Sweep stale temps
    swept = sweep_stale_temp_dirs()
    if swept:
        log.info("[Preflight] Cleaned %d stale temp director%s", swept, "y" if swept == 1 else "ies")

    # 4. Orphan warning
    warn_orphaned_office_processes()

    return com_avail


# ---------------------------------------------------------------------------
# ZIP extraction with security (§4, §8)
# ---------------------------------------------------------------------------
HIDDEN_NAMES = ("__MACOSX", ".DS_Store", "Thumbs.db", "desktop.ini")


def _is_hidden_or_system(name: str) -> bool:
    parts = Path(name).parts
    for p in parts:
        if p.startswith(".") or p in HIDDEN_NAMES or p.startswith("__MACOSX"):
            return True
    return False


def safe_extract_zip(zip_path: Path, dest: Path) -> List[Path]:
    """Extract ZIP to dest, filtering hidden files and blocking path traversal.
    Returns list of extracted file paths (relative to dest)."""
    extracted: List[Path] = []
    dest = dest.resolve()

    with zipfile.ZipFile(str(zip_path), "r") as zf:
        for info in zf.infolist():
            # Skip directories
            if info.is_dir():
                continue
            # Skip hidden/system
            if _is_hidden_or_system(info.filename):
                log.debug("Filtered hidden/system file: %s", info.filename)
                continue
            # Path traversal check
            target = (dest / info.filename).resolve()
            if not str(target).startswith(str(dest)):
                log.warning("Blocked path traversal attempt: %s", info.filename)
                continue
            # Skip zero-byte
            if info.file_size == 0:
                log.debug("Skipped zero-byte file: %s", info.filename)
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(str(target), "wb") as dst:
                shutil.copyfileobj(src, dst)
            extracted.append(Path(info.filename))

    return extracted


# ---------------------------------------------------------------------------
# File classification (§2)
# ---------------------------------------------------------------------------
def classify_files(
    files: List[Path], com_avail: Dict[str, bool]
) -> Tuple[Dict[str, List[Path]], List[Tuple[Path, str]]]:
    """Classify extracted files into handler groups.
    Returns (groups_dict, skipped_list) where skipped has (path, reason)."""
    groups: Dict[str, List[Path]] = {
        "word": [], "excel": [], "powerpoint": [],
        "image": [], "text": [], "csv": [], "passthrough": [],
    }
    skipped: List[Tuple[Path, str]] = []

    for f in files:
        ext = f.suffix.lower()
        handler = EXTENSION_MAP.get(ext)
        if handler is None:
            skipped.append((f, f"unsupported type ({ext or 'no extension'})"))
            continue
        # Check COM availability for Office types
        if handler in ("word", "excel", "powerpoint") and not com_avail.get(handler, False):
            skipped.append((f, f"{handler} COM unavailable"))
            continue
        groups[handler].append(f)

    return groups, skipped


# ---------------------------------------------------------------------------
# Output naming & collision resolution (§7)
# ---------------------------------------------------------------------------
def _extension_sort_key(ext: str) -> str:
    return ext.lower()


def resolve_output_names(
    files: List[Path], groups: Dict[str, List[Path]]
) -> Dict[str, str]:
    """Build source→output mapping with collision resolution per §7.
    Keys and values are POSIX-style relative paths (str)."""
    from collections import defaultdict

    passthrough_set = {str(p) for p in groups.get("passthrough", [])}
    mapping: Dict[str, str] = {}
    buckets: Dict[str, List[Tuple[str, str]]] = defaultdict(list)

    for f in files:
        src = f.as_posix()
        out_base = (f.parent / (f.stem + ".pdf")).as_posix()
        out_key = out_base.lower()
        buckets[out_key].append((src, f.suffix.lower()))

    for out_key, entries in buckets.items():
        if len(entries) == 1:
            src, ext = entries[0]
            p = Path(src)
            mapping[src] = (p.parent / (p.stem + ".pdf")).as_posix()
        else:
            # Separate passthrough vs converted
            pt = [(s, e) for s, e in entries if s in passthrough_set]
            non_pt = [(s, e) for s, e in entries if s not in passthrough_set]
            non_pt.sort(key=lambda x: _extension_sort_key(x[1]))

            # Passthrough wins unsuffixed name
            if pt:
                for s, e in pt:
                    p = Path(s)
                    mapping[s] = (p.parent / (p.stem + ".pdf")).as_posix()
                counter = 1
                for s, e in non_pt:
                    p = Path(s)
                    mapping[s] = (p.parent / (f"{p.stem}_{counter}.pdf")).as_posix()
                    counter += 1
            else:
                # First alphabetical extension gets unsuffixed
                first_src, first_ext = non_pt[0]
                p = Path(first_src)
                mapping[first_src] = (p.parent / (p.stem + ".pdf")).as_posix()
                counter = 1
                for s, e in non_pt[1:]:
                    p = Path(s)
                    mapping[s] = (p.parent / (f"{p.stem}_{counter}.pdf")).as_posix()
                    counter += 1

    return mapping


# ---------------------------------------------------------------------------
# Post-conversion verification (§3h)
# ---------------------------------------------------------------------------
def verify_pdf(path: Path) -> bool:
    """Check output exists, size > 0, starts with %PDF-."""
    if not path.exists():
        return False
    if path.stat().st_size == 0:
        return False
    try:
        with open(str(path), "rb") as f:
            header = f.read(5)
        return header == b"%PDF-"
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Converters
# ---------------------------------------------------------------------------

# --- Retry helper for AV/EDR file locks (§5) ---

def retry_on_permission_error(fn, *args, retries: int = 1, delay: float = 2.0, **kwargs):
    """Call fn(*args, **kwargs), retrying once on PermissionError/WinError 32."""
    try:
        return fn(*args, **kwargs)
    except PermissionError:
        if retries > 0:
            log.debug("PermissionError — retrying in %.1fs...", delay)
            time.sleep(delay)
            return retry_on_permission_error(fn, *args, retries=retries - 1, delay=delay, **kwargs)
        raise
    except OSError as exc:
        # WinError 32: The process cannot access the file because it is being used
        if getattr(exc, "winerror", None) == 32 and retries > 0:
            log.debug("WinError 32 — retrying in %.1fs...", delay)
            time.sleep(delay)
            return retry_on_permission_error(fn, *args, retries=retries - 1, delay=delay, **kwargs)
        raise


# --- COM Office converters (§3a-c) ---

EXE_NAMES = {
    "word": "WINWORD.EXE",
    "excel": "EXCEL.EXE",
    "powerpoint": "POWERPNT.EXE",
}


def _launch_com_app(group: str):
    """Launch a COM Office application and return (app, pid)."""
    import comtypes

    progid = COM_PROGIDS[group]
    exe_name = EXE_NAMES[group]

    pids_before = _get_process_pids(exe_name)
    app = comtypes.CreateObject(progid)

    # Set security and visibility BEFORE opening any files
    try:
        app.AutomationSecurity = 3  # msoAutomationSecurityForceDisable
    except Exception:
        log.debug("Could not set AutomationSecurity for %s", group)

    if group == "word":
        app.Visible = False
        app.DisplayAlerts = False
    elif group == "excel":
        app.Visible = False
        app.DisplayAlerts = False
        app.ScreenUpdating = False
    elif group == "powerpoint":
        app.Visible = False
        app.DisplayAlerts = False

    # Detect spawned PID
    time.sleep(0.5)
    pids_after = _get_process_pids(exe_name)
    new_pids = pids_after - pids_before
    pid = new_pids.pop() if new_pids else None
    if pid:
        _tracked_pids.append(pid)
        log.debug("Tracked %s PID: %d", group, pid)

    return app, pid


def _quit_com_app(app, pid: Optional[int], group: str) -> None:
    """Quit COM app and remove PID from tracking."""
    try:
        app.Quit()
    except Exception:
        pass

    if pid:
        # Give it a moment to exit gracefully
        time.sleep(1)
        # Only force kill if still running
        exe_name = EXE_NAMES.get(group, "")
        still_running = pid in _get_process_pids(exe_name) if exe_name else False
        if still_running:
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/F"],
                    capture_output=True, timeout=10,
                )
                log.debug("Force-killed lingering %s PID %d", group, pid)
            except Exception:
                pass
        if pid in _tracked_pids:
            _tracked_pids.remove(pid)


def _word_open_export(app, src_abs: str, out_abs: str) -> None:
    """Strategy callback for Word COM conversion."""
    doc = retry_on_permission_error(
        app.Documents.Open,
        src_abs,
        ConfirmConversions=False,
        ReadOnly=True,
        AddToRecentFiles=False,
        PasswordDocument="",
    )
    doc.ExportAsFixedFormat(
        OutputFileName=out_abs,
        ExportFormat=17,  # wdExportFormatPDF
        OpenAfterExport=False,
        OptimizeFor=0,  # wdExportOptimizeForPrint
    )
    doc.Close(SaveChanges=False)


def _excel_open_export(app, src_abs: str, out_abs: str) -> None:
    """Strategy callback for Excel COM conversion."""
    wb = retry_on_permission_error(
        app.Workbooks.Open,
        src_abs,
        UpdateLinks=0,
        ReadOnly=True,
        Password="",
    )
    wb.ExportAsFixedFormat(
        Type=0,  # xlTypePDF
        Filename=out_abs,
        Quality=0,  # xlQualityStandard
        OpenAfterPublish=False,
    )
    wb.Close(SaveChanges=False)


def _powerpoint_open_export(app, src_abs: str, out_abs: str) -> None:
    """Strategy callback for PowerPoint COM conversion."""
    pres = retry_on_permission_error(
        app.Presentations.Open,
        src_abs,
        ReadOnly=True,
        Untitled=False,
        WithWindow=False,  # msoFalse
    )
    pres.ExportAsFixedFormat(
        out_abs,
        FixedFormatType=2,  # ppFixedFormatTypePDF
        Intent=1,  # ppFixedFormatIntentPrint
        RangeType=1,  # ppPrintAll
    )
    pres.Close()


COM_STRATEGIES = {
    "word": _word_open_export,
    "excel": _excel_open_export,
    "powerpoint": _powerpoint_open_export,
}


def convert_office(
    group: str,
    files: List[Path],
    input_dir: Path,
    output_dir: Path,
    name_map: Dict[str, str],
    batch_size: int,
) -> List[Dict[str, Any]]:
    """Generic COM converter. Uses strategy callback from COM_STRATEGIES."""
    strategy = COM_STRATEGIES[group]
    label = group.capitalize()
    results = []
    app = None
    pid = None
    count = 0

    for rel_path in files:
        src_abs = (input_dir / rel_path).resolve()
        out_rel = name_map[rel_path.as_posix()]
        out_abs = (output_dir / out_rel).resolve()
        out_abs.parent.mkdir(parents=True, exist_ok=True)

        t0 = time.perf_counter()
        result: Dict[str, Any] = {
            "source": rel_path.as_posix(),
            "output": out_rel,
            "status": "failed",
            "output_bytes": 0,
            "duration_seconds": 0,
        }

        try:
            if app is None:
                app, pid = _launch_com_app(group)

            strategy(app, str(src_abs), str(out_abs))

            if verify_pdf(out_abs):
                result["status"] = "converted"
                result["output_bytes"] = out_abs.stat().st_size
            else:
                result["status"] = "failed"
                result["error"] = "output verification failed (truncated or corrupt PDF)"
                if out_abs.exists():
                    out_abs.unlink()

        except Exception as exc:
            err_msg = str(exc)
            if "password" in err_msg.lower() or "encrypt" in err_msg.lower():
                result["error"] = "password-protected or encrypted"
            else:
                result["error"] = err_msg
            log.debug("%s conversion failed for %s", label, rel_path, exc_info=True)

            # Check if COM crashed
            if app is not None:
                try:
                    _ = app.Visible  # test if COM is alive
                except Exception:
                    log.critical("%s COM crashed. Restarting for remaining files.", label)
                    _quit_com_app(app, pid, group)
                    app = None
                    pid = None

        result["duration_seconds"] = round(time.perf_counter() - t0, 2)
        results.append(result)

        count += 1
        if count % batch_size == 0 and app is not None:
            log.debug("Restarting %s COM after %d files", label, count)
            _quit_com_app(app, pid, group)
            app = None
            pid = None

    if app is not None:
        _quit_com_app(app, pid, group)

    return results


# Convenience aliases for backward compatibility
def convert_word(files, input_dir, output_dir, name_map, batch_size):
    return convert_office("word", files, input_dir, output_dir, name_map, batch_size)

def convert_excel(files, input_dir, output_dir, name_map, batch_size):
    return convert_office("excel", files, input_dir, output_dir, name_map, batch_size)

def convert_powerpoint(files, input_dir, output_dir, name_map, batch_size):
    return convert_office("powerpoint", files, input_dir, output_dir, name_map, batch_size)


# --- Image converter (§3d) ---

def convert_images(
    files: List[Path],
    input_dir: Path,
    output_dir: Path,
    name_map: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Convert images to PDF via Pillow."""
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    results = []

    for rel_path in files:
        src_abs = input_dir / rel_path
        out_rel = name_map[rel_path.as_posix()]
        out_abs = output_dir / out_rel
        out_abs.parent.mkdir(parents=True, exist_ok=True)

        t0 = time.perf_counter()
        result: Dict[str, Any] = {
            "source": rel_path.as_posix(),
            "output": out_rel,
            "status": "failed",
            "output_bytes": 0,
            "duration_seconds": 0,
        }

        try:
            img = Image.open(str(src_abs))

            # Multi-frame TIFF
            if getattr(img, "n_frames", 1) > 1:
                frames = []
                for i in range(img.n_frames):
                    img.seek(i)
                    frame = img.copy()
                    if frame.mode != "RGB":
                        frame = frame.convert("RGB")
                    frames.append(frame)
                frames[0].save(
                    str(out_abs), "PDF", resolution=150.0,
                    save_all=True, append_images=frames[1:],
                )
            else:
                if img.mode in ("RGBA", "P", "LA", "PA"):
                    img = img.convert("RGB")
                img.save(str(out_abs), "PDF", resolution=150.0)

            if verify_pdf(out_abs):
                result["status"] = "converted"
                result["output_bytes"] = out_abs.stat().st_size
            else:
                result["status"] = "failed"
                result["error"] = "output verification failed"
                if out_abs.exists():
                    out_abs.unlink()

        except Image.DecompressionBombError:
            result["error"] = "image exceeds decompression bomb limit"
            log.warning("Decompression bomb rejected: %s", rel_path)
        except Exception as exc:
            result["error"] = str(exc)
            log.debug("Image conversion failed for %s", rel_path, exc_info=True)

        result["duration_seconds"] = round(time.perf_counter() - t0, 2)
        results.append(result)

    return results


# --- Text converter (§3e) ---

def _detect_encoding(file_path: Path) -> str:
    """Detect file encoding using charset_normalizer with fallback chain."""
    from charset_normalizer import from_path

    try:
        detection = from_path(str(file_path))
        best = detection.best()
        if best and best.encoding:
            log.debug("Detected encoding %s for %s", best.encoding, file_path.name)
            return best.encoding
    except Exception:
        pass

    # Fallback chain
    raw = file_path.read_bytes()
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            raw.decode(enc)
            log.debug("Fallback encoding %s for %s", enc, file_path.name)
            return enc
        except (UnicodeDecodeError, LookupError):
            continue
    return "latin-1"


def convert_text(
    files: List[Path],
    input_dir: Path,
    output_dir: Path,
    name_map: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Convert plain text files to PDF via ReportLab."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas as rl_canvas

    results = []
    page_w, page_h = letter
    usable_w = page_w - TEXT_LEFT_MARGIN - TEXT_RIGHT_MARGIN

    for rel_path in files:
        src_abs = input_dir / rel_path
        out_rel = name_map[rel_path.as_posix()]
        out_abs = output_dir / out_rel
        out_abs.parent.mkdir(parents=True, exist_ok=True)

        t0 = time.perf_counter()
        result: Dict[str, Any] = {
            "source": rel_path.as_posix(),
            "output": out_rel,
            "status": "failed",
            "output_bytes": 0,
            "duration_seconds": 0,
        }

        try:
            encoding = _detect_encoding(src_abs)
            text = src_abs.read_text(encoding=encoding, errors="replace")

            c = rl_canvas.Canvas(str(out_abs), pagesize=letter)
            c.setFont(TEXT_FONT_NAME, TEXT_FONT_SIZE)

            y = page_h - TEXT_TOP_MARGIN
            # Approximate chars per line
            char_width = c.stringWidth("M", TEXT_FONT_NAME, TEXT_FONT_SIZE)
            max_chars = int(usable_w / char_width) if char_width > 0 else 80

            for line in text.splitlines():
                # Wrap long lines
                while len(line) > max_chars:
                    c.drawString(TEXT_LEFT_MARGIN, y, line[:max_chars])
                    y -= TEXT_LINE_SPACING
                    line = line[max_chars:]
                    if y < TEXT_BOTTOM_MARGIN:
                        c.showPage()
                        c.setFont(TEXT_FONT_NAME, TEXT_FONT_SIZE)
                        y = page_h - TEXT_TOP_MARGIN

                c.drawString(TEXT_LEFT_MARGIN, y, line)
                y -= TEXT_LINE_SPACING

                if y < TEXT_BOTTOM_MARGIN:
                    c.showPage()
                    c.setFont(TEXT_FONT_NAME, TEXT_FONT_SIZE)
                    y = page_h - TEXT_TOP_MARGIN

            c.save()

            if verify_pdf(out_abs):
                result["status"] = "converted"
                result["output_bytes"] = out_abs.stat().st_size
            else:
                result["status"] = "failed"
                result["error"] = "output verification failed"
                if out_abs.exists():
                    out_abs.unlink()

        except Exception as exc:
            result["error"] = str(exc)
            log.debug("Text conversion failed for %s", rel_path, exc_info=True)

        result["duration_seconds"] = round(time.perf_counter() - t0, 2)
        results.append(result)

    return results


# --- CSV converter (§3f) ---

def convert_csv(
    files: List[Path],
    input_dir: Path,
    output_dir: Path,
    name_map: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Convert CSV files to PDF via ReportLab tables."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    results = []

    for rel_path in files:
        src_abs = input_dir / rel_path
        out_rel = name_map[rel_path.as_posix()]
        out_abs = output_dir / out_rel
        out_abs.parent.mkdir(parents=True, exist_ok=True)

        t0 = time.perf_counter()
        result: Dict[str, Any] = {
            "source": rel_path.as_posix(),
            "output": out_rel,
            "status": "failed",
            "output_bytes": 0,
            "duration_seconds": 0,
        }

        try:
            encoding = _detect_encoding(src_abs)
            text = src_abs.read_text(encoding=encoding, errors="replace")
            reader = csv.reader(io.StringIO(text))
            rows = list(reader)

            if not rows:
                result["error"] = "empty CSV"
                result["duration_seconds"] = round(time.perf_counter() - t0, 2)
                results.append(result)
                continue

            max_cols = max(len(r) for r in rows) if rows else 0
            use_landscape = max_cols > CSV_LANDSCAPE_COL_THRESHOLD
            pagesize = landscape(letter) if use_landscape else letter

            # Truncate cells
            truncated_rows = []
            for row in rows:
                truncated_rows.append([
                    (cell[:CSV_MAX_COL_WIDTH] + "…" if len(cell) > CSV_MAX_COL_WIDTH else cell)
                    for cell in row
                ])

            doc = SimpleDocTemplate(str(out_abs), pagesize=pagesize)
            styles = getSampleStyleSheet()

            table = Table(truncated_rows)
            style_cmds = [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d9e2f3")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
            # Alternating row shading
            for i in range(1, len(truncated_rows)):
                if i % 2 == 0:
                    style_cmds.append(
                        ("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f2f2f2"))
                    )
            table.setStyle(TableStyle(style_cmds))

            doc.build([table])

            if verify_pdf(out_abs):
                result["status"] = "converted"
                result["output_bytes"] = out_abs.stat().st_size
            else:
                result["status"] = "failed"
                result["error"] = "output verification failed"
                if out_abs.exists():
                    out_abs.unlink()

        except Exception as exc:
            result["error"] = str(exc)
            log.debug("CSV conversion failed for %s", rel_path, exc_info=True)

        result["duration_seconds"] = round(time.perf_counter() - t0, 2)
        results.append(result)

    return results


# --- Pass-through (§3g) ---

def copy_passthrough(
    files: List[Path],
    input_dir: Path,
    output_dir: Path,
    name_map: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Copy existing PDFs to output directory."""
    results = []

    for rel_path in files:
        src_abs = input_dir / rel_path
        out_rel = name_map[rel_path.as_posix()]
        out_abs = output_dir / out_rel
        out_abs.parent.mkdir(parents=True, exist_ok=True)

        t0 = time.perf_counter()
        result: Dict[str, Any] = {
            "source": rel_path.as_posix(),
            "output": out_rel,
            "status": "failed",
            "output_bytes": 0,
            "duration_seconds": 0,
        }

        try:
            shutil.copy2(str(src_abs), str(out_abs))
            result["status"] = "passed_through"
            result["output_bytes"] = out_abs.stat().st_size
        except Exception as exc:
            result["error"] = str(exc)

        result["duration_seconds"] = round(time.perf_counter() - t0, 2)
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# Build output ZIP (§4, §6)
# ---------------------------------------------------------------------------
def build_output_zip(
    output_dir: Path,
    output_zip_path: Path,
    manifest: Dict[str, Any],
) -> None:
    """Create the output ZIP from output_dir contents + manifest."""
    with zipfile.ZipFile(
        str(output_zip_path), "w",
        compression=zipfile.ZIP_DEFLATED,
        allowZip64=True,
    ) as zf:
        for root, dirs, filenames in os.walk(str(output_dir)):
            for fn in filenames:
                full = Path(root) / fn
                arcname = full.relative_to(output_dir).as_posix()
                zf.write(str(full), arcname)

        # Include manifest
        manifest_json = json.dumps(manifest, indent=2, ensure_ascii=False)
        zf.writestr("conversion_manifest.json", manifest_json)


# ---------------------------------------------------------------------------
# Cleanup helper (§4)
# ---------------------------------------------------------------------------
def _rmtree_onerror(func, path, exc_info):
    """On PermissionError, retry once after 2s sleep."""
    if isinstance(exc_info[1], PermissionError):
        time.sleep(2)
        try:
            func(path)
        except Exception:
            log.warning("Could not delete locked file: %s", path)
    else:
        log.warning("Cleanup error: %s — %s", path, exc_info[1])


# ---------------------------------------------------------------------------
# Main orchestrator (Appendix A)
# ---------------------------------------------------------------------------
def main() -> int:
    t_start = time.perf_counter()
    parser = argparse.ArgumentParser(
        description="zip2pdf — Convert all files in a ZIP archive to PDF."
    )
    parser.add_argument("input", help="Path to input ZIP file")
    parser.add_argument(
        "-o", "--output",
        help="Path for output ZIP (default: <input>_converted.zip)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
        help=f"COM restart cadence (default: {DEFAULT_BATCH_SIZE})",
    )
    args = parser.parse_args()

    # Validate input
    input_path = Path(args.input).resolve()
    if not input_path.exists() or not input_path.is_file():
        print(f"ERROR: Input file not found: {input_path}")
        return 2

    if not zipfile.is_zipfile(str(input_path)):
        print(f"ERROR: Not a valid ZIP file: {input_path}")
        return 2

    # Determine output path
    if args.output:
        output_zip = Path(args.output).resolve()
    else:
        output_zip = input_path.parent / f"{input_path.stem}_converted.zip"

    log_file = output_zip.parent / "conversion.log"
    setup_logging(log_file)
    log.info("zip2pdf v%s", TOOL_VERSION)
    log.info("Input:  %s", input_path)
    log.info("Output: %s", output_zip)

    # Platform check
    assert_windows()

    # Preflight
    com_avail = run_preflight(input_path)

    # Create working directory
    work_dir = Path(tempfile.mkdtemp(prefix="zip2pdf_"))
    input_dir = work_dir / "input"
    output_dir = work_dir / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    exit_code = 0

    try:
        # Extract
        log.info("Extracting ZIP...")
        extracted = safe_extract_zip(input_path, input_dir)
        if not extracted:
            log.warning("ZIP is empty or contains no processable files.")
            # Build empty output
            manifest = {
                "tool_version": TOOL_VERSION,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "input_zip": input_path.name,
                "office_available": com_avail,
                "counts": {"total": 0, "converted": 0, "passed_through": 0, "failed": 0, "skipped": 0},
                "files": [],
            }
            build_output_zip(output_dir, output_zip, manifest)
            log.info("Output: %s (empty)", output_zip)
            return 0

        log.info("Extracted %d files", len(extracted))

        # Classify
        groups, skipped = classify_files(extracted, com_avail)

        # Build name map
        all_processable = []
        for g in groups.values():
            all_processable.extend(g)
        name_map = resolve_output_names(all_processable, groups)

        # Detect collisions for manifest notes
        collision_notes: Dict[str, str] = {}
        for src, out in name_map.items():
            p = Path(src)
            natural_out = (p.parent / (p.stem + ".pdf")).as_posix()
            if out != natural_out:
                collision_notes[src] = f"renamed due to collision with {p.stem}.*"

        total_files = len(all_processable) + len(skipped)
        file_counter = [0]  # mutable for closure
        all_results: List[Dict[str, Any]] = []

        def log_progress(result: Dict[str, Any]) -> None:
            file_counter[0] += 1
            src = result["source"]
            status = result["status"].upper()
            extra = ""
            if status == "FAILED":
                extra = f": {result.get('error', 'unknown')}"
            dur = result.get("duration_seconds", 0)
            log.info(
                "[%2d/%d] %s %s ... %s%s (%.1fs)",
                file_counter[0], total_files, 
                "Converting" if result["status"] != "passed_through" else "Pass-through",
                src,
                status if status != "PASSED_THROUGH" else "OK",
                extra, dur,
            )

        # --- COM conversions (§3a-c) ---
        com_initialized = False
        has_com_work = any(groups[g] for g in ("word", "excel", "powerpoint"))
        if has_com_work:
            import comtypes
            comtypes.CoInitialize()
            com_initialized = True

        try:
            for group, converter_fn in [
                ("word", convert_word),
                ("excel", convert_excel),
                ("powerpoint", convert_powerpoint),
            ]:
                if groups[group]:
                    results = converter_fn(
                        groups[group], input_dir, output_dir, name_map, args.batch_size
                    )
                    for r in results:
                        log_progress(r)
                    all_results.extend(results)
        finally:
            if com_initialized:
                comtypes.CoUninitialize()

        # --- Non-COM conversions ---
        if groups["image"]:
            results = convert_images(groups["image"], input_dir, output_dir, name_map)
            for r in results:
                log_progress(r)
            all_results.extend(results)

        if groups["text"]:
            results = convert_text(groups["text"], input_dir, output_dir, name_map)
            for r in results:
                log_progress(r)
            all_results.extend(results)

        if groups["csv"]:
            results = convert_csv(groups["csv"], input_dir, output_dir, name_map)
            for r in results:
                log_progress(r)
            all_results.extend(results)

        if groups["passthrough"]:
            results = copy_passthrough(groups["passthrough"], input_dir, output_dir, name_map)
            for r in results:
                log_progress(r)
            all_results.extend(results)

        # Log skipped files
        for path, reason in skipped:
            file_counter[0] += 1
            log.info("[%2d/%d] Skipping %s — %s", file_counter[0], total_files, path, reason)
            all_results.append({
                "source": path.as_posix(),
                "output": None,
                "status": "skipped",
                "error": reason,
            })

        # Annotate collisions
        for r in all_results:
            src = r["source"]
            if src in collision_notes:
                r["note"] = collision_notes[src]

        # Tally counts
        converted = sum(1 for r in all_results if r["status"] == "converted")
        passed = sum(1 for r in all_results if r["status"] == "passed_through")
        failed = sum(1 for r in all_results if r["status"] == "failed")
        skipped_count = sum(1 for r in all_results if r["status"] == "skipped")

        # Build manifest
        elapsed_seconds = round(time.perf_counter() - t_start, 2)
        manifest = {
            "tool_version": TOOL_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "input_zip": input_path.name,
            "office_available": com_avail,
            "elapsed_seconds": elapsed_seconds,
            "counts": {
                "total": total_files,
                "converted": converted,
                "passed_through": passed,
                "failed": failed,
                "skipped": skipped_count,
            },
            "files": all_results,
        }

        # Build output ZIP
        build_output_zip(output_dir, output_zip, manifest)

        # Summary
        elapsed_seconds = round(time.perf_counter() - t_start, 2)
        minutes, secs = divmod(int(elapsed_seconds), 60)
        elapsed_str = f"{minutes}m {secs:02d}s" if minutes else f"{secs}s"
        log.info("")
        log.info("=== Conversion Summary ===")
        log.info("Total files:     %d", total_files)
        log.info("Converted:       %d", converted)
        log.info("Passed through:  %d", passed)
        log.info("Failed:          %d", failed)
        log.info("Skipped:         %d  (unsupported)", skipped_count)
        log.info("Elapsed:         %s", elapsed_str)

        if failed:
            log.info("")
            log.info("Failures:")
            for r in all_results:
                if r["status"] == "failed":
                    log.info("  - %s → %s", r["source"], r.get("error", "unknown"))

        log.info("")
        log.info("Output: %s", output_zip)
        log.info("Log:    %s", log_file)

        if failed:
            exit_code = 1

    except zipfile.BadZipFile:
        log.error("Input ZIP is corrupt or unreadable.")
        return 2
    except Exception as exc:
        log.critical("Fatal error: %s", exc, exc_info=True)
        return 2
    finally:
        # Cleanup temp
        shutil.rmtree(str(work_dir), onerror=_rmtree_onerror)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
