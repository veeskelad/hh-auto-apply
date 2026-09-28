// Кампании: список с графиком откликов по дням и страница кампании.
// Подключается после app_v6.js и заменяет его renderCampaignsList; остальное
// (loadCampaigns, campStart/campStop/campEdit/campDelete, _campaignsCache) берётся оттуда.

const Camp = {
  applied: [],         // все отклики из /api/applied, для графиков и «сегодня»
  appliedAt: 0,
  range: 'month',      // week | month | all — окно графика на списке
  focus: null,         // id кампании, выделенной в графике списка
  detail: null,        // id открытой кампании
  tab: 'stats',        // stats | settings
  apps: null,          // отклики открытой кампании с hh-статусами
  appsFor: null,
  status: 'all',       // фильтр истории по статусу hh
  page: 1,
};

const CAMP_COLORS = ['#3457ec', '#15803d', '#c2410c', '#7c3aed', '#0e7490'];
const SKIP_REASONS = {
  already:  ['Уже откликались', ''],
  test:     ['Нужен тест работодателя', 'Включите «откликаться на вакансии с тестом» или отвечайте на них вручную во вкладке История → Тесты.'],
  title:    ['Название не прошло фильтр', 'Уберите лишние стоп-слова или отключите строгое совпадение названия.'],
  schedule: ['Не тот формат работы', 'Расширьте список форматов или снимите «только удалёнка».'],
  salary:   ['Зарплата ниже порога', 'Снизьте минимальную зарплату или разрешите вакансии без зарплаты.'],
};
const PAGE_SIZE = 10;

const dayKey = (d) => d.toISOString().slice(0, 10);
const fmtDay = (k) => `${k.slice(8, 10)}.${k.slice(5, 7)}`;
const fmtDateTime = (iso) => iso ? new Date(iso).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';
const plural = (n, a, b, c) => (typeof ruPlural === 'function' ? ruPlural(n, a, b, c) : c);
const campColor = (id) => {
  const i = _campaignsCache.findIndex((c) => c.id === id);
  return i >= 0 ? CAMP_COLORS[i % CAMP_COLORS.length] : 'var(--border-strong)';
};

async function campLoadApplied(force) {
  if (!force && Date.now() - Camp.appliedAt < 60000) return;
  try {
    const d = await (await fetch('/api/applied?limit=20000')).json();
    if (Array.isArray(d)) { Camp.applied = d; Camp.appliedAt = Date.now(); }
  } catch (e) { /* график просто останется прежним */ }
}

function campTodayCount() {
  const k = dayKey(new Date());
  return Camp.applied.filter((a) => (a.at || '').startsWith(k)).length;
}

function campDays(range) {
  const n = range === 'week' ? 7 : range === 'month' ? 30 : null;
  const today = new Date(); today.setHours(12, 0, 0, 0);
  let first;
  if (n) { first = new Date(today); first.setDate(first.getDate() - n + 1); }
  else {
    const oldest = Camp.applied.reduce((m, a) => (a.at && a.at < m ? a.at : m), dayKey(today));
    first = new Date(oldest.slice(0, 10) + 'T12:00:00');
  }
  const days = [];
  for (const d = new Date(first); d <= today; d.setDate(d.getDate() + 1)) days.push(dayKey(d));
  return days;
}

// Столбики по дням. series: [{id, color, label}], value(day, id) → число
function campChartSvg(days, series, value) {
  const W = 1000, H = 180, padL = 34, padB = 22, padT = 8;
  const totals = days.map((d) => series.reduce((s, x) => s + value(d, x.id), 0));
  const max = Math.max(4, ...totals);
  const step = Math.pow(10, Math.floor(Math.log10(max)));
  const top = Math.ceil(max / step) * step;
  const bw = (W - padL) / days.length;
  const y = (v) => padT + (H - padT - padB) * (1 - v / top);
  let svg = '';
  for (let i = 0; i <= 4; i++) {
    const v = Math.round((top / 4) * i), yy = y(v);
    svg += `<line x1="${padL}" x2="${W}" y1="${yy}" y2="${yy}" class="grid"/><text x="${padL - 6}" y="${yy + 4}" class="axis" text-anchor="end">${v}</text>`;
  }
  const labelEvery = Math.ceil(days.length / 12);
  days.forEach((d, i) => {
    let acc = 0;
    const x = padL + i * bw + bw * 0.18, w = Math.max(2, bw * 0.64);
    const parts = [];
    series.forEach((s) => {
      const v = value(d, s.id);
      if (!v) return;
      const y0 = y(acc), y1 = y(acc + v);
      svg += `<rect x="${x}" y="${y1}" width="${w}" height="${Math.max(1, y0 - y1)}" rx="2" fill="${s.color}"/>`;
      parts.push(`${s.label}: ${v}`);
      acc += v;
    });
    svg += `<rect x="${padL + i * bw}" y="${padT}" width="${bw}" height="${H - padT - padB}" fill="transparent"><title>${fmtDay(d)}: ${acc} ${plural(acc, 'отклик', 'отклика', 'откликов')}${parts.length > 1 ? '\n' + parts.join('\n') : ''}</title></rect>`;
    if (i % labelEvery === 0) svg += `<text x="${padL + i * bw + bw / 2}" y="${H - 6}" class="axis" text-anchor="middle">${fmtDay(d)}</text>`;
  });
  return `<svg class="camp-chart-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Отклики по дням">${svg}</svg>`;
}

