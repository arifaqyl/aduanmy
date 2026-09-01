/* ==========================================================================
   TrafficMY — board.js
   Replaces the 3,600-line app.js. One controller, no framework.
   --------------------------------------------------------------------------
   Product thesis this UI must never violate:
     A quiet line means NO REPORT WAS CAPTURED. It is not an all-clear.
     So we always show evidence strength, never a bare green verdict.
   ========================================================================== */
(() => {
  'use strict';

  /* --- Path ------------------------------------------------------------- */
  const BASE = (() => {
    const m = location.pathname.match(/^(.*?\/traffic)\/?/);
    return m ? m[1] : '';
  })();
  const api = p => BASE + p;

  /* --- State ------------------------------------------------------------ */
  const S = {
    lines: [],
    reports: [],       // recent_reports from board
    pins: null,        // map/live pins (have server-computed line_id)
    meta: {},
    fetchedAt: null,
    status: 'load',    // load | ok | stale | down
    lang: (localStorage.getItem('tm.lang') === 'ms') ? 'ms' : 'en',
    filter: 'all',
    tab: 'pBoard',
    openLine: null,
    map: null,
    lastFocus: null,
  };

  /* --- Copy ------------------------------------------------------------- */
  const L = {
    en: {
      quiet:      'No rider reports today',
      quietSub:   'Quiet is not an all-clear — verify before you travel',
      some:       n => `${n} line${n === 1 ? '' : 's'} with rider reports`,
      someSub:    'Tap a line to see the evidence behind it',
      checking:   'Checking sources',
      down:       'Cannot reach the feed',
      downSub:    'Showing nothing rather than something wrong',
      st_disruption: 'DISRUPTION',
      st_delay:      'DELAYS REPORTED',
      st_minor:      'MINOR REPORTS',
      st_none:       'NO SIGNAL',
      st_ended:      'ENDED TODAY',
      st_before:     'NOT YET OPEN',
      st_off:        'NOT IN SERVICE',
      peak:       'PEAK',
      live:       'Live today · MYT',
      closed:     'Outside service hours',
      nLines:     n => `${n}`,
      noMatch:    'No lines match this filter',
      evidence:   'Evidence',
      reports:    n => `${n} rider report${n === 1 ? '' : 's'}`,
      official:   'matched by an official notice',
      noOfficial: 'no official match',
      latest:     'latest',
      srcs:       'rider sources',
      normal:     'Is this normal for this line?',
      today:      'today',
      typical:    w => `typical ${w}`,
      said:       'What riders said',
      nothing:    'Nothing captured for this line today',
      nothingSub: 'That is an absence of data, not a confirmation of normal service.',
      timetable:  'Official timetable and route',
      staleWarn:  'Feed has not refreshed in over 20 minutes. Treat this board as out of date.',
      mapEmpty:   'Official route geometry. No geolocated reports today.',
      mapNote:    n => `Official route geometry. ${n} rider report${n === 1 ? '' : 's'} placed by mentioned station — not live vehicle tracking.`,
      mapLoad:    'Loading reports',
      mapFail:    'Could not load map data',
      cmp: { elevated: 'ELEVATED', typical: 'TYPICAL', quieter_than_usual: 'QUIETER THAN USUAL', no_baseline: 'NO BASELINE YET' },
    },
    ms: {
      quiet:      'Tiada laporan penumpang hari ini',
      quietSub:   'Sunyi bukan bermakna lancar — sahkan sebelum bergerak',
      some:       n => `${n} laluan ada laporan penumpang`,
      someSub:    'Ketik laluan untuk lihat buktinya',
      checking:   'Memeriksa sumber',
      down:       'Tidak dapat menghubungi suapan',
      downSub:    'Lebih baik tiada data daripada data salah',
      st_disruption: 'GANGGUAN',
      st_delay:      'KELEWATAN',
      st_minor:      'LAPORAN KECIL',
      st_none:       'TIADA ISYARAT',
      st_ended:      'TAMAT HARI INI',
      st_before:     'BELUM BUKA',
      st_off:        'TIDAK BEROPERASI',
      peak:       'PUNCAK',
      live:       'Langsung hari ini · MYT',
      closed:     'Di luar waktu perkhidmatan',
      nLines:     n => `${n}`,
      noMatch:    'Tiada laluan sepadan',
      evidence:   'Bukti',
      reports:    n => `${n} laporan penumpang`,
      official:   'dipadan notis rasmi',
      noOfficial: 'tiada padanan rasmi',
      latest:     'terkini',
      srcs:       'sumber penumpang',
      normal:     'Adakah ini biasa bagi laluan ini?',
      today:      'hari ini',
      typical:    w => `biasa ${w}`,
      said:       'Apa kata penumpang',
      nothing:    'Tiada rekod untuk laluan ini hari ini',
      nothingSub: 'Itu ketiadaan data, bukan pengesahan perkhidmatan normal.',
      timetable:  'Jadual dan laluan rasmi',
      staleWarn:  'Suapan tidak dikemas kini lebih 20 minit. Anggap papan ini lapuk.',
      mapEmpty:   'Geometri laluan rasmi. Tiada laporan berlokasi hari ini.',
      mapNote:    n => `Geometri laluan rasmi. ${n} laporan penumpang diletak ikut stesen disebut — bukan pengesanan kenderaan langsung.`,
      mapLoad:    'Memuatkan laporan',
      mapFail:    'Gagal memuatkan data peta',
      cmp: { elevated: 'LEBIH TINGGI', typical: 'BIASA', quieter_than_usual: 'LEBIH SUNYI', no_baseline: 'TIADA ASAS' },
    },
  };
  const t = k => L[S.lang][k];

  /* --- Networks --------------------------------------------------------- */
  const NET = {
    'kelana-jaya': 'lrt', 'ampang-sri-petaling': 'lrt', 'lrt3': 'lrt',
    'kajang': 'mrt', 'putrajaya': 'mrt', 'kajang-putrajaya': 'mrt', 'mrt3': 'mrt',
    'monorail': 'monorail',
    'ktm-komuter': 'ktm', 'ktm-north': 'ktm', 'ets-intercity': 'ktm',
    'ecrl': 'ktm', 'klia-rail': 'ktm', 'sabah-railway': 'ktm', 'rts-johor': 'ktm',
    'brt-sunway': 'bus', 'rapid-bus': 'bus', 'mybas': 'bus',
  };
  const netOf = l => NET[l.id] || (l.mode === 'bus' ? 'bus' : 'rail');

  const PEAK = new Set([
    'kelana-jaya', 'ampang-sri-petaling', 'kajang', 'putrajaya',
    'ktm-komuter', 'monorail', 'lrt3',
  ]);

  /* --- Utils ------------------------------------------------------------ */
  const $ = id => document.getElementById(id);

  const esc = s => String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  function signal(ms) {
    if (AbortSignal.timeout) return AbortSignal.timeout(ms);
    const c = new AbortController();
    setTimeout(() => c.abort(), ms);
    return c.signal;
  }

  function mytParts() {
    const f = new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Asia/Kuala_Lumpur', hour: '2-digit', minute: '2-digit',
      hour12: false, weekday: 'short',
    });
    const p = Object.fromEntries(f.formatToParts(new Date()).map(x => [x.type, x.value]));
    return { hh: +p.hour, mm: p.minute, hour: p.hour, weekday: p.weekday };
  }

  const isPeak = () => {
    const h = mytParts().hh;
    return (h >= 7 && h < 10) || (h >= 17 && h < 20);
  };

  function ago(iso) {
    if (!iso) return '';
    const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
    if (!isFinite(s) || s < 0) return '';
    if (s < 60) return 'now';
    if (s < 3600) return Math.floor(s / 60) + 'm';
    if (s < 86400) return Math.floor(s / 3600) + 'h';
    return Math.floor(s / 86400) + 'd';
  }

  function clockMYT(iso) {
    if (!iso) return '';
    return new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Asia/Kuala_Lumpur', hour: '2-digit', minute: '2-digit', hour12: false,
    }).format(new Date(iso));
  }

  /* --- Signal meter ----------------------------------------------------- */
  /* The differentiator: strength of evidence, not a verdict.
     4 = official corroboration · 3 = many independent · 2 = a few · 1 = single */
  function meterLevel(line) {
    const n = line.report_count || 0;
    if (!n) return 0;
    if (line.corroborated) return 4;
    if (n >= 4) return 3;
    if (n >= 2) return 2;
    return 1;
  }

  function meterHTML(level, status) {
    if (!level) return '<span class="meter">────</span>';
    const full = '█'.repeat(level);
    const rest = '░'.repeat(4 - level);
    return `<span class="meter" data-s="${esc(status)}">${full}${rest ? `<i>${rest}</i>` : ''}</span>`;
  }

  /* --- Status ----------------------------------------------------------- */
  function statusKey(line) {
    if (line.in_service === false) {
      if (line.service_status === 'after_service') return 'ended';
      if (line.service_status === 'before_service') return 'before';
      return 'off';
    }
    if (line.status === 'disruption') return 'disruption';
    if (line.status === 'delay') return 'delay';
    if (line.status === 'minor') return 'minor';
    return 'none';
  }
  const statusText = line => t('st_' + statusKey(line));
  const isLive = k => k === 'disruption' || k === 'delay' || k === 'minor';

  /* --- Fetch ------------------------------------------------------------ */
  async function loadBoard() {
    try {
      const r = await fetch(api('/api/trafficmy/lines'), { signal: signal(15000) });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const d = await r.json();
      S.lines = d.lines || [];
      S.reports = d.recent_reports || [];
      S.meta = d;
      S.fetchedAt = Date.now();
      S.status = 'ok';
    } catch (e) {
      S.status = 'down';
      console.warn('[TrafficMY] board fetch failed:', e.message);
    }
    paintDot();
    paintGlance();
    paintBoard();
  }

  async function loadPins() {
    if (S.pins) return S.pins;
    try {
      const r = await fetch(api('/api/trafficmy/map/live?report_limit=120'), { signal: signal(15000) });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const d = await r.json();
      S.pins = d.reports || [];
    } catch (e) {
      console.warn('[TrafficMY] pins fetch failed:', e.message);
      S.pins = [];
    }
    return S.pins;
  }

  /* --- Paint: chrome ---------------------------------------------------- */
  function paintClock() {
    const p = mytParts();
    $('clock').textContent = `${p.hour}:${p.mm} MYT`;
  }

  function paintDot() {
    let s = S.status;
    if (s === 'ok' && S.fetchedAt && Date.now() - S.fetchedAt > 20 * 60e3) s = 'stale';
    $('dot').dataset.s = s;
    const b = $('staleBanner');
    b.hidden = s !== 'stale';
    if (!b.hidden) b.textContent = t('staleWarn');
  }

  function paintGlance() {
    const g = $('glance'), txt = $('glanceTxt'), meta = $('glanceMeta');

    if (S.status === 'load') {
      g.removeAttribute('data-s');
      txt.textContent = t('checking');
      meta.textContent = '';
      return;
    }
    if (S.status === 'down') {
      g.dataset.s = 'major';
      txt.innerHTML = `${esc(t('down'))}<span class="glance-sub">${esc(t('downSub'))}</span>`;
      meta.textContent = '';
      return;
    }

    const live = S.lines.filter(l => l.in_service !== false && isLive(statusKey(l)));
    const major = live.some(l => l.status === 'disruption');
    const delay = live.some(l => l.status === 'delay');

    if (!live.length) {
      g.dataset.s = 'ok';
      txt.innerHTML = `${esc(t('quiet'))}<span class="glance-sub">${esc(t('quietSub'))}</span>`;
    } else {
      g.dataset.s = major ? 'major' : delay ? 'delay' : 'ok';
      txt.innerHTML = `${esc(t('some')(live.length))}<span class="glance-sub">${esc(t('someSub'))}</span>`;
    }
    meta.textContent = S.fetchedAt ? ago(new Date(S.fetchedAt).toISOString()) : '';
  }

  /* --- Paint: board ----------------------------------------------------- */
  function visibleLines() {
    let out = S.lines.filter(l => !AGGREGATE.has(l.id) || (l.report_count || 0) > 0);
    if (S.filter === 'signals') {
      out = out.filter(l => l.in_service !== false && isLive(statusKey(l)));
    } else if (S.filter !== 'all') {
      out = out.filter(l => netOf(l) === S.filter);
    }
    return out;
  }

  const RANK = { disruption: 4, delay: 3, minor: 2, unknown: 1 };

  /* Synthetic aggregate buckets exist server-side to catch reports naming two
     lines at once. They are not lines you can board, so they only earn a row
     when they actually carry evidence. */
  const AGGREGATE = new Set(['kajang-putrajaya']);

  function paintBoard() {
    const host = $('board');

    if (S.status === 'down' && !S.lines.length) {
      host.innerHTML = `<div class="empty">
        <p class="empty-t">${esc(t('down'))}</p>
        <p class="empty-b">${esc(t('downSub'))}</p>
      </div>`;
      return;
    }

    const rows = visibleLines();
    if (!rows.length) {
      host.innerHTML = `<div class="empty"><p class="empty-t">${esc(t('noMatch'))}</p></div>`;
      return;
    }

    const sorted = rows.slice().sort((a, b) => {
      const ea = a.in_service === false ? 1 : 0;
      const eb = b.in_service === false ? 1 : 0;
      if (ea !== eb) return ea - eb;
      const ra = RANK[a.status] || 0, rb = RANK[b.status] || 0;
      if (ra !== rb) return rb - ra;
      return (b.report_count || 0) - (a.report_count || 0);
    });

    const open = sorted.filter(l => l.in_service !== false);
    const shut = sorted.filter(l => l.in_service === false);
    const peak = isPeak();

    let h = '';
    if (open.length) {
      h += head(t('live'), open.length);
      h += open.map(l => row(l, peak)).join('');
    }
    if (shut.length) {
      h += head(t('closed'), shut.length);
      h += shut.map(l => row(l, false)).join('');
    }
    host.innerHTML = h;
  }

  const head = (label, n) => `<div class="shead">
    <span class="shead-l">${esc(label)}</span><span class="shead-n">${n}</span></div>`;

  function row(l, peak) {
    const k = statusKey(l);
    const lvl = meterLevel(l);
    const dead = l.in_service === false;
    const q = dead ? 'ended' : (k === 'none' ? 'quiet' : 'live');
    const showPeak = peak && PEAK.has(l.id) && !dead;
    const age = (!dead && l.last_seen_at) ? ago(l.last_seen_at) : '';
    const n = l.report_count || 0;

    return `<button class="row" type="button" data-line="${esc(l.id)}" data-q="${q}"
        aria-label="${esc(l.name + ', ' + statusText(l))}">
      <span class="row-rail" style="background:${esc(l.id && l.color ? l.color : railColor(l))}"></span>
      <span class="row-main">
        <span class="row-name">${esc(l.name)}</span>
        <span class="row-sub">
          <span class="row-status" data-s="${esc(k)}">${esc(statusText(l))}</span>
          ${n ? `<span class="row-ev">${n} · ${l.corroborated ? 'official' : 'rider'}</span>` : ''}
        </span>
      </span>
      <span class="row-sig">
        ${dead ? '' : meterHTML(lvl, k)}
        ${age ? `<span class="row-age">${esc(age)}</span>` : ''}
        ${showPeak ? `<span class="pk">${esc(t('peak'))}</span>` : ''}
      </span>
    </button>`;
  }

  /* Fallback palette, mirroring the backend LINE_COLORS. Values are the
     operators' own `route_color` from the official GTFS static feeds, so the
     rail on screen matches the colour on station signage. */
  const FALLBACK = {
    'kelana-jaya': '#d50032', 'ampang-sri-petaling': '#e57200', 'kajang': '#047940',
    'putrajaya': '#ffcd00', 'kajang-putrajaya': '#00a651', 'monorail': '#84bd00',
    'brt-sunway': '#115740', 'ktm-komuter': '#dc2420', 'ktm-north': '#018000',
    'ets-intercity': '#ffc72c', 'klia-rail': '#7f1734', 'sabah-railway': '#9b6a31',
    'rapid-bus': '#e21836', 'penang': '#00843d', 'kuantan': '#008b8b',
    'mybas': '#0f766e', 'lrt3': '#00a9e0', 'ecrl': '#003d7a',
    'rts-johor': '#c41230', 'mrt3': '#2563eb', 'penang-lrt': '#0f766e',
  };
  const railColor = l => l.color || FALLBACK[l.id] || '#3f3f46';

  /* --- Sheet ------------------------------------------------------------ */
  async function openSheet(id) {
    const l = S.lines.find(x => x.id === id);
    if (!l) return;

    S.openLine = id;
    S.lastFocus = document.activeElement;

    $('sheetRail').style.background = railColor(l);
    $('sheetT').textContent = l.name;
    $('sheetBd').innerHTML = '<div class="load"><div class="spin"></div></div>';

    const scrim = $('scrim'), sheet = $('sheet');
    scrim.hidden = false; sheet.hidden = false;
    requestAnimationFrame(() => { scrim.classList.add('on'); sheet.classList.add('on'); });
    document.body.style.overflow = 'hidden';
    $('sheetX').focus();

    const [hist, pins] = await Promise.all([loadHistory(id), loadPins()]);
    if (S.openLine !== id) return;
    paintSheet(l, hist, pins.filter(p => p.line_id === id));
  }

  async function loadHistory(id) {
    try {
      const r = await fetch(api(`/api/trafficmy/lines/${encodeURIComponent(id)}/history?days=14`), { signal: signal(12000) });
      return r.ok ? await r.json() : null;
    } catch { return null; }
  }

  function paintSheet(l, hist, pins) {
    const k = statusKey(l);
    const lvl = meterLevel(l);
    const n = l.report_count || 0;
    const dead = l.in_service === false;
    let h = '';

    /* Verdict */
    h += `<div class="verdict">
      <span class="verdict-l" data-s="${esc(k)}">${esc(statusText(l))}</span>
      ${dead ? '' : meterHTML(lvl, k)}
    </div>`;

    /* Evidence ledger — the honest core */
    if (!dead) {
      h += `<div class="blk"><p class="blk-l">${esc(t('evidence'))}</p><div class="ledger">`;
      if (n) {
        h += `<b>${esc(t('reports')(n))}</b> · <u>${esc(l.corroborated ? t('official') : t('noOfficial'))}</u><br>`;
        if (l.last_seen_at) h += `${esc(t('latest'))} <b>${esc(clockMYT(l.last_seen_at))}</b> MYT · <u>${esc(ago(l.last_seen_at))} ago</u><br>`;
        if (l.sources) h += `${esc(t('srcs'))} <u>${esc(l.sources)}</u>`;
      } else {
        h += `<u>${esc(t('nothing'))}</u>`;
      }
      h += `</div></div>`;
    }

    /* Is this normal? — nobody else answers this */
    if (hist && hist.daily_counts && hist.daily_counts.length) {
      const d = hist.daily_counts;
      const max = Math.max(1, ...d.map(x => x.count));
      const todayKey = hist.today && hist.today.date;
      const bars = d.map(x => {
        const px = Math.max(2, Math.round((x.count / max) * 40));
        return `<div class="spark-b" data-today="${x.date === todayKey ? '1' : '0'}"
          style="height:${px}px" title="${esc(x.weekday)} ${esc(x.date)}: ${x.count}"></div>`;
      }).join('');

      const tod = hist.today || {};
      const cmpKey = tod.comparison || 'no_baseline';
      const typ = tod.typical_for_weekday;

      h += `<div class="blk">
        <p class="blk-l">${esc(t('normal'))}</p>
        <div class="spark" role="img" aria-label="14 day signal history">${bars}</div>
        <div class="spark-x"><span>${esc(d[0].weekday)}</span><span>${esc(t('today'))}</span></div>
        <span class="cmp" data-c="${esc(cmpKey)}">
          <b>${esc(t('today'))} ${tod.count ?? 0}</b>
          ${typ != null ? `<span>· ${esc(t('typical')(tod.weekday || ''))} ${typ}</span>` : ''}
          <b>· ${esc(L[S.lang].cmp[cmpKey] || cmpKey)}</b>
        </span>
      </div>`;
    }

    /* What riders said */
    if (!dead) {
      h += `<div class="blk"><p class="blk-l">${esc(t('said'))}</p>`;
      if (pins && pins.length) {
        h += pins.slice(0, 8).map(p => {
          const sev = p.status === 'disruption' ? 'disruption' : p.status === 'delay' ? 'delay' : 'minor';
          const srcs = String(p.sources || '').split(',').map(s => s.trim()).filter(Boolean);
          return `<div class="rep" data-s="${esc(sev)}">
            <p class="rep-t">${esc(p.summary || p.headline || '')}</p>
            <p class="rep-m">
              ${p.location ? `<span>${esc(p.location)}</span>` : ''}
              ${srcs.map(s => `<span class="tag"${s === 'official' ? ' data-official' : ''}>${esc(s)}</span>`).join('')}
            </p>
          </div>`;
        }).join('');
      } else if (l.reason) {
        h += `<div class="rep" data-s="${esc(k)}"><p class="rep-t">${esc(l.reason)}</p></div>`;
      } else {
        h += `<p class="blk-b">${esc(t('nothingSub'))}</p>`;
      }
      h += `</div>`;
    }

    /* Official source */
    if (l.timetable_url) {
      h += `<a class="lnk" href="${esc(l.timetable_url)}" target="_blank" rel="noopener">
        ${esc(t('timetable'))} ↗</a>`;
    }

    $('sheetBd').innerHTML = h;
  }

  function closeSheet() {
    S.openLine = null;
    const scrim = $('scrim'), sheet = $('sheet');
    scrim.classList.remove('on'); sheet.classList.remove('on');
    document.body.style.overflow = '';
    setTimeout(() => { scrim.hidden = true; sheet.hidden = true; }, 320);
    if (S.lastFocus && S.lastFocus.focus) S.lastFocus.focus();
  }

  /* --- Map -------------------------------------------------------------- */
  /* Deliberately NO route-shape overlay. The GTFS shapes were wrong and a
     wrong map is worse than no map. Rider report pins only, labelled as such. */
  async function initMap() {
    if (S.map) return;
    S.map = 'loading';
    const note = $('mapNote');
    note.textContent = t('mapLoad');

    try {
      await Promise.all([
        loadCSS('https://unpkg.com/maplibre-gl@5.24.0/dist/maplibre-gl.css'),
        loadJS('https://unpkg.com/maplibre-gl@5.24.0/dist/maplibre-gl.js'),
      ]);
    } catch {
      note.textContent = t('mapFail');
      S.map = null;
      return;
    }

    /* OpenFreeMap: keyless vector tiles. CARTO's basemap now demands an API
       key and stamps "API KEY REQUIRED" across every tile, so it cannot ship. */
    const map = new maplibregl.Map({
      container: 'map',
      style: 'https://tiles.openfreemap.org/styles/dark',
      center: [101.6869, 3.1390],
      zoom: 10.5,
      attributionControl: { compact: true },
    });
    S.map = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');

    const [pins, routes] = await Promise.all([loadPins(), loadRoutes()]);
    const placed = pins.filter(p => typeof p.lat === 'number' && typeof p.lon === 'number');

    note.textContent = placed.length ? t('mapNote')(placed.length) : t('mapEmpty');

    map.on('load', () => {
      drawRoutes(map, routes);

      placed.forEach(p => {
        const el = document.createElement('div');
        el.style.cssText = `width:12px;height:12px;border-radius:50%;
          background:${p.color || '#f5a524'};border:2px solid #0a0a0b;
          box-shadow:0 0 0 1px ${p.color || '#f5a524'}66;cursor:pointer`;
        new maplibregl.Marker({ element: el })
          .setLngLat([p.lon, p.lat])
          .setPopup(new maplibregl.Popup({ offset: 14, closeButton: false }).setHTML(
            `<strong style="display:block;margin-bottom:4px">${esc(p.entity || p.location || 'Report')}</strong>
             <span style="color:#a1a1aa">${esc((p.summary || '').slice(0, 140))}</span>`
          ))
          .addTo(map);
      });
      /* Frame the network, not just the incidents — an empty-report day should
         still show a usable map rather than the default world view. */
      const b = new maplibregl.LngLatBounds();
      let any = false;
      placed.forEach(p => { b.extend([p.lon, p.lat]); any = true; });
      if (!any && routes) {
        (routes.features || []).forEach(f => {
          (f.geometry?.coordinates || []).forEach(c => { b.extend(c); any = true; });
        });
      }
      if (any) map.fitBounds(b, { padding: 48, maxZoom: 13, duration: 0 });
    });
  }

  /* Official Prasarana route geometry (GTFS shapes.txt), coloured with the
     operators' own route_color. Drawn beneath the report pins. */
  async function loadRoutes() {
    try {
      const r = await fetch(api('/api/trafficmy/map/rail-lines'), { signal: signal(15000) });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return await r.json();
    } catch (e) {
      console.warn('[TrafficMY] routes fetch failed:', e.message);
      return null;
    }
  }

  function drawRoutes(map, geo) {
    if (!geo || !geo.features || !geo.features.length) return;
    if (map.getSource('routes')) return;

    map.addSource('routes', { type: 'geojson', data: geo });

    // Dark casing first so line colours stay legible where routes overlap.
    map.addLayer({
      id: 'routes-casing',
      type: 'line',
      source: 'routes',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': '#0a0a0b',
        'line-opacity': 0.9,
        'line-width': ['interpolate', ['linear'], ['zoom'], 9, 4, 13, 7.5, 16, 11],
      },
    });

    map.addLayer({
      id: 'routes-line',
      type: 'line',
      source: 'routes',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': ['coalesce', ['get', 'color'], '#3f3f46'],
        'line-width': ['interpolate', ['linear'], ['zoom'], 9, 1.8, 13, 3.4, 16, 5.5],
      },
    });
  }

  const loadJS = src => new Promise((res, rej) => {
    if (window.maplibregl) return res();
    const s = document.createElement('script');
    s.src = src; s.onload = res; s.onerror = rej;
    document.head.appendChild(s);
  });

  const loadCSS = href => new Promise(res => {
    if (document.querySelector(`link[href="${href}"]`)) return res();
    const l = document.createElement('link');
    l.rel = 'stylesheet'; l.href = href; l.onload = res; l.onerror = res;
    document.head.appendChild(l);
  });

  /* --- Plan ------------------------------------------------------------- */
  /* Honest: TrafficMY does not run a routing engine. Pretending to would be
     the exact "larp" the rest of this rebuild removes. Point at the real one. */
  function paintPlan() {
    const en = S.lang === 'en';
    $('planBody').innerHTML = `
      <h2>${en ? 'Route planning' : 'Rancang perjalanan'}</h2>
      <p>${en
        ? 'TrafficMY does not run its own routing engine. It reports what riders are saying. For actual routes, times and fares, these are the authoritative sources:'
        : 'TrafficMY tidak menjalankan enjin laluan sendiri. Ia melaporkan apa yang penumpang katakan. Untuk laluan, masa dan tambang sebenar, gunakan sumber rasmi ini:'}</p>
      <p><a class="lnk" href="https://myrapid.com.my/plan-your-journey/" target="_blank" rel="noopener">Rapid KL journey planner ↗</a></p>
      <p><a class="lnk" href="https://www.google.com/maps/dir/?api=1&travelmode=transit" target="_blank" rel="noopener">Google Maps transit ↗</a></p>
      <p><a class="lnk" href="https://www.ktmb.com.my/" target="_blank" rel="noopener">KTMB ↗</a></p>
      <h2>${en ? 'How to use both' : 'Cara guna kedua-dua'}</h2>
      <p>${en
        ? 'Plan the route there. Check the board here before you leave. If a line shows reports with three or four bars of evidence, consider the alternative before you commit to the platform.'
        : 'Rancang laluan di sana. Semak papan di sini sebelum bergerak. Jika satu laluan menunjukkan bukti tiga atau empat bar, pertimbangkan alternatif sebelum ke platform.'}</p>`;
  }

  /* --- About ------------------------------------------------------------ */
  function paintAbout() {
    const en = S.lang === 'en';
    $('aboutBody').innerHTML = `
      <h2>${en ? 'What this is' : 'Apa ini'}</h2>
      <p>${en
        ? 'TrafficMY reads public rider posts about Malaysian transit and groups them by line. It shows what was reported today, Malaysia time, and how strong that evidence is.'
        : 'TrafficMY membaca hantaran awam penumpang tentang transit Malaysia dan mengumpulkannya mengikut laluan. Ia menunjukkan apa yang dilaporkan hari ini, waktu Malaysia, dan sekuat mana bukti itu.'}</p>
      <p><strong>${en
        ? 'A quiet line is not an all-clear.'
        : 'Laluan yang sunyi bukan bermakna lancar.'}</strong> ${en
        ? 'It means nothing was captured. Operators do not feed this board. Absence of a report is absence of data, nothing more.'
        : 'Ia bermakna tiada apa yang direkodkan. Pengendali tidak menyuap papan ini. Ketiadaan laporan ialah ketiadaan data, tiada lebih.'}</p>

      <h2>${en ? 'Reading the meter' : 'Membaca meter'}</h2>
      <div class="prose-key">
        <b>████</b> <span>${en ? 'rider reports matched by an official notice' : 'laporan penumpang dipadan notis rasmi'}</span><br>
        <b>███</b><i>░</i> <span>${en ? 'four or more independent reports' : 'empat atau lebih laporan bebas'}</span><br>
        <b>██</b><i>░░</i> <span>${en ? 'two or three reports' : 'dua atau tiga laporan'}</span><br>
        <b>█</b><i>░░░</i> <span>${en ? 'a single unverified report' : 'satu laporan belum disahkan'}</span><br>
        <b>────</b> <span>${en ? 'nothing captured today' : 'tiada rekod hari ini'}</span>
      </div>

      <h2>${en ? 'Sources' : 'Sumber'}</h2>
      <p>${en
        ? 'Threads, Reddit and official operator RSS. Collected roughly every 15 minutes. The board resets at midnight Malaysia time.'
        : 'Threads, Reddit dan RSS rasmi pengendali. Dikumpul lebih kurang setiap 15 minit. Papan ini set semula tengah malam waktu Malaysia.'}</p>

      <h2>${en ? 'Privacy' : 'Privasi'}</h2>
      <p>${en
        ? 'Usernames are never republished. Rider wording is summarised, not quoted in full.'
        : 'Nama pengguna tidak disiarkan semula. Perkataan penumpang diringkaskan, bukan dipetik penuh.'}</p>

      <p><a class="lnk" href="${BASE}/methodology">${en ? 'Full methodology' : 'Metodologi penuh'} ↗</a></p>`;
  }

  /* --- Tabs ------------------------------------------------------------- */
  function tab(pid) {
    S.tab = pid;
    document.querySelectorAll('.panel').forEach(p => p.classList.toggle('on', p.id === pid));
    document.querySelectorAll('.nav-b').forEach(b => {
      b.setAttribute('aria-selected', String(b.dataset.p === pid));
    });
    if (pid === 'pMap') initMap();
    if (pid === 'pPlan') paintPlan();
    if (pid === 'pAbout') paintAbout();
    try { localStorage.setItem('tm.tab', pid); } catch {}
  }

  /* --- Language --------------------------------------------------------- */
  function toggleLang() {
    S.lang = S.lang === 'ms' ? 'en' : 'ms';
    try { localStorage.setItem('tm.lang', S.lang); } catch {}
    document.documentElement.lang = S.lang;
    $('lang').textContent = S.lang === 'ms' ? 'BM' : 'EN';
    paintDot(); paintGlance(); paintBoard();
    if (S.tab === 'pPlan') paintPlan();
    if (S.tab === 'pAbout') paintAbout();
    if (S.openLine) openSheet(S.openLine);
    if (S.map && S.map !== 'loading' && S.pins) {
      const n = S.pins.filter(p => typeof p.lat === 'number').length;
      $('mapNote').textContent = n ? t('mapNote')(n) : t('mapEmpty');
    }
  }

  /* --- Init ------------------------------------------------------------- */
  function init() {
    document.documentElement.lang = S.lang;
    $('lang').textContent = S.lang === 'ms' ? 'BM' : 'EN';

    paintClock();
    setInterval(paintClock, 20000);
    setInterval(paintDot, 60000);

    $('refresh').addEventListener('click', async e => {
      const b = e.currentTarget;
      b.dataset.spin = '1';
      S.pins = null;
      await loadBoard();
      delete b.dataset.spin;
    });

    $('lang').addEventListener('click', toggleLang);

    document.querySelectorAll('.nav-b').forEach(b => {
      b.addEventListener('click', () => tab(b.dataset.p));
    });

    document.querySelector('.filter').addEventListener('click', e => {
      const c = e.target.closest('.chip');
      if (!c) return;
      S.filter = c.dataset.f;
      document.querySelectorAll('.chip').forEach(x => {
        x.setAttribute('aria-pressed', String(x === c));
      });
      paintBoard();
    });

    $('board').addEventListener('click', e => {
      const r = e.target.closest('.row');
      if (r) openSheet(r.dataset.line);
    });

    $('sheetX').addEventListener('click', closeSheet);
    $('scrim').addEventListener('click', closeSheet);
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && S.openLine) closeSheet();
    });

    try {
      const saved = localStorage.getItem('tm.tab');
      if (saved && document.getElementById(saved)) tab(saved);
    } catch {}

    loadBoard();
    setInterval(() => { S.pins = null; loadBoard(); }, 5 * 60e3);

    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register(BASE + '/sw.js', { scope: (BASE || '') + '/' }).catch(() => {});
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
