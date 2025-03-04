const puppeteer = require('puppeteer');
const { PuppeteerScreenRecorder } = require('puppeteer-screen-recorder');

const width = 1920;
const height = 1080;
const eachTime = 20000;
const numFragments = 30;

const config = {
  followNewTab: true,
  fps: 24,
  ffmpeg_Path: '/opt/homebrew/bin/ffmpeg' || null,
  videoFrame: {
    width: width,
    height: height,
  },
  //videoCrf: 23,
  videoCodec: 'libx264',
  //videoPreset: 'slow',
  //videoBitrate: 2048,
  aspectRatio: '16:9',
  protocolTimeout: 3600000,
  recordDurationLimit: (eachTime / 1000) + 10,
};

(async () => {
  const browser = await puppeteer.launch();
  for (let i = 1; i <= numFragments; i++) {
    console.log(i);
    const page = await browser.newPage();
    const recorder = new PuppeteerScreenRecorder(page, config);
    const status = await page.goto(`
      http://localhost:8000/?horizontal=1&rotate=1&fragment=${i}`,
      { timeout: 0, waitUntil: "domcontentloaded" }
    );
    console.log(status.statusText());
    await recorder.start(`./mp4/fragment-${i}.mp4`);
    /*const recorder = await page.screencast({
      path: 'recording.webm'
    });*/
    await new Promise(r => setTimeout(r, eachTime));
    page.setViewport({width, height});
    await recorder.stop();
  }
  await browser.close();
})();