function campCountBy(filterFn) {
  const m = {};
  Camp.applied.forEach((a) => { if (a.at && filterFn(a)) { const k = a.at.slice(0, 10); m[k] = (m[k] || 0) + 1; } });
  return m;
}

// ── Список ────────────────────────────────────────────────────────────
function renderCampaignsChart() {
  let box = document.getElementById('campaigns-chart');
  const list = document.getElementById('campaigns-list');
  if (!box && list) {
    box = document.createElement('section');
    box.id = 'campaigns-chart';
    box.className = 'camp-card camp-chart';
    list.parentNode.insertBefore(box, list.previousElementSibling || list);
  }
  if (!box) return;
  if (!Camp.applied.length) { box.hidden = true; return; }
  box.hidden = false;

  const days = campDays(Camp.range);
  const inRange = new Set(days);
  const known = new Set(_campaignsCache.map((c) => c.id));
  const byCamp = {};
  Camp.applied.forEach((a) => {
    if (!a.at || !inRange.has(a.at.slice(0, 10))) return;
    const id = known.has(a.campaign_id) ? a.campaign_id : '_other';
    (byCamp[id] = byCamp[id] || {})[a.at.slice(0, 10)] = ((byCamp[id] || {})[a.at.slice(0, 10)] || 0) + 1;
  });
  const sum = (id) => Object.values(byCamp[id] || {}).reduce((s, v) => s + v, 0);
  let series = _campaignsCache.map((c) => ({ id: c.id, color: campColor(c.id), label: c.name || 'Без названия' }));
  series.push({ id: '_other', color: 'var(--border-strong)', label: 'Без кампании' });
  series = series.filter((s) => sum(s.id) > 0);
  const total = series.reduce((s, x) => s + sum(x.id), 0);
  const shown = Camp.focus ? series.filter((s) => s.id === Camp.focus) : series;

  const chip = (id, label, n, color) => `<button type="button" class="camp-chip${(Camp.focus || null) === id ? ' on' : ''}" onclick="campFocus(${id ? `'${id}'` : 'null'})">${color ? `<i style="background:${color}"></i>` : ''}${esc(label)}<b>${n}</b></button>`;
  const rangeBtn = (r, label) => `<button type="button" class="${Camp.range === r ? 'on' : ''}" onclick="campRange('${r}')">${label}</button>`;
  box.innerHTML = `
    <header class="camp-chart-head">
      <h3>Отклики по дням</h3>
      <div class="camp-seg" role="group" aria-label="Период">${rangeBtn('week', 'Неделя')}${rangeBtn('month', 'Месяц')}${rangeBtn('all', 'Всё время')}</div>
    </header>
    <div class="camp-chips">${chip(null, 'Все кампании', total)}${series.map((s) => chip(s.id, s.label, sum(s.id), s.color)).join('')}</div>
    ${total ? campChartSvg(days, shown, (d, id) => (byCamp[id] || {})[d] || 0) : '<p class="camp-empty">За этот период откликов нет.</p>'}`;
}

function campFocus(id) { Camp.focus = Camp.focus === id ? null : id; renderCampaignsChart(); }
function campRange(r) { Camp.range = r; renderCampaignsChart(); }

