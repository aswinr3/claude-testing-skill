/**
 * Precision/recall harness for the testing skill's deterministic UI sweep.
 *
 * GOOD fixture: correct markup carrying every shape that classically trips a
 *               naive sweep. ANY finding here is a FALSE POSITIVE.
 * BAD  fixture: seeded defects, each tagged `data-defect`. Any miss is a
 *               FALSE NEGATIVE. Untagged findings on BAD are noise.
 *
 *   node evals/ui-audit/harness.mjs
 *
 * Run from a project with @playwright/test installed. Re-run after ANY edit to
 * the sweep, and add a GOOD-fixture shape for every false positive a real run
 * produces — that is how precision stays where it is.
 */
import { chromium } from '@playwright/test';

/* ------------------------------------------------------------------ fixtures */

const GOOD = `<!doctype html><meta charset=utf-8><title>good</title><style>
 *{box-sizing:border-box} body{margin:0;font:16px/1.5 sans-serif;background:#fff;color:#222}
 .vis{width:60px;overflow:visible;white-space:nowrap}              /* T1 readable overflow */
 .ell{width:60px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}  /* T2 */
 .drawer{position:absolute;top:0;left:0;width:300px;height:300px;visibility:hidden} /* T3 */
 .drawer a{display:block;height:44px}
 .content a{display:block;height:44px;width:200px}
 .deco{position:absolute;top:0;left:0;width:300px;height:60px;pointer-events:none} /* T5 */
 .scroller{width:80px;height:40px;overflow:auto;white-space:nowrap}  /* T7 */
 .btn{display:block;width:44px;height:44px}
 .dark{background:#111;color:#fff;padding:4px}                     /* T10 contrast OK */
 .hero{background-image:linear-gradient(#000,#fff);color:#777;padding:4px} /* T11 unknowable */
 .clamp{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;width:180px} /* T14 deliberate */
</style>
<div class="vis">OVERFLOWING BUT FULLY READABLE</div>
<div class="ell">ELLIPSIZED PROPERLY SO THE USER IS TOLD</div>
<nav class="drawer"><a href=#>Drawer one</a><a href=#>Drawer two</a></nav>
<div class="content"><a href=#>Content A</a><a href=#>Content B</a></div>
<div class="deco"></div>
<div class="scroller">A SCROLLABLE STRIP THE USER CAN PAN</div>
<button class="btn">OK</button>
<p>An <a href=#>inline link in a sentence</a> which SC 2.5.8 exempts.</p>
<label><input type="checkbox" style="width:20px;height:20px"> A generously sized label</label>
<input type="text" aria-label="Search products" style="width:200px;height:32px">
<button aria-label="Close dialog"><svg width="24" height="24"></svg></button>
<p class="dark">White on near-black passes contrast comfortably.</p>
<p class="hero">Text over a gradient — background is not knowable from computed style.</p>
<label for="sort">Sort by</label><select id="sort" style="width:200px;height:32px"><option>Name (A to Z)</option></select>
<p class="clamp">A card title deliberately clamped to two lines, which the browser ellipsises itself, and which is therefore not an accidental clip at all.</p>
<div id="unique-a"></div><div id="unique-b"></div>
<img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" alt="decorative">`;

const BAD = `<!doctype html><meta charset=utf-8><title>bad</title><style>
 *{box-sizing:border-box} body{margin:0;font:16px/1.5 sans-serif;background:#fff;color:#222}
 .clip{width:60px;overflow:hidden;white-space:nowrap}
 .under{display:block;width:200px;height:44px}
 .over{position:absolute;top:0;left:0;width:200px;height:44px;background:#fff}
 .ghost{position:absolute;top:0;left:0;width:200px;height:44px;background:#fff;opacity:0}
 .tiny{display:block;width:16px;height:16px}
 .faint{color:#999;background:#fff}
 .wide{width:2200px;height:10px;background:#eee}
</style>
<div class="clip" data-defect="D1">GENUINELY CLIPPED WITH NO AFFORDANCE</div>
<div style="position:relative;height:44px">
  <a class="under" href=# data-defect="D2">Buried link</a>
  <div class="over"></div>
</div>
<div style="position:relative;height:44px">
  <button data-defect="D6" style="width:200px;height:44px">Under a transparent sheet</button>
  <div class="ghost"></div>
</div>
<button class="tiny" data-defect="D3">x</button>
<img src="/does-not-exist-404.png" alt="broken" data-defect="D4">
<img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" data-defect="D5">
<input type="text" data-defect="D7" style="width:200px;height:30px">
<label for="dupe">First</label><input id="dupe" aria-label="one" style="width:200px;height:32px"><input id="dupe" aria-label="two" data-defect="D8" style="width:200px;height:32px">
<div class="wide" data-defect="D9"></div>
<button data-defect="D11" style="width:44px;height:44px"></button>
<select data-defect="D12" style="width:200px;height:32px"><option>Name (A to Z)</option><option>Price</option></select>
<input data-defect="D13" placeholder="Email address" style="width:200px;height:32px">`;

