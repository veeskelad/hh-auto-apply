window.switchTab = function(tab) {
  const t = document.querySelector(`.tab[data-tab="${tab}"]`);
  if (!t) return;

  // HIDE campaign configurator when switching tabs manually
  closeModal();
  
  // Clear any inline display=none from panels that might have been set by modal logic
  document.querySelectorAll('.panel').forEach(p => p.style.display = '');

  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(el => el.classList.remove('active'));
  
  t.classList.add('active');
  const panel = document.getElementById('panel-' + tab);
  if (panel) panel.classList.add('active');
  
  State.currentTab = tab;
  try { localStorage.setItem('hh-tab', tab); } catch(e) {}

  // Reset settings-tab built flags so they rebuild with fresh data on next open
  if (tab !== 'settings') {
    const urlEl = document.getElementById('url-pool-rows');
    if (urlEl) urlEl.dataset.built = 'false';
    const sessEl = document.getElementById('sess-list');
    if (sessEl) sessEl.dataset.count = '';
  }

  // Load REST tabs on switch
  if (tab === 'history') {
    const subTab = localStorage.getItem('hh-history-tab') || 'applied';
    window.switchHistoryTab(subTab);
  }
  else if (tab === 'llm') {
    // Only reload table if stale (>10s since last load) — prevents wipe on quick tab switches
    const stale = Date.now() - _llmLastDbRefresh > 10000;
    if (stale) { llmInterviewsLoad(); llmRenderAccStats(); }
    if (State.lastSnapshot) renderLlmLog(State.lastSnapshot);
  }
  else if (tab === 'log' && State.lastSnapshot) renderLog(State.lastSnapshot);
  else if (tab === 'apply') {
    closeConfigurator();             // показываем список, не форму
    if (State.lastSnapshot) renderCampaignAccountUI(State.lastSnapshot);
    loadCampaigns();                 // подтянуть библиотеку кампаний + сводку
  }
  else if (tab === 'settings' && State.lastSnapshot) {
    syncSettingsSliders(State.lastSnapshot);
    qSyncFromSnapshot(State.lastSnapshot);
    ltSyncFromSnapshot(State.lastSnapshot);
    buildAccCookiesList(State.lastSnapshot);
    urlPoolBuild(State.lastSnapshot);
    buildSessList(State.lastSnapshot);
  }
};

window.switchHistoryTab = function(subTab) {
  document.querySelectorAll('.history-tab').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.history-subpanel').forEach(el => el.classList.remove('active'));
  
  const t = document.querySelector(`.history-tab[data-subtab="${subTab}"]`);
  if (t) t.classList.add('active');
  
  const panel = document.getElementById('panel-' + subTab);
  if (panel) panel.classList.add('active');
  
  try { localStorage.setItem('hh-history-tab', subTab); } catch(e) {}

  // Load sub-tab content
  if (subTab === 'applied') loadApplied();
  else if (subTab === 'tests') loadTests();
  else if (subTab === 'db') loadDB();
  else if (subTab === 'hh' && State.lastSnapshot) renderHH(State.lastSnapshot);
  else if (subTab === 'views') loadViews();
};

// ── i18n ──────────────────────────────────────────────────────
let lang = localStorage.getItem('hh-lang') || 'ru';

const T = {
  ru: {
    // Tabs
    tab_main: 'Обзор',
    tab_log: 'Диагностика',
    tab_history: 'История',
    tab_llm: 'Чаты',
    tab_apply: 'Кампании',
    tab_settings: 'Настройки',
    // Header
    hdr_found: 'найдено',
    hdr_replies: 'откликов',
    hdr_in_db: 'в базе',
    hdr_tests: 'тестов',
    hdr_new_views: 'новых просм.',
    hdr_new_inv: 'новых приглаш.',
    hdr_shows: 'показов',
    btn_pause: 'Пауза',
    btn_resume: 'Продолжить (все)',
    // Status badges
    status_idle: 'ОЖИДАНИЕ',
    status_collecting: 'СБОР ВАКАНСИЙ',
    status_applying: 'ОТПРАВКА ОТКЛИКОВ',
    status_limit: 'ЛИМИТ',
    status_waiting: 'ПАУЗА',
    status_checking: 'ПРОВЕРКА ЛИМИТА',
    status_inactive: 'НЕАКТИВНА',
    status_all_paused: 'ВСЕ НА ПАУЗЕ',
    status_acc_paused: 'НА ПАУЗЕ',
    status_daily_limit: 'ДНЕВНОЙ ЛИМИТ',
    status_daily_limit_hint: 'Дневной лимит откликов исчерпан. Сбросится завтра в 00:00',
    status_hh_limit: 'ЛИМИТ HH',
    status_hh_limit_hint: 'HH ограничил отклики. Бот проверит снятие лимита автоматически',
    // Card labels
    stat_replies: 'Отклики',
    stat_tests: 'Тесты',
    stat_surveys: 'Опросы',
    stat_already: 'Повторы',
    stat_errors: 'Ошибки',
    stat_salary: 'Зарплата',
    stat_interviews: 'Интервью',
    stat_new_inv: 'Новые',
    card_waiting: 'Ожидание...',
    card_hh_loading: 'Загружаю HH данные...',
    card_sending: 'Отправка...',
    btn_acc_pause: 'Пауза аккаунта',
    btn_acc_resume: 'Продолжить',
    btn_acc_global_pause: 'Глобальная пауза',
    btn_resume_touch: 'Поднять резюме',
    btn_clear_discards: 'Скрыть отказы из чатов',
    btn_launch: 'Запустить',
    btn_delete: 'Удалить',
    card_apply_tests: 'Откликаться на вакансии с тестом',
    letter_section: 'Письмо',
    url_section: 'URL поиска',
    btn_save: 'Сохранить',
    btn_apply_url: 'Применить',
    cookies_expired_badge: 'Куки протухли! Обновите куки',
    errs_in_row: 'ошибок подряд',
    // Global stats
    gs_session: 'Сессия',
    gs_found: 'Найдено',
    gs_applied: 'Отклики',
    gs_tests: 'Тесты',
    gs_errors: 'Ошибки',
    gs_in_db: 'В базе',
    gs_in_db_tests: 'Тесты',
    sidebar_recent: 'Последние отклики',
    recent_empty: 'Ожидание откликов...',
    no_accounts: 'Нет аккаунтов. Добавьте аккаунт в настройках',
    // Resume stats
    rs_views: 'просм. (7д)',
    rs_shows: 'показов',
    rs_inv: 'приглаш.',
    rs_raise_in: 'поднять через',
    rs_raises_avail: 'поднятий доступно',
    // Log tab
    log_search_ph: 'Поиск...',
    log_all_accs: 'Все аккаунты',
    log_all: 'Все',
    // Applied tab
    applied_title: 'Отклики',
    applied_search_ph: 'Поиск по названию / компании...',
    applied_all_accs: 'Все аккаунты',
    applied_only_named: 'Только с названием',
    col_date: 'Дата',
    col_account: 'Аккаунт',
    col_vacancy: 'Вакансия',
    col_company: 'Компания',
    col_salary: 'Зарплата',
    btn_show_more: 'Показать ещё',
    shown_of: 'показано',
    shown_of2: 'из',
    // Tests tab
    tests_title: 'Вакансии с тестами',
    col_applied_yn: 'Откликнулись',
    col_link: 'Ссылка',
    // DB tab
    db_title: 'База вакансий',
    db_search_ph: 'Название / компания / ID...',
    db_all_statuses: 'Все статусы',
    db_status_sent: 'Откликнулись',
    db_status_test_passed: 'Тест пройден',
    db_status_test_pending: 'Тест не пройден',
    db_all_accs: 'Все аккаунты',
    col_status: 'Статус',
    col_accounts: 'Аккаунты',
    // HH Status
    hh_interviews: 'Интервью',
    hh_viewed: 'Просмотрено',
    hh_discards: 'Отказы',
    hh_not_viewed: 'Не просм.',
    hh_updated: 'Обновлено:',
    hh_inv_list: 'Приглашения на интервью:',
    hh_offers: 'Возможные предложения:',
    hh_no_data: 'Нет данных',
    hh_loading: 'Загружаю данные HH...',
    // Views tab
    views_7d: 'Просмотров резюме (7д)',
    views_new: 'Новых просмотров',
    views_shows: 'Показов в поиске',
    views_invitations: 'Приглашений (7д)',
    views_inv_new: 'Новых приглашений',
    views_loading: 'Загружаю историю просмотров...',
    btn_load_history: '↻ Загрузить историю',
    views_no_data: 'Нет данных (обновите через 15 мин)',
    col_employer: 'Компания',
    // Apply tab
    apply_title: 'Ручной отклик',
    apply_desc: 'Введите ссылку или ID вакансии — бот проверит, нужен ли опрос, покажет вопросы и отправит отклик.',
    apply_label_acc: 'Аккаунт',
    apply_label_vacancy: 'Ссылка на вакансию или ID',
    apply_vacancy_ph: 'https://hh.ru/vacancy/130334718 или просто 130334718',
    apply_label_tpl: 'Шаблон письма',
    apply_tpl_ph: '— выбрать шаблон —',
    apply_btn_clear: 'Очистить',
    apply_label_letter: 'Сопроводительное письмо',
    apply_letter_ph: 'Сопроводительное письмо (необязательно)',
    apply_btn_check: 'Проверить / Откликнуться',
    // Settings tab
    settings_title: 'Настройки бота',
    btn_apply_settings: 'Применить',
    settings_applied: 'Настройки применены',
    // Settings param labels
    lbl_pages_per_url: 'Страниц на URL',
    hint_pages_per_url: 'Сколько страниц результатов загружать для каждого поискового запроса',
    lbl_response_delay: 'Задержка отклика (с)',
    hint_response_delay: 'Пауза между пачками откликов в секундах',
    lbl_pause_between_cycles: 'Пауза между циклами (с)',
    hint_pause_between_cycles: 'Ожидание после завершения полного цикла обработки вакансий',
    lbl_batch_responses: 'Размер пачки откликов',
    hint_batch_responses: 'Сколько откликов отправлять параллельно',
    lbl_limit_check_interval: 'Интервал проверки лимита (м)',
    hint_limit_check_interval: 'Как часто проверять сброс дневного лимита откликов',
    lbl_min_salary: 'Минимальная зарплата (₽)',
    hint_min_salary: 'Пропускать вакансии с зарплатой ниже указанной (0 = без фильтра)',
    lbl_auto_pause_errors: 'Авто-пауза при ошибках',
    hint_auto_pause_errors: 'Авто-пауза аккаунта после N ошибок подряд (0 = выключено)',
    // Settings sections
    sec_main_accounts: 'Основные аккаунты',
    sec_main_accounts_desc: 'Добавляйте и редактируйте основные аккаунты. Изменения сохраняются в data/accounts.json.',
    sec_url_pool: 'Пул поисковых запросов',
    sec_url_pool_desc: 'Добавьте URL-адреса поиска вакансий — они появятся как чекбоксы на карточке каждого аккаунта.',
    sec_letters: 'Шаблоны писем',
    sec_letters_desc: 'Создайте именованные шаблоны — они появятся в выпадающем списке на каждой карточке аккаунта.',
    sec_questionnaire: 'Шаблонные ответы на опросы',
    sec_questionnaire_desc: 'Когда вакансия требует опрос — бот автоматически заполнит его.',
    sec_cookies: 'Обновить куки аккаунтов',
    sec_sessions: 'Браузерные сессии',
    // Account form
    acc_field_name: 'Имя (полное)',
    acc_field_short: 'Короткое имя',
    acc_field_color: 'Цвет',
    acc_ph_name: 'Иван (основной)',
    acc_ph_short: 'основной',
    acc_cookies_label: 'Cookies (cURL или строка)',
    btn_add: 'Добавить',
    btn_add_account: 'Добавить аккаунт',
    btn_add_url: 'Добавить URL',
    btn_save_pool: 'Сохранить пул',
    btn_add_template: 'Добавить шаблон',
    btn_save_templates: 'Сохранить шаблоны',
    // Questionnaire
    q_keywords_ph: 'опыт, работа, QA',
    q_keywords_label: 'Ключевые слова (через запятую)',
    q_answer_label: 'Ответ',
    q_default_label: 'Ответ по умолчанию (если ни один шаблон не подошёл)',
    q_default_ph: 'Готова рассказать подробнее на собеседовании.',
    // Cookies section
    ck_desc: 'Вставьте новый cURL или строку cookie: hhtoken=…',
    btn_update_cookies: 'Обновить куки',
    // Sessions
    sess_add: 'Добавить сессию из браузера',
    sess_mode_curl: 'cURL / строка',
    sess_mode_manual: 'Вручную',
    sess_curl_desc: 'Самый простой способ — Copy as cURL',
    sess_name_label: 'Имя (необязательно)',
    sess_name_ph: 'Например: Мария',
    sess_letter_label: 'Сопроводительное письмо (необязательно)',
    btn_connect: 'Подключить сессию',
    sess_active: 'активна',
    sess_inactive: 'неактивна',
    // Confirm dialogs
    confirm_delete: 'Удалить',
    confirm_cancel: 'Отмена',
    // Shortcuts
    shortcuts_title: 'Горячие клавиши',
    shortcuts_tabs: 'Переключить вкладку',
    shortcuts_pause: 'Пауза / продолжить все',
    shortcuts_help: 'Это окно',
    shortcuts_esc: 'Закрыть это окно',
    btn_close: 'Закрыть',
    // Notifications
    notif_new_inv: 'Новое приглашение —',
    notif_inv_count_pre: 'Теперь',
    notif_inv_count_mid: 'интервью (+',
    notif_limit: 'Лимит —',
    notif_limit_body: 'Дневной лимит откликов исчерпан',
    notif_cookies: 'Куки протухли —',
    notif_cookies_body: 'Обновите куки в настройках аккаунта',
    // Page titles
    title_limit: 'ЛИМИТ | HH Bot',
    title_paused: 'Пауза | HH Bot',
    // Confirm dialog texts
    confirm_del_acc_pre: 'Удалить аккаунт',
    confirm_del_acc_body: 'Воркер будет остановлен.',
    confirm_del_db_pre: 'Удалить',
    confirm_del_db_mid: 'из базы?',
    confirm_del_db_body: 'Бот сможет откликнуться повторно.',
    confirm_del_sess: 'Удалить браузерную сессию?',
  },
  en: {
    // Tabs
    tab_main: 'Overview',
    tab_log: 'Diagnostics',
    tab_history: 'History',
    tab_llm: 'Chats',
    tab_apply: 'Campaigns',
    tab_settings: 'Settings',
    // Header
    hdr_found: 'found',
    hdr_replies: 'applied',
    hdr_in_db: 'in DB',
    hdr_tests: 'tests',
    hdr_new_views: 'new views',
    hdr_new_inv: 'new invitations',
    hdr_shows: 'shows',
    btn_pause: 'Pause',
    btn_resume: 'Resume (all)',
    // Status badges
    status_idle: 'IDLE',
    status_collecting: 'COLLECTING',
    status_applying: 'APPLYING',
    status_limit: 'LIMIT',
    status_waiting: 'PAUSED',
    status_checking: 'CHECKING LIMIT',
    status_inactive: 'INACTIVE',
    status_all_paused: 'ALL PAUSED',
    status_acc_paused: 'PAUSED',
    status_daily_limit: 'DAILY LIMIT',
    status_daily_limit_hint: 'Daily apply limit reached. Resets at midnight',
    status_hh_limit: 'HH LIMIT',
    status_hh_limit_hint: 'HH rate-limited responses. Bot will auto-check for reset',
    // Card labels
    stat_replies: 'Replies',
    stat_tests: 'Tests',
    stat_surveys: 'Surveys',
    stat_already: 'Already',
    stat_errors: 'Errors',
    stat_salary: 'Salary',
    stat_interviews: 'Interviews',
    stat_new_inv: 'New inv.',
    card_waiting: 'Waiting...',
    card_hh_loading: 'Loading HH data...',
    card_sending: 'Sending...',
    btn_acc_pause: 'Pause account',
    btn_acc_resume: 'Resume',
    btn_acc_global_pause: 'Global pause',
    btn_resume_touch: 'Raise resume',
    btn_clear_discards: 'Hide rejections from chats',
    btn_launch: 'Launch',
    btn_delete: 'Delete',
    card_apply_tests: 'Apply to vacancies with test',
    letter_section: 'Letter',
    url_section: 'Search URLs',
    btn_save: 'Save',
    btn_apply_url: 'Apply',
    cookies_expired_badge: 'Cookies expired! Update cookies',
    errs_in_row: 'errors in a row',
    // Global stats
    gs_session: 'Session',
    gs_found: 'Found',
    gs_applied: 'Applied',
    gs_tests: 'Tests',
    gs_errors: 'Errors',
    gs_in_db: 'In DB',
    gs_in_db_tests: 'Tests',
    sidebar_recent: 'Recent Replies',
    recent_empty: 'Waiting for replies...',
    no_accounts: 'No accounts. Add an account in Settings',
    // Resume stats
    rs_views: 'views (7d)',
    rs_shows: 'shows',
    rs_inv: 'invitations',
    rs_raise_in: 'raise in',
    rs_raises_avail: 'raises available',
    // Log tab
    log_search_ph: 'Search...',
    log_all_accs: 'All accounts',
    log_all: 'All',
    // Applied tab
    applied_title: 'Applied',
    applied_search_ph: 'Search by title / company...',
    applied_all_accs: 'All accounts',
    applied_only_named: 'Only with title',
    col_date: 'Date',
    col_account: 'Account',
    col_vacancy: 'Vacancy',
    col_company: 'Company',
    col_salary: 'Salary',
    btn_show_more: 'Show more',
    shown_of: 'showing',
    shown_of2: 'of',
    // Tests tab
    tests_title: 'Vacancies with tests',
    col_applied_yn: 'Applied',
    col_link: 'Link',
    // DB tab
    db_title: 'Vacancy Database',
    db_search_ph: 'Title / company / ID...',
    db_all_statuses: 'All statuses',
    db_status_sent: 'Applied',
    db_status_test_passed: 'Test passed',
    db_status_test_pending: 'Test pending',
    db_all_accs: 'All accounts',
    col_status: 'Status',
    col_accounts: 'Accounts',
    // HH Status
    hh_interviews: 'Interviews',
    hh_viewed: 'Viewed',
    hh_discards: 'Discards',
    hh_not_viewed: 'Not viewed',
    hh_updated: 'Updated:',
    hh_inv_list: 'Interview invitations:',
    hh_offers: 'Possible offers:',
    hh_no_data: 'No data',
    hh_loading: 'Loading HH data...',
    // Views tab
    views_7d: 'Resume views (7d)',
    views_new: 'New views',
    views_shows: 'Search shows',
    views_invitations: 'Invitations (7d)',
    views_inv_new: 'New invitations',
    views_loading: 'Loading view history...',
    btn_load_history: '↻ Load history',
    views_no_data: 'No data (refresh in 15 min)',
    col_employer: 'Company',
    // Apply tab
    apply_title: 'Manual Apply',
    apply_desc: 'Enter vacancy URL or ID — the bot will check if a survey is required, show questions, and submit the reply.',
    apply_label_acc: 'Account',
    apply_label_vacancy: 'Vacancy URL or ID',
    apply_vacancy_ph: 'https://hh.ru/vacancy/130334718 or just 130334718',
    apply_label_tpl: 'Letter template',
    apply_tpl_ph: '— select template —',
    apply_btn_clear: 'Clear',
    apply_label_letter: 'Cover letter',
    apply_letter_ph: 'Cover letter (optional)',
    apply_btn_check: 'Check / Apply',
    // Settings tab
    settings_title: 'Bot Settings',
    btn_apply_settings: 'Apply',
    settings_applied: 'Settings applied',
    // Settings param labels
    lbl_pages_per_url: 'Pages per URL',
    hint_pages_per_url: 'How many result pages to load per search query',
    lbl_response_delay: 'Reply delay (s)',
    hint_response_delay: 'Pause between reply batches in seconds',
    lbl_pause_between_cycles: 'Pause between cycles (s)',
    hint_pause_between_cycles: 'Wait after completing a full vacancy processing cycle',
    lbl_batch_responses: 'Reply batch size',
    hint_batch_responses: 'How many replies to send in parallel',
    lbl_limit_check_interval: 'Limit check interval (m)',
    hint_limit_check_interval: 'How often to check daily reply limit reset',
    lbl_min_salary: 'Minimum salary (₽)',
    hint_min_salary: 'Skip vacancies with salary below specified (0 = no filter)',
    lbl_auto_pause_errors: 'Auto-pause on errors',
    hint_auto_pause_errors: 'Auto-pause account after N consecutive errors (0 = disabled)',
    // Settings sections
    sec_main_accounts: 'Main Accounts',
    sec_main_accounts_desc: 'Add and edit main accounts. Changes are saved to data/accounts.json.',
    sec_url_pool: 'Search URL Pool',
    sec_url_pool_desc: 'Add search URLs — they will appear as checkboxes on each account card.',
    sec_letters: 'Letter Templates',
    sec_letters_desc: 'Create named templates — they will appear in the dropdown on each account card.',
    sec_questionnaire: 'Questionnaire Templates',
    sec_questionnaire_desc: 'When a vacancy requires a survey — the bot will fill it automatically.',
    sec_cookies: 'Update Account Cookies',
    sec_sessions: 'Browser Sessions',
    // Account form
    acc_field_name: 'Full name',
    acc_field_short: 'Short name',
    acc_field_color: 'Color',
    acc_ph_name: 'Ivan (main)',
    acc_ph_short: 'main',
    acc_cookies_label: 'Cookies (cURL or string)',
    btn_add: 'Add',
    btn_add_account: 'Add account',
    btn_add_url: 'Add URL',
    btn_save_pool: 'Save pool',
    btn_add_template: 'Add template',
    btn_save_templates: 'Save templates',
    // Questionnaire
    q_keywords_ph: 'experience, work, QA',
    q_keywords_label: 'Keywords (comma-separated)',
    q_answer_label: 'Answer',
    q_default_label: 'Default answer (if no template matched)',
    q_default_ph: 'I\'d be happy to share more details at the interview.',
    // Cookies section
    ck_desc: 'Paste new cURL or cookie string: hhtoken=…',
    btn_update_cookies: 'Update cookies',
    // Sessions
    sess_add: 'Add browser session',
    sess_mode_curl: 'cURL / string',
    sess_mode_manual: 'Manual',
    sess_curl_desc: 'Easiest way — Copy as cURL',
    sess_name_label: 'Name (optional)',
    sess_name_ph: 'e.g.: Maria',
    sess_letter_label: 'Cover letter (optional)',
    btn_connect: 'Connect session',
    sess_active: 'active',
    sess_inactive: 'inactive',
    // Confirm dialogs
    confirm_delete: 'Delete',
    confirm_cancel: 'Cancel',
    // Shortcuts
    shortcuts_title: 'Keyboard Shortcuts',
    shortcuts_tabs: 'Switch tab',
    shortcuts_pause: 'Pause / resume all',
    shortcuts_help: 'This window',
    shortcuts_esc: 'Close this window',
    btn_close: 'Close',
    // Notifications
    notif_new_inv: 'New invitation —',
    notif_inv_count_pre: 'Now',
    notif_inv_count_mid: 'interviews (+',
    notif_limit: 'Limit —',
    notif_limit_body: 'Daily reply limit reached',
    notif_cookies: 'Cookies expired —',
    notif_cookies_body: 'Update cookies in account settings',
    // Page titles
    title_limit: 'LIMIT | HH Bot',
    title_paused: 'Paused | HH Bot',
    // Confirm dialog texts
    confirm_del_acc_pre: 'Delete account',
    confirm_del_acc_body: 'Worker will be stopped.',
    confirm_del_db_pre: 'Delete',
    confirm_del_db_mid: 'from DB?',
    confirm_del_db_body: 'Bot will be able to apply again.',
    confirm_del_sess: 'Delete browser session?',
  }
};

function t(key) {
  return (T[lang]?.[key]) ?? (T.ru[key]) ?? key;
}

function applyI18n() {
  document.documentElement.lang = lang;
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    const val = t(key);
    // For th elements with sort arrows, preserve the arrow span
    const arrow = el.querySelector('.sort-arrow');
    if (arrow) {
      // Replace text before the arrow span
      const nodes = Array.from(el.childNodes);
      const textNode = nodes.find(n => n.nodeType === Node.TEXT_NODE);
      if (textNode) textNode.textContent = val + ' ';
      else el.insertBefore(document.createTextNode(val + ' '), el.firstChild);
    } else {
      el.textContent = val;
    }
  });
  document.querySelectorAll('[data-i18n-ph]').forEach(el => {
    el.placeholder = t(el.dataset.i18nPh);
  });
  // Rebuild settings labels/hints
  document.querySelectorAll('[data-setting-label]').forEach(el => {
    const key = el.dataset.settingLabel;
    const def = SETTINGS_DEF.find(s => s.key === key);
    if (def) {
      const span = el.querySelector('span');
      el.textContent = t(def.labelKey) + ' ';
      if (span) el.appendChild(span);
    }
  });
  document.querySelectorAll('[data-setting-desc]').forEach(el => {
    const key = el.dataset.settingDesc;
    const def = SETTINGS_DEF.find(s => s.key === key);
    if (def) el.textContent = t(def.descKey);
  });
  if (State && State.lastSnapshot) {
    try { renderAll(State.lastSnapshot); } catch(e) {}
  }
}

function toggleLang() {
  lang = lang === 'ru' ? 'en' : 'ru';
  localStorage.setItem('hh-lang', lang);
  document.getElementById('lang-btn').textContent = lang.toUpperCase();
  applyI18n();
}

// ── State ──────────────────────────────────────────────────────
const State = {
  ws: null,
  lastSnapshot: null,
  currentTab: 'apply',
  reconnectDelay: 1000,
  reconnectTimer: null,
  logNodeCount: 0,
  MAX_LOG_NODES: 100,
  prevInterviews: {},      // {acc_idx: count} — для браузерных уведомлений
  prevLimitState: {},      // {acc_idx: bool}
  prevCookiesExpired: {},  // {acc_idx: bool}
  compactCards: new Set(), // idx карточек в компактном режиме
  logLevel: '',          // фильтр уровня лога
};
let _campaignConfiguratorDismissed = false;
let _loginModalDismissed = false;
let _llmSettingsEditing = false;
let _llmSettingsEditTimer = null;
const AppliedSort = { field: 'at', dir: -1 };  // -1=desc 1=asc
const DBSort      = { field: 'at', dir: -1 };

// Settings config definition
const SETTINGS_DEF = [
  { key: 'pages_per_url',        labelKey: 'lbl_pages_per_url',        descKey: 'hint_pages_per_url',        min: 5,  max: 100, step: 5  },
  { key: 'response_delay',       labelKey: 'lbl_response_delay',       descKey: 'hint_response_delay',       min: 0,  max: 30,  step: 1  },
  { key: 'pause_between_cycles', labelKey: 'lbl_pause_between_cycles', descKey: 'hint_pause_between_cycles', min: 15, max: 600, step: 15 },
  { key: 'batch_responses',      labelKey: 'lbl_batch_responses',      descKey: 'hint_batch_responses',      min: 1,  max: 10,  step: 1  },
  { key: 'limit_check_interval', labelKey: 'lbl_limit_check_interval', descKey: 'hint_limit_check_interval', min: 5,  max: 120, step: 5  },
  { key: 'min_salary',           labelKey: 'lbl_min_salary',           descKey: 'hint_min_salary',           min: 0,  max: 300000, step: 10000 },
  { key: 'auto_pause_errors',    labelKey: 'lbl_auto_pause_errors',    descKey: 'hint_auto_pause_errors',    min: 0,  max: 20,  step: 1  },
];

// Build settings UI once
function buildSettings() {
  const grid = document.getElementById('settings-grid');
  grid.innerHTML = '';
  SETTINGS_DEF.forEach(s => {
    const row = document.createElement('div');
    row.className = 'setting-row';
    row.dataset.settingKey = s.key;
    row.innerHTML = `
      <div class="setting-label" data-setting-label="${s.key}">${t(s.labelKey)} <span id="sv-${s.key}">—</span></div>
      <div class="setting-desc" data-setting-desc="${s.key}">${t(s.descKey)}</div>
      <input type="range" id="sr-${s.key}" min="${s.min}" max="${s.max}" step="${s.step}" value="${s.min}"
        oninput="document.getElementById('sv-${s.key}').textContent=this.value">
    `;
    grid.appendChild(row);
  });
}

// ── Letter templates (Settings) ──────────────────────────────
function ltRenderTemplates(templates) {
  const list = document.getElementById('lt-templates-list');
  if (!list) return;
  list.innerHTML = '';
  (templates || []).forEach((t, i) => {
    const row = document.createElement('div');
    row.className = 'q-template-row';
    row.dataset.idx = i;
    row.innerHTML =
      `<button class="q-del" onclick="ltDelTemplate(${i})">×</button>` +
      `<div style="flex:1">` +
        `<input class="q-keywords-input" placeholder="Название шаблона (напр: IT, Аналитик)" value="${esc(t.name||'')}">` +
        `<textarea class="q-answer-input" rows="3" placeholder="Текст письма...">${esc(t.text||'')}</textarea>` +
      `</div>`;
    list.appendChild(row);
  });
}

function ltAddTemplate() {
  const list = document.getElementById('lt-templates-list');
  if (!list) return;
  const i = list.children.length;
  const row = document.createElement('div');
  row.className = 'q-template-row';
  row.dataset.idx = i;
  row.innerHTML =
    `<button class="q-del" onclick="ltDelTemplate(${i})">×</button>` +
    `<div style="flex:1">` +
      `<input class="q-keywords-input" placeholder="Название шаблона">` +
      `<textarea class="q-answer-input" rows="3" placeholder="Текст письма..."></textarea>` +
    `</div>`;
  list.appendChild(row);
}

function ltDelTemplate(idx) {
  const list = document.getElementById('lt-templates-list');
  if (!list) return;
  const rows = list.querySelectorAll('.q-template-row');
  if (rows[idx]) rows[idx].remove();
  // Re-index delete buttons
  list.querySelectorAll('.q-template-row').forEach((r, i) => {
    r.dataset.idx = i;
    const btn = r.querySelector('.q-del');
    if (btn) btn.onclick = () => ltDelTemplate(i);
  });
}

function ltReadTemplates() {
  const list = document.getElementById('lt-templates-list');
  if (!list) return [];
  return Array.from(list.querySelectorAll('.q-template-row')).map(r => ({
    name: (r.querySelector('.q-keywords-input')?.value || '').trim(),
    text: (r.querySelector('.q-answer-input')?.value || '').trim(),
  })).filter(t => t.name || t.text);
}

function ltSave() {
  const templates = ltReadTemplates();
  sendCmd({ type: 'set_letter_templates', templates });
  const st = document.getElementById('lt-status');
  if (st) { st.textContent = 'Сохранено'; setTimeout(() => { st.textContent = ''; }, 3000); }
}

function ltSyncFromSnapshot(snap) {
  const templates = snap?.config?.letter_templates || [];
  ltRenderTemplates(templates);
}

// ── LLM multi-profile ─────────────────────────────────────────
let _llmDetectTimers = {};

function llmProfileAdd(profile) {
  const p = profile || {name: '', api_key: '', base_url: '', model: '', enabled: true};
  const list = document.getElementById('llm-profiles-list');
  const idx = list.children.length;
  const row = document.createElement('div');
  row.className = 'llm-profile-row' + (p.enabled === false ? ' disabled' : '');
  row.dataset.idx = idx;
  row.innerHTML = `
    <div class="llm-profile-row-header">
      <input class="form-input" style="font-size:11px;flex:1" placeholder="Название (например: DeepSeek)" value="${esc(p.name||'')}">
      <label style="display:flex;align-items:center;gap:4px;font-size:11px;cursor:pointer;white-space:nowrap">
        <input type="checkbox" class="lp-enabled" ${p.enabled !== false ? 'checked' : ''} style="accent-color:var(--cyan)"> Вкл
      </label>
      <button class="btn-sm" style="color:var(--red);border-color:var(--red);padding:1px 8px" onclick="this.closest('.llm-profile-row').remove();llmProfileReindex()">×</button>
    </div>
    <div class="llm-profile-fields">
      <div>
        <div style="font-size:10px;color:var(--dim);margin-bottom:2px">API Key</div>
        <input class="form-input" type="password" style="font-size:11px" placeholder="sk-..." value="${esc(p.api_key||'')}" oninput="llmProfileDetectDebounce(this)">
      </div>
      <div>
        <div style="font-size:10px;color:var(--dim);margin-bottom:2px">Модель</div>
        <input class="form-input" style="font-size:11px" placeholder="gpt-4o-mini" value="${esc(p.model||'')}">
      </div>
    </div>
    <div style="display:flex;gap:6px;align-items:center">
      <div style="flex:1">
        <div style="font-size:10px;color:var(--dim);margin-bottom:2px">Base URL</div>
        <input class="form-input" style="font-size:11px" placeholder="https://api.openai.com/v1" value="${esc(p.base_url||'')}">
      </div>
      <div style="display:flex;flex-direction:column;gap:3px;padding-top:14px">
        <button class="btn-sm" onclick="llmProfileDetect(this.closest('.llm-profile-row'))" title="Определить провайдера и загрузить модели">Определить</button>
        <span class="lp-status" style="font-size:10px;color:var(--dim)"></span>
      </div>
    </div>
  `;
  list.appendChild(row);
}

