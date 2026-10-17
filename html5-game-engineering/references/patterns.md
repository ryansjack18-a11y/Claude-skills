# Game patterns reference

Read the section(s) that match the game you are building. Each pattern drops into the
GAME LOGIC section of `assets/game-template.html`.

## Contents
1. Grid movement with a direction queue (snake, Pac-Man-likes, Tron)
2. Turn-based / puzzle games (2048, match-3, sliding, Lights Out, Sokoban)
3. Paddle-and-ball physics (Breakout, Pong)
4. Platformer physics (gravity, jump buffering, coyote time)
5. Collision helpers
6. Procedural sprites: canvas paths, pre-rendered sprites, inline SVG
7. Particles and juice without garbage
8. Levels, difficulty and victory
9. Pointer / tap / drag input
10. Seeded randomness (daily puzzles, reproducible levels)
11. Choosing aspect ratio and logical resolution

---

## 1. Grid movement with a direction queue

The classic bug: the snake moves right, the player presses Up then Left within one tick,
and the snake turns back into itself. The fix is to validate each queued turn against the
*last accepted* direction rather than the current one, and to consume at most one turn per tick.

```js
const DIRS = { ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0] };
// in newGame(): dir: [1, 0], queue: [], moveTimer: 0, tickRate: 8 /* cells per second */

function queueTurns(g) {
  for (const code of input.drain()) {
    const d = DIRS[code];
    if (!d) continue;
    const lastDir = g.queue.length ? g.queue[g.queue.length - 1] : g.dir;
    const isReverse = d[0] === -lastDir[0] && d[1] === -lastDir[1];
    const isSame = d[0] === lastDir[0] && d[1] === lastDir[1];
    if (!isReverse && !isSame && g.queue.length < 2) g.queue.push(d); // cap prevents buffering overflow
  }
}

function update(dt) {
  const g = game;
  queueTurns(g);
  g.moveTimer += dt;
  const interval = 1 / g.tickRate;
  while (g.moveTimer >= interval) {          // grid ticks decoupled from frame rate
    g.moveTimer -= interval;
    if (g.queue.length) g.dir = g.queue.shift(); // at most one turn per tick
    stepSnake(g);
    if (state !== State.PLAYING) return;     // stepSnake may have ended the game
  }
}
```

For smooth visuals between grid ticks, render each segment at
`lerp(prevCell, cell, g.moveTimer / interval)`.

Swipe input on phones complements the D-pad:
```js
let touchStart = null;
canvas.addEventListener('pointerdown', (e) => { touchStart = { x: e.clientX, y: e.clientY }; });
canvas.addEventListener('pointerup', (e) => {
  if (!touchStart) return;
  const dx = e.clientX - touchStart.x, dy = e.clientY - touchStart.y; touchStart = null;
  if (Math.max(Math.abs(dx), Math.abs(dy)) < 24) return; // a tap, not a swipe
  const code = Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? 'ArrowRight' : 'ArrowLeft') : (dy > 0 ? 'ArrowDown' : 'ArrowUp');
  input.press(code); // same bounded queue as the keyboard
});
```

## 2. Turn-based / puzzle games

Puzzle logic is event-driven: a move happens when the player acts, not every frame.
Keep the rAF loop anyway, because it drives animations (tile slides, merges, shakes),
but keep the *rules* in pure functions over plain data:

```js
// state is plain data → easy to clone for undo, compare for "did anything move", save to localStorage
function applyMove(board, dir) { /* returns { board: newBoard, moved: bool, gained: number } */ }

function tryMove(dir) {
  if (game.animating) return;                       // ignore input mid-animation, or queue one move
  const { board, moved, gained } = applyMove(game.board, dir);
  if (!moved) { sfx.bump(); return; }
  game.history.push(structuredClone(game.board));   // undo stack; cap its length
  if (game.history.length > 50) game.history.shift();
  game.board = board; game.score += gained; game.moves++;
  startTweens(/* from old positions to new */);
  if (isWon(board)) setTimeout(() => endGame(true), 400);     // let the final animation play
  else if (!hasMoves(board)) setTimeout(() => endGame(false), 400);
}
```