const SEEDED = ['D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'D9', 'D11', 'D12', 'D13'];

/* --------------------------------- v1 — the sweep as originally shipped ---- */

const v1 = () => {
  const out = [];
  for (const el of document.body.querySelectorAll('*')) {
    if (!el.textContent?.trim() || el.children.length > 0) continue;
    const s = getComputedStyle(el);
    const cx = el.scrollWidth > el.clientWidth + 1;
    const cy = el.scrollHeight > el.clientHeight + 1;
    const handled = s.textOverflow === 'ellipsis' || s.overflow === 'auto' || s.overflow === 'scroll';
    if ((cx || cy) && !handled) out.push({ rule: 'text-clipped', el: el.dataset.defect || el.className });
  }
  const sel = 'a,button,input,select,textarea,[role="button"],[role="link"],[tabindex]:not([tabindex="-1"])';
  const els = [...document.querySelectorAll(sel)].filter(e => {
    const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0;
  });
  for (let i = 0; i < els.length; i++) for (let j = i + 1; j < els.length; j++) {
    if (els[i].contains(els[j]) || els[j].contains(els[i])) continue;
    const a = els[i].getBoundingClientRect(), b = els[j].getBoundingClientRect();
    if (Math.min(a.right, b.right) - Math.max(a.left, b.left) > 2 &&
        Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 2)
      out.push({ rule: 'interactive-overlap', el: els[i].dataset.defect || els[i].className });
  }
  for (const e of document.querySelectorAll('a,button,input:not([type=hidden]),select,[role="button"],[role="link"]')) {
    const r = e.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && (r.width < 24 || r.height < 24))
      out.push({ rule: 'touch-target-too-small', el: e.dataset.defect || e.className });
  }
  for (const img of document.images) {
    if (img.complete && img.naturalWidth === 0) out.push({ rule: 'broken-image', el: img.dataset.defect || '' });
    if (!img.hasAttribute('alt')) out.push({ rule: 'image-missing-alt', el: img.dataset.defect || '' });
  }
  return out;
};

/* ------------- v4 — current: 9 rule families, every exception applied ------ */

