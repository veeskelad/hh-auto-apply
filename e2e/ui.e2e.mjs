// UI e2e дашборда через ego-browser (ego lite). Запуск: python e2e/run_ui.py
// Параметры: E2E_BASE (стенд с фикстурами), E2E_EMPTY_BASE (стенд без аккаунтов), E2E_OUT (скриншоты).
// ego-browser не передаёт окружение в скрипт, поэтому run_ui.py подставляет их в globalThis.__E2E.
const ENV = globalThis.__E2E || process.env;
const BASE = ENV.E2E_BASE;
const EMPTY = ENV.E2E_EMPTY_BASE;
const OUT = ENV.E2E_OUT;
const TABS = { apply: "panel-apply", llm: "panel-llm", history: "panel-history", settings: "panel-settings", log: "panel-log" };
const results = [];
// вывод ego-browser приходит только по завершении, поэтому ход прогона пишется в файл сразу
const { appendFileSync } = await import("node:fs");
const trace = (msg) => { try { appendFileSync(`${OUT}/trace.log`, `${new Date().toISOString().slice(11, 19)} ${msg}\n`); } catch {} };
const missed = [];

async function check(name, fn) {
  console.log("E2E_STEP " + name);
  trace("шаг: " + name);
  try {
    await fn();
    results.push({ name, ok: true });
  } catch (e) {
    results.push({ name, ok: false, error: String(e?.message || e).slice(0, 400) });
  }
}
const assert = (cond, msg) => { if (!cond) throw new Error(msg); };

