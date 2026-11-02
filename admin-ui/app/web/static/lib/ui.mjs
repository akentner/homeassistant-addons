// Shared Preact components and hooks (tracer subset; plan 26-08 completes it). Text nodes only: values are never
// inserted as markup.
import {
  html,
  render,
  useState,
  useEffect,
  useMemo,
  useRef,
  useCallback,
  useErrorBoundary,
} from "./vendor/preact-htm.mjs";

export { html, render, useState, useEffect, useMemo, useRef, useCallback, useErrorBoundary };

export function Badge({ kind = "muted", children }) {
  return html`<span class=${`badge ${kind}`}>${children}</span>`;
}