function llmProfileReindex() {
  document.querySelectorAll('#llm-profiles-list .llm-profile-row').forEach((row, i) => { row.dataset.idx = i; });
}

function llmProfileDetectDebounce(keyInput) {
  const row = keyInput.closest('.llm-profile-row');
  const idx = row.dataset.idx;
  clearTimeout(_llmDetectTimers[idx]);
  _llmDetectTimers[idx] = setTimeout(() => llmProfileDetect(row), 900);
}

async function llmProfileDetect(row) {
  const keyEl = row.querySelector('.lp-key');
  const urlEl = row.querySelector('.lp-url');
  const modelEl = row.querySelector('.lp-model');
  const st = row.querySelector('.lp-status');
  const key = keyEl?.value.trim() || '';
  if (!key || key.length < 8) return;
  if (st) { st.textContent = '...'; st.style.color = 'var(--dim)'; }
  try {
    const res = await fetch('/api/llm_detect', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({api_key: key, base_url: urlEl?.value.trim() || ''})
    });
    const data = await res.json();
    if (!data.ok) {
      if (st) { st.textContent = '' + (data.error||'').slice(0,40); st.style.color = 'var(--red)'; }
      return;
    }
    if (data.base_url && urlEl && !urlEl.value.trim()) urlEl.value = data.base_url;
    if (data.models?.length) {
      if (modelEl && !modelEl.value.trim()) modelEl.value = data.models[0];
      if (st) { st.textContent = `${data.models.length} моделей`; st.style.color = 'var(--primary)'; }
      llmShowModelPicker(row, data.base_url, data.models);
    } else {
      if (st) { st.textContent = 'Нет моделей'; st.style.color = 'var(--yellow)'; }
    }
  } catch(e) {
    if (st) { st.textContent = '' + e; st.style.color = 'var(--red)'; }
  }
}

function llmShowModelPicker(row, base_url, models) {
  row.querySelector('.lp-model-picker')?.remove();
  const modelEl = row.querySelector('.lp-model');
  const picker = document.createElement('select');
  picker.className = 'premium-input lp-model-picker';
  picker.style.cssText = 'font-size:11px;margin-top:4px;width:100%';
  picker.innerHTML = '<option value="">— выбрать из найденных —</option>' +
    models.map(m => `<option value="${esc(m)}">${esc(m)}</option>`).join('');
  picker.onchange = () => {
    if (picker.value) { modelEl.value = picker.value; picker.remove(); }
  };
  modelEl.parentElement.appendChild(picker);
}

function llmProfilesRead() {
  const rows = document.querySelectorAll('#llm-profiles-list .llm-profile-row');
  return [...rows].map(row => ({
    name: row.querySelector('.lp-name')?.value.trim() || '',
    api_key: row.querySelector('.lp-key')?.value.trim() || '',
    base_url: row.querySelector('.lp-url')?.value.trim() || '',
    model: row.querySelector('.lp-model')?.value.trim() || '',
    enabled: row.querySelector('.lp-enabled')?.checked ?? true,
  }));
}

async function llmSave(btn) {
  _llmSettingsEditing = false;
  clearTimeout(_llmSettingsEditTimer);
  const st = document.getElementById('llm-status');
  if (btn) btn.disabled = true;
  if (st) st.textContent = 'Сохраняю...';
  try {
    const profiles = llmProfilesRead();
    const mode = document.getElementById('llm-profile-mode')?.value || 'fallback';
    // Save profiles separately
    await fetch('/api/llm_profiles', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({profiles, mode})
    });
    // Save other settings via llm_config
    const res = await fetch('/api/llm_config', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        system_prompt: document.getElementById('llm-system-prompt')?.value || '',
        auto_send: document.getElementById('llm-auto-send')?.checked || false,
        use_cover_letter: document.getElementById('llm-use-cover-letter')?.checked ?? true,
        use_resume: document.getElementById('llm-use-resume')?.checked ?? true,
        api_key: profiles[0]?.api_key || '',
        base_url: profiles[0]?.base_url || '',
        model: profiles[0]?.model || '',
      })
    });
    const data = await res.json();
    if (st) { st.textContent = `Сохранено (${profiles.length} профилей)`; st.style.color = 'var(--primary)'; }
  } catch(e) {
    if (st) { st.textContent = '' + e; st.style.color = 'var(--red)'; }
  } finally {
    if (btn) btn.disabled = false;
    setTimeout(() => { if (st) { st.textContent = ''; st.style.color = ''; } }, 4000);
  }
}

async function llmGlobalToggle(btn) {
  if (btn) btn.disabled = true;
  try {
    const res = await fetch('/api/llm_toggle', {method: 'POST'});
    const data = await res.json();
    _llmUpdateToggleBtn(data.llm_enabled);
  } catch(e) {}
  finally { if (btn) btn.disabled = false; }
}

function _llmUpdateToggleBtn(enabled) {
  const btn = document.getElementById('llm-global-toggle-btn');
  if (!btn) return;
  if (enabled) {
    btn.textContent = 'ВКЛ';
    btn.style.color = 'var(--primary)';
    btn.style.borderColor = 'var(--primary)';
  } else {
    btn.textContent = 'ВЫКЛ';
    btn.style.color = 'var(--dim)';
    btn.style.borderColor = 'var(--dim)';
  }
}

function _llmMarkEditing() {
  _llmSettingsEditing = true;
  clearTimeout(_llmSettingsEditTimer);
  _llmSettingsEditTimer = setTimeout(() => { _llmSettingsEditing = false; }, 5000);
}

function syncLlmSettings(snap) {
  const cfg = snap?.config || {};
  const as = document.getElementById('llm-auto-send');
  const cl = document.getElementById('llm-use-cover-letter');
  const ur = document.getElementById('llm-use-resume');
  const fq = document.getElementById('llm-fill-questionnaire');
  const modeEl = document.getElementById('llm-profile-mode');
  if (!_llmSettingsEditing) {
    if (as && cfg.llm_auto_send !== undefined) as.checked = cfg.llm_auto_send;
    if (cl && cfg.llm_use_cover_letter !== undefined) cl.checked = cfg.llm_use_cover_letter;
    if (ur && cfg.llm_use_resume !== undefined) ur.checked = cfg.llm_use_resume;
    if (fq && cfg.llm_fill_questionnaire !== undefined) fq.checked = cfg.llm_fill_questionnaire;
  }
  if (modeEl && cfg.llm_profile_mode) modeEl.value = cfg.llm_profile_mode;
  // Update the global toggle button
  if (cfg.llm_enabled !== undefined) _llmUpdateToggleBtn(cfg.llm_enabled);
  // Render profiles only if list is empty to avoid wiping user edits
  const list = document.getElementById('llm-profiles-list');
  if (list && list.children.length === 0 && cfg.llm_profiles?.length) {
    cfg.llm_profiles.forEach(p => llmProfileAdd(p));
  }
  // Populate account selector for resume preview
  const sel = document.getElementById('llm-resume-acc-sel');
  if (sel && snap?.accounts?.length && sel.options.length !== snap.accounts.length) {
    sel.innerHTML = snap.accounts.map(a =>
      `<option value="${a.idx}">${esc(a.short || a.name)}</option>`).join('');
  }
}

// ── Schedule filter & auto-tests sync ────────────────────────
let _schedInited = false;
function syncScheduleSettings(snap) {
  const cfg = snap?.config || {};
  // Sync schedule checkboxes
  if (cfg.allowed_schedules !== undefined) {
    document.querySelectorAll('.sched-cb').forEach(cb => {
      cb.checked = cfg.allowed_schedules.includes(cb.value);
    });
  }
  // Bind onchange only once
  if (!_schedInited) {
    _schedInited = true;
    document.querySelectorAll('.sched-cb').forEach(cb => {
      cb.onchange = () => {
        const checked = [...document.querySelectorAll('.sched-cb:checked')].map(c => c.value);
        sendCmd({type: 'set_config', key: 'allowed_schedules', value: checked});
      };
    });
  }
  // Title stop-words (don't overwrite while user is typing)
  const tbl = document.getElementById('title-blacklist');
  if (tbl && cfg.title_blacklist !== undefined && document.activeElement !== tbl)
    tbl.value = (cfg.title_blacklist || []).join(', ');
  const twl = document.getElementById('title-whitelist');
  if (twl && cfg.title_whitelist !== undefined && document.activeElement !== twl)
    twl.value = (cfg.title_whitelist || []).join(', ');
  // Auto-tests
  const at = document.getElementById('auto-apply-tests');
  if (at && cfg.auto_apply_tests !== undefined) at.checked = cfg.auto_apply_tests;
  const oa = document.getElementById('use-oauth-apply');
  if (oa && cfg.use_oauth_apply !== undefined) oa.checked = cfg.use_oauth_apply;
  const dal = document.getElementById('daily-apply-limit');
  if (dal && cfg.daily_apply_limit !== undefined) dal.value = cfg.daily_apply_limit;
  const sohl = document.getElementById('stop-on-hh-limit');
  if (sohl && cfg.stop_on_hh_limit !== undefined) sohl.checked = cfg.stop_on_hh_limit;
  // Skip inconsistent
  const si = document.getElementById('skip-inconsistent');
  if (si && cfg.skip_inconsistent !== undefined) si.checked = cfg.skip_inconsistent;
  // Smart search filters
  const fa = document.getElementById('filter-agencies');
  if (fa && cfg.filter_agencies !== undefined) fa.checked = cfg.filter_agencies;
  const flc = document.getElementById('filter-low-comp');
  if (flc && cfg.filter_low_competition !== undefined) flc.checked = cfg.filter_low_competition;
  const sp = document.getElementById('search-period');
  if (sp && cfg.search_period_days !== undefined) sp.value = cfg.search_period_days;
}

// ── LLM resume preview ───────────────────────────────────────
async function llmPreviewResume(btn) {
  const sel = document.getElementById('llm-resume-acc-sel');
  const pre = document.getElementById('llm-resume-preview');
  const st  = document.getElementById('llm-resume-status');
  const idx = sel?.value;
  if (!idx && idx !== 0) return;
  if (btn) btn.disabled = true;
  if (st) { st.textContent = 'Загружаю…'; st.style.color = 'var(--dim)'; }
  try {
    const res = await fetch(`/api/account/${idx}/resume_text`);
    const data = await res.json();
    if (data.ok && data.text) {
      if (pre) { pre.textContent = data.text; pre.style.display = ''; }
      if (st) { st.textContent = `${data.length} симв.`; st.style.color = 'var(--primary)'; }
    } else {
      if (pre) { pre.style.display = 'none'; }
      const reason = data.error ? `${data.error}` : 'Резюме не удалось извлечь (пустой результат). Проверь куки.';
      if (st) { st.textContent = reason; st.style.color = 'var(--yellow)'; }
    }
  } catch(e) {
    if (st) { st.textContent = '' + e; st.style.color = 'var(--red)'; }
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ── LLM per-account toggle ────────────────────────────────────
function llmToggleAccount(idx, btn) {
  sendCmd({type: 'account_llm', idx});
}

let _llmTotals = null;  // {replied, draft, pending} из /api/interviews, для статус-бара
function updateLlmStatusBar(snap) {
  const stState = document.getElementById('llm-st-state');
  const stInterval = document.getElementById('llm-st-interval');
  const stChats = document.getElementById('llm-st-chats');
  const stReplied = document.getElementById('llm-st-replied');
  if (!stState) return;

  const cfg = snap?.config || {};
  const accs = snap?.accounts || [];
  const globalOn = cfg.llm_enabled;
  const interval = cfg.llm_check_interval || 15;
  const anyAccOn = accs.some(a => a.llm_enabled !== false);
  const paused = snap?.paused || accs.every(a => a.paused);

  // State
  if (!globalOn) {
    stState.textContent = 'LLM выключен';
    stState.style.color = 'var(--dim)';
  } else if (paused) {
    stState.textContent = 'На паузе';
    stState.style.color = 'var(--yellow)';
  } else if (anyAccOn) {
    stState.textContent = 'LLM работает';
    stState.style.color = 'var(--primary)';
  } else {
    stState.textContent = 'Нет аккаунтов с LLM';
    stState.style.color = 'var(--yellow)';
  }

  // Interval
  stInterval.textContent = `каждые ${interval}м`;

  // Chat stats from accounts
  const totalInterviews = accs.reduce((s, a) => s + (a.hh_interviews || 0), 0);
  const totalUnread = accs.reduce((s, a) => s + (a.hh_unread_by_employer || 0), 0);
  stChats.textContent = `${totalInterviews} интервью`;

  // Отправлено/черновики — из персистентной таблицы переписок (_llmTotals),
  // которую считает llmRenderAccStats. Временный llm_log обнуляется при рестарте
  // и показывал 0, хотя ответы реально отправлены — используем его лишь как fallback.
  let sentCount, draftCount;
  if (_llmTotals) {
    sentCount = _llmTotals.replied;
    draftCount = _llmTotals.draft;
  } else {
    const llmLog = snap?.llm_log || [];
    sentCount = llmLog.filter(l => l.sent).length;
    draftCount = llmLog.filter(l => !l.sent).length;
  }
  stReplied.textContent = `${sentCount} отправлено · ${draftCount} черновиков`;
}

async function llmRunNow() {
  try {
    const r = await fetch('/api/llm_run_now', {method: 'POST'});
    const d = await r.json();
    if (d.started) {
      // Visual feedback
      document.querySelectorAll('.btn-sm').forEach(b => {
        if (b.textContent.includes('Ответить')) b.textContent = '...';
      });
      setTimeout(() => {
        document.querySelectorAll('.btn-sm').forEach(b => {
          if (b.textContent.includes('...')) b.textContent = 'Ответить сейчас';
        });
      }, 5000);
    }
  } catch(e) {}
}

function oauthToggleAccount(idx, btn) {
  sendCmd({type: 'account_oauth', idx});
}

// ── LLM tab: interviews from DB ───────────────────────────────
async function llmInterviewsLoad() {
  if (_llmLoading) return;   // уже идёт запрос — не запускаем параллельный
  _llmLoading = true;
  const acc = document.getElementById('llm-log-acc-filter')?.value || '';
  const statusF = document.getElementById('llm-log-sent-filter')?.value || '';
  let url = `/api/interviews?limit=2000${acc ? '&acc=' + encodeURIComponent(acc) : ''}${statusF ? '&status=' + encodeURIComponent(statusF) : ''}`;
  let rows;
  try {
    const res = await fetch(url);
    rows = await res.json();
    _llmLastDbRefresh = Date.now();
  } catch(e) {
    _llmLoading = false;
    return; // Сетевая ошибка — не трогаем текущее содержимое таблицы
  } finally {
    _llmLoading = false;
  }

  const table = document.getElementById('llm-interviews-table');
  const empty = document.getElementById('llm-interviews-empty');
  const countEl = document.getElementById('llm-log-count');
  const tbody = document.getElementById('llm-interviews-body');
  if (!tbody) return;
  if (countEl) countEl.textContent = rows.length ? `${rows.length} записей` : '';

  if (rows.length === 0) {
    const hasRows = tbody.querySelectorAll('tr').length > 0 &&
                    !tbody.querySelector('tr td[colspan]');
    if (statusF || acc) {
      // Фильтр активен — показываем сообщение, таблицу не прячем
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:var(--dim);padding:12px">Нет записей по выбранному фильтру</td></tr>`;
      if (table) table.style.display = '';
      if (empty) empty.style.display = 'none';
    } else if (!hasRows) {
      // Таблица действительно пуста и раньше была пустой — показываем заглушку
      if (table) table.style.display = 'none';
      if (empty) empty.style.display = '';
    }
    // Если hasRows && нет фильтра — оставляем текущее содержимое (избегаем мигания)
    return;
  }
  if (table) table.style.display = '';
  if (empty) empty.style.display = 'none';

  const statusBadge = s => {
    if (s === 'replied')         return '<span class="llm-sent-badge">Отправлено</span>';
    if (s === 'draft')           return '<span class="llm-draft-badge">Черновик</span>';
    if (s === 'pending_reply')   return '<span style="color:var(--yellow);font-size:11px">Ждёт ответа</span>';
    if (s === 'chat_closed')     return '<span style="color:var(--dim);font-size:11px">Закрыт</span>';
    return '<span style="color:var(--dim);font-size:11px">— нет</span>';
  };

  const chatBadge = s => {
    if (s === 'robot')       return '<span style="color:var(--magenta);font-size:10px">Робот</span>';
    if (s === 'locked')      return '<span style="color:var(--dim);font-size:10px">Закрыт</span>';
    if (s === 'waiting_hr')  return '<span style="color:var(--cyan);font-size:10px">Ждём HR</span>';
    if (s === 'replied')     return '<span style="color:var(--primary);font-size:10px">Ответили</span>';
    return '';
  };

  tbody.innerHTML = rows.map(r => {
    const empMsg = esc(r.employer_last_msg || '—').replace(/\n/g, '<br>');
    const botReply = esc(r.llm_reply || '').replace(/\n/g, '<br>');
    const negLink = r.neg_id
      ? `<a href="https://hh.ru/chat/${r.neg_id}" target="_blank" style="font-size:10px;color:var(--cyan)"></a>` : '';
    const dateStr = (r.last_seen || r.first_seen || '').replace('T', ' ').slice(0, 16);
    return `<tr>
      <td style="font-size:11px;color:var(--dim);white-space:nowrap">${dateStr}</td>
      <td style="font-size:11px;color:${colorVar(r.acc_color||'')}">${esc(r.acc||'')}</td>
      <td style="font-size:11px">${esc(r.employer||'')} ${negLink}</td>
      <td style="font-size:11px;color:var(--dim)">${esc(r.vacancy_title||'')}</td>
      <td class="llm-msg-cell">${empMsg}</td>
      <td class="llm-reply-cell">${botReply}</td>
      <td>${statusBadge(r.status)}</td>
      <td>${chatBadge(r.chat_status || '')}</td>
    </tr>`;
  }).join('');

  // Populate account filter from loaded data
  const accSel = document.getElementById('llm-log-acc-filter');
  if (accSel) {
    const known = new Set([...accSel.options].map(o => o.value).filter(Boolean));
    rows.forEach(r => {
      if (r.acc && !known.has(r.acc)) {
        const opt = document.createElement('option');
        opt.value = r.acc; opt.textContent = r.acc;
        accSel.appendChild(opt);
        known.add(r.acc);
      }
    });
  }

  // Per-account stats (always from full unfiltered data — re-fetch all)
  llmRenderAccStats();
}

async function llmRenderAccStats() {
  const statsEl = document.getElementById('llm-acc-stats');
  if (!statsEl) return;
  let all;
  try {
    const res = await fetch('/api/interviews?limit=2000');
    all = await res.json();
  } catch(e) { return; }

  // Group by acc
  const byAcc = {};
  all.forEach(r => {
    const a = r.acc || '?';
    if (!byAcc[a]) byAcc[a] = {acc: a, color: r.acc_color || '', pending: 0, draft: 0, replied: 0, total: 0};
    byAcc[a].total++;
    if (r.status === 'pending_reply') byAcc[a].pending++;
    else if (r.status === 'draft')    byAcc[a].draft++;
    else if (r.status === 'replied')  byAcc[a].replied++;
  });
  // Итоги для статус-бара (персистентный источник, не временный llm_log)
  _llmTotals = Object.values(byAcc).reduce((t, a) => {
    t.replied += a.replied; t.draft += a.draft; t.pending += a.pending; return t;
  }, { replied: 0, draft: 0, pending: 0 });
  if (State.lastSnapshot) updateLlmStatusBar(State.lastSnapshot);  // сразу обновить бар

  statsEl.innerHTML = Object.values(byAcc).map(a => `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:6px;padding:8px 14px;min-width:220px">
      <div style="font-size:12px;font-weight:700;color:${colorVar(a.color)};margin-bottom:6px">${esc(a.acc)} — переписка с HR</div>
      <div style="display:flex;gap:16px;font-size:12px">
        <span title="Сообщений HR ждут ответа">Ждут ответа: <b>${a.pending}</b></span>
        <span style="color:var(--yellow)" title="Черновики в очереди на подтверждение">Черновиков: <b>${a.draft}</b></span>
        <span style="color:var(--primary)" title="Ответов уже отправлено">Отправлено: <b>${a.replied}</b></span>
      </div>
    </div>`).join('');
}

async function llmRunNow(btn) {
  const orig = btn ? btn.textContent : '';
  if (btn) { btn.disabled = true; btn.textContent = '…'; }
  try {
    await fetch('/api/llm_run_now', {method:'POST'});
    if (btn) { btn.textContent = 'Готовлю…'; }
    setTimeout(() => { if (btn) { btn.textContent = orig; btn.disabled = false; } }, 3000);
    setTimeout(() => llmInterviewsLoad(), 8000);
  } catch(e) {
    if (btn) { btn.textContent = orig; btn.disabled = false; }
  }
}

async function llmResetReplied(btn) {
  if (!confirm('Сбросить историю «уже отвечали» для всех аккаунтов?\n\nБот повторно обработает все чаты работодателей в следующем цикле.')) return;
  const orig = btn.textContent;
  btn.disabled = true; btn.textContent = '…';
  try {
    const r = await fetch('/api/llm_reset_replied', {method:'POST'});
    const data = await r.json();
    btn.textContent = 'Сброшено';
    setTimeout(() => { btn.textContent = orig; btn.disabled = false; }, 4000);
  } catch(e) {
    btn.textContent = orig; btn.disabled = false;
  }
}

// ── LLM log tab: debug log from WS snapshot + auto-refresh DB ─
let _llmLastDbRefresh = 0;
let _llmDebugHash = '';
let _llmLoading = false;   // guard: only one fetch at a time
function _llmUpdateAccToggles(snap) {
  const container = document.getElementById('llm-acc-toggles');
  if (!container || !snap?.accounts) return;
  const accs = snap.accounts;
  // Add missing buttons
  accs.forEach(acc => {
    let btn = document.getElementById(`llm-acc-btn-${acc.idx}`);
    if (!btn) {
      btn = document.createElement('button');
      btn.id = `llm-acc-btn-${acc.idx}`;
      btn.style.cssText = 'padding:4px 10px;border-radius:4px;border:1px solid;cursor:pointer;font-size:11px;background:transparent;transition:color .15s,border-color .15s';
      btn.setAttribute('data-idx', acc.idx);
      btn.onclick = function() { llmToggleAccount(acc.idx, this); };
      container.appendChild(btn);
    }
    // Update label and color
    const on = acc.llm_enabled !== false;
    btn.textContent = `${esc(acc.short || acc.name)}`;
    btn.style.color = on ? colorVar(acc.color || 'green') : 'var(--dim)';
    btn.style.borderColor = on ? colorVar(acc.color || 'green') : 'var(--dim)';
    btn.style.opacity = on ? '1' : '0.5';
    btn.title = on ? 'LLM вкл — нажми чтобы выключить' : 'LLM выкл — нажми чтобы включить';
  });
  // Remove stale buttons
  const idxSet = new Set(accs.map(a => String(a.idx)));
  container.querySelectorAll('[id^="llm-acc-btn-"]').forEach(btn => {
    const i = btn.id.replace('llm-acc-btn-', '');
    if (!idxSet.has(i)) btn.remove();
  });
}

function renderLlmLog(snap) {
  if (!snap) return;

  // Update per-account LLM toggles
  _llmUpdateAccToggles(snap);

  // Очередь черновиков на подтверждение
  renderLlmPending(snap);

  // Auto-refresh interviews table from DB every 30s
  const now = Date.now();
  if (now - _llmLastDbRefresh > 30000) {
    _llmLastDbRefresh = now;
    llmInterviewsLoad();
  }

  // Update debug log from activity log — preserve scroll position
  const debugBox = document.getElementById('llm-debug-log');
  const debugCount = document.getElementById('llm-debug-count');
  if (debugBox && snap.log) {
    const debugEntries = snap.log.filter(e => (e.message || '').includes('') || (e.message || '').includes('LLM'));
    // Skip rebuild if content hasn't changed
    const newHash = debugEntries.map(e => e.time + e.message).join('|');
    if (newHash === _llmDebugHash) return;
    _llmDebugHash = newHash;
    if (debugCount) debugCount.textContent = debugEntries.length ? `(${debugEntries.length})` : '';
    // Preserve scroll position
    const wasAtBottom = debugBox.scrollHeight - debugBox.scrollTop <= debugBox.clientHeight + 4;
    const savedTop = debugBox.scrollTop;
    debugBox.innerHTML = debugEntries.length === 0
      ? '<span style="color:var(--dim)">Нет LLM-записей в логе. Первый запуск через ~15 мин после старта HH-статистики.</span>'
      : debugEntries.map(e => {
          const lvlColor = e.level === 'error' ? 'var(--red)' : e.level === 'warning' ? 'var(--yellow)' : e.level === 'success' ? 'var(--primary)' : 'var(--dim)';
          const chatLink = e.neg_id ? `<a href="https://hh.ru/chat/${e.neg_id}" target="_blank" style="color:var(--cyan);text-decoration:none" title="Открыть чат"></a> ` : '';
          return `<div style="line-height:1.5"><span style="color:var(--dim)">${esc(e.time||'')}</span> <span style="color:${colorVar(e.color)}">${esc(e.acc||'')}</span> ${chatLink}<span style="color:${lvlColor}">${esc(e.message||'')}</span></div>`;
        }).join('');
    // Restore scroll: if was at bottom stay at bottom, otherwise restore position
    if (wasAtBottom) debugBox.scrollTop = debugBox.scrollHeight;
    else debugBox.scrollTop = savedTop;
  }
}

// ── Очередь черновиков ответов (подтверждение перед отправкой) ─
let _llmQueueSig = '';

function renderLlmPending(snap) {
  const list = document.getElementById('llm-queue-list');
  const countEl = document.getElementById('llm-queue-count');
  if (!list) return;
  const items = (snap && snap.llm_pending) || [];
  if (countEl) countEl.textContent = `${items.length} в очереди`;
  // Перестраиваем DOM только если набор/тексты изменились — иначе не затираем ввод
  const sig = items.map(d => d.draft_id + '|' + (d.draft || '').length).join('~');
  if (sig === _llmQueueSig) return;
  _llmQueueSig = sig;
  if (!items.length) {
    list.innerHTML = '<div style="color:var(--dim);font-size:12px">Очередь пуста. «Подготовить черновики» — бот прочитает новые сообщения HR и составит ответы для проверки.</div>';
    return;
  }
  list.innerHTML = items.map(d => {
    const id = esc(d.draft_id);
    const chat = d.neg_id ? `<a href="https://hh.ru/chat/${esc(d.neg_id)}" target="_blank" style="color:var(--cyan);text-decoration:none;font-size:11px">открыть чат ↗</a>` : '';
    return `<div class="llm-queue-item" style="border:1px solid var(--border);border-radius:6px;padding:10px;background:var(--bg)">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap">
        <span style="font-weight:600;color:${colorVar(d.color)}">${esc(d.acc || '')}</span>
        <span style="font-weight:600">${esc(d.employer || '')}</span>
        ${d.vacancy_title ? `<span style="color:var(--dim);font-size:12px">· ${esc(d.vacancy_title)}</span>` : ''}
        <span style="margin-left:auto;font-size:11px;color:var(--dim)">${esc(d.ts || '')}</span>
        ${chat}
      </div>
      <div style="font-size:12px;color:var(--dim);margin-bottom:6px"><b>HR:</b> ${esc(d.employer_msg || '')}</div>
      <textarea class="form-input llmq-text" data-id="${id}" rows="3" style="width:100%;font-size:13px;resize:vertical"
        onchange="llmQueueEdit('${id}', this.value)">${esc(d.draft || '')}</textarea>
      <div style="display:flex;gap:6px;margin-top:6px;justify-content:flex-end">
        <button class="btn" onclick="llmQueueSendOne('${id}', this)" style="background:var(--green);color:#000;border-color:var(--green)">Отправить</button>
        <button class="btn" onclick="llmQueueDiscardOne('${id}', this)">Удалить</button>
      </div>
    </div>`;
  }).join('');
}

async function llmQueueEdit(id, text) {
  try {
    await fetch('/api/llm/pending/edit', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, text })
    });
    _llmQueueSig = '';  // позволить перерисовку с обновлённым текстом
  } catch (e) {}
}

async function _llmQueuePost(url, body) {
  const res = await fetch(url, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {})
  });
  return res.json();
}

async function llmQueueRefresh(btn) {
  if (btn) { btn.disabled = true; btn.textContent = 'Генерирую…'; }
  try {
    await fetch('/api/llm_run_now', { method: 'POST' });
    // черновики генерируются в фоне — подождём и подтянем очередь
    await new Promise(r => setTimeout(r, 2500));
    const data = await (await fetch('/api/llm/pending')).json();
    _llmQueueSig = '';
    renderLlmPending({ llm_pending: data.pending || [] });
  } catch (e) {
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Подготовить черновики'; }
  }
}

async function llmQueueSend(btn) {
  const n = document.querySelectorAll('.llm-queue-item').length;
  if (!n) { showToast('Очередь пуста', 'error'); return; }
  const ok = await showConfirm(`Отправить все ${n} ответ(ов) работодателям? Это реальные сообщения в чаты hh.ru.`, 'Отправить все', 'Отмена');
  if (!ok) return;
  if (btn) btn.disabled = true;
  try {
    const r = await _llmQueuePost('/api/llm/pending/send', {});
    _llmQueueSig = '';
    const data = await (await fetch('/api/llm/pending')).json();
    renderLlmPending({ llm_pending: data.pending || [] });
    llmRenderAccStats();  // обновить «отправлено» в статус-баре и карточках
    showToast(`Отправлено: ${r.sent || 0}${r.failed ? ', ошибок: ' + r.failed : ''}`, r.failed ? 'error' : 'success');
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function llmQueueSendOne(id, btn) {
  const ok = await showConfirm('Отправить этот ответ работодателю?', 'Отправить', 'Отмена');
  if (!ok) return;
  if (btn) btn.disabled = true;
  const r = await _llmQueuePost('/api/llm/pending/send', { ids: [id] });
  _llmQueueSig = '';
  const data = await (await fetch('/api/llm/pending')).json();
  renderLlmPending({ llm_pending: data.pending || [] });
  llmRenderAccStats();  // обновить «отправлено» в статус-баре и карточках
  if ((r.failed || 0) > 0) await showConfirm('Не удалось отправить — оставлено в очереди.', 'OK', 'Закрыть');
}

async function llmQueueDiscardOne(id, btn) {
  await _llmQueuePost('/api/llm/pending/discard', { ids: [id] });
  _llmQueueSig = '';
  const data = await (await fetch('/api/llm/pending')).json();
  renderLlmPending({ llm_pending: data.pending || [] });
}

// ── Letter in account cards ───────────────────────────────────
function syncLetterSelects(snap) {
  const templates = snap?.config?.letter_templates || [];
  if (!templates.length) return;
  document.querySelectorAll('[id^="acc-letter-tpl-"]').forEach(sel => {
    const idx = sel.id.replace('acc-letter-tpl-', '');
    const ta = document.getElementById('acc-letter-ta-' + idx);
    const curText = ta?.value || '';
    const matched = templates.findIndex(t => t.text === curText);
    // Rebuild only if count differs or first option is wrong
    const needsRebuild = sel.options.length !== templates.length + 2 ||
      (templates.length > 0 && sel.options[1]?.text !== templates[0].name);
    if (!needsRebuild) return;
    sel.innerHTML = '<option value="">— пусто —</option>' +
      templates.map((t, i) => `<option value="${i}"${matched===i?' selected':''}>${esc(t.name)}</option>`).join('') +
      '<option value="__custom__"' + (curText && matched === -1 ? 'selected' : '') + '>Своё</option>';
  });
}

function letterPickTpl(idx) {
  const sel = document.getElementById('acc-letter-tpl-' + idx);
  const ta  = document.getElementById('acc-letter-ta-'  + idx);
  if (!sel || !ta) return;
  const val = sel.value;
  if (val === '' ) { ta.value = ''; return; }
  if (val === '__custom__') { ta.focus(); return; }
  const templates = State.lastSnapshot?.config?.letter_templates || [];
  const tpl = templates[parseInt(val)];
  if (tpl) ta.value = tpl.text;
}

async function letterSave(idx, btn) {
  const ta = document.getElementById('acc-letter-ta-' + idx);
  const st = document.getElementById('acc-letter-st-' + idx);
  if (btn) btn.disabled = true;
  if (st) { st.textContent = '...'; st.style.color = 'var(--dim)'; }
  try {
    const res = await fetch(`/api/account/${idx}/set_letter`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ letter: ta?.value || '' })
    });
    const data = await res.json();
    if (data.ok) {
      if (st) { st.textContent = 'Сохранено'; st.style.color = 'var(--primary)'; }
      // Update ApplyLetters cache
      ApplyLetters[idx] = ta?.value || '';
    } else {
      if (st) { st.textContent = '' + (data.error || 'Ошибка'); st.style.color = 'var(--red)'; }
    }
  } catch(e) {
    if (st) { st.textContent = '' + e; st.style.color = 'var(--red)'; }
  } finally {
    if (btn) { btn.disabled = false; }
    if (st) setTimeout(() => { if (st.textContent !== '') st.textContent = ''; }, 4000);
  }
}

