/* Secrets Sync UI. Data comes only from api/status.json (names, never values). All DOM is built with
 * createElement/textContent; nothing from the state is ever interpreted as markup. Pure builders take an
 * injected `doc` so they can be unit tested with node --test (tests/web/js). */
(function (root) {
  'use strict';

  var MAX_KEYS = 500;
  var MAX_USAGE = 300;
  var MAX_EVENTS = 100;
  var MAX_REFS = 20;
  var TABS = ['keys', 'synthetic', 'usage', 'events'];
  var POLL_MS = 15000;
  var COPY_HINT = 'Double-click to copy';

  function isObj(v) { return v !== null && typeof v === 'object' && !Array.isArray(v); }
  function asObj(v) { return isObj(v) ? v : {}; }
  function asArr(v) { return Array.isArray(v) ? v : []; }
  function str(v) { return v === null || v === undefined ? '' : String(v); }
  function dash(v) { var s = str(v); return s === '' ? '-' : s; }

  /* h(doc, tag, {cls, text, attrs, on}, children) -> element; children may be nodes or strings. */
  function h(doc, tag, opts, kids) {
    var el = doc.createElement(tag);
    opts = opts || {};
    if (opts.cls) el.className = opts.cls;
    if (opts.text !== undefined) el.textContent = str(opts.text);
    var attrs = opts.attrs || {};
    Object.keys(attrs).forEach(function (k) { el.setAttribute(k, str(attrs[k])); });
    var on = opts.on || {};
    Object.keys(on).forEach(function (k) { el.addEventListener(k, on[k]); });
    asArr(kids).forEach(function (kid) {
      if (kid === null || kid === undefined) return;
      el.appendChild(typeof kid === 'string' ? doc.createTextNode(kid) : kid);
    });
    return el;
  }

  function clear(el) {
    if (typeof el.replaceChildren === 'function') el.replaceChildren();
    else el.textContent = '';
  }

  function relTime(iso, now) {
    if (typeof iso !== 'string') return '-';
    var t = Date.parse(iso);
    if (isNaN(t)) return '-';
    var secs = Math.floor(((now instanceof Date ? now.getTime() : Date.now()) - t) / 1000);
    if (secs < 0) return 'just now';
    var units = [['d', 86400], ['h', 3600], ['min', 60]];
    for (var i = 0; i < units.length; i++) {
      if (secs >= units[i][1]) return Math.floor(secs / units[i][1]) + ' ' + units[i][0] + ' ago';
    }
    return secs + ' s ago';
  }

  function isStale(state) {
    if (state.stale === true) return true;
    var age = state.age_seconds, iv = state.interval;
    return typeof age === 'number' && typeof iv === 'number' && age > 2 * iv;
  }

  /* {label, cls}: stale when ok but stale, starting when status is missing/unknown. */
  function statusInfo(state) {
    var s = typeof state.status === 'string' && state.status ? state.status : 'starting';
    if (s === 'ok' && isStale(state)) s = 'stale';
    var known = ['ok', 'degraded', 'error', 'stale', 'starting'];
    return { label: s, cls: known.indexOf(s) >= 0 ? s : 'starting' };
  }

  function filterKeys(names, query) {
    var q = str(query).trim().toLowerCase();
    var all = asArr(names).map(str);
    if (!q) return all;
    return all.filter(function (n) { return n.toLowerCase().indexOf(q) >= 0; });
  }

  function pickTab(hash, stored) {
    var fromHash = str(hash).replace(/^#/, '');
    if (TABS.indexOf(fromHash) >= 0) return fromHash;
    return TABS.indexOf(stored) >= 0 ? stored : 'keys';
  }

  function syntheticSet(state) {
    var set = {};
    asArr(asObj(state.keys).synthetic).forEach(function (n) { set[str(n)] = true; });
    return set;
  }

  /* ---- builders (return DOM nodes) ---- */

  function buildBadges(doc, state, now) {
    var info = statusInfo(state);
    var versions = asObj(state.versions);
    var when = state.last_success_at;
    return [
      h(doc, 'span', { cls: 'badge ' + info.cls, text: info.label }),
      h(doc, 'span', { cls: 'badge', text: dash(state.items) + ' items' }),
      h(doc, 'span', { cls: 'badge', text: 'synced ' + relTime(when, now), attrs: { title: str(when) } }),
      h(doc, 'span', { cls: 'badge', text: 'v' + dash(versions.addon) })
    ];
  }

  function stat(doc, label, value, cls) {
    return h(doc, 'div', {}, [
      h(doc, 'div', { cls: 'k', text: label }),
      h(doc, 'div', { cls: cls || '', text: dash(value) })
    ]);
  }

  function buildGeneral(doc, state, now) {
    var versions = asObj(state.versions);
    var out = [
      stat(doc, 'Last attempt', relTime(state.last_attempt_at, now)),
      stat(doc, 'Next sync', state.next_sync_at),
      stat(doc, 'Error', state.error_code, state.error_code ? 'error' : ''),
      stat(doc, 'bw', versions.bw),
      stat(doc, 'sops', versions.sops)
    ];
    var check = state.check;
    if (isObj(check)) {
      var res = typeof check.result === 'string' ? check.result : '';
      out.push(stat(doc, 'Change check', check.enabled === true ? 'every ' + str(check.interval) + ' s' : 'disabled'));
      out.push(stat(doc, 'Last check', relTime(check.last_check_at, now)));
      out.push(stat(doc, 'Check result', res, res));
      out.push(stat(doc, 'Check error', check.error_code, check.error_code ? 'error' : ''));
      out.push(stat(doc, 'Triggered syncs', check.triggered_syncs === undefined ? 0 : check.triggered_syncs));
    }
    return out;
  }

  /* Copy text to the clipboard: async Clipboard API when available, else a hidden textarea + execCommand (the
   * ingress iframe may lack clipboard permission). Resolves to true/false, never rejects. */
  function copyText(win, text) {
    function fallback() {
      try {
        var d = win.document;
        var ta = d.createElement('textarea');
        ta.value = text;
        ta.setAttribute('readonly', '');
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        d.body.appendChild(ta);
        ta.select();
        var ok = !!d.execCommand('copy');
        d.body.removeChild(ta);
        return ok;
      } catch (e) { return false; }
    }
    var nav = win.navigator;
    if (nav && nav.clipboard && typeof nav.clipboard.writeText === 'function') {
      try {
        return Promise.resolve(nav.clipboard.writeText(text)).then(function () { return true; },
          function () { return fallback(); });
      } catch (e) { return Promise.resolve(fallback()); }
    }
    return Promise.resolve(fallback());
  }

  function chips(doc, names, synthetic, cls) {
    var list = asArr(names).map(str);
    var kids = list.slice(0, MAX_KEYS).map(function (n) {
      var kid = [h(doc, 'span', { cls: 'key' + (cls ? ' ' + cls : ''), text: n, attrs: { title: COPY_HINT } })];
      if (synthetic && synthetic[n]) kid.push(h(doc, 'span', { cls: 'tag', text: 'synthetic' }));
      return h(doc, 'span', {}, kid);
    });
    if (list.length > MAX_KEYS) kids.push(h(doc, 'span', { cls: 'k', text: '+' + (list.length - MAX_KEYS) + ' more' }));
    if (!kids.length) kids.push(h(doc, 'span', { cls: 'k', text: '-' }));
    return h(doc, 'div', { cls: 'chips' }, kids);
  }

  /* Shrink guard card: only while error_code == shrink_guard and guard is an object. null otherwise. */
  function buildGuardCard(doc, state, onApply) {
    var guard = state.guard;
    if (state.error_code !== 'shrink_guard' || !isObj(guard)) return null;
    var removed = asArr(guard.removed);
    var count = removed.length;
    var btn = h(doc, 'button', {
      cls: 'danger', text: 'Apply anyway', attrs: { type: 'button' },
      on: { click: function () { if (onApply) onApply(count); } }
    });
    return h(doc, 'section', { cls: 'card guard' }, [
      h(doc, 'h2', { cls: 'bad', text: 'Write blocked by the shrink guard' }),
      h(doc, 'p', {
        text: 'The new set has ' + dash(guard.new_items) + ' keys, the last write had ' + dash(guard.last_items) +
          '. Nothing was written; secrets.yaml is unchanged. Applying removes the keys below from secrets.yaml ' +
          '(the previous file is kept as .bak).'
      }),
      h(doc, 'h3', { cls: 'bad', text: 'Would be removed (' + count + ')' }),
      chips(doc, removed, null, 'bad'),
      h(doc, 'h3', { text: 'Would be added (' + asArr(guard.added).length + ')' }),
      chips(doc, guard.added, null),
      h(doc, 'h3', { text: 'Would change (' + asArr(guard.changed).length + ')' }),
      chips(doc, guard.changed, null),
      h(doc, 'p', {}, [btn])
    ]);
  }

  function buildProviders(doc, state) {
    var provs = asObj(state.providers);
    var names = Object.keys(provs).sort();
    if (!names.length) return h(doc, 'div', { cls: 'k', text: 'no providers reported yet' });
    var head = h(doc, 'tr', {}, ['Provider', 'Status', 'Items', 'Revision', 'Last success', 'Error', 'Problems'].map(
      function (t) { return h(doc, 'th', { text: t }); }));
    var rows = names.map(function (name) {
      var p = asObj(provs[name]);
      var st = typeof p.status === 'string' ? p.status : 'unknown';
      var problems = asArr(p.problems).map(function (pr) {
        pr = asObj(pr);
        return h(doc, 'div', {}, [
          h(doc, 'span', { cls: pr.severity === 'error' ? 'error' : 'warning', text: str(pr.severity) + ': ' }),
          h(doc, 'code', { text: str(pr.code) }),
          ' ' + str(pr.message)
        ]);
      });
      return h(doc, 'tr', {}, [
        h(doc, 'td', { text: name }),
        h(doc, 'td', { cls: st, text: st }),
        h(doc, 'td', { text: dash(p.items) }),
        h(doc, 'td', {}, [h(doc, 'code', { text: dash(p.revision) })]),
        h(doc, 'td', { text: dash(p.last_success_at) }),
        h(doc, 'td', { text: dash(p.error_code) }),
        h(doc, 'td', {}, problems)
      ]);
    });
    return h(doc, 'table', {}, [head].concat(rows));
  }

  function section(doc, title, cls) {
    return h(doc, 'h3', { cls: cls || '', text: title });
  }

  function buildKeysPanel(doc, state, query) {
    var keys = asObj(state.keys);
    var syn = syntheticSet(state);
    var out = [];
    [['Added', keys.added], ['Removed', keys.removed], ['Changed', keys.changed]].forEach(function (s) {
      var list = filterKeys(s[1], query);
      if (!list.length) return;
      out.push(section(doc, s[0] + ' (' + list.length + ')', s[0] === 'Removed' ? 'bad' : ''));
      out.push(chips(doc, list, syn));
    });
    var all = filterKeys(keys.names, query);
    out.push(section(doc, 'All keys (' + all.length + ')'));
    out.push(chips(doc, all, syn));
    return out;
  }

  function buildSyntheticPanel(doc, state) {
    var items = asArr(state.synthetic).map(asObj);
    if (!items.length) {
      return [h(doc, 'div', { cls: 'k', text: 'No synthetic keys configured (option synthetic_keys).' })];
    }
    var head = h(doc, 'tr', {}, ['Key', 'Template', 'Uses', 'Status'].map(function (t) {
      return h(doc, 'th', { text: t });
    }));
    var rows = items.map(function (it) {
      var st = ['ok', 'pending', 'error'].indexOf(it.status) >= 0 ? it.status : 'pending';
      var label = { ok: 'ok', pending: 'parsed (not rendered yet)', error: 'error' }[st];
      if (it.error_code) label += ' ' + str(it.error_code);
      return h(doc, 'tr', {}, [
        h(doc, 'td', {}, [h(doc, 'code', { text: str(it.name) })]),
        h(doc, 'td', {}, [h(doc, 'code', { text: str(it.template) })]),
        h(doc, 'td', {}, [chips(doc, it.refs, null)]),
        h(doc, 'td', { cls: st === 'error' ? 'error' : st, text: label })
      ]);
    });
    return [h(doc, 'div', { cls: 'scroll' }, [h(doc, 'table', {}, [head].concat(rows))])];
  }

  function usageEntries(doc, map, query, bad) {
    var names = filterKeys(Object.keys(asObj(map)), query).sort();
    var out = names.slice(0, MAX_USAGE).map(function (name) {
      var e = asObj(asObj(map)[name]);
      var refs = asArr(e.refs).slice(0, MAX_REFS).map(function (r) {
        r = asObj(r);
        return h(doc, 'div', {}, [h(doc, 'code', { text: str(r.file) + ':' + str(r.line) })]);
      });
      var total = typeof e.count === 'number' ? e.count : refs.length;
      if (total > refs.length) refs.push(h(doc, 'div', { cls: 'k', text: '+' + (total - refs.length) + ' more' }));
      return h(doc, 'details', {}, [
        h(doc, 'summary', {}, [
          h(doc, 'span', { cls: 'key' + (bad ? ' bad' : ''), text: name, attrs: { title: COPY_HINT } }),
          h(doc, 'span', { cls: 'k', text: ' ' + total + (total === 1 ? ' use' : ' uses') })
        ])
      ].concat(refs));
    });
    if (names.length > MAX_USAGE) out.push(h(doc, 'div', { cls: 'k', text: '+' + (names.length - MAX_USAGE) + ' more' }));
    return out;
  }

  function buildUsagePanel(doc, state, query) {
    var usage = asObj(state.usage);
    if (usage.enabled !== true) {
      return [h(doc, 'div', { cls: 'k', text: 'Usage scan is off (option usage_scan).' })];
    }
    var roots = asArr(usage.roots).map(str).join(', ') || '-';
    var note = usage.truncated ? ' (scan stopped at a limit)' : '';
    var out = [h(doc, 'div', {
      cls: 'k',
      text: dash(usage.files_scanned) + ' YAML files scanned in ' + roots + ' at ' + dash(usage.scanned_at) + note +
        '. Looks for !secret key; values are never read.'
    })];
    var missing = usageEntries(doc, usage.missing, query, true);
    if (missing.length) {
      out.push(section(doc, 'Referenced but missing in secrets.yaml (' + Object.keys(asObj(usage.missing)).length + ')',
        'bad'));
      out = out.concat(missing);
    }
    var unused = filterKeys(usage.unused, query);
    out.push(section(doc, 'Unused (' + unused.length + ')'));
    out.push(chips(doc, unused, null));
    var used = usageEntries(doc, usage.used, query, false);
    out.push(section(doc, 'Used (' + Object.keys(asObj(usage.used)).length + ')'));
    if (used.length) out = out.concat(used);
    else out.push(h(doc, 'div', { cls: 'k', text: 'no references found' }));
    return out;
  }

  function buildEvents(doc, state) {
    var events = asArr(state.events).map(asObj).slice(0, MAX_EVENTS);
    if (!events.length) return h(doc, 'div', { cls: 'k', text: 'no events' });
    var head = h(doc, 'tr', {}, ['Time', 'Level', 'Code', 'Message'].map(function (t) { return h(doc, 'th', { text: t }); }));
    var rows = events.map(function (ev) {
      var level = ['info', 'warning', 'error'].indexOf(ev.level) >= 0 ? ev.level : '';
      return h(doc, 'tr', {}, [
        h(doc, 'td', { text: str(ev.at) }),
        h(doc, 'td', { cls: level, text: str(ev.level) }),
        h(doc, 'td', {}, [h(doc, 'code', { text: str(ev.code) })]),
        h(doc, 'td', { text: str(ev.message) })
      ]);
    });
    return h(doc, 'table', {}, [head].concat(rows));
  }

  /* Preview result: key names only. */
  function buildPreview(doc, result, onClose) {
    var r = asObj(result);
    var kids = [
      h(doc, 'div', { cls: 'row' }, [
        h(doc, 'h2', { text: 'Preview (dry run, nothing written)' }),
        h(doc, 'button', { cls: 'secondary', text: 'Close', attrs: { type: 'button' }, on: { click: onClose } })
      ])
    ];
    [['Added', r.added], ['Removed', r.removed], ['Changed', r.changed]].forEach(function (s) {
      kids.push(section(doc, s[0] + ' (' + asArr(s[1]).length + ')', s[0] === 'Removed' ? 'bad' : ''));
      kids.push(chips(doc, s[1], null));
    });
    var errors = asArr(r.errors);
    if (errors.length) {
      kids.push(section(doc, 'Errors (' + errors.length + ')', 'bad'));
      errors.forEach(function (e) {
        var text = typeof e === 'string' ? e : isObj(e) ? (str(e.code) + ' ' + str(e.message)).trim() : str(e);
        kids.push(h(doc, 'div', { cls: 'error', text: text }));
      });
    }
    return kids;
  }

  /* ---- page wiring (browser only) ---- */

  function init(win) {
    var doc = win.document;
    var $ = function (id) { return doc.getElementById(id); };
    var ui = { state: {}, tab: 'keys', timers: [], busy: false };

    function storedTab() {
      try { return win.localStorage.getItem('ss-tab'); } catch (e) { return null; }
    }
    function storeTab(t) {
      try { win.localStorage.setItem('ss-tab', t); } catch (e) { /* ignore */ }
    }
    function fill(el, nodes) {
      clear(el);
      asArr(nodes).forEach(function (n) { if (n) el.appendChild(n); });
    }

    function renderTabs() {
      TABS.forEach(function (t) {
        var sel = t === ui.tab;
        $('tab-' + t).setAttribute('aria-selected', sel ? 'true' : 'false');
        $('tab-' + t).setAttribute('tabindex', sel ? '0' : '-1');
        $('panel-' + t).hidden = !sel;
      });
    }

    function renderCounts(state) {
      var keys = asObj(state.keys), usage = asObj(state.usage);
      $('count-keys').textContent = asArr(keys.names).length ? '(' + asArr(keys.names).length + ')' : '';
      $('count-synthetic').textContent = asArr(state.synthetic).length ? '(' + asArr(state.synthetic).length + ')' : '';
      $('count-usage').textContent = usage.enabled === true ? '(' + Object.keys(asObj(usage.missing)).length + ' missing)' : '';
      $('count-events').textContent = asArr(state.events).length ? '(' + asArr(state.events).length + ')' : '';
    }

    function renderKeys() { fill($('body-keys'), buildKeysPanel(doc, ui.state, $('search-keys').value)); }
    function renderUsage() { fill($('body-usage'), buildUsagePanel(doc, ui.state, $('search-usage').value)); }

    function render() {
      var s = ui.state, now = new Date();
      fill($('badges'), buildBadges(doc, s, now));
      fill($('general'), buildGeneral(doc, s, now));
      fill($('guard'), [buildGuardCard(doc, s, applyAnyway)]);
      fill($('providers'), [buildProviders(doc, s)]);
      fill($('body-synthetic'), buildSyntheticPanel(doc, s));
      fill($('body-events'), [buildEvents(doc, s)]);
      renderKeys();
      renderUsage();
      renderCounts(s);
      renderTabs();
    }

    function setUpdated(text) { $('updated').textContent = text; }
    function notice(text) {
      var el = $('notice');
      el.textContent = text || '';
      el.hidden = !text;
    }

    function refresh() {
      return win.fetch('api/status.json', { cache: 'no-store' }).then(function (r) {
        if (!r.ok) throw new Error('status ' + r.status);
        return r.json();
      }).then(function (data) {
        ui.state = isObj(data) ? data : {};
        render();
        ui.lastUpdate = new Date().toLocaleTimeString();
        setUpdated('updated ' + ui.lastUpdate);
        notice('');
      }).catch(function () {
        notice('Offline: could not load the status. Showing the last data' +
          (ui.lastUpdate ? ' (last update ' + ui.lastUpdate + ').' : '.'));
        setUpdated('offline');
      });
    }

    function refreshSoon() {
      ui.timers.forEach(win.clearTimeout);
      ui.timers = [win.setTimeout(refresh, 3000), win.setTimeout(refresh, 10000)];
    }

    function post(url, label) {
      return win.fetch(url, { method: 'POST' }).then(function (r) {
        if (r.status === 202) notice(label + ': started.');
        else if (r.status === 429) notice(label + ': rate limited, try again in a few seconds.');
        else if (r.status === 403) notice(label + ': not allowed (ingress only).');
        else notice(label + ': failed (' + r.status + ').');
        return r;
      }).catch(function () { notice(label + ': request failed.'); });
    }

    function applyAnyway(count) {
      if (!win.confirm('Remove ' + count + ' keys from secrets.yaml?')) return;
      post('api/sync?force=1', 'Apply anyway').then(refreshSoon);
    }

    function closePreview() { $('preview').hidden = true; clear($('preview')); }

    function preview() {
      win.fetch('api/preview', { method: 'POST' }).then(function (r) {
        if (!r.ok) throw new Error('status ' + r.status);
        return r.json();
      }).then(function (data) {
        fill($('preview'), buildPreview(doc, data, closePreview));
        $('preview').hidden = false;
        refreshSoon();
      }).catch(function () { notice('Preview failed.'); });
    }

    function selectTab(t) {
      ui.tab = t;
      storeTab(t);
      try { win.history.replaceState(null, '', '#' + t); } catch (e) { /* ignore */ }
      renderTabs();
    }

    TABS.forEach(function (t, i) {
      var btn = $('tab-' + t);
      btn.addEventListener('click', function () { selectTab(t); });
      btn.addEventListener('keydown', function (ev) {
        var d = ev.key === 'ArrowRight' ? 1 : ev.key === 'ArrowLeft' ? -1 : 0;
        if (!d) return;
        var next = TABS[(i + d + TABS.length) % TABS.length];
        selectTab(next);
        $('tab-' + next).focus();
        ev.preventDefault();
      });
    });
    win.addEventListener('hashchange', function () { ui.tab = pickTab(win.location.hash, ui.tab); renderTabs(); });
    $('search-keys').addEventListener('input', renderKeys);
    $('search-usage').addEventListener('input', renderUsage);
    $('btn-sync').addEventListener('click', function () { post('api/sync', 'Sync').then(refreshSoon); });
    $('btn-preview').addEventListener('click', preview);
    $('btn-refresh').addEventListener('click', refresh);

    // Double-click on a key name copies the whole name (keys are one unit: select-all in CSS)
    doc.addEventListener('dblclick', function (ev) {
      var el = ev.target && ev.target.closest ? ev.target.closest('.key') : null;
      if (!el) return;
      ev.preventDefault();
      var name = el.textContent;
      copyText(win, name).then(function (ok) {
        if (ok) {
          el.classList.add('copied');
          win.setTimeout(function () { el.classList.remove('copied'); }, 900);
        }
        notice(ok ? 'Copied "' + name + '" to the clipboard.' : 'Copy failed: clipboard not available.');
        win.setTimeout(function () { notice(''); }, 2500);
      });
    });

    var poll = null;
    function startPoll() { if (!poll) poll = win.setInterval(refresh, POLL_MS); }
    function stopPoll() { if (poll) { win.clearInterval(poll); poll = null; } }
    doc.addEventListener('visibilitychange', function () {
      if (doc.hidden) stopPoll();
      else { refresh(); startPoll(); }
    });

    ui.tab = pickTab(win.location.hash, storedTab());
    renderTabs();
    refresh();
    if (!doc.hidden) startPoll();
  }

  var api = {
    h: h, copyText: copyText, relTime: relTime, statusInfo: statusInfo, filterKeys: filterKeys, pickTab: pickTab, isStale: isStale,
    buildBadges: buildBadges, buildGeneral: buildGeneral, buildGuardCard: buildGuardCard,
    buildProviders: buildProviders, buildKeysPanel: buildKeysPanel, buildSyntheticPanel: buildSyntheticPanel,
    buildUsagePanel: buildUsagePanel, buildEvents: buildEvents, buildPreview: buildPreview, init: init
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else if (root && root.document) init(root);
})(typeof window !== 'undefined' ? window : this);
