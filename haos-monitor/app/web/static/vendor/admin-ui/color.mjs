// Colour maths for the optional HA theme sync: strict parsing, WCAG 2 luminance and contrast,
// and re-serialisation. Only colours that were parsed to numbers are ever written back out,
// which is what keeps a hostile CSS value from reaching the DOM.

// Relative luminance at which black and white text have equal contrast on the background.
const DARK_LUMINANCE = 0.179;
const MAX_INPUT = 64;

const HEX = /^#([0-9a-f]{3}|[0-9a-f]{6})$/;
const NUM = "(\\d{1,3})";
const ALPHA = "(\\d*\\.?\\d+)";
const RGB_COMMA = new RegExp(`^rgba?\\(\\s*${NUM}\\s*,\\s*${NUM}\\s*,\\s*${NUM}\\s*(?:,\\s*${ALPHA}\\s*)?\\)$`);
const RGB_SPACE = new RegExp(`^rgba?\\(\\s*${NUM}\\s+${NUM}\\s+${NUM}\\s*(?:/\\s*${ALPHA}\\s*)?\\)$`);

function channelsOf(m) {
  const [r, g, b] = [m[1], m[2], m[3]].map(Number);
  const a = m[4] === undefined ? 1 : Number(m[4]);
  if (r > 255 || g > 255 || b > 255 || !(a >= 0 && a <= 1)) return null;
  return { r, g, b, a };
}

export function parseColor(value) {
  if (typeof value !== "string" || value.length > MAX_INPUT) return null;
  const text = value.trim().toLowerCase();
  const hex = HEX.exec(text);
  if (hex) {
    const digits = hex[1].length === 3 ? [...hex[1]].map((c) => c + c).join("") : hex[1];
    return {
      r: parseInt(digits.slice(0, 2), 16),
      g: parseInt(digits.slice(2, 4), 16),
      b: parseInt(digits.slice(4, 6), 16),
      a: 1,
    };
  }
  const fn = RGB_COMMA.exec(text) || RGB_SPACE.exec(text);
  return fn ? channelsOf(fn) : null;
}

const byte = (n) => Number.isInteger(n) && n >= 0 && n <= 255;

export function serializeColor(color) {
  if (!color || !byte(color.r) || !byte(color.g) || !byte(color.b)) return null;
  const a = typeof color.a === "number" && color.a >= 0 && color.a <= 1 ? color.a : null;
  if (a === null) return null;
  const rounded = Number(a.toFixed(3));
  if (rounded === 1) {
    return "#" + [color.r, color.g, color.b].map((n) => n.toString(16).padStart(2, "0")).join("");
  }
  return `rgba(${color.r}, ${color.g}, ${color.b}, ${rounded})`;
}

function linear(channel) {
  const c = channel / 255;
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

export function relativeLuminance(color) {
  return 0.2126 * linear(color.r) + 0.7152 * linear(color.g) + 0.0722 * linear(color.b);
}

export function contrastRatio(a, b) {
  const la = relativeLuminance(a);
  const lb = relativeLuminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

export function isDarkColor(color) {
  return relativeLuminance(color) < DARK_LUMINANCE;
}

const ON_LIGHT = "#ffffff";
const ON_DARK = "#111111";

export function pickOnColor(background) {
  const white = parseColor(ON_LIGHT);
  const ink = parseColor(ON_DARK);
  return contrastRatio(white, background) >= contrastRatio(ink, background) ? ON_LIGHT : ON_DARK;
}