trace("создаю пространство");
const task = await taskSpace("hh-auto-apply e2e");
trace("пространство " + task.spaceId);
const page = task.page("p1");
try {
  // дашборд через 3 с после загрузки просит разрешение на уведомления; запрос браузера
  // забрал бы управление у теста, поэтому в каждом документе стенда API уведомлений подменяется
  await page.cdp("Page.addScriptToEvaluateOnNewDocument", {
    source: "if(window.Notification){Object.defineProperty(Notification,'permission',{get:()=>'denied',configurable:true});" +
      "Notification.requestPermission=()=>Promise.resolve('denied');}",
  });
  // ошибки JS после загрузки страницы копятся в window.__e2eErrors
  const hookErrors = () => page.evaluate(() => {
    if (window.__e2eErrors) return;
    window.__e2eErrors = [];
    addEventListener("error", (e) => window.__e2eErrors.push(String(e.message)));
    addEventListener("unhandledrejection", (e) => window.__e2eErrors.push("promise: " + String(e.reason?.message || e.reason)));
  });

  const visible = (id) => page.evaluate((id) => { const e = document.getElementById(id); return !!e && e.offsetParent !== null; }, id);
  const openTab = async (tab) => {
    await page.click(`.tab[data-tab="${tab}"]`, { label: `open ${tab} tab` });
    await page.waitForFunction((id) => { const e = document.getElementById(id); return e && e.offsetParent !== null; }, TABS[tab], { timeout: 5000 });
  };
  // скриншот — артефакт для глаз, не проверка. Chromium не рисует перекрытое окно, и съёмка
  // тогда висит: берём кадр через CDP с таймаутом, после первого сбоя съёмку выключаем.
  const { writeFileSync } = await import("node:fs");
  let shotsOff = false;
  const shoot = async (name) => {
    if (shotsOff) { missed.push(name); return; }
    try {
      const { data } = await page.cdp("Page.captureScreenshot", { format: "png" }, { timeout: 5000 });
      writeFileSync(`${OUT}/${name}.png`, Buffer.from(data, "base64"));
    } catch {
      shotsOff = true;
      missed.push(name);
    }
  };

  // фиксированный размер окна: результат не зависит от того, как открыт ego lite
  const DESKTOP = { width: 1280, height: 800, deviceScaleFactor: 1, mobile: false };
  await page.cdp("Emulation.setDeviceMetricsOverride", DESKTOP);
  await page.goto(BASE + "/");
  await hookErrors();
  await check("дашборд загрузился, кампании из фикстур видны", async () => {
    await page.waitForFunction(() => /backend/.test(document.getElementById("campaigns-list")?.innerText || ""), undefined, { timeout: 15000 });
    const txt = await page.evaluate(() => document.getElementById("campaigns-list").innerText);
    assert(txt.includes("data"), "нет второй кампании");
    assert(!(await page.evaluate(() => document.body.classList.contains("auth-required"))), "висит экран подключения");
  });

  for (const tab of Object.keys(TABS)) {
    await check(`вкладка ${tab} открывается`, async () => {
      await openTab(tab);
      for (const other of Object.values(TABS)) if (other !== TABS[tab]) assert(!(await visible(other)), `видна чужая панель ${other}`);
      await page.waitForTimeout(1000);
      await shoot(`desktop-${tab}`);
    });
  }

  await check("история: отклики из фикстур", async () => {
    await openTab("history");
    await page.waitForFunction(() => /Альфа Софт/.test(document.getElementById("panel-history")?.innerText || ""), undefined, { timeout: 8000 });
  });

  await check("ручной отклик: аккаунт в списке", async () => {
    await openTab("history");
    const opts = await page.evaluate(() => [...document.querySelectorAll("#apply-account option")].map((o) => o.textContent));
    assert(opts.includes("Тест Тестов"), `в списке аккаунтов: ${JSON.stringify(opts)}`);
  });

  await check("настройки: разделы на месте", async () => {
    await openTab("settings");
    const txt = await page.evaluate(() => document.getElementById("panel-settings").innerText);
    for (const s of ["Подключение", "Поиск и отклики", "Шаблоны", "AI / LLM", "Продвинутое"]) assert(txt.includes(s), `нет раздела «${s}»`);
  });

  await check("создание кампании через форму", async () => {
    await openTab("apply");
    await page.click("text=+ Новая кампания", { label: "new campaign" });
    await page.waitForFunction(() => document.getElementById("campaign-configurator")?.offsetParent !== null, undefined, { timeout: 5000 });
    await page.waitForTimeout(500); // дождаться конца анимации появления
    await shoot("desktop-campaign-form");
    await page.fill("#campaign-name", "ui-e2e");
    await page.fill("#campaign-query", "Rust Developer");
    await page.click("text=Сохранить кампанию", { label: "save campaign" });
    let found = null;
    for (let i = 0; i < 20 && !found; i++) {
      await page.waitForTimeout(300);
      const r = await fetch(BASE + "/api/campaigns").then((r) => r.json());
      found = r.campaigns.find((c) => c.name === "ui-e2e");
    }
    assert(found, "кампания не сохранилась");
    assert(found.search_query === "Rust Developer", `запрос сохранился как «${found.search_query}»`);
    await fetch(BASE + `/api/campaigns/${found.id}`, { method: "DELETE" });
  });

  await check("график откликов по дням на списке кампаний", async () => {
    await openTab("apply");
    await page.waitForFunction(() => document.querySelectorAll("#campaigns-chart svg rect[fill]:not([fill=transparent])").length > 0, undefined, { timeout: 8000 });
    await page.click("#campaigns-chart .camp-chip:nth-child(2)", { label: "focus first campaign" });
    await page.waitForFunction(() => document.querySelector("#campaigns-chart .camp-chip.on:nth-child(2)"), undefined, { timeout: 3000 });
    await page.click("text=Неделя", { label: "week range" });
    await page.waitForFunction(() => document.querySelector("#campaigns-chart .camp-seg .on")?.textContent === "Неделя", undefined, { timeout: 3000 });
  });

  await check("страница кампании: статистика, причины пропусков, история", async () => {
    await openTab("apply");
    await page.click("article.camp-row >> nth=0", { label: "open campaign" });
    await page.waitForFunction(() => {
      const d = document.getElementById("campaign-detail");
      return d && !d.hidden && /Почему пропущены/.test(d.innerText) && /Уже откликались/.test(d.innerText) && d.querySelectorAll(".camp-history li").length === 10;
    }, undefined, { timeout: 10000 });
    await page.waitForTimeout(400);
    await shoot("desktop-campaign-detail");
    await page.click(".camp-pager button:last-child", { label: "next page" });
    await page.waitForFunction(() => document.querySelectorAll("#campaign-detail .camp-history li").length === 2, undefined, { timeout: 3000 });
    await page.click("text=\"Настройки\" >> nth=-1", { label: "campaign settings tab" });
    await page.waitForFunction(() => /Поисковый запрос/.test(document.getElementById("campaign-detail").innerText), undefined, { timeout: 3000 });
    await shoot("desktop-campaign-settings");
    await page.click(".camp-back", { label: "back to list" });
    await page.waitForFunction(() => document.getElementById("campaign-detail").hidden && !document.getElementById("campaigns-dash").hidden, undefined, { timeout: 3000 });
  });

  await check("тёмная тема переключается и запоминается", async () => {
    await openTab("apply");
    // перекрытое окно Chromium не анимирует: без этого переходы цвета застревают на старте
    await page.evaluate(() => { const st = document.createElement("style"); st.id = "e2e-no-motion"; st.textContent = "*,*::before,*::after{transition:none!important;animation:none!important}"; document.head.appendChild(st); });
    const before = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    await page.click("#theme-btn", { label: "toggle theme" });
    await page.waitForFunction((b) => getComputedStyle(document.body).backgroundColor !== b, before, { timeout: 3000 });
    const saved = await page.evaluate(() => localStorage.getItem("hh-theme"));
    assert(saved === "dark" || saved === "light", `тема не сохранилась: ${saved}`);
    await page.waitForTimeout(500);
    // кнопки и карточки обязаны перекраситься вместе с фоном, а не остаться светлыми
    const clash = await page.evaluate(() => {
      const lum = (c) => { const m = c.match(/\d+(\.\d+)?/g).map(Number); return (m[0] * 299 + m[1] * 587 + m[2] * 114) / 1000; };
      const bodyL = lum(getComputedStyle(document.body).backgroundColor);
      return ["#pause-btn", "#theme-btn", "#campaigns-list > div", ".dashboard-sidebar"]
        .map((sel) => ({ sel, el: document.querySelector(sel) }))
        .filter((x) => x.el)
        .map((x) => ({ sel: x.sel, l: lum(getComputedStyle(x.el).backgroundColor) }))
        .filter((x) => Math.abs(x.l - bodyL) > 90);
    });
    assert(clash.length === 0, `не перекрасились: ${JSON.stringify(clash)}`);
    for (const tab of ["apply", "history", "settings"]) {
      await openTab(tab);
      await page.waitForTimeout(900);
      await shoot(`theme-${saved}-${tab}`);
    }
    await page.click("#theme-btn", { label: "toggle theme back" });
    await page.waitForFunction((b) => getComputedStyle(document.body).backgroundColor === b, before, { timeout: 3000 });
  });

  await check("мобильная ширина: без горизонтальной прокрутки", async () => {
    await page.cdp("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
    const errsBefore = await page.evaluate(() => window.__e2eErrors || []);
    await openTab("apply"); // дашборд восстанавливает последнюю вкладку, а список кампаний рисуется на своей
    await page.reload();
    await page.waitForFunction(() => /backend/.test(document.getElementById("campaigns-list")?.innerText || ""), undefined, { timeout: 15000 });
    await hookErrors();
    await page.evaluate((e) => window.__e2eErrors.push(...e), errsBefore);
    for (const tab of Object.keys(TABS)) {
      await page.evaluate((t) => window.switchTab ? window.switchTab(t) : document.querySelector(`.tab[data-tab="${t}"]`).click(), tab);
      await page.waitForTimeout(500);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      await shoot(`mobile-${tab}`);
      assert(overflow <= 1, `вкладка ${tab}: страница шире экрана на ${overflow}px`);
    }
    await page.cdp("Emulation.setDeviceMetricsOverride", DESKTOP);
  });

  await check("нет ошибок JavaScript", async () => {
    const errs = await page.evaluate(() => window.__e2eErrors || []);
    assert(errs.length === 0, errs.join(" | "));
  });

  if (EMPTY) {
    await check("без аккаунтов: экран подключения", async () => {
      await page.evaluate(() => localStorage.clear());
      await page.goto(EMPTY + "/");
      await page.waitForFunction(() => document.body.classList.contains("auth-required"), undefined, { timeout: 15000 });
      await page.waitForFunction(() => {
        const p = document.getElementById("panel-auth");
        return !!p && p.offsetParent !== null && /Подключите аккаунт/.test(p.innerText);
      }, undefined, { timeout: 5000 });
      await shoot("desktop-auth");
      await page.click("#auth-open-curl", { label: "open cURL login" });
      await page.waitForFunction(() => {
        const m = document.getElementById("login-modal"), c = document.getElementById("lm-panel-cookie");
        return m && getComputedStyle(m).display !== "none" && c && c.offsetParent !== null;
      }, undefined, { timeout: 5000 });
      await shoot("desktop-auth-curl");
    });
  }
} finally {
  await task.finish({ keep: [] });
}
console.log("E2E_RESULTS " + JSON.stringify(results));
if (missed.length) console.log("E2E_MISSED_SCREENSHOTS " + missed.join(","));
