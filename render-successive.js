const puppeteer = require('puppeteer');
const { PuppeteerScreenRecorder } = require('puppeteer-screen-recorder');

const width = 1600;
const height = 900;
const eachTime = 60000;
const numFragments = 30;
const totalTime = eachTime * numFragments;
const recordTime = totalTime + 10000;
const recordTimeSeconds = recordTime / 1000;

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
  recordDurationLimit: recordTimeSeconds,
};

(async () => {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();
  page.setViewport({width, height});
  const recorder = new PuppeteerScreenRecorder(page, config);
  const status = await page.goto(
    "http://localhost:3000/successive",
    { timeout: 0, waitUntil: "domcontentloaded" }
  );
  console.log(status.statusText());
  await recorder.start("./mp4/successive.mp4");
  /*    const recorder = await page.screencast({
        path: 'recording.webm'
        });*/
  await new Promise(r => setTimeout(r, recordTime));
  await recorder.stop();
  await browser.close();
})();