const v4 = () => {
  const out = [];
  const tag = (e) => e?.dataset?.defect || e?.className || e?.tagName?.toLowerCase() || '';
  const vis = (e) => e.checkVisibility
    ? e.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })
    : getComputedStyle(e).visibility !== 'hidden';

  // 1. clipped text — only when overflow is ACTUALLY hidden/clip on that axis
  for (const el of document.body.querySelectorAll('*')) {
    if (!el.textContent?.trim() || el.children.length > 0 || !vis(el)) continue;
    const s = getComputedStyle(el);
    const hx = s.overflowX === 'hidden' || s.overflowX === 'clip';
    const hy = s.overflowY === 'hidden' || s.overflowY === 'clip';
    const cx = hx && el.scrollWidth > el.clientWidth + 1;
    const cy = hy && el.scrollHeight > el.clientHeight + 1;
    const clamped = parseInt(s.getPropertyValue('-webkit-line-clamp'), 10) > 0;
    if ((cx || cy) && s.textOverflow !== 'ellipsis' && !clamped)
      out.push({ rule: 'text-clipped', severity: 'high', el: tag(el) });
  }

  const ISEL = 'a,button,input:not([type=hidden]),select,textarea,[role="button"],[role="link"],[tabindex]:not([tabindex="-1"])';

  // 2. occlusion — hit test, not rect intersection
  for (const e of document.querySelectorAll(ISEL)) {
    if (!vis(e)) continue;
    const r = e.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) continue;
    const x = r.left + r.width / 2, y = r.top + r.height / 2;
    if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) continue;
    const top = document.elementFromPoint(x, y);
    if (top && top !== e && !e.contains(top) && !top.contains(e))
      out.push({ rule: 'interactive-occluded', severity: 'high', el: tag(e) });
  }

  // 3. touch target — WCAG 2.2 AA SC 2.5.8, with its exceptions
  const labelOf = (e) =>
    (e.id && document.querySelector(`label[for="${CSS.escape(e.id)}"]`)) || e.closest('label');
  const targetRect = (e) => {
    const r = e.getBoundingClientRect(), l = labelOf(e);
    if (!l) return r;
    const q = l.getBoundingClientRect();
    return { width: Math.max(r.right, q.right) - Math.min(r.left, q.left),
             height: Math.max(r.bottom, q.bottom) - Math.min(r.top, q.top) };
  };
  for (const e of document.querySelectorAll('a,button,input:not([type=hidden]),select,[role="button"],[role="link"]')) {
    if (!vis(e)) continue;
    const box = e.getBoundingClientRect();
    if (box.width <= 0 || box.height <= 0) continue;
    const r = targetRect(e);
    if (r.width >= 24 && r.height >= 24) continue;
    const st = getComputedStyle(e), p = e.parentElement;
    const inlineInSentence = st.display === 'inline' && p &&
      p.textContent.replace(e.textContent ?? '', '').trim().length > 0;
    if (inlineInSentence) continue;
    out.push({ rule: 'touch-target-too-small', severity: 'medium', el: tag(e) });
  }

  // 4/5. images
  for (const img of document.images) {
    if (img.complete && img.naturalWidth === 0)
      out.push({ rule: 'broken-image', severity: 'high', el: tag(img) });
    if (!img.hasAttribute('alt'))
      out.push({ rule: 'image-missing-alt', severity: 'medium', el: tag(img) });
  }

  // 6. accessible name — a control nobody can address by name
  const FORM = ['INPUT', 'SELECT', 'TEXTAREA'];
  const nameOf = (e) => {
    const aria = e.getAttribute('aria-label');
    if (aria?.trim()) return aria.trim();
    const by = e.getAttribute('aria-labelledby');
    if (by) {
      const t = by.split(/\s+/).map(id => document.getElementById(id)?.textContent || '').join(' ').trim();
      if (t) return t;
    }
    const l = labelOf(e);
    if (l?.textContent?.trim()) return l.textContent.trim();
    if (e.tagName === 'INPUT' && ['submit', 'button', 'reset'].includes(e.type))
      return (e.value || '').trim();
    // A form control's own textContent is its OPTION text, not a name. Using it
    // makes every unlabelled <select> look named. Its placeholder, however, IS
    // part of the accessible-name computation (HTML-AAM).
    if (FORM.includes(e.tagName)) {
      const ph = e.getAttribute('placeholder');
      if (ph?.trim()) return ph.trim();
    } else {
      const own = (e.textContent || '').trim();
      if (own) return own;
      const img = e.querySelector('img[alt]');
      if (img?.getAttribute('alt')?.trim()) return img.getAttribute('alt').trim();
    }
    if (e.getAttribute('title')?.trim()) return e.getAttribute('title').trim();
    return '';
  };

  // 6b. placeholder carrying the label alone — a real defect, but a DIFFERENT one:
  //     the control has a name, and that name vanishes the moment the user types.
  for (const e of document.querySelectorAll('input[placeholder],textarea[placeholder]')) {
    if (!vis(e)) continue;
    const l = labelOf(e);
    if (l?.textContent?.trim() || e.getAttribute('aria-label')?.trim() || e.getAttribute('aria-labelledby')) continue;
    out.push({ rule: 'placeholder-as-only-label', severity: 'medium', el: tag(e) });
  }

  for (const e of document.querySelectorAll(ISEL)) {
    if (!vis(e)) continue;
    const r = e.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) continue;
    if (!nameOf(e))
      out.push({ rule: 'control-missing-accessible-name', severity: 'high', el: tag(e) });
  }

  // 7. duplicate ids — silently breaks label[for], aria-labelledby and anchors
  const seen = new Set();
  for (const e of document.querySelectorAll('[id]')) {
    if (!e.id) continue;
    if (seen.has(e.id)) out.push({ rule: 'duplicate-id', severity: 'medium', el: tag(e) });
    else seen.add(e.id);
  }

  // 8. horizontal page overflow — the whole page pans sideways
  const de = document.documentElement;
  if (de.scrollWidth > de.clientWidth + 1) {
    let worst = null, max = de.clientWidth;
    for (const e of document.body.querySelectorAll('*')) {
      const r = e.getBoundingClientRect();
      if (r.width > 0 && r.right > max + 1) { max = r.right; worst = e; }
    }
    out.push({ rule: 'page-overflows-horizontally', severity: 'high', el: tag(worst) });
  }

  // 9. contrast — intentionally absent. axe owns it; a computed-style
  //    implementation cannot tell a resolved backdrop from a wrong one.

  return out;
};

/* ------------------------------------------------------------------- scoring */

const run = async (page, html, fn) => {
  await page.setContent(html, { waitUntil: 'load' });
  await page.waitForTimeout(200);          // let the 404 image settle
  return page.evaluate(fn);
};

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1000, height: 700 } });

const report = {};
for (const [name, fn] of [['v1 (originally shipped)', v1], ['v4 (current)', v4]]) {
  const good = await run(page, GOOD, fn);
  const bad = await run(page, BAD, fn);
  const found = new Set(bad.map(f => f.el).filter(e => SEEDED.includes(e)));
  const fp = good.length;
  const tp = found.size;
  const noise = bad.filter(f => !SEEDED.includes(f.el)).length;
  report[name] = {
    falsePositives_onCorrectPage: fp,
    fpDetail: good.map(f => `${f.rule}:${f.el}`),
    trueDefectsFound: `${tp}/${SEEDED.length}`,
    missed: SEEDED.filter(d => !found.has(d)),
    extraNoise_onBadPage: noise,
    precision: +(tp / (tp + fp + noise) || 0).toFixed(2),
    recall: +(tp / SEEDED.length).toFixed(2),
  };
}
console.log(JSON.stringify(report, null, 2));
await browser.close();