// ── Search URLs section ───────────────────────────────────────
const HH_AREAS = {
  '1':'Москва','2':'Санкт-Петербург','3':'Екатеринбург','4':'Новосибирск',
  '5':'Казань','16':'Нижний Новгород','54':'Краснодар','88':'Россия','1001':'СНГ'
};
const HH_EXP = {
  'noExperience':'без опыта','between1And3':'1–3 года',
  'between3And6':'3–6 лет','moreThan6':'6+ лет'
};
const HH_SCHEDULE = {
  'fullDay':'полный день','shift':'сменный','flexible':'гибкий',
  'remote':'удалённо','flyInFlyOut':'вахта'
};

function parseUrlFilter(url) {
  try {
    const u = new URL(url.startsWith('http') ? url : 'https://' + url);
    const p = u.searchParams;
    const parts = [];

    const text = p.get('text');
    if (text) parts.push('' + decodeURIComponent(text.replace(/\+/g,'')));

    const resume = p.get('resume');
    if (resume && !text) parts.push('По резюме');

    const area = p.get('area');
    if (area) parts.push('' + (HH_AREAS[area] || 'регион' + area));

    const exp = p.get('experience');
    if (exp) parts.push('' + (HH_EXP[exp] || exp));

    const sal = p.get('salary');
    if (sal) parts.push('от' + Number(sal).toLocaleString('ru') + '₽');

    const sched = p.get('schedule');
    if (sched) parts.push(HH_SCHEDULE[sched] || sched);

    const role = p.get('professional_role');
    if (role) parts.push('роль' + role);

    const order = p.get('order_by');
    if (order === 'publication_time') parts.push('по дате');
    else if (order === 'salary_desc') parts.push('по зарплате↓');

    return parts.length ? parts.join('') : '' + u.pathname;
  } catch(e) { return url; }
}

// ── URL pool (Settings) ───────────────────────────────────────
function buildPoolRow(item, rowIdx) {
  const url = typeof item === 'string' ? item : (item?.url || '');
  const pages = typeof item === 'object' && item !== null ? (item?.pages ?? '') : '';
  const badge = parseUrlFilter(url);
  return `<div class="url-row" id="pool-row-${rowIdx}">
    <div class="url-badge">${badge}</div>
    <div style="display:flex;gap:4px;align-items:center">
      <input class="form-input" style="font-size:10px;padding:2px 6px;flex:1"
        value="${esc(url)}" oninput="urlPoolReparse(${rowIdx},this.value)">
      <input type="number" class="form-input" min="1" max="200"
        style="font-size:10px;padding:2px 4px;width:54px;text-align:center"
        placeholder="стр." title="Глубина поиска (страниц)" value="${esc(String(pages))}">
      <button class="btn-sm" style="padding:2px 7px;color:var(--red);border-color:var(--red)"
        onclick="urlPoolRemoveRow(${rowIdx})">×</button>
    </div>
  </div>`;
}

function urlPoolReparse(rowIdx, val) {
  const badge = document.querySelector(`#pool-row-${rowIdx} .url-badge`);
  if (badge) badge.textContent = parseUrlFilter(val);
}

function urlPoolRemoveRow(rowIdx) {
  const row = document.getElementById(`pool-row-${rowIdx}`);
  if (row) row.remove();
  document.getElementById('url-pool-rows')?.querySelectorAll('.url-row').forEach((r, i) => {
    r.id = `pool-row-${i}`;
    const inp = r.querySelector('.url-input');
    if (inp) inp.oninput = function() { urlPoolReparse(i, this.value); };
    const btn = r.querySelector('button');
    if (btn) btn.onclick = () => urlPoolRemoveRow(i);
  });
}

function urlPoolAddRow() {
  const container = document.getElementById('url-pool-rows');
  if (!container) return;
  const rowIdx = container.querySelectorAll('.url-row').length;
  const div = document.createElement('div');
  div.innerHTML = buildPoolRow('', rowIdx);
  container.appendChild(div.firstElementChild);
}

async function urlPoolSave(btn) {
  const container = document.getElementById('url-pool-rows');
  if (!container) return;
  const globalPages = State.lastSnapshot?.config?.pages_per_url || 40;
  const urls = Array.from(container.querySelectorAll('.url-row')).map(row => {
    const urlInp = row.querySelector('.url-input');
    const pagesInp = row.querySelector('.url-pages-input');
    const url = urlInp?.value?.trim() || '';
    const pages = parseInt(pagesInp?.value) || globalPages;
    return {url, pages};
  }).filter(u => u.url);
  const st = document.getElementById('url-pool-st');
  if (btn) btn.disabled = true;
  if (st) { st.textContent = '...'; st.style.color = 'var(--dim)'; }
  try {
    sendCmd({type: 'set_url_pool', urls});
    if (st) { st.textContent = `Сохранено (${urls.length} URL)`; st.style.color = 'var(--primary)'; }
  } catch(e) {
    if (st) { st.textContent = '' + e; st.style.color = 'var(--red)'; }
  } finally {
    if (btn) btn.disabled = false;
    setTimeout(() => { if (st) st.textContent = ''; }, 4000);
  }
}

function urlPoolBuild(snap) {
  const el = document.getElementById('url-pool-rows');
  if (!el || el.dataset.built === 'true') return;
  el.dataset.built = 'true';
  el.innerHTML = '';
  const pool = snap?.config?.url_pool || [];
  pool.forEach((item, i) => {
    const div = document.createElement('div');
    div.innerHTML = buildPoolRow(item, i);
    el.appendChild(div.firstElementChild);
  });
  if (!pool.length) {
    el.innerHTML = '<div style="font-size:11px;color:var(--dim)">Пул пустой — добавьте первый URL</div>';
  }
}

// ── URL selector on account cards ────────────────────────────
function syncAccUrlChecks(snap) {
  const pool = snap?.config?.url_pool || [];
  (snap?.accounts || []).forEach(acc => {
    const container = document.getElementById(`acc-url-checks-${acc.idx}`);
    const wrap = document.getElementById(`acc-url-wrap-${acc.idx}`);
    if (!container || (wrap && wrap.open)) return; // don't overwrite while user is choosing
    const selected = new Set(acc.urls || []);
    if (!pool.length) {
      container.innerHTML = '<div style="font-size:11px;color:var(--dim)">Пул пустой — добавьте URL в Настройках</div>';
      return;
    }
    const globalPages = State.lastSnapshot?.config?.pages_per_url || 40;
    container.innerHTML = pool.map((item, i) => {
      const url = typeof item === 'string' ? item : (item?.url || '');
      const poolPages = typeof item === 'object' && item?.pages ? item.pages : globalPages;
      // Per-account override (0 = use pool/global)
      const accPages = acc.url_pages?.[url] || '';
      const checked = selected.has(url) ? 'checked' : '';
      const badge = parseUrlFilter(url);
      const urlCount = acc.url_stats?.[url];
      const countInfo = urlCount != null ? `<span style="color:var(--primary);font-size:10px;margin-left:4px">→${urlCount}</span>` : '';
      return `<div style="display:flex;align-items:center;gap:6px;margin-bottom:5px">
        <label style="display:flex;align-items:flex-start;gap:5px;cursor:pointer;font-size:11px;flex:1;min-width:0">
          <input type="checkbox" value="${esc(url)}" ${checked} style="margin-top:2px;flex-shrink:0">
          <span style="color:var(--dim);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${badge}${countInfo}</span>
        </label>
        <input type="number" class="form-input" data-url="${esc(url)}"
          min="1" max="200" placeholder="${poolPages}"
          value="${esc(String(accPages))}"
          title="Глубина для этого URL (пусто = ${poolPages} стр. из пула)"
          style="width:52px;font-size:10px;padding:2px 4px;text-align:center;flex-shrink:0">
      </div>`;
    }).join('');
  });
}

async function urlAccSave(accIdx, btn) {
  const container = document.getElementById(`acc-url-checks-${accIdx}`);
  if (!container) return;
  const urls = Array.from(container.querySelectorAll('input[type=checkbox]:checked'))
    .map(cb => cb.value).filter(Boolean);
  // Collect per-URL pages overrides
  const url_pages = {};
  container.querySelectorAll('.acc-url-pages-inp').forEach(inp => {
    const v = parseInt(inp.value);
    if (v > 0) url_pages[inp.dataset.url] = v;
  });
  const st = document.getElementById(`url-acc-st-${accIdx}`);
  if (btn) btn.disabled = true;
  if (st) { st.textContent = '...'; st.style.color = 'var(--dim)'; }
  try {
    const res = await fetch(`/api/account/${accIdx}/set_urls`, {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({urls, url_pages})
    });
    const data = await res.json();
    if (data.ok) {
      if (st) { st.textContent = `${data.count} URL`; st.style.color = 'var(--primary)'; }
    } else {
      if (st) { st.textContent = '' + (data.error||'Ошибка'); st.style.color = 'var(--red)'; }
    }
  } catch(e) {
    if (st) { st.textContent = '' + e; st.style.color = 'var(--red)'; }
  } finally {
    if (btn) btn.disabled = false;
    setTimeout(() => { if (st) st.textContent = ''; }, 4000);
  }
}

// ── Main accounts management ──────────────────────────────────
const ACC_COLORS = ['cyan','magenta','green','yellow','blue','red'];

async function accDeleteCard(idx, btn) {
  if (!await showConfirm(`Удалить аккаунт <b>#${idx}</b>? Действие необратимо.`)) return;
  if (btn) btn.disabled = true;
  try {
    const res = await fetch(`/api/account/${idx}/delete`, {method: 'DELETE'});
    const data = await res.json();
    if (data.ok) {
      const card = document.getElementById('card-' + idx);
      if (card) card.remove();
    } else {
      alert('Ошибка: ' + (data.error || ''));
      if (btn) btn.disabled = false;
    }
  } catch(e) {
    alert('Ошибка: ' + e);
    if (btn) btn.disabled = false;
  }
}

// ── Browser sessions management in Settings ──────────────────
function buildSessList(snap) {
  const el = document.getElementById('sess-list');
  if (!el) return;
  const sessions = (snap?.accounts || []).filter(a => a.temp);
  if (!sessions.length) {
    el.innerHTML = '<div style="font-size:11px;color:var(--dim);margin-bottom:8px">Нет сессий — добавьте первую ниже.</div>';
    return;
  }
  // Rebuild only if count changed
  if (el.dataset.count === String(sessions.length)) return;
  el.dataset.count = String(sessions.length);
  el.innerHTML = '';
  sessions.forEach(acc => {
    const div = document.createElement('div');
    div.id = `sess-row-${acc.idx}`;
    div.style.cssText = 'margin-bottom:8px;padding:10px 12px;background:var(--bg);border:1px solid var(--border);border-radius:6px';
    div.innerHTML =
      `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">` +
        `<div>` +
          `<span style="font-size:12px;font-weight:600;color:var(--yellow)">${esc(acc.name)}</span>` +
          `<span style="font-size:11px;color:var(--dim);margin-left:8px">${acc.bot_active ? t('sess_active') : t('sess_inactive')}</span>` +
        `</div>` +
        `<div style="display:flex;gap:6px">` +
          `<button class="btn-sm" style="color:var(--primary);border-color:var(--primary)" onclick="showCampaignConfigurator(${acc.idx})">Настроить кампанию</button>` +
          `<button class="btn-sm" onclick="sessEditToggle(${acc.idx})">Изменить</button>` +
          `<button class="btn-sm" style="color:var(--red);border-color:var(--red)" onclick="sessionRemove(${acc.idx})">×</button>` +
        `</div>` +
      `</div>` +
      `<div style="font-size:11px;color:var(--dim)">` +
        `resume_hash: <b style="font-family:monospace;color:var(--text)">${esc((acc.resume_hash||'').slice(0,14))}...</b>` +
      `</div>` +
      `<div id="sess-edit-form-${acc.idx}" style="display:none;margin-top:10px">` +
        `<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px">` +
          `<div><div style="font-size:11px;color:var(--dim);margin-bottom:3px">Имя</div>` +
            `<input id="sess-edit-name-${acc.idx}" class="form-input" style="font-size:11px" value="${esc(acc.name)}"></div>` +
          `<div><div style="font-size:11px;color:var(--dim);margin-bottom:3px">Короткое</div>` +
            `<input id="sess-edit-short-${acc.idx}" class="form-input" style="font-size:11px" value="${esc(acc.short||'')}"></div>` +
          `<div><div style="font-size:11px;color:var(--dim);margin-bottom:3px">Цвет</div>` +
            `<select id="sess-edit-color-${acc.idx}" class="form-input" style="font-size:11px">` +
              ACC_COLORS.map(c => `<option value="${c}"${c===(acc.color||'yellow')?' selected':''}>${c}</option>`).join('') +
            `</select></div>` +
          `<div><div style="font-size:11px;color:var(--dim);margin-bottom:3px">resume_hash</div>` +
            `<input id="sess-edit-hash-${acc.idx}" class="form-input" style="font-size:11px;font-family:monospace" value="${esc(acc.resume_hash||'')}"></div>` +
        `</div>` +
        `<div style="display:flex;gap:8px;align-items:center">` +
          `<button class="btn-sm" onclick="sessProfileSave(${acc.idx},this)">Сохранить</button>` +
          `<span id="sess-edit-st-${acc.idx}" style="font-size:11px;color:var(--dim)"></span>` +
        `</div>` +
      `</div>`;
    el.appendChild(div);
  });
}

async function sessActivate(idx, btn) {
  if (btn) btn.disabled = true;
  try {
    const res = await fetch(`/api/session/${idx}/activate`, {method: 'POST'});
    const data = await res.json();
    if (data.ok) {
      const listEl = document.getElementById('sess-list');
      if (listEl) listEl.dataset.count = '';
    } else {
      alert('Ошибка: ' + (data.error || ''));
      if (btn) btn.disabled = false;
    }
  } catch(e) {
    alert('Ошибка: ' + e);
    if (btn) btn.disabled = false;
  }
}

const _touchPending = {};  // idx → ts, до которого снапшот НЕ трогает тумблер (анти-гонка)
async function touchToggle(idx, el) {
  if (!el) return;
  const wasOn = el.classList.contains('on');
  // оптимистично переключаем сразу + блокируем обновление из снапшота на 2с,
  // чтобы устаревший «в полёте» снапшот не вернул тумблер обратно.
  _touchPending[idx] = Date.now() + 2000;
  const setUI = (on) => {
    el.classList.toggle('on', on);
    el.classList.toggle('off', !on);
    const lbl = document.getElementById('acc-touch-label-' + idx);
    if (lbl) lbl.textContent = on ? 'вкл' : 'выкл';
  };
  setUI(!wasOn);
  try {
    const res = await fetch(`/api/account/${idx}/resume_touch_toggle`, {method: 'POST'});
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();
    // авторитетное состояние от сервера + продлеваем окно, чтобы снапшот догнал
    if (typeof data.enabled === 'boolean') setUI(data.enabled);
    _touchPending[idx] = Date.now() + 1500;
  } catch(e) {
    setUI(wasOn);  // откат
    _touchPending[idx] = 0;
  }
}

async function resumeTouchNow(idx, btn) {
  if (btn) { btn.disabled = true; btn.textContent = 'поднимаю...'; btn.style.color = ''; }
  try {
    await fetch(`/api/account/${idx}/resume_touch`, {method: 'POST'});
    // держим disabled — updateCard разблокирует кнопку когда придёт реальный таймер
    if (btn) btn.setAttribute('data-touching', '1');
    // страховка: разблокировать через 15с если WebSocket не пришёл
    setTimeout(() => {
      if (btn && btn.getAttribute('data-touching')) {
        btn.removeAttribute('data-touching');
        btn.disabled = false;
        btn.textContent = 'Поднять';
        btn.style.color = '';
      }
    }, 15000);
  } catch(e) {
    if (btn) { btn.textContent = ''; btn.style.color = 'var(--red)'; btn.disabled = false; btn.removeAttribute('data-touching'); }
  }
}

function sessEditToggle(idx) {
  const form = document.getElementById(`sess-edit-form-${idx}`);
  if (form) form.style.display = form.style.display === 'none' ? 'block' : 'none';
}

async function sessProfileSave(idx, btn) {
  const st = document.getElementById(`sess-edit-st-${idx}`);
  const body = {
    name:        document.getElementById(`sess-edit-name-${idx}`)?.value.trim(),
    short:       document.getElementById(`sess-edit-short-${idx}`)?.value.trim(),
    color:       document.getElementById(`sess-edit-color-${idx}`)?.value,
    resume_hash: document.getElementById(`sess-edit-hash-${idx}`)?.value.trim(),
  };
  if (btn) btn.disabled = true;
  if (st) { st.textContent = '...'; st.style.color = 'var(--dim)'; }
  try {
    const res = await fetch(`/api/session/${idx}/profile`, {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body)
    });
    const data = await res.json();
    if (data.ok) {
      if (st) { st.textContent = 'Сохранено'; st.style.color = 'var(--primary)'; }
      const listEl = document.getElementById('sess-list');
      if (listEl) listEl.dataset.count = '';
    } else {
      if (st) { st.textContent = '' + (data.error||'Ошибка'); st.style.color = 'var(--red)'; }
    }
  } catch(e) {
    if (st) { st.textContent = '' + e; st.style.color = 'var(--red)'; }
  } finally {
    if (btn) btn.disabled = false;
    setTimeout(() => { if (st) st.textContent = ''; }, 4000);
  }
}

// Build/refresh account cookies list from snapshot
function buildAccCookiesList(snap) {
  const el = document.getElementById('acc-cookies-list');
  if (!el) return;
  const accs = (snap?.accounts || []);
  if (!accs.length) { el.innerHTML = '<div class="c-dim" style="font-size:12px">Нет аккаунтов</div>'; return; }
  // Only rebuild if account count changed
  if (el.dataset.count === String(accs.length)) return;
  el.dataset.count = String(accs.length);
  el.innerHTML = '';
  accs.forEach(acc => {
    const colorStyle = `color:${colorVar(acc.color || 'text')}`;
    const div = document.createElement('div');
    div.style.cssText = 'margin-bottom:14px;padding:10px 12px;background:var(--bg);border:1px solid var(--border);border-radius:6px';
    div.innerHTML =
      `<div style="font-size:12px;font-weight:600;margin-bottom:6px;${colorStyle}">${esc(acc.name)}</div>` +
      `<textarea id="ck-ta-${acc.idx}" class="form-input" rows="2" style="font-size:11px;margin-bottom:6px" ` +
        `placeholder="curl 'https://hh.ru/...' -H 'cookie: hhtoken=...' ...&#10;— или: hhtoken=xxx; _xsrf=yyy; hhul=zzz; crypted_id=aaa"></textarea>` +
      `<div style="display:flex;gap:8px;align-items:center">` +
        `<button class="btn-sm" onclick="updateAccCookies(${acc.idx})">${t('btn_update_cookies')}</button>` +
        `<span id="ck-st-${acc.idx}" style="font-size:11px;color:var(--dim)"></span>` +
      `</div>`;
    el.appendChild(div);
  });
}

async function updateAccCookies(idx) {
  const ta = document.getElementById('ck-ta-' + idx);
  const st = document.getElementById('ck-st-' + idx);
  const val = ta?.value.trim();
  if (!val) { if (st) { st.textContent = 'Пусто'; st.style.color = 'var(--red)'; } return; }
  if (st) { st.textContent = 'Обновляю...'; st.style.color = 'var(--dim)'; }
  try {
    const res = await fetch(`/api/account/${idx}/update_cookies`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({cookies: val})
    });
    const data = await res.json();
    if (data.ok) {
      if (ta) ta.value = '';
      if (st) { st.textContent = `Обновлено (${(data.keys||[]).length} ключей)`; st.style.color = 'var(--primary)'; }
    } else {
      if (st) { st.textContent = '' + (data.error || 'Ошибка'); st.style.color = 'var(--red)'; }
    }
  } catch(e) {
    if (st) { st.textContent = '' + e; st.style.color = 'var(--red)'; }
  }
}

function applySettings() {
  SETTINGS_DEF.forEach(s => {
    const el = document.getElementById('sr-' + s.key);
    if (el) sendCmd({ type: 'set_config', key: s.key, value: Number(el.value) });
  });
  const st = document.getElementById('settings-status');
  st.textContent = t('settings_applied');
  setTimeout(() => { st.textContent = ''; }, 3000);
}

// ── WebSocket ──────────────────────────────────────────────────
function connect() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  State.ws = ws;

  ws.onopen = () => {
    document.getElementById('conn-dot').classList.add('connected');
    State.reconnectDelay = 1000;
  };

  ws.onmessage = (ev) => {
    try {
      const snap = JSON.parse(ev.data);
      if (snap.type === 'state_update') {
        State.lastSnapshot = snap;
  updateAuthHeader(snap);
        try {
          renderAll(snap);
          const dbg = document.getElementById('dbg-err');
          if (dbg) dbg.style.display = 'none';
        } catch (renderErr) {
          const dbg = document.getElementById('dbg-err');
          if (dbg) { dbg.style.display = ''; dbg.textContent = 'JS ERROR: ' + renderErr; }
          console.error('renderAll error:', renderErr);
        }
      }
    } catch (e) { console.error('WS parse error:', e); }
  };

  ws.onclose = () => {
    document.getElementById('conn-dot').classList.remove('connected');
    State.reconnectTimer = setTimeout(() => {
      State.reconnectDelay = Math.min(State.reconnectDelay * 2, 30000);
      connect();
    }, State.reconnectDelay);
  };

  ws.onerror = (e) => { console.error('WS error:', e); ws.close(); };
}

function sendCmd(obj) {
  if (State.ws && State.ws.readyState === 1) {
    State.ws.send(JSON.stringify(obj));
  }
}

function authCompleteLocal() {
  try {
    return localStorage.getItem('hh-auth-complete') === '1';
  } catch(e) {
    return false;
  }
}

function markAuthComplete() {
  try {
    localStorage.setItem('hh-auth-complete', '1');
    localStorage.setItem('hh-tab', 'apply');
  } catch(e) {}
  document.body.classList.remove('auth-required');
  document.body.classList.add('dashboard-authenticated');
  const authTab = document.querySelector('.tab[data-tab="auth"]');
  if (authTab) authTab.hidden = true;
  if (State.currentTab === 'auth') switchTab('apply');
}

function hasDashboardAccess(snap) {
  const accounts = Array.isArray(snap?.accounts) ? snap.accounts : [];
  const sessionGroups = [snap?.sessions, snap?.browser_sessions, snap?.temp_sessions];
  const hasSessions = sessionGroups.some(group => Array.isArray(group) && group.length > 0);
  const statsCount = Number(snap?.stats?.accounts || snap?.accounts_count || 0);
  return accounts.length > 0 || hasSessions || statsCount > 0 || authCompleteLocal();
}

function applyAuthState(snap) {
  const authorized = hasDashboardAccess(snap);
  document.body.classList.toggle('auth-required', !authorized);
  document.body.classList.toggle('dashboard-authenticated', authorized);

  const authTab = document.querySelector('.tab[data-tab="auth"]');
  if (authTab) authTab.hidden = authorized;

  if (!authorized) {
    if (State.currentTab !== 'auth') switchTab('auth');
    return;
  }

  if (State.currentTab === 'auth') {
    try { localStorage.setItem('hh-tab', 'apply'); } catch(e) {}
    switchTab('apply');
  }
}

// ── Rendering ──────────────────────────────────────────────────
function renderAll(snap) {
  applyAuthState(snap);
  renderHeader(snap);
  updateHeaderResumeStats(snap);
  syncLetterSelects(snap);
  syncAccUrlChecks(snap);
  syncLlmSettings(snap);
  syncScheduleSettings(snap);
  syncAuditSelector(snap);
  updateLlmStatusBar(snap);
  updatePageTitle(snap);
  checkNotifications(snap);
  if (State.currentTab === 'log') renderLog(snap);
  else if (State.currentTab === 'hh') renderHH(snap);
  else if (State.currentTab === 'llm') renderLlmLog(snap);
  else if (State.currentTab === 'views') loadViews();
  else if (State.currentTab === 'apply') {
    renderCampaignAccountUI(snap);   // чип аккаунта + бар действий
    // само-восстановление: кэш пуст (мог обнулиться на ошибке) — перечитать
    if (!_campaignsCache.length && !_campaignsReloading) { _campaignsReloading = true; loadCampaigns().finally(() => { _campaignsReloading = false; }); }
    _liveMergeActiveCampaign(snap);  // live-счётчики активной кампании в список
  }
  // applied/tests/views rendered on tab switch
}

// Обновить строку активной кампании живыми счётчиками из снапшота (без ре-фетча)
function _liveMergeActiveCampaign(snap) {
  const acc = (snap.accounts || []).find(a => a.armed && a.active_campaign_id);
  if (!acc) return;
  const c = _campaignsCache.find(x => x.id === acc.active_campaign_id);
  if (!c) return;
  c.status = 'running';
  // sent — кумулятивный из applied (приходит через loadCampaigns); тут только live skipped/errors
  c.stats = { ...(c.stats || {}), skipped: acc.campaign_skipped, errors: acc.campaign_errors };
  if (!_editingCampaignId) { renderCampaignsSummaryFromCache(); renderCampaignsList(); }
}
function renderCampaignsSummaryFromCache() {
  renderCampaignsSummary({
    total: _campaignsCache.length,
    active: _campaignsCache.filter(c => c.status === 'running').length,
    total_responses: _campaignsCache.reduce((s, c) => s + ((c.stats || {}).sent || 0), 0),
  });
}

function updatePageTitle(snap) {
  const hasLimit = (snap.accounts || []).some(a => a.status === 'limit');
  const sent = snap.global_stats?.total_sent || 0;
  if (hasLimit) {
    document.title = t('title_limit');
  } else if (snap.paused) {
    document.title = t('title_paused');
  } else if (sent > 0) {
    document.title = `${sent} откл. | HH Bot`;
  } else {
    document.title = 'HH Bot Dashboard';
  }
}

function checkNotifications(snap) {
  if (!('Notification' in window) || Notification.permission !== 'granted') return;
  (snap.accounts || []).forEach(acc => {
    const prev = State.prevInterviews[acc.idx] ?? acc.hh_interviews;
    if (acc.hh_interviews > prev) {
      sendBotNotification(
        `${t('notif_new_inv')}${acc.short}`,
        `${t('notif_inv_count_pre')} ${acc.hh_interviews} ${t('notif_inv_count_mid')}${acc.hh_interviews - prev})`
      );
    }
    State.prevInterviews[acc.idx] = acc.hh_interviews;
    const wasLimit = State.prevLimitState[acc.idx];
    if (acc.status === 'limit' && !wasLimit) {
      sendBotNotification(`${t('notif_limit')}${acc.short}`, t('notif_limit_body'));
    }
    State.prevLimitState[acc.idx] = acc.status === 'limit';
    // Cookies expired detection
    const wasExpired = State.prevCookiesExpired[acc.idx];
    if (acc.cookies_expired && !wasExpired) {
      sendBotNotification(`${t('notif_cookies')}${acc.short}`, t('notif_cookies_body'));
    }
    State.prevCookiesExpired[acc.idx] = acc.cookies_expired;
  });
}

function sendBotNotification(title, body) {
  try { new Notification(title, { body, icon: '/favicon.ico' }); } catch(e) {}
}

function fmtUptime(s) {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}ч ${String(m).padStart(2,'0')}м`;
  return `${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;
}

function renderHeader(snap) {
  document.getElementById('uptime').textContent = '' + fmtUptime(snap.uptime_seconds);
  document.getElementById('global-found').textContent = snap.global_stats.total_found;
  document.getElementById('global-sent').textContent = snap.global_stats.total_sent;
  document.getElementById('storage-total').textContent = snap.global_stats.storage_total;
  document.getElementById('storage-tests').textContent = snap.global_stats.storage_tests;

  // Daily counter
  const dailyEl = document.getElementById('hdr-daily-counter');
  if (dailyEl) {
    const accs = snap.accounts || [];
    const totalDaily = accs.reduce((s, a) => s + (a.daily_sent || 0), 0);
    const limit = snap.config?.daily_apply_limit || 0;
    const stopped = accs.some(a => a.hard_stopped);
    if (limit > 0) {
      dailyEl.textContent = `(${totalDaily}/${limit} сегодня)`;
      dailyEl.style.color = totalDaily >= limit ? 'var(--red)' : 'var(--yellow)';
    } else if (totalDaily > 0) {
      dailyEl.textContent = `(${totalDaily} сегодня)`;
      dailyEl.style.color = stopped ? 'var(--red)' : 'var(--yellow)';
    } else {
      dailyEl.textContent = '';
    }
  }

  // Smart search filter badges
  const filterEl = document.getElementById('hdr-filters');
  if (filterEl && snap.config) {
    const badges = [];
    if (snap.config.filter_agencies) badges.push('Без агентств');
    if (snap.config.filter_low_competition) badges.push('<10 откликов');
    if (snap.config.search_period_days > 0) badges.push(`${snap.config.search_period_days}д`);
    if (snap.config.skip_inconsistent) badges.push('Пре-чек');
    filterEl.innerHTML = badges.map(b => `<span style="background:rgba(57,208,216,0.12);color:var(--cyan);padding:1px 6px;border-radius:3px;font-size:9px">${b}</span>`).join(' ');
  }

  const btn = document.getElementById('pause-btn');
  if (btn) {
    if (snap.paused) {
      btn.textContent = t('btn_resume');
      btn.classList.add('paused');
    } else {
      const pausedAccs = (snap.accounts || []).filter(a => a.paused).length;
      btn.textContent = pausedAccs ? `${t('btn_pause')} (${pausedAccs})` : t('btn_pause');
      btn.classList.remove('paused');
    }
  }

  // Apply mode badge — show per-account summary
  const modeBadge = document.getElementById('apply-mode-badge');
  if (modeBadge) {
    const accs = snap.accounts || [];
    const oauthCount = accs.filter(a => a.use_oauth).length;
    const globalOAuth = snap.config?.use_oauth_apply;
    if (oauthCount > 0 || globalOAuth) {
      const label = globalOAuth ? 'OAuth · все' : `OAuth · ${oauthCount}/${accs.length}`;
      modeBadge.textContent = label;
      modeBadge.style.background = 'rgba(63,185,80,0.15)';
      modeBadge.style.color = 'var(--primary)';
    } else {
      modeBadge.textContent = 'Web';
      modeBadge.style.background = 'rgba(57,208,216,0.15)';
      modeBadge.style.color = 'var(--cyan)';
    }
  }

  // ── Login button visibility ──
  const loginBtn = document.getElementById('hh-login-btn');
  if (loginBtn) {
    const accs = snap.accounts || [];
    if (accs.length > 0 || hasDashboardAccess(snap)) {
      loginBtn.textContent = 'Подключено · +HH';
      loginBtn.style.borderColor = 'var(--primary)';
      loginBtn.style.color = 'var(--primary)';
      loginBtn.style.cursor = 'pointer';
      loginBtn.onclick = showLoginModal;
      loginBtn.title = 'Добавить или переподключить HH-аккаунт';
      loginBtn.style.opacity = '1';
    } else {
      loginBtn.textContent = 'Войти в HH';
      loginBtn.style.borderColor = 'var(--primary)';
      loginBtn.style.color = 'var(--primary)';
      loginBtn.style.cursor = 'pointer';
      loginBtn.onclick = showLoginModal;
      loginBtn.title = 'Войти в HH.ru';
      loginBtn.style.opacity = '1';
    }
  }
}

// ── Main tab ──
function renderMain(snap) {
  renderAccounts(snap);
  renderGlobalStats(snap);
  renderRecentResponses(snap);
}

const STATUS_MAP = {
  idle:       ['', 'status_idle',       'status-idle'],
  collecting: ['', 'status_collecting', 'status-collecting'],
  applying:   ['', 'status_applying',   'status-applying'],
  limit:      ['', 'status_limit',      'status-limit'],
  waiting:    ['', 'status_waiting',    'status-waiting'],
  checking:   ['', 'status_checking',   'status-checking'],
  '—':        ['', 'status_inactive',   'status-idle'],
};