function renderCampaignsList() {
  const el = document.getElementById('campaigns-list');
  if (!el) return;
  if (Camp.detail) { renderCampaignDetail(); }
  if (!_campaignsCache.length) {
    el.innerHTML = `<div class="camp-card camp-empty-state"><p>Кампаний пока нет. Кампания — это поисковый запрос, фильтры и лимиты: бот ищет вакансии и откликается от вашего имени.</p><button class="btn primary" onclick="newCampaign()">Создать кампанию</button></div>`;
    renderCampaignsChart();
    return;
  }
  const todayKey = dayKey(new Date());
  el.innerHTML = _campaignsCache.map((c) => {
    const s = c.stats || {};
    const running = c.status === 'running';
    const today = Camp.applied.filter((a) => a.campaign_id === c.id && (a.at || '').startsWith(todayKey)).length;
    return `<article class="camp-card camp-row" onclick="campOpen('${c.id}')" tabindex="0" onkeydown="if(event.key==='Enter')campOpen('${c.id}')">
      <span class="camp-dot" style="background:${campColor(c.id)}"></span>
      <div class="camp-row-main">
        <div class="camp-row-title"><h3>${esc(c.name || 'Без названия')}</h3>${_campStatusBadge(c.status)}</div>
        <p class="camp-row-query">${esc(c.search_query || '')}</p>
        <dl class="camp-row-stats">
          <div><dt>отправлено</dt><dd>${s.sent || 0}</dd></div>
          <div><dt>сегодня</dt><dd>${today}${c.daily_limit ? `<small> из ${c.daily_limit}</small>` : ''}</dd></div>
          <div><dt>пропущено</dt><dd>${s.skipped || 0}</dd></div>
          <div><dt>ошибок</dt><dd>${s.errors || 0}</dd></div>
          <div><dt>последний запуск</dt><dd class="muted">${fmtDateTime(s.started_at)}</dd></div>
        </dl>
      </div>
      <div class="camp-row-actions" onclick="event.stopPropagation()">
        ${running
          ? `<button class="btn" onclick="campStop('${c.id}',this)">Остановить</button>`
          : `<button class="btn primary" onclick="campStart('${c.id}',this)">Запустить</button>`}
        <button class="btn btn-ghost camp-open" onclick="campOpen('${c.id}')" aria-label="Открыть кампанию ${esc(c.name || '')}"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg></button>
      </div>
    </article>`;
  }).join('');
  renderCampaignsChart();
  campLoadApplied().then(() => { renderCampaignsChart(); setText('hdr-today', Math.max(Number(document.getElementById('hdr-today')?.textContent) || 0, campTodayCount())); });
}

// ── Страница кампании ─────────────────────────────────────────────────
function campOpen(id) {
  Camp.detail = id; Camp.tab = 'stats'; Camp.status = 'all'; Camp.page = 1;
  if (Camp.appsFor !== id) { Camp.apps = null; Camp.appsFor = id; campLoadApps(id); }
  campLoadApplied(true).then(renderCampaignDetail);
  renderCampaignDetail();
  document.querySelector('.dashboard-main')?.scrollTo({ top: 0 });
}

function campClose() {
  Camp.detail = null;
  const box = document.getElementById('campaign-detail');
  if (box) box.hidden = true;
  const dash = document.getElementById('campaigns-dash');
  if (dash) dash.hidden = false;
  renderCampaignsChart();
}

async function campLoadApps(id) {
  try {
    const d = await (await fetch(`/api/campaigns/${id}/applications`)).json();
    if (Camp.appsFor === id) { Camp.apps = d.applications || []; renderCampaignDetail(); }
  } catch (e) { if (Camp.appsFor === id) { Camp.apps = []; renderCampaignDetail(); } }
}

function campTab(t) { Camp.tab = t; renderCampaignDetail(); }
function campStatus(s) { Camp.status = s; Camp.page = 1; renderCampaignDetail(); }
function campPage(p) { Camp.page = p; renderCampaignDetail(); }

