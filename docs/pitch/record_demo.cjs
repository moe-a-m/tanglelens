const { chromium } = require(process.env.PWCORE);
const { execSync } = require("child_process");
(async () => {
  const [base, outDir, repo] = process.argv.slice(2);
  const browser = await chromium.launch({ executablePath: process.env.CHROME });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, recordVideo: { dir: outDir, size: { width: 1440, height: 900 } } });
  const p = await ctx.newPage();
  const errors = []; p.on("pageerror", e => errors.push(e.message));
  const caption = async (text) => p.evaluate((t) => {
    let c = document.getElementById("__cap");
    if (!c) { c = document.createElement("div"); c.id = "__cap";
      c.style.cssText = "position:fixed;left:0;right:0;bottom:0;z-index:99999;background:#14213D;color:#F4F6F8;font:600 22px 'IBM Plex Sans',system-ui,sans-serif;padding:14px 28px";
      document.body.appendChild(c); }
    c.textContent = t; }, text);
  await p.goto(base, { waitUntil: "networkidle" }); await p.waitForSelector("tr.row");
  await caption("TangleLens on the real aeriOS tangle (HORNET 2.0.2): five aeriOS trust messages, all confirmed by milestones");
  await p.waitForTimeout(3500);
  await p.locator("tr.row", { hasText: "domain-1-ie-2" }).filter({ hasText: "trust.score" }).first().click();
  await p.waitForTimeout(800);
  await caption("ie-2's trust score 0.61: on the Tangle, solid, referenced by a milestone, contents identical");
  await p.waitForTimeout(4500);
  await p.locator("#detail a[data-trace]").first().click(); await p.waitForSelector(".tl li");
  await caption("Trace for ie-2: every event verified against its own block id");
  await p.waitForTimeout(4500);
  await caption("Now someone inflates ie-2's trust score in the explorer's database: 0.61 → 0.95 …");
  await p.waitForTimeout(2000);
  execSync("make pitch-tamper", { cwd: repo, env: { ...process.env, EXPLORER_PORT: "8091" }, stdio: "ignore" });
  await p.waitForSelector(".tl li.bad", { timeout: 15000 });   // UI refreshes every 5 s
  await caption("Caught: the trace is no longer verified, and an integrity alert fires (UI, webhook, MQTT)");
  await p.waitForTimeout(5500);
  await p.locator(".tl li.bad").first().click(); await p.waitForSelector(".cmp", { timeout: 15000 });
  await p.evaluate(() => { const d = document.querySelector(".diffkeys"); if (d) d.scrollIntoView({ block: "center" }); });
  await caption("Stored copy vs. the Tangle copy: the changed field is named. The Tangle stays the authority.");
  await p.waitForTimeout(6500);
  console.log("errors", JSON.stringify(errors));
  const video = p.video(); await ctx.close(); console.log("video", await video.path());
  await browser.close();
})();
