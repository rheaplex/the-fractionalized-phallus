#!/usr/bin/env node
// Frame-stepped renderer for the museum loop, using the same model-viewer
// pipeline as index.html.
//
// render-mp4.js screen-recorded a wall-clock animation, so it captured
// whatever angles the compositor happened to fire at and could never loop --
// it also recorded only 20s of a 60s rotation. This drives the page one frame
// at a time at an explicit angle instead, writing a PNG per frame. Angle 360 is
// never rendered because it is frame 0, so the sequence loops by construction.
//
// Resumable: existing frames are skipped, and each PNG is written to a temp
// name and renamed only once complete.
//
// Usage: node render-frames.js [--fragment=24] [--frames=2880]
//                              [--width=2160] [--height=3840]
//                              [--spin=orientation|orbit] [--roll=90deg]
//                              [--fov=3]  narrow fov ~= orthographic, kills pulsing
//                              [--out=png/mv-loop-24-2160x3840]

const puppeteer = require('puppeteer');
const http = require('http');
const fs = require('fs');
const path = require('path');

const arg = (name, dflt) => {
  const hit = process.argv.find(a => a.startsWith(`--${name}=`));
  return hit ? hit.split('=').slice(1).join('=') : dflt;
};

const FRAGMENT = parseInt(arg('fragment', '24'));
const FRAMES   = parseInt(arg('frames', '2880'));
const WIDTH    = parseInt(arg('width', '2160'));
const HEIGHT   = parseInt(arg('height', '3840'));
const SPIN     = arg('spin', 'orientation');
const FOV      = arg('fov', '');
const ROLL     = arg('roll', '90deg');
const OUTDIR   = arg('out', `png/mv-loop-${FRAGMENT}-${WIDTH}x${HEIGHT}`);
const CHROME   = arg('chrome', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome');

const MIME = { '.html':'text/html', '.js':'text/javascript', '.css':'text/css',
               '.glb':'model/gltf-binary', '.gltf':'model/gltf+json',
               '.bin':'application/octet-stream', '.png':'image/png' };

function serve(root) {
  return new Promise(resolve => {
    const server = http.createServer((req, res) => {
      const rel = decodeURIComponent(req.url.split('?')[0]).replace(/^\/+/, '');
      const file = path.join(root, rel);
      if (!file.startsWith(root)) { res.writeHead(403).end(); return; }
      fs.readFile(file, (err, buf) => {
        if (err) { res.writeHead(404).end(); return; }
        res.writeHead(200, {
          'Content-Type': MIME[path.extname(file)] || 'application/octet-stream',
          'Access-Control-Allow-Origin': '*',
        });
        res.end(buf);
      });
    });
    server.listen(0, '127.0.0.1', () => resolve(server));
  });
}

(async () => {
  fs.mkdirSync(OUTDIR, { recursive: true });
  for (const f of fs.readdirSync(OUTDIR)) {
    if (f.startsWith('.partial-')) fs.unlinkSync(path.join(OUTDIR, f));
  }

  const server = await serve(process.cwd());
  const port = server.address().port;

  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--use-gl=angle', '--enable-unsafe-swiftshader',
           '--hide-scrollbars', '--force-device-scale-factor=1'],
  });

  try {
    const page = await browser.newPage();
    page.on('pageerror', e => console.error('page error:', e.message));
    await page.setViewport({ width: WIDTH, height: HEIGHT, deviceScaleFactor: 1 });

    const url = `http://127.0.0.1:${port}/render-frames.html`
              + `?fragment=${FRAGMENT}&width=${WIDTH}&height=${HEIGHT}`
              + `&spin=${SPIN}&roll=${encodeURIComponent(ROLL)}`
              + (FOV ? `&fov=${encodeURIComponent(FOV)}` : '');
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 0 });

    await page.waitForFunction('window.frameRenderer !== undefined', { timeout: 60000 });
    const info = await page.evaluate(() => window.frameRenderer.ready());
    console.log(`fragment ${FRAGMENT} | ${FRAMES} frames | ${WIDTH}x${HEIGHT}`
              + ` | spin=${info.spin} roll=${info.baseRoll}`);
    console.log(`canvas ${info.canvas[0]}x${info.canvas[1]} | framed radius ${info.radius.toFixed(4)}m`
              + ` | fov ${info.fov.toFixed(3)}deg`);
    console.log(`-> ${OUTDIR}`);

    if (info.canvas[0] !== WIDTH || info.canvas[1] !== HEIGHT) {
      console.warn(`WARNING: canvas is ${info.canvas[0]}x${info.canvas[1]},`
                 + ` not the requested ${WIDTH}x${HEIGHT}.`);
    }

    let rendered = 0, skipped = 0;
    const start = Date.now();

    for (let i = 0; i < FRAMES; i++) {
      const out = path.join(OUTDIR, `frame-${String(i).padStart(4, '0')}.png`);
      if (fs.existsSync(out)) { skipped++; continue; }

      await page.evaluate((i, n) => window.frameRenderer.setAngle(i, n), i, FRAMES);
      const dataUrl = await page.evaluate(() => window.frameRenderer.capture());
      const b64 = dataUrl.split(',')[1];
      if (!b64) throw new Error(`frame ${i}: capture returned no data`);
      const buf = Buffer.from(b64, 'base64');
      if (buf.length < 1000) throw new Error(`frame ${i}: capture suspiciously small (${buf.length} bytes)`);

      const tmp = path.join(OUTDIR, `.partial-${String(i).padStart(4, '0')}.png`);
      fs.writeFileSync(tmp, buf);
      fs.renameSync(tmp, out);

      rendered++;
      const elapsed = (Date.now() - start) / 1000;
      const rate = elapsed / rendered;
      const eta = (rate * (FRAMES - i - 1)) / 60;
      process.stdout.write(`\rframe ${i + 1}/${FRAMES}  ${rate.toFixed(3)}s/frame`
                         + `  ${elapsed.toFixed(0)}s elapsed  ETA ${eta.toFixed(1)}min   `);
    }
    process.stdout.write('\n');
    const total = fs.readdirSync(OUTDIR).filter(f => /^frame-\d+\.png$/.test(f)).length;
    console.log(`done: ${rendered} rendered, ${skipped} already present, ${total} frames total`);
  } finally {
    await browser.close();
    server.close();
  }
})().catch(e => { console.error('FAILED:', e.message); process.exit(1); });
