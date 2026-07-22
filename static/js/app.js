  const APP_BASE = (() => { const m = location.pathname.match(/^(.*?\/traffic)\/?/); return m ? m[1] : ''; })();
  const api = p => `${APP_BASE}${p.startsWith('/') ? p : '/' + p}`;
  const $ = id => document.getElementById(id);
  const staticUrl = p => `${APP_BASE}/static/${p.replace(/^\//, '')}`;
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register(`${APP_BASE}/sw.js`, { scope: `${APP_BASE || ''}/` }).catch(() => {});
    });
  }
  ['logoImg', 'footerLogo'].forEach(id => { const el = $(id); if (el) el.src = staticUrl('logo.svg'); });
  const brandLogo = document.querySelector('.stitch-brand-logo');
  if (brandLogo) brandLogo.src = staticUrl('logo.svg');
  const favicon = document.querySelector('link[rel="icon"]');
  if (favicon) favicon.href = staticUrl('favicon.svg');
  const appleIcon = document.querySelector('link[rel="apple-touch-icon"]');
  if (appleIcon) appleIcon.href = staticUrl('favicon.svg');
  const ogImage = document.querySelector('meta[property="og:image"]');
  if (ogImage) ogImage.content = staticUrl('og-image.png');
  const methodUrl = APP_BASE ? `${APP_BASE}/methodology` : '/methodology';
  ['methodLink', 'footerMethodLink'].forEach(id => { const el = $(id); if (el) el.href = methodUrl; });
  const trustMethod = document.querySelector('#trustLine a');
  if (trustMethod) trustMethod.href = methodUrl;

  const LINE_COLORS = {
    'kelana-jaya': '#e31837',
    'ampang-sri-petaling': '#f7941d',
    'lrt3': '#7b2d8e',
    'kajang': '#007a33',
    'putrajaya': '#f4c300',
    'kajang-putrajaya': '#00a651',
    'monorail': '#8dc63f',
    'brt-sunway': '#5c2d91',
    'ktm-komuter': '#0066b3',
    'ktm-north': '#2b6cb0',
    'ets-intercity': '#b8860b',
    'klia-rail': '#7f1734',
    'sabah-railway': '#9b6a31',
    'rapid-bus': '#e21836',
    'penang': '#00843d',
    'kuantan': '#008b8b',
    'mybas': '#0f766e',
    'lrt3': '#7b2d8e',
    'ecrl': '#003d7a',
    'rts-johor': '#c41230',
    'mrt3': '#2563eb',
    'penang-lrt': '#0f766e',
  };

  const MODE_LABEL = { rail: 'Rail', bus: 'Bus' };
  const SEVERITY_RANK = { normal: 0, unknown: 0, minor: 1, delay: 2, disruption: 3 };
  const DEFAULT_POLL_SEC = 300;
  const DEFAULT_INGEST_SEC = 900;
  const FETCH_TIMEOUT_MS = 25000;

  let REFRESH_INTERVAL = DEFAULT_POLL_SEC * 1000;
  let COUNTDOWN_SEC = DEFAULT_POLL_SEC;
  let ingestIntervalSec = DEFAULT_INGEST_SEC;

  let isRefreshing = false;
  let boardSnapshot = null;
  let boardData = null;
  let healthSnapshot = null;
  let activeFilter = 'all';
  let activeSort = 'severity';
  let placeFilter = '';
  let placeSearchTimer = null;
  let stationCatalog = [];
  let countdownTimer = null;
  let secondsLeft = COUNTDOWN_SEC;
  let loadGeneration = 0;
  let mapInstance = null;
  // GPS (Official GTFS-RT dots) is OFF by default — KTM line layer must not auto-pull EMU telemetry.
  let mapLayers = {
    reports: true,
    lrt: true,
    mrt: true,
    monorail: true,
    ktm: true,
    interchanges: true,
    buses: false,
    gps: false,
  };
  const MAP_LAYER_UI = [
    ['reports', 'mapLayerReports'],
    ['lrt', 'mapLayerLrt'],
    ['mrt', 'mapLayerMrt'],
    ['monorail', 'mapLayerMonorail'],
    ['ktm', 'mapLayerKtm'],
    ['interchanges', 'mapLayerInterchanges'],
    ['buses', 'mapLayerBuses'],
    ['gps', 'mapLayerGps'],
  ];
  let mapPollTimer = null;
  let linesReferenceById = {};
  let panelLastFocus = null;
  let maplibrePromise = null;
  let mapEventsBound = false;
  let reportMarkers = [];
  let reportMarkerCount = 0;
  let activeMapPopup = null;
  let panelTouchStartY = 0;
  let notifyEnabled = localStorage.getItem('trafficmy:notify') === '1';
  let lastLineStatus = {};
  let brandMeta = null;
  const STORAGE_KEYS = {
    tab: 'trafficmy:tab',
    filter: 'trafficmy:filter',
    sort: 'trafficmy:sort',
    place: 'trafficmy:place',
  };
  const LANG_KEY = 'trafficmy:lang';
  let uiLang = localStorage.getItem(LANG_KEY) === 'ms' ? 'ms' : 'en';

  function pickLang(en, ms) {
    return uiLang === 'ms' && ms ? ms : (en || '');
  }

  function isRushHourMYT() {
    const now = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Kuala_Lumpur' }));
    const h = now.getHours();
    return (h >= 7 && h < 10) || (h >= 17 && h < 20);
  }

  function setUiLang(lang) {
    uiLang = lang === 'ms' ? 'ms' : 'en';
    localStorage.setItem(LANG_KEY, uiLang);
    document.documentElement.lang = uiLang === 'ms' ? 'ms' : 'en';
    const btn = $('langToggle');
    if (btn) {
      btn.textContent = uiLang === 'ms' ? 'BM' : 'EN';
      btn.setAttribute('aria-pressed', uiLang === 'ms' ? 'true' : 'false');
      btn.title = uiLang === 'ms' ? 'Tukar ke English' : 'Switch to Bahasa Malaysia';
    }
    if (boardSnapshot) {
      renderBoardSummary(boardSnapshot);
      renderRiskStrip(boardSnapshot.lines || []);
      renderBoard();
      renderReports(boardSnapshot.recent_reports || []);
    }
  }

  function rushHourContext() {
    const now = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Kuala_Lumpur' }));
    const h = now.getHours();
    const m = now.getMinutes();
    const time = now.toLocaleTimeString('en-MY', { hour: 'numeric', minute: '2-digit', timeZone: 'Asia/Kuala_Lumpur' });
    let band = 'Off-peak';
    if ((h >= 7 && h < 10) || (h >= 17 && h < 20)) band = 'Rush hour';
    else if (h >= 10 && h < 17) band = 'Midday';
    return `${band} · ${time} MYT`;
  }

  function renderContextBar() {
    const el = $('contextBar');
    if (!el) return;
    const scope = pickLang('Malaysia transport only', 'Pengangkutan Malaysia sahaja');
    el.innerHTML = `<span class="stat-pill"><span>${esc(rushHourContext())}</span></span><span class="stat-pill">${esc(scope)}</span>`;
  }

  function renderRiskStrip(lines) {
    const el = $('riskStrip');
    if (!el) return;
    const favLines = (lines || []).filter(l => favoriteLineIds.has(l.id));
    if (!isRushHourMYT() || !favLines.length) {
      el.hidden = true;
      el.innerHTML = '';
      return;
    }
    const title = pickLang('My lines · rush hour', 'Laluan saya · waktu puncak');
    el.hidden = false;
    el.innerHTML = `
      <div class="play-risk-head">${esc(title)}</div>
      <div class="play-risk-chips">${favLines.slice(0, 5).map(line => {
        const tone = ['delay', 'disruption', 'minor'].includes(line.status) ? line.status : 'ok';
        const shortName = line.name.replace(/ Line$/, '').replace(/^KTM /, 'KTM ');
        return `<button type="button" class="risk-chip risk-chip--${esc(tone)}" data-line-id="${esc(line.id)}">${esc(shortName)} · ${esc(shortStatusLabel(line))}</button>`;
      }).join('')}</div>`;
  }

  function saveUiState() {
    try {
      const activeTab = document.querySelector('.main-tab.active')?.dataset.tab || 'status';
      localStorage.setItem(STORAGE_KEYS.tab, activeTab);
      localStorage.setItem(STORAGE_KEYS.filter, activeFilter || 'all');
      localStorage.setItem(STORAGE_KEYS.sort, activeSort || 'severity');
      localStorage.setItem(STORAGE_KEYS.place, placeFilter || '');
    } catch { /* ignore storage failures */ }
  }

  function restoreUiState() {
    try {
      const savedFilter = localStorage.getItem(STORAGE_KEYS.filter);
      const savedSort = localStorage.getItem(STORAGE_KEYS.sort);
      const savedPlace = localStorage.getItem(STORAGE_KEYS.place);
      if (savedFilter) activeFilter = savedFilter;
      if (savedSort) activeSort = savedSort;
      if (savedPlace) {
        const low = savedPlace.toLowerCase().trim();
        // Generic words match almost every line name and make search feel broken.
        if (!['line', 'station', 'lines', 'stations'].includes(low)) {
          placeFilter = savedPlace;
        } else {
          localStorage.removeItem(STORAGE_KEYS.place);
        }
      }
    } catch { /* ignore storage failures */ }
  }

  function glanceModeChips(lines) {
    const nets = new Set();
    (lines || []).filter(l => ['minor', 'delay', 'disruption'].includes(l.status)).forEach(l => {
      const n = getNetworkForLine(l.id);
      if (n === 'lrt') nets.add('lrt');
      if (n === 'mrt') nets.add('mrt');
      if (n === 'ktm') nets.add('ktm');
      if (n === 'monorail') nets.add('mono');
      if (n === 'bus') nets.add('bus');
    });
    const labels = { lrt: 'LRT', mrt: 'MRT', ktm: 'KTM', mono: 'Mono', bus: 'Bus' };
    return [...nets].map(k => `<span class="stitch-glance-chip stitch-glance-chip--${k}">${labels[k] || k}</span>`).join('');
  }

  function shortStatusLabel(line) {
    if (line.in_service === false) {
      if (line.service_status === 'after_service') return pickLang('Ended today', 'Tamat hari ini');
      if (line.service_status === 'before_service') return pickLang('Starts later', 'Mula nanti');
    }
    const mapEn = {
      normal: 'Quiet',
      unknown: 'Quiet',
      minor: 'Minor',
      delay: 'Delayed',
      disruption: 'Disruption',
    };
    const mapMs = {
      normal: 'Tenang',
      unknown: 'Tenang',
      minor: 'Kecil',
      delay: 'Lewat',
      disruption: 'Gangguan',
    };
    const map = uiLang === 'ms' ? mapMs : mapEn;
    return map[line.status] || line.status_label || (uiLang === 'ms' ? 'Tenang' : 'Quiet');
  }

  function cardDetail(line) {
    if (line.in_service === false && line.service_label) return line.service_label;
    const reason = (line.reason || '').trim();
    if (['minor', 'delay', 'disruption'].includes(line.status) && reason) {
      return reason.length > 72 ? `${reason.slice(0, 69)}…` : reason;
    }
    if (line.report_count > 0) {
      const when = line.last_seen_at ? reportAgeLabel(line.last_seen_at) : '';
      const n = line.report_count;
      const base = n === 1
        ? pickLang('1 report', '1 laporan')
        : pickLang(`${n} reports`, `${n} laporan`);
      return when ? `${base} · ${when}` : base;
    }
    if (['normal', 'unknown'].includes(line.status)) {
      return pickLang('No recent rider signal', 'Tiada isyarat penumpang terkini');
    }
    if (line.commuter_note) return pickLang(line.commuter_note, line.commuter_note_ms);
    return '';
  }

  function facilityChip(line) {
    if (!line.facility_alert) return '';
    const label = pickLang('Lift/escalator', 'Lift/eskalator');
    return `<span class="play-facility-chip" title="${esc(label)}">${esc(label)}</span>`;
  }

  function statusFace(status) {
    const map = {
      normal: { emoji: '✓', cls: 'ok' },
      unknown: { emoji: '○', cls: 'muted' },
      minor: { emoji: '!', cls: 'warn' },
      delay: { emoji: '⏱', cls: 'delay' },
      disruption: { emoji: '!!', cls: 'bad' },
    };
    return map[status] || map.unknown;
  }

  function applyBrand(meta) {
    if (!meta) return;
    brandMeta = meta;
    const productName = meta.name || meta.product || 'TrafficMY';
    const tagline = meta.tagline || 'Malaysia transport';
    const title = `${productName} · ${tagline}`;
    document.title = title;
    const ogTitle = document.querySelector('meta[property="og:title"]');
    if (ogTitle) ogTitle.setAttribute('content', title);
    const ogDesc = document.querySelector('meta[property="og:description"]');
    if (ogDesc) ogDesc.setAttribute('content', 'See if your line is delayed — at a glance.');
    const desc = document.querySelector('meta[name="description"]');
    if (desc) desc.setAttribute('content', 'See if your line is delayed — at a glance.');
    const footerTagline = $('footerTagline');
    if (footerTagline) footerTagline.textContent = tagline;
  }

  function sortReportsThreadsFirst(reports) {
    const list = [...(reports || [])];
    list.sort((a, b) => {
      const ta = new Date(a.last_seen_at || 0).getTime();
      const tb = new Date(b.last_seen_at || 0).getTime();
      if (tb !== ta) return tb - ta;
      const aThreads = (a.sources || '').includes('threads') ? 1 : 0;
      const bThreads = (b.sources || '').includes('threads') ? 1 : 0;
      return bThreads - aThreads;
    });
    return list;
  }

  function reportAgeLabel(iso) {
    if (!iso) return '';
    const mins = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  }

  function isTodayMYT(iso) {
    if (!iso) return false;
    try {
      const mytDate = (d) => new Intl.DateTimeFormat('en-CA', {
        timeZone: 'Asia/Kuala_Lumpur',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
      }).format(d);
      return mytDate(new Date(iso)) === mytDate(new Date());
    } catch {
      return false;
    }
  }

  function mapLayerActiveForNetwork(network) {
    if (network === 'lrt') return mapLayers.lrt;
    if (network === 'mrt') return mapLayers.mrt;
    if (network === 'monorail') return mapLayers.monorail;
    if (network === 'ktm') return mapLayers.ktm;
    if (network === 'bus') return mapLayers.buses;
    // Unscoped pins (no line_id / unknown network) only show on broad filters.
    if (network === 'other') {
      return ['all', 'rail', 'favorites'].includes(activeFilter);
    }
    return false;
  }

  function syncMapLayersFromHomeFilter() {
    const presets = {
      lrt: { lrt: true, mrt: false, monorail: false, ktm: false, buses: false },
      mrt: { lrt: false, mrt: true, monorail: false, ktm: false, buses: false },
      ktm: { lrt: false, mrt: false, monorail: false, ktm: true, buses: false },
      monorail: { lrt: false, mrt: false, monorail: true, ktm: false, buses: false },
      bus: { lrt: false, mrt: false, monorail: false, ktm: false, buses: true },
      rail: { lrt: true, mrt: true, monorail: true, ktm: true, buses: false },
      all: { lrt: true, mrt: true, monorail: true, ktm: true, buses: false },
      favorites: { lrt: true, mrt: true, monorail: true, ktm: true, buses: false },
    };
    const preset = presets[activeFilter];
    if (!preset) return;
    // Never auto-enable GPS from home filters — keep user's GPS opt-in sticky.
    const gpsOn = !!mapLayers.gps;
    mapLayers = { reports: true, interchanges: true, gps: gpsOn, ...preset };
    syncMapLayerUi();
  }

  function renderPulseStrip(lines, reports) {
    const el = $('pulseStrip');
    if (!el) return;
    const active = (lines || []).filter(l => ['minor', 'delay', 'disruption'].includes(l.status));
    if (!active.length) {
      el.hidden = true;
      el.innerHTML = '';
      return;
    }
    el.hidden = false;
    el.innerHTML = active.map(l =>
      `<button type="button" class="pulse-chip ${esc(l.status)}" data-line-id="${esc(l.id)}">${esc(l.name)} · ${esc(l.status_label)}</button>`
    ).join('');
  }

  function healthClass(score) {
    if (score == null) return '';
    if (score >= 70) return 'good';
    if (score >= 40) return 'warn';
    return 'bad';
  }

  function emptyStateLabel(line) {
    if (line.empty_state === 'no_data') return '<span class="nodata-label">No current signal</span>';
    return '';
  }

  function healthRingSvg(score, status) {
    if (score == null) return '';
    const pct = Math.max(0, Math.min(100, score));
    const r = 16;
    const c = 2 * Math.PI * r;
    const offset = c - (pct / 100) * c;
    const color = pct >= 70 ? 'var(--ok)' : pct >= 40 ? 'var(--warn)' : 'var(--bad)';
    return `<svg class="health-ring" viewBox="0 0 36 36" aria-hidden="true"><circle cx="18" cy="18" r="${r}" fill="none" stroke="rgba(255,255,255,.08)" stroke-width="2"/><circle cx="18" cy="18" r="${r}" fill="none" stroke="${color}" stroke-width="2" stroke-dasharray="${c}" stroke-dashoffset="${offset}" transform="rotate(-90 18 18)" stroke-linecap="round"/></svg>`;
  }

  function stitchStatusPill(line) {
    if (line.in_service === false) {
      return { label: line.status_label || pickLang('Ended for today', 'Tamat hari ini'), cls: 'stitch-status--ended' };
    }
    if (line.status === 'disruption') {
      return { label: shortStatusLabel(line), cls: 'stitch-status--bad' };
    }
    if (line.status === 'delay' || line.status === 'minor') {
      return { label: shortStatusLabel(line), cls: 'stitch-status--delay' };
    }
    return { label: pickLang('Quiet', 'Senyap'), cls: 'stitch-status--quiet' };
  }

  function renderMapFloatCard(lines) {
    const el = $('mapFloatCard');
    if (!el) return;
    if (mapLayers.reports && reportMarkerCount > 0) {
      el.hidden = true;
      el.innerHTML = '';
      el.closest('.stitch-map-wrap')?.classList.remove('has-float-card');
      return;
    }
    const rank = { disruption: 3, delay: 2, minor: 1 };
    let items = (lines || []).filter(l => !l.planned && rank[l.status]);
    items = items.filter(line => {
      const net = getNetworkForLine(line.id);
      if (net === 'lrt' && !mapLayers.lrt) return false;
      if (net === 'mrt' && !mapLayers.mrt) return false;
      if (net === 'monorail' && !mapLayers.monorail) return false;
      if (net === 'ktm' && !mapLayers.ktm) return false;
      return true;
    });
    items.sort((a, b) => (rank[b.status] || 0) - (rank[a.status] || 0) || (b.report_count || 0) - (a.report_count || 0));
    if (!items.length || !document.getElementById('tabMap')?.classList.contains('active')) {
      el.hidden = true;
      el.innerHTML = '';
      el.closest('.stitch-map-wrap')?.classList.remove('has-float-card');
      return;
    }
    const line = items[0];
    const color = LINE_COLORS[line.id] || '#64748b';
    const pill = stitchStatusPill(line);
    const shortName = line.name.replace(/ Line$/, '');
    const reports = line.report_count || 0;
    el.hidden = false;
    el.closest('.stitch-map-wrap')?.classList.add('has-float-card');
    const statusUpper = line.status === 'disruption'
      ? pickLang('DISRUPTION', 'GANGGUAN')
      : line.status === 'delay'
        ? pickLang('DELAY', 'LEWAT')
        : pickLang('MINOR', 'KECIL');
    el.innerHTML = `
      <div class="stitch-map-float-card">
        <div class="stitch-map-float-head">
          <div class="stitch-map-float-stripe" style="background:${esc(color)}"></div>
          <div class="stitch-map-float-copy">
            <h3>${esc(shortName)}</h3>
            <p>${esc(reports)} ${pickLang('reports today', 'laporan hari ini')}</p>
          </div>
          <span class="stitch-status-pill ${pill.cls} stitch-map-float-pill">${esc(statusUpper)}</span>
        </div>
        <div class="stitch-map-float-actions">
          <button type="button" class="stitch-map-detail-btn" data-line-id="${esc(line.id)}" data-cluster="${esc(line.top_cluster_id || '')}">${pickLang('Details', 'Perincian')}</button>
          <button type="button" class="stitch-map-plan-btn stitch-btn-primary" data-line-id="${esc(line.id)}">${pickLang('Plan route', 'Rancang')}</button>
        </div>
      </div>`;
    el.querySelector('.stitch-map-detail-btn')?.addEventListener('click', () => {
      openLineGuide(line.id, { clusterId: line.top_cluster_id, label: line.name, status: line.status });
    });
    el.querySelector('.stitch-map-plan-btn')?.addEventListener('click', () => {
      switchTab('travel');
      const from = $('journeyFrom');
      if (from && !from.value) from.focus();
    });
  }

  function confidenceBadge(report) {
    const band = report.confidence_band;
    if (!band) return '';
    return `<span class="confidence ${esc(band)}">${esc(band)}</span>`;
  }

  function guessLineIdFromReport(r) {
    const blob = `${r.line_id || ''} ${r.entity || ''} ${r.headline || ''} ${r.location || ''}`.toLowerCase();
    if (blob.includes('kelana')) return 'kelana-jaya';
    if (blob.includes('ampang') || blob.includes('sri petaling')) return 'ampang-sri-petaling';
    if (blob.includes('putrajaya')) return 'putrajaya';
    if (blob.includes('kajang')) return 'kajang';
    if (blob.includes('monorail')) return 'monorail';
    if (blob.includes('ktm') || blob.includes('komuter')) return 'ktm-komuter';
    return '';
  }

  function reportStripeColor(r) {
    const id = r.line_id || guessLineIdFromReport(r);
    return LINE_COLORS[id] || '#6b6660';
  }

  function reportSourceTag(r) {
    const sources = (r.sources || '').split(',').map(s => s.trim()).filter(Boolean);
    if (sources.includes('official') || (r.source_roles || []).includes('official_grounding')) {
      return { label: pickLang('Official', 'Rasmi'), cls: 'stitch-tag--official' };
    }
    if (sources.includes('threads')) return { label: 'Threads', cls: 'stitch-tag--src' };
    if (sources.includes('reddit')) return { label: 'Reddit', cls: 'stitch-tag--src' };
    if (sources.includes('rss')) return { label: pickLang('News', 'Berita'), cls: 'stitch-tag--src' };
    return { label: pickLang('Rider', 'Penumpang'), cls: 'stitch-tag--src' };
  }

  function ridingNowFromReport(r) {
    const sources = (r.sources || '');
    if (sources.includes('official') && !sources.includes('threads') && !sources.includes('reddit')) return false;
    const t = [r.headline, r.summary, r.example_text, r.entity, r.location].filter(Boolean).join(' ').toLowerCase();
    const present = ['stuck', 'tak gerak', 'waiting', 'tunggu', 'hari ni', 'harini', 'today', 'this morning', 'again', 'sekarang', 'pagi ni', 'not moving'].some(x => t.includes(x));
    const impact = ['stuck', 'tak gerak', 'waiting', 'tunggu', 'minit', 'minute', 'fire alarm', 'not moving', 'tak boleh', 'pintu'].some(x => t.includes(x));
    const delayNow = ['delay', 'delays', 'kelewatan', 'gangguan', 'lambat'].some(x => t.includes(x)) && present;
    return impact || delayNow;
  }

  function checkNotify(lines) {
    if (!notifyEnabled || !('Notification' in window)) return;
    lines.forEach(line => {
      const prev = lastLineStatus[line.id];
      const now = line.status;
      if (prev && prev !== now && ['delay', 'disruption'].includes(now) && favoriteLineIds.has(line.id)) {
        if (Notification.permission === 'granted') {
          new Notification(`TrafficMY · ${line.name}`, { body: line.status_label + (line.reason ? ': ' + line.reason.slice(0, 80) : ''), tag: line.id });
        }
      }
      lastLineStatus[line.id] = now;
    });
  }

  function mapPollIntervalMs() {
    const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (conn?.saveData) return 60000;
    if (conn?.effectiveType && ['slow-2g', '2g', '3g'].includes(conn.effectiveType)) return 60000;
    return 30000;
  }

  function ensureMapLibre() {
    if (typeof maplibregl !== 'undefined') return Promise.resolve();
    if (!maplibrePromise) {
      maplibrePromise = new Promise((resolve, reject) => {
        const s = document.createElement('script');
        s.src = 'https://unpkg.com/maplibre-gl@5.24.0/dist/maplibre-gl.js';
        s.onload = () => resolve();
        s.onerror = () => reject(new Error('MapLibre failed to load'));
        document.body.appendChild(s);
      });
    }
    return maplibrePromise;
  }

  function panelFocusables() {
    const panel = $('panel');
    if (!panel) return [];
    return [...panel.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')]
      .filter(el => !el.disabled && el.offsetParent !== null);
  }

  function trapPanelFocus(e) {
    if (!$('panel')?.classList.contains('open') || e.key !== 'Tab') return;
    const nodes = panelFocusables();
    if (!nodes.length) return;
    const first = nodes[0];
    const last = nodes[nodes.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  function showPanel() {
    panelLastFocus = document.activeElement;
    $('panel').classList.add('open');
    $('panel').setAttribute('aria-hidden', 'false');
    $('backdrop').classList.add('show');
    document.body.classList.add('no-scroll');
    setTimeout(() => $('closePanel')?.focus(), 50);
    document.addEventListener('keydown', trapPanelFocus);
  }

  function closePanel() {
    $('panel').classList.remove('open');
    $('panel').setAttribute('aria-hidden', 'true');
    $('backdrop').classList.remove('show');
    document.body.classList.remove('no-scroll');
    document.removeEventListener('keydown', trapPanelFocus);
    if (panelLastFocus?.focus) panelLastFocus.focus();
    panelLastFocus = null;
  }

  function renderMapSidebar(lines) {
    const el = $('mapSidebarList');
    if (!el) return;
    let items = (lines || []).filter(l => !l.planned);
    items = items.filter(line => {
      const net = getNetworkForLine(line.id);
      if (net === 'lrt' && !mapLayers.lrt) return false;
      if (net === 'mrt' && !mapLayers.mrt) return false;
      if (net === 'monorail' && !mapLayers.monorail) return false;
      if (net === 'ktm' && !mapLayers.ktm) return false;
      return true;
    });
    items = items.slice(0, 24);
    if (!items.length) {
      el.innerHTML = '<p style="padding:12px;font-size:12px;color:var(--text-dim)">No lines matching active layers</p>';
      renderMapFloatCard([]);
      return;
    }
    el.innerHTML = items.map(line => {
      const color = LINE_COLORS[line.id] || '#64748b';
      return `<button type="button" class="map-sidebar-item" data-line-id="${esc(line.id)}">
        <span class="map-sidebar-dot" style="background:${esc(color)}"></span>
        <span style="flex:1;min-width:0">
          <strong style="font-size:13px">${esc(line.name)}</strong>
          <span style="display:block;font-size:11px;color:var(--text-dim)">${esc(line.status_label)}</span>
        </span>
      </button>`;
    }).join('');
    renderMapFloatCard(items);
  }

  function syncSearchInputs(value) {
    const input = $('placeSearch');
    if (input && input.value !== value) input.value = value;
    $('searchWrap')?.classList.toggle('has-value', !!value);
  }

  function focusSearchInput() {
    $('placeSearch')?.focus();
  }

  function openMapPopup(lngLat, html, opts = {}) {
    if (!mapInstance) return;
    activeMapPopup?.remove();
    // Popups can land anywhere on the map, including right over the "Where
    // to?" search bar — reuse the float-card push-up treatment so the search
    // bar always stays clear of whatever is currently showing.
    const wrap = mapInstance.getContainer()?.closest('.stitch-map-wrap');
    wrap?.classList.add('has-map-popup');
    activeMapPopup = new maplibregl.Popup({ offset: 12, maxWidth: '300px', ...opts })
      .setLngLat(lngLat)
      .setHTML(html)
      .addTo(mapInstance);
    activeMapPopup.on('close', () => {
      wrap?.classList.remove('has-map-popup');
      activeMapPopup = null;
    });
  }

  function clearReportMarkers() {
    reportMarkers.forEach(m => m.remove());
    reportMarkers = [];
  }

  function drawReportMarkers(features) {
    clearReportMarkers();
    reportMarkerCount = (features || []).length;
    if (!mapInstance || !mapLayers.reports) return;

    const zoom = mapInstance.getZoom();
    const shouldCluster = zoom < 13;
    const clusterRadius = zoom < 7 ? 0.2 : zoom < 10 ? 0.08 : 0.02;

    const clusters = [];
    (features || []).forEach(feature => {
      const coords = feature.geometry.coordinates;
      let added = false;
      if (shouldCluster) {
        for (const cluster of clusters) {
          const dx = coords[0] - cluster.center[0];
          const dy = coords[1] - cluster.center[1];
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < clusterRadius) {
            cluster.features.push(feature);
            const count = cluster.features.length;
            cluster.center[0] = (cluster.center[0] * (count - 1) + coords[0]) / count;
            cluster.center[1] = (cluster.center[1] * (count - 1) + coords[1]) / count;
            added = true;
            break;
          }
        }
      }
      if (!added) {
        clusters.push({
          center: [coords[0], coords[1]],
          features: [feature]
        });
      }
    });

    clusters.forEach(cluster => {
      if (cluster.features.length === 1) {
        const feature = cluster.features[0];
        const severity = feature.properties?.severity || 'minor';
        const isCorroborated = feature.properties?.corroborated_by_official || false;
        const ageHours = feature.properties?.last_seen_at 
          ? (Date.now() - new Date(feature.properties.last_seen_at).getTime()) / 3600000 
          : 0;

        const el = document.createElement('button');
        el.type = 'button';
        el.className = `stitch-map-pin stitch-map-pin--${severity}`;
        if (isCorroborated) el.classList.add('stitch-map-pin--corroborated');
        if (ageHours > 2) el.classList.add('stitch-map-pin--stale');

        el.setAttribute('aria-label', feature.properties?.headline || 'Rider report');
        el.innerHTML = `
          <span class="stitch-map-pin-bubble" aria-hidden="true">${severity === 'disruption' ? '!' : severity === 'delay' ? 'D' : '·'}</span>
          <span class="stitch-map-pin-tail" aria-hidden="true"></span>
        `;
        el.addEventListener('click', (e) => {
          e.stopPropagation();
          const p = feature.properties || {};
          if (p.cluster_id) {
            openPanel(p.cluster_id, p.headline || 'Rider signal');
            return;
          }
          const link = p.url ? `<div style="margin-top:8px"><a href="${esc(p.url)}" target="_blank" rel="noopener noreferrer">Open source</a></div>` : '';
          openMapPopup(
            feature.geometry.coordinates,
            `<strong>${esc(p.headline || 'Rider signal')}</strong><div style="margin-top:6px;font-size:13px">${esc(p.summary || '')}</div>${link}`,
            { className: 'stitch-map-popup' }
          );
        });
        const marker = new maplibregl.Marker({ element: el, anchor: 'bottom' })
          .setLngLat(feature.geometry.coordinates)
          .addTo(mapInstance);
        reportMarkers.push(marker);
      } else {
        const el = document.createElement('button');
        el.type = 'button';
        el.className = 'stitch-map-cluster-badge';
        el.setAttribute('aria-label', `${cluster.features.length} reports`);
        let maxSeverity = 'minor';
        cluster.features.forEach(f => {
          const s = f.properties?.severity || 'minor';
          if (SEVERITY_RANK[s] > SEVERITY_RANK[maxSeverity]) maxSeverity = s;
        });
        el.classList.add(`stitch-map-cluster-badge--${maxSeverity}`);

        el.innerHTML = `
          <span class="cluster-count">${cluster.features.length}</span>
          <span class="cluster-label">${pickLang('REPORTS', 'LAPORAN')}</span>
        `;
        el.addEventListener('click', (e) => {
          e.stopPropagation();
          mapInstance.easeTo({
            center: cluster.center,
            zoom: Math.min(15, mapInstance.getZoom() + 2)
          });
        });
        const marker = new maplibregl.Marker({ element: el, anchor: 'center' })
          .setLngLat(cluster.center)
          .addTo(mapInstance);
        reportMarkers.push(marker);
      }
    });
  }

  async function ensureMap() {
    const loading = $('mapLoading');
    const hideLoading = () => { if (loading) loading.hidden = true; };
    const showLoading = (msg) => {
      if (!loading) return;
      loading.hidden = false;
      if (msg) loading.textContent = msg;
    };
    if (!mapInstance) showLoading('Loading live map…');
    try {
      await ensureMapLibre();
    } catch {
      showLoading('Map unavailable. Check your connection and retry.');
      return;
    }
    if (typeof maplibregl === 'undefined') {
      showLoading('Map unavailable. Check your connection and retry.');
      return;
    }
    const params = new URLSearchParams();
    // Opt-in only — never fetch GPS just because KTM/Bus line layers are on.
    if (mapLayers.gps) params.set('vehicles', 'true');
    const res = await fetchWithTimeout(api(`/api/trafficmy/map/live?${params}`));
    if (!res.ok) {
      showLoading('Map data unavailable. Retry in a moment.');
      return;
    }
    const data = await res.json();
    if (!mapInstance) {
      mapInstance = new maplibregl.Map({
        container: 'malaysiaMap',
        style: 'https://tiles.openfreemap.org/styles/dark',
        center: [data.center.lon, data.center.lat],
        zoom: 11,
        pitch: 0,
        bearing: 0,
        minZoom: 5,
        maxZoom: 19,
        maxBounds: [[data.bounds.west, data.bounds.south], [data.bounds.east, data.bounds.north]],
        canvasContextAttributes: { antialias: true },
        attributionControl: true,
      });
      mapInstance.on('styleimagemissing', event => {
        if (!mapInstance.hasImage(event.id)) {
          mapInstance.addImage(event.id, { width: 1, height: 1, data: new Uint8Array(4) });
        }
      });
      mapInstance.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
      mapInstance.addControl(new maplibregl.GeolocateControl({ positionOptions: { enableHighAccuracy: false }, trackUserLocation: true }), 'top-right');
      await new Promise(resolve => mapInstance.once('load', resolve));

      const firstLabel = (mapInstance.getStyle().layers || []).find(layer => layer.type === 'symbol' && layer.layout?.['text-field']);
      if (!mapInstance.getSource('trafficmy-buildings')) {
        mapInstance.addSource('trafficmy-buildings', { url: 'https://tiles.openfreemap.org/planet', type: 'vector' });
        mapInstance.addLayer({
          id: 'trafficmy-3d-buildings',
          source: 'trafficmy-buildings',
          'source-layer': 'building',
          type: 'fill-extrusion',
          minzoom: 14.5,
          filter: ['!=', ['get', 'hide_3d'], true],
          paint: {
            'fill-extrusion-color': ['interpolate', ['linear'], ['get', 'render_height'], 0, '#252a32', 160, '#47413d', 360, '#8a4c28'],
            'fill-extrusion-height': ['interpolate', ['linear'], ['zoom'], 14.5, 0, 16, ['get', 'render_height']],
            'fill-extrusion-base': ['coalesce', ['get', 'render_min_height'], 0],
            'fill-extrusion-opacity': .72,
          },
        }, firstLabel?.id);
      }
    } else {
      mapInstance.resize();
      if (!mapInstance.loaded()) await new Promise(resolve => mapInstance.once('idle', resolve));
    }

    const reportFeatures = [];
    if (mapLayers.reports) {
      const reportsWithCoords = (data.reports || []).filter(r => r.lat != null && r.lon != null);
      const mapReports = liveRelevantReports(
        reportsWithCoords.length ? reportsWithCoords : (boardSnapshot?.recent_reports || []),
        boardSnapshot?.lines || boardData?.lines,
      );
      mapReports.forEach(rep => {
        const net = getNetworkForLine(rep.line_id);
        if (!mapLayerActiveForNetwork(net)) return;

        if (placeFilter) {
          const needle = placeFilter.toLowerCase().trim();
          let match = reportMatchesPlace(rep, needle);
          if (!match && rep.line_id) {
            const line = (boardSnapshot?.lines || []).find(l => l.id === rep.line_id);
            if (line && lineMatchesPlace(line, needle)) {
              match = true;
            }
          }
          if (!match) return;
        }

        reportFeatures.push({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [rep.lon, rep.lat] },
          properties: {
            cluster_id: rep.cluster_id || '',
            headline: rep.headline || rep.entity || rep.location || 'Rider signal',
            summary: rep.summary || '',
            severity: rep.severity || 'minor',
            url: rep.example_url || '',
            sources: rep.sources || '',
            corroborated_by_official: rep.corroborated_by_official || false,
            last_seen_at: rep.last_seen_at || '',
          },
        });
      });
    }

    const vehicleFeatures = [];
    if (mapLayers.gps) {
      const showRail = mapLayers.ktm || (!mapLayers.ktm && !mapLayers.buses);
      const showBus = mapLayers.buses || (!mapLayers.ktm && !mapLayers.buses);
      (data.vehicles || []).forEach(veh => {
        const isRail = veh.mode === 'rail';
        if (isRail && !showRail) return;
        if (!isRail && !showBus) return;
        vehicleFeatures.push({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [veh.lon, veh.lat] },
          properties: {
            mode: isRail ? 'rail' : 'bus',
            label: veh.label || veh.route_id || (isRail ? 'KTM train' : 'Bus'),
            age: veh.age_seconds != null ? `${veh.age_seconds}s ago` : 'Unknown age',
          },
        });
      });
    }

    drawRailPolylines(data.rail_lines);
    drawInterchangeMarkers(mapLayers.interchanges ? (data.interchanges || []) : []);
    drawReportMarkers(reportFeatures);
    setMapGeoJSON('trafficmy-reports', [], 'circle', {
      'circle-radius': 0,
      'circle-opacity': 0,
    });
    setMapGeoJSON('trafficmy-vehicles', vehicleFeatures, 'circle', {
      'circle-radius': ['match', ['get', 'mode'], 'rail', 7, 5],
      'circle-color': ['match', ['get', 'mode'], 'rail', '#0066b3', '#f97316'],
      'circle-stroke-color': '#1b1c1c',
      'circle-stroke-width': 2,
      'circle-opacity': mapLayers.gps ? 0.9 : 0,
    });
    bindMapEvents();
    hideLoading();
    renderMapFloatCard(boardSnapshot?.lines || boardData?.lines || []);
  }

  function setMapGeoJSON(id, features, type, paint, beforeId) {
    if (!mapInstance) return;
    const data = { type: 'FeatureCollection', features: features || [] };
    const source = mapInstance.getSource(id);
    if (source) {
      source.setData(data);
      return;
    }
    mapInstance.addSource(id, { type: 'geojson', data });
    mapInstance.addLayer({ id, source: id, type, paint }, beforeId);
  }

  function bindMapEvents() {
    if (mapEventsBound || !mapInstance) return;
    mapEventsBound = true;
    ['trafficmy-reports', 'trafficmy-vehicles', 'trafficmy-hubs', 'trafficmy-rail-lines', 'trafficmy-rail-lines-disrupted'].forEach(layerId => {
      mapInstance.on('mouseenter', layerId, () => { mapInstance.getCanvas().style.cursor = 'pointer'; });
      mapInstance.on('mouseleave', layerId, () => { mapInstance.getCanvas().style.cursor = ''; });
    });
    mapInstance.on('click', 'trafficmy-reports', event => {
      const feature = event.features?.[0];
      if (!feature) return;
      const p = feature.properties || {};
      const link = p.url ? `<div style="margin-top:8px"><a href="${esc(p.url)}" target="_blank" rel="noopener noreferrer">Open source evidence</a></div>` : '';
      openMapPopup(
        event.lngLat,
        `<strong>${esc(p.headline || 'Rider signal')}</strong><div style="margin-top:5px">${esc(p.summary || '')}</div>${link}`,
        { offset: 10, maxWidth: '320px' }
      );
    });
    mapInstance.on('click', 'trafficmy-vehicles', event => {
      const p = event.features?.[0]?.properties || {};
      openMapPopup(
        event.lngLat,
        `<strong>${esc(p.label || 'Vehicle')}</strong><br>Official GPS · ${esc(p.age || '')}<br><em>Reference telemetry, not incident truth.</em>`,
        { offset: 8 }
      );
    });
    mapInstance.on('click', 'trafficmy-hubs', event => {
      const p = event.features?.[0]?.properties || {};
      let chipsHtml = '';
      if (p.lines_json) {
        try {
          const lines = JSON.parse(p.lines_json);
          chipsHtml = `<div class="ix-chips" style="margin-top: 8px; justify-content: center;">` + 
            lines.map(lc => {
              const name = lc.name.replace(/ Line$/, '').replace(/LRT |MRT |KTM /, '');
              return `<span class="ix-line-chip" style="--chip-color:${esc(lc.color)}">${esc(name)}</span>`;
            }).join('') + `</div>`;
        } catch (e) {
          chipsHtml = `<div style="margin-top:5px;font-size:12px">${esc(p.lines || '')}</div>`;
        }
      }
      openMapPopup(
        event.lngLat,
        `<div style="text-align:center">
          <strong style="font-size:14px">${esc(p.station || 'Interchange')}</strong>
          ${chipsHtml}
        </div>`,
        { offset: 8 }
      );
    });

    const handleLineClick = event => {
      const feature = event.features?.[0];
      if (!feature) return;
      const p = feature.properties || {};
      const lineId = p.line_id || '';
      const color = p.color || LINE_COLORS[lineId] || '#64748b';
      const name = p.name || linesReferenceById[lineId]?.name || lineId || 'Rail line';
      openMapPopup(
        event.lngLat,
        `<div class="map-line-popup">
          <div class="map-line-popup-head">
            <span class="map-line-dot" style="background:${esc(color)}"></span>
            <strong>${esc(name)}</strong>
          </div>
          <button type="button" class="guide-btn primary map-popup-line-guide" data-line-id="${esc(lineId)}">Line guide</button>
        </div>`,
        { offset: 8, maxWidth: '280px' }
      );
      mapInstance.getContainer()?.querySelector('.map-popup-line-guide')?.addEventListener('click', () => {
        activeMapPopup?.remove();
        if (lineId) openLineGuide(lineId, { label: name });
      });
    };

    mapInstance.on('click', 'trafficmy-rail-lines', handleLineClick);
    mapInstance.on('click', 'trafficmy-rail-lines-disrupted', handleLineClick);
  }

  function drawInterchangeMarkers(hubs) {
    const features = (hubs || []).filter(hub => {
      const lineIds = hub.lines || [];
      if (!lineIds.length) return true;
      return lineIds.some(id => mapLayerActiveForNetwork(getNetworkForLine(id)));
    }).map(hub => {
      const linesData = (hub.line_labels || []).map(line => ({
        id: line.id,
        name: line.name,
        color: LINE_COLORS[line.id] || '#64748b'
      }));
      return {
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [hub.lon, hub.lat] },
        properties: {
          station: hub.station || '',
          lines: (hub.line_labels || []).map(line => line.name).join(' · '),
          lines_json: JSON.stringify(linesData)
        },
      };
    });

    setMapGeoJSON('trafficmy-hubs', features, 'circle', {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 9, 4, 14, 8],
      'circle-color': '#ffffff',
      'circle-stroke-width': ['interpolate', ['linear'], ['zoom'], 9, 2, 14, 4],
      'circle-stroke-color': '#111111',
    });
  }

  function syncMapLayerUi() {
    MAP_LAYER_UI.forEach(([key, id]) => {
      const on = !!mapLayers[key];
      const el = $(id);
      el?.classList.toggle('map-on', on);
      el?.classList.toggle('active', on);
      el?.setAttribute('aria-pressed', String(on));
    });
    const allEl = $('mapLayerAll');
    if (allEl) {
      const allOn = activeFilter === 'all';
      allEl.classList.toggle('active', allOn);
      allEl.classList.toggle('map-on', allOn);
      allEl.setAttribute('aria-pressed', String(allOn));
    }
  }

  const MAP_NETWORK_FILTER_KEYS = new Set(['lrt', 'mrt', 'monorail', 'ktm']);

  function onMapLayerChipClick(key) {
    if (key === 'all') {
      setActiveFilter('all');
      return;
    }
    if (MAP_NETWORK_FILTER_KEYS.has(key)) {
      setActiveFilter(key);
      return;
    }
    if (key === 'buses') {
      setActiveFilter('bus');
      return;
    }
    if (key === 'gps') {
      toggleMapLayer('gps');
      return;
    }
    toggleMapLayer(key);
  }

  function toggleMapLayer(key) {
    mapLayers[key] = !mapLayers[key];
    syncMapLayerUi();
    if (key === 'reports' && !mapLayers.reports) clearReportMarkers();
    if (key === 'gps' && !mapLayers.gps) {
      setMapGeoJSON('trafficmy-vehicles', [], 'circle', {
        'circle-radius': 0,
        'circle-opacity': 0,
      });
    }
    ensureMap();
    if (boardData) {
      renderMapSidebar(boardData.lines || []);
    }
    // Poll live GPS only while the opt-in GPS layer is on.
    const wantGpsPoll = !!mapLayers.gps;
    if (wantGpsPoll && !mapPollTimer) {
      const interval = mapPollIntervalMs();
      mapPollTimer = setInterval(() => {
        if (document.getElementById('tabMap')?.classList.contains('active') && mapLayers.gps) ensureMap();
      }, interval);
    }
    if (!wantGpsPoll && mapPollTimer) {
      clearInterval(mapPollTimer);
      mapPollTimer = null;
    }
  }

  let polylinePulseVal = 0.8;
  let polylinePulseDir = -1;
  function animateDisruptedLines() {
    if (!mapInstance) return;
    polylinePulseVal += polylinePulseDir * 0.03;
    if (polylinePulseVal <= 0.25) {
      polylinePulseVal = 0.25;
      polylinePulseDir = 1;
    } else if (polylinePulseVal >= 0.9) {
      polylinePulseVal = 0.9;
      polylinePulseDir = -1;
    }
    try {
      if (mapInstance.getLayer('trafficmy-rail-lines-disrupted')) {
        mapInstance.setPaintProperty('trafficmy-rail-lines-disrupted', 'line-opacity', polylinePulseVal);
      }
    } catch (e) {}
    requestAnimationFrame(animateDisruptedLines);
  }

  function drawRailPolylines(geojson) {
    if (!mapInstance) return;
    const query = (placeFilter || '').toLowerCase().trim();
    const features = (geojson?.features || []).filter(feature => {
      const lineId = feature.properties?.line_id;
      let network = feature.properties?.network || 'other';
      if ((!network || network === 'other') && lineId) {
        network = getNetworkForLine(lineId);
      }
      if (!mapLayerActiveForNetwork(network)) return false;

      if (query && lineId) {
        const line = (boardSnapshot?.lines || []).find(l => l.id === lineId) || { id: lineId, name: feature.properties?.name || '' };
        if (!lineMatchesPlace(line, query)) {
          return false;
        }
      }
      feature.properties = {
        ...(feature.properties || {}),
        color: feature.properties?.color || LINE_COLORS[lineId] || '#6b6660',
      };
      return true;
    });

    setMapGeoJSON('trafficmy-rail-lines', features, 'line', {
      'line-color': ['get', 'color'],
      'line-width': ['interpolate', ['linear'], ['zoom'], 9, 4, 14, 9],
      'line-opacity': 0.92,
      'line-blur': 0.4,
    });

    const disruptedFeatures = features.filter(feature => {
      const lineId = feature.properties?.line_id;
      if (!lineId) return false;
      const lineStatus = (boardSnapshot?.lines || []).find(l => l.id === lineId)?.status;
      return ['delay', 'disruption'].includes(lineStatus);
    });

    setMapGeoJSON('trafficmy-rail-lines-disrupted', disruptedFeatures, 'line', {
      'line-color': '#DC143C',
      'line-width': ['interpolate', ['linear'], ['zoom'], 9, 6, 14, 12],
      'line-opacity': 0.8,
      'line-dasharray': [2, 2],
    });

    if (disruptedFeatures.length && !window._linesPulseStarted) {
      window._linesPulseStarted = true;
      animateDisruptedLines();
    }
  }

  function formatIntervalLabel(seconds) {
    const s = Math.max(60, Number(seconds) || 60);
    if (s % 3600 === 0) return `${s / 3600} hr`;
    if (s % 60 === 0) return `${s / 60} min`;
    return `${s}s`;
  }

  function updateIntervalMeta() {
    const poll = formatIntervalLabel(COUNTDOWN_SEC);
    const ingest = formatIntervalLabel(ingestIntervalSec);
    const popoverHtml = `
      <p>Dashboard checks every <strong>${poll}</strong> · autonomous collection every <strong>${ingest}</strong></p>
      <p><strong>Check latest</strong> reloads the server snapshot. Collection runs unattended in the background.</p>`;
    const popMobile = $('refreshInfoPopoverMobile');
    const popDesktop = $('refreshInfoPopover');
    if (popMobile) popMobile.innerHTML = popoverHtml;
    if (popDesktop) popDesktop.innerHTML = popoverHtml;
    const desktop = $('intervalMeta');
    if (desktop) {
      desktop.innerHTML = `
        <span class="refresh-pill">Dashboard: <strong>${poll}</strong></span>
        <span class="refresh-pill">Collector: <strong>${ingest}</strong></span>`;
    }
  }

  function toggleInfoPopover(btn, popover) {
    if (!btn || !popover) return;
    const open = popover.classList.toggle('open');
    btn.setAttribute('aria-expanded', open);
  }

  function bindRefreshInfoButtons() {
    const pairs = [
      [$('refreshInfoBtn'), $('refreshInfoPopoverMobile')],
      [$('refreshInfoBtnDesktop'), $('refreshInfoPopover')],
    ];
    pairs.forEach(([btn, pop]) => {
      if (!btn || btn.dataset.bound) return;
      btn.dataset.bound = '1';
      btn.addEventListener('click', e => {
        e.stopPropagation();
        toggleInfoPopover(btn, pop);
      });
    });
    document.addEventListener('click', e => {
      if (e.target.closest('.info-btn') || e.target.closest('.info-popover')) return;
      document.querySelectorAll('.info-popover.open').forEach(p => p.classList.remove('open'));
      document.querySelectorAll('.info-btn[aria-expanded="true"]').forEach(b => b.setAttribute('aria-expanded', 'false'));
    });
  }

  async function fetchWithTimeout(url, timeoutMs = FETCH_TIMEOUT_MS, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      return await fetch(url, { ...options, signal: controller.signal });
    } finally {
      clearTimeout(timer);
    }
  }

  function applyConfig(cfg) {
    if (!cfg) return;
    if (cfg.poll_interval_seconds) {
      COUNTDOWN_SEC = cfg.poll_interval_seconds;
      REFRESH_INTERVAL = COUNTDOWN_SEC * 1000;
      secondsLeft = COUNTDOWN_SEC;
    }
    if (cfg.ingest_interval_seconds) ingestIntervalSec = cfg.ingest_interval_seconds;
    const statusLabels = { active: 'online', healthy: 'online', empty: 'checked · quiet', scheduled: 'scheduled', dormant: 'standby', reference: 'map reference', degraded: 'degraded', failed: 'down' };
    const sourceHtml = (cfg.source_lanes || []).map(lane =>
      `<span class="source-pill ${esc(lane.status)}" title="${esc(lane.notes || '')}">${esc(lane.label)} · ${esc(statusLabels[lane.status] || lane.status)}</span>`
    ).join('');
    if ($('sourceHealth')) $('sourceHealth').innerHTML = sourceHtml;
    if ($('sourceCoverageStrip')) $('sourceCoverageStrip').innerHTML = sourceHtml;
    updateIntervalMeta();
  }

  async function loadConfig() {
    try {
      const res = await fetchWithTimeout(api('/api/trafficmy/config'), 10000);
      if (!res.ok) return;
      applyConfig(await res.json());
    } catch { /* keep defaults */ }
  }

  async function loadAppShell() {
    try {
      const res = await fetchWithTimeout(api('/api/trafficmy/app-shell'), 10000);
      if (!res.ok) return false;
      const shell = await res.json();
      if (shell.brand) applyBrand(shell.brand);
      if (shell.meta) applyBrand(shell.meta);
      if (shell.config) applyConfig(shell.config);
      if (shell.status?.freshness) {
        updateLiveStatus({ freshness: shell.status.freshness });
      }
      return true;
    } catch {
      return false;
    }
  }

  function skeletonRows(n) {
    return Array.from({ length: n }, () => `
      <div class="skel-row">
        <div class="skel skel-badge"></div>
        <div style="flex:1"><div class="skel skel-text"></div><div class="skel skel-text short"></div></div>
        <div class="skel skel-time"></div>
      </div>`).join('');
  }

  function showLoadingState() {
    $('liveMeta').textContent = 'Loading…';
    $('liveDot').classList.remove('stale');
    const ps = $('pulseStrip');
    if (ps) { ps.hidden = true; ps.innerHTML = ''; }
    const ss = $('summaryStrip');
    if (ss) {
      ss.hidden = false;
      ss.removeAttribute('aria-hidden');
      ss.innerHTML = `
        <div class="stat-pill"><span class="skel skel-pill"></span></div>
        <div class="stat-pill"><span class="skel skel-pill" style="width:88px"></span></div>
        <div class="stat-pill"><span class="skel skel-pill" style="width:72px"></span></div>`;
    }
    $('statsBar').innerHTML = `<button type="button" class="stats-bar-btn" disabled><span class="skel skel-pill" style="width:100%"></span></button>`;
    $('boardSummary').classList.remove('show');
    const boardCountEl = document.querySelector('#lineBoard .board-count');
    if (boardCountEl) boardCountEl.textContent = '…';
    $('lineBoard').innerHTML = `
      <div class="board-head"><span>Lines</span><span class="board-count">…</span></div>
      <div class="loading-banner"><span class="loading-spinner" aria-hidden="true"></span><span>Loading line status…</span></div>
      ${skeletonRows(5)}`;
    $('reportFeed').innerHTML = skeletonRows(3);
    $('reportCount').textContent = '';
  }

  function showBoardError(title, detail, retryId = 'boardRetry') {
    $('lineBoard').innerHTML = `
      <div class="board-head"><span>Lines</span><span>—</span></div>
      <div class="error-state">
        <strong>${esc(title)}</strong>
        <p>${esc(detail)}</p>
        <button class="btn-retry" id="${retryId}" type="button">Try again</button>
      </div>`;
    const btn = $(retryId);
    if (btn) btn.addEventListener('click', () => loadAll());
  }

  function parseTs(ts) {
    if (!ts) return null;
    const raw = String(ts).trim();
    if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(raw)) return new Date(raw.replace(' ', 'T') + 'Z');
    return new Date(raw);
  }

  function relTime(ts) {
    const d = parseTs(ts);
    if (!d || isNaN(d)) return '';
    const m = Math.floor((Date.now() - d.getTime()) / 60000);
    if (m < 1) return 'just now';
    if (m < 60) return `${m} min ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h} hr ago`;
    return `${Math.floor(h / 24)} d ago`;
  }

  function fmtMYT(ts) {
    const d = parseTs(ts);
    return d && !isNaN(d)
      ? d.toLocaleString('en-MY', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kuala_Lumpur' })
      : '—';
  }

  function esc(s) {
    const el = document.createElement('div');
    el.textContent = s || '';
    return el.innerHTML;
  }

  function formatSources(sources) {
    if (!sources) return '';
    return String(sources).split(/[,;|]/).map(s => s.trim()).filter(Boolean)
      .map(s => `<span class="source-chip">${esc(s)}</span>`).join('');
  }

  function platformClass(p) {
    const low = (p || '').toLowerCase();
    if (low.includes('reddit')) return 'reddit';
    if (low.includes('thread')) return 'threads';
    return '';
  }

  const ICON_SVG = {
    train: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 13c0-3.87-3.37-7-10-7h-8"/><path d="M3 15h16a2 2 0 0 0 2-2"/><path d="M3 6v5h17.5"/><path d="M3 11v4"/><path d="M8 11v-5"/><path d="M13 11v-4.5"/><path d="M3 19h18"/></svg>',
    tram: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 15h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v4a2 2 0 0 0 2 2z"/><path d="M4 11h16"/><path d="M8 15v3"/><path d="M16 15v3"/><path d="M3 19h18"/></svg>',
    monorail: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10h18"/><path d="M5 10V7a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3"/><path d="M7 10v5a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1v-5"/><path d="M9 16v2"/><path d="M15 16v2"/><path d="M10 13h4"/></svg>',
    bus: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 17m-2 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0"/><path d="M18 17m-2 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0"/><path d="M4 17h-2v-11a1 1 0 0 1 1-1h14a5 7 0 0 1 5 7v5h-2m-4 0h-8"/><path d="M16 5l1.5 7l4.5 0"/><path d="M2 10l15 0"/><path d="M7 5l0 5"/><path d="M12 5l0 5"/></svg>',
  };

  const LINE_ICON_TYPE = {
    'kelana-jaya': 'tram', 'ampang-sri-petaling': 'tram', 'kajang': 'tram', 'putrajaya': 'tram',
    'kajang-putrajaya': 'tram', 'monorail': 'monorail', 'brt-sunway': 'bus', 'lrt3': 'tram',
    'ktm-komuter': 'train', 'ktm-north': 'train', 'ets-intercity': 'train', 'klia-rail': 'train',
    'sabah-railway': 'train', 'rapid-bus': 'bus', 'penang': 'bus', 'kuantan': 'bus', 'mybas': 'bus',
  };

  function lineIconType(line) {
    if (LINE_ICON_TYPE[line.id]) return LINE_ICON_TYPE[line.id];
    if (line.mode === 'bus') return 'bus';
    if ((line.name || '').toLowerCase().includes('monorail')) return 'monorail';
    if ((line.operator || '').toLowerCase().includes('ktm')) return 'train';
    return 'tram';
  }

  function lineIconHtml(line) {
    const type = lineIconType(line);
    const ring = healthRingSvg(line.health_score, line.status);
    return `<span class="line-icon-wrap">${ring}<span class="line-icon" aria-hidden="true">${ICON_SVG[type] || ICON_SVG.tram}</span></span>`;
  }

  const FAV_KEY = 'trafficmy:favorites';
  const LAST_INCIDENT_KEY = 'trafficmy:lastIncident';
  const FILTER_LABELS = { all: 'All', favorites: 'My lines', rail: 'Rail', lrt: 'LRT', mrt: 'MRT', ktm: 'KTM', monorail: 'Monorail', bus: 'Bus' };
  const CHIP_LABELS = {
    all: 'All',
    favorites: '⭐ Saved',
    rail: '🚆 Rail',
    lrt: '🚇 LRT',
    mrt: '🚊 MRT',
    ktm: '🚂 KTM',
    monorail: '🛤 Mono',
    bus: '🚌 Bus',
  };

  function getNetworkForLine(lineId) {
    if (!lineId) return 'other';
    const id = lineId.toLowerCase();
    if (['kelana-jaya', 'ampang-sri-petaling', 'lrt3', 'lrt3-shah-alam'].includes(id) || id.includes('lrt') || id.includes('kelana') || id.includes('ampang')) return 'lrt';
    if (id === 'monorail' || id.includes('monorail')) return 'monorail';
    if (['kajang', 'putrajaya'].includes(id) || id.includes('mrt')) return 'mrt';
    if (['ktm-komuter', 'ktm-north', 'ets-intercity', 'klia-rail', 'sabah-railway', 'ktm'].includes(id) || id.startsWith('ktm-') || id.includes('ktm') || id.includes('komuter')) return 'ktm';
    if (id.includes('bus') || id.includes('rapid-bus') || id.includes('penang') || id.includes('kuantan') || id.includes('mybas')) return 'bus';
    return 'other';
  }

  function loadFavoriteLineIds() {
    try {
      const raw = JSON.parse(localStorage.getItem(FAV_KEY) || '[]');
      return new Set(Array.isArray(raw) ? raw.filter(Boolean) : []);
    } catch {
      return new Set();
    }
  }

  let favoriteLineIds = loadFavoriteLineIds();

  function saveFavorites() {
    localStorage.setItem(FAV_KEY, JSON.stringify([...favoriteLineIds]));
  }

  function toggleFavorite(lineId) {
    if (favoriteLineIds.has(lineId)) favoriteLineIds.delete(lineId);
    else favoriteLineIds.add(lineId);
    saveFavorites();
    if (boardSnapshot) {
      renderBoard();
      renderRiskStrip(boardSnapshot.lines || []);
    }
    showToast(favoriteLineIds.has(lineId)
      ? pickLang('Added to My lines', 'Ditambah ke Laluan saya')
      : pickLang('Removed from My lines', 'Dibuang dari Laluan saya'));
  }

  function showToast(msg, ms = 2600) {
    const el = $('toast');
    if (!el) return;
    el.textContent = msg;
    el.classList.add('show');
    clearTimeout(showToast._timer);
    showToast._timer = setTimeout(() => el.classList.remove('show'), ms);
  }

  function rememberLastIncident(clusterId, label) {
    const payload = { clusterId, label, at: Date.now() };
    sessionStorage.setItem(LAST_INCIDENT_KEY, JSON.stringify(payload));
    renderLastViewed();
  }

  function renderLastViewed() {
    const el = $('lastViewed');
    if (!el) return;
    try {
      const raw = sessionStorage.getItem(LAST_INCIDENT_KEY);
      if (!raw) { el.hidden = true; return; }
      const { clusterId, label } = JSON.parse(raw);
      el.hidden = false;
      el.innerHTML = `Last viewed: <button type="button" id="lastViewedBtn">${esc(label)}</button>`;
      $('lastViewedBtn').addEventListener('click', () => openPanel(clusterId, label));
    } catch { el.hidden = true; }
  }

  async function shareLineStatus(line) {
    const text = `${line.name} — ${line.status_label}${line.reason ? ': ' + line.reason : ''} (TrafficMY)`;
    const url = `${location.origin}${location.pathname}#line=${encodeURIComponent(line.id)}`;
    try {
      if (navigator.share) {
        await navigator.share({ title: line.name, text, url });
        showToast('Shared');
      } else {
        await navigator.clipboard.writeText(`${text}\n${url}`);
        showToast('Copied to clipboard');
      }
    } catch (err) {
      if (err?.name !== 'AbortError') showToast('Could not share');
    }
  }

  function filteredLines(lines) {
    const source = lines || boardSnapshot?.lines || [];
    let out = [...source];
    if (activeFilter === 'favorites') out = out.filter(l => favoriteLineIds.has(l.id));
    else if (activeFilter === 'rail') out = out.filter(l => l.mode === 'rail');
    else if (activeFilter === 'lrt') out = out.filter(l => ['kelana-jaya', 'ampang-sri-petaling', 'lrt3', 'lrt3-shah-alam'].includes(l.id));
    else if (activeFilter === 'mrt') out = out.filter(l => ['kajang', 'putrajaya'].includes(l.id));
    else if (activeFilter === 'ktm') out = out.filter(l => l.id.startsWith('ktm-') || ['ets-intercity', 'klia-rail', 'sabah-railway'].includes(l.id));
    else if (activeFilter === 'monorail') out = out.filter(l => l.id === 'monorail');
    else if (activeFilter === 'bus') out = out.filter(l => l.mode === 'bus');
    if (placeFilter) {
      const needle = placeFilter.toLowerCase();
      out = out.filter(l => lineMatchesPlace(l, needle));
    }
    return sortLines(out);
  }

  function boardFilterCounts() {
    const lines = boardSnapshot?.lines || [];
    return {
      all: lines.length,
      favorites: lines.filter(l => favoriteLineIds.has(l.id)).length,
      rail: lines.filter(l => l.mode === 'rail').length,
      lrt: lines.filter(l => ['kelana-jaya', 'ampang-sri-petaling', 'lrt3', 'lrt3-shah-alam'].includes(l.id)).length,
      mrt: lines.filter(l => ['kajang', 'putrajaya'].includes(l.id)).length,
      ktm: lines.filter(l => l.id.startsWith('ktm-') || ['ets-intercity', 'klia-rail', 'sabah-railway'].includes(l.id)).length,
      monorail: lines.filter(l => l.id === 'monorail').length,
      bus: lines.filter(l => l.mode === 'bus').length,
    };
  }

  function updateFilterChips() {
    const counts = boardFilterCounts();
    document.querySelectorAll('#filters .chip').forEach(chip => {
      const mode = chip.dataset.mode;
      const baseLabel = CHIP_LABELS[mode] || FILTER_LABELS[mode] || mode;
      const n = counts[mode];
      chip.textContent = n != null ? `${baseLabel} · ${n}` : baseLabel;
      chip.classList.toggle('active', mode === activeFilter);
    });
    const hint = $('filterHint');
    if (!hint) return;
    const parts = [];
    if (activeFilter !== 'all') parts.push(FILTER_LABELS[activeFilter] || activeFilter);
    if (placeFilter) parts.push(`"${placeFilter}"`);
    if (parts.length) {
      hint.hidden = false;
      hint.innerHTML = `Showing <strong>${esc(parts.join(' + '))}</strong> — tap <strong>All</strong> or Clear search to reset.`;
    } else {
      hint.hidden = true;
      hint.textContent = '';
    }
  }

  function setActiveFilter(mode) {
    activeFilter = mode || 'all';
    if (mode === 'all') {
      placeFilter = '';
      syncSearchInputs('');
      const banner = $('filterBanner');
      if (banner) banner.classList.remove('show');
    }
    updateFilterChips();
    updateSchematic();
    syncMapLayersFromHomeFilter();
    renderBoard();
    if (boardSnapshot) renderReports(boardSnapshot.recent_reports || []);
    if (document.getElementById('tabMap')?.classList.contains('active')) {
      ensureMap();
      renderMapSidebar(boardSnapshot?.lines || []);
    }
    saveUiState();
  }

  function resetBoardFilters() {
    activeFilter = 'all';
    placeFilter = '';
    syncSearchInputs('');
    $('filterBanner')?.classList.remove('show');
    updateFilterChips();
    syncMapLayersFromHomeFilter();
    updateSchematic();
    renderBoard();
    if (boardSnapshot) renderReports(boardSnapshot.recent_reports || []);
    if (document.getElementById('tabMap')?.classList.contains('active')) {
      ensureMap();
      renderMapSidebar(boardSnapshot?.lines || []);
    }
    saveUiState();
  }

  function reportMatchesLine(report, line) {
    const blob = [report.entity, report.location, report.headline, report.summary].join(' ').toLowerCase();
    const tokens = [line.name, ...(line.name.split(/[/,&]/))].map(s => s.trim().toLowerCase()).filter(Boolean);
    return tokens.some(t => t.length > 3 && blob.includes(t));
  }

  function lineMatchesPlace(line, needle) {
    const blob = [line.name, line.route, line.reason, line.region, line.operator, line.id.replace(/-/g, ' ')].join(' ').toLowerCase();
    if (blob.includes(needle)) return true;
    const station = stationCatalog.find(s => s.label.toLowerCase() === needle || s.token === needle);
    if (station && blob.includes(station.token)) return true;
    const reports = boardSnapshot?.recent_reports || boardData?.recent_reports || [];
    return reports.some(r => reportMatchesPlace(r, needle) && reportMatchesLine(r, line));
  }

  function sortLines(lines) {
    const copy = [...lines];
    if (activeSort === 'severity') {
      copy.sort((a, b) => {
        const diff = (SEVERITY_RANK[b.status] || 0) - (SEVERITY_RANK[a.status] || 0);
        if (diff !== 0) return diff;
        return (b.report_count || 0) - (a.report_count || 0);
      });
    } else if (activeSort === 'freshest') {
      copy.sort((a, b) => {
        const ta = parseTs(a.last_seen_at)?.getTime() || 0;
        const tb = parseTs(b.last_seen_at)?.getTime() || 0;
        return tb - ta;
      });
    } else if (activeSort === 'reports') {
      copy.sort((a, b) => (b.report_count || 0) - (a.report_count || 0));
    }
    return copy;
  }

  function reportMatchesPlace(report, needle) {
    const blob = [report.entity, report.location, report.headline, report.summary].join(' ').toLowerCase();
    return blob.includes(needle);
  }

  function filteredReports(reports) {
    if (!placeFilter) return reports;
    const needle = placeFilter.toLowerCase();
    return reports.filter(r => reportMatchesPlace(r, needle));
  }

  function renderRouteLegend(lines) {
    const el = $('routeLegend');
    if (!el) return;
    el.hidden = true;
    el.innerHTML = '';
  }

  function renderLineLegendGrid(lines) {
    const el = $('lineLegendGrid');
    if (!el || !lines?.length) return;
    el.innerHTML = lines
      .filter(l => l.mode === 'rail' || LINE_COLORS[l.id])
      .map(l => `
        <button type="button" class="legend-chip" data-line-id="${esc(l.id)}" title="${esc(l.where_it_goes || l.name)}">
          <span class="legend-dot" style="background:${esc(l.official_colour || LINE_COLORS[l.id] || '#6b6660')}"></span>
          ${esc(l.name.replace(/^LRT /, '').replace(/ Line$/, ''))}
        </button>`)
      .join('');
  }

  function serviceHintHtml(lineId) {
    const ref = linesReferenceById[lineId];
    const svc = ref?.service_status_now;
    if (!svc || !svc.label) return '';
    if (['before_service', 'after_service', 'not_operating'].includes(svc.status)) {
      return `<span class="service-hint ${esc(svc.status)}">${esc(svc.label)}</span>`;
    }
    return '';
  }

  function weekendPillHtml(lineId) {
    const day = new Date().getDay();
    if (day !== 0 && day !== 6) return '';
    const note = linesReferenceById[lineId]?.operating_hours?.weekend_note;
    if (!note) return '';
    return `<span class="schedule-pill" title="${esc(note)}">Weekend</span>`;
  }

  function delayMinHtml(line) {
    if (!['delay', 'disruption'].includes(line.status)) return '';
    const match = (line.reason || '').match(/(\d+)\s*min/i);
    if (match) return `<span class="delay-min">+${esc(match[1])} min</span>`;
    return '';
  }

  function _parse_hm(str) {
    if (!str) return null;
    const match = str.trim().match(/^(\d{1,2}):(\d{2})$/);
    if (!match) return null;
    return { hour: parseInt(match[1], 10), minute: parseInt(match[2], 10) };
  }

  function computeClientServiceStatus(oh) {
    if (!oh || !oh.first_train || !oh.last_train) {
      return { status: 'unknown', label: pickLang('Hours not available', 'Waktu tidak tersedia'), in_service: null };
    }
    const mytNow = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Kuala_Lumpur' }));
    const nowMin = mytNow.getHours() * 60 + mytNow.getMinutes();

    const first = _parse_hm(oh.first_train);
    const last = _parse_hm(oh.last_train);
    if (!first || !last) {
      return { status: 'unknown', label: pickLang('Hours not available', 'Waktu tidak tersedia'), in_service: null };
    }

    const firstMin = first.hour * 60 + first.minute;
    let lastMin = last.hour * 60 + last.minute;
    if (lastMin <= firstMin) lastMin += 1440;

    let testNowMin = nowMin;
    if (testNowMin < firstMin && lastMin > 1440) {
      testNowMin += 1440;
    }

    const timeToLast = lastMin - testNowMin;
    if (timeToLast > 0 && timeToLast <= 30) {
      return {
        status: 'warning',
        label: pickLang(`LAST TRAIN IN ${timeToLast} MIN`, `TREN TERAKHIR DALAM ${timeToLast} MIN`),
        in_service: true,
        last_train_warning: true,
        next_change_min: timeToLast
      };
    }

    if (testNowMin < firstMin) {
      const diff = firstMin - testNowMin;
      return {
        status: 'before_service',
        label: pickLang(`Starts in ${diff} min`, `Mula dalam ${diff} min`),
        in_service: false,
        next_change_min: diff
      };
    }
    if (testNowMin > lastMin) {
      return {
        status: 'after_service',
        label: pickLang('Service ended', 'Perkhidmatan tamat'),
        in_service: false
      };
    }

    for (const peak of oh.peak_hours || []) {
      const start = _parse_hm(peak.start);
      const end = _parse_hm(peak.end);
      if (start && end) {
        let ps = start.hour * 60 + start.minute;
        let pe = end.hour * 60 + end.minute;
        if (ps < firstMin) ps += 1440;
        if (pe < firstMin) pe += 1440;

        if (ps <= testNowMin && testNowMin <= pe) {
          const diff = pe - testNowMin;
          const headway = peak.headway_min;
          const freq = headway ? `~${headway} min` : 'Peak';
          return {
            status: 'peak',
            label: pickLang(`Peak · ${freq} (ends in ${diff}m)`, `Puncak · ${freq} (tamat ${diff}m)`),
            in_service: true,
            next_change_min: diff
          };
        }
      }
    }

    let nextEventMin = lastMin;
    for (const peak of oh.peak_hours || []) {
      const start = _parse_hm(peak.start);
      if (start) {
        let ps = start.hour * 60 + start.minute;
        if (ps < firstMin) ps += 1440;
        if (ps > testNowMin && ps < nextEventMin) {
          nextEventMin = ps;
        }
      }
    }

    const diff = nextEventMin - testNowMin;
    const isNextPeak = nextEventMin < lastMin;
    const labelSuffix = isNextPeak 
      ? pickLang(`peak in ${diff}m`, `puncak dlm ${diff}m`)
      : pickLang(`ends in ${diff}m`, `tamat dlm ${diff}m`);

    const offPeakFreq = oh.off_peak_headway_min ? ` ~${oh.off_peak_headway_min}m` : '';
    return {
      status: 'off_peak',
      label: pickLang(`Off-peak${offPeakFreq} (${labelSuffix})`, `Luar Puncak${offPeakFreq} (${labelSuffix})`),
      in_service: true,
      next_change_min: diff
    };
  }

  function renderHoursTimeline(hours, svc) {
    if (!hours || !hours.first_train || !hours.last_train) return '';
    const first = _parse_hm(hours.first_train);
    const last = _parse_hm(hours.last_train);
    if (!first || !last) return '';

    const firstMin = first.hour * 60 + first.minute;
    let lastMin = last.hour * 60 + last.minute;
    if (lastMin <= firstMin) lastMin += 1440;

    const totalMin = lastMin - firstMin;
    if (totalMin <= 0) return '';

    const zones = [];
    (hours.peak_hours || []).forEach(p => {
      const start = _parse_hm(p.start);
      const end = _parse_hm(p.end);
      if (start && end) {
        let sMin = start.hour * 60 + start.minute;
        let eMin = end.hour * 60 + end.minute;
        if (sMin < firstMin) sMin += 1440;
        if (eMin < firstMin) eMin += 1440;
        if (sMin >= firstMin && eMin <= lastMin) {
          const leftPct = ((sMin - firstMin) / totalMin) * 100;
          const widthPct = ((eMin - sMin) / totalMin) * 100;
          zones.push({ label: p.label || 'Peak', left: leftPct, width: widthPct, cls: 'timeline-zone--peak' });
        }
      }
    });

    const mytNow = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Kuala_Lumpur' }));
    let curMin = mytNow.getHours() * 60 + mytNow.getMinutes();
    if (curMin < firstMin && lastMin > 1440) {
      curMin += 1440;
    }

    let indicatorHtml = '';
    if (curMin >= firstMin && curMin <= lastMin) {
      const curPct = ((curMin - firstMin) / totalMin) * 100;
      indicatorHtml = `<div class="hours-timeline-now" style="left: ${curPct}%" title="Now (${mytNow.getHours().toString().padStart(2,'0')}:${mytNow.getMinutes().toString().padStart(2,'0')})"></div>`;
    }

    const zonesHtml = zones.map(z => 
      `<div class="hours-timeline-zone ${z.cls}" style="left: ${z.left}%; width: ${z.width}%" title="${esc(z.label)}"></div>`
    ).join('');

    return `
      <div class="hours-timeline-container">
        <div class="hours-timeline-labels">
          <span>${esc(hours.first_train)}</span>
          <span class="timeline-middle-label">${pickLang('Active Timeline', 'Garis Masa Perkhidmatan')}</span>
          <span>${esc(hours.last_train)}</span>
        </div>
        <div class="hours-timeline-track">
          <div class="hours-timeline-fill" style="width: ${curMin >= firstMin && curMin <= lastMin ? ((curMin - firstMin) / totalMin * 100).toFixed(0) : 0}%"></div>
          ${zonesHtml}
          ${indicatorHtml}
        </div>
      </div>
    `;
  }

  function renderKeyInterchanges(interchanges) {
    if (!interchanges?.length) return '';
    const keyIxs = interchanges.slice(0, 4);
    const items = keyIxs.map(ix => {
      const walk = ix.transfer_walk_min ? `<span class="key-ix-walk">🚶 ${esc(ix.transfer_walk_min)}m</span>` : '';
      const chips = (ix.line_colours || []).map(lc => {
        const shortName = lc.short_name || lc.name || lc.label || '';
        const miniName = shortName.replace(/LRT |MRT |KTM /, '').replace(/ Line$/, '');
        return `<span class="ix-line-chip" style="--chip-color:${esc(lc.color || '#64748b')}">${esc(miniName)}</span>`;
      }).join('');
      return `
        <div class="key-ix-item">
          <div class="key-ix-station-row">
            <strong class="key-ix-station-name">${esc(ix.station)}</strong>
            ${walk}
          </div>
          <div class="key-ix-lines">${chips || `<span class="ix-connects">${esc(ix.connects_to || 'Other lines')}</span>`}</div>
        </div>
      `;
    }).join('');

    return `
      <div class="guide-section guide-section--key-interchanges">
        <h3>${pickLang('Key Interchanges', 'Pertukaran Utama')}</h3>
        <div class="key-interchanges-grid">
          ${items}
        </div>
      </div>
    `;
  }

  function renderStationList(stations, interchanges, color) {
    if (!stations?.length) {
      return '<p style="color:var(--text-dim);font-size:12px">Station list not available yet.</p>';
    }
    const ixByName = {};
    (interchanges || []).forEach(ix => {
      if (ix.station) ixByName[String(ix.station).toLowerCase()] = ix;
    });
    const lookupIx = name => {
      const n = String(name).toLowerCase();
      if (ixByName[n]) return ixByName[n];
      return Object.entries(ixByName).find(([k]) => n.includes(k) || k.includes(n))?.[1];
    };
    return `<ol class="station-list" style="--line-color:${esc(color)}">${stations.map(name => {
      const ix = lookupIx(name);
      let changeHint = '';
      if (ix) {
        const chips = (ix.line_colours || []).map(lc => {
          const shortName = lc.short_name || lc.name || lc.label || '';
          const miniName = shortName.replace(/LRT |MRT |KTM /, '').replace(/ Line$/, '');
          return `<span class="ix-line-chip" style="--chip-color:${esc(lc.color || '#64748b')}">${esc(miniName)}</span>`;
        }).join('');
        const walk = ix.transfer_walk_min ? `<span class="station-walk-hint">🚶 ${esc(ix.transfer_walk_min)}m</span>` : '';
        changeHint = `<div class="station-interchange-info">${chips}${walk}</div>`;
      }
      return `<li class="station-item${ix ? ' interchange' : ''}">
        <span class="station-rail" aria-hidden="true"></span>
        <div class="station-item-content">
          <span class="station-name">${esc(name)}</span>
          ${changeHint}
        </div>
      </li>`;
    }).join('')}</ol>`;
  }

  function openSchematicModal(src, alt) {
    const modal = $('schematicModal');
    const img = $('schematicModalImg');
    if (!modal || !img) return;
    img.src = src;
    img.alt = alt || 'Route diagram';
    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');
    $('schematicModalClose')?.focus();
  }

  function closeSchematicModal() {
    const modal = $('schematicModal');
    if (!modal) return;
    modal.hidden = true;
    modal.setAttribute('aria-hidden', 'true');
    $('schematicModalImg').src = '';
  }

  function interchangeMetaHtml(lineId) {
    const count = linesReferenceById[lineId]?.interchange_count;
    if (!count) return '';
    return `<div class="interchange-meta">${count} interchange${count === 1 ? '' : 's'}</div>`;
  }

  function renderInterchangeSection(interchanges) {
    if (!interchanges?.length) {
      return '<p class="guide-empty-hint">No interchange data for this line yet.</p>';
    }
    return `<div class="interchange-list">${interchanges.map(ix => {
      const chips = (ix.line_colours || []).map(lc =>
        `<span class="ix-line-chip" style="--chip-color:${esc(lc.color || '#64748b')}">${esc(lc.short_name || lc.name || lc.label || '')}</span>`
      ).join('');
      const walk = ix.transfer_walk_min
        ? `<span class="ix-walk">~${esc(ix.transfer_walk_min)} min walk</span>` : '';
      return `<div class="interchange-row">
        <div class="ix-row-top">
          <strong class="ix-station">${esc(ix.station)}</strong>
          ${walk}
        </div>
        <div class="ix-chips">${chips || `<span class="ix-connects">${esc(ix.connects_to || 'Other lines')}</span>`}</div>
        ${ix.walking_note ? `<p class="ix-note">${esc(ix.walking_note)}</p>` : ''}
      </div>`;
    }).join('')}</div>`;
  }

  const HOURS_STATUS_META = {
    peak: { cls: 'hours-now--peak', icon: '🔴' },
    off_peak: { cls: 'hours-now--running', icon: '🟢' },
    before_service: { cls: 'hours-now--upcoming', icon: '🕐' },
    after_service: { cls: 'hours-now--ended', icon: '⚪' },
    not_operating: { cls: 'hours-now--upcoming', icon: '🕐' },
    warning: { cls: 'schedule-svc--warning', icon: '⚠️' },
    unknown: { cls: 'hours-now--unknown', icon: '' },
  };

  function renderHoursSection(hours, svc) {
    if (!hours) return '<p class="guide-empty-hint">Operating hours not published for this line.</p>';
    const meta = HOURS_STATUS_META[svc?.status] || HOURS_STATUS_META.unknown;
    const nowChip = svc?.label
      ? `<div class="hours-now-chip ${meta.cls}">${meta.icon ? `<span aria-hidden="true">${meta.icon}</span>` : ''}${esc(svc.label)}</div>`
      : '';
    const peakIcons = { 'Morning Peak': '🌅', 'Evening Peak': '🌆', 'Morning peak': '🌅', 'Evening peak': '🌆' };
    const peakRows = (hours.peak_hours || []).map(p => {
      const label = p.label || 'Peak';
      return `<div class="hours-peak-row">
        <span class="hours-peak-icon" aria-hidden="true">${peakIcons[label] || '⏱'}</span>
        <span class="hours-peak-label">${esc(label)}</span>
        <span class="hours-peak-time">${esc(p.start)}–${esc(p.end)}</span>
        ${p.headway_min ? `<span class="hours-peak-headway">~${esc(p.headway_min)} min</span>` : ''}
      </div>`;
    }).join('');
    const timelineHtml = renderHoursTimeline(hours, svc);
    return `<div class="guide-hours">
      ${nowChip}
      ${timelineHtml}
      <div class="hours-grid">
        <div class="hours-stat"><span class="hours-stat-label">First train</span><span class="hours-stat-value">${esc(hours.first_train)} MYT</span></div>
        <div class="hours-stat"><span class="hours-stat-label">Last train</span><span class="hours-stat-value">${esc(hours.last_train)} MYT</span></div>
      </div>
      ${hours.days ? `<p class="hours-days">${esc(hours.days)}</p>` : ''}
      ${peakRows ? `<div class="hours-peak-list">${peakRows}</div>` : ''}
      ${hours.off_peak_headway_min ? `<div class="hours-peak-row hours-peak-row--offpeak"><span class="hours-peak-icon" aria-hidden="true">⏱</span><span class="hours-peak-label">Off-peak</span><span class="hours-peak-headway">~${esc(hours.off_peak_headway_min)} min headway</span></div>` : ''}
      ${hours.disclaimer ? `<p class="hours-disclaimer">${esc(hours.disclaimer)}</p>` : ''}
    </div>`;
  }

  function renderLineHistorySection(history, color) {
    if (!history || !history.daily_counts?.length) return '';
    const days = history.daily_counts;
    const max = Math.max(1, ...days.map(d => d.count));
    const bars = days.map(d => {
      const pct = Math.round((d.count / max) * 100);
      const isToday = d.date === history.today?.date;
      return `<div class="history-bar-wrap" title="${esc(d.weekday)} ${esc(d.date)} — ${d.count} signal${d.count === 1 ? '' : 's'}">
        <div class="history-bar${isToday ? ' history-bar--today' : ''}" style="height:${Math.max(pct, d.count ? 6 : 2)}%;background:${esc(color)}"></div>
        <span class="history-bar-label">${esc(d.weekday[0])}</span>
      </div>`;
    }).join('');
    const cmp = history.today?.comparison;
    const cmpCopy = {
      elevated: { label: pickLang('More signals than usual', 'Lebih isyarat dari biasa'), cls: 'history-cmp--elevated' },
      typical: { label: pickLang('Typical for today', 'Normal untuk hari ini'), cls: 'history-cmp--typical' },
      quieter_than_usual: { label: pickLang('Quieter than usual', 'Lebih senyap dari biasa'), cls: 'history-cmp--quiet' },
      no_baseline: { label: pickLang('Not enough history yet', 'Sejarah tidak mencukupi lagi'), cls: 'history-cmp--unknown' },
    }[cmp] || { label: '', cls: '' };
    const typical = history.today?.typical_for_weekday;
    const compareLine = typical != null
      ? pickLang(
          `${history.today.count} today vs ~${typical} typical for ${history.today.weekday}`,
          `${history.today.count} hari ini vs ~${typical} biasa untuk ${history.today.weekday}`
        )
      : pickLang('Building baseline from the last 2 weeks.', 'Membina asas dari 2 minggu lepas.');
    return `<div class="guide-section guide-section--history">
      <h3>${pickLang('Is this normal?', 'Adakah ini normal?')}</h3>
      <div class="history-chart">${bars}</div>
      <div class="history-summary">
        ${cmpCopy.label ? `<span class="history-cmp ${cmpCopy.cls}">${esc(cmpCopy.label)}</span>` : ''}
        <span class="history-compare-line">${esc(compareLine)}</span>
      </div>
      <p class="history-hint">${pickLang('Rider signal volume over the last 14 days — not official ridership stats.', 'Jumlah isyarat penumpang 14 hari lepas — bukan statistik penumpang rasmi.')}</p>
    </div>`;
  }

  async function openLineGuide(lineId, opts = {}) {
    const { clusterId, label, status } = opts;
    const lineName = label || linesReferenceById[lineId]?.name || lineId;
    $('panelTitle').textContent = lineName;
    const statusLabels = { unknown: 'No current signal', minor: 'Minor', delay: 'Delay', disruption: 'Disruption' };
    const svc = linesReferenceById[lineId]?.service_status_now;
    const svcBadge = svc?.label && ['before_service', 'after_service', 'not_operating', 'warning'].includes(svc.status)
      ? `<span class="service-hint ${esc(svc.status)}">${esc(svc.label)}</span>` : '';
    $('panelSub').innerHTML = status && statusLabels[status]
      ? `<span class="badge ${esc(status)}" style="display:inline-block;min-width:auto">${esc(statusLabels[status])}</span>${svcBadge}`
      : svcBadge;
    $('panelBody').innerHTML = '<div class="skel-row"><div style="flex:1"><div class="skel skel-text"></div><div class="skel skel-text short" style="margin-top:8px"></div></div></div>';
    showPanel();
    try {
      const [res, historyRes] = await Promise.all([
        fetch(api(`/api/trafficmy/lines/${encodeURIComponent(lineId)}/info`)),
        fetch(api(`/api/trafficmy/lines/${encodeURIComponent(lineId)}/history`)).catch(() => null),
      ]);
      if (!res.ok) throw new Error('not found');
      const info = await res.json();
      const history = historyRes && historyRes.ok ? await historyRes.json().catch(() => null) : null;
      const ref = info.reference || {};
      const live = info.status || {};
      const schematic = info.schematic_url ? staticUrl(info.schematic_url.replace(/^\/static\//, '')) : '';
      const endpoints = ref.endpoints ? `${esc(ref.endpoints.from)} → ${esc(ref.endpoints.to)}` : esc(ref.where_it_goes || '');
      const reportBtn = (clusterId || live.top_cluster_id)
        ? `<button type="button" class="guide-btn primary" data-open-cluster="${esc(clusterId || live.top_cluster_id)}" data-line-label="${esc(lineName)}" data-line-status="${esc(status || live.status || '')}">View reports</button>`
        : '';
      const color = LINE_COLORS[lineId] || ref.official_colour || '#64748b';
      const stations = info.stations_ordered || ref.stations_ordered || [];
      const interchangeHtml = renderInterchangeSection(ref.interchanges);
      const activeStatuses = ['minor', 'delay', 'disruption'];
      const lineQuiet = !activeStatuses.includes(live.status) && live.in_service !== false;
      const filteredRiders = (info.rider_reports || []).filter(r => {
        if (!lineQuiet) return true;
        if (!r.last_seen_at) return false;
        return (Date.now() - new Date(r.last_seen_at).getTime()) < 2 * 3600000;
      });
      const riders = filteredRiders.map(r => `
        <div class="ev" style="margin-bottom:8px">
          <div class="ev-text"><strong>${esc(r.headline || 'Rider signal')}</strong><br>${esc(r.summary || '')}</div>
          <div class="ev-meta" style="margin-top:6px"><span title="${r.last_seen_at ? esc(fmtMYT(r.last_seen_at)) + ' MYT' : ''}">${r.last_seen_at ? esc(relTime(r.last_seen_at)) : ''}</span>${r.from_threads ? ' · Threads' : ''}${r.example_url ? ` · <a href="${esc(r.example_url)}" target="_blank" rel="noopener noreferrer">Source</a>` : ''}</div>
        </div>`).join('');

      const stationListSection = `<div class="guide-section guide-section--stations">
        <details class="guide-stations-details" ${schematic ? '' : 'open'}>
          <summary class="guide-stations-summary">
            <h3>${pickLang(`Stations (${stations.length || '—'})`, `Stesen (${stations.length || '—'})`)}</h3>
            <span class="guide-stations-chevron">▼</span>
          </summary>
          <div class="guide-stations-content" style="margin-top:10px">
            ${renderStationList(stations, ref.interchanges, color)}
          </div>
        </details>
      </div>`;

      const schematicSection = schematic
        ? `<div class="guide-section guide-section--schematic">
          <h3>Route diagram</h3>
          <p class="guide-schematic-hint">${pickLang('Tap to enlarge · dots mark interchange stations', 'Ketik untuk besarkan · titik menandakan pertukaran')}</p>
          <div class="guide-schematic-wrap"><img class="guide-schematic schematic-zoomable" src="${esc(schematic)}" alt="${esc(lineName)} route diagram" loading="lazy"></div>
        </div>
        ${stationListSection}`
        : stationListSection;

      const keyInterchangesSection = ref.interchanges?.length
        ? renderKeyInterchanges(ref.interchanges)
        : '';
      const interchangeSection = ref.interchanges?.length
        ? `<div class="guide-section guide-section--interchanges"><h3>All Interchanges</h3>${interchangeHtml}</div>`
        : '';
      const riderSection = riders
        ? `<div class="guide-section"><h3>Rider pulse</h3>${riders}</div>`
        : '';
      const historySection = renderLineHistorySection(history, color);
      const statParts = [];
      if (ref.length_km) statParts.push(pickLang(`${ref.length_km} km`, `${ref.length_km} km`));
      if (ref.stations_count) statParts.push(pickLang(`${ref.stations_count} stations`, `${ref.stations_count} stesen`));
      if (ref.journey_minutes) statParts.push(pickLang(`~${ref.journey_minutes} min end-to-end`, `~${ref.journey_minutes} min hujung ke hujung`));
      const statChips = statParts.map(part => `<span class="guide-stat-chip">${esc(part)}</span>`).join('');
      const statLine = statParts.length ? `<div class="guide-stat-chips">${statChips}</div>` : '';
      const capacityLine = ref.capacity_note ? `<p class="guide-capacity-line">${esc(ref.capacity_note)}</p>` : '';
      $('panelBody').innerHTML = `
        ${riderSection}
        ${keyInterchangesSection}
        ${historySection}
        ${schematicSection}
        ${interchangeSection}
        <div class="guide-section guide-section--facts">
          <h3>Route &amp; facts</h3>
          <p class="guide-endpoints">${endpoints}</p>
          ${statLine}
          ${capacityLine}
          <p class="guide-source-note">${pickLang('Public rider posts &amp; operator references — not live headway data.', 'Laporan penumpang awam &amp; rujukan operator — bukan data selang masa langsung.')}</p>
        </div>
        <div class="guide-section">
          <h3>Operating hours</h3>
          ${renderHoursSection(info.operating_hours, info.service_status_now || svc)}
        </div>
        ${(info.social_info || []).length ? `<div class="guide-section"><h3>Line notices</h3>${info.social_info.map(s => `<div class="ev" style="margin-bottom:8px"><div class="ev-text"><strong>${esc(s.headline || 'Line notice')}</strong><br>${esc(s.summary || '')}</div><div class="ev-meta" style="margin-top:6px">${s.last_seen_at ? esc(relTime(s.last_seen_at)) : ''}</div></div>`).join('')}</div>` : ''}
        <div class="guide-actions">
          ${reportBtn}
          ${info.timetable_url ? `<a class="guide-btn" href="${esc(info.timetable_url)}" target="_blank" rel="noopener noreferrer">Official timetable</a>` : ''}
          <button type="button" class="guide-btn" data-filter-station="${esc(ref.endpoints?.from || '')}">Filter board</button>
        </div>`;
      $('panelBody').querySelector('[data-open-cluster]')?.addEventListener('click', e => {
        const btn = e.currentTarget;
        openPanel(btn.dataset.openCluster, btn.dataset.lineLabel, btn.dataset.lineStatus);
      });
      $('panelBody').querySelector('[data-filter-station]')?.addEventListener('click', e => {
        const station = e.currentTarget.dataset.filterStation;
        if (station) { closePanel(); switchTab('status'); setPlaceFilter(station); }
      });
    } catch {
      $('panelBody').innerHTML = '<div class="error-state"><strong>Line guide unavailable</strong><p>Reference data could not be loaded.</p></div>';
    }
  }

  function openGlossary() {
    const glossary = boardData?.legend?.glossary || [];
    $('panelTitle').textContent = 'Status glossary';
    $('panelSub').innerHTML = '';
    $('panelBody').innerHTML = glossary.length
      ? glossary.map(g => `<div class="guide-gloss"><strong>${esc(g.term)}</strong><p>${esc(g.meaning)}</p></div>`).join('')
      : '<p>Glossary not loaded.</p>';
    showPanel();
  }

  function setPlaceFilter(label) {
    placeFilter = (label || '').trim();
    syncSearchInputs(placeFilter);
    const banner = $('filterBanner');
    if (banner) {
      banner.classList.toggle('show', !!placeFilter);
      $('filterLabel').textContent = placeFilter;
    }
    updateFilterChips();
    renderBoard();
    if (boardSnapshot) renderReports(boardSnapshot.recent_reports || []);
    if (mapInstance && document.getElementById('tabMap')?.classList.contains('active')) {
      ensureMap();
    }
    saveUiState();
  }

  async function loadStationCatalog() {
    try {
      const res = await fetchWithTimeout(api('/api/trafficmy/stations?limit=50'));
      if (res.ok) stationCatalog = (await res.json()).items || [];
    } catch { /* optional */ }
  }

  async function searchPlaces(query) {
    const list = $('searchSuggestions');
    if (!query || query.length < 2) {
      list?.classList.remove('open');
      if (list) list.innerHTML = '';
      return;
    }
    try {
      const params = new URLSearchParams({ q: query, limit: '8' });
      const res = await fetchWithTimeout(api(`/api/trafficmy/stations?${params}`), 8000);
      if (!res.ok) return;
      const items = (await res.json()).items || [];
      if (!list) return;
      list.innerHTML = !items.length
        ? '<div class="search-item" style="cursor:default;color:var(--text-dim)">No stations found</div>'
        : items.map(item =>
          `<button type="button" class="search-item" data-label="${esc(item.label)}">${esc(item.label)}${item.state ? `<small>${esc(item.state)}</small>` : ''}</button>`
        ).join('');
      list.classList.add('open');
    } catch { /* ignore */ }
  }

  function queuePlaceSearch(value) {
    clearTimeout(placeSearchTimer);
    placeSearchTimer = setTimeout(() => searchPlaces(value), 220);
  }

  function switchTab(tabId) {
    document.querySelectorAll('.main-tab').forEach(btn => {
      const active = btn.dataset.tab === tabId;
      btn.classList.toggle('active', active);
      btn.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    document.querySelectorAll('.bottom-nav-btn').forEach(btn => {
      const active = btn.dataset.tab === tabId;
      btn.classList.toggle('active', active);
      btn.classList.toggle('stitch-nav-item--active', active);
      btn.setAttribute('aria-current', active ? 'page' : 'false');
    });
    document.querySelectorAll('.tab-panel').forEach(panel => {
      const id = tabId.charAt(0).toUpperCase() + tabId.slice(1);
      const active = panel.id === `tab${id}`;
      panel.classList.toggle('active', active);
      panel.hidden = !active;
    });
    $('pulseHero').hidden = tabId !== 'status';
    const glance = $('glanceCard');
    if (glance) glance.hidden = tabId !== 'status';
    if (tabId === 'map') {
      syncMapLayersFromHomeFilter();
      renderMapSidebar(boardData?.lines || []);
      setTimeout(() => {
        ensureMap().then(() => {
          renderMapFloatCard(boardSnapshot?.lines || boardData?.lines || []);
          mapInstance?.resize();
        });
      }, 80);
    }
    if (tabId === 'travel') {
      updateStationOptions();
      if (!$('updatesGrid')?.children?.length) loadUpdates();
      compareSavings();
    }
    history.replaceState(null, '', `#${tabId}`);
    saveUiState();
  }

  function renderBoardSummary(data) {
    const el = $('glanceCard') || $('boardSummary');
    if (!el) return;
    const summary = data.board_summary || '';
    const active = data.active_alert_count ?? data.active_line_count ?? 0;
    const ok = active === 0;
    const lines = data.lines || boardSnapshot?.lines || [];
    if (!summary && !data.lines_tracked_count) {
      el.className = 'play-glance stitch-glance play-glance--ok';
      el.innerHTML = `
        <div class="stitch-glance-copy">
          <strong>${pickLang('Loading', 'Memuatkan')}</strong>
          <span>${pickLang('Checking lines · today MYT', 'Menyemak laluan · hari ini MYT')}</span>
        </div>`;
      return;
    }
    el.className = `play-glance stitch-glance play-glance--${ok ? 'ok' : 'alert'}`;
    const title = ok
      ? pickLang('No active signals', 'Tiada isyarat aktif')
      : pickLang(`${active} line${active === 1 ? '' : 's'} with reports`, `${active} laluan dengan laporan`);
    const sub = ok
      ? pickLang('Quiet ≠ all-clear · today MYT', 'Tenang ≠ lancar · hari ini MYT')
      : esc(summary);
    const chips = ok ? '' : glanceModeChips(lines);
    el.innerHTML = `
      <div class="stitch-glance-copy">
        <strong>${title}</strong>
        <span>${sub}</span>
        ${chips ? `<div class="stitch-glance-chips">${chips}</div>` : ''}
      </div>`;
    const trust = $('trustLine');
    if (trust) {
      trust.innerHTML = pickLang(
        'Rider signals today · quiet ≠ all-clear · <a href="' + methodUrl + '">Method</a>',
        'Isyarat penumpang hari ini · tenang ≠ lancar · <a href="' + methodUrl + '">Kaedah</a>'
      );
    }
  }

  function renderStatsBar(data, status) {
    const el = $('statsBar');
    if (!el) return;
    const total = data.lines_tracked_count ?? (data.lines || []).length;
    const modes = data.modes_breakdown || {};
    const rail = modes.rail ?? (data.lines || []).filter(l => l.mode === 'rail').length;
    const bus = modes.bus ?? (data.lines || []).filter(l => l.mode === 'bus').length;
    const active = data.active_alert_count ?? data.active_line_count ?? 0;
    const windowHours = data.status_window_hours || 24;
    const latest = status?.freshness?.latest_created_at || status?.freshness?.latest_inserted_at;
    const updatedMYT = latest ? fmtMYT(latest) : '—';

    const actAll = activeFilter === 'all' ? ' active' : '';
    const actRail = activeFilter === 'rail' ? ' active' : '';
    const actBus = activeFilter === 'bus' ? ' active' : '';

    el.innerHTML = `
      <div class="stats-bar-wrap">
        <button type="button" class="stat-pill-btn${actAll}" id="statBtnAll" title="Show all lines">
          <strong>${total}</strong>
          lines
        </button>
        <button type="button" class="stat-pill-btn${actRail}" id="statBtnRail" title="Filter by rail lines">
          <strong>${rail}</strong>
          rail
        </button>
        <button type="button" class="stat-pill-btn${active > 0 ? ' alert-active' : ''}" id="statBtnAlerts" title="What these numbers mean">
          <strong>${active}</strong>
          alerts
        </button>
      </div>
      <span class="countdown sr-only" id="countdown">Refresh ${Math.floor(COUNTDOWN_SEC / 60)}:00</span>`;

    $('statBtnAll')?.addEventListener('click', () => setActiveFilter('all'));
    $('statBtnRail')?.addEventListener('click', () => setActiveFilter('rail'));
    $('statBtnBus')?.addEventListener('click', () => setActiveFilter('bus'));
    $('statBtnAlerts')?.addEventListener('click', () => openStatsExplain({ total, rail, bus, active, windowHours, updatedMYT }));
  }

  function openStatsExplain({ total, rail, bus, active, windowHours, updatedMYT }) {
    $('panelTitle').textContent = 'What these numbers mean';
    $('panelSub').innerHTML = '';
    $('panelBody').innerHTML = `
      <p><strong>${total} lines tracked</strong> — operating rail and bus services across Malaysia on this board (planned future lines are listed separately).</p>
      <p><strong>${rail} rail · ${bus} bus</strong> — mode split. Rail includes LRT, MRT, monorail, KTM and airport rail. Bus covers Rapid KL and regional networks.</p>
      <p><strong>${active} active alert${active === 1 ? '' : 's'}</strong> — lines with delay or disruption reports in the last <strong>${windowHours}h</strong>. Zero means no qualifying recent reports, not confirmed normal service.</p>
      <p><strong>Status</strong> = crowd-reported delays from Threads, Reddit and news — not the official RapidKL/KTMB status page.</p>
      <p style="margin-top:12px;color:var(--text-dim);font-size:12px">Last data update: ${esc(updatedMYT)} MYT</p>`;
    showPanel();
  }

  function renderSummary(data, status) {
    renderStatsBar(data, status);
    renderBoardSummary(data);
    renderRiskStrip(data.lines || []);
    const ss = $('summaryStrip');
    if (ss) {
      ss.hidden = true;
      ss.setAttribute('aria-hidden', 'true');
    }
  }

  const SCHEMATIC_FILTER_LINES = {
    lrt: ['kelana-jaya', 'ampang-sri-petaling', 'lrt3', 'lrt3-shah-alam'],
    mrt: ['kajang', 'putrajaya'],
    monorail: ['monorail'],
    ktm: ['ktm-komuter', 'ktm', 'ktm-north', 'ets-intercity', 'klia-rail', 'sabah-railway'],
  };

  function schematicLineMatchesFilter(lineId) {
    const filter = activeFilter;
    if (!lineId) return false;
    if (filter === 'all' || filter === 'rail') return true;
    if (filter === 'lrt') {
      return SCHEMATIC_FILTER_LINES.lrt.includes(lineId) || lineId.startsWith('lrt3');
    }
    if (filter === 'mrt') return SCHEMATIC_FILTER_LINES.mrt.includes(lineId);
    if (filter === 'monorail') return lineId === 'monorail';
    if (filter === 'ktm') {
      return lineId.startsWith('ktm') || SCHEMATIC_FILTER_LINES.ktm.includes(lineId);
    }
    return false;
  }

  let schematicLoaded = false;
  let schematicLoading = false;
  async function initSchematic() {
    if (schematicLoaded || schematicLoading) return;
    schematicLoading = true;
    const stage = $('schematicStage');
    const loading = $('schematicLoading');
    try {
      const res = await fetch(staticUrl('lines/kv-system.svg'));
      if (!res.ok) throw new Error('fetch failed');
      let svgText = await res.text();
      svgText = svgText.replace(/<\?xml[^>]*\?>/i, '');
      const temp = document.createElement('div');
      temp.innerHTML = svgText;
      const svgEl = temp.querySelector('svg');
      if (svgEl && stage) {
        svgEl.id = 'kvSchematic';
        svgEl.classList.add('kv-schematic', 'tm-kv-schematic');
        loading?.remove();
        stage.appendChild(svgEl);
        schematicLoaded = true;
        updateSchematicHighlights();
      }
    } catch (e) {
      if (loading) loading.textContent = pickLang('Schematic unavailable', 'Gambar rajah tidak tersedia');
      console.error('Failed to load system schematic:', e);
    } finally {
      schematicLoading = false;
    }
  }

  function updateSchematicHighlights() {
    const svg = $('kvSchematic');
    if (!svg) return;
    const statusByLine = Object.fromEntries((boardSnapshot?.lines || []).map(l => [l.id, l.status]));

    svg.querySelectorAll('[data-line-id]').forEach(el => {
      const lineId = el.dataset.lineId;
      const visible = schematicLineMatchesFilter(lineId);
      el.classList.toggle('schem-filtered-out', !visible);
      el.classList.remove('schem-active', 'schem-minor', 'schem-delay', 'schem-disruption');
      if (!visible) return;
      const status = statusByLine[lineId];
      if (['minor', 'delay', 'disruption'].includes(status)) {
        el.classList.add(`schem-${status}`);
      }
    });

    svg.querySelectorAll('.schem-connector, .schem-station').forEach(el => {
      const ids = (el.dataset.lines || '').split(',').map(s => s.trim()).filter(Boolean);
      const visible = !ids.length || ids.some(id => schematicLineMatchesFilter(id));
      el.classList.toggle('schem-filtered-out', !visible);
    });
  }

  function updateSchematic() {
    // Schematic stays off the primary Home path — line board is the scan surface.
    const wrap = $('schematicWrap');
    if (!wrap) return;
    wrap.hidden = true;
    wrap.setAttribute('aria-hidden', 'true');
  }

  function scrollToLineRow(lineId) {
    const row = document.querySelector(`.line-row[data-line-id="${lineId}"]`);
    if (!row) return;
    row.scrollIntoView({ behavior: 'smooth', block: 'center' });
    row.classList.add('highlight');
    setTimeout(() => row.classList.remove('highlight'), 2200);
    document.querySelectorAll('#kvSchematic [data-line-id]').forEach(p => {
      p.classList.toggle('active', p.dataset.lineId === lineId);
    });
  }

  function openStatusHelp() {
    $('panelTitle').textContent = 'What is Status?';
    $('panelSub').innerHTML = '<span class="badge unknown" style="display:inline-block;min-width:auto">Crowd reports</span>';
    $('panelBody').innerHTML = `
      <p>The <strong>Status</strong> tab shows per-line severity from recent public posts — delays, disruptions and minor complaints scraped from Threads, Reddit and news RSS.</p>
      <p>It is <strong>not</strong> the official RapidKL, Prasarana or KTMB status page. <strong>No current signal</strong> means no public evidence passed the filter in the last 24 hours; it does not confirm trains are running normally.</p>
      <p>Tap a row with reports to see source evidence. Lines marked <strong>Official</strong> have corroboration from operator notices.</p>`;
    showPanel();
  }

  function lineRowHtml(line) {
    const color = LINE_COLORS[line.id] || '#64748b';
    const clickable = !line.planned;
    const pulseClass = ['delay', 'disruption'].includes(line.status) ? ' severity-pulse' : '';
    const disruptionClass = line.status === 'disruption' ? ' severity-disruption' : '';
    const detail = esc(cardDetail(line));
    const pinned = favoriteLineIds.has(line.id);
    const pinLabel = pinned ? pickLang('Saved', 'Disimpan') : pickLang('Save', 'Simpan');
    const pill = stitchStatusPill(line);
    const shortName = line.name.replace(/ Line$/, '').replace(/^KTM /, 'KTM ');
    const official = line.corroborated
      ? `<span class="stitch-tag stitch-tag--official">${esc(pickLang('Official', 'Rasmi'))}</span>`
      : '';
    return `
      <div class="line-row stitch-line-row${clickable ? '' : ' planned-row'}${pulseClass}${disruptionClass}" role="${clickable ? 'button' : 'group'}" tabindex="${clickable ? '0' : '-1'}"
        data-line-id="${esc(line.id)}" data-cluster="${esc(line.top_cluster_id || '')}" data-name="${esc(line.name)}"
        data-status="${esc(line.status)}" data-status-label="${esc(line.status_label)}" data-reason="${esc(line.reason || '')}" ${clickable ? '' : 'aria-disabled="true"'}>
        <div class="stitch-line-stripe" style="background:${esc(color)}"></div>
        <div class="stitch-line-body">
          <div style="min-width:0;flex:1">
            <h4 class="stitch-line-name">
              <button type="button" class="stitch-fav-btn fav-btn${pinned ? ' fav-on' : ''}" data-line-id="${esc(line.id)}" aria-label="${esc(pinLabel)}" title="${esc(pinLabel)}">${pinned ? 'Save' : '+'}</button>
              ${esc(shortName)}${facilityChip(line)}${official}
            </h4>
            <p class="stitch-line-detail">${detail || '&nbsp;'}</p>
          </div>
          <span class="stitch-status-pill ${pill.cls}">${esc(pill.label)}</span>
        </div>
      </div>`;
  }

  function renderBoard() {
    boardData = boardSnapshot;
    if (!boardSnapshot) return;
    const lines = filteredLines();
    renderRouteLegend(boardSnapshot.lines || []);
    updateFilterChips();
    updateSchematic();

    const countEl = document.querySelector('#lineBoard .board-count');
    if (countEl) countEl.textContent = String(lines.length);

    const rowsHtml = (rows) => rows.map(lineRowHtml).join('');

    if (!lines.length) {
      const counts = boardFilterCounts();
      let hint = 'Try another filter or clear your search.';
      let actions = '<button class="btn-retry" type="button" id="emptyResetFilters">Show all lines</button>';
      if (activeFilter === 'favorites') {
        hint = counts.favorites
          ? 'None of your pinned lines match the current search.'
          : 'Pin lines with the Pin button on any row — they appear here for quick access.';
        actions = counts.favorites
          ? '<button class="btn-retry" type="button" id="emptyResetFilters">Clear filters</button>'
          : '<button class="btn-retry" type="button" id="emptyResetFilters">Show all lines</button>';
      } else if (activeFilter === 'rail') {
        hint = placeFilter
          ? `No rail lines match "${esc(placeFilter)}".`
          : `No rail lines in the board (${counts.rail} rail lines loaded).`;
      } else if (activeFilter === 'bus') {
        hint = placeFilter
          ? `No bus networks match "${esc(placeFilter)}".`
          : `No bus networks in the board (${counts.bus} bus networks loaded).`;
      } else if (placeFilter) {
        hint = `No lines match "${esc(placeFilter)}". Clear search or pick a station from suggestions.`;
      }
      $('lineBoard').innerHTML = `
        <div class="stitch-section-head" id="lineBoardHead">
          <h2 class="tm-live-today-title">Line status</h2>
          <span class="stitch-count-badge board-count">0</span>
        </div>
        <div class="empty">
          No matching lines.<br>
          <span style="font-size:12px;color:var(--text-dim)">${hint}</span>
          <div class="empty-filter-actions">
            ${actions}
            <button class="btn-retry" id="emptyRefresh" type="button">Check latest</button>
          </div>
        </div>`;
      $('emptyResetFilters')?.addEventListener('click', resetBoardFilters);
      $('emptyRefresh')?.addEventListener('click', triggerRefresh);
      return;
    }

    const usePulseGrouping = activeFilter === 'all' && !placeFilter;
    const priorityLines = usePulseGrouping
      ? lines.filter(line => ['minor', 'delay', 'disruption'].includes(line.status) || favoriteLineIds.has(line.id))
      : lines;
    const quietLines = usePulseGrouping ? lines.filter(line => !priorityLines.includes(line)) : [];
    $('lineBoard').innerHTML = `
      <div class="stitch-section-head" id="lineBoardHead">
        <h2 class="tm-live-today-title">Line status</h2>
        <span class="stitch-count-badge board-count">${lines.length}</span>
      </div>
      ${priorityLines.length
        ? rowsHtml(priorityLines)
        : `<div class="quiet-empty"><strong>${pickLang('No active signals', 'Tiada isyarat aktif')}</strong><br><span style="font-size:13px">${pickLang('Quiet ≠ confirmed normal service', 'Tenang ≠ perkhidmatan disahkan normal')}</span></div>`}
      ${quietLines.length ? `<details class="quiet-lines"><summary><span>${pickLang('Quiet lines', 'Laluan tenang')}</span><span>${quietLines.length}</span></summary>${rowsHtml(quietLines)}</details>` : ''}`;
  }

  function renderPlanned(services) {
    const section = $('plannedSection');
    if (!services?.length) {
      section.hidden = true;
      return;
    }
    section.hidden = false;
    $('plannedServices').innerHTML = `
      <div class="board-head"><span>Future network</span><span>${services.length}</span></div>
      ${services.map(service => `
        <div class="line-row planned-row" style="--line-color:${LINE_COLORS[service.id] || '#64748b'}">
          <span class="badge unknown">Planned</span>
          <div class="line-main">
            <div class="line-name">${esc(service.name)}</div>
            <div class="line-reason">${esc(service.route)} · ${esc(service.stage)}</div>
          </div>
          <div class="line-meta"><div class="line-mode">Future</div></div>
        </div>`).join('')}`;
  }

  function renderOfficialStrip(reports) {
    const official = (reports || []).filter(r =>
      r.corroborated_by_official || (r.source_roles || []).includes('official_grounding') || (r.sources || '').includes('official')
    );
    const strip = $('officialStrip');
    if (!official.length) { strip.hidden = true; return; }
    strip.hidden = false;
    $('officialFeed').innerHTML = official.slice(0, 4).map(r =>
      `<div class="report" data-cluster="${esc(r.cluster_id)}" data-name="${esc(r.entity || 'Official')}">
        <div class="report-top"><span class="report-entity">${esc(r.entity || '—')}</span><span>${esc(relTime(r.last_seen_at))}</span></div>
        <div class="report-title">${esc(r.headline || r.entity || 'Structured incident signal')}</div>
        <div class="report-body">${esc(r.summary || '')}</div>
      </div>`
    ).join('');
  }

  function liveRelevantReports(reports, lines) {
    const byId = Object.fromEntries((lines || []).map(l => [l.id, l]));
    const now = Date.now();
    const activeStatuses = ['minor', 'delay', 'disruption'];
    return (reports || []).filter(r => {
      // Live today = MYT calendar day first; fall back to a short clock window.
      if (r.last_seen_at && isTodayMYT(r.last_seen_at)) {
        const lineId = r.line_id || guessLineIdFromReport(r);
        const line = lineId ? byId[lineId] : null;
        if (line?.in_service === false) return false;
        return true;
      }
      const ageMs = r.last_seen_at ? now - new Date(r.last_seen_at).getTime() : Infinity;
      if (ageMs > 6 * 3600000) return false;
      const lineId = r.line_id || guessLineIdFromReport(r);
      const line = lineId ? byId[lineId] : null;
      if (!line) return ageMs < 3 * 3600000;
      if (line.in_service === false) return false;
      if (activeStatuses.includes(line.status)) return ageMs < 6 * 3600000;
      return ageMs < 2 * 3600000;
    });
  }

  function renderTrainSchedule() {
    const el = $('trainScheduleCard');
    if (!el) return;
    const lines = Object.values(linesReferenceById || {})
      .filter(l => l.operating_hours?.first_train && l.operating_hours?.last_train && !l.planned)
      .sort((a, b) => (a.name || '').localeCompare(b.name || ''));
    if (!lines.length) {
      el.hidden = true;
      return;
    }
    el.hidden = false;

    function renderHeadways(oh, status) {
      const peakMin = oh.peak_hours?.[0]?.headway_min;
      const offPeakMin = oh.off_peak_headway_min;
      if (!peakMin && !offPeakMin) return '';
      const peakText = peakMin ? `<span class="headway-item${status === 'peak' ? ' active' : ''}">${pickLang('Peak', 'Puncak')}: <strong>~${esc(peakMin)}m</strong></span>` : '';
      const offPeakText = offPeakMin ? `<span class="headway-item${status === 'off_peak' ? ' active' : ''}">${pickLang('Off-peak', 'Luar Puncak')}: <strong>~${esc(offPeakMin)}m</strong></span>` : '';
      if (peakText && offPeakText) {
        return `<div class="schedule-headways">${peakText} <span class="headway-sep">·</span> ${offPeakText}</div>`;
      }
      return `<div class="schedule-headways">${peakText || offPeakText}</div>`;
    }

    const rows = lines.map(line => {
      const oh = line.operating_hours;
      const svc = computeClientServiceStatus(oh);
      const color = LINE_COLORS[line.id] || line.official_colour || '#64748b';
      const svcHtml = svc?.label
        ? `<span class="schedule-svc schedule-svc--${esc(svc.status || 'unknown')}">${esc(svc.label)}</span>`
        : '';
      const ttLink = line.timetable_url
        ? `<a class="schedule-tt" href="${esc(line.timetable_url)}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()">${pickLang('Timetable ↗', 'Jadual waktu ↗')}</a>`
        : '';
      const headwaysHtml = renderHeadways(oh, svc.status);

      return `<button type="button" class="schedule-row schedule-row--click" data-line-id="${esc(line.id)}" style="--line-color:${esc(color)}">
        <div class="schedule-row-header">
          <span class="schedule-line">${esc(line.name.replace(/ Line$/, ''))}</span>
          ${ttLink}
        </div>
        <div class="schedule-row-times">
          ${esc(oh.first_train)} – ${esc(oh.last_train)} MYT
        </div>
        <div class="schedule-row-status-line">
          ${svcHtml}
          ${headwaysHtml}
        </div>
      </button>`;
    }).join('');
    el.innerHTML = `
      <div class="tm-travel-card-head">
        <div>
          <h2 id="scheduleTitle">Service hours</h2>
          <p class="tm-travel-lead">${pickLang('First & last trains · Rapid KL rail', 'Kereta pertama & terakhir · Rapid KL')}</p>
        </div>
      </div>
      <div class="schedule-grid">${rows}</div>`;
  }

  function renderReports(reports) {
    const relevant = liveRelevantReports(reports, boardSnapshot?.lines || boardData?.lines);
    const sorted = sortReportsThreadsFirst(relevant);
    const visible = filteredReports(sorted);
    renderOfficialStrip(sorted);
    const countLabel = visible.length
      ? `${visible.length} today${placeFilter ? ' · filtered' : ''}`
      : pickLang('Nothing reported today', 'Tiada laporan hari ini');
    $('reportCount').textContent = countLabel;
    if (!visible.length) {
      const collectorState = placeFilter ? 'quiet' : threadsCollectorStatus();
      const subtext = collectorState === 'broken'
        ? pickLang('Rider signal collection is temporarily degraded — official notices are still active. We are investigating.', 'Pengumpulan isyarat penumpang terganggu seketika — notis rasmi masih aktif. Kami sedang menyiasat.')
        : placeFilter
          ? pickLang('No active rider reports found for this station/line. Remember: quiet lines are not confirmed normal service.', 'Tiada laporan aktif ditemui untuk stesen/laluan ini. Ingat: laluan senyap bukanlah jaminan perkhidmatan normal.')
          : pickLang('Quiet lines mean no recent crowd reports are captured. It is not an operator all-clear.', 'Laluan senyap bermakna tiada laporan penumpang diterima baru-baru ini. Ia bukan pengesahan rasmi perkhidmatan lancar.');
      $('reportFeed').innerHTML = `
        <div class="empty tm-live-empty${collectorState === 'broken' ? ' tm-live-empty--degraded' : ''}">
          <div class="empty-icon" aria-hidden="true">${ICON_SVG.train}</div>
          ${pickLang('No rider delays reported in the last 24 hours.', 'Tiada kelewatan dilaporkan dalam 24 jam terakhir.')}<br>
          <span style="font-size:12px;color:var(--text-dim)">${subtext}</span><br>
          <button class="btn-retry" id="emptyReportRefresh" type="button" style="margin-top:14px">${pickLang('Check latest', 'Semak semula')}</button>
        </div>`;
      $('emptyReportRefresh')?.addEventListener('click', triggerRefresh);
      return;
    }
    $('reportFeed').innerHTML = `<div class="tm-report-scroll">${visible.map(r => {
      const glance = pickLang(r.glance_line, r.glance_line_ms) || pickLang(r.headline, r.headline_ms) || r.entity || pickLang('Rider signal', 'Isyarat penumpang');
      const quote = pickLang(r.summary, r.summary_ms) || '';
      const lineLabel = r.entity || r.location || guessLineIdFromReport(r).replace(/-/g, ' ') || '';
      const age = r.report_when || reportAgeLabel(r.last_seen_at);
      const src = reportSourceTag(r);
      const riding = ridingNowFromReport(r);
      const facility = r.facility_alert ? `<span class="stitch-tag stitch-tag--src" title="${esc(pickLang('Facility', 'Kemudahan'))}">♿</span>` : '';
      const tags = [
        riding ? `<span class="stitch-tag stitch-tag--riding">${esc(pickLang('Riding now', 'Sedang menaiki'))}</span>` : '',
        `<span class="stitch-tag ${src.cls}">${esc(src.label)}</span>`,
        facility,
      ].filter(Boolean).join('');
      const foot = [lineLabel, age || relTime(r.last_seen_at)].filter(Boolean).join(' · ');
      const stripe = reportStripeColor(r);

      const timeToken = `<span class="report-token report-token--time">${esc(pickLang(r.report_when, r.report_when_ms) || reportAgeLabel(r.last_seen_at))}</span>`;
      const lineToken = `<span class="report-token report-token--line" style="border-color:${esc(stripe)};color:${esc(stripe)}">${esc(r.entity || '')}</span>`;
      const placeToken = r.location ? `<span class="report-token report-token--place">${esc(r.location)}</span>` : '';
      const issueText = pickLang(r.report_issue, r.report_issue_ms) || 'issue';
      const issueToken = `<span class="report-token report-token--issue severity-${esc(r.severity || 'minor')}">${esc(issueText)}</span>`;

      return `
      <div class="report report-card" style="--report-line-color:${esc(stripe)}" data-cluster="${esc(r.cluster_id)}" data-name="${esc(glance)}" data-severity="${esc(r.severity || '')}">
        <div class="report-card-tags">${tags}</div>
        <div class="report-card-quote">
          <div class="report-glance-tokens">
            ${timeToken}
            ${lineToken}
            ${placeToken}
            ${issueToken}
          </div>
          ${quote ? `<span class="report-card-detail">“${esc(quote)}”</span>` : ''}
        </div>
        <div class="report-card-foot" title="${esc(fmtMYT(r.last_seen_at))} MYT">${esc(foot)}</div>
      </div>`;
    }).join('')}</div>`;
  }

  function lineStatusOnRoute(lineIds) {
    if (!boardSnapshot?.lines || !lineIds?.length) return [];
    const byId = Object.fromEntries(boardSnapshot.lines.map(l => [l.id, l]));
    return lineIds.map(id => byId[id]).filter(l => l && ['minor', 'delay', 'disruption'].includes(l.status));
  }

  function renderJourneyTransferStep(leg) {
    const hint = leg.interchange_hint;
    if (!hint) {
      return `<div class="journey-step"><span class="step-mark" style="--step-color:#fbbf24"></span><div><div class="step-title">${esc(pickLang('Change at', 'Tukar di'))} ${esc(leg.to)}</div><div class="step-copy">${esc(pickLang('Follow interchange signs', 'Ikut papan pertukaran'))}${leg.distance_metres ? ` · ${esc(pickLang('about', 'kira-kira'))} ${esc(leg.distance_metres)} m` : ''}</div></div><span class="step-time">${esc(leg.minutes)} min</span></div>`;
    }
    const note = pickLang(hint.note_en, hint.note_ms);
    const paid = hint.paid_separate
      ? `<span class="journey-paid-badge">${esc(pickLang('Tap out · separate ticket', 'Tap keluar · tiket berasingan'))}</span>`
      : '';
    const ets = pickLang(hint.ets_warning_en, hint.ets_warning_ms);
    const etsHtml = ets ? `<div class="step-copy journey-ets">${esc(ets)}</div>` : '';
    return `<div class="journey-step journey-step--transfer${hint.paid_separate ? ' journey-step--paid' : ''}"><span class="step-mark" style="--step-color:#fbbf24"></span><div><div class="step-title">${esc(pickLang('Change at', 'Tukar di'))} ${esc(hint.station || leg.to)} ${paid}</div><div class="step-copy">${esc(note)}</div>${etsHtml}</div><span class="step-time">${esc(leg.minutes)} min</span></div>`;
  }

  function renderJourneyMalaysiaNotes(data) {
    const my = data.malaysia;
    if (!my) return '';
    const notes = (uiLang === 'ms' ? my.notes_ms : my.notes_en) || [];
    const pass = my.pass_fit || {};
    const passLine = pass.recommended
      ? pickLang(
          `Pass tip: ${pass.recommended} (~RM${pass.monthly_cost}/mo)`,
          `Tip pas: ${pass.recommended} (~RM${pass.monthly_cost}/bulan)`
        )
      : '';
    const alerts = lineStatusOnRoute(data.line_ids_on_route);
    const alertHtml = alerts.length
      ? `<div class="journey-alert">${esc(pickLang('Crowd signals on this route:', 'Isyarat penumpang pada laluan ini:'))} ${alerts.map(l => `<strong>${esc(l.name)}</strong> (${esc(shortStatusLabel(l))})`).join(' · ')}</div>`
      : '';
    const paid = (my.paid_transfer_stations || []).length
      ? `<div class="journey-warn">⚠ ${esc(pickLang('Tap out required at: ', 'Tap keluar di: '))}${esc(my.paid_transfer_stations.join(', '))}</div>`
      : '';
    return `
      <div class="journey-my-notes">
        ${paid}
        ${alertHtml}
        ${notes.map(n => `<p class="step-copy">${esc(n)}</p>`).join('')}
        ${passLine ? `<p class="step-copy"><strong>${esc(passLine)}</strong>${pass.note ? ` — ${esc(pass.note)}` : ''}</p>` : ''}
      </div>`;
  }

  function updateLiveStatus(status) {
    const latest = status.freshness?.latest_checked_at || status.freshness?.latest_inserted_at;
    const stale = status.freshness?.is_stale;
    const dot = $('liveDot');
    dot.classList.toggle('stale', !!stale);
    const label = stale ? 'Data may be old' : 'Updated';
    const timeStr = latest ? relTime(latest) : '';
    $('liveMeta').textContent = timeStr ? `${label} ${timeStr} ago` : label;
    const banner = $('staleBanner');
    if (banner) {
      banner.classList.toggle('show', !!stale);
      const detail = $('staleBannerDetail');
      if (detail && timeStr) {
        detail.textContent = ` — last successful collection check ${timeStr} MYT.`;
      }
    }
  }

  function startCountdown() {
    secondsLeft = COUNTDOWN_SEC;
    if (countdownTimer) clearInterval(countdownTimer);
    countdownTimer = setInterval(() => {
      if (isRefreshing || $('panel').classList.contains('open')) return;
      secondsLeft = Math.max(0, secondsLeft - 1);
      const el = $('countdown');
      if (el) {
        const m = Math.floor(secondsLeft / 60);
        const s = String(secondsLeft % 60).padStart(2, '0');
        el.textContent = `Refresh ${m}:${s}`;
      }
      if (secondsLeft <= 0) {
        secondsLeft = COUNTDOWN_SEC;
        loadAll();
      }
    }, 1000);
  }

  let healthCheckedAt = 0;
  async function refreshHealthSnapshot() {
    // Cheap, low-frequency check so the empty state can tell "quiet" from "collector broken"
    // without hammering /health on every poll tick.
    if (Date.now() - healthCheckedAt < 4 * 60 * 1000) return;
    healthCheckedAt = Date.now();
    try {
      const res = await fetchWithTimeout(api('/health'));
      if (res.ok) {
        healthSnapshot = await res.json();
        if (boardSnapshot) renderReports(boardSnapshot.recent_reports || []);
      }
    } catch {
      // Health check is best-effort — never blocks the main board render.
    }
  }

  function threadsCollectorStatus() {
    const src = (healthSnapshot?.sources || []).find(s => s.source === 'threads');
    if (!src) return 'unknown';
    if (src.needs_attention || src.status === 'failed') return 'broken';
    if (src.status === 'healthy') return 'healthy';
    return 'quiet';
  }

  async function loadAll() {
    const gen = ++loadGeneration;
    if (!boardData) showLoadingState();
    $('refreshBtn').disabled = true;

    try {
      const [statusRes, boardRes, refRes] = await Promise.all([
        fetchWithTimeout(api('/api/trafficmy/status')),
        fetchWithTimeout(api('/api/trafficmy/lines?source_group=social&quality_only=true&malaysia_only=true')),
        fetchWithTimeout(api('/api/trafficmy/lines/reference')),
      ]);
      if (gen !== loadGeneration) return;
      if (!statusRes.ok || !boardRes.ok) throw new Error('API error');
      const status = await statusRes.json();
      const board = await boardRes.json();
      if (refRes.ok) {
        const refData = await refRes.json();
        linesReferenceById = Object.fromEntries((refData.lines || []).map(line => [line.id, line]));
        renderLineLegendGrid(refData.lines || []);
        renderTrainSchedule();
      }
      boardSnapshot = board;
      boardData = board;
      updateLiveStatus(status);
      renderContextBar();
      renderSummary(board, status);
      renderPulseStrip(board.lines || [], board.recent_reports || []);
      syncMapLayersFromHomeFilter();
      syncMapLayerUi();
      renderMapSidebar(board.lines || []);
      updateSchematic();
      updateFilterChips();
      renderBoard();
      renderPlanned(board.planned_services || []);
      renderReports(board.recent_reports || []);
      updateSchematicHighlights();
      checkNotify(board.lines || []);
      startCountdown();
      refreshHealthSnapshot();
    } catch (err) {
      if (gen !== loadGeneration) return;
      // Retry once after 3 seconds
      if (!loadAll._retried) {
        loadAll._retried = true;
        await new Promise(r => setTimeout(r, 3000));
        if (gen === loadGeneration) {
          loadAll._retried = false;
          return loadAll();
        }
      }
      loadAll._retried = false;
      const timedOut = err && err.name === 'AbortError';
      $('liveMeta').textContent = timedOut ? 'Timed out' : 'Error';
      $('liveDot').classList.add('stale');
      const ss = $('summaryStrip');
      if (ss) {
        ss.hidden = false;
        ss.removeAttribute('aria-hidden');
        ss.innerHTML = `<div class="stat-pill alert"><span>${timedOut ? 'Request timed out' : 'Could not load data'}</span></div>`;
      }
      $('statsBar').innerHTML = `<button type="button" class="stats-bar-btn" disabled style="color:var(--bad)">${timedOut ? 'Request timed out' : 'Could not load data'}</button>`;
      showBoardError(
        timedOut ? 'Loading timed out' : 'Failed to load data',
        timedOut
          ? 'The server took longer than expected. Check your connection or try again.'
          : 'Check your connection and try Check latest.',
      );
      $('reportFeed').innerHTML = `<div class="empty" style="padding:24px">Incident signals unavailable.</div>`;
    } finally {
      if (gen === loadGeneration) {
        $('refreshBtn').disabled = isRefreshing;
        const fab = $('fabRefresh');
        if (fab) {
          fab.disabled = isRefreshing;
          fab.classList.toggle('loading', isRefreshing);
        }
      }
    }
  }

  async function openPanel(clusterId, label, status) {
    if (!clusterId) return;
    rememberLastIncident(clusterId, label);
    $('panelTitle').textContent = label;
    const statusLabels = { unknown: 'No current signal', minor: 'Minor', delay: 'Delay', disruption: 'Disruption' };
  $('panelSub').innerHTML = status && statusLabels[status]
      ? `<span class="badge ${esc(status)}" style="display:inline-block;min-width:auto">${esc(statusLabels[status])}</span>`
      : '';
    $('panelBody').innerHTML = '<div class="skel-row"><div style="flex:1"><div class="skel skel-text"></div><div class="skel skel-text short" style="margin-top:8px"></div></div></div>';
    showPanel();
    try {
      const r = await fetch(api(`/api/trafficmy/incidents/${encodeURIComponent(clusterId)}`));
      const d = await r.json();
      const items = d.items || [];
      const incident = d.incident || {};
      $('panelTitle').textContent = incident.headline || label;
      $('panelBody').innerHTML = `
        <div class="guide-section"><h3>Operational summary</h3><p>${esc(incident.summary || 'TrafficMY is monitoring this signal.')}</p></div>
        <div class="guide-section"><h3>Confidence</h3><p>${esc((incident.confidence_band || 'early').replace(/^./, c => c.toUpperCase()))} · ${Number(incident.volume || items.length)} source signal${Number(incident.volume || items.length) === 1 ? '' : 's'} · Last seen ${esc(relTime(incident.last_seen_at))}</p></div>
        <div class="guide-section"><h3>Source evidence</h3>
          ${items.length ? items.map(ev => `<div class="evidence-source"><span><strong>${esc((ev.source_platform || 'public').replace('_', ' '))}</strong><br><small>${esc(fmtMYT(ev.created_at))} MYT</small></span>${ev.url ? `<a href="${esc(ev.url)}" target="_blank" rel="noopener noreferrer">Open source</a>` : ''}</div>`).join('') : '<p>No public source link is available.</p>'}
        </div>
        <p class="map-layer-note">TrafficMY does not republish rider wording or usernames. Source links are provided for audit.</p>`;
    } catch {
      $('panelBody').innerHTML = '<div class="error-state"><strong>Failed to load</strong><p>Try again.</p></div>';
    }
  }

  async function triggerRefresh() {
    if (isRefreshing) return;
    isRefreshing = true;
    const btn = $('refreshBtn');
    const fab = $('fabRefresh');
    btn.disabled = true;
    if (fab) { fab.disabled = true; fab.classList.add('loading'); }
    btn.classList.add('loading');
    btn.querySelector('.btn-label').textContent = 'Checking…';
    try {
      await loadAll();
      showToast('Latest server data loaded');
    } catch {
      $('liveMeta').textContent = 'Check failed';
      $('liveDot').classList.add('stale');
      showToast('Could not load latest data');
    } finally {
      isRefreshing = false;
      btn.disabled = false;
      btn.classList.remove('loading');
      btn.querySelector('.btn-label').textContent = 'Check latest';
      if (fab) { fab.disabled = false; fab.classList.remove('loading'); }
      btn.querySelector('.btn-label').textContent = 'Refresh';
    }
  }

  let stationSearchTimer = null;
  let journeyRequestGeneration = 0;
  let savingsRequestGeneration = 0;

  async function updateStationOptions(query = '') {
    try {
      const params = new URLSearchParams({ q: query, limit: '30' });
      const response = await fetchWithTimeout(api(`/api/trafficmy/journey/stations?${params}`), 15000);
      if (!response.ok) return;
      const data = await response.json();
      $('stationOptions').innerHTML = (data.items || []).map(item =>
        `<option value="${esc(item.name)}">${esc((item.lines || []).join(' · '))}</option>`
      ).join('');
    } catch { /* Autocomplete is optional. */ }
  }

  function queueStationSearch(value) {
    clearTimeout(stationSearchTimer);
    stationSearchTimer = setTimeout(() => updateStationOptions(value), 220);
  }

  function renderJourney(data) {
    const startWalk = data.origin.walk_minutes
      ? `<div class="journey-step"><span class="step-mark" style="--step-color:#94a3b8"></span><div><div class="step-title">Walk to ${esc(data.origin.station)}</div><div class="step-copy">About ${esc(data.origin.walk_metres)} m from ${esc(data.origin.label)}</div></div><span class="step-time">${esc(data.origin.walk_minutes)} min</span></div>`
      : '';
    const railSteps = (data.legs || []).map(leg => {
      if (leg.kind === 'transfer') return renderJourneyTransferStep(leg);
      const stopLabel = Number(leg.stops) === 1 ? 'stop' : 'stops';
      const lineLabel = leg.short_name && leg.short_name !== leg.line ? `${leg.line} (${leg.short_name})` : leg.line;
      return `<div class="journey-step"><span class="step-mark" style="--step-color:${esc(leg.color)}"></span><div><div class="step-title">${esc(lineLabel)}</div><div class="step-copy">${esc(leg.from)} → ${esc(leg.to)} · ${esc(leg.stops)} ${stopLabel}</div></div><span class="step-time">${esc(leg.minutes)} min</span></div>`;
    }).join('');
    const endWalk = data.destination.walk_minutes
      ? `<div class="journey-step"><span class="step-mark" style="--step-color:#94a3b8"></span><div><div class="step-title">Walk to destination</div><div class="step-copy">About ${esc(data.destination.walk_metres)} m from ${esc(data.destination.station)}</div></div><span class="step-time">${esc(data.destination.walk_minutes)} min</span></div>`
      : '';
    const fare = data.fare;
    const farePill = fare
      ? `<div class="stat-pill">~RM<strong>${esc(fare.estimate_typical)}</strong> (${esc(fare.estimate_low)}–${esc(fare.estimate_high)})</div>`
      : '';
    $('journeyResult').innerHTML = `
      <div class="journey-summary">
        <div class="stat-pill"><strong>${esc(data.total_minutes)}</strong> min estimated</div>
        <div class="stat-pill"><strong>${esc(data.transfers)}</strong> changes</div>
        ${farePill}
        <div class="stat-pill">${esc(pickLang('Rapid KL GTFS', 'Rapid KL GTFS'))}</div>
      </div>
      ${startWalk}${railSteps}${endWalk}
      ${renderJourneyMalaysiaNotes(data)}
      <p class="step-copy" style="margin-top:12px">${esc(data.walking_note)} ${fare ? esc(fare.disclaimer) : ''}</p>`;
    $('journeyResult').hidden = false;
  }

  async function planJourney(event) {
    event.preventDefault();
    const requestGeneration = ++journeyRequestGeneration;
    const fromInput = $('journeyFrom');
    const toInput = $('journeyTo');
    const origin = fromInput.dataset.coordinates || fromInput.value.trim();
    const destination = toInput.dataset.coordinates || toInput.value.trim();
    if (!origin || !destination) return;
    $('journeyResult').hidden = false;
    $('journeyResult').innerHTML = '<div class="loading-banner"><span class="loading-spinner" aria-hidden="true"></span><span>Building the route…</span></div>';
    try {
      const params = new URLSearchParams({ origin, destination });
      const response = await fetchWithTimeout(api(`/api/trafficmy/journey/plan?${params}`), 25000);
      const data = await response.json();
      if (requestGeneration !== journeyRequestGeneration) return;
      if (!response.ok) throw new Error(data.detail || 'No route found');
      renderJourney(data);
    } catch (error) {
      if (requestGeneration !== journeyRequestGeneration) return;
      $('journeyResult').innerHTML = `<div class="journey-error"><strong>Could not build this route.</strong><br>${esc(error.message || 'Try station names or use the official mixed-mode planner.')}</div>`;
    }
  }

  function useCurrentLocation() {
    if (!navigator.geolocation) return;
    const button = $('useLocation');
    button.textContent = 'Locating…';
    navigator.geolocation.getCurrentPosition(
      position => {
        const input = $('journeyFrom');
        input.value = 'Current location';
        input.dataset.coordinates = `@${position.coords.latitude},${position.coords.longitude}`;
        button.textContent = 'Location ready';
      },
      () => { button.textContent = 'Location unavailable'; },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 },
    );
  }

  async function loadUpdates() {
    try {
      const response = await fetchWithTimeout(api('/api/trafficmy/updates'));
      if (!response.ok) throw new Error();
      const data = await response.json();
      const items = [...(data.active || []), ...(data.upcoming || [])].slice(0, 10);
      $('updatesAsOf').textContent = `Checked ${data.as_of}`;
      $('updatesGrid').innerHTML = items.map(item => `
        <a class="update-card${item.featured ? ' featured' : ''}" href="${esc(item.url)}" target="_blank" rel="noopener noreferrer">
          <span class="update-badge">${esc(item.status === 'upcoming' ? 'Starts soon' : item.badge || item.type)}</span>
          <h3>${esc(item.title)}</h3>
          <p>${esc(item.summary)}</p>
          <div class="update-meta">${esc(item.operator || '')}${item.valid_to ? ` · until ${esc(item.valid_to)}` : ''}${item.ending_soon ? ' · ending soon' : ''}</div>
        </a>`).join('');
    } catch {
      $('updatesGrid').innerHTML = '<div class="empty">Current offers are unavailable. Check operator websites directly.</div>';
    }
  }

  async function compareSavings(event) {
    event?.preventDefault();
    const requestGeneration = ++savingsRequestGeneration;
    const params = new URLSearchParams({
      rides_per_month: $('monthlyRides').value,
      average_fare: $('averageFare').value,
      malaysian: $('isMalaysian').checked,
      student: $('isStudent').checked,
    });
    try {
      const response = await fetchWithTimeout(api(`/api/trafficmy/pass-comparison?${params}`));
      const data = await response.json();
      if (requestGeneration !== savingsRequestGeneration) return;
      const best = data.recommendation;
      $('savingResult').innerHTML = `
        <div>Best estimate: <strong>${esc(best.name)}</strong> · RM${Number(best.monthly_cost).toFixed(2)}/month
        ${data.estimated_saving ? ` · save about <strong>RM${Number(data.estimated_saving).toFixed(2)}</strong>` : ''}</div>
        <div class="saving-options">${(data.options || []).map(option => `
          <div class="saving-option${option.id === best.id ? ' best' : ''}${!option.eligible ? ' ineligible' : ''}">
            <strong>${esc(option.name)}</strong><br>RM${Number(option.monthly_cost).toFixed(2)}${!option.eligible ? '<br>Not eligible' : option.break_even_rides ? `<br>Break-even: ${esc(option.break_even_rides)} trips` : ''}
          </div>`).join('')}</div>
        <p class="step-copy" style="margin-top:10px">${esc(data.note)}</p>
        <div class="source-health" id="sourceHealthPasses" aria-label="Data source health"></div>`;
      $('savingResult').hidden = false;
    } catch {
      if (requestGeneration === savingsRequestGeneration) $('savingResult').hidden = true;
    }
  }

  document.getElementById('lineBoard').addEventListener('click', e => {
    if (e.target.closest('.fav-btn')) {
      e.stopPropagation();
      toggleFavorite(e.target.closest('.fav-btn').dataset.lineId);
      return;
    }
    if (e.target.closest('.share-btn')) {
      e.stopPropagation();
      const row = e.target.closest('.line-row');
      if (!row) return;
      shareLineStatus({
        id: row.dataset.lineId,
        name: row.dataset.name,
        status_label: row.dataset.statusLabel,
        reason: row.dataset.reason,
      });
      return;
    }
    const row = e.target.closest('.line-row[role="button"]');
    if (row) openLineGuide(row.dataset.lineId, { clusterId: row.dataset.cluster, label: row.dataset.name, status: row.dataset.status });
  });
  document.getElementById('lineBoard').addEventListener('keydown', e => {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    const row = e.target.closest('.line-row[role="button"]');
    if (row) {
      e.preventDefault();
      openLineGuide(row.dataset.lineId, { clusterId: row.dataset.cluster, label: row.dataset.name, status: row.dataset.status });
    }
  });
  document.getElementById('reportFeed').addEventListener('click', e => {
    const row = e.target.closest('.report');
    if (row) openPanel(row.dataset.cluster, row.dataset.name);
  });

  $('officialFeed')?.addEventListener('click', e => {
    const row = e.target.closest('.report');
    if (row) openPanel(row.dataset.cluster, row.dataset.name);
  });

  $('contrastToggle').addEventListener('click', () => {
    const on = document.body.classList.toggle('high-contrast');
    $('contrastToggle').classList.toggle('active', on);
    $('contrastToggle').setAttribute('aria-pressed', on);
    localStorage.setItem('trafficmy:contrast', on ? '1' : '0');
  });
  $('langToggle')?.addEventListener('click', () => setUiLang(uiLang === 'ms' ? 'en' : 'ms'));
  $('riskStrip')?.addEventListener('click', e => {
    const chip = e.target.closest('.risk-chip');
    if (!chip) return;
    scrollToLineRow(chip.dataset.lineId);
  });
  $('fabRefresh')?.addEventListener('click', triggerRefresh);
  $('journeyForm').addEventListener('submit', planJourney);
  $('useLocation').addEventListener('click', useCurrentLocation);
  $('swapJourney').addEventListener('click', () => {
    const from = $('journeyFrom'); const to = $('journeyTo');
    [from.value, to.value] = [to.value, from.value];
    [from.dataset.coordinates, to.dataset.coordinates] = [to.dataset.coordinates || '', from.dataset.coordinates || ''];
  });
  ['journeyFrom', 'journeyTo'].forEach(id => $(id).addEventListener('input', event => {
    delete event.target.dataset.coordinates;
    queueStationSearch(event.target.value);
  }));
  $('savingsForm').addEventListener('submit', compareSavings);
  $('closePanel').addEventListener('click', closePanel);
  $('backdrop').addEventListener('click', closePanel);
  $('schematicModalClose')?.addEventListener('click', closeSchematicModal);
  $('schematicModalBackdrop')?.addEventListener('click', closeSchematicModal);
  $('panelBody')?.addEventListener('click', e => {
    const img = e.target.closest('.schematic-zoomable');
    if (img?.src) openSchematicModal(img.src, img.alt);
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !$('schematicModal')?.hidden) closeSchematicModal();
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      if ($('shortcutsPanel')?.classList.contains('open')) {
        $('shortcutsPanel').classList.remove('open');
        $('shortcutsPanel').hidden = true;
        return;
      }
      if ($('panel')?.classList.contains('open')) closePanel();
      return;
    }
    if ((e.key === '/' || (e.key === 'k' && (e.ctrlKey || e.metaKey))) && !e.altKey
        && document.activeElement?.tagName !== 'INPUT' && document.activeElement?.tagName !== 'TEXTAREA') {
      e.preventDefault();
      focusSearchInput();
      return;
    }
    if (e.key === '?' && !e.ctrlKey && !e.metaKey && document.activeElement?.tagName !== 'INPUT') {
      e.preventDefault();
      $('shortcutsPanel')?.classList.add('open');
      $('shortcutsPanel').hidden = false;
      return;
    }
    if (!e.ctrlKey && !e.metaKey && !e.altKey && document.activeElement?.tagName !== 'INPUT' && document.activeElement?.tagName !== 'TEXTAREA') {
      const tabKeys = { '1': 'status', '2': 'map', '3': 'travel' };
      if (tabKeys[e.key]) switchTab(tabKeys[e.key]);
    }
  });

  $('methodToggle').addEventListener('click', () => {
    const section = $('methodSection');
    const open = section.classList.toggle('open');
    $('methodToggle').setAttribute('aria-expanded', open);
  });

  document.getElementById('pulseStrip').addEventListener('click', e => {
    const chip = e.target.closest('.pulse-chip[data-line-id]');
    if (chip) {
      if (!document.getElementById('tabStatus')?.classList.contains('active')) switchTab('status');
      const row = document.querySelector(`.line-row[data-line-id="${chip.dataset.lineId}"]`);
      if (row) { row.scrollIntoView({ behavior: 'smooth', block: 'center' }); row.style.outline = '2px solid var(--accent)'; setTimeout(() => { row.style.outline = ''; }, 2000); }
      return;
    }
    const clusterChip = e.target.closest('.pulse-chip[data-cluster]');
    if (clusterChip) openPanel(clusterChip.dataset.cluster, clusterChip.dataset.name);
  });

  if (localStorage.getItem('trafficmy:contrast') === '1') {
    document.body.classList.add('high-contrast');
    $('contrastToggle').classList.add('active');
    $('contrastToggle').setAttribute('aria-pressed', 'true');
  }

  $('notifyToggle').addEventListener('click', async () => {
    if (!('Notification' in window)) { showToast('Notifications not supported'); return; }
    if (Notification.permission === 'default') await Notification.requestPermission();
    notifyEnabled = Notification.permission === 'granted';
    localStorage.setItem('trafficmy:notify', notifyEnabled ? '1' : '0');
    $('notifyToggle').classList.toggle('active', notifyEnabled);
    $('notifyToggle').setAttribute('aria-pressed', notifyEnabled);
    showToast(notifyEnabled ? 'Watching saved lines while this tab is open' : 'Tab watch off');
  });
  if (notifyEnabled) {
    $('notifyToggle').classList.add('active');
    $('notifyToggle').setAttribute('aria-pressed', 'true');
  }

  $('schematicWrap')?.addEventListener('click', e => {
    const hit = e.target.closest('[data-line-id]');
    if (!hit || hit.classList.contains('schem-filtered-out')) return;
    scrollToLineRow(hit.dataset.lineId);
  });

  $('mapSearchForm')?.addEventListener('submit', e => {
    e.preventDefault();
    const dest = $('mapSearchInput')?.value?.trim();
    switchTab('travel');
    if (dest) {
      $('journeyTo').value = dest;
      $('journeyTo').focus();
    } else {
      $('journeyFrom')?.focus();
    }
  });

  document.querySelector('.stitch-header')?.addEventListener('click', e => {
    if (e.target.closest('.status-info-btn')) {
      e.stopPropagation();
      openStatusHelp();
      return;
    }
    if (e.target.closest('#brandLink')) {
      e.preventDefault();
      switchTab('status');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  });

  document.getElementById('mainTabs')?.addEventListener('click', e => {
    const tab = e.target.closest('.main-tab');
    if (tab) switchTab(tab.dataset.tab);
  });
  $('bottomNav')?.addEventListener('click', e => {
    const btn = e.target.closest('.bottom-nav-btn[data-tab]');
    if (btn) switchTab(btn.dataset.tab);
  });

  $('mapSidebarList')?.addEventListener('click', e => {
    const item = e.target.closest('.map-sidebar-item[data-line-id]');
    if (item) openLineGuide(item.dataset.lineId, { label: linesReferenceById[item.dataset.lineId]?.name });
  });

  $('trainScheduleCard')?.addEventListener('click', e => {
    const row = e.target.closest('.schedule-row[data-line-id]');
    if (!row) return;
    openLineGuide(row.dataset.lineId, { label: linesReferenceById[row.dataset.lineId]?.name });
  });

  $('lineLegendToggle')?.addEventListener('click', () => {
    const legend = $('lineLegend');
    const collapsed = legend.classList.toggle('collapsed-mobile');
    $('lineLegendToggle').setAttribute('aria-expanded', collapsed ? 'false' : 'true');
  });

  const panelEl = $('panel');
  const dragHandle = $('panelDragHandle');
  dragHandle?.addEventListener('touchstart', e => { panelTouchStartY = e.touches[0].clientY; }, { passive: true });
  dragHandle?.addEventListener('touchmove', e => {
    if (!panelEl?.classList.contains('open')) return;
    const dy = e.touches[0].clientY - panelTouchStartY;
    if (dy > 0) panelEl.style.transform = `translateY(${dy}px)`;
  }, { passive: true });
  dragHandle?.addEventListener('touchend', e => {
    if (!panelEl?.classList.contains('open')) return;
    const dy = e.changedTouches[0].clientY - panelTouchStartY;
    panelEl.style.transform = '';
    if (dy > 80) closePanel();
  }, { passive: true });
  panelEl?.addEventListener('touchstart', e => {
    if (e.target.closest('.panel-body')) panelTouchStartY = e.touches[0].clientY;
  }, { passive: true });

  $('glossaryBtn')?.addEventListener('click', openGlossary);
  $('lineLegendGrid')?.addEventListener('click', e => {
    const chip = e.target.closest('.legend-chip[data-line-id]');
    if (!chip) return;
    openLineGuide(chip.dataset.lineId, { label: linesReferenceById[chip.dataset.lineId]?.name });
  });
  $('mapLayerAll')?.addEventListener('click', () => onMapLayerChipClick('all'));
  $('mapLayerReports')?.addEventListener('click', () => onMapLayerChipClick('reports'));
  $('mapLayerLrt')?.addEventListener('click', () => onMapLayerChipClick('lrt'));
  $('mapLayerMrt')?.addEventListener('click', () => onMapLayerChipClick('mrt'));
  $('mapLayerMonorail')?.addEventListener('click', () => onMapLayerChipClick('monorail'));
  $('mapLayerKtm')?.addEventListener('click', () => onMapLayerChipClick('ktm'));
  $('mapLayerInterchanges')?.addEventListener('click', () => onMapLayerChipClick('interchanges'));
  $('mapLayerBuses')?.addEventListener('click', () => onMapLayerChipClick('buses'));
  $('mapLayerGps')?.addEventListener('click', () => onMapLayerChipClick('gps'));
  $('mapTiltToggle')?.addEventListener('click', () => {
    if (!mapInstance) { ensureMap(); return; }
    const enabled = mapInstance.getPitch() < 20;
    mapInstance.easeTo({ pitch: enabled ? 46 : 0, bearing: enabled ? -8 : 0, duration: 700 });
    $('mapTiltToggle').classList.toggle('active', enabled);
    $('mapTiltToggle').classList.toggle('map-on', enabled);
    $('mapTiltToggle').setAttribute('aria-pressed', String(enabled));
  });
  document.querySelector('[data-open-tab="map"]')?.addEventListener('click', () => switchTab('map'));

  $('busExplainerToggle')?.addEventListener('click', () => {
    const box = $('busExplainer');
    const open = box.classList.toggle('open');
    $('busExplainerToggle').setAttribute('aria-expanded', open);
  });

  document.getElementById('filters').addEventListener('click', e => {
    const chip = e.target.closest('.chip[data-mode]');
    if (!chip) return;
    e.preventDefault();
    setActiveFilter(chip.dataset.mode || 'all');
  });

  $('sortSelect').addEventListener('change', e => {
    activeSort = e.target.value;
    if (boardSnapshot) renderBoard();
    saveUiState();
  });

  $('placeSearch').addEventListener('input', e => {
    const val = e.target.value.trim();
    syncSearchInputs(val);
    if (!val) {
      setPlaceFilter('');
      $('searchSuggestions').classList.remove('open');
      return;
    }
    queuePlaceSearch(val);
  });

  $('placeSearch').addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      e.preventDefault();
      setPlaceFilter(e.target.value.trim());
      $('searchSuggestions').classList.remove('open');
    }
  });

  $('searchSuggestions').addEventListener('click', e => {
    const item = e.target.closest('.search-item[data-label]');
    if (!item) return;
    setPlaceFilter(item.dataset.label);
    $('searchSuggestions').classList.remove('open');
  });

  $('searchClear').addEventListener('click', () => setPlaceFilter(''));
  $('filterClear').addEventListener('click', () => {
    placeFilter = '';
    syncSearchInputs('');
    $('filterBanner')?.classList.remove('show');
    updateFilterChips();
    renderBoard();
    if (boardSnapshot) renderReports(boardSnapshot.recent_reports || []);
  });

  document.addEventListener('click', e => {
    if (!e.target.closest('#searchWrap')) {
      $('searchSuggestions')?.classList.remove('open');
    }
  });

  function initFromHash() {
    const hash = location.hash.replace(/^#/, '');
    if (hash === 'plan' || hash === 'passes') {
      switchTab('travel');
      return;
    }
    if (hash === 'travel' || hash === 'status' || hash === 'map') {
      switchTab(hash);
      return;
    }
    const savedTab = localStorage.getItem(STORAGE_KEYS.tab);
    if (savedTab === 'plan' || savedTab === 'passes') {
      switchTab('travel');
      return;
    }
    if (savedTab === 'travel' || savedTab === 'status' || savedTab === 'map') {
      switchTab(savedTab);
      return;
    }
    const lineMatch = hash.match(/^line=(.+)$/);
    if (lineMatch && boardData) {
      const lineId = decodeURIComponent(lineMatch[1]);
      const line = (boardData.lines || []).find(l => l.id === lineId);
      if (line) {
        switchTab('status');
        openLineGuide(lineId, { clusterId: line.top_cluster_id, label: line.name, status: line.status });
      }
    }
  }

  $('footerTime').textContent = new Date().toLocaleString('en-MY', { timeZone: 'Asia/Kuala_Lumpur' });
  renderLastViewed();
  restoreUiState();
  syncMapLayersFromHomeFilter();
  syncMapLayerUi();
  initSchematic();
  setUiLang(uiLang);
  $('sortSelect').value = activeSort;
  syncSearchInputs(placeFilter);
  updateIntervalMeta();
  loadStationCatalog();
  loadAppShell()
    .then(ok => {
      if (!ok) return loadConfig();
      return null;
    })
    .finally(() => { updateIntervalMeta(); bindRefreshInfoButtons(); });
  loadAll().then(() => initFromHash()).catch(() => initFromHash());
  updateStationOptions();
  loadUpdates();
  compareSavings();

