// Temporary shim (removed by plan 27-05): everything comes from the synced admin-ui lib copy, except the ntfy
// components that now live in ../components.mjs and that the old views still import from here.
export * from "../vendor/admin-ui/ui.mjs";
export { OriginBadge, PermSelect, ErrorNote } from "../components.mjs";