function renderAccounts(snap) {
  const wizard = document.getElementById('onboarding-wizard');
  const mainPanel = document.getElementById('panel-apply');  // карточки теперь здесь
  const grid = document.getElementById('accounts-grid');
  
  if (!snap.accounts || snap.accounts.length === 0) {
    if (hasDashboardAccess(snap)) {
      if (wizard) wizard.style.display = 'none';
      if (mainPanel && State.currentTab === 'apply') mainPanel.style.display = 'block';
      if (grid) {
        grid.innerHTML = `
          <div id="accounts-empty" class="empty-dashboard-card">
            <div>
              <div class="empty-dashboard-title">Сессия HH подключена</div>
              <div class="empty-dashboard-text">Dashboard готов. Добавь поисковые запросы или настрой кампанию, когда websocket подтянет аккаунт.</div>
            </div>
            <div class="empty-dashboard-actions">
              <button class="btn primary" onclick="switchTab('settings')">Настройки</button>
              <button class="btn" onclick="switchTab('apply')">Кампании</button>
            </div>
          </div>`;
      }
      return;
    }
    if (wizard) {
      wizard.style.display = 'block';
      if (mainPanel) mainPanel.style.display = 'none';
    } else {
      if (State.currentTab !== 'auth') {
        switchTab('auth');
      }
    }
    return;
  } else {
    if (wizard) wizard.style.display = 'none';
    
    // Check if there is an inactive temp session, if so, show campaign configurator
    const draftAcc = snap.accounts.find(a => a.temp && !a.bot_active);

    
    // Only show mainPanel if we are on the main tab
    if (mainPanel && State.currentTab === 'apply' && document.getElementById('campaign-configurator').style.display === 'none') {
      mainPanel.style.display = 'block';
    }
  }

  // Убираем старый пустой блок, если он был
  const oldEmptyEl = document.getElementById('accounts-empty');
  if (oldEmptyEl) oldEmptyEl.remove();
  // Убираем карточки которых больше нет
  const alive = new Set(snap.accounts.map(a => 'card-' + a.idx));
  grid.querySelectorAll('.acc-card').forEach(el => {
    if (el.id && !alive.has(el.id)) el.remove();
  });
  snap.accounts.forEach(acc => {
    let card = document.getElementById('card-' + acc.idx);
    if (!card) {
      card = document.createElement('div');
      card.id = 'card-' + acc.idx;
      card.className = 'acc-card color-' + (acc.color || 'yellow');
      card.innerHTML = buildCardHTML(acc);
      grid.appendChild(card);
    } else {
      card.className = 'acc-card color-' + (acc.color || 'yellow');
      updateCard(card, acc);
    }
  });
}

function buildCardHTML(acc) {
  return `
    <div class="acc-card-header">
      <div class="acc-card-title" id="acc-name-${acc.idx}">${acc.name}</div>
      <div class="acc-card-tools">
        <button class="compact-btn" title="Свернуть/развернуть карточку" onclick="toggleCompact(${acc.idx})">–</button>
        <button class="compact-btn danger" title="Удалить аккаунт" onclick="${acc.temp ? `sessionRemove(${acc.idx})` : `accDeleteCard(${acc.idx}, this)`}">×</button>
        <div class="acc-status-badge status-idle" id="acc-badge-${acc.idx}">${t('status_idle')}</div>
        <button class="acc-oauth-btn" id="acc-oauth-btn-${acc.idx}"
          style="color:${acc.use_oauth ? 'var(--primary)' : 'var(--cyan)'};border-color:${acc.use_oauth ? 'var(--primary)' : 'var(--cyan)'}"
          onclick="oauthToggleAccount(${acc.idx},this)" title="Метод откликов: OAuth API или Web cookies">${acc.use_oauth ? 'API' : 'Web'}</button>
      </div>
    </div>
    <div class="acc-progress"><div class="acc-progress-fill" id="acc-prog-${acc.idx}"></div></div>
    <div class="acc-stats">
      <div class="stat-box" title="Сессия / Всего за всё время">
        <div class="stat-val c-green" id="acc-sent-${acc.idx}">0</div>
        <div class="stat-lbl">${t('stat_replies')} <span style="color:var(--dim);font-size:10px">/ <span id="acc-total-${acc.idx}">0</span></span></div>
      </div>
      <div class="stat-box">
        <div class="stat-val c-magenta" id="acc-tests-${acc.idx}">0</div>
        <div class="stat-lbl">${t('stat_tests')}</div>
      </div>
      <div class="stat-box" id="acc-qsent-box-${acc.idx}" style="display:none">
        <div class="stat-val c-cyan" id="acc-qsent-${acc.idx}">0</div>
        <div class="stat-lbl">${t('stat_surveys')}</div>
      </div>
      <div class="stat-box">
        <div class="stat-val c-blue" id="acc-already-${acc.idx}">0</div>
        <div class="stat-lbl">${t('stat_already')}</div>
      </div>
      <div class="stat-box">
        <div class="stat-val c-red" id="acc-err-${acc.idx}">0</div>
        <div class="stat-lbl">${t('stat_errors')}</div>
      </div>
      <div class="stat-box" id="acc-sal-box-${acc.idx}" style="display:none">
        <div class="stat-val c-yellow" id="acc-sal-${acc.idx}">0</div>
        <div class="stat-lbl">${t('stat_salary')}</div>
      </div>
      <div class="stat-box" id="acc-intrv-box-${acc.idx}" style="display:none">
        <div class="stat-val" style="color:#f0c060" id="acc-intrv-${acc.idx}">0</div>
        <div id="acc-intrv-total-${acc.idx}" style="font-size:10px;color:var(--dim);line-height:1.2"></div>
        <div class="stat-lbl">${t('stat_interviews')}</div>
      </div>
    </div>
    <div class="acc-vacancy" id="acc-vacancy-${acc.idx}">
      <div class="acc-vacancy-title c-dim">${t('card_waiting')}</div>
    </div>
    <div class="acc-meta" id="acc-meta-${acc.idx}"></div>
    <div class="acc-hh-stats" id="acc-hh-${acc.idx}">${t('card_hh_loading')}</div>
    <div id="acc-llm-status-${acc.idx}" style="font-size:11px;padding:2px 0;color:var(--cyan);display:none"></div>
    <div class="acc-resume-stats" id="acc-rs-${acc.idx}" style="display:none">
      <span class="acc-resume-stat"><span id="acc-rs-views-${acc.idx}">0</span> ${t('rs_views')}</span>
      <span class="acc-resume-stat c-cyan">+<span id="acc-rs-vnew-${acc.idx}">0</span> новых</span>
      <span class="acc-resume-stat"><span id="acc-rs-shows-${acc.idx}">0</span> ${t('rs_shows')}</span>
      <span class="acc-resume-stat c-green"><span id="acc-rs-inv-${acc.idx}">0</span> ${t('rs_inv')}</span>
      <span class="acc-touch-timer c-yellow" id="acc-touch-timer-${acc.idx}" style="display:none"></span>
    </div>
    <div class="acc-history" id="acc-hist-${acc.idx}"></div>
    <div class="acc-event-log" id="acc-elog-${acc.idx}"></div>
    <div id="acc-errbadge-${acc.idx}" style="display:none;font-size:11px;padding:2px 0;margin-bottom:2px"></div>
    <div id="acc-cookiesbadge-${acc.idx}" class="cookies-expired-badge" style="display:none">${t('cookies_expired_badge')}</div>
    <label class="acc-skip-tests${acc.apply_tests ? ' active' : ''}" id="acc-apply-label-${acc.idx}">
      <input type="checkbox" id="acc-apply-cb-${acc.idx}" ${acc.apply_tests ? 'checked' : ''}
        onchange="applyTestsToggle(${acc.idx}, this)">
      ${t('card_apply_tests')}
    </label>
    <div class="acc-actions">
      <button class="btn-sm" id="acc-pause-btn-${acc.idx}"
        onclick="sendCmd({type:'account_pause', idx:${acc.idx}})">${t('btn_acc_pause')}</button>
      <span class="touch-toggle ${acc.resume_touch_enabled !== false ? 'on' : 'off'}" id="acc-touch-toggle-${acc.idx}" onclick="touchToggle(${acc.idx},this)" title="Авто-подъём резюме: бот сам «обновляет дату» резюме на hh каждые несколько часов (бесплатно), чтобы оно поднималось в поиске рекрутеров. Больше просмотров → больше приглашений. Клик — вкл/выкл.">
        <span class="tgl-dot"></span>
        <span>Авто-подъём резюме</span>
        <span id="acc-touch-label-${acc.idx}">${acc.resume_touch_enabled !== false ? 'вкл' : 'выкл'}</span>
      </span>
      <button class="btn-sm" id="acc-touch-btn-${acc.idx}"
        onclick="resumeTouchNow(${acc.idx},this)" title="Поднять резюме в поиске hh прямо сейчас (разовое «обновление даты»).">Поднять сейчас</button>
      <button class="btn-sm"
        onclick="declineDiscards(${acc.idx},this)" title="Когда работодатель отклоняет отклик, переписка-«отказ» так и висит в списке чатов на hh и засоряет его. Кнопка массово закрывает (архивирует) эти отказные переписки — чисто косметика. На отклики, резюме и новые вакансии НЕ влияет.">${t('btn_clear_discards')}</button>
      <button class="btn-sm llm-toggle-btn llm-on" id="acc-llm-btn-${acc.idx}"
        onclick="llmToggleAccount(${acc.idx},this)" title="Вкл/выкл генерацию AI-ответов на сообщения HR для этого аккаунта. Отправку всё равно подтверждаешь вручную во вкладке «Чаты».">AI-ответы</button>
      <button class="btn-sm" style="font-size:9px;padding:1px 5px;color:var(--primary);border-color:var(--primary)"
        onclick="llmRunNow(this)" title="Прочитать новые сообщения HR и подготовить черновики ответов в очередь (вкладка «Чаты»). НИЧЕГО не отправляет.">Подготовить ответы</button>
      <button class="btn-sm" id="acc-campaign-btn-${acc.idx}"
        style="color:var(--primary);border-color:var(--primary);font-weight:600"
        onclick="showCampaignConfigurator(${acc.idx})">Запустить кампанию</button>
      ${acc.temp ? `<button class="btn-sm" style="color:var(--red);border-color:var(--red)" onclick="sessionRemove(${acc.idx})">${t('btn_delete')}</button>` : ''}
    </div>
    <details class="acc-letter-wrap" id="acc-letter-wrap-${acc.idx}">
      <summary>${t('letter_section')}</summary>
      <div class="acc-letter-body">
        <select id="acc-letter-tpl-${acc.idx}" class="form-input" style="font-size:11px;padding:3px 6px;margin-bottom:6px"
          onchange="letterPickTpl(${acc.idx})">
          <option value="">— пусто —</option>
          <option value="__custom__">Своё</option>
        </select>
        <textarea id="acc-letter-ta-${acc.idx}" class="form-input" rows="3"
          style="font-size:11px" placeholder="Сопроводительное письмо...">${esc(acc.letter||'')}</textarea>
        <div style="display:flex;gap:6px;margin-top:6px;align-items:center">
          <button class="btn-sm" onclick="letterSave(${acc.idx},this)">${t('btn_save')}</button>
          <span id="acc-letter-st-${acc.idx}" style="font-size:11px;color:var(--dim)"></span>
        </div>
      </div>
    </details>
    <details class="acc-letter-wrap" id="acc-url-wrap-${acc.idx}">
      <summary>${t('url_section')}</summary>
      <div class="acc-letter-body">
        <div id="acc-url-checks-${acc.idx}" style="margin-bottom:8px"></div>
        <div style="display:flex;gap:6px;align-items:center">
          <button class="btn-sm" onclick="urlAccSave(${acc.idx},this)">${t('btn_apply_url')}</button>
          <span id="url-acc-st-${acc.idx}" style="font-size:11px;color:var(--dim)"></span>
        </div>
      </div>
    </details>
    <details class="acc-letter-wrap">
      <summary>Умные фильтры</summary>
      <div class="acc-letter-body" style="font-size:11px">
        <div style="display:flex;flex-wrap:wrap;gap:6px 14px;margin-bottom:8px">
          <label style="cursor:pointer;display:flex;align-items:center;gap:4px">
            <input type="checkbox" class="smart-filter-cb" data-key="filter_low_competition" style="accent-color:var(--primary)"><10 откликов
          </label>
          <label style="cursor:pointer;display:flex;align-items:center;gap:4px">
            <input type="checkbox" class="smart-filter-cb" data-key="filter_agencies" style="accent-color:var(--yellow)"> Без агентств
          </label>
          <label style="cursor:pointer;display:flex;align-items:center;gap:4px">
            <input type="checkbox" class="smart-filter-cb" data-key="skip_inconsistent" style="accent-color:var(--cyan)"> Пре-чек опыта
          </label>
          <label style="cursor:pointer;display:flex;align-items:center;gap:4px">
            <input type="checkbox" class="smart-filter-cb" data-key="auto_apply_tests" style="accent-color:var(--magenta)"> Авто-тесты
          </label>
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:6px 14px;margin-bottom:8px">
          <label style="display:flex;align-items:center;gap:4px">Свежесть:
            <select class="smart-filter-sel" data-key="search_period_days" style="font-size:10px;padding:1px 4px">
              <option value="0">Все</option><option value="1">1д</option><option value="3">3д</option><option value="7">7д</option><option value="14">14д</option>
            </select>
          </label>
          <label style="display:flex;align-items:center;gap:4px">LLM каждые:
            <select class="smart-filter-sel" data-key="llm_check_interval" style="font-size:10px;padding:1px 4px">
              <option value="2">2м</option><option value="5">5м</option><option value="10">10м</option><option value="15">15м</option><option value="30">30м</option>
            </select>
          </label>
          <label style="display:flex;align-items:center;gap:4px">Лимит/день:
            <input type="number" class="smart-filter-num" data-key="daily_apply_limit" min="0" max="500" style="width:50px;font-size:10px;padding:1px 4px" placeholder="0">
          </label>
        </div>
        <div style="color:var(--dim);font-size:10px;line-height:1.5">
          Из анализа 14К переговоров: удалёнка 74%, junior 78%, аналитик 100%, IT-аккред. только 17% интервью
        </div>
      </div>
    </details>
  `;
}

function updateCard(card, acc) {
  // Status badge — глобальная пауза перекрывает статус
  const badge = document.getElementById('acc-badge-' + acc.idx);
  if (badge) {
    const globalPaused = State.lastSnapshot?.paused;
    const accPaused = acc.paused;
    if (globalPaused) {
      badge.className = 'acc-status-badge status-idle';
      badge.textContent = t('status_all_paused');
      badge.title = '';
    } else if (accPaused) {
      if (acc.hard_stopped && acc.daily_limit > 0 && acc.daily_sent >= acc.daily_limit) {
        badge.className = 'acc-status-badge status-limit';
        badge.textContent = `${t('status_daily_limit')} ${acc.daily_sent}/${acc.daily_limit}`;
        badge.title = t('status_daily_limit_hint');
      } else if (acc.limit_exceeded) {
        badge.className = 'acc-status-badge status-limit';
        badge.textContent = '' + t('status_hh_limit');
        badge.title = acc.status_detail || t('status_hh_limit_hint');
      } else {
        badge.className = 'acc-status-badge status-idle';
        badge.textContent = t('status_acc_paused');
        badge.title = '';
      }
    } else if (!acc.armed) {
      // Кампания не запущена — главный предохранитель
      badge.className = 'acc-status-badge status-idle';
      badge.textContent = acc.status === 'done' ? 'ЗАВЕРШЕНА' : 'НЕ ЗАПУЩЕНА';
      badge.title = acc.status_detail || 'Нажмите «Запустить кампанию»';
    } else {
      const [icon, labelKey, cls] = STATUS_MAP[acc.status] || ['', null, 'status-idle'];
      badge.className = 'acc-status-badge ' + cls;
      const tl = acc.total_limit || 0;
      const progress = tl ? ` ${acc.campaign_sent || 0}/${tl}` : '';
      badge.textContent = icon + ' ' + (labelKey ? t(labelKey) : acc.status.toUpperCase()) + progress;
      if (acc.status_detail) badge.title = acc.status_detail;
    }
  }
  // Кнопка запуска/остановки кампании на карточке — синхронизировать с armed
  const campBtn = document.getElementById('acc-campaign-btn-' + acc.idx);
  if (campBtn) {
    if (acc.armed) {
      campBtn.textContent = 'Остановить кампанию';
      campBtn.style.color = 'var(--red)';
      campBtn.style.borderColor = 'var(--red)';
      campBtn.onclick = () => cardStopCampaign(acc.idx);
    } else {
      campBtn.textContent = 'Запустить кампанию';
      campBtn.style.color = 'var(--primary)';
      campBtn.style.borderColor = 'var(--primary)';
      campBtn.onclick = () => showCampaignConfigurator(acc.idx);
    }
  }

  // Resume stats block
  const rsBlock = document.getElementById('acc-rs-' + acc.idx);
  if (rsBlock && acc.resume_views_7d > 0) {
    rsBlock.style.display = '';
    setText('acc-rs-views-' + acc.idx, acc.resume_views_7d);
    setText('acc-rs-vnew-' + acc.idx, acc.resume_views_new);
    setText('acc-rs-shows-' + acc.idx, acc.resume_shows_7d);
    setText('acc-rs-inv-' + acc.idx, acc.resume_invitations_7d);
    // Touch timer
    const timerEl = document.getElementById('acc-touch-timer-' + acc.idx);
    if (timerEl) {
      const secs = acc.resume_next_touch_seconds || 0;
      if (secs > 0) {
        const h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60);
        timerEl.style.display = '';
        timerEl.textContent = `${t('rs_raise_in')} ${h > 0 ? h + 'ч' : ''}${m}м`;
      } else {
        timerEl.style.display = '';
        timerEl.textContent = `${acc.resume_free_touches || 0} ${t('rs_raises_avail')}`;
        timerEl.className = 'acc-touch-timer c-green';
      }
    }
  }

  // Auto-touch toggle + button
  const touchToggleEl = document.getElementById('acc-touch-toggle-' + acc.idx);
  const touchLabelEl  = document.getElementById('acc-touch-label-' + acc.idx);
  const touchBtn      = document.getElementById('acc-touch-btn-' + acc.idx);
  const autoOn = acc.resume_touch_enabled !== false;
  const m = acc.next_resume_touch ? acc.next_resume_touch.match(/\(([^)]+)\)/) : null;
  const countdown = m && m[1]; // "2ч30м"
  if (touchToggleEl && !(_touchPending[acc.idx] && Date.now() < _touchPending[acc.idx])) {
    touchToggleEl.className = 'touch-toggle ' + (autoOn ? 'on' : 'off');
    if (touchLabelEl) {
      if (autoOn) {
        touchLabelEl.textContent = countdown ? `вкл · через ${countdown}` : 'вкл';
      } else {
        touchLabelEl.textContent = countdown ? `выкл · было через ${countdown}` : 'выкл';
      }
    }
  }
  if (touchBtn) {
    const touching = touchBtn.getAttribute('data-touching');
    if (touching) {
      if (countdown) {
        touchBtn.removeAttribute('data-touching');
        touchBtn.disabled = false;
        touchBtn.textContent = 'Сейчас';
        touchBtn.style.color = '';
      }
    } else if (!touchBtn.disabled) {
      touchBtn.textContent = 'Сейчас';
      touchBtn.style.color = '';
    }
  }

  // Stats
  const dailyInfo = acc.daily_limit > 0 ? ` (${acc.daily_sent || 0}/${acc.daily_limit} сегодня)` : (acc.daily_sent ? ` (${acc.daily_sent} сегодня)` : '');
  setText('acc-sent-' + acc.idx, acc.sent);
  setText('acc-total-' + acc.idx, (acc.total_applied ?? '') + dailyInfo);
  setText('acc-tests-' + acc.idx, acc.tests);
  setText('acc-already-' + acc.idx, acc.already_applied);
  setText('acc-err-' + acc.idx, acc.errors);

  // Questionnaire sent (show when > 0)
  const qBox = document.getElementById('acc-qsent-box-' + acc.idx);
  if (qBox) {
    const qSent = acc.questionnaire_sent || 0;
    qBox.style.display = qSent > 0 ? '' : 'none';
    setText('acc-qsent-' + acc.idx, qSent);
  }

  // Salary filter stat (only show when filter is active)
  const salBox = document.getElementById('acc-sal-box-' + acc.idx);
  if (salBox) {
    const minSal = acc.min_salary || (State.lastSnapshot && State.lastSnapshot.config && State.lastSnapshot.config.min_salary) || 0;
    salBox.style.display = minSal > 0 ? '' : 'none';
    setText('acc-sal-' + acc.idx, acc.salary_skipped || 0);
  }

  // HH interviews stat box — свежие (60д) крупно, всего мелко
  const intrvBox = document.getElementById('acc-intrv-box-' + acc.idx);
  if (intrvBox) {
    const recent = acc.hh_interviews_recent ?? acc.hh_interviews ?? 0;
    const total  = acc.hh_interviews || 0;
    intrvBox.style.display = total > 0 ? '' : 'none';
    setText('acc-intrv-' + acc.idx, recent);
    const totalEl = document.getElementById('acc-intrv-total-' + acc.idx);
    if (totalEl) totalEl.textContent = total > recent ? `всего ${total}` : '';
  }


  // Progress bar
  const prog = document.getElementById('acc-prog-' + acc.idx);
  if (prog) {
    let pct = 0;
    if (acc.status === 'applying' && acc.total_vacancies > 0) {
      pct = Math.round(acc.current_vacancy_idx / acc.total_vacancies * 100);
      prog.className = 'acc-progress-fill applying';
    } else if (acc.status === 'collecting') {
      pct = 30; // indeterminate pulse
      prog.className = 'acc-progress-fill';
    } else if (acc.status === 'limit') {
      pct = 100;
      prog.className = 'acc-progress-fill limit';
    } else {
      pct = 0;
      prog.className = 'acc-progress-fill';
    }
    prog.style.width = pct + '%';
  }

  // Compact card mode
  if (State.compactCards.has(acc.idx)) {
    card.classList.add('compact');
  } else {
    card.classList.remove('compact');
  }

  // Consecutive errors badge
  const errBadge = document.getElementById('acc-errbadge-' + acc.idx);
  if (errBadge) {
    const n = acc.consecutive_errors || 0;
    const threshold = State.lastSnapshot?.config?.auto_pause_errors || 5;
    if (n > 0) {
      errBadge.style.display = '';
      errBadge.textContent = `${n} ${t('errs_in_row')}`;
      errBadge.style.color = n >= threshold ? 'var(--red)' : 'var(--yellow)';
    } else {
      errBadge.style.display = 'none';
    }
  }

  // Cookies expired badge
  const cookiesBadge = document.getElementById('acc-cookiesbadge-' + acc.idx);
  if (cookiesBadge) {
    cookiesBadge.style.display = acc.cookies_expired ? '' : 'none';
  }

  // Current vacancy
  const vac = document.getElementById('acc-vacancy-' + acc.idx);
  if (vac) {
    if (acc.current_vacancy_title) {
      vac.innerHTML = `
        <div class="acc-vacancy-title">${esc(acc.current_vacancy_title)}</div>
        <div class="acc-vacancy-company c-dim">@ ${esc(acc.current_vacancy_company)}</div>
      `;
    } else if (acc.status === 'applying') {
      vac.innerHTML = `<div class="acc-vacancy-title c-dim">${t('card_sending')}</div>`;
    } else {
      vac.innerHTML = `<div class="acc-vacancy-title c-dim">${esc(acc.status_detail) || t('card_waiting')}</div>`;
    }
  }

  // Meta
  const meta = document.getElementById('acc-meta-' + acc.idx);
  if (meta) {
    const parts = [];
    if (acc.found_vacancies > 0) parts.push(`${acc.found_vacancies} найдено`);
    if (acc.next_resume_touch) parts.push(`резюме: ${acc.next_resume_touch}`);
    meta.textContent = parts.join('  ');
  }

  // HH stats
  const hh = document.getElementById('acc-hh-' + acc.idx);
  if (hh) {
    if (acc.hh_stats_loading && !acc.hh_stats_updated) {
      hh.textContent = t('card_hh_loading');
    } else if (acc.hh_stats_updated) {
      const recent = acc.hh_interviews_recent ?? acc.hh_interviews ?? 0;
      const total  = acc.hh_interviews || 0;
      const intrvStr = total > recent
        ? `<span style="color:#f0c060">${recent}</span><span class="c-dim">(${total} всего)</span>`
        : `<span style="color:#f0c060">${recent}</span>`;
      const unreadStr = acc.hh_unread_by_employer ? ` &nbsp;<span class="c-blue">${acc.hh_unread_by_employer} HR не чит.</span>` : '';
      hh.innerHTML =
        intrvStr + ` ${t('hh_interviews')} &nbsp;` +
        `<span class="c-yellow">${acc.hh_viewed}</span> ${t('hh_viewed')} &nbsp;` +
        `<span class="c-red">${acc.hh_discards}</span> ${t('hh_discards')}` +
        unreadStr +
        ` &nbsp;<span class="c-dim">(${acc.hh_stats_updated})</span>`;
    } else {
      hh.textContent = acc.hh_stats_loading ? 'HH...' : '—';
    }
  }

  // History
  const hist = document.getElementById('acc-hist-' + acc.idx);
  if (hist && acc.action_history && acc.action_history.length > 0) {
    hist.textContent = acc.action_history.slice(-5).join('  |  ');
  }

  // Per-account event log
  const elog = document.getElementById('acc-elog-' + acc.idx);
  if (elog && acc.acc_event_log) {
    if (acc.acc_event_log.length === 0) {
      elog.innerHTML = '';
    } else {
      elog.innerHTML = acc.acc_event_log.map(e => {
        const co = e.company ? ` <span style="color:var(--dim)">@ ${esc(e.company)}</span>` : '';
        const extra = e.extra ? `<div class="acc-elog-extra">${esc(e.extra)}</div>` : '';
        return `<div class="acc-elog-entry">
          <span class="acc-elog-time">${e.time}</span>
          <span class="acc-elog-icon">${e.icon}</span>
          <div class="acc-elog-body">
            <div class="acc-elog-title">${esc(e.title)}${co}</div>
            ${extra}
          </div>
        </div>`;
      }).join('');
    }
  }

  // Apply tests checkbox
  const skipCb = document.getElementById('acc-apply-cb-' + acc.idx);
  const skipLabel = document.getElementById('acc-apply-label-' + acc.idx);
  if (skipCb && skipCb.checked !== !!acc.apply_tests) skipCb.checked = !!acc.apply_tests;
  if (skipLabel) {
    if (acc.apply_tests) skipLabel.classList.add('active');
    else skipLabel.classList.remove('active');
  }

  // Pause button — учитываем глобальную паузу
  const pauseBtn = document.getElementById('acc-pause-btn-' + acc.idx);
  if (pauseBtn) {
    const globalPaused = State.lastSnapshot?.paused;
    if (globalPaused) {
      pauseBtn.textContent = t('btn_acc_global_pause');
      pauseBtn.classList.add('paused');
      pauseBtn.disabled = true;
      pauseBtn.title = 'Снимите глобальную паузу в правом верхнем углу';
    } else {
      pauseBtn.disabled = false;
      pauseBtn.title = '';
      if (acc.paused) {
        pauseBtn.textContent = t('btn_acc_resume');
        pauseBtn.classList.add('paused');
      } else {
        pauseBtn.textContent = t('btn_acc_pause');
        pauseBtn.classList.remove('paused');
      }
    }
  }

  // LLM toggle button
  const llmBtn = document.getElementById('acc-llm-btn-' + acc.idx);
  if (llmBtn) {
    const enabled = acc.llm_enabled !== false; // default true
    llmBtn.textContent = enabled ? 'AI-ответы: вкл' : 'AI-ответы: выкл';
    llmBtn.classList.toggle('llm-on', enabled);
    llmBtn.classList.toggle('llm-off', !enabled);
  }
  // LLM status line on card
  const llmSt = document.getElementById('acc-llm-status-' + acc.idx);
  if (llmSt) {
    const globalLlm = State.lastSnapshot?.config?.llm_enabled;
    const accLlm = acc.llm_enabled !== false;
    if (!globalLlm) {
      llmSt.style.display = '';
      llmSt.textContent = 'LLM глобально выключен';
      llmSt.style.color = 'var(--red)';
    } else if (!accLlm) {
      llmSt.style.display = '';
      llmSt.textContent = 'LLM выключен для аккаунта';
      llmSt.style.color = 'var(--dim)';
    } else if (acc.llm_status) {
      llmSt.style.display = '';
      llmSt.textContent = '' + acc.llm_status + (acc.llm_replied_count ? ` (всего: ${acc.llm_replied_count})` : '');
      llmSt.style.color = acc.llm_status.startsWith('') ? 'var(--primary)' : acc.llm_status.startsWith('') ? 'var(--dim)' : 'var(--cyan)';
    } else {
      llmSt.style.display = '';
      llmSt.textContent = 'LLM: ожидание первого цикла';
      llmSt.style.color = 'var(--dim)';
    }
  }
  const oauthBtn = document.getElementById('acc-oauth-btn-' + acc.idx);
  if (oauthBtn) {
    const oauth = !!acc.use_oauth;
    oauthBtn.textContent = oauth ? 'API' : 'Web';
    oauthBtn.style.color = oauth ? 'var(--primary)' : 'var(--cyan)';
    oauthBtn.style.borderColor = oauth ? 'var(--primary)' : 'var(--cyan)';
  }

  // Smart filters sync (global config → card checkboxes)
  const cfg = State.lastSnapshot?.config || {};
  card.querySelectorAll('.smart-filter-cb').forEach(cb => {
    const key = cb.dataset.key;
    if (cfg[key] !== undefined) cb.checked = cfg[key];
    if (!cb._bound) {
      cb._bound = true;
      cb.onchange = () => sendCmd({type: 'set_config', key, value: cb.checked});
    }
  });
  card.querySelectorAll('.smart-filter-sel').forEach(sel => {
    const key = sel.dataset.key;
    if (cfg[key] !== undefined) sel.value = cfg[key];
    if (!sel._bound) {
      sel._bound = true;
      sel.onchange = () => sendCmd({type: 'set_config', key, value: parseInt(sel.value) || 0});
    }
  });
  card.querySelectorAll('.smart-filter-num').forEach(inp => {
    const key = inp.dataset.key;
    if (cfg[key] !== undefined && !inp._focused) inp.value = cfg[key] || '';
    if (!inp._bound) {
      inp._bound = true;
      inp.onfocus = () => { inp._focused = true; };
      inp.onblur = () => { inp._focused = false; };
      inp.onchange = () => sendCmd({type: 'set_config', key, value: parseInt(inp.value) || 0});
    }
  });
}

function renderGlobalStats(snap) {
  const g = snap.global_stats;
  const el = document.getElementById('global-stats-body');
  if (!el) return;
  const rows = [
    [t('gs_found'),    `<span class="c-cyan">${g.total_found}</span>`],
    [t('gs_applied'),  `<span class="c-green">${g.total_sent}</span>`],
    [t('gs_tests'),    `<span class="c-magenta">${g.total_tests}</span>`],
    [t('gs_errors'),   `<span class="c-red">${g.total_errors}</span>`],
    [t('gs_in_db'),    `<span class="c-blue">${g.storage_total}</span>`],
    [t('gs_in_db_tests'), `<span class="c-magenta">${g.storage_tests}</span>`],
  ];
  el.innerHTML = rows.map(([l, v]) =>
    `<div class="global-row"><span class="lbl">${l}</span>${v}</div>`
  ).join('');
}

function renderRecentResponses(snap) {
  const list = document.getElementById('recent-list');
  if (!list) return;
  if (!snap.recent_responses.length) {
    list.innerHTML = `<div class="c-dim" style="padding:8px;font-size:11px">${t('recent_empty')}</div>`;
    return;
  }
  list.innerHTML = snap.recent_responses.slice(0, 50).map(r => {
    const title = r.title ? r.title.substring(0, 35) + (r.title.length > 35 ? '…' : '') : `ID:${r.id}`;
    return `
      <div class="resp-item">
        <span class="resp-time">${r.time}</span>
        <span>${r.icon}</span>
        <div>
          <div class="resp-title">${esc(title)}</div>
          ${r.company ? `<div class="resp-company">@ ${esc(r.company)}</div>` : ''}
        </div>
      </div>
    `;
  }).join('');
}

// ── Log tab ──
function logSetLevel(btn, level) {
  State.logLevel = level;
  document.querySelectorAll('.log-level-btn').forEach(b => {
    const isActive = b.dataset.level === level;
    if (isActive) b.classList.add('active');
    else b.classList.remove('active');
  });
  if (State.lastSnapshot) renderLog(State.lastSnapshot);
}