function renderCampaignDetail() {
  const c = _campaignsCache.find((x) => x.id === Camp.detail);
  const dash = document.getElementById('campaigns-dash');
  let box = document.getElementById('campaign-detail');
  if (!c) { if (Camp.detail && _campaignsCache.length) campClose(); return; }
  if (!box && dash) {
    box = document.createElement('div');
    box.id = 'campaign-detail';
    dash.parentNode.insertBefore(box, dash.nextSibling);
  }
  if (!box) return;
  if (dash) dash.hidden = true;
  box.hidden = false;

  const s = c.stats || {};
  const running = c.status === 'running';
  const mine = Camp.applied.filter((a) => a.campaign_id === c.id);
  const todayKey = dayKey(new Date());
  const today = mine.filter((a) => (a.at || '').startsWith(todayKey)).length;
  const sent = Math.max(s.sent || 0, mine.length);

  const head = `
    <button class="camp-back" onclick="campClose()"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>Все кампании</button>
    <header class="camp-detail-head">
      <div>
        <div class="camp-row-title"><h2>${esc(c.name || 'Без названия')}</h2>${_campStatusBadge(c.status)}</div>
        <p class="camp-row-query">${esc(c.search_query || '')}</p>
        ${c.created_at ? `<p class="camp-created muted">Создана ${fmtDateTime(c.created_at)}</p>` : ''}
      </div>
      <div class="camp-detail-actions">
        ${running ? `<button class="btn" onclick="campStop('${c.id}',this)">Остановить</button>` : `<button class="btn primary" onclick="campStart('${c.id}',this)">Запустить</button>`}
        <button class="btn" onclick="campClose(); campEdit('${c.id}')">Изменить</button>
        <button class="btn camp-danger" onclick="campDeleteFromDetail('${c.id}',this)">Удалить</button>
      </div>
    </header>
    <div class="camp-tabs" role="tablist">
      <button role="tab" aria-selected="${Camp.tab === 'stats'}" class="${Camp.tab === 'stats' ? 'on' : ''}" onclick="campTab('stats')">Статистика</button>
      <button role="tab" aria-selected="${Camp.tab === 'settings'}" class="${Camp.tab === 'settings' ? 'on' : ''}" onclick="campTab('settings')">Настройки</button>
    </div>`;

  box.innerHTML = head + (Camp.tab === 'stats' ? campStatsHtml(c, s, sent, today, mine) : campSettingsHtml(c));
}

async function campDeleteFromDetail(id, btn) {
  await campDelete(id, btn);
  await loadCampaigns();
  if (!_campaignsCache.find((x) => x.id === id)) campClose();
}

function campStatsHtml(c, s, sent, today, mine) {
  const tile = (n, label, hint, cls) => `<div class="camp-tile ${cls || ''}"><b>${n}</b><span>${label}</span><small>${hint}</small></div>`;
  const tiles = `<div class="camp-tiles">
    ${tile(sent, 'отправлено', 'за всё время кампании', 'is-sent')}
    ${tile(today, 'сегодня', c.daily_limit ? `лимит ${c.daily_limit}${c.daily_limit_max && c.daily_limit_max !== c.daily_limit ? '–' + c.daily_limit_max : ''} в день` : 'без дневного лимита')}
    ${tile(s.skipped || 0, 'пропущено', 'в последнем запуске, по фильтрам', 'is-skipped')}
    ${tile(s.errors || 0, 'ошибок', 'в последнем запуске', (s.errors ? 'is-error' : ''))}
  </div>`;

  const total = c.total_limit || 0;
  const pct = total ? Math.min(100, Math.round((sent / total) * 100)) : 0;
  const progress = `<section class="camp-card camp-progress">
    <div class="camp-progress-line"><span>${total ? `Отправлено ${sent} из ${total}` : `Отправлено ${sent}, общий лимит не задан`}</span>${total ? `<b>${pct}%</b>` : ''}</div>
    ${total ? `<div class="camp-bar"><i style="width:${pct}%"></i></div>` : ''}
    <ul class="camp-facts">
      <li><span>Письмо</span><b>${c.ai_cover_letter ? 'нейросеть пишет под каждую вакансию' : 'шаблон'}</b></li>
      <li><span>Последний запуск</span><b>${fmtDateTime(s.started_at)}${s.finished_at ? `, завершён ${fmtDateTime(s.finished_at)}` : ''}</b></li>
    </ul>
  </section>`;

  const reasons = Object.entries(s.skip_reasons || {}).filter(([, n]) => n > 0).sort((a, b) => b[1] - a[1]);
  const rmax = reasons.length ? reasons[0][1] : 0;
  const worst = reasons.find(([k]) => k !== 'already' && SKIP_REASONS[k] && SKIP_REASONS[k][1]);
  const why = `<section class="camp-card">
    <h3 class="camp-h">Почему пропущены вакансии</h3>
    ${reasons.length ? `<ul class="camp-reasons">${reasons.map(([k, n]) => `<li><span>${esc((SKIP_REASONS[k] || [k])[0])}</span><b>${n}</b><div class="camp-bar thin"><i style="width:${Math.max(2, Math.round((n / rmax) * 100))}%"></i></div></li>`).join('')}</ul>
      ${worst ? `<p class="camp-advice">Чтобы откликов стало больше: ${esc(SKIP_REASONS[worst[0]][1])}</p>` : ''}`
      : `<p class="camp-empty">Причины появятся после следующего запуска кампании.</p>`}
  </section>`;

  const days = campDays('month');
  const byDay = campCountBy((a) => a.campaign_id === c.id);
  const chart = `<section class="camp-card camp-chart">
    <header class="camp-chart-head"><h3>Отклики по дням</h3><span class="muted">последние 30 дней</span></header>
    ${mine.length ? campChartSvg(days, [{ id: c.id, color: campColor(c.id), label: c.name }], (d) => byDay[d] || 0) : '<p class="camp-empty">Откликов пока нет.</p>'}
  </section>`;

  return tiles + progress + why + chart + campHistoryHtml();
}

