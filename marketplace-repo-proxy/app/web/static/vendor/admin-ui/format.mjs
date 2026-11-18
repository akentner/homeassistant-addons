// Locale-aware formatting through Intl (languages "de" and "en"; anything else falls back to "en").
// Time inputs are epoch milliseconds. The browser's time zone is used unless opts.timeZone is given; it can differ
// from the zone of the Home Assistant server.
// Intl.* instances are created lazily and cached per (kind, lang, options).
const cache = new Map();
const CTORS = {
  DateTimeFormat: Intl.DateTimeFormat,
  RelativeTimeFormat: Intl.RelativeTimeFormat,
  NumberFormat: Intl.NumberFormat,
};

const norm = (lang) => (lang === "de" ? "de" : "en");

function cached(kind, lang, opts) {
  const key = `${kind}|${lang}|${JSON.stringify(opts)}`;
  let fmt = cache.get(key);
  if (!fmt) {
    fmt = new CTORS[kind](lang, opts);
    cache.set(key, fmt);
  }
  return fmt;
}

const validTime = (ms) => typeof ms === "number" && Number.isFinite(ms);

export function formatDateTime(ms, lang, opts = {}) {
  if (!validTime(ms)) return "-";
  return cached("DateTimeFormat", norm(lang), { dateStyle: "medium", timeStyle: "short", ...opts }).format(ms);
}

export function formatRelative(ms, lang, nowMs = Date.now()) {
  if (!validTime(ms)) return "-";
  const fmt = cached("RelativeTimeFormat", norm(lang), { numeric: "auto" });
  const diff = Math.round((ms - nowMs) / 1000);
  const abs = Math.abs(diff);
  if (abs < 45) return fmt.format(0, "second");
  if (abs < 3_600) return fmt.format(Math.round(diff / 60), "minute");
  if (abs < 86_400) return fmt.format(Math.round(diff / 3_600), "hour");
  return fmt.format(Math.round(diff / 86_400), "day");
}

const BYTE_UNITS = ["B", "KiB", "MiB", "GiB", "TiB"];

export function formatBytes(n, lang) {
  if (typeof n !== "number" || !Number.isFinite(n) || n < 0) return "-";
  let v = n;
  let i = 0;
  while (v >= 1024 && i < BYTE_UNITS.length - 1) {
    v /= 1024;
    i += 1;
  }
  const num = cached("NumberFormat", norm(lang), { maximumFractionDigits: i === 0 ? 0 : 1 }).format(v);
  return `${num} ${BYTE_UNITS[i]}`;
}

export function formatNumber(n, lang) {
  if (typeof n !== "number" || !Number.isFinite(n)) return "-";
  return cached("NumberFormat", norm(lang), {}).format(n);
}
