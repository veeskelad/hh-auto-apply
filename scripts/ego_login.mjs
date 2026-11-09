// Куки hh.ru из браузера ego lite → дашборд бота (/api/session/add).
// Запускает scripts/ego_login.py: он подставляет globalThis.__CFG = {base, name}.
// Значения кук не печатаются: в выводе только строка EGO_LOGIN {...} с итогом.
const cfg = globalThis.__CFG || {};
const SPACE = "hh-auto-apply login";
const out = (o) => console.log("EGO_LOGIN " + JSON.stringify(o));

// Своё пространство с прошлого раза (в том числе отданное человеку для входа)
let task;
const prev = (await listTaskSpaces()).filter((s) => s.name === SPACE);
if (prev.length) {
  const s = prev[prev.length - 1];
  task = s.ownership === "agent" ? await taskSpace(s.id) : await claimTaskSpace(s.id);
} else {
  task = await taskSpace(SPACE);
}
const pages = await task.pages();
const page = pages.length ? pages[0] : await task.newPage();

await page.goto("https://hh.ru/applicant/resumes", { timeout: 45000 });
await page.waitForLoadState("domcontentloaded").catch(() => {});
const url = await page.url();

const { cookies } = await page.cdp("Network.getCookies", { urls: ["https://hh.ru/"] });
const jar = Object.fromEntries(cookies.map((c) => [c.name, c.value]));
// hhtoken и _xsrf есть и у гостя; вошёл ли человек, видно по userType страницы
const userType = await page.evaluate(() => (window.globalVars || {}).userType || "").catch(() => "");
const loggedIn = !/\/account\/login/.test(url) && userType === "applicant" && jar.hhtoken && jar._xsrf;

if (!loggedIn) {
  if (!/\/account\/login/.test(url)) await page.goto("https://hh.ru/account/login", { timeout: 45000 });
  await task.handOff();
  out({ ok: false, need_login: true, space: task.spaceId,
        message: "Не выполнен вход на hh.ru. Войди в открытой вкладке ego lite и запусти команду ещё раз." });
} else {
  const cookieLine = cookies.map((c) => `${c.name}=${c.value}`).join("; ");
  let res;
  try {
    const r = await fetch(cfg.base + "/api/session/add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cookies: cookieLine, name: cfg.name || "" }),
    });
    res = await r.json();
  } catch (e) {
    res = { status: "error", message: "Дашборд не ответил: " + String(e).slice(0, 200) };
  }
  await task.finish({ keep: [] });
  out({ ok: res.status === "ok", message: res.message, name: res.name, idx: res.idx,
        keys: Object.keys(jar).filter((k) => ["hhtoken", "_xsrf", "hhul", "crypted_id"].includes(k)) });
}
