"""Detect the desktop/compositor and self-configure floating for the card.

Tiling Wayland compositors (niri, sway, hyprland) tile every window by default
and forbid clients from positioning themselves, so the triage card needs a
compositor rule to float and center. Stacking desktops (GNOME, KDE, most X11
WMs) float frameless utility windows on their own, so nothing is needed there.

Everything here is idempotent and backs up the user's config before editing.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

APP_ID = "dirwatch"
_MARKER = "dirwatch floating rule (managed)"


class Compositor(str, Enum):
    NIRI = "niri"
    SWAY = "sway"
    HYPRLAND = "hyprland"
    GNOME = "gnome"
    KDE = "kde"
    OTHER = "other"


@dataclass
class FloatingResult:
    compositor: Compositor
    needs_rule: bool          # does this compositor require a rule at all?
    configured: bool          # is the rule present now?
    changed: bool             # did we just change something?
    message: str              # human-friendly status
    config_path: str | None = None
    snippet: str | None = None  # the rule, for manual application / display


def detect() -> Compositor:
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    if os.environ.get("NIRI_SOCKET") or "niri" in desktop:
        return Compositor.NIRI
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") or "hyprland" in desktop:
        return Compositor.HYPRLAND
    if os.environ.get("SWAYSOCK") or "sway" in desktop:
        return Compositor.SWAY
    if "gnome" in desktop:
        return Compositor.GNOME
    if "kde" in desktop or "plasma" in desktop:
        return Compositor.KDE
    return Compositor.OTHER


# ---- per-compositor rule text ---------------------------------------------

def _niri_snippet() -> str:
    return (
        f"\n// {_MARKER} — delete this block to disable floating\n"
        "window-rule {\n"
        f'    match app-id=r#"^{APP_ID}$"#\n'
        "    open-floating true\n"
        "    focus-ring { off; }\n"
        "    border { off; }\n"
        "    shadow { off; }\n"
        "}\n"
    )


def _sway_snippet() -> str:
    return (
        f"\n# {_MARKER}\n"
        f'for_window [app_id="{APP_ID}"] floating enable, move position center\n'
    )


def _hyprland_snippet() -> str:
    return (
        f"\n# {_MARKER}\n"
        f"windowrulev2 = float, class:^({APP_ID})$\n"
        f"windowrulev2 = center, class:^({APP_ID})$\n"
    )


def _config_for(comp: Compositor) -> tuple[Path, str]:
    home = Path.home()
    if comp is Compositor.NIRI:
        base = os.environ.get("XDG_CONFIG_HOME")
        root = Path(base) if base else home / ".config"
        return root / "niri" / "config.kdl", _niri_snippet()
    if comp is Compositor.SWAY:
        return home / ".config" / "sway" / "config", _sway_snippet()
    if comp is Compositor.HYPRLAND:
        return home / ".config" / "hypr" / "hyprland.conf", _hyprland_snippet()
    raise ValueError(comp)


# ---- public API ------------------------------------------------------------

def status() -> FloatingResult:
    comp = detect()
    if comp in (Compositor.GNOME, Compositor.KDE, Compositor.OTHER):
        return FloatingResult(
            compositor=comp, needs_rule=False, configured=True, changed=False,
            message="Your desktop floats pop-up windows automatically — "
                    "no configuration needed.",
        )
    path, snippet = _config_for(comp)
    token = {
        Compositor.NIRI: f'app-id=r#"^{APP_ID}$"#',
        Compositor.SWAY: f'app_id="{APP_ID}"',
        Compositor.HYPRLAND: f"class:^({APP_ID})$",
    }[comp]
    text = path.read_text() if path.exists() else ""
    # Configured if our managed block OR any equivalent rule already exists.
    configured = _MARKER in text or token in text
    return FloatingResult(
        compositor=comp, needs_rule=True, configured=configured, changed=False,
        message=("Floating is configured." if configured
                 else f"{comp.value} needs a one-line rule to float the card."),
        config_path=str(path), snippet=snippet,
    )


def ensure_floating() -> FloatingResult:
    """Apply the floating rule for tiling compositors if not already present."""
    res = status()
    if not res.needs_rule or res.configured:
        return res

    comp = res.compositor
    path = Path(res.config_path)
    snippet = res.snippet
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        original = path.read_text() if path.exists() else ""
        candidate = original + snippet

        if comp is Compositor.NIRI and not _niri_validate(candidate):
            res.message = ("Could not safely edit the niri config "
                           "(validation failed). Add the rule manually.")
            return res

        if path.exists():
            shutil.copy2(path, path.with_suffix(path.suffix + ".dirwatch.bak"))
        path.write_text(candidate)
        _reload(comp)
        res.configured = True
        res.changed = True
        res.message = f"Floating configured for {comp.value} (backup saved)."
    except OSError as exc:
        res.message = f"Could not write {path}: {exc}. Add the rule manually."
    return res


def remove_floating() -> FloatingResult:
    """Remove the managed rule block, restoring tiling behavior."""
    res = status()
    if not res.needs_rule or not res.configured:
        return res
    path = Path(res.config_path)
    try:
        lines = path.read_text().splitlines(keepends=True)
        out, skip = [], False
        for line in lines:
            if _MARKER in line:
                skip = True
                continue
            if skip:
                # niri block: skip until its closing brace; line-rules: one/two lines
                if line.strip() in ("}", "") and res.compositor is Compositor.NIRI:
                    skip = False
                elif res.compositor is not Compositor.NIRI and not line.startswith(
                    ("for_window", "windowrulev2")
                ):
                    skip = False
                    out.append(line)
                continue
            out.append(line)
        shutil.copy2(path, path.with_suffix(path.suffix + ".dirwatch.bak"))
        path.write_text("".join(out))
        _reload(res.compositor)
        res.configured = False
        res.changed = True
        res.message = "Floating rule removed."
    except OSError as exc:
        res.message = f"Could not edit {path}: {exc}"
    return res


# ---- helpers ---------------------------------------------------------------

def _niri_validate(candidate_text: str) -> bool:
    try:
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".kdl", delete=False) as fh:
            fh.write(candidate_text)
            tmp = fh.name
        proc = subprocess.run(
            ["niri", "validate", "-c", tmp],
            capture_output=True, timeout=10,
        )
        os.unlink(tmp)
        return proc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _reload(comp: Compositor) -> None:
    cmd = {
        Compositor.SWAY: ["swaymsg", "reload"],
        Compositor.HYPRLAND: ["hyprctl", "reload"],
        # niri auto-reloads its config on change; nothing to do.
    }.get(comp)
    if not cmd:
        return
    try:
        subprocess.run(cmd, capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        pass