function logSyncAccFilter(snap) {
  const sel = document.getElementById('log-acc-filter');
  if (!sel) return;
  const current = sel.value;
  const names = [...new Set((snap.accounts||[]).map(a => a.short).filter(Boolean))];
  sel.innerHTML = `<option value="">${t('log_all_accs')}</option>` +
    names.map(n => `<option value="${esc(n)}"${current===n?' selected':''}>${esc(n)}</option>`).join('');
}

let _renderLogLastKey = '';
function renderLog(snap) {
  if (!snap) return;
  logSyncAccFilter(snap);
  const list = document.getElementById('log-list');
  if (!list || !snap.log) return;

  const search = (document.getElementById('log-search')?.value || '').toLowerCase();
  const accF   = document.getElementById('log-acc-filter')?.value || '';
  const level  = State.logLevel;

  let entries = snap.log;
  if (level)  entries = entries.filter(e => e.level === level);
  if (accF)   entries = entries.filter(e => e.acc === accF);
  if (search) entries = entries.filter(e =>
    (e.message||'').toLowerCase().includes(search) || (e.acc||'').toLowerCase().includes(search)
  );
  entries = entries.slice(0, State.MAX_LOG_NODES);

  const cnt = document.getElementById('log-count');
  if (cnt) cnt.textContent = `${entries.length} записей`;

  const last = entries.length > 0 ? entries[entries.length - 1] : null;
  const logKey = entries.length + '|' + (last ? last.time + last.acc + (last.message||'') : '');
  if (logKey === _renderLogLastKey) return;
  _renderLogLastKey = logKey;

  const frag = document.createDocumentFragment();
  entries.forEach(entry => {
    const el = document.createElement('div');
    el.className = 'log-item';
    el.innerHTML = `
      <span class="log-time">${entry.time}</span>
      <span class="log-acc" style="color:${colorVar(entry.color)}">${esc(entry.acc)}</span>
      <span class="log-msg log-${entry.level}">${esc(entry.message)}</span>
    `;
    frag.appendChild(el);
  });
  list.innerHTML = '';
  list.appendChild(frag);
}

// ── HH Status tab ──
function renderHH(snap) {
  const content = document.getElementById('hh-content');
  if (!content || !snap.accounts) return;

  content.innerHTML = snap.accounts.filter(acc => !acc.temp || acc.bot_active).map(acc => {
    let body = '';
    if (acc.hh_stats_loading && !acc.hh_stats_updated) {
      body = `<div class="c-dim">${t('hh_loading')}</div>`;
    } else if (!acc.hh_stats_updated) {
      body = `<div class="c-dim">${t('hh_no_data')}</div>`;
    } else {
      // Counters
      body += `<div class="hh-counters">
        <div class="hh-counter"><div class="hh-counter-val c-green">${acc.hh_interviews}</div><div class="hh-counter-lbl">${t('hh_interviews')}</div></div>
        <div class="hh-counter"><div class="hh-counter-val c-yellow">${acc.hh_viewed}</div><div class="hh-counter-lbl">${t('hh_viewed')}</div></div>
        <div class="hh-counter"><div class="hh-counter-val c-red">${acc.hh_discards}</div><div class="hh-counter-lbl">${t('hh_discards')}</div></div>
        <div class="hh-counter"><div class="hh-counter-val c-dim">${acc.hh_not_viewed}</div><div class="hh-counter-lbl">${t('hh_not_viewed')}</div></div>
        ${acc.hh_unread_by_employer ? `<div class="hh-counter"><div class="hh-counter-val c-blue">${acc.hh_unread_by_employer}</div><div class="hh-counter-lbl">HR не чит.</div></div>` : ''}
      </div>`;
      body += `<div class="c-dim" style="font-size:11px;margin-bottom:10px">${t('hh_updated')} ${acc.hh_stats_updated}</div>`;

      // Interview list
      if (acc.hh_interviews_list && acc.hh_interviews_list.length) {
        body += `<div style="font-weight:700;margin-bottom:6px;color:var(--primary)">${t('hh_inv_list')}</div>`;
        body += acc.hh_interviews_list.map(item => {
          const url = item.neg_id ? `https://hh.ru/applicant/negotiations/${item.neg_id}` : '';
          const textEl = url
            ? `<a class="hh-interview-text" href="${url}" target="_blank" rel="noopener">${esc(item.text || '')}</a>`
            : `<span class="hh-interview-text">${esc(item.text || '')}</span>`;
          return `<div class="hh-interview-item">` +
            (item.date ? `<span class="hh-interview-date">${esc(item.date)}</span>` : '') +
            textEl +
            `</div>`;
        }).join('');
      }

      // Possible offers
      if (acc.hh_possible_offers && acc.hh_possible_offers.length) {
        body += `<div style="font-weight:700;margin:12px 0 6px;color:var(--yellow)">${t('hh_offers')}</div>`;
        body += acc.hh_possible_offers.map(o =>
          `<div class="hh-offer-item">
            <div class="hh-offer-name">${esc(o.name)}</div>
            <div class="hh-offer-vacs">${o.vacancyNames.slice(0,3).map(n=>esc(n)).join(', ')}</div>
          </div>`
        ).join('');
      }
    }

    const colorStyle = `color:var(--${acc.color === 'magenta' ? 'magenta' : acc.color || 'text'})`;
    return `
      <div class="hh-account-block">
        <div class="hh-account-title" style="${colorStyle}">${esc(acc.name)}</div>
        ${body}
      </div>
    `;
  }).join('');
}

// ── Applied / Tests tabs ──
// Applied tab state
const AppliedState = { all: [], shown: 0, pageSize: 80 };
// Активные мультивыбранные критерии (source_query). Пусто = все.
const AppliedFilters = { sources: new Set() };

async function loadApplied(force) {
  if (!force && AppliedState.all.length) { appliedRender(); return; }
  try {
    const res = await fetch('/api/applied?limit=2000');
    const items = await res.json();
    AppliedState.all = items;
    // Populate account filter
    const sel = document.getElementById('applied-acc-filter');
    const prev = sel.value;
    const accs = [...new Set(items.map(i => i.account).filter(Boolean))].sort();
    sel.innerHTML = `<option value="">${t('applied_all_accs')}</option>` +
      accs.map(a => `<option value="${esc(a)}"${a===prev?' selected':''}>${esc(a)}</option>`).join('');
    appliedRenderChips();
    appliedRender();
  } catch(e) { console.error('loadApplied', e); }
}

// Чипы критериев со счётчиком откликов по каждому
function appliedRenderChips() {
  const box = document.getElementById('applied-source-chips');
  if (!box) return;
  const counts = {};
  for (const i of AppliedState.all) {
    const s = i.source_query;
    if (s) counts[s] = (counts[s] || 0) + 1;
  }
  const srcs = Object.keys(counts).sort((a,b) => counts[b]-counts[a] || a.localeCompare(b,'ru'));
  // Сбросить выбор, которого больше нет в данных
  for (const s of [...AppliedFilters.sources]) if (!(s in counts)) AppliedFilters.sources.delete(s);
  if (!srcs.length) { box.innerHTML = ''; return; }
  box.innerHTML = srcs.map(s => {
    const on = AppliedFilters.sources.has(s);
    return `<button class="chip${on ? ' chip-on' : ''}" onclick="appliedToggleSource('${esc(s).replace(/'/g, "\\'")}')">`
      + `${esc(s)}<span class="chip-count">${counts[s]}</span></button>`;
  }).join('');
}

function appliedToggleSource(s) {
  if (AppliedFilters.sources.has(s)) AppliedFilters.sources.delete(s);
  else AppliedFilters.sources.add(s);
  appliedRenderChips();
  appliedRender();
}

function appliedToggleAdv() {
  const adv = document.getElementById('applied-adv');
  if (adv) adv.style.display = (adv.style.display === 'none' || !adv.style.display) ? 'flex' : 'none';
}

function appliedOnPeriodChange() {
  const v = document.getElementById('applied-period')?.value;
  const custom = document.getElementById('applied-date-custom');
  if (custom) custom.style.display = (v === 'custom') ? 'flex' : 'none';
  appliedRender();
}

function appliedResetFilters() {
  AppliedFilters.sources.clear();
  ['applied-search','applied-sal-min','applied-sal-max','applied-date-from','applied-date-to'].forEach(id => {
    const el = document.getElementById(id); if (el) el.value = '';
  });
  ['applied-sal-only','applied-hide-empty'].forEach(id => {
    const el = document.getElementById(id); if (el) el.checked = false;
  });
  const acc = document.getElementById('applied-acc-filter'); if (acc) acc.value = '';
  const per = document.getElementById('applied-period'); if (per) per.value = '';
  const custom = document.getElementById('applied-date-custom'); if (custom) custom.style.display = 'none';
  appliedRenderChips();
  appliedRender();
}

function appliedSort(field) {
  if (AppliedSort.field === field) AppliedSort.dir *= -1;
  else { AppliedSort.field = field; AppliedSort.dir = -1; }
  // update header arrows
  document.querySelectorAll('#panel-applied .sort-th').forEach(th => {
    const f = th.getAttribute('onclick')?.match(/appliedSort\('(\w+)'\)/)?.[1];
    th.classList.toggle('sorted', f === field);
    const arrow = th.querySelector('.sort-arrow');
    if (arrow) arrow.textContent = (f === field) ? (AppliedSort.dir === -1 ? '↓' : '↑') : '↕';
  });
  appliedRender();
}

function appliedRender() {
  const search = (document.getElementById('applied-search')?.value || '').toLowerCase();
  const accF   = document.getElementById('applied-acc-filter')?.value || '';
  const hideEmpty = document.getElementById('applied-hide-empty')?.checked;
  const srcSet = AppliedFilters.sources;

  // Период
  const period = document.getElementById('applied-period')?.value || '';
  let dateFrom = null, dateTo = null;
  if (period === 'custom') {
    const f = document.getElementById('applied-date-from')?.value;
    const to = document.getElementById('applied-date-to')?.value;
    if (f) dateFrom = new Date(f + 'T00:00:00');
    if (to) dateTo = new Date(to + 'T23:59:59');
  } else if (period) {
    const days = parseInt(period, 10);
    const d = new Date(); d.setHours(0,0,0,0);
    if (days === 1) dateFrom = d;                 // сегодня
    else { d.setDate(d.getDate() - (days - 1)); dateFrom = d; }
  }

  // Зарплата
  const salMin = parseInt(document.getElementById('applied-sal-min')?.value, 10);
  const salMax = parseInt(document.getElementById('applied-sal-max')?.value, 10);
  const salOnly = document.getElementById('applied-sal-only')?.checked;
  const hasSalMin = !isNaN(salMin), hasSalMax = !isNaN(salMax);

  let items = AppliedState.all;
  if (accF)        items = items.filter(i => i.account === accF);
  if (srcSet.size) items = items.filter(i => srcSet.has(i.source_query));
  if (hideEmpty)   items = items.filter(i => i.title || i.company);
  if (dateFrom)    items = items.filter(i => i.at && new Date(i.at) >= dateFrom);
  if (dateTo)      items = items.filter(i => i.at && new Date(i.at) <= dateTo);
  if (salOnly)     items = items.filter(i => i.salary_from || i.salary_to);
  if (hasSalMin)   items = items.filter(i => (i.salary_to || i.salary_from || 0) >= salMin);
  if (hasSalMax)   items = items.filter(i => (i.salary_from || i.salary_to || 0) <= salMax || (!i.salary_from && !i.salary_to));
  if (search)      items = items.filter(i =>
    (i.title||'').toLowerCase().includes(search) ||
    (i.company||'').toLowerCase().includes(search) ||
    (i.source_query||'').toLowerCase().includes(search) ||
    (i.vacancy_id||'').includes(search)
  );

  // Счётчик активных фильтров + кнопка сброса
  const activeCount = (accF?1:0) + srcSet.size + (hideEmpty?1:0) + (period?1:0)
    + (hasSalMin?1:0) + (hasSalMax?1:0) + (salOnly?1:0);
  const cntEl = document.getElementById('applied-filter-count');
  if (cntEl) { cntEl.textContent = activeCount; cntEl.style.display = activeCount ? 'inline-block' : 'none'; }
  const resetEl = document.getElementById('applied-reset');
  if (resetEl) resetEl.style.display = (activeCount || search) ? 'inline-block' : 'none';

  // Sort
  const sf = AppliedSort.field, sd = AppliedSort.dir;
  items = [...items].sort((a, b) => {
    let av = a[sf] ?? '', bv = b[sf] ?? '';
    if (typeof av === 'number') return (av - bv) * sd;
    return String(av).localeCompare(String(bv), 'ru') * sd;
  });

  document.getElementById('applied-count').textContent = `(${items.length})`;
  AppliedState.shown = Math.min(AppliedState.pageSize, items.length);
  appliedFillTable(items.slice(0, AppliedState.shown));

  const lm = document.getElementById('applied-loadmore');
  const sh = document.getElementById('applied-shown');
  if (items.length > AppliedState.shown) {
    lm.style.display = 'block';
    sh.textContent = `${t('shown_of')} ${AppliedState.shown} ${t('shown_of2')} ${items.length}`;
    lm._items = items;
  } else {
    lm.style.display = 'none';
  }
}

function appliedShowMore() {
  const lm = document.getElementById('applied-loadmore');
  const items = lm._items || [];
  AppliedState.shown = Math.min(AppliedState.shown + AppliedState.pageSize, items.length);
  appliedFillTable(items.slice(0, AppliedState.shown));
  const sh = document.getElementById('applied-shown');
  if (AppliedState.shown >= items.length) {
    lm.style.display = 'none';
  } else {
    sh.textContent = `${t('shown_of')} ${AppliedState.shown} ${t('shown_of2')} ${items.length}`;
  }
}

function appliedFillTable(items) {
  const tbody = document.getElementById('applied-tbody');
  const cards = document.getElementById('applied-cards');
  if (!tbody) return;
  tbody.innerHTML = items.map(item => {
    const dt = item.at
      ? new Date(item.at).toLocaleString('ru-RU', {day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})
      : '';
    const acc = (item.account || '').replace(/^(.*?)\s*\((.+?)\)\s*$/, '$2') || item.account || '';
    const sal = item.salary_from || item.salary_to
      ? `${item.salary_from ? item.salary_from.toLocaleString('ru') : '?'} — ${item.salary_to ? item.salary_to.toLocaleString('ru') : '?'}`
      : '';
    const hasTitle = !!(item.title || item.company);
    const titleCell = item.title
      ? `<a href="${esc(item.url)}" target="_blank">${esc(item.title)}</a>`
      : `<a href="${esc(item.url)}" target="_blank" style="color:var(--dim)">hh.ru/vacancy/${esc(item.vacancy_id)}</a>`;
    const srcCell = item.source_query
      ? `<span class="criteria-badge">${esc(item.source_query)}</span>` : '<span class="c-dim">—</span>';
    return `<tr class="${hasTitle ? '' : 'row-no-title'}">
      <td class="c-dim" style="white-space:nowrap">${dt}</td>
      <td style="white-space:nowrap">${esc(acc)}</td>
      <td>${titleCell}</td>
      <td>${esc(item.company || '')}</td>
      <td>${srcCell}</td>
      <td class="c-green" style="white-space:nowrap">${sal}</td>
    </tr>`;
  }).join('');

  // Mobile card view (shown via CSS on narrow screens)
  if (cards) {
    cards.innerHTML = items.map(item => {
      const dt = item.at
        ? new Date(item.at).toLocaleString('ru-RU', {day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})
        : '';
      const acc = (item.account || '').replace(/^(.*?)\s*\((.+?)\)\s*$/, '$2') || item.account || '';
      const sal = item.salary_from || item.salary_to
        ? `${item.salary_from ? item.salary_from.toLocaleString('ru') : '?'} — ${item.salary_to ? item.salary_to.toLocaleString('ru') : '?'}`
        : '';
      const titleHtml = item.title
        ? `<a href="${esc(item.url)}" target="_blank">${esc(item.title)}</a>`
        : `<a href="${esc(item.url)}" target="_blank" style="color:var(--dim)">hh.ru/vacancy/${esc(item.vacancy_id)}</a>`;
      const badge = item.source_query
        ? `<span class="criteria-badge">${esc(item.source_query)}</span>` : '';
      return `<div class="applied-card">
        <div class="applied-card-title">${titleHtml}</div>
        ${item.company ? `<div class="applied-card-company">${esc(item.company)}</div>` : ''}
        <div class="applied-card-meta">
          ${badge}
          ${sal ? `<span class="c-green">${sal}</span>` : ''}
        </div>
        <div class="applied-card-foot">
          <span>${esc(acc)}</span><span class="c-dim">${dt}</span>
        </div>
      </div>`;
    }).join('');
  }
}

// ── Vacancy DB tab ───────────────────────────────────────────────
const DBState = { all: [], shown: 0, pageSize: 100 };
const DB_STATUS = {
  sent:         ['', 'db_status_sent_lbl',        'c-green'],
  test_passed:  ['', 'db_status_test_passed_lbl', 'c-cyan'],
  test_pending: ['', 'db_status_test_pending_lbl','c-magenta'],
};
// DB_STATUS translated labels
T.ru.db_status_sent_lbl         = 'Откликнулись';
T.ru.db_status_test_passed_lbl  = 'Тест пройден';
T.ru.db_status_test_pending_lbl = 'Не пройден';
T.en.db_status_sent_lbl         = 'Applied';
T.en.db_status_test_passed_lbl  = 'Test passed';
T.en.db_status_test_pending_lbl = 'Not passed';

async function loadDB(force) {
  if (!force && DBState.all.length) { dbRender(); return; }
  try {
    const res = await fetch('/api/vacancies?limit=3000');
    const items = await res.json();
    DBState.all = items;
    // Populate account filter
    const sel = document.getElementById('db-acc-filter');
    const prev = sel.value;
    const accs = [...new Set(items.flatMap(i => i.applied_by || []))].sort();
    sel.innerHTML = `<option value="">${t('db_all_accs')}</option>` +
      accs.map(a => `<option value="${esc(a)}"${a===prev?' selected':''}>${esc(a)}</option>`).join('');
    dbRender();
  } catch(e) { console.error('loadDB', e); }
}

function dbSort(field) {
  if (DBSort.field === field) DBSort.dir *= -1;
  else { DBSort.field = field; DBSort.dir = -1; }
  document.querySelectorAll('#panel-db .sort-th').forEach(th => {
    const f = th.getAttribute('onclick')?.match(/dbSort\('(\w+)'\)/)?.[1];
    th.classList.toggle('sorted', f === field);
    const arrow = th.querySelector('.sort-arrow');
    if (arrow) arrow.textContent = (f === field) ? (DBSort.dir === -1 ? '↓' : '↑') : '↕';
  });
  dbRender();
}

function dbRender() {
  const search  = (document.getElementById('db-search')?.value || '').toLowerCase();
  const statusF = document.getElementById('db-status-filter')?.value || '';
  const accF    = document.getElementById('db-acc-filter')?.value || '';

  let items = DBState.all;
  if (statusF) items = items.filter(i => i.status === statusF);
  if (accF)    items = items.filter(i => (i.applied_by || []).includes(accF));
  if (search)  items = items.filter(i =>
    (i.title||'').toLowerCase().includes(search) ||
    (i.company||'').toLowerCase().includes(search) ||
    (i.vacancy_id||'').includes(search)
  );

  // Sort
  const sf = DBSort.field, sd = DBSort.dir;
  items = [...items].sort((a, b) => {
    let av = a[sf] ?? '', bv = b[sf] ?? '';
    if (typeof av === 'number') return (av - bv) * sd;
    return String(av).localeCompare(String(bv), 'ru') * sd;
  });

  document.getElementById('db-count').textContent =
    `(${items.length} из ${DBState.all.length})`;
  DBState.shown = Math.min(DBState.pageSize, items.length);
  dbFillTable(items.slice(0, DBState.shown));

  const lm = document.getElementById('db-loadmore');
  const sh = document.getElementById('db-shown');
  if (items.length > DBState.shown) {
    lm.style.display = 'block';
    sh.textContent = `${t('shown_of')} ${DBState.shown} ${t('shown_of2')} ${items.length}`;
    lm._items = items;
  } else {
    lm.style.display = 'none';
  }
}

function dbShowMore() {
  const lm = document.getElementById('db-loadmore');
  const items = lm._items || [];
  DBState.shown = Math.min(DBState.shown + DBState.pageSize, items.length);
  dbFillTable(items.slice(0, DBState.shown));
  const sh = document.getElementById('db-shown');
  if (DBState.shown >= items.length) lm.style.display = 'none';
  else sh.textContent = `${t('shown_of')} ${DBState.shown} ${t('shown_of2')} ${items.length}`;
}

function dbFillTable(items) {
  const tbody = document.getElementById('db-tbody');
  if (!tbody) return;
  tbody.innerHTML = items.map(item => {
    const [icon, labelKey, cls] = DB_STATUS[item.status] || ['', null, 'c-dim'];
    const label = labelKey ? t(labelKey) : item.status;
    const dt = item.at
      ? new Date(item.at).toLocaleString('ru-RU', {day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})
      : '';
    const titleCell = item.title
      ? `<a href="${esc(item.url)}" target="_blank">${esc(item.title)}</a>`
      : `<a href="${esc(item.url)}" target="_blank" style="color:var(--dim)">hh.ru/vacancy/${esc(item.vacancy_id)}</a>`;
    const accs = (item.applied_by || [])
      .map(a => `<span style="font-size:10px;background:var(--bg-card2);padding:1px 5px;border-radius:3px">${esc(a.replace(/^.*?\((.+?)\).*$/, '$1') || a)}</span>`)
      .join(' ');
    return `<tr>
      <td><span class="${cls}" style="white-space:nowrap">${icon} ${label}</span></td>
      <td class="c-dim" style="white-space:nowrap">${dt}</td>
      <td>${titleCell}</td>
      <td>${esc(item.company || '')}</td>
      <td>${accs || '<span class="c-dim">—</span>'}</td>
      <td><button class="btn-sm" style="padding:1px 6px;color:var(--red);border-color:var(--red)"
        onclick="dbDelete('${esc(item.vacancy_id)}',this)" title="Удалить из базы">×</button></td>
    </tr>`;
  }).join('');
}

async function dbDelete(vid, btn) {
  if (!await showConfirm(`${t('confirm_del_db_pre')} <b>${vid}</b> ${t('confirm_del_db_mid')}<br><span style="color:var(--dim);font-size:12px">${t('confirm_del_db_body')}</span>`)) return;
  btn.disabled = true;
  try {
    const res = await fetch(`/api/vacancy/${vid}`, {method:'DELETE'});
    const data = await res.json();
    if (data.ok) {
      DBState.all = DBState.all.filter(i => i.vacancy_id !== vid);
      btn.closest('tr').remove();
      const cnt = document.getElementById('db-count');
      if (cnt) cnt.textContent = `(${DBState.all.length})`;
    } else {
      btn.disabled = false;
    }
  } catch(e) { btn.disabled = false; }
}

async function loadTests() {
  try {
    const res = await fetch('/api/tests?limit=300');
    const items = await res.json();
    const tbody = document.getElementById('tests-tbody');
    document.getElementById('tests-count').textContent = `(${items.length})`;

    tbody.innerHTML = items.map(item => {
      const dt = item.at ? new Date(item.at).toLocaleString('ru-RU', {day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}) : '';
      // Account name: short (strip parenthetical) if possible
      const accFull = item.account_name || '';
      const accShort = accFull.replace(/^.*?\((.+?)\).*$/, '$1') || accFull;
      const resumeLink = item.resume_hash
        ? `<a href="https://hh.ru/resume/${item.resume_hash}" target="_blank" style="font-size:11px;color:var(--cyan)">${accShort}</a>`
        : `<span class="c-dim">${esc(accShort) || '—'}</span>`;
      // Applied by list
      const appliedBy = item.applied_by || [];
      const appliedCell = appliedBy.length
        ? `<span style="color:var(--primary)">${appliedBy.map(a =>a.replace(/^.*?\((.+?)\).*$/, '$1') || a).join(',')}</span>`
        : `<span class="c-dim">—</span>`;
      return `<tr>
        <td class="c-dim">${dt}</td>
        <td>${esc(item.title || item.vacancy_id)}</td>
        <td>${esc(item.company)}</td>
        <td>${resumeLink}</td>
        <td>${appliedCell}</td>
        <td><a href="${esc(item.url)}" target="_blank">hh.ru/vacancy/${item.vacancy_id}</a></td>
      </tr>`;
    }).join('');
  } catch(e) {}
}

// ── Tabs switching ──────────────────────────────────────────────
document.getElementById('tabs').addEventListener('click', e => {
  const t = e.target.closest('.tab');
  if (!t) return;
  const tab = t.dataset.tab;
  if (!tab) return;
  window.switchTab(tab);
});

function syncSettingsSliders(snap) {
  if (!snap.config) return;
  SETTINGS_DEF.forEach(s => {
    const el = document.getElementById('sr-' + s.key);
    const sv = document.getElementById('sv-' + s.key);
    if (el && snap.config[s.key] !== undefined) {
      el.value = snap.config[s.key];
      if (sv) sv.textContent = snap.config[s.key];
    }
  });
}

// ── Helpers ──────────────────────────────────────────────────
function esc(s) {
  if (!s) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// Всплывающее уведомление. type: 'success' | 'error' | 'info'
function showToast(message, type = 'info') {
  const box = document.getElementById('toast-container');
  if (!box) { console.log('toast:', type, message); return; }
  const el = document.createElement('div');
  el.className = 'toast toast-' + type;
  el.textContent = message;
  box.appendChild(el);
  // авто-скрытие
  setTimeout(() => {
    el.classList.add('toast-hide');
    setTimeout(() => el.remove(), 300);
  }, 3500);
  el.onclick = () => el.remove();
}
window.showToast = showToast;

// Заголовок резюме из HH может быть строкой, [{string:...}] или {string:...}
function resumeTitle(r) {
  const t = r && r.title;
  if (typeof t === 'string') return t || 'Резюме';
  let v = Array.isArray(t) ? t[0] : t;
  if (v && typeof v === 'object') return v.string || v.text || v.name || 'Резюме';
  return t ? String(t) : 'Резюме';
}

// Разбить строку «слово1, слово2; слово3» в массив непустых слов
function parseWords(s) {
  return String(s || '')
    .split(/[,;\n]+/)
    .map(w => w.trim())
    .filter(Boolean);
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function colorVar(color) {
  const map = {
    cyan: 'var(--cyan)',
    magenta: 'var(--magenta)',
    green: 'var(--primary)',
    yellow: 'var(--yellow)',
    red: 'var(--red)',
    blue: 'var(--blue)',
  };
  return map[color] || 'var(--text)';
}

// ── Session mode toggle ───────────────────────────────────────
let _sessMode = 'curl';
function sessSetMode(mode) {
  _sessMode = mode;
  const panelCurl = document.getElementById('sess-panel-curl');
  const panelManual = document.getElementById('sess-panel-manual');
  if (panelCurl) panelCurl.style.display = mode === 'curl' ? '' : 'none';
  if (panelManual) panelManual.style.display = mode === 'manual' ? '' : 'none';
  const btnCurl = document.getElementById('sess-mode-curl');
  const btnManual = document.getElementById('sess-mode-manual');
  if (btnCurl) { btnCurl.style.background = mode === 'curl' ? 'var(--cyan)' : 'transparent'; btnCurl.style.color = mode === 'curl' ? '#000' : 'var(--dim)'; }
  if (btnManual) { btnManual.style.background = mode === 'manual' ? 'var(--cyan)' : 'transparent'; btnManual.style.color = mode === 'manual' ? '#000' : 'var(--dim)'; }
}

// ── Session Add ───────────────────────────────────────────────
async function sessionAdd() {
  const nameEl   = document.getElementById('session-name');
  const letterEl = document.getElementById('session-letter');
  const st       = document.getElementById('session-status');
  let cookieStr = '';

  if (_sessMode === 'manual') {
    const hhtoken   = document.getElementById('ck-hhtoken')?.value.trim();
    const xsrf      = document.getElementById('ck-xsrf')?.value.trim();
    const hhul      = document.getElementById('ck-hhul')?.value.trim();
    const cryptedId = document.getElementById('ck-crypted-id')?.value.trim();
    if (!hhtoken) { st.textContent = 'hhtoken обязателен'; st.style.color = 'var(--red)'; return; }
    if (!xsrf)    { st.textContent = '_xsrf обязателен';   st.style.color = 'var(--red)'; return; }
    const parts = [`hhtoken=${hhtoken}`, `_xsrf=${xsrf}`];
    if (hhul)      parts.push(`hhul=${hhul}`);
    if (cryptedId) parts.push(`crypted_id=${cryptedId}`);
    cookieStr = parts.join('; ');
  } else {
    const ta = document.getElementById('session-cookies');
    cookieStr = ta?.value.trim();
    if (!cookieStr) { st.textContent = 'Вставьте строку cookies'; st.style.color = 'var(--red)'; return; }
  }

  st.textContent = 'Проверяю сессию...'; st.style.color = 'var(--dim)';
  try {
    const res = await fetch('/api/session/add', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        cookies: cookieStr,
        name: nameEl?.value.trim() || '',
        letter: letterEl?.value || ''
      })
    });
    const data = await res.json();
    if (data.status === 'ok') {
      markAuthComplete();
      st.textContent = '' + data.message; st.style.color = 'var(--primary)';
      // Очищаем оба режима
      const ta = document.getElementById('session-cookies');
      if (ta) ta.value = '';
      ['ck-hhtoken','ck-xsrf','ck-hhul','ck-crypted-id'].forEach(id => {
        const el = document.getElementById(id); if (el) el.value = '';
      });
      if (nameEl)   nameEl.value = '';
      if (letterEl) letterEl.value = '';
    } else {
      st.textContent = '' + data.message; st.style.color = 'var(--red)';
    }
  } catch(e) {
    st.textContent = '' + e; st.style.color = 'var(--red)';
  }
}


async function sessionChangeResume(idx, hash) {
  await fetch('/api/session/' + idx, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ resume_hash: hash })
  });
  // Обновляем ссылку на резюме в карточке без перерисовки
  const card = document.getElementById('sess-card-' + idx);
  if (card) {
    const link = card.querySelector('a[href*="/resume/"]');
    if (link) link.href = 'https://hh.ru/resume/' + hash;
  }
}

async function sessionSaveLetter(idx) {
  const ta = document.getElementById('sess-letter-' + idx);
  const st = document.getElementById('sess-letter-st-' + idx);
  if (!ta || !st) return;
  st.textContent = ''; st.style.color = 'var(--dim)';
  try {
    const res = await fetch('/api/session/' + idx, {
      method: 'PATCH',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({letter: ta.value})
    });
    const data = await res.json();
    if (data.status === 'ok') {
      st.textContent = 'Сохранено'; st.style.color = 'var(--primary)';
      // Обновить ApplyLetters чтобы шаблон в дропдауне тоже обновился
      ApplyLetters[idx] = ta.value;
      setTimeout(() => { st.textContent = ''; }, 2000);
    } else {
      st.textContent = '' + data.message; st.style.color = 'var(--red)';
    }
  } catch(e) {
    st.textContent = '' + e; st.style.color = 'var(--red)';
  }
}

async function sessionRemove(idx) {
  if (!await showConfirm(t('confirm_del_sess'))) return;
  const card = document.getElementById('card-' + idx);
  if (card) card.remove();
  await fetch('/api/session/' + idx, {method: 'DELETE'});
}

async function sessionRefresh(idx) {
  const res = await fetch('/api/session/' + idx + '/refresh', {method: 'POST'});
  const data = await res.json();
  // snapshot will update via WS
}

async function sessionActivate(idx) {
  const res = await fetch('/api/session/' + idx + '/activate', {method: 'POST'});
  const data = await res.json();
  if (data.status !== 'ok') {
    alert('Ошибка: ' + data.message);
  }
}

// ── Apply Tab ────────────────────────────────────────────────
const ApplyState = { checking: false, submitting: false, vid: '', accIdx: 0, questions: [] };

const ApplyLetters = {};

function applyBuildAccountSelect(snap) {
  const sel = document.getElementById('apply-account');
  const tpl = document.getElementById('apply-letter-tpl');
  if (!sel || !snap) return;

  (snap.accounts || []).forEach(a => { ApplyLetters[a.idx] = a.letter || ''; });

  // пересоздаём только если изменился состав аккаунтов
  const newKey = (snap.accounts || []).map(a => a.idx + ':' + a.name).join(',');
  if (sel.dataset.builtKey !== newKey) {
    sel.dataset.builtKey = newKey;
    const prev = sel.value;
    sel.innerHTML = (snap.accounts || []).map(a =>
      `<option value="${a.idx}">${esc(a.name)}</option>`
    ).join('');
    if (prev) sel.value = prev;
  }

  // Rebuild template dropdown: one option per account letter
  if (tpl) {
    const newTplKey = newKey;
    if (tpl.dataset.builtKey !== newTplKey) {
      tpl.dataset.builtKey = newTplKey;
      const prevTpl = tpl.value;
      tpl.innerHTML = `<option value="">— выбрать шаблон —</option>` +
        (snap.accounts || []).map(a =>
          `<option value="${a.idx}">${esc(a.name)}</option>`
        ).join('');
      if (prevTpl) tpl.value = prevTpl;
    }
  }

  // Fill letter textarea if it's empty or still contains a default letter
  const ta = document.getElementById('apply-letter');
  if (ta && (!ta.value || Object.values(ApplyLetters).includes(ta.value))) {
    ta.value = ApplyLetters[parseInt(sel.value) || 0] || '';
  }
}

