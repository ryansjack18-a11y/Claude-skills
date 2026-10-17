---
name: html5-game-engineering
description: Build complete, polished, single-file HTML5 browser games (arcade, action, puzzle, logic, board, idle, and "make a game where..." concepts) as one self-contained index.html with vanilla JS, canvas or SVG graphics, Web Audio sound, start/play/game-over screens, high scores, and keyboard plus touch controls. Use this skill whenever the user asks for a game, a playable prototype, a browser/web/HTML/JavaScript/canvas game, a clone of a classic (snake, tetris, breakout, pong, flappy bird, 2048, asteroids, space invaders, minesweeper, sokoban, match-3, etc.), or describes a game mechanic or concept they want to play, even if they never say "HTML5" or "single file". Also use it when fixing or extending an existing HTML/JS game.
---

# HTML5 Game Engineering

Turn a game idea, whether a classic clone or a one-line abstract concept, into a single
`index.html` that runs anywhere by double-clicking it: no build step, no network, no
broken asset links. The game should feel finished: a welcome screen that teaches the
controls, responsive gameplay with clear feedback, and an end screen that remembers
your best score.

Bundled resources:
- `assets/game-template.html`: a tested, working skeleton (a tiny demo game) with the fixed-timestep
  loop, input queue, Web Audio synth, safe storage, responsive canvas, three screens,
  pause, touch D-pad, and crash overlay already wired up. **Start from this file.**
- `references/patterns.md`: patterns for specific genres (grid movement and direction
  queues, puzzle state and undo, ball physics, platformers, collisions, procedural
  sprites, particles, levels, pointer input, seeded RNG, aspect ratios). Read the sections
  that match your game.
- `scripts/check_game.py`: static checker for every requirement below, plus a JS syntax check.
- `scripts/smoke_test.js`: optional headless-browser test (needs Node + Playwright).

## Workflow

### 1. Design before code (keep it short, in your head or a few lines to the user)

Decide:
- **Core loop and verbs:** what the player does every few seconds (move, aim, place, merge, dodge).
- **Win/lose:** how a run ends, and whether there is a real victory (finite levels) or
  only a high score (endless).
- **Score and progression:** what earns points, and what gets harder over time (speed,
  spawn rate, level layouts).
- **Controls:** keyboard mapping *and* a touch/pointer equivalent. Every game must be
  playable on a phone.
- **Timing model:** real-time (physics, spawning) or turn-based (puzzles). Turn-based
  games still use the rAF loop for animation, but their rules run on input events.
- **Shape:** 16:9 for side-on action, 1:1 for boards and grids, 9:16 for vertical or
  phone-first games (see patterns §11).

For an abstract concept ("a lighthouse keeper guiding ships"), invent a concrete mechanic
that is fun in the first ten seconds. Make sensible design decisions yourself instead of
quizzing the user, and mention the key choices when you deliver. Ask only when the request
is genuinely ambiguous in a way that changes the whole game.

Before writing code, spend a moment on balance. Ask what the laziest strategy that wins
looks like (waving a beam back and forth, hugging one wall, spamming one button), and design
the mechanic so it doesn't work. Common fixes are a dwell time, a cooldown, a resource
cost, or threats from several directions. Set the starting difficulty with the rules of
thumb in patterns §8. Settling balance here, by reasoning, is far cheaper than finding
exploits with simulated players after the game is built.

### 2. Build from the template

Copy `assets/game-template.html` to the output path (default `index.html` in the working
directory, unless the user named a file or location). Then:
- Replace everything between the `GAME LOGIC` banners with your game: `newGame()`,
  `update(dt)`, `render()`, and helpers. Keep the surrounding infrastructure. It already
  solves the problems that make browser games flaky, and rewriting it costs length and adds risk.
- Update the title, the menu screen text, the controls list, `GAME_ID` (localStorage
  namespace), the theme colors, `W/H` and the aspect CSS variables, and the touch buttons
  (add an action button such as `data-key="Space"` if the game needs one, and remove the
  D-pad for pointer-only games).
