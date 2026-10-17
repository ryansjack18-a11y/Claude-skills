#!/usr/bin/env node
/*
 * Headless smoke test for a single-file HTML5 game (optional: needs Node + Playwright).
 *
 *   node smoke_test.js path/to/index.html [--out dir] [--json]
 *
 * If Playwright is installed globally, run with NODE_PATH="$(npm root -g)".
 *
 * What it does:
 *   1. Loads the file, records console errors, uncaught exceptions and any network
 *      request that is not file:/data:/blob: (proves the game is self-contained).
 *   2. Screenshots the start screen, starts the game (Start/Play button, else Enter,
 *      else a canvas click) and plays ~4 s of random arrow/WASD/space input + taps.
 *   3. Checks that arrow keys are preventDefault()-ed during play (no page scroll).
 *   4. Throws an injected error and checks the message appears on screen (error overlay).
 *   5. Loads at phone size (375x740, touch) and checks for horizontal overflow.
 * Screenshots go to --out (default: next to the game file).
 */
const path = require('path');
const fs = require('fs');

let chromium;
try { ({ chromium } = require('playwright')); } catch (_) {
  console.error('Playwright not found. Install it or run with NODE_PATH="$(npm root -g)". Skipping smoke test.');
  process.exit(3);
}

const args = process.argv.slice(2);
const file = args.find((a) => !a.startsWith('--'));
if (!file) { console.error('usage: node smoke_test.js index.html [--out dir] [--json]'); process.exit(2); }
const outIdx = args.indexOf('--out');
const outDir = outIdx >= 0 ? args[outIdx + 1] : path.dirname(path.resolve(file));
const asJson = args.includes('--json');
fs.mkdirSync(outDir, { recursive: true });

const url = 'file://' + path.resolve(file);
const INJECTED = 'SMOKE_TEST_INJECTED_ERROR';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function startGame(page) {
  const btn = page.locator('button:visible, [role=button]:visible, a:visible')
    .filter({ hasText: /start|play|begin|new game|go\b/i }).first();
  if (await btn.count()) { await btn.click({ timeout: 2000 }).catch(() => {}); return 'button'; }
  await page.keyboard.press('Enter');
  await sleep(150);
  await page.keyboard.press('Space');
  const box = await page.locator('canvas').first().boundingBox().catch(() => null);
  if (box) await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  return 'keyboard/click fallback';
}

async function play(page, ms) {
  const keys = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'KeyW', 'KeyA', 'KeyS', 'KeyD', 'Space'];
  const box = await page.locator('canvas, svg, #game, main').first().boundingBox().catch(() => null);
  const end = Date.now() + ms;
  let i = 0;
  while (Date.now() < end) {
    const k = keys[Math.floor(Math.random() * keys.length)];
    await page.keyboard.down(k); await sleep(60 + Math.random() * 120); await page.keyboard.up(k);
    if (box && i++ % 4 === 0) {
      await page.mouse.click(box.x + Math.random() * box.width, box.y + box.height * (0.2 + Math.random() * 0.7));
    }
  }
}

(async () => {
  const result = { file: path.resolve(file), checks: [], screenshots: [] };
  const add = (check, status, detail) => result.checks.push({ check, status, detail });
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
    const consoleErrors = [], pageErrors = [], external = [];
    page.on('console', (m) => { if (m.type() === 'error' && !m.text().includes(INJECTED)) consoleErrors.push(m.text()); });
    page.on('pageerror', (e) => { if (!String(e.message).includes(INJECTED)) pageErrors.push(e.message); });
    page.on('request', (r) => { if (!/^(file|data|blob|about):/.test(r.url())) external.push(r.url()); });

    await page.goto(url);
    await sleep(800);
    const shot = (name) => { const p = path.join(outDir, name); result.screenshots.push(p); return page.screenshot({ path: p }); };
    await shot('smoke-1-start.png');
    add('loads_without_errors', pageErrors.length ? 'FAIL' : 'PASS',
      pageErrors.length ? pageErrors.slice(0, 3).join(' | ') : 'no uncaught exceptions on load');

    // Probe whether arrow keys get preventDefault during play.
    await page.evaluate(() => {
      window.__smoke = { arrows: 0, prevented: 0 };
      window.addEventListener('keydown', (e) => {
        if (e.key.startsWith('Arrow') || e.code === 'Space') { window.__smoke.arrows++; if (e.defaultPrevented) window.__smoke.prevented++; }
      });
    });

    const how = await startGame(page);
    await sleep(400);
    await play(page, 4000);
    await shot('smoke-2-play.png');
    const probe = await page.evaluate(() => window.__smoke);
    add('started_via', 'INFO', how);
    add('no_runtime_errors_during_play', pageErrors.length ? 'FAIL' : 'PASS',
      pageErrors.length ? pageErrors.slice(0, 3).join(' | ') : 'no uncaught exceptions during 4 s of random input');
    add('no_console_errors', consoleErrors.length ? 'WARN' : 'PASS',
      consoleErrors.length ? consoleErrors.slice(0, 3).join(' | ') : 'console clean');
    const usesKeys = /Arrow(Up|Down|Left|Right)|KeyW|keyCode\s*===?\s*3[7-9]/.test(await page.content());
    if (!usesKeys) add('arrow_keys_prevent_scroll', 'INFO', 'game does not use arrow keys; not applicable');
    else add('arrow_keys_prevent_scroll', probe.arrows && probe.prevented / probe.arrows > 0.8 ? 'PASS' : 'FAIL',
      `${probe.prevented}/${probe.arrows} arrow/space presses were preventDefault()-ed`);
    add('self_contained_network', external.length ? 'FAIL' : 'PASS',
      external.length ? 'requested: ' + [...new Set(external)].slice(0, 3).join(', ') : 'no network requests');
    const scrolled = await page.evaluate(() => window.scrollY);
    add('page_did_not_scroll', scrolled === 0 ? 'PASS' : 'FAIL', `window.scrollY = ${scrolled}`);

    // Error overlay: throw asynchronously so it reaches window.onerror.
    await page.evaluate((msg) => { setTimeout(() => { throw new Error(msg); }, 0); }, INJECTED);
    await sleep(500);
    const shown = await page.evaluate((msg) => document.body.innerText.includes(msg), INJECTED);
    await shot('smoke-3-error.png');
    add('error_overlay_shows_message', shown ? 'PASS' : 'FAIL',
      shown ? 'injected error message rendered on the page' : 'injected error did not appear in any visible text');

    // Mobile layout: no horizontal overflow at phone width.
    const phone = await browser.newPage({ viewport: { width: 375, height: 740 }, hasTouch: true, isMobile: true });
    await phone.goto(url); await sleep(600);
    const overflow = await phone.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    const p = path.join(outDir, 'smoke-4-phone.png'); await phone.screenshot({ path: p }); result.screenshots.push(p);
    add('phone_no_horizontal_overflow', overflow <= 1 ? 'PASS' : 'FAIL', `horizontal overflow ${overflow}px at 375px width`);
    await phone.close();
  } catch (e) {
    add('harness', 'FAIL', 'smoke test harness error: ' + e.message);
  } finally {
    await browser.close();
  }

  if (asJson) console.log(JSON.stringify(result, null, 2));
  else {
    for (const c of result.checks) console.log(`[${c.status}] ${c.check}: ${c.detail}`);
    console.log('screenshots:', result.screenshots.join(', '));
  }
  process.exit(result.checks.some((c) => c.status === 'FAIL') ? 1 : 0);
})();