function applyFillLetter(idx) {
  const ta = document.getElementById('apply-letter');
  if (ta) ta.value = ApplyLetters[parseInt(idx)] || '';
  // Sync template selector to the chosen account
  const tpl = document.getElementById('apply-letter-tpl');
  if (tpl) tpl.value = idx;
}

function applyPickTemplate(idx) {
  if (!idx) return;
  const ta = document.getElementById('apply-letter');
  if (ta && ApplyLetters[parseInt(idx)] !== undefined)
    ta.value = ApplyLetters[parseInt(idx)];
}

function applyShowResult(msg, type) {
  const el = document.getElementById('apply-result');
  if (!el) return;
  el.style.display = '';
  el.className = 'apply-result ' + type;
  el.innerHTML = msg;
}

function applyHideQuestionnaire() {
  const el = document.getElementById('apply-questionnaire');
  if (el) { el.style.display = 'none'; el.innerHTML = ''; }
}

async function applyCheck() {
  if (ApplyState.checking) return;
  const accIdx = parseInt(document.getElementById('apply-account').value || '0');
  const raw = document.getElementById('apply-vacancy').value.trim();
  if (!raw) { applyShowResult('Введите ссылку или ID вакансии', 'err'); return; }

  ApplyState.checking = true;
  ApplyState.accIdx = accIdx;
  applyHideQuestionnaire();
  applyShowResult('Проверяю вакансию...', 'info');

  try {
    const letter = document.getElementById('apply-letter')?.value || '';
    const res = await fetch('/api/apply/check', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({account_idx: accIdx, vacancy_id: raw, letter})
    });
    const data = await res.json();
    ApplyState.vid = data.vacancy_id || raw;

    if (data.status === 'sent') {
      applyShowResult(`${data.message}`, 'ok');
      applyHideQuestionnaire();
    } else if (data.status === 'already') {
      applyShowResult(`${data.message}`, 'warn');
    } else if (data.status === 'limit') {
      applyShowResult(`${data.message}`, 'err');
    } else if (data.status === 'test_required') {
      ApplyState.questions = data.questions || [];
      applyShowResult(
        `<b>${data.message}</b><br>Проверьте ответы ниже и нажмите «Откликнуться»`,
        'info'
      );
      applyRenderQuestionnaire(data);
    } else {
      applyShowResult(`${data.message || 'Неизвестная ошибка'}`, 'err');
    }
  } catch(e) {
    applyShowResult('Ошибка запроса:' + e, 'err');
  } finally {
    ApplyState.checking = false;
  }
}

function applyRenderQuestionnaire(data) {
  const el = document.getElementById('apply-questionnaire');
  if (!el) return;
  el.style.display = '';
  const qs = data.questions || [];

  let html = `
    <hr class="apply-divider">
    <div style="font-size:13px;font-weight:700;margin-bottom:12px">
      Опросник — ${qs.length} вопросов
    </div>

    <div class="apply-q-list">
  `;

  qs.forEach((q, i) => {
    html += `<div class="apply-q-item">
      <div class="apply-q-num">Вопрос ${i+1} из ${qs.length}</div>
      <div class="apply-q-text">${esc(q.text)}</div>
    `;

    if (q.type === 'radio') {
      html += `<div class="apply-radio-opts">`;
      q.options.forEach(opt => {
        const checked = opt.value === q.suggested ? 'checked' : '';
        html += `<label class="apply-radio-opt">
          <input type="radio" name="aq_${q.field}" value="${esc(opt.value)}" ${checked}>
          ${esc(opt.label)}
        </label>`;
      });
      html += `</div>`;
    } else if (q.type === 'textarea') {
      html += `<textarea class="apply-q-answer" id="aq_${q.field}" rows="3">${esc(q.suggested)}</textarea>`;
    }
    html += `</div>`;
  });

  html += `</div>
    <div class="apply-btn-row" style="margin-top:16px">
      <button class="apply-btn" onclick="applySubmit()">Откликнуться</button>
      <button class="apply-btn-secondary" onclick="applyHideQuestionnaire();applyShowResult('','');document.getElementById('apply-result').style.display='none'">Отмена</button>
      <span id="apply-submit-status" style="font-size:12px;color:var(--dim)"></span>
    </div>
  `;

  el.innerHTML = html;
}

async function applySubmit() {
  if (ApplyState.submitting) return;
  ApplyState.submitting = true;
  const statusEl = document.getElementById('apply-submit-status');
  if (statusEl) statusEl.textContent = 'Отправляю...';

  // Собираем ответы
  const answers = {};
  ApplyState.questions.forEach(q => {
    if (q.type === 'radio') {
      const checked = document.querySelector(`input[name="aq_${q.field}"]:checked`);
      if (checked) answers[q.field] = checked.value;
    } else if (q.type === 'textarea') {
      const ta = document.getElementById('aq_' + q.field);
      if (ta) answers[q.field] = ta.value;
    }
  });

  const letter = document.getElementById('apply-letter')?.value || '';

  try {
    const res = await fetch('/api/apply/submit', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({account_idx: ApplyState.accIdx, vacancy_id: ApplyState.vid, letter, answers})
    });
    const data = await res.json();

    if (data.status === 'sent') {
      applyShowResult(`${data.message}`, 'ok');
      applyHideQuestionnaire();
    } else if (data.status === 'limit') {
      applyShowResult(`${data.message}`, 'err');
    } else {
      applyShowResult(`${data.message}`, 'err');
    }
    if (statusEl) statusEl.textContent = '';
  } catch(e) {
    applyShowResult('Ошибка:' + e, 'err');
  } finally {
    ApplyState.submitting = false;
  }
}

// ── Resume Views Tab ────────────────────────────────────────
let _loadViewsLastTs = 0;
async function loadViews() {
  const now = Date.now();
  if (now - _loadViewsLastTs < 30000) return;
  _loadViewsLastTs = now;
  const statsRow = document.getElementById('views-stats-row');
  const accsEl = document.getElementById('views-accounts');
  if (!statsRow || !accsEl) return;

  const snap = State.lastSnapshot;
  if (!snap) return;

  // Aggregate header stats
  let totalViews = 0, totalViewsNew = 0, totalShows = 0, totalInv = 0, totalInvNew = 0;
  (snap.accounts || []).forEach(a => {
    totalViews += a.resume_views_7d || 0;
    totalViewsNew += a.resume_views_new || 0;
    totalShows += a.resume_shows_7d || 0;
    totalInv += a.resume_invitations_7d || 0;
    totalInvNew += a.resume_invitations_new || 0;
  });

  statsRow.innerHTML = `
    <div class="views-stat-card"><div class="views-stat-val c-cyan">${totalViews}</div><div class="views-stat-lbl">${t('views_7d')}</div></div>
    <div class="views-stat-card"><div class="views-stat-val c-green">+${totalViewsNew}</div><div class="views-stat-lbl">${t('views_new')}</div></div>
    <div class="views-stat-card"><div class="views-stat-val" style="color:var(--dim)">${totalShows}</div><div class="views-stat-lbl">${t('views_shows')}</div></div>
    <div class="views-stat-card"><div class="views-stat-val c-magenta">${totalInv}</div><div class="views-stat-lbl">${t('views_invitations')}</div></div>
    <div class="views-stat-card"><div class="views-stat-val c-green">+${totalInvNew}</div><div class="views-stat-lbl">${t('views_inv_new')}</div></div>
  `;

  // Per-account blocks
  const existingIds = new Set([...accsEl.querySelectorAll('.views-acc-block')].map(el => el.dataset.idx));
  const snapIds = new Set((snap.accounts || []).map(a => String(a.idx)));
  const needRebuild = [...snapIds].some(id => !existingIds.has(id)) || [...existingIds].some(id => !snapIds.has(id));

  if (needRebuild) {
    accsEl.innerHTML = '';
    for (const acc of (snap.accounts || [])) {
      const block = document.createElement('div');
      block.className = 'views-acc-block';
      block.dataset.idx = String(acc.idx);
      const colorStyle = `color:${colorVar(acc.color)}`;
      block.innerHTML = `
        <div class="views-acc-title">
          <span style="${colorStyle}">${esc(acc.name)}</span>
          <button class="btn-refresh" onclick="loadViewHistory(${acc.idx})">${t('btn_load_history')}</button>
          <button class="btn-sm" onclick="declineDiscards(${acc.idx},this)">Очистить дискарды</button>
        </div>
        <div id="views-hist-${acc.idx}"><div class="c-dim" style="font-size:12px;padding:8px 0">Загружаю...</div></div>
      `;
      accsEl.appendChild(block);
      loadViewHistory(acc.idx);
    }
  } else {
    // повторяем загрузку для тех у кого ещё нет данных и не помечено как loaded
    for (const acc of (snap.accounts || [])) {
      const histEl = document.getElementById('views-hist-' + acc.idx);
      if (histEl && !histEl.dataset.loaded && !histEl.dataset.loading) {
        histEl.dataset.loading = '1';
        loadViewHistory(acc.idx).finally(() => { histEl.removeAttribute('data-loading'); });
      }
    }
  }
}

// ── Resume Audit ─────────────────────────────────────────────
let _auditSelPopulated = false;
function syncAuditSelector(snap) {
  const sel = document.getElementById('audit-acc-sel');
  if (!sel || _auditSelPopulated) return;
  const accs = snap?.accounts || [];
  if (!accs.length) return;
  sel.innerHTML = accs.map(a => `<option value="${a.idx}">${esc(a.short || a.name)}</option>`).join('');
  _auditSelPopulated = true;
}

async function runResumeAudit(btn) {
  const sel = document.getElementById('audit-acc-sel');
  const st = document.getElementById('audit-status');
  const res = document.getElementById('audit-result');
  if (!sel || !res) return;
  const idx = sel.value;
  if (btn) btn.disabled = true;
  if (st) { st.textContent = 'Анализирую...'; st.style.color = 'var(--dim)'; }
  res.style.display = 'none';
  try {
    const extraTerms = (document.getElementById('audit-extra-terms')?.value || '').trim();
    const qs = extraTerms ? `?extra_terms=${encodeURIComponent(extraTerms)}` : '';
    const r = await fetch(`/api/account/${idx}/resume_audit${qs}`);
    const data = await r.json();
    if (data.error) {
      if (st) { st.textContent = '' + data.error; st.style.color = 'var(--red)'; }
      return;
    }
    if (st) st.textContent = '';
    res.style.display = '';
    res.innerHTML = renderAuditResult(data);
  } catch(e) {
    if (st) { st.textContent = '' + e; st.style.color = 'var(--red)'; }
  } finally {
    if (btn) btn.disabled = false;
  }
}

function renderAuditResult(d) {
  const levelIcon = {critical: '', high: '', medium: '', low: '', info: 'ℹ'};
  const levelOrder = {critical: 0, high: 1, medium: 2, low: 3, info: 4};
  const issues = (d.issues || []).sort((a, b) => (levelOrder[a.level] ?? 5) - (levelOrder[b.level] ?? 5));

  const expYears = Math.floor((d.total_experience_months || 0) / 12);
  const expMonths = (d.total_experience_months || 0) % 12;
  const expStr = expYears ? `${expYears} г. ${expMonths ? expMonths + ' м.' : ''}` : `${expMonths} м.`;

  const statusColors = {
    'not_looking_for_job': 'var(--red)',
    'looking_for_offers': 'var(--yellow)',
    'actively_searching': 'var(--primary)',
  };
  const statusColor = statusColors[d.job_search_status] || 'var(--dim)';

  const pctColor = (d.percent || 0) >= 80 ? 'var(--primary)' : (d.percent || 0) >= 60 ? 'var(--yellow)' : 'var(--red)';

  let html = `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:12px">
      <div style="font-size:14px;font-weight:700;margin-bottom:8px">${esc(d.name || '?')}</div>
      <div style="font-size:12px;color:var(--dim);margin-bottom:12px">${esc(d.title || '')}</div>

      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:8px;margin-bottom:14px">
        <div class="audit-card">
          <div class="audit-label">Статус поиска</div>
          <div style="color:${statusColor};font-weight:600">${esc(d.job_search_status_label || '?')}</div>
        </div>
        <div class="audit-card">
          <div class="audit-label">Заполненность</div>
          <div style="color:${pctColor};font-weight:600">${d.percent || 0}%</div>
        </div>
        <div class="audit-card">
          <div class="audit-label">Опыт</div>
          <div>${expStr}</div>
        </div>
        <div class="audit-card">
          <div class="audit-label">Зарплата</div>
          <div>${d.salary ? d.salary + ' ₽' : '<span style="color:var(--red)">не указана</span>'}</div>
        </div>
        <div class="audit-card">
          <div class="audit-label">Фото</div>
          <div>${d.has_photo ? '<span style="color:var(--primary)">Есть</span>' : '<span style="color:var(--red)">Нет</span>'}</div>
        </div>
        <div class="audit-card">
          <div class="audit-label">Статус резюме</div>
          <div style="color:${d.status === 'published' ? 'var(--primary)' : 'var(--red)'}">${esc(d.status || '?')}</div>
        </div>
      </div>

      <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:14px;font-size:12px">
        <div><span style="color:var(--dim)">Формат:</span> ${(d.work_formats || []).join(', ') || '—'}</div>
        <div><span style="color:var(--dim)">График:</span> ${(d.work_schedule || []).join(', ') || '—'}</div>
        <div><span style="color:var(--dim)">Занятость:</span> ${(d.employment || []).join(', ') || '—'}</div>
        <div><span style="color:var(--dim)">Роли:</span> ${(d.roles || []).map(r => esc(r)).join(', ') || '—'}</div>
      </div>

      <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:14px;font-size:12px">
        <div><b>${d.stats_7d?.search_shows ?? 0}</b>показов/7д</div>
        <div><b>${d.stats_7d?.views ?? 0}</b>просмотров<span class="c-green">+${d.stats_7d?.views_new ?? 0}</span></div>
        <div><b>${d.stats_7d?.invitations ?? 0}</b>приглашений<span class="c-green">+${d.stats_7d?.invitations_new ?? 0}</span></div>
      </div>

      <div style="font-size:12px;color:var(--dim);margin-bottom:6px">Навыки: <span style="color:var(--text)">${(d.skills || []).slice(0, 15).map(s => esc(s)).join(', ')}</span></div>
    </div>`;

  if (issues.length) {
    html += `<div style="font-size:13px;font-weight:700;margin-bottom:8px">Рекомендации (${issues.length})</div>`;
    html += issues.map(iss => `
      <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:6px;padding:10px 12px;margin-bottom:6px;display:flex;gap:8px;align-items:flex-start">
        <div style="flex-shrink:0;font-size:14px">${levelIcon[iss.level] || ''}</div>
        <div>
          <div style="font-size:12px">${esc(iss.text)}</div>
          ${iss.fix ? `<div style="font-size:11px;color:var(--cyan);margin-top:3px">${esc(iss.fix)}</div>` : ''}
        </div>
      </div>
    `).join('');
  } else {
    html += '<div style="color:var(--primary);font-size:13px">Проблем не найдено — резюме в хорошей форме!</div>';
  }

  // Market analytics
  const m = d.market;
  if (m && (m.vacancy_count || m.active_seekers)) {
    const ratioColor = m.supply_demand_ratio > 5 ? 'var(--red)' : m.supply_demand_ratio > 2 ? 'var(--yellow)' : 'var(--primary)';
    html += `
      <div style="font-size:13px;font-weight:700;margin-top:16px;margin-bottom:8px">Анализ рынка</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:8px;margin-bottom:14px">
        <div class="audit-card">
          <div class="audit-label">Вакансий</div>
          <div style="font-weight:600;color:var(--cyan)">${(m.vacancy_count || 0).toLocaleString()}</div>
        </div>
        <div class="audit-card">
          <div class="audit-label">Активных соискателей</div>
          <div style="font-weight:600;color:var(--yellow)">${(m.active_seekers || 0).toLocaleString()}</div>
        </div>
        <div class="audit-card">
          <div class="audit-label">Конкуренция (чел/вак)</div>
          <div style="font-weight:600;color:${ratioColor}">${m.supply_demand_ratio || '—'}</div>
        </div>
      </div>`;

    // Experience distribution
    if (m.experience_distribution && m.experience_distribution.length) {
      html += `<div style="font-size:12px;color:var(--dim);margin-bottom:6px">Опыт конкурентов:</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px">`;
      for (const ed of m.experience_distribution) {
        html += `<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:4px;padding:4px 8px;font-size:11px">
          ${esc(ed.name)} <span style="color:var(--cyan);font-weight:600">${(ed.count || 0).toLocaleString()}</span>
        </div>`;
      }
      html += '</div>';
    }

    // Top skills from competitors: green if user has it, red if missing
    if (m.top_competitor_skills && m.top_competitor_skills.length) {
      const userSkills = new Set((d.skills || []).map(s => s.toLowerCase()));
      html += `<div style="font-size:12px;color:var(--dim);margin-bottom:6px">Топ навыки конкурентов:</div>
        <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px">`;
      for (const sk of m.top_competitor_skills) {
        const skName = typeof sk === 'string' ? sk : (sk.name || '');
        const skCount = typeof sk === 'object' ? (sk.count || '') : '';
        const has = userSkills.has(skName.toLowerCase());
        const skColor = has ? 'var(--primary)' : 'var(--red)';
        const skBg = has ? 'rgba(0,255,0,0.08)' : 'rgba(255,0,0,0.08)';
        const countLabel = skCount ? ` (${(skCount/1000).toFixed(0)}K)` : '';
        html += `<span style="background:${skBg};color:${skColor};border:1px solid ${skColor};border-radius:4px;padding:2px 7px;font-size:11px">${esc(skName)}${countLabel}</span>`;
      }
      html += '</div>';
    }
  }

  // ── Weight analysis — exact recipe for 100% ──
  if (d.weight_analysis && d.weight_analysis.length) {
    const filled = d.filled_weight || 0;
    const total = d.total_weight || 1;
    const pct = Math.round(filled / total * 100);
    html += `<div style="font-size:13px;font-weight:700;margin:14px 0 8px">Заполненность резюме: ${filled}/${total} (${pct}%)</div>`;
    html += `<div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:12px">`;
    for (const f of d.weight_analysis) {
      const color = f.filled ? 'var(--primary)' : 'var(--red)';
      const bg = f.filled ? 'rgba(63,185,80,0.1)' : 'rgba(248,81,73,0.1)';
      const icon = f.filled ? '+' : '–';
      html += `<span style="background:${bg};color:${color};border:1px solid ${color};border-radius:4px;padding:2px 8px;font-size:11px" title="weight=${f.weight}, status=${f.status}">${icon} ${esc(f.label)} <b>×${f.weight}</b></span>`;
    }
    html += `</div>`;
    // How to reach 80%+
    const unfilled = d.weight_analysis.filter(f => !f.filled);
    if (unfilled.length && pct < 80) {
      const needed80 = Math.ceil(total * 0.8) - filled;
      html += `<div style="font-size:11px;color:var(--cyan);margin-bottom:12px">Для 80%+ нужно ещё<b>${needed80}</b> веса. Самые ценные: ${unfilled.slice(0,4).map(f =>`<b>${esc(f.label)}</b>(×${f.weight})`).join(',')}</div>`;
    }
  }

  // ── Supply/demand comparison ──
  if (d.supply_demand_comparison && d.supply_demand_comparison.length) {
    html += `<div style="font-size:13px;font-weight:700;margin:14px 0 8px">Конкуренция по запросам</div>`;
    html += `<table style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:12px">`;
    html += `<tr style="color:var(--dim);text-align:left"><th style="padding:4px 8px">Запрос</th><th style="padding:4px 8px">Вакансий</th><th style="padding:4px 8px">Конкуренция</th><th style="padding:4px 8px">Оценка</th></tr>`;
    for (const item of d.supply_demand_comparison) {
      const ratio = item.ratio || 0;
      const rColor = ratio > 30 ? 'var(--red)' : ratio > 15 ? 'var(--yellow)' : 'var(--primary)';
      const label = ratio > 30 ? 'высокая' : ratio > 15 ? 'средняя' : ratio > 0 ? 'низкая' : '—';
      html += `<tr style="border-top:1px solid var(--border)">
        <td style="padding:4px 8px">${esc(item.term)}</td>
        <td style="padding:4px 8px;font-weight:600">${item.vacancies || 0}</td>
        <td style="padding:4px 8px;color:${rColor};font-weight:600">${ratio ? ratio + ' чел/вак' : '—'}</td>
        <td style="padding:4px 8px">${label}</td>
      </tr>`;
    }
    html += `</table>`;
    // Best term recommendation
    const best = d.supply_demand_comparison.find(x => x.ratio > 0);
    if (best && d.supply_demand_comparison.length > 1) {
      const worst = d.supply_demand_comparison[d.supply_demand_comparison.length - 1];
      if (best.term !== worst.term && worst.ratio > best.ratio * 1.5) {
        html += `<div style="font-size:11px;color:var(--cyan);margin-bottom:8px">Запрос «<b>${esc(best.term)}</b>» имеет наименьшую конкуренцию — оптимизируй заголовок резюме под него</div>`;
      }
    }
  }

  // HR Activity
  if (d.hr_activity) {
    const ha = d.hr_activity;
    const total = ha.active_count + ha.slow_count + ha.dead_count;
    if (total > 0) {
      html += `<div style="margin-top:14px;border-top:1px solid var(--border);padding-top:10px">
        <div style="font-size:13px;font-weight:700;margin-bottom:8px">Активность HR-менеджеров</div>
        <div style="display:flex;gap:16px;font-size:12px">
          <div><span style="color:var(--primary);font-weight:600">${ha.active_count}</span> <span style="color:var(--dim)">активных (&lt;3 дн.)</span></div>
          <div><span style="color:var(--yellow);font-weight:600">${ha.slow_count}</span> <span style="color:var(--dim)">медленных (3-7 дн.)</span></div>
          <div><span style="color:var(--red);font-weight:600">${ha.dead_count}</span> <span style="color:var(--dim)">неактивных (&gt;7 дн.)</span></div>
        </div>`;
      if (ha.dead_count > ha.active_count) {
        html += `<div style="font-size:11px;color:var(--yellow);margin-top:6px">Много неактивных HR — часть откликов может не получить ответа</div>`;
      }
      html += `</div>`;
    }
  }

  return html;
}