function campHistoryHtml() {
  if (Camp.apps === null) return `<section class="camp-card"><h3 class="camp-h">История откликов</h3><p class="camp-empty">Загружаю отклики и статусы с hh.ru…</p></section>`;
  const apps = Camp.apps;
  const counts = {};
  apps.forEach((a) => { const k = a.hh_status || 'Отправлен'; counts[k] = (counts[k] || 0) + 1; });
  const statusCls = (st) => /приглаш|интервью|собесед/i.test(st) ? 'ok' : /отказ/i.test(st) ? 'no' : /просмотр/i.test(st) ? 'seen' : '';
  const list = Camp.status === 'all' ? apps : apps.filter((a) => (a.hh_status || 'Отправлен') === Camp.status);
  const pages = Math.max(1, Math.ceil(list.length / PAGE_SIZE));
  Camp.page = Math.min(Camp.page, pages);
  const slice = list.slice((Camp.page - 1) * PAGE_SIZE, Camp.page * PAGE_SIZE);
  const chip = (k, label, n) => `<button type="button" class="camp-chip${Camp.status === k ? ' on' : ''}" onclick="campStatus('${k.replace(/'/g, "\\'")}')">${esc(label)}<b>${n}</b></button>`;
  const pager = pages > 1 ? `<nav class="camp-pager" aria-label="Страницы">
      <button ${Camp.page === 1 ? 'disabled' : ''} onclick="campPage(${Camp.page - 1})" aria-label="Назад">‹</button>
      <span>${Camp.page} из ${pages}</span>
      <button ${Camp.page === pages ? 'disabled' : ''} onclick="campPage(${Camp.page + 1})" aria-label="Вперёд">›</button></nav>` : '';
  return `<section class="camp-card">
    <header class="camp-chart-head"><h3>История откликов <span class="muted">${apps.length}</span></h3>${pager}</header>
    ${apps.length ? `<div class="camp-chips">${chip('all', 'Все', apps.length)}${Object.entries(counts).sort((a, b) => b[1] - a[1]).map(([k, n]) => chip(k, k, n)).join('')}</div>
    <ul class="camp-history">${slice.map((a) => `<li>
        <div><a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.title || 'Вакансия ' + a.vacancy_id)}</a><span class="muted">${esc(a.company || '')}</span></div>
        <span class="camp-status ${statusCls(a.hh_status || '')}">${esc(a.hh_status || 'Отправлен')}</span>
        <time class="muted">${fmtDateTime(a.at)}</time></li>`).join('')}</ul>`
      : '<p class="camp-empty">Откликов пока нет. Запустите кампанию, и здесь появится каждая вакансия со статусом на hh.ru.</p>'}
  </section>`;
}

function campSettingsHtml(c) {
  const exp = { noExperience: 'без опыта', between1And3: '1–3 года', between3And6: '3–6 лет', moreThan6: 'больше 6 лет' };
  const yes = (v) => (v ? 'да' : 'нет');
  const rows = [
    ['Поисковый запрос', c.search_query],
    ['Регион', c.region || 'любой'],
    ['Зарплата от', c.salary_from ? `${Number(c.salary_from).toLocaleString('ru-RU')} ₽` : 'не важна'],
    ['Опыт', exp[c.experience] || 'любой'],
    ['Только удалёнка', yes(c.remote_only)],
    ['Название должно содержать запрос', yes(c.strict_title_match)],
    ['Стоп-слова', c.stop_words || 'нет'],
    ['Откликов в день', c.daily_limit ? `${c.daily_limit}${c.daily_limit_max && c.daily_limit_max !== c.daily_limit ? '–' + c.daily_limit_max : ''}` : 'без лимита'],
    ['Всего откликов', c.total_limit || 'без лимита'],
    ['Письмо от нейросети', yes(c.ai_cover_letter)],
    ['Ответы на вопросы работодателя', yes(c.ai_answers)],
    ['Контакт в письме', c.tg || 'не указан'],
  ];
  return `<section class="camp-card">
    <header class="camp-chart-head"><h3>Параметры кампании</h3><button class="btn primary" onclick="campClose(); campEdit('${c.id}')">Изменить</button></header>
    <dl class="camp-kv">${rows.map(([k, v]) => `<div><dt>${k}</dt><dd>${esc(String(v))}</dd></div>`).join('')}</dl>
  </section>`;
}
