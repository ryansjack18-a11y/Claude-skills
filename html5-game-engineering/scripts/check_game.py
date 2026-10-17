#!/usr/bin/env python3
"""Static self-check for a single-file HTML5 game.

Usage:
    python3 check_game.py path/to/index.html [--json]

Checks the file against the html5-game-engineering requirements (self-contained,
fixed/delta timestep, Web Audio, responsive wrapper, error overlay, high score,
input handling, complete states) and syntax-checks every inline <script> with
`node --check` when Node is available. Exit code is 1 if any check FAILs.

These are heuristics: a PASS means the pattern is present, not that it is correct.
Read the code for the things a regex cannot see.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


def strip_namespaces(text: str) -> str:
    # SVG/XHTML namespace URIs are identifiers, not network requests.
    return re.sub(r"https?://www\.w3\.org/[\w/.\-]*", "", text)


def inline_scripts(html: str):
    for m in re.finditer(r"<script\b([^>]*)>(.*?)</script>", html, re.S | re.I):
        attrs, body = m.group(1), m.group(2)
        if re.search(r"type\s*=\s*[\"'](?!text/javascript|module)", attrs, re.I):
            continue  # e.g. type="text/plain" templates
        yield attrs, body


def css_text(html: str) -> str:
    return "\n".join(re.findall(r"<style\b[^>]*>(.*?)</style>", html, re.S | re.I))


def run_checks(path: Path):
    html = path.read_text(encoding="utf-8", errors="replace")
    js = "\n".join(body for _, body in inline_scripts(html))
    css = css_text(html)
    clean = strip_namespaces(html)
    results = []

    def add(name, status, detail):
        results.append({"check": name, "status": status, "detail": detail})

    # 1. Self-contained
    ext = []
    if re.search(r"<script\b[^>]*\bsrc\s*=", html, re.I):
        ext.append("<script src=...>")
    if re.search(r"<link\b[^>]*\bhref\s*=\s*[\"']?(https?:)?//", html, re.I):
        ext.append("<link href=remote>")
    for m in re.finditer(r"""(?:src|href|url\(|fetch\(|import\s*\(?)\s*=?\s*["']?(https?:)?//[^\s"')]+""", clean, re.I):
        ext.append(m.group(0)[:80])
    for m in re.finditer(r"""(?:src|href)\s*=\s*["'](?!data:|#|javascript:|blob:)([^"']+\.(?:png|jpe?g|gif|webp|svg|css|js))["']""", html, re.I):
        ext.append(m.group(0)[:80])
    add("self_contained", FAIL if ext else PASS,
        "external references: " + "; ".join(sorted(set(ext))[:5]) if ext else "no external scripts, styles, images or URLs")

    # 2. No audio files
    audio_files = re.findall(r"""["'][^"']*\.(?:mp3|wav|ogg|m4a|aac|flac)["']""", html, re.I)
    add("no_audio_files", FAIL if audio_files else PASS,
        f"audio file references: {audio_files[:3]}" if audio_files else "no audio file references")

    # 3. Web Audio synthesis
    has_ac = re.search(r"AudioContext", js) is not None
    has_osc = re.search(r"createOscillator|createBufferSource|createBuffer", js) is not None
    add("web_audio", PASS if (has_ac and has_osc) else WARN,
        "AudioContext + oscillator/buffer synthesis found" if (has_ac and has_osc)
        else "no Web Audio synthesis found (fine only if the game is intentionally silent)")
    if has_ac:
        gesture = re.search(r"\.resume\(\)", js) is not None
        add("audio_unlock", PASS if gesture else WARN,
            "AudioContext.resume() present (autoplay policy)" if gesture
            else "no ctx.resume(): audio may stay silent until the context is created inside a user gesture")

    # 4. Loop + timing
    has_raf = "requestAnimationFrame" in js
    add("raf_loop", PASS if has_raf else FAIL,
        "requestAnimationFrame used" if has_raf else "no requestAnimationFrame loop")
    timing = re.search(r"\b(dt|delta\w*|accumulator|acc|elapsed|timestep|STEP|FIXED\w*)\b", js) is not None
    no_interval_loop = re.search(r"setInterval\s*\(\s*\w*(loop|tick|update|frame)", js, re.I) is None
    add("frame_rate_independent", PASS if (timing and no_interval_loop) else FAIL,
        "delta-time / fixed-step identifiers found" if timing and no_interval_loop
        else "no delta-time or fixed-step logic found (or a setInterval game loop)")
    clamp = re.search(r"Math\.min\([^)]*\b(dt|delta\w*|elapsed)\b|\b(dt|delta\w*|elapsed)\b\s*>\s*[\w.]+", js) is not None
    add("dt_clamped", PASS if clamp else WARN,
        "frame delta is clamped" if clamp else "frame delta does not appear to be clamped (tab-switch spike risk)")

    # 5. Responsive wrapper
    has_max = re.search(r"max-width|min\([^;]*px", css) is not None
    has_aspect = "aspect-ratio" in css
    has_flex = re.search(r"display\s*:\s*(flex|grid)", css) is not None
    viewport = re.search(r'<meta[^>]+name=["\']viewport', html, re.I) is not None
    ok = has_max and has_aspect and has_flex and viewport
    add("responsive_layout", PASS if ok else FAIL,
        f"max-width={has_max}, aspect-ratio={has_aspect}, flex/grid={has_flex}, viewport meta={viewport}")

    # 6. Error handling
    onerror = re.search(r"window\.onerror|addEventListener\(\s*['\"]error['\"]", js) is not None
    rejection = "unhandledrejection" in js
    add("error_overlay", PASS if onerror else FAIL,
        f"window.onerror={onerror}, unhandledrejection={rejection}")

    # 7. High score persistence
    ls = "localStorage" in js
    guarded = ls and re.search(r"try\s*\{[^}]*localStorage", js, re.S) is not None
    add("high_score_storage", PASS if guarded else (WARN if ls else FAIL),
        "localStorage wrapped in try/catch" if guarded
        else ("localStorage used without try/catch (throws in some sandboxes)" if ls else "no localStorage high score"))

    # 8. Input
    keys = re.search(r"keydown", js) is not None
    prevent = re.search(r"preventDefault\(\)", js) is not None
    add("keyboard_no_scroll", PASS if (not keys or prevent) else FAIL,
        "keydown handler calls preventDefault" if keys and prevent
        else ("no keyboard input" if not keys else "keydown without preventDefault: arrows/space will scroll the page"))
    touch = re.search(r"pointerdown|touchstart|['\"]click['\"]", js) is not None
    add("touch_or_onscreen_controls", PASS if touch else FAIL,
        "pointer/touch/click handlers found" if touch else "no pointer/touch handlers: unplayable on phones")
    touch_action = "touch-action" in css
    add("touch_action_css", PASS if touch_action else WARN,
        "touch-action set" if touch_action else "no touch-action CSS: taps may zoom/scroll on mobile")

    # 9. States (wording varies a lot between games, so a miss is a WARN to verify by hand)
    low = html.lower()
    start = re.search(r"\bstart\b|\bplay\b|\bbegin\b", low) is not None
    over = re.search(r"game over|you win|victory|you lose|level complete|game.?over|all clear|solved|"
                     r"id=[\"'][^\"']*(end|over|result|win|complete|summary)[^\"']*[\"']", low) is not None
    restart = re.search(r"restart|play again|try again|retry|replay|new game|another|again", low) is not None
    add("three_states", PASS if (start and over and restart) else WARN,
        f"start={start}, end screen={over}, restart={restart}"
        + ("" if (start and over and restart) else " (heuristic: confirm the screens exist by reading the markup)"))

    # 10. Truncation / placeholder detection
    placeholders = re.findall(
        r"(//\s*\.\.\.|/\*\s*\.\.\.\s*\*/|\bTODO\b|rest of (the )?(code|game)|add (more|your) .{0,20} here|implement(ation)? (goes )?here)",
        js, re.I)
    add("no_placeholders", FAIL if placeholders else PASS,
        f"placeholder/truncation markers: {[p[0] for p in placeholders][:3]}" if placeholders else "no placeholder markers")
    ends = re.search(r"</html>\s*$", html, re.I) is not None
    add("file_complete", PASS if ends else FAIL, "ends with </html>" if ends else "file does not end with </html> (truncated?)")

    # 11. Syntax check every inline script with node
    node = shutil.which("node")
    if node:
        errors = []
        for i, (attrs, body) in enumerate(inline_scripts(html)):
            suffix = ".mjs" if "module" in attrs else ".js"
            with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False) as f:
                f.write(body)
                tmp = f.name
            proc = subprocess.run([node, "--check", tmp], capture_output=True, text=True)
            Path(tmp).unlink(missing_ok=True)
            if proc.returncode != 0:
                lines = [l for l in proc.stderr.splitlines() if "Error" in l or "^" in l]
                errors.append(f"script #{i}: " + (lines[-1] if lines else proc.stderr.strip()[:200]))
        add("js_syntax", FAIL if errors else PASS, "; ".join(errors) if errors else "all inline scripts parse")
    else:
        add("js_syntax", WARN, "node not found; syntax not checked")

    size_kb = len(html.encode()) / 1024
    lines = html.count("\n") + 1
    add("size", PASS, f"{lines} lines, {size_kb:.1f} KB")
    return results


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        sys.exit(2)
    results = run_checks(Path(args[0]))
    if "--json" in sys.argv:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            print(f"[{r['status']}] {r['check']}: {r['detail']}")
        fails = sum(r["status"] == FAIL for r in results)
        warns = sum(r["status"] == WARN for r in results)
        print(f"\n{fails} fail, {warns} warn, {len(results) - fails - warns} pass")
    sys.exit(1 if any(r["status"] == FAIL for r in results) else 0)


if __name__ == "__main__":
    main()