// ── Hot Leads ────────────────────────────────────────────────
async function loadHotLeads(btn) {
  const sel = document.getElementById('audit-acc-sel');
  const st = document.getElementById('leads-status');
  const res = document.getElementById('leads-result');
  if (!sel || !res) return;
  const idx = sel.value;
  if (btn) btn.disabled = true;
  if (st) { st.textContent = 'Загружаю...'; st.style.color = 'var(--dim)'; }
  res.style.display = 'none';
  try {
    const r = await fetch(`/api/account/${idx}/hot_leads`);
    const data = await r.json();
    if (data.error) {
      if (st) { st.textContent = '' + data.error; st.style.color = 'var(--red)'; }
      return;
    }
    if (st) st.textContent = `${data.total || 0} работодателей`;
    res.style.display = '';
    const offers = data.offers || [];
    if (!offers.length) {
      res.innerHTML = '<div style="color:var(--dim);font-size:12px">Нет горячих лидов</div>';
      return;
    }
    res.innerHTML = `<div style="display:flex;flex-direction:column;gap:6px">${offers.map(o => {
      const vacs = (o.vacancies || []).slice(0, 2).map(v => esc(v)).join(', ');
      const invBadge = o.has_invitation ? '<span style="background:rgba(63,185,80,0.15);color:var(--primary);padding:1px 6px;border-radius:3px;font-size:10px;margin-left:6px">приглашение</span>' : '';
      const link = o.vacancy_id ? `<a href="https://hh.ru/vacancy/${o.vacancy_id}" target="_blank" style="color:var(--cyan);font-size:11px;margin-left:6px">→ вакансия</a>` : '';
      return `<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:6px;padding:8px 12px">
        <div style="font-size:12px;font-weight:600">${esc(o.employer)}${invBadge}${link}</div>
        <div style="font-size:11px;color:var(--dim);margin-top:2px">${vacs}</div>
      </div>`;
    }).join('')}</div>`;
  } catch(e) {
    if (st) { st.textContent = '' + e; st.style.color = 'var(--red)'; }
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ── HR Contacts ─────────────────────────────────────────────
async function loadHrContacts(btn) {
  const st = document.getElementById('contacts-status');
  const res = document.getElementById('contacts-result');
  if (!res) return;
  if (btn) btn.disabled = true;
  if (st) { st.textContent = 'Загружаю...'; st.style.color = 'var(--dim)'; }
  res.style.display = 'none';
  try {
    const r = await fetch('/api/hr_contacts');
    const data = await r.json();
    if (st) st.textContent = `${data.total || 0} контактов`;
    res.style.display = '';
    const contacts = data.contacts || [];
    if (!contacts.length) {
      res.innerHTML = '<div style="color:var(--dim);font-size:12px">Нет собранных контактов. Контакты HR собираются автоматически при проверке вакансий (skip_inconsistent).</div>';
      return;
    }
    let html = '<table style="width:100%;border-collapse:collapse;font-size:11px">';
    html += '<tr style="color:var(--dim);border-bottom:1px solid var(--border)"><th style="text-align:left;padding:4px 6px">Время</th><th style="text-align:left;padding:4px 6px">Вакансия</th><th style="text-align:left;padding:4px 6px">Компания</th><th style="text-align:left;padding:4px 6px">ФИО</th><th style="text-align:left;padding:4px 6px">Email</th><th style="text-align:left;padding:4px 6px">Телефон</th></tr>';
    contacts.slice().reverse().forEach(c => {
      const link = c.vacancy_id ? `<a href="https://hh.ru/vacancy/${c.vacancy_id}" target="_blank" style="color:var(--cyan)">${esc(c.title || c.vacancy_id)}</a>` : esc(c.title || '?');
      html += `<tr style="border-bottom:1px solid rgba(48,54,61,0.5)">
        <td style="padding:4px 6px;color:var(--dim);white-space:nowrap">${esc(c.time || '')}</td>
        <td style="padding:4px 6px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${link}</td>
        <td style="padding:4px 6px;color:var(--dim)">${esc(c.company || '')}</td>
        <td style="padding:4px 6px">${esc(c.fio || '')}</td>
        <td style="padding:4px 6px">${c.email ? `<a href="mailto:${esc(c.email)}" style="color:var(--cyan)">${esc(c.email)}</a>` : ''}</td>
        <td style="padding:4px 6px">${esc(c.phone || '')}</td>
      </tr>`;
    });
    html += '</table>';
    res.innerHTML = html;
  } catch(e) {
    if (st) { st.textContent = '' + e; st.style.color = 'var(--red)'; }
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ── Remindable Negotiations ─────────────────────────────────
async function loadRemindable(btn) {
  const sel = document.getElementById('audit-acc-sel');
  const st = document.getElementById('remindable-status');
  const res = document.getElementById('remindable-result');
  if (!sel || !res) return;
  const idx = sel.value;
  if (btn) btn.disabled = true;
  if (st) { st.textContent = 'Проверяю...'; st.style.color = 'var(--dim)'; }
  res.style.display = 'none';
  try {
    const r = await fetch(`/api/account/${idx}/remindable`);
    const data = await r.json();
    if (data.error) {
      if (st) { st.textContent = '' + data.error; st.style.color = 'var(--red)'; }
      return;
    }
    if (st) st.textContent = `${data.total || 0} переговоров`;
    res.style.display = '';
    const items = data.remindable || [];
    if (!items.length) {
      res.innerHTML = '<div style="color:var(--dim);font-size:12px">Нет переговоров, где можно отправить напоминание.</div>';
      return;
    }
    res.innerHTML = `<div style="display:flex;flex-direction:column;gap:6px">${items.map(item => {
      return `<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:6px;padding:8px 12px">
        <div style="font-size:12px;font-weight:600">${esc(item.employer || '?')}</div>
        <div style="font-size:11px;color:var(--dim);margin-top:2px">${esc(item.vacancy || '')}</div>
      </div>`;
    }).join('')}</div>`;
  } catch(e) {
    if (st) { st.textContent = '' + e; st.style.color = 'var(--red)'; }
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ── OAuth API ────────────────────────────────────────────────
async function oauthGetToken(btn) {
  const sel = document.getElementById('audit-acc-sel');
  const st = document.getElementById('oauth-status');
  if (!sel) return;
  if (btn) btn.disabled = true;
  if (st) { st.textContent = 'Получаю токен...'; st.style.color = 'var(--dim)'; }
  try {
    const r = await fetch(`/api/account/${sel.value}/oauth_token`, {method: 'POST'});
    const d = await r.json();
    if (d.ok) {
      const hrs = Math.round(d.expires_in / 3600);
      if (st) { st.textContent = `Токен: ${d.token_prefix} | ${hrs}ч осталось | refresh: ${d.has_refresh ? 'да' : 'нет'}`; st.style.color = 'var(--primary)'; }
    } else {
      if (st) { st.textContent = '' + (d.error || 'Ошибка'); st.style.color = 'var(--red)'; }
    }
  } catch(e) {
    if (st) { st.textContent = '' + e; st.style.color = 'var(--red)'; }
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function oauthTouch(btn) {
  const sel = document.getElementById('audit-acc-sel');
  const st = document.getElementById('oauth-status');
  if (!sel) return;
  if (btn) btn.disabled = true;
  if (st) { st.textContent = 'Поднимаю резюме...'; st.style.color = 'var(--dim)'; }
  try {
    const r = await fetch(`/api/account/${sel.value}/oauth_touch`, {method: 'POST'});
    const d = await r.json();
    if (d.ok) {
      if (st) { st.textContent = '' + d.message; st.style.color = 'var(--primary)'; }
    } else {
      if (st) { st.textContent = '' + (d.message || d.error); st.style.color = 'var(--yellow)'; }
    }
  } catch(e) {
    if (st) { st.textContent = '' + e; st.style.color = 'var(--red)'; }
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ── Resume Cloning ───────────────────────────────────────────
async function loadAllResumes(btn) {
  const sel = document.getElementById('audit-acc-sel');
  const st = document.getElementById('resumes-status');
  const res = document.getElementById('resumes-result');
  if (!sel || !res) return;
  if (btn) btn.disabled = true;
  if (st) { st.textContent = '...'; st.style.color = 'var(--dim)'; }
  res.style.display = 'none';
  try {
    const r = await fetch(`/api/account/${sel.value}/all_resumes`);
    const data = await r.json();
    if (st) st.textContent = `${data.total || 0} резюме`;
    res.style.display = '';
    const items = data.resumes || [];
    if (!items.length) { res.innerHTML = '<div style="color:var(--dim);font-size:12px">Нет резюме</div>'; return; }
    res.innerHTML = items.map(r => {
      const statusColor = r.status === 'published' ? 'var(--primary)' : r.status === 'not_finished' ? 'var(--red)' : 'var(--yellow)';
      const statusLabel = r.status === 'published' ? 'опубликовано' : r.status === 'not_finished' ? 'не завершено' : r.status === 'modified' ? 'изменено' : r.status;
      const pctColor = (r.percent || 0) >= 80 ? 'var(--primary)' : (r.percent || 0) > 0 ? 'var(--yellow)' : 'var(--red)';
      const statsInfo = (r.views_7d || r.shows_7d) ? ` · ${r.views_7d} · ${r.shows_7d}` : '';
      const contentInfo = r.skills_count ? `${r.skills_count} навыков, ${r.experience_count} мест работы` : 'пусто';
      return `<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:6px;padding:10px 12px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center;gap:12px">
        <div style="flex:1;min-width:0">
          <div style="font-size:12px;font-weight:600">${esc(r.title)}</div>
          <div style="font-size:11px;color:var(--dim);margin-top:2px">
            <span style="color:${statusColor}">${esc(statusLabel)}</span> ·
            <span style="color:${pctColor}">${r.percent || '?'}%</span> ·
            ${r.is_searchable ? 'в поиске' : 'скрыто'} ·
            ${contentInfo}${statsInfo}
          </div>
        </div>
        <div style="display:flex;gap:4px;flex-shrink:0">
          <a href="${esc(r.edit_url)}" target="_blank" class="btn-sm" style="font-size:11px">hh.ru</a>
          <button class="btn-sm" style="font-size:11px" onclick="quickEditResume('${esc(r.hash)}')">Быстро</button>
        </div>
      </div>`;
    }).join('');
  } catch(e) {
    if (st) { st.textContent = '' + e; st.style.color = 'var(--red)'; }
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function cloneResume(btn) {
  const sel = document.getElementById('audit-acc-sel');
  const st = document.getElementById('resumes-status');
  if (!sel) return;
  const preset = document.getElementById('clone-preset')?.value || '';
  const custom = document.getElementById('clone-title')?.value.trim() || '';
  const title = custom || preset;
  if (!title) {
    if (!confirm('Клонировать без заголовка? Придётся задать вручную на hh.ru')) return;
  }
  if (btn) btn.disabled = true;
  if (st) { st.textContent = 'Клонирую...'; st.style.color = 'var(--dim)'; }
  try {
    const r = await fetch(`/api/account/${sel.value}/clone_resume`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({title})
    });
    const data = await r.json();
    if (data.ok) {
      const msg = data.title_set ? `Склонировано: "${title}"` : 'Склонировано (заголовок задай на hh.ru)';
      if (st) { st.textContent = msg; st.style.color = 'var(--primary)'; }
      // Refresh list
      setTimeout(() => loadAllResumes(), 500);
    } else {
      if (st) { st.textContent = '' + (data.error || 'Ошибка'); st.style.color = 'var(--red)'; }
    }
  } catch(e) {
    if (st) { st.textContent = '' + e; st.style.color = 'var(--red)'; }
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function quickEditResume(hash) {
  const sel = document.getElementById('audit-acc-sel');
  if (!sel) return;
  const idx = sel.value;
  const title = prompt('Заголовок резюме (должность):', '');
  if (title === null) return;
  const salary = prompt('Зарплата (₽, 0 = убрать):', '0');
  const skills = prompt('О себе (описание, пусто = не менять):', '');

  const body = {resume_hash: hash};
  if (title) body.title = title;
  if (salary && parseInt(salary) > 0) body.salary = parseInt(salary);
  if (skills) body.skills = skills;

  if (!Object.keys(body).some(k => k !== 'resume_hash')) {
    alert('Нечего менять'); return;
  }

  try {
    const r = await fetch(`/api/account/${idx}/edit_resume`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    });
    const data = await r.json();
    if (data.ok) {
      alert('Резюме обновлено!');
      loadAllResumes();
    } else {
      alert('' + (data.error || 'Ошибка'));
    }
  } catch(e) {
    alert('' + e);
  }
}

async function loadViewHistory(idx) {
  const el = document.getElementById('views-hist-' + idx);
  if (!el) return;
  el.innerHTML = '<div class="c-dim" style="font-size:12px;padding:8px 0">Загружаю...</div>';
  try {
    const res = await fetch(`/api/account/${idx}/resume_views`);
    const data = await res.json();

    // обновляем карточки статов сразу из ответа API не дожидаясь WebSocket
    const s = data.stats || {};
    const statsRow = document.getElementById('views-stats-row');
    if (statsRow && (s.views_7d || s.shows_7d || s.invitations_7d)) {
      statsRow.querySelector('.views-stat-val.c-cyan') && (statsRow.querySelector('.views-stat-val.c-cyan').textContent = s.views_7d || 0);
      const greens = statsRow.querySelectorAll('.views-stat-val.c-green');
      if (greens[0]) greens[0].textContent = '+' + (s.views_new || 0);
      if (greens[1]) greens[1].textContent = '+' + (s.invitations_new || 0);
      const dim = statsRow.querySelector('.views-stat-val[style]');
      if (dim) dim.textContent = s.shows_7d || 0;
      const magenta = statsRow.querySelector('.views-stat-val.c-magenta');
      if (magenta) magenta.textContent = s.invitations_7d || 0;
    }

    el.dataset.loaded = '1'; // помечаем — больше не ретраить
    const history = data.history || [];
    if (!history.length) {
      el.innerHTML = `<div class="c-dim" style="font-size:12px;padding:8px 0">${t('views_no_data')}</div>`;
      return;
    }
    el.innerHTML = `
      <table class="views-table">
        <thead><tr><th>${t('col_date')}</th><th>${t('col_employer')}</th><th>${t('col_vacancy')}</th></tr></thead>
        <tbody>
          ${history.map(h => `<tr>
            <td class="c-dim">${esc(h.date)}</td>
            <td><a href="https://hh.ru/employer/${esc(h.employer_id)}" target="_blank">${esc(h.name)}</a></td>
            <td class="c-dim">${esc(h.vacancy)}</td>
          </tr>`).join('')}
        </tbody>
      </table>
    `;
  } catch(e) {
    el.innerHTML = '<div class="c-red" style="font-size:12px">Ошибка загрузки</div>';
    // не ставим loaded — пусть retry при следующем тике
  }
}

async function declineDiscards(idx, btn) {
  if (!btn) return;
  btn.disabled = true;
  btn.textContent = 'Обрабатываю...';
  try {
    const res = await fetch(`/api/account/${idx}/decline_discards`, {method:'POST'});
    const data = await res.json();
    btn.textContent = `Отклонено: ${data.declined || 0}`;
    setTimeout(() => { btn.disabled = false; btn.textContent = t('btn_clear_discards'); }, 4000);
  } catch(e) {
    btn.textContent = 'Ошибка';
    setTimeout(() => { btn.disabled = false; btn.textContent = t('btn_clear_discards'); }, 3000);
  }
}

async function applyTestsToggle(idx, cb) {
  try {
    const res = await fetch(`/api/account/${idx}/apply_tests`, {method:'POST'});
    const data = await res.json();
    if (!data.ok) { cb.checked = !cb.checked; return; }
    const label = document.getElementById('acc-apply-label-' + idx);
    if (label) {
      if (data.apply_tests) label.classList.add('active');
      else label.classList.remove('active');
    }
  } catch(e) {
    cb.checked = !cb.checked;
  }
}

// ── JSON Editor ─────────────────────────────────────────────────
const JSON_CONFIG_TEMPLATE = {
  "pages_per_url": 3,
  "max_concurrent": 5,
  "response_delay": 2,
  "pause_between_cycles": 5,
  "limit_check_interval": 30,
  "resume_touch_interval": 4,
  "batch_responses": 5,
  "min_salary": 0,
  "questionnaire_default_answer": "Готова рассказать подробнее на собеседовании.",
  "questionnaire_templates": [
    {"keyword": "ключевое слово вопроса", "answer": "ответ на этот вопрос"}
  ],
  "letter_templates": [
    {"name": "Название шаблона", "text": "Текст сопроводительного письма..."}
  ],
  "url_pool": [
    {"url": "https://hh.ru/search/vacancy?text=QA&area=1&order_by=publication_time&items_on_page=20", "pages": 40}
  ]
};

const JSON_ACCOUNT_TEMPLATE = {
  "name": "Имя (Компания)",
  "short": "Имя",
  "color": "yellow",
  "resume_hash": "ВСТАВЬТЕ_ХЭШ_РЕЗЮМЕ",
  "letter": "",
  "apply_tests": false,
  "urls": [],
  "cookies": {
    "hhtoken": "",
    "_xsrf": "",
    "hhul": "",
    "crypted_id": ""
  }
};

function jsonConfigTemplate() {
  const ta = document.getElementById('json-config-ta');
  const st = document.getElementById('json-config-st');
  ta.value = JSON.stringify(JSON_CONFIG_TEMPLATE, null, 2);
  st.textContent = 'Шаблон загружен — отредактируйте и сохраните';
  st.style.color = 'var(--cyan)';
}

function jsonAccountsTemplate() {
  const ta = document.getElementById('json-accounts-ta');
  const st = document.getElementById('json-accounts-st');
  // Если уже есть данные — добавляем новый аккаунт в конец массива
  let arr = [];
  try { arr = JSON.parse(ta.value); if (!Array.isArray(arr)) arr = []; } catch(e) {}
  arr.push(JSON.parse(JSON.stringify(JSON_ACCOUNT_TEMPLATE)));
  ta.value = JSON.stringify(arr, null, 2);
  st.textContent = arr.length > 1
    ? `Добавлен шаблон аккаунта (всего ${arr.length})`
    : 'Шаблон загружен — заполните данные и сохраните';
  st.style.color = 'var(--cyan)';
}
async function jsonConfigLoad(btn) {
  btn.disabled = true;
  try {
    const res = await fetch('/api/raw/config');
    const data = await res.json();
    document.getElementById('json-config-ta').value = JSON.stringify(data, null, 2);
    document.getElementById('json-config-st').textContent = 'Загружено';
    document.getElementById('json-config-st').style.color = 'var(--primary)';
  } catch(e) {
    document.getElementById('json-config-st').textContent = '' + e;
    document.getElementById('json-config-st').style.color = 'var(--red)';
  }
  btn.disabled = false;
}

async function jsonConfigSave(btn) {
  const ta = document.getElementById('json-config-ta');
  const st = document.getElementById('json-config-st');
  let parsed;
  try { parsed = JSON.parse(ta.value); }
  catch(e) { st.textContent = 'Невалидный JSON:' + e.message; st.style.color = 'var(--red)'; return; }
  btn.disabled = true;
  try {
    const res = await fetch('/api/raw/config', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify(parsed)
    });
    const data = await res.json();
    if (data.ok) { st.textContent = 'Сохранено'; st.style.color = 'var(--primary)'; }
    else { st.textContent = '' + (data.error || 'Ошибка'); st.style.color = 'var(--red)'; }
  } catch(e) { st.textContent = '' + e; st.style.color = 'var(--red)'; }
  btn.disabled = false;
}

async function jsonAccountsLoad(btn) {
  btn.disabled = true;
  try {
    const res = await fetch('/api/raw/accounts');
    const data = await res.json();
    document.getElementById('json-accounts-ta').value = JSON.stringify(data, null, 2);
    document.getElementById('json-accounts-st').textContent = 'Загружено';
    document.getElementById('json-accounts-st').style.color = 'var(--primary)';
  } catch(e) {
    document.getElementById('json-accounts-st').textContent = '' + e;
    document.getElementById('json-accounts-st').style.color = 'var(--red)';
  }
  btn.disabled = false;
}

async function jsonAccountsSave(btn) {
  const ta = document.getElementById('json-accounts-ta');
  const st = document.getElementById('json-accounts-st');
  let parsed;
  try { parsed = JSON.parse(ta.value); }
  catch(e) { st.textContent = 'Невалидный JSON:' + e.message; st.style.color = 'var(--red)'; return; }
  if (!Array.isArray(parsed)) {
    st.textContent = 'Ожидается массив аккаунтов'; st.style.color = 'var(--red)'; return;
  }
  btn.disabled = true;
  try {
    const res = await fetch('/api/raw/accounts', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify(parsed)
    });
    const data = await res.json();
    if (data.ok) { st.textContent = `Сохранено (${data.count} аккаунтов)`; st.style.color = 'var(--primary)'; }
    else { st.textContent = '' + (data.error || 'Ошибка'); st.style.color = 'var(--red)'; }
  } catch(e) { st.textContent = '' + e; st.style.color = 'var(--red)'; }
  btn.disabled = false;
}

// Update header resume stats
function updateHeaderResumeStats(snap) {
  let totalViewsNew = 0, totalInvNew = 0, totalShows = 0;
  (snap.accounts || []).forEach(a => {
    totalViewsNew += a.resume_views_new || 0;
    totalInvNew += a.resume_invitations_new || 0;
    totalShows += a.resume_shows_7d || 0;
  });
  const hdrEl = document.getElementById('hdr-resume-stats');
  if (hdrEl) {
    hdrEl.style.display = (totalViewsNew > 0 || totalInvNew > 0 || totalShows > 0) ? '' : 'none';
    setText('hdr-views-new', totalViewsNew);
    setText('hdr-inv-new', totalInvNew);
    setText('hdr-shows', totalShows);
  }
}

// ── Questionnaire templates ──────────────────────────────────
function qRenderTemplates(templates) {
  const list = document.getElementById('q-templates-list');
  list.innerHTML = '';
  (templates || []).forEach((tmpl, i) => {
    const row = document.createElement('div');
    row.className = 'q-template-row';
    row.dataset.idx = i;
    row.innerHTML = `
      <button class="q-del" onclick="qDelTemplate(${i})" title="Удалить">×</button>
      <label>${t('q_keywords_label')} — по ним ищется совпадение с текстом вопроса</label>
      <input type="text" class="q-keywords-input" placeholder="${t('q_keywords_ph')}"
        value="${esc((tmpl.keywords || []).join(', '))}">
      <label>${t('q_answer_label')}</label>
      <textarea class="q-answer-input" rows="3" placeholder="Ваш ответ...">${esc(tmpl.answer || '')}</textarea>
    `;
    list.appendChild(row);
  });
}

// ── Questionnaire presets ─────────────────────────────────────
const Q_PRESETS = {
  universal: {
    default: 'Готова рассказать подробнее на собеседовании.',
    templates: [
      { keywords: ['командировк'],
        answer: 'Да, готова к командировкам.' },
      { keywords: ['переработк', 'сверхурочн', 'задерж'],
        answer: 'Да, готова к переработкам при необходимости.' },
      { keywords: ['ненормированн', 'гибкий график', 'нестандартн'],
        answer: 'Да, рассматриваю.' },
      { keywords: ['вахт'],
        answer: 'Нет, вахтовый метод не рассматриваю.' },
      { keywords: ['ночн смен', 'сменн', 'посменн', '2/2', '3/3'],
        answer: 'Да, рассматриваю сменный график.' },
      { keywords: ['выходн', 'праздник', 'суббот', 'воскресен'],
        answer: 'Да, готова работать в выходные при необходимости.' },
      { keywords: ['почему', 'привлекает', 'хотите работать у нас', 'хотите работать в'],
        answer: 'Меня привлекает стабильная компания, интересные задачи и возможность профессионального роста.' },
      { keywords: ['расскажите о себе', 'опишите себя', 'кто вы'],
        answer: 'Ответственный и целеустремлённый специалист с опытом работы. Быстро обучаюсь, умею работать в команде и самостоятельно. Готова к новым задачам и развитию.' },
      { keywords: ['опыт работ', 'стаж', 'сколько лет'],
        answer: 'Имею опыт работы в данной сфере более 2 лет. Готова рассказать подробнее на собеседовании.' },
      { keywords: ['сильн сторон', 'достоинств', 'преимущест'],
        answer: 'Ответственность, стрессоустойчивость, коммуникабельность и быстрое обучение.' },
      { keywords: ['почему уволил', 'предыдущ', 'прошл место'],
        answer: 'В поиске новых возможностей для профессионального развития.' },
      { keywords: ['зарплат', 'оклад', 'доход', 'вознагражд', 'ожидани', 'желаем'],
        answer: 'От 70 000 рублей. Готова обсудить на собеседовании.' },
      { keywords: ['когда', 'приступить', 'выйти на работу', 'дата выхода', 'готов'],
        answer: 'Готова приступить в течение 2 недель.' },
      { keywords: ['формат работ', 'офис', 'удалённ', 'удален', 'remote', 'гибрид'],
        answer: 'Рассматриваю гибридный и удалённый формат.' },
      { keywords: ['город', 'регион', 'переезд', 'релокац'],
        answer: 'Готова рассмотреть предложение.' },
      { keywords: ['английск', 'english', 'иностранн язык'],
        answer: 'Базовый уровень.' },
      { keywords: ['автомобил', 'машин', 'водительск', 'права кат'],
        answer: 'Нет.' },
      { keywords: ['образован', 'диплом', 'вуз', 'институт', 'университет'],
        answer: 'Высшее.' },
      { keywords: ['обучени', 'курс', 'тренинг'],
        answer: 'Да, готова к обучению и развитию.' },
    ]
  },
  sales: {
    default: 'Готова рассказать подробнее на собеседовании.',
    templates: [
      { keywords: ['командировк'],
        answer: 'Да, готова.' },
      { keywords: ['переработк', 'сверхурочн'],
        answer: 'Да, при необходимости.' },
      { keywords: ['вахт'],
        answer: 'Нет.' },
      { keywords: ['почему', 'привлекает', 'хотите'],
        answer: 'Интересует возможность работать с клиентами, выполнять план и расти в доходе.' },
      { keywords: ['опыт продаж', 'продавал', 'менеджер по продажам'],
        answer: 'Да, есть опыт активных продаж. Умею работать с возражениями и выполнять KPI.' },
      { keywords: ['опыт работ с клиент', 'клиентск'],
        answer: 'Да, есть опыт работы с клиентами: входящие и исходящие звонки, консультации, оформление заказов.' },
      { keywords: ['колл-центр', 'кол центр', 'call center', 'оператор'],
        answer: 'Да, есть опыт работы оператором колл-центра.' },
      { keywords: ['crm', 'срм', '1с', '1c'],
        answer: 'Да, работала с CRM-системами и 1С.' },
      { keywords: ['план', 'kpi', 'ки пи ай', 'выполнени'],
        answer: 'Да, умею работать по плановым показателям и выполняю их.' },
      { keywords: ['стресс', 'конфликт', 'сложн клиент'],
        answer: 'Стрессоустойчива, умею работать со сложными клиентами и находить компромисс.' },
      { keywords: ['зарплат', 'оклад', 'доход', 'ожидани'],
        answer: 'Оклад от 50 000 + % от продаж.' },
      { keywords: ['когда', 'приступить', 'выйти'],
        answer: 'Готова приступить в течение недели.' },
      { keywords: ['формат', 'офис', 'удалённ'],
        answer: 'Рассматриваю офисный и гибридный форматы.' },
      { keywords: ['английск', 'english'],
        answer: 'Базовый.' },
      { keywords: ['обучени', 'тренинг'],
        answer: 'Да, готова к обучению.' },
    ]
  },
  office: {
    default: 'Готова рассказать подробнее на собеседовании.',
    templates: [
      { keywords: ['командировк'],
        answer: 'Нет, командировки не рассматриваю.' },
      { keywords: ['переработк', 'сверхурочн'],
        answer: 'В исключительных случаях готова.' },
      { keywords: ['вахт'],
        answer: 'Нет.' },
      { keywords: ['почему', 'привлекает', 'хотите'],
        answer: 'Привлекает стабильность, официальное оформление и чёткий функционал.' },
      { keywords: ['опыт работ', 'стаж'],
        answer: 'Есть опыт офисной работы: документооборот, работа с оргтехникой, MS Office, координация задач.' },
      { keywords: ['1с', '1c'],
        answer: 'Да, базовый опыт работы в 1С.' },
      { keywords: ['excel', 'word', 'office', 'офис'],
        answer: 'Уверенный пользователь MS Office: Word, Excel, Outlook.' },
      { keywords: ['оргтехник', 'принтер', 'скан'],
        answer: 'Да, умею работать с оргтехникой.' },
      { keywords: ['документооборот', 'делопроизводств'],
        answer: 'Да, есть опыт ведения документооборота и делопроизводства.' },
      { keywords: ['зарплат', 'оклад', 'доход', 'ожидани'],
        answer: 'От 60 000 рублей.' },
      { keywords: ['когда', 'приступить', 'выйти'],
        answer: 'Готова приступить в течение 2 недель.' },
      { keywords: ['формат', 'офис', 'удалённ'],
        answer: 'Предпочтительно офисный или гибридный формат.' },
      { keywords: ['английск', 'english'],
        answer: 'Базовый.' },
      { keywords: ['автомобил', 'права'],
        answer: 'Нет.' },
      { keywords: ['образован'],
        answer: 'Высшее.' },
    ]
  },
  remote: {
    default: 'Готова рассказать подробнее на собеседовании.',
    templates: [
      { keywords: ['командировк'],
        answer: 'Нет, предпочитаю удалённый формат.' },
      { keywords: ['переработк', 'сверхурочн'],
        answer: 'Да, при необходимости готова.' },
      { keywords: ['вахт'],
        answer: 'Нет.' },
      { keywords: ['почему', 'привлекает', 'хотите'],
        answer: 'Привлекает удалённый формат, интересные задачи и возможность развиваться в IT-сфере.' },
      { keywords: ['опыт работ', 'стаж'],
        answer: 'Есть опыт удалённой работы. Умею самостоятельно организовывать рабочий процесс.' },
      { keywords: ['интернет', 'оборудован', 'компьютер', 'пк'],
        answer: 'Да, есть стабильный интернет и необходимое оборудование.' },
      { keywords: ['часовой пояс', 'мск', 'москов'],
        answer: 'Работаю в часовом поясе МСК+0.' },
      { keywords: ['english', 'английск'],
        answer: 'Pre-Intermediate / Базовый.' },
      { keywords: ['python', 'java', 'sql', 'программирован'],
        answer: 'Да, есть базовые знания. Готова развиваться.' },
      { keywords: ['google', 'таблиц', 'notion', 'jira', 'confluence', 'trello'],
        answer: 'Да, работала с Google-сервисами, Notion, Trello.' },
      { keywords: ['зарплат', 'оклад', 'доход', 'ожидани'],
        answer: 'От 70 000 рублей.' },
      { keywords: ['когда', 'приступить', 'выйти'],
        answer: 'Готова приступить в течение недели.' },
      { keywords: ['формат', 'удалённ', 'гибрид'],
        answer: 'Предпочтительно полностью удалённый или гибридный.' },
      { keywords: ['обучени', 'курс'],
        answer: 'Да, готова к обучению за счёт компании.' },
    ]
  }
};

function qLoadPreset(name) {
  const preset = Q_PRESETS[name];
  if (!preset) return;
  if (!confirm(`Загрузить пресет "${name}"? Текущие шаблоны будут заменены.`)) return;
  qRenderTemplates(preset.templates);
  const defEl = document.getElementById('q-default-answer');
  if (defEl) defEl.value = preset.default;
  const st = document.getElementById('q-status');
  st.textContent = `Пресет загружен (${preset.templates.length} шаблонов). Отредактируй и нажми «Сохранить».`;
  st.style.color = 'var(--yellow)';
  setTimeout(() => { st.textContent = ''; st.style.color = ''; }, 6000);
  document.getElementById('q-templates-list')?.scrollIntoView({behavior:'smooth'});
}

function qAddTemplate() {
  const templates = qReadTemplates();
  templates.push({keywords: [], answer: ''});
  qRenderTemplates(templates);
  // Scroll to new row
  document.getElementById('q-templates-list').lastElementChild?.scrollIntoView({behavior:'smooth'});
}

function qDelTemplate(idx) {
  const templates = qReadTemplates();
  templates.splice(idx, 1);
  qRenderTemplates(templates);
}

function qReadTemplates() {
  const rows = document.querySelectorAll('#q-templates-list .q-template-row');
  const result = [];
  rows.forEach(row => {
    const kw = row.querySelector('.q-keywords-input')?.value || '';
    const ans = row.querySelector('.q-answer-input')?.value || '';
    result.push({
      keywords: kw.split(',').map(s => s.trim()).filter(Boolean),
      answer: ans
    });
  });
  return result;
}

function qSave() {
  const templates = qReadTemplates();
  const defaultAnswer = document.getElementById('q-default-answer')?.value || '';
  sendCmd({type: 'set_questionnaire', templates, default_answer: defaultAnswer});
  const st = document.getElementById('q-status');
  st.textContent = `Сохранено ${templates.length} шаблонов`;
  setTimeout(() => { st.textContent = ''; }, 3000);
}

function qSyncFromSnapshot(snap) {
  if (!snap || !snap.config) return;
  const templates = snap.config.questionnaire_templates || [];
  const defaultAns = snap.config.questionnaire_default_answer || '';
  qRenderTemplates(templates);
  const el = document.getElementById('q-default-answer');
  if (el && !el._userEdited) el.value = defaultAns;
}

// Mark as user-edited so we don't override on next snapshot
document.addEventListener('DOMContentLoaded', () => {
  const el = document.getElementById('q-default-answer');
  if (el) el.addEventListener('input', () => { el._userEdited = true; });
});

// ── Dark confirm dialog ──────────────────────────────────────────
function showConfirm(msg, okLabel = null, cancelLabel = null) {
  if (okLabel === null) okLabel = t('confirm_delete');
  if (cancelLabel === null) cancelLabel = t('confirm_cancel');
  return new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.className = 'confirm-overlay';
    overlay.innerHTML = `
      <div class="confirm-box">
        <p>${msg}</p>
        <div class="confirm-btns">
          <button class="confirm-cancel">${cancelLabel}</button>
          <button class="confirm-ok">${okLabel}</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector('.confirm-ok').onclick = () => { document.body.removeChild(overlay); resolve(true); };
    overlay.querySelector('.confirm-cancel').onclick = () => { document.body.removeChild(overlay); resolve(false); };
    overlay.onclick = (e) => { if (e.target === overlay) { document.body.removeChild(overlay); resolve(false); } };
  });
}

// ── Compact card mode ──────────────────────────────────────────
function toggleCompact(idx) {
  if (State.compactCards.has(idx)) State.compactCards.delete(idx);
  else State.compactCards.add(idx);
  const card = document.getElementById('card-' + idx);
  if (!card) return;
  const btn = card.querySelector('.compact-btn');
  if (State.compactCards.has(idx)) {
    card.classList.add('compact');
    if (btn) { btn.textContent = ''; btn.title = 'Развернуть карточку'; }
  } else {
    card.classList.remove('compact');
    if (btn) { btn.textContent = ''; btn.title = 'Свернуть карточку'; }
  }
}

// ── CSV Export ──────────────────────────────────────────────────
function exportCSV(headers, rows, filename) {
  const lines = [
    headers.map(h => '"' + h.replace(/"/g, '""') + '"').join(','),
    ...rows.map(r => r.map(v => '"' + String(v ?? '').replace(/"/g, '""') + '"').join(','))
  ];
  const blob = new Blob(['\uFEFF' + lines.join('\n')], {type: 'text/csv;charset=utf-8'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}

function exportAppliedCSV() {
  if (!AppliedState.all.length) return;
  const headers = ['Дата', 'Аккаунт', 'ID вакансии', 'Название', 'Компания', 'Зарплата от', 'Зарплата до', 'Ссылка'];
  const rows = AppliedState.all.map(i => [
    i.at ? new Date(i.at).toLocaleString('ru-RU') : '',
    i.account || '',
    i.vacancy_id || '',
    i.title || '',
    i.company || '',
    i.salary_from || '',
    i.salary_to || '',
    i.url || `https://hh.ru/vacancy/${i.vacancy_id}`,
  ]);
  exportCSV(headers, rows, `hh_applied_${new Date().toISOString().slice(0,10)}.csv`);
}

function exportDbCSV() {
  if (!DBState.all.length) return;
  const STATUS_LABELS = {sent: 'Откликнулись', test_passed: 'Тест пройден', test_pending: 'Не пройден'};
  const headers = ['Статус', 'Дата', 'ID вакансии', 'Название', 'Компания', 'Аккаунты', 'Ссылка'];
  const rows = DBState.all.map(i => [
    STATUS_LABELS[i.status] || i.status,
    i.at ? new Date(i.at).toLocaleString('ru-RU') : '',
    i.vacancy_id || '',
    i.title || '',
    i.company || '',
    (i.applied_by || []).join('; '),
    `https://hh.ru/vacancy/${i.vacancy_id}`,
  ]);
  exportCSV(headers, rows, `hh_db_${new Date().toISOString().slice(0,10)}.csv`);
}

// ── Keyboard shortcuts ─────────────────────────────────────────
const TAB_KEYS = {'1':'apply','2':'log','3':'applied','4':'tests','5':'db','6':'hh','7':'views','8':'apply','9':'settings'};

document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key in TAB_KEYS) {
    const tabEl = document.querySelector(`.tab[data-tab="${TAB_KEYS[e.key]}"]`);
    if (tabEl) tabEl.click();
    return;
  }
  if (e.key === 'p' || e.key === 'P') { sendCmd({type: 'pause_toggle'}); return; }
  if (e.key === '?' || e.key === '/') { toggleShortcutsHelp(); return; }
  if (e.key === 'Escape') { closeShortcutsHelp(); }
});

function toggleShortcutsHelp() {
  if (document.getElementById('shortcuts-overlay')) { closeShortcutsHelp(); return; }
  const el = document.createElement('div');
  el.id = 'shortcuts-overlay';
  el.className = 'shortcuts-overlay';
  el.innerHTML = `
    <div class="shortcuts-box">
      <h3>${t('shortcuts_title')}</h3>
      <table>
        <tr><td>1–9</td><td>${t('shortcuts_tabs')}</td></tr>
        <tr><td>P</td><td>${t('shortcuts_pause')}</td></tr>
        <tr><td>? / /</td><td>${t('shortcuts_help')}</td></tr>
        <tr><td>Esc</td><td>${t('shortcuts_esc')}</td></tr>
      </table>
      <div style="margin-top:14px;text-align:right">
        <button class="confirm-cancel" onclick="closeShortcutsHelp()">${t('btn_close')}</button>
      </div>
    </div>`;
  el.onclick = e => { if (e.target === el) closeShortcutsHelp(); };
  document.body.appendChild(el);
}
function closeShortcutsHelp() {
  const el = document.getElementById('shortcuts-overlay');
  if (el) el.remove();
}

// ── Init ──────────────────────────────────────────────────────
buildSettings();
if (authCompleteLocal()) markAuthComplete();
connect();
// Set default system prompt for LLM if not yet configured
const spEl = document.getElementById('llm-system-prompt');
if (spEl && !spEl.value) spEl.value = 'Ты помощник соискателя работы. Отвечай вежливо и кратко (2-4 предложения) на сообщения от HR и работодателей. Пиши от первого лица, женский род. Соглашайся на предложенное время собеседования или уточни детали.';
document.getElementById('lang-btn').textContent = lang.toUpperCase();
// Restore last active tab from localStorage
try {
  const savedTab = localStorage.getItem('hh-tab');
  let _clicked = false;
  if (savedTab && !(authCompleteLocal() && savedTab === 'auth')) {
    const tabEl = document.querySelector(`.tab[data-tab="${savedTab}"]`);
    if (tabEl) { tabEl.click(); _clicked = true; }
  }
  // Первый заход / устаревшая вкладка → открыть «Кампании» (и подтянуть библиотеку)
  if (!_clicked) {
    const apTab = document.querySelector('.tab[data-tab="apply"]');
    if (apTab) apTab.click();
  }
} catch(e) {}
// Request browser notification permission
if ('Notification' in window && Notification.permission === 'default') {
  setTimeout(() => Notification.requestPermission(), 3000);
}

// Auto-load JSON editors on first open
document.getElementById('json-config-details').addEventListener('toggle', function() {
  if (this.open && !document.getElementById('json-config-ta').value.trim())
    jsonConfigLoad(this.querySelector('button'));
});
document.getElementById('json-accounts-details').addEventListener('toggle', function() {
  if (this.open && !document.getElementById('json-accounts-ta').value.trim())
    jsonAccountsLoad(this.querySelector('button'));
});

// ── Campaign Configurator ─────────────────────────────────────────────
let currentCampaignIdx = null;
let currentCampaignIsTemp = true;  // временная сессия (true) или постоянный аккаунт (false)

// Подсветить активную кнопку сегмента по значению data-val
function _segSetActive(segId, val) {
  const seg = document.getElementById(segId);
  if (!seg) return;
  seg.querySelectorAll('button').forEach(b => {
    b.classList.toggle('active', b.dataset.val === val);
  });
}

function setEmployment(type, btn) {
  document.getElementById('campaign-employment').value = type;
  if (btn) {
    btn.parentElement.querySelectorAll('button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  } else {
    _segSetActive('campaign-employment-seg', type);
  }
}

function setGender(type, btn) {
  document.getElementById('campaign-gender').value = type;
  if (btn) {
    btn.parentElement.querySelectorAll('button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  } else {
    _segSetActive('campaign-gender-seg', type);
  }
}

// Показывать ошибку «обязательное поле» только когда запрос пуст
function campaignValidateQuery() {
  const inp = document.getElementById('campaign-query');
  const err = document.getElementById('campaign-query-error');
  const ok = document.getElementById('campaign-query-ok');
  if (!inp) return true;
  const filled = !!inp.value.trim();
  if (err) err.style.display = filled ? 'none' : '';
  if (ok) ok.style.display = filled ? '' : 'none';
  inp.classList.toggle('input-error', !filled);
  return filled;
}

// Справочник отраслей HH — грузим один раз, потом из кэша
let _industriesCache = null;
async function ensureIndustriesLoaded(selected) {
  const sel = document.getElementById('campaign-industry');
  if (!sel) return;
  if (!_industriesCache) {
    try {
      const r = await fetch('/api/dict/industries');
      const d = await r.json();
      _industriesCache = d.industries || [];
    } catch (e) { _industriesCache = []; }
  }
  sel.innerHTML = '<option value="">Любая отрасль</option>' +
    _industriesCache.map(it => `<option value="${esc(it.id)}">${esc(it.name)}</option>`).join('');
  if (selected) sel.value = selected;
}

// ── PDF-резюме (доп. контекст для AI) ───────────────────────────
function campaignSetPdfStatus(name, extra) {
  const st = document.getElementById('campaign-pdf-status');
  const rm = document.getElementById('campaign-pdf-remove');
  if (st) {
    st.textContent = name ? `Загружено: ${name}${extra ? ' · ' + extra : ''}` : 'PDF не загружен';
    st.style.color = name ? 'var(--primary)' : 'var(--dim)';
  }
  if (rm) rm.style.display = name ? '' : 'none';
}

async function campaignUploadPdf(input) {
  const file = input.files && input.files[0];
  if (!file) return;
  const st = document.getElementById('campaign-pdf-status');
  if (st) { st.textContent = 'Парсю PDF…'; st.style.color = 'var(--dim)'; }
  const fd = new FormData();
  fd.append('file', file);
  try {
    const res = await fetch(`/api/account/${currentCampaignIdx}/resume_pdf`, { method: 'POST', body: fd });
    const data = await res.json();
    if (data.ok) {
      campaignSetPdfStatus(data.name, `${data.length} симв.`);
    } else {
      if (st) { st.textContent = data.error || 'Не удалось загрузить'; st.style.color = 'var(--yellow)'; }
      input.value = '';
    }
  } catch (e) {
    if (st) { st.textContent = 'Ошибка: ' + e; st.style.color = 'var(--red)'; }
  }
}

async function campaignRemovePdf() {
  try {
    await fetch(`/api/account/${currentCampaignIdx}/resume_pdf`, { method: 'DELETE' });
  } catch (e) {}
  const inp = document.getElementById('campaign-pdf');
  if (inp) inp.value = '';
  campaignSetPdfStatus('');
}

function showCampaignConfigurator(idx) {
  _campaignConfiguratorDismissed = false;
  const acc = State.lastSnapshot.accounts.find(a => a.idx === idx);
  if (!acc) return;
  currentCampaignIdx = idx;
  
  const oldWizard = document.getElementById('onboarding-wizard');
  if (oldWizard) oldWizard.style.display = 'none';
  
  
  if (State.currentTab !== 'apply') switchTab('apply');
  const conf = document.getElementById('campaign-configurator');
  if (conf) conf.classList.add('active');
  const backdrop = document.getElementById('modal-backdrop');
  if (backdrop) backdrop.style.display = 'block';
  // Scroll to configurator
  setTimeout(() => {
    const conf = document.getElementById('campaign-configurator');
    if (conf) conf.scrollIntoView({behavior: 'smooth'});
  }, 100);

  
  fillCampaignForm(acc);
}

// Наполнить форму конфигуратора данными аккаунта (резюме, PDF, все поля).
// Вызывается и при открытии по кнопке, и при заходе на вкладку «Кампании».
function _fillResumeSelects(resumes, acc) {
  const sel = document.getElementById('campaign-resume');
  if (!sel) return;
  sel.innerHTML = '';
  resumes.forEach(r => {
    const opt = document.createElement('option');
    opt.value = r.hash; opt.textContent = resumeTitle(r);
    sel.appendChild(opt);
  });
  if (resumes.length) sel.value = acc.resume_hash || resumes[0].hash;

  const sel2 = document.getElementById('campaign-resume-2');
  if (sel2) {
    sel2.innerHTML = '<option value="">— нет (одно резюме) —</option>' +
      resumes.map(r => `<option value="${esc(r.hash)}">${esc(resumeTitle(r))}</option>`).join('');
    sel2.value = acc.resume_hash_2 || '';
  }
}

let _campaignResumesLoading = false;
async function _loadResumesLive(acc) {
  if (_campaignResumesLoading) return;
  _campaignResumesLoading = true;
  const sel = document.getElementById('campaign-resume');
  if (sel) sel.innerHTML = '<option value="">Загрузка резюме…</option>';
  try {
    const r = await fetch(`/api/account/${acc.idx}/all_resumes`);
    const data = await r.json();
    const resumes = data.resumes || [];
    if (resumes.length) {
      acc.all_resumes = resumes;  // закэшировать в текущем снапшоте
      _fillResumeSelects(resumes, acc);
    } else if (sel) {
      sel.innerHTML = '<option value="">Резюме не найдено — проверь куки</option>';
    }
  } catch (e) {
    if (sel) sel.innerHTML = '<option value="">Ошибка загрузки резюме</option>';
  } finally {
    _campaignResumesLoading = false;
  }
}

// Дозаполнить форму кампании из снапшота, если резюме ещё не подгрузились
// (гонка: снапшот приходит ПОСЛЕ первого рендера вкладки после рестарта/refresh).
function ensureCampaignResumesFilled(snap) {
  if (_campaignResumesLoading) return;
  const sel = document.getElementById('campaign-resume');
  if (!sel) return;
  const hasReal = Array.from(sel.options).some(o => o.value);
  if (hasReal) return;  // уже заполнено — не трогаем, чтобы не затереть ввод
  const accs = (snap && snap.accounts) || [];
  if (!accs.length) return;
  const valid = currentCampaignIdx != null && accs.some(a => a.idx === currentCampaignIdx);
  const acc = valid ? accs.find(a => a.idx === currentCampaignIdx) : accs[0];
  if (acc) fillCampaignForm(acc);
}

function fillCampaignForm(acc) {
  if (!acc) return;
  currentCampaignIdx = acc.idx;
  // Populate resumes (основное + дополнительное)
  const resumes = acc.all_resumes || [];
  const sel = document.getElementById('campaign-resume');
  if (!sel) return;
  _fillResumeSelects(resumes, acc);
  // Если в снапшоте резюме нет — подтянуть вживую с HH (fallback)
  if (!resumes.length) _loadResumesLive(acc);

  // Состояние загруженного PDF-резюме
  campaignSetPdfStatus(acc.resume_pdf_name || '');
  const pdfInput = document.getElementById('campaign-pdf');
  if (pdfInput) pdfInput.value = '';

  // Pre-fill всех полей кампании из снапшота
  const setVal = (id, v) => { const el = document.getElementById(id); if (el && v !== undefined && v !== null) el.value = v; };
  const setChk = (id, v) => { const el = document.getElementById(id); if (el) el.checked = !!v; };
  setVal('campaign-query', acc.search_query);
  campaignValidateQuery();  // скрыть/показать ошибку «обязательное поле» по факту
  setVal('campaign-region', acc.region);
  setVal('campaign-salary', acc.salary_from);
  setVal('campaign-exp', acc.experience);
  setVal('campaign-daily-min', acc.daily_limit);
  setVal('campaign-daily-max', acc.daily_limit_max);
  setVal('campaign-total', acc.total_limit);
  ensureIndustriesLoaded(acc.industry || '');  // заполнить справочник отраслей + выбрать
  setVal('campaign-schedule', acc.schedule);
  setVal('campaign-employment', acc.employment);
  setVal('campaign-stopwords', acc.stop_words);
  setVal('campaign-gender', acc.gender);
  // Подсветить активные кнопки сегментов под текущие значения
  _segSetActive('campaign-employment-seg', acc.employment || 'any');
  _segSetActive('campaign-gender-seg', acc.gender || 'none');
  setVal('campaign-phone', acc.phone);
  setVal('campaign-tg', acc.tg);
  setVal('campaign-batch', acc.batch_responses);
  setVal('campaign-delay', acc.response_delay);
  setChk('campaign-remote', acc.remote_only);
  setChk('campaign-24-7', acc.limit_24_7);
  setChk('campaign-salary-only', acc.salary_only);
  setChk('campaign-accredited', acc.accredited_it);
  // Эти три по умолчанию ВКЛ (как в разметке): если в снапшоте значения нет —
  // оставляем включёнными, а не сбрасываем. Выкл только при явном false.
  setChk('campaign-strict-match', acc.strict_title_match !== false);
  setChk('campaign-ai-letter', acc.ai_cover_letter !== false);
  setChk('campaign-ai-answer', acc.ai_answers !== false);
  setChk('campaign-skip-inconsistent', acc.skip_inconsistent);
  // Запомнить тип кампании для роутинга сохранения
  currentCampaignIsTemp = (acc.is_temp !== false);

  // Состояние запуска кампании (armed) и сброс превью
  campaignSetArmedButtons(!!acc.armed);
  const actSt = document.getElementById('campaign-action-status');
  if (actSt) {
    if (acc.armed) {
      const tl = acc.total_limit || 0;
      actSt.textContent = `Кампания запущена · отправлено ${acc.campaign_sent || 0}${tl ? ' из ' + tl : ''}`;
      actSt.style.color = 'var(--primary)';
    } else {
      actSt.textContent = '';
    }
  }
  const prev = document.getElementById('campaign-preview-panel');
  if (prev) prev.style.display = 'none';
}

async function saveCampaignConfig(opts) {
  opts = opts || {};  // opts.silent — сохранить без тоста и БЕЗ закрытия (для предпросмотра)
  if (currentCampaignIdx === null) return;
  
  const gv = id => { const el = document.getElementById(id); return el ? el.value : undefined; };
  const gc = id => { const el = document.getElementById(id); return el ? el.checked : undefined; };
  const payload = {
    resume_hash: gv('campaign-resume'),
    resume_hash_2: gv('campaign-resume-2') || '',
    search_query: gv('campaign-query'),
    region: gv('campaign-region'),
    remote_only: gc('campaign-remote'),
    salary_from: parseInt(gv('campaign-salary')) || 0,
    experience: gv('campaign-exp'),
    daily_limit: parseInt(gv('campaign-daily-min')) || 8,
    daily_limit_max: parseInt(gv('campaign-daily-max')) || 15,
    total_limit: parseInt(gv('campaign-total')) || 0,
    industry: gv('campaign-industry'),
    schedule: gv('campaign-schedule'),
    employment: gv('campaign-employment'),
    stop_words: gv('campaign-stopwords'),
    limit_24_7: gc('campaign-24-7'),
    salary_only: gc('campaign-salary-only'),
    accredited_it: gc('campaign-accredited'),
    strict_title_match: gc('campaign-strict-match'),
    ai_cover_letter: gc('campaign-ai-letter'),
    ai_answers: gc('campaign-ai-answer'),
    gender: gv('campaign-gender'),
    phone: gv('campaign-phone'),
    tg: gv('campaign-tg')
  };
  const batch = parseInt(gv('campaign-batch')); if (!isNaN(batch)) payload.batch_responses = batch;
  const delay = parseInt(gv('campaign-delay')); if (!isNaN(delay)) payload.response_delay = delay;
  const skipInc = gc('campaign-skip-inconsistent'); if (skipInc !== undefined) payload.skip_inconsistent = skipInc;

  payload.name = (gv('campaign-name') || '').trim();
  if (!payload.name) { showToast('Укажите название кампании', 'error'); return false; }
  if (!campaignValidateQuery()) { showToast('Укажите поисковый запрос', 'error'); return false; }

  // Создать новую или обновить существующую кампанию (НЕ запускает бота).
  try {
    let url, body;
    if (_editingCampaignId) {
      url = `/api/campaigns/${_editingCampaignId}`;
      body = payload;
    } else {
      url = `/api/campaigns`;
      body = { ...payload, account_idx: _currentAccountIdx() };
    }
    const res = await fetch(url, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const data = await res.json();
    if (data.ok) {
      const wasNew = !_editingCampaignId;
      // запомнить id созданной кампании → повторные сохранения/предпросмотр
      // правят ЕЁ же, а не плодят дубликаты
      if (wasNew && data.campaign && data.campaign.id) _editingCampaignId = data.campaign.id;
      if (!opts.silent) {
        showToast(wasNew ? 'Кампания создана' : 'Кампания обновлена', 'success');
        closeConfigurator();
      }
      loadCampaigns();
      return true;
    }
    showToast(data.error || 'Ошибка сохранения', 'error');
    return false;
  } catch (e) {
    console.error(e);
    showToast('Ошибка сети', 'error');
    return false;
  }
}

// ══════════════════════════════════════════════════════════════
// БИБЛИОТЕКА КАМПАНИЙ (список, сводка, запуск, отклики)
// ══════════════════════════════════════════════════════════════
let _campaignsCache = [];
let _campaignsReloading = false;  // защита от дабл-фетча в само-восстановлении
let _expandedCampaign = null;
let _editingCampaignId = null;

function _currentAccountIdx() {
  const accs = (State.lastSnapshot && State.lastSnapshot.accounts) || [];
  return accs.length ? accs[0].idx : 0;
}
function _currentAccount() {
  const accs = (State.lastSnapshot && State.lastSnapshot.accounts) || [];
  return accs[0] || null;
}

async function loadCampaigns() {
  try {
    const r = await fetch('/api/campaigns');
    const d = await r.json();
    // Затираем кэш ТОЛЬКО если ответ валидный (есть массив campaigns).
    // Иначе (401/ошибка/рестарт) — сохраняем прошлый список, чтобы кампании
    // не «исчезали» из UI при том, что на бэке они на месте.
    if (!r.ok || !Array.isArray(d.campaigns)) {
      console.warn('loadCampaigns: невалидный ответ, оставляю прошлый список', d);
      return;
    }
    _campaignsCache = d.campaigns;
    renderCampaignsSummary(d);
    renderCampaignsList();
  } catch (e) {
    console.warn('loadCampaigns network error, оставляю прошлый список', e);
  }
}

function renderCampaignsSummary(d) {
  const el = document.getElementById('campaigns-summary');
  if (!el) return;
  const card = (label, val, color) =>
    `<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:10px;padding:16px 18px">
       <div style="font-size:11px;letter-spacing:.04em;text-transform:uppercase;color:var(--dim)">${label}</div>
       <div style="font-size:30px;font-weight:800;margin-top:6px;${color ? 'color:' + color : ''}">${val}</div>
     </div>`;
  el.innerHTML = card('Всего кампаний', d.total || 0)
    + card('Активные', d.active || 0, 'var(--primary)')
    + card('Всего откликов', d.total_responses || 0);
}

function _campStatusBadge(st) {
  const m = { running: ['Активна', 'var(--green)'], stopped: ['Остановлена', 'var(--dim)'],
              finished: ['Завершена', 'var(--cyan)'], idle: ['Не запущена', 'var(--dim)'] };
  const [t, c] = m[st] || ['—', 'var(--dim)'];
  return `<span style="font-size:11px;font-weight:600;padding:2px 9px;border-radius:999px;background:var(--bg-card2);color:${c}">${t}</span>`;
}

function renderCampaignsList() {
  const el = document.getElementById('campaigns-list');
  if (!el) return;
  if (!_campaignsCache.length) {
    el.innerHTML = `<div style="color:var(--dim);font-size:13px;padding:24px;text-align:center;border:1px dashed var(--border);border-radius:10px">Пока нет кампаний. «+ Новая кампания» — создать первую.</div>`;
    return;
  }
  el.innerHTML = _campaignsCache.map(c => {
    const s = c.stats || {};
    const started = s.started_at ? new Date(s.started_at).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';
    const open = _expandedCampaign === c.id;
    return `<div class="campaign-row" style="border:1px solid var(--border);border-radius:10px;background:var(--bg-card);margin-bottom:10px;overflow:hidden">
      <div style="display:flex;align-items:center;gap:12px;padding:14px 16px;cursor:pointer" onclick="toggleCampaign('${c.id}')">
        <div style="flex:1;min-width:0">
          <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
            <span style="font-weight:700;font-size:15px">${esc(c.name || 'Без названия')}</span>
            ${_campStatusBadge(c.status)}
          </div>
          <div style="font-size:12px;color:var(--dim);margin-top:6px">Отправлено: <b style="color:var(--text-main)">${s.sent || 0}</b> &nbsp; Пропущено: <b>${s.skipped || 0}</b> &nbsp; Ошибок: <b>${s.errors || 0}</b> &nbsp; Начато: ${started}</div>
        </div>
        <div onclick="event.stopPropagation()" style="display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end">
          ${c.status === 'running'
            ? `<button class="btn-sm" onclick="campStop('${c.id}',this)">Остановить</button>`
            : `<button class="btn-sm" style="color:var(--primary);border-color:var(--primary)" onclick="campStart('${c.id}',this)">Запустить</button>`}
          <button class="btn-sm" onclick="campEdit('${c.id}')">Изменить</button>
          <button class="btn-sm" style="color:var(--red);border-color:var(--red)" onclick="campDelete('${c.id}',this)">Удалить</button>
        </div>
      </div>
      <div id="camp-apps-${c.id}" style="display:${open ? 'block' : 'none'};border-top:1px solid var(--border);padding:12px 16px"></div>
    </div>`;
  }).join('');
  if (_expandedCampaign) loadCampaignApps(_expandedCampaign);
}

function toggleCampaign(id) {
  _expandedCampaign = (_expandedCampaign === id) ? null : id;
  renderCampaignsList();
}

async function loadCampaignApps(id) {
  const box = document.getElementById('camp-apps-' + id);
  if (!box || box.dataset.loaded === id) return;
  box.innerHTML = '<div style="color:var(--dim);font-size:12px">Загрузка откликов…</div>';
  try {
    const d = await (await fetch(`/api/campaigns/${id}/applications`)).json();
    const apps = d.applications || [];
    box.dataset.loaded = id;
    if (!apps.length) { box.innerHTML = '<div style="color:var(--dim);font-size:12px">Откликов пока нет.</div>'; return; }
    const stColor = { 'Приглашение': 'var(--green)', 'Отказ': 'var(--red)', 'Отправлен': 'var(--dim)' };
    box.innerHTML = `<div style="font-size:12px;color:var(--dim);margin-bottom:8px">Откликов: ${apps.length}</div>
      <div style="max-height:340px;overflow:auto">` + apps.map(a => {
        const dt = a.at ? new Date(a.at).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' }) : '';
        return `<div style="display:flex;gap:10px;align-items:center;padding:6px 0;border-bottom:1px solid var(--border);font-size:13px">
          <a href="${esc(a.url)}" target="_blank" style="flex:1;min-width:0;color:var(--text-main);text-decoration:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis"><b>${esc(a.company || '—')}</b> · ${esc(a.title || '')}</a>
          <span style="color:${stColor[a.hh_status] || 'var(--dim)'};font-weight:600;font-size:12px;white-space:nowrap">${esc(a.hh_status || '')}</span>
          <span style="color:var(--dim);font-size:11px;width:42px;text-align:right">${dt}</span>
        </div>`;
      }).join('') + `</div>`;
  } catch (e) { box.innerHTML = '<div style="color:var(--red);font-size:12px">Ошибка загрузки откликов</div>'; }
}

async function campStart(id, btn) {
  const c = _campaignsCache.find(x => x.id === id) || {};
  const tl = c.total_limit || 0;
  const summary = `Запустить кампанию «${esc(c.name || '')}»?<br><br>Запрос: <b>${esc(c.search_query || '')}</b><br>Лимит: <b>${tl ? tl + ' откликов' : 'без лимита'}</b><br><br>Отклики уйдут реальным работодателям на hh.ru.`;
  if (!await showConfirm(summary, 'Запустить', 'Отмена')) return;
  if (btn) btn.disabled = true;
  try {
    const r = await (await fetch(`/api/campaigns/${id}/start`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ account_idx: _currentAccountIdx() })
    })).json();
    if (!r.ok) showToast(r.error || 'Не удалось запустить', 'error');
    else showToast('Кампания запущена', 'success');
  } finally { loadCampaigns(); }
}

async function campStop(id, btn) {
  if (btn) btn.disabled = true;
  try {
    const r = await (await fetch(`/api/campaigns/${id}/stop`, { method: 'POST' })).json();
    if (r && r.ok) showToast('Кампания остановлена', 'success');
    else showToast((r && r.error) || 'Не удалось остановить', 'error');
  } catch (e) { showToast('Ошибка сети', 'error'); }
  finally { loadCampaigns(); }
}

async function campDelete(id, btn) {
  if (!await showConfirm('Удалить кампанию? История откликов сохранится.', 'Удалить', 'Отмена')) return;
  if (btn) btn.disabled = true;
  try { await fetch(`/api/campaigns/${id}`, { method: 'DELETE' }); }
  finally { loadCampaigns(); }
}

function campEdit(id) {
  const c = _campaignsCache.find(x => x.id === id);
  if (c) showConfiguratorFor(c);
}
function newCampaign() { showConfiguratorFor(null); }

function closeConfigurator() {
  const cfg = document.getElementById('campaign-configurator');
  if (cfg) cfg.style.display = 'none';
  _editingCampaignId = null;
}

function showConfiguratorFor(c) {
  _editingCampaignId = c ? c.id : null;
  currentCampaignIdx = _currentAccountIdx();
  const titleEl = document.getElementById('campaign-configurator-title');
  if (titleEl) titleEl.textContent = c ? 'Изменить кампанию' : 'Новая кампания';
  fillConfigurator(c);
  const cfg = document.getElementById('campaign-configurator');
  if (cfg) { cfg.style.display = ''; cfg.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
}

// Заполнить форму из кампании (c) или дефолтами (c=null). Резюме — из текущего аккаунта.
function fillConfigurator(c) {
  c = c || {};
  const acc = _currentAccount() || {};
  const setVal = (id, v) => { const el = document.getElementById(id); if (el) el.value = (v !== undefined && v !== null) ? v : ''; };
  const setChk = (id, v) => { const el = document.getElementById(id); if (el) el.checked = !!v; };
  setVal('campaign-name', c.name);
  // резюме из аккаунта
  const resumes = acc.all_resumes || [];
  _fillResumeSelects(resumes, { resume_hash: c.resume_hash || acc.resume_hash, resume_hash_2: c.resume_hash_2 || '' });
  if (!resumes.length) _loadResumesLive(acc);
  setVal('campaign-query', c.search_query);
  campaignValidateQuery();
  setVal('campaign-region', c.region);
  setVal('campaign-salary', c.salary_from);
  setVal('campaign-exp', c.experience);
  setVal('campaign-daily-min', c.daily_limit);
  setVal('campaign-daily-max', c.daily_limit_max);
  setVal('campaign-total', c.total_limit);
  ensureIndustriesLoaded(c.industry || '');
  setVal('campaign-schedule', c.schedule);
  setVal('campaign-employment', c.employment || 'any');
  setVal('campaign-stopwords', c.stop_words);
  setVal('campaign-gender', c.gender || 'none');
  setVal('campaign-phone', c.phone);
  setVal('campaign-tg', c.tg);
  setVal('campaign-batch', c.batch_responses);
  setVal('campaign-delay', c.response_delay);
  setChk('campaign-remote', c.remote_only);
  setChk('campaign-24-7', c.limit_24_7);
  setChk('campaign-salary-only', c.salary_only);
  setChk('campaign-accredited', c.accredited_it);
  setChk('campaign-skip-inconsistent', c.skip_inconsistent);
  // три «по умолчанию вкл» (нет значения → вкл)
  setChk('campaign-strict-match', c.strict_title_match !== false);
  setChk('campaign-ai-letter', c.ai_cover_letter !== false);
  setChk('campaign-ai-answer', c.ai_answers !== false);
  _segSetActive('campaign-employment-seg', c.employment || 'any');
  _segSetActive('campaign-gender-seg', c.gender || 'none');
  campaignSetPdfStatus(acc.resume_pdf_name || '');
  const prev = document.getElementById('campaign-preview-panel');
  if (prev) prev.style.display = 'none';
}

// Аккаунт-чип и бар действий аккаунта (под списком кампаний)
function renderCampaignAccountUI(snap) {
  const acc = (snap.accounts || [])[0];
  const chip = document.getElementById('campaigns-acc-chip');
  if (chip) {
    chip.innerHTML = acc
      ? `<div style="display:flex;align-items:center;gap:8px;background:var(--bg-card);border:1px solid var(--border);border-radius:999px;padding:6px 14px;font-size:13px">
           <span style="width:8px;height:8px;border-radius:50%;background:${acc.armed ? 'var(--green)' : 'var(--dim)'}"></span>
           <span style="color:var(--dim)">Аккаунт:</span> <b>${esc(acc.name || '')}</b></div>`
      : '';
  }
  const bar = document.getElementById('campaigns-acc-bar');
  if (bar && acc) {
    const autoOn = acc.resume_touch_enabled !== false;
    bar.innerHTML = `<div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;background:var(--bg-card);border:1px solid var(--border);border-radius:10px;padding:8px 12px">
      <span style="font-size:12px;color:var(--dim);margin-right:4px">Аккаунт:</span>
      <button class="btn-sm" onclick="sendCmd({type:'account_pause', idx:${acc.idx}})" title="Пауза/возобновление аккаунта">${acc.paused ? 'Снять паузу' : 'Пауза'}</button>
      <span class="touch-toggle ${autoOn ? 'on' : 'off'}" id="acc-touch-toggle-${acc.idx}" onclick="touchToggle(${acc.idx},this)" title="Авто-подъём резюме в поиске hh каждые несколько часов (бесплатно)"><span class="tgl-dot"></span><span>Авто-подъём</span><span id="acc-touch-label-${acc.idx}">${autoOn ? 'вкл' : 'выкл'}</span></span>
      <button class="btn-sm" onclick="resumeTouchNow(${acc.idx},this)" title="Поднять резюме сейчас">Поднять</button>
      <button class="btn-sm" onclick="declineDiscards(${acc.idx},this)" title="Убрать отказы из переписок">Очистить дискарды</button>
      <button class="btn-sm" id="acc-llm-btn-${acc.idx}" onclick="llmToggleAccount(${acc.idx},this)" title="AI-ответы на сообщения HR (отправка вручную во вкладке Чаты)">AI-ответы</button>
      <button class="btn-sm" style="color:var(--primary);border-color:var(--primary)" onclick="llmRunNow(this)" title="Подготовить черновики ответов в очередь (вкладка Чаты)">Подготовить ответы</button>
    </div>`;
  }
}

// ── Предпросмотр письма (ничего не отправляет) ──────────────────
async function previewLetter(btn) {
  const panel = document.getElementById('campaign-preview-panel');
  const meta = document.getElementById('campaign-preview-meta');
  const text = document.getElementById('campaign-preview-text');
  if (panel) panel.style.display = '';
  if (currentCampaignIdx === null) {
    if (meta) meta.textContent = 'Сначала открой кампанию и дождись загрузки резюме.';
    return;
  }
  const query = document.getElementById('campaign-query')?.value || '';
  if (!query.trim()) {
    if (meta) meta.textContent = 'Укажи поисковый запрос — по нему подбирается вакансия для примера.';
    return;
  }
  if (btn) btn.disabled = true;
  if (text) text.textContent = '';
  // Индикатор ожидания (генерация AI-письма занимает ~5–15с)
  let secs = 0;
  if (meta) meta.textContent = 'Подбираю вакансию и генерирую письмо…';
  const timer = setInterval(() => {
    secs++;
    if (meta) meta.textContent = `Подбираю вакансию и генерирую письмо… ${secs}с`;
  }, 1000);
  try {
    // сначала тихо сохраним конфиг (без закрытия формы), чтобы превью использовал
    // актуальный запрос/резюме
    await saveCampaignConfig({ silent: true });
    const res = await fetch(`/api/account/${currentCampaignIdx}/letter_preview`, {method: 'POST'});
    const data = await res.json();
    clearInterval(timer);
    if (data.ok) {
      if (meta) meta.textContent = `${data.ai ? 'AI-письмо' : 'Шаблон'} · вакансия: ${data.vacancy_title || '—'}${data.company ? ' · ' + data.company : ''}`;
      if (text) text.textContent = data.letter || '(пусто)';
    } else {
      if (meta) meta.textContent = data.error || 'Не удалось сгенерировать (нет вакансий по запросу?)';
    }
  } catch (e) {
    clearInterval(timer);
    if (meta) meta.textContent = 'Ошибка сети: ' + e;
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ── Запуск кампании (с подтверждением) ──────────────────────────
async function startCampaign(btn) {
  if (currentCampaignIdx === null) return;
  const total = parseInt(document.getElementById('campaign-total')?.value) || 0;
  const resumeSel = document.getElementById('campaign-resume');
  const resumeName = resumeSel ? (resumeSel.options[resumeSel.selectedIndex]?.textContent || '') : '';
  const query = document.getElementById('campaign-query')?.value || '';
  const dmin = document.getElementById('campaign-daily-min')?.value || '?';
  const dmax = document.getElementById('campaign-daily-max')?.value || '?';
  const aiLetter = document.getElementById('campaign-ai-letter')?.checked;
  const aiAnswer = document.getElementById('campaign-ai-answer')?.checked;

  if (!query.trim()) { showToast('Укажите поисковый запрос', 'error'); return; }

  // Сводка-подтверждение
  const totalLine = total > 0
    ? `<b>${total}</b> откликов`
    : `<b style="color:var(--red)">БЕЗ ЛИМИТА</b> — бот будет слать, пока не остановишь`;
  const summary =
    `Запустить кампанию?<br><br>` +
    `Резюме: <b>${esc(resumeName)}</b><br>` +
    `Запрос: <b>${esc(query)}</b><br>` +
    `В день: <b>${esc(dmin)}–${esc(dmax)}</b><br>` +
    `Всего: ${totalLine}<br>` +
    `Письмо: <b>${aiLetter ? 'AI под вакансию' : 'шаблон'}</b> · Ответы в чате: <b>${aiAnswer ? 'AI' : 'нет'}</b><br><br>` +
    `Отклики уйдут реальным работодателям на hh.ru.`;
  if (!await showConfirm(summary)) return;

  if (btn) btn.disabled = true;
  const st = document.getElementById('campaign-action-status');
  if (st) { st.textContent = 'Сохраняю и запускаю…'; st.style.color = 'var(--dim)'; }
  const saved = await saveCampaignConfig();
  if (!saved) { if (btn) btn.disabled = false; if (st) st.textContent = ''; return; }
  try {
    const res = await fetch(`/api/account/${currentCampaignIdx}/campaign/start`, {method: 'POST'});
    const data = await res.json();
    if (data.ok) {
      showToast('Кампания запущена', 'success');
      if (st) { st.textContent = `Запущена. Цель: ${data.total_limit || '∞'} откликов.`; st.style.color = 'var(--primary)'; }
      campaignSetArmedButtons(true);
    } else {
      showToast(data.error || 'Не удалось запустить', 'error');
      if (st) { st.textContent = data.error || 'Ошибка'; st.style.color = 'var(--red)'; }
    }
  } catch (e) {
    if (st) { st.textContent = 'Ошибка сети: ' + e; st.style.color = 'var(--red)'; }
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function stopCampaign(btn) {
  if (currentCampaignIdx === null) return;
  if (btn) btn.disabled = true;
  try {
    await fetch(`/api/account/${currentCampaignIdx}/campaign/stop`, {method: 'POST'});
    showToast('Кампания остановлена', 'success');
    const st = document.getElementById('campaign-action-status');
    if (st) { st.textContent = 'Остановлено.'; st.style.color = 'var(--dim)'; }
    campaignSetArmedButtons(false);
  } catch (e) {
    showToast('Ошибка сети', 'error');
  } finally {
    if (btn) btn.disabled = false;
  }
}

function campaignSetArmedButtons(armed) {
  const startBtn = document.getElementById('campaign-start-btn');
  const stopBtn = document.getElementById('campaign-stop-btn');
  if (startBtn) startBtn.style.display = armed ? 'none' : '';
  if (stopBtn) stopBtn.style.display = armed ? '' : 'none';
}

// Остановить кампанию прямо с карточки (по idx)
async function cardStopCampaign(idx) {
  try {
    await fetch(`/api/account/${idx}/campaign/stop`, {method: 'POST'});
    showToast('Кампания остановлена', 'success');
  } catch (e) {
    showToast('Ошибка сети', 'error');
  }
}

function closeModal() {
  _campaignConfiguratorDismissed = true;
  const backdrop = document.getElementById('modal-backdrop');
  if (backdrop) backdrop.style.display = 'none';
  const conf = document.getElementById('campaign-configurator');
  if (conf) conf.classList.remove('active');
}

function updateAuthHeader(snap) {
  if (!snap || !snap.accounts) return;
  const hasAuth = hasDashboardAccess(snap) || snap.accounts.some(a => a.cookies && a.cookies.length > 10);
  const loginBtn = document.getElementById('hh-login-btn');
  const authBadge = document.getElementById('auth-status-badge');
  if (hasAuth) {
    if (loginBtn) loginBtn.style.display = 'none';
    if (authBadge) authBadge.style.display = 'flex';
  } else {
    if (loginBtn) loginBtn.style.display = '';
    if (authBadge) authBadge.style.display = 'none';
  }
  
  // Pause button
  const pb = document.getElementById('pause-btn');
  if (pb) {
    if (snap.global_pause) {
      pb.textContent = 'Запустить';
      pb.style.background = 'var(--primary)';
      pb.style.color = 'white';
    } else {
      pb.textContent = 'Пауза';
      pb.style.background = 'var(--bg-card)';
      pb.style.color = '';
    }
  }
}
