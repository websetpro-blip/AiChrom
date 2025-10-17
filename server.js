const path = require("path");
const fs = require("fs");
const express = require("express");
const cors = require("cors");
const { chromium } = require("playwright");

const ROOT = __dirname;
const PROFILES_DIR = path.join(ROOT, "profiles");
fs.mkdirSync(PROFILES_DIR, { recursive: true });

const app = express();
app.use(cors());
app.use(express.json({ limit: "1mb" }));

app.get("/api/health", (req, res) => res.json({ ok: true, service: "BrowserVault", cwd: ROOT }));

// ===== Playwright: запуск/стоп профилей =====
const contexts = new Map(); // id -> PersistentContext
function normProxy(p){
  if (!p || !p.server) return null;
  let s = p.server.trim();
  if (!/^https?:\]/i.test(s) && !/^socks5:\//i.test(s)) {
    s = ((p.type||"").toLowerCase().includes("socks") ? "socks5://" : "http://") + s;
  }
  return { server: s, username: p.username||p.login, password: p.password };
}

app.post("/api/launch", async (req, res) => {
  try {
    const { id, userAgent, locale, timezone, viewport, proxy, colorScheme, deviceScaleFactor, startUrls } = req.body||{};
    if (!id) return res.status(400).json({ ok:false, error:"profile id required" });
    if (contexts.has(id)) return res.json({ ok:true, already:true });

    const userDataDir = path.join(PROFILES_DIR, id);
    fs.mkdirSync(userDataDir, { recursive: true });

    const ctx = await chromium.launchPersistentContext(userDataDir, {
      headless: false,
      userAgent: userAgent || undefined,
      viewport: (viewport && viewport.width && viewport.height) ? viewport : { width:1280, height:800 },
      locale: locale || "ru-RU",
      timezoneId: timezone || "Europe/Riga",
      colorScheme: colorScheme || "light",
      deviceScaleFactor: deviceScaleFactor || 1,
      proxy: normProxy(proxy) || undefined,
      args: ["--restore-last-session","--no-first-run","--no-default-browser-check"]
    });
    contexts.set(id, ctx);

    if (Array.isArray(startUrls) && startUrls.length) {
      for (const url of startUrls) { const p = await ctx.newPage(); await p.goto(url, { waitUntil:"domcontentloaded" }); }
    } else if (ctx.pages().length === 0) {
      await ctx.newPage();
    }
    res.json({ ok:true });
  } catch (e) {
    console.error("LAUNCH ERROR:", e);
    res.status(500).json({ ok:false, error:String(e) });
  }
});

app.post("/api/stop", async (req, res) => {
  try {
    const { id } = req.body||{};
    const ctx = contexts.get(id);
    if (!ctx) return res.json({ ok:true, already:false });
    await ctx.close();
    contexts.delete(id);
    res.json({ ok:true });
  } catch (e) {
    console.error("STOP ERROR:", e);
    res.status(500).json({ ok:false, error:String(e) });
  }
});

// ===== Статика UI =====
app.use(express.static(ROOT, { extensions: ["html"] }));
app.get("/", (req, res) => res.sendFile(path.join(ROOT, "index.html")));

// ===== Error handler =====
app.use((err, req, res, next) => {
  console.error("UNCAUGHT:", err);
  res.status(500).json({ ok:false, error:String(err) });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`BrowserVault server: http://localhost:${PORT}`));