- Add per-game sounds to the `sfx` object, built from `audio.tone(...)`.
- If the game ends in victory, call `endGame(true)`. Extend the end screen with
  game-specific stats (level reached, moves, time) where useful.

If you are modifying an existing game rather than writing a new one, keep its structure
and retrofit the missing requirements below instead of forcing it into the template.

### 3. Write it without truncation

Long single-file outputs fail in one way: the response runs out partway and the file is cut
off, or the model "saves space" with `// ... rest of code` and ships a broken game.
Prevent both:
- **Budget scope, not completeness.** Aim for roughly 500–1200 lines total. If the idea
  is large, cut breadth (fewer enemy types, fewer levels, simpler effects), never
  correctness or the required states. Data-driven designs (level arrays, config tables,
  one generic entity update) stay compact.
- **Write in passes when using file tools.** Write the full copied template first, then
  replace the GAME LOGIC section, then make further `Edit`s for any additions. Each edit is
  small and complete, so no single output has to hold the whole file.
- **Never leave placeholders.** No `TODO`, `// ...`, or "implement X here". If something
  doesn't fit, remove the feature cleanly.
- **Without file tools** (plain chat), output the whole file in one fenced `html` block.
  If it won't fit, reduce scope until it does.

### 4. Verify before delivering, within a fixed budget

The two bundled scripts already test what generated games most often get wrong. Run them as
black boxes: their output explains each failure, so you don't need to read their source.

1. Run the static checker. It covers the requirements and parses every script:
   ```bash
   python3 <skill-dir>/scripts/check_game.py index.html
   ```
   Fix every FAIL. Fix each WARN unless it is deliberate.
2. If Node and Playwright are available, run the smoke test once. It loads the game
   headlessly, starts it, plays random input, injects an error to test the overlay, checks
   the phone layout and saves screenshots:
   ```bash
   NODE_PATH="$(npm root -g)" node <skill-dir>/scripts/smoke_test.js index.html --out /tmp/smoke
   ```
3. Look once at the start, play and phone screenshots. A blank canvas or an overlapping HUD
   shows up here and nowhere else.
4. Reread your game logic once, against the pitfalls listed below.

Then deliver. Don't build extra test infrastructure on top: no custom Playwright scripts,
no bots that play the game, no instrumented copies of the file, and no rounds of difficulty
simulation. In testing, that extra work doubled build time and token cost, and it mostly
confirmed what the checks and a careful reread had already shown. Balance belongs in the
design step, and the player can ask for tuning once they've played.

Two narrow exceptions are worth their cost:
- **Pure rule functions,** such as a puzzle solver, level generator or scoring formula,
  can be checked with a single throwaway `node -e` run before you wire them in.
- **A failing check you can't explain** from its message and a reread can get one small,
  targeted reproduction.

If a fix touches the file, rerun only the checker and the smoke test.

### 5. Deliver

Give the path and a short note: how to play (controls), the key design choices you made,
and anything notable (levels, power-ups, how the difficulty ramps). Keep it brief; the game
speaks for itself.

## Requirements and why they matter

**Self-contained single file.** HTML, CSS and JS inline. No CDNs, libraries, web fonts,
image or audio files, unless the user supplies assets. The file must work offline, from
`file://`, inside sandboxed iframes, and years from now. `data:` URIs generated in code are fine.

**Code-drawn graphics.** Draw sprites, characters, tiles and UI with Canvas 2D paths or
inline SVG (see patterns §6). Put effort into the look: a cohesive palette, a few details
of character (eyes, highlights, glow), and motion (squash, particles, easing).
Programmer-art rectangles make a game feel unfinished.

**Frame-rate independence.** Displays run at 60, 120 or 144 Hz, and frames drop. The
template runs `update(STEP)` in a fixed-timestep accumulator with the frame delta clamped
(`MAX_FRAME`). Inside `update`, scale every motion and every timer by `dt`
(`x += vx * dt`, `cooldown -= dt`). Never move things by a constant per frame. Never use
`setTimeout`/`setInterval` for game logic: those timers keep running while the game is paused
and fire into the next game after a restart. Keep timers as numbers in the game state instead.

