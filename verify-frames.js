#!/usr/bin/env node
// Verify a render-frames.js PNG sequence covers exactly [0, 360) and loops.
//
// Same reasoning as verify-loop.sh: a pixel-difference heuristic comparing the
// wrap against typical adjacent-frame deltas does NOT work on this geometry --
// it is thin and mostly transparent, so any rotation decorrelates nearly every
// pixel and the metric saturates. A partial rotation passes such a test.
//
// So this re-renders frames at the angles they are supposed to hold and
// compares them against what is on disk, and renders angle 360 to confirm it
// reproduces frame 0. Pass the frame count the render was launched with.
//
// Usage: node verify-frames.js --dir=png/mv-loop-24-2160x3840 --frames=2880
//                              [--width=] [--height=] [--fov=] [--spin=] [--fragment=]

const puppeteer = require('puppeteer');
const http = require('http');
const fs = require('fs');
const path = require('path');
const { PNG_SERVE } = {};

const arg = (n, d) => {
  const h = process.argv.find(a => a.startsWith(`--${n}=`));
  return h ? h.split('=').slice(1).join('=') : d;
};
const DIR      = arg('dir');
const EXPECTED = parseInt(arg('frames', '0'));
const FRAGMENT = parseInt(arg('fragment', '24'));
const WIDTH    = parseInt(arg('width', '2160'));
const HEIGHT   = parseInt(arg('height', '3840'));
const SPIN     = arg('spin', 'orbit');
const FOV      = arg('fov', '0.25');
const ROLL     = arg('roll', '0deg');
const CHROME   = arg('chrome', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome');

if (!DIR) { console.error('need --dir'); process.exit(1); }

const MIME = { '.html':'text/html', '.js':'text/javascript', '.css':'text/css',
               '.glb':'model/gltf-binary', '.gltf':'model/gltf+json',
               '.bin':'application/octet-stream', '.png':'image/png' };
const serve = root => new Promise(res => {
  const s = http.createServer((rq, rs) => {
    const f = path.join(root, decodeURIComponent(rq.url.split('?')[0]).replace(/^\/+/, ''));
    fs.readFile(f, (e, b) => e ? rs.writeHead(404).end()
      : (rs.writeHead(200, {'Content-Type': MIME[path.extname(f)] || 'application/octet-stream'}), rs.end(b)));
  });
  s.listen(0, '127.0.0.1', () => res(s));
});

// Mean absolute difference per channel between two PNGs, decoded in the browser.
async function mad(page, aPath, bPath) {
  const a = fs.readFileSync(aPath).toString('base64');
  const b = fs.readFileSync(bPath).toString('base64');
  return page.evaluate(async (a, b) => {
    const load = src => new Promise(r => {
      const i = new Image(); i.onload = () => r(i); i.src = 'data:image/png;base64,' + src;
    });
    const [ia, ib] = await Promise.all([load(a), load(b)]);
    if (ia.width !== ib.width || ia.height !== ib.height) return null;
    const c = new OffscreenCanvas(ia.width, ia.height), x = c.getContext('2d');
    x.drawImage(ia, 0, 0); const da = x.getImageData(0, 0, ia.width, ia.height).data;
    x.clearRect(0, 0, ia.width, ia.height);
    x.drawImage(ib, 0, 0); const db = x.getImageData(0, 0, ia.width, ia.height).data;
    let s = 0; for (let i = 0; i < da.length; i++) s += Math.abs(da[i] - db[i]);
    return s / da.length;
  }, a, b);
}

(async () => {
  const files = fs.readdirSync(DIR).filter(f => /^frame-\d+\.png$/.test(f)).sort();
  const n = files.length;
  if (n < 3) { console.error(`need more than 2 frames in ${DIR}`); process.exit(1); }

  const highest = Math.max(...files.map(f => parseInt(f.match(/(\d+)/)[1])));
  if (highest !== n - 1) {
    console.error(`ABORT: ${n} frames present but highest index is ${highest} -- gaps.`);
    process.exit(1);
  }
  if (EXPECTED && n !== EXPECTED) {
    console.error(`ABORT: expected ${EXPECTED} frames, found ${n}.`);
    console.error('  The render is probably still running, or stopped early.');
    process.exit(1);
  }
  if (!EXPECTED) console.log(`WARNING: no --frames given; inferring ${n} from the directory.\n`);

  const server = await serve(process.cwd());
  const port = server.address().port;
  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: 'new',
    args: ['--no-sandbox', '--use-gl=angle', '--enable-unsafe-swiftshader',
           '--hide-scrollbars', '--force-device-scale-factor=1'],
  });
  const tmp = fs.mkdtempSync('/tmp/verify-frames-');
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: WIDTH, height: HEIGHT, deviceScaleFactor: 1 });
    await page.goto(`http://127.0.0.1:${port}/render-frames.html`
      + `?fragment=${FRAGMENT}&width=${WIDTH}&height=${HEIGHT}&spin=${SPIN}`
      + `&roll=${encodeURIComponent(ROLL)}${FOV ? `&fov=${FOV}` : ''}`,
      { waitUntil: 'domcontentloaded', timeout: 0 });
    await page.waitForFunction('window.frameRenderer !== undefined', { timeout: 60000 });
    await page.evaluate(() => window.frameRenderer.ready());

    const shot = async (i, nn, name) => {
      await page.evaluate((i, nn) => window.frameRenderer.setAngle(i, nn), i, nn);
      const d = await page.evaluate(() => window.frameRenderer.capture());
      const f = path.join(tmp, name);
      fs.writeFileSync(f, Buffer.from(d.split(',')[1], 'base64'));
      return f;
    };

    console.log(`verifying ${n} frames in ${DIR} (fragment ${FRAGMENT} @ ${WIDTH}x${HEIGHT}, fov ${FOV || 'default'})`);
    console.log(`expected angles: i * 360/${n}, i = 0..${n - 1}\n`);

    const nf = await mad(page, await shot(0, n, 'nf_a.png'), await shot(0, n, 'nf_b.png'));
    const tol = Math.max(nf * 4, 0.05);
    console.log(`  renderer noise floor (same angle twice) : ${nf.toFixed(5)}`);
    console.log(`  tolerance (4x floor)                    : ${tol.toFixed(5)}\n`);

    let ok = true;
    // Angle 360 is frame 0's angle plus a full turn: must reproduce frame 0.
    const wrap = await mad(page, await shot(n, n, 'wrap.png'), path.join(DIR, 'frame-0000.png'));
    ok = ok && wrap !== null && wrap <= tol;
    console.log(`  seam    angle 360 vs frame 0000         : ${wrap === null ? 'SIZE MISMATCH' : wrap.toFixed(5)}  ${ok ? 'OK' : 'FAIL'}`);

    for (const frac of [4, 2]) {
      const idx = Math.floor(n / frac);
      const f = await shot(idx, n, `spot_${idx}.png`);
      const d = await mad(page, f, path.join(DIR, `frame-${String(idx).padStart(4, '0')}.png`));
      const pass = d !== null && d <= tol;
      ok = ok && pass;
      console.log(`  frame ${String(idx).padEnd(5)} expected angle ${(idx * 360 / n).toFixed(4).padStart(8)}     : ${d === null ? 'SIZE MISMATCH' : d.toFixed(5)}  ${pass ? 'OK' : 'FAIL'}`);
    }

    console.log();
    if (ok) console.log('  SEAMLESS: frames sit at their expected angles and 360 reproduces frame 0.');
    else { console.log('  BROKEN: the sequence does not cover exactly [0, 360).'); process.exitCode = 1; }
  } finally {
    await browser.close(); server.close();
    fs.rmSync(tmp, { recursive: true, force: true });
  }
})().catch(e => { console.error('FAILED:', e.message); process.exit(1); });