- Tweens: store `{from, to, t0, dur}` per piece and interpolate in `render()` using elapsed
  time from the loop. Use an ease such as `t => 1 - (1 - t) ** 3`.
- Grid puzzles render well as either canvas or a CSS grid of DOM/SVG elements. DOM is fine
  for < ~200 cells and gives free hit-testing and crisp text; canvas scales better.
- Level-based puzzles: define levels as compact data (strings or arrays), validate that
  each is solvable (or generate by scrambling a solved state with legal moves, which is
  always solvable), and persist `unlockedLevel` plus per-level best (moves/time).
- The "victory" end screen matters as much as game over: show moves, time, stars, and a
  "Next level" button in addition to restart.
- Lights Out-style puzzles: generate by applying random legal presses to the solved board.
  Random boards are often unsolvable.
- Sliding puzzles: only half of random permutations are solvable. Shuffle by legal moves.

## 3. Paddle-and-ball physics

- Move by velocity × dt; at high speeds a ball can tunnel through thin bricks in one step.
  Either keep `speed * STEP < brick thickness / 2` (cap speed), or sub-step:
  `const n = Math.ceil(speed * dt / (ball.r)); for (i < n) move(dt / n)`.
- Resolve brick hits by the axis of least penetration (compare overlapX vs overlapY),
  flip that velocity component, and push the ball out of the brick so it can't double-hit.
- Paddle "english": set the outgoing angle from where the ball hit the paddle
  (`(ball.x - paddle.x) / (paddle.w / 2)` → -1..1 → angle up to ±60°), then renormalize
  to the current speed. This gives the player control and prevents boring horizontal loops.
- Enforce a minimum vertical speed so the ball can't bounce horizontally forever.
- Ball "attached to paddle until launch" at the start of each life and level is a big UX win.
- Power-ups: a capsule falls from a destroyed brick (e.g. 15% chance); catch it with the
  paddle; effects carry a timer (`g.effects.wide = 10`) that counts down in update().

## 4. Platformer physics

```js
const GRAVITY = 1800, JUMP_V = 620, MOVE = 260, COYOTE = 0.1, BUFFER = 0.12;
p.vx = dirX * MOVE;
p.vy = Math.min(p.vy + GRAVITY * dt, 1200);              // terminal velocity
p.coyote = p.onGround ? COYOTE : p.coyote - dt;          // jump shortly after leaving a ledge
p.jumpBuf = pressedJump ? BUFFER : p.jumpBuf - dt;       // jump pressed shortly before landing
if (p.jumpBuf > 0 && p.coyote > 0) { p.vy = -JUMP_V; p.jumpBuf = p.coyote = 0; }
if (!input.isDown('Space') && p.vy < 0) p.vy *= 0.9;     // variable jump height
// Move and collide one axis at a time: x first, resolve; then y, resolve and set onGround.
```
For tile maps, collide against the tiles overlapping the player's AABB only (compute the
tile range from the box), never loop over every tile.

## 5. Collision helpers

```js
const aabb = (a, b) => a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
const circles = (a, b) => (a.x - b.x) ** 2 + (a.y - b.y) ** 2 < (a.r + b.r) ** 2;
function circleRect(c, r) {
  const nx = clamp(c.x, r.x, r.x + r.w), ny = clamp(c.y, r.y, r.y + r.h);
  return (c.x - nx) ** 2 + (c.y - ny) ** 2 < c.r * c.r;
}
// Point in rotated/complex shapes: build a Path2D and use ctx.isPointInPath(path, x, y).
```
Many entities (> a few hundred) colliding with each other: bucket them in a uniform grid
keyed by `(cx, cy)` and only test neighbors.

## 6. Procedural sprites

Three approaches. Pick by need:

**Direct canvas paths** (default). Cheap, scale perfectly, easy to animate (rotate a
`ctx.save()/translate/rotate/restore` block). Give characters personality with a few
details: eyes that look toward the movement direction, a squash/stretch on jump
(`ctx.scale(1 + k, 1 - k)`), a two-frame walk cycle driven by `Math.sin(time * 12)`.

**Pre-rendered sprites** for anything drawn many times per frame (bricks, tiles,
particles with glow). `shadowBlur` is expensive; bake it once:
```js
function makeSprite(w, h, draw) {
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  draw(c.getContext('2d')); return c;           // then ctx.drawImage(sprite, x, y)
}
```
(For crispness on high-DPI screens, render the sprite at `w * devicePixelRatio`
and draw it scaled down.)