**Web Audio only.** Synthesize effects with oscillators and gain envelopes (`audio.tone`).
Browsers block audio until a user gesture, so the AudioContext is created/resumed in the
Start click or first touch (`audio.unlock()`). Include a mute toggle, which the template
already has. Audio failures must never throw into the game loop.

**Responsive layout.** The game box is a flex-centered container with `max-width` and
`aspect-ratio`, sized so it also fits the viewport height. The canvas uses a fixed
*logical* resolution (`W×H`) and scales for devicePixelRatio, so game code never deals
with screen pixels. Convert pointer positions with `toGame(e)`.

**Input that is immediate but bounded.** Key presses go into a small queue (`input.drain()`)
consumed by the simulation, so quick taps between frames are never lost and a burst of keys
can't pile up. Held keys are read with `input.isDown()`. Validate queued actions against
the *last accepted* state. The canonical example is a snake that must not reverse into itself
when two turns arrive within one tick (patterns §1). Arrow keys and Space are
`preventDefault()`-ed so the page doesn't scroll, but Enter/Space on focused buttons still work.
Held keys are cleared on window blur.

When the keyboard and the pointer control the same thing (aim with the mouse *or* the
arrow keys), don't let one silently override the other. A mouse resting over the canvas
must not snap the aim back every frame while the player uses the keys. Follow
`input.lastDevice`: keys take control on keydown, and the pointer takes control only when it
actually moves. This is the most common way generated games end up with "the keyboard
doesn't work". Keep the template's `keyCode()` fallback and its click-to-refocus as well,
because games often run inside embedded previews (iframes) where focus and `e.code` are
less reliable than in a normal tab.

**Graceful failure.** A separate `<script>` before the game installs `window.onerror` and
`unhandledrejection` handlers, so even a syntax error in the main script is reported. The
loop wraps `update/render` in `try/catch`. Any crash cancels the animation frame and shows a
small debug overlay (hidden until needed) with a readable message, a "Try to resume" button
and a "Reload" button. This turns a frozen black screen into something the user can report.

**Three complete states, plus pause.**
1. *Welcome:* title, one-line premise, controls for keyboard **and** touch, Start button,
   current best score.
2. *Playing:* a live HUD with score plus lives, level, timer or moves as relevant, and pause/mute buttons.
   Pause on `P`/`Esc` and automatically when the tab is hidden.
3. *Game over / victory:* final score, best score from `localStorage` (wrapped in
   try/catch because it throws in some sandboxes), a "New best!" highlight, Play again,
   and Menu.

Enter starts from the menu and end screens. Focus moves to the primary button on each
screen so keyboard users never need the mouse.

**Controls accessibility.** Show on-screen controls on touch devices (the template's
`#touch` bar appears automatically on coarse pointers), or make the game fully playable by
tapping or dragging the canvas. Keep tap targets ≥ 44 px. Respect `prefers-reduced-motion`
for shake and flashes.

## Pitfalls to check before delivering

These are the bugs that most often ship in generated games:
- **Restart leaks state:** `newGame()` must rebuild *everything*: entity arrays, timers,
  level, speed, power-up effects, and the input queue (`input.clear()`).
- **Game over fires twice:** several collisions in one step each call `endGame`. Return from
  `update` (or check `state`) right after ending the game.
- **Spawning inside things:** food on the snake, enemies on the player, a ball stuck in a
  brick. Spawn into a free cell or position.
- **Unfair start:** the first 20–30 seconds should be easy enough that a new player
  understands the game before it ramps up.
- **Unwinnable puzzles:** generate by scrambling a solved state with legal moves (patterns §2).
- **Tunneling:** fast objects passing through thin walls. Cap speed or sub-step (patterns §3).
- **Stale focus:** the clicked Start button keeps focus, so Space presses it again. The
  template blurs on play. Preserve that if you restructure screens.
- **Blurry or stretched canvas:** don't set canvas size from CSS alone. Keep the template's `resize()`.
- **Text that doesn't fit on a phone:** check the 375 px screenshot from the smoke test.
  Menu screens may need smaller text or fewer lines in portrait.