**Inline SVG** when you want authored vector art (gradients, strokes, text) as an image:
```js
function svgImage(svg) {
  const img = new Image();
  img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
  return img; // check img.complete before drawing; draw nothing until loaded
}
const ship = svgImage(`<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <path d="M32 4 L56 58 L32 46 L8 58 Z" fill="#4cc9f0" stroke="#fff" stroke-width="3"/></svg>`);
```
A `data:` URI is self-contained. It is not an external asset. DOM-based games (puzzles,
boards) can instead put `<svg>` elements straight into the markup and style them with CSS.

## 7. Particles and juice

Small touches make a game feel responsive: a hit flash, a 0.2 s screen shake, particles
on destruction, a score popup that floats up, a short pitch-rising blip on combos.
Respect `prefers-reduced-motion` for shake and flashing.

Avoid allocating per frame in hot paths. Use a fixed pool:
```js
const MAX_P = 300, parts = Array.from({ length: MAX_P }, () => ({ life: 0 }));
function emit(x, y, color, n = 12) {
  for (const p of parts) {
    if (n === 0) break;
    if (p.life > 0) continue;
    const a = Math.random() * Math.PI * 2, s = 60 + Math.random() * 180;
    Object.assign(p, { x, y, vx: Math.cos(a) * s, vy: Math.sin(a) * s, life: 0.6, color }); n--;
  }
}
function updateParts(dt) { for (const p of parts) if (p.life > 0) { p.life -= dt; p.x += p.vx * dt; p.y += p.vy * dt; } }
```

## 8. Levels, difficulty and victory

- Express levels as data: `const LEVELS = [{ rows: [...], speed: 1 }, ...]`, or
  generate procedurally from the level number with a difficulty function such as
  `speed = base * (1 + 0.12 * level)`, `spawnInterval = max(min, start * 0.9 ** level)`.
- Show progression on the HUD (level, wave, remaining targets, timer) so players see
  where they stand.
- Between levels, briefly show a "Level 2" banner (1–1.5 s) instead of jumping straight
  into play.
- Endless games end only in game over, so "victory" means a new high score: celebrate
  it on the end screen. Finite games need a real "You Win" screen with stats.
- Store more than one number if it helps: `{ best, bestLevel, bestTime }` under one key.

## 9. Pointer / tap / drag input

Use Pointer Events (one code path for mouse, touch and pen) and map coordinates with the
template's `toGame(e)`:
```js
canvas.addEventListener('pointerdown', (e) => {
  if (state !== State.PLAYING) return;
  audio.unlock();
  canvas.setPointerCapture(e.pointerId);        // keep receiving moves outside the canvas
  const { x, y } = toGame(e); handleTap(x, y);
});
canvas.addEventListener('pointermove', (e) => { if (dragging) { const { x } = toGame(e); paddle.targetX = x; } });
```
- `touch-action: none` on the canvas is required, or the browser will scroll and zoom.
- Make tap targets at least ~44 CSS px on phones. At small scales a 20-logical-px tile
  may be far smaller than that on screen, so enlarge hit areas beyond the drawn shape.
- For "aim and release" mechanics, draw the aim line while dragging and fire on `pointerup`.

## 10. Seeded randomness

```js
function mulberry32(seed) {
  return function () {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const today = new Date(); const rng = mulberry32(today.getFullYear() * 10000 + (today.getMonth() + 1) * 100 + today.getDate());
```
Use it for daily puzzles, reproducible level generation, and debugging ("seed 1234 crashes").

## 11. Aspect ratio and logical resolution

The template defaults to 800×450 (16:9), which suits side-on arcade games. Change
`W`, `H`, and the `--aspect-w/--aspect-h` CSS variables together:
- Grid / board / puzzle games: square (`600×600`, `1/1`).
- Vertical shooters, stackers, phone-first games: portrait (`450×800`, `9/16`). Lower
  `--max-w` (e.g. `450px`) so it doesn't get enormous on desktop.
- Pick a logical size where your grid divides evenly (e.g. 20 px cells × 30 cols = 600).
