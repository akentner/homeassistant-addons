// Deutsche Texte der Marketplace-Repo-Proxy-Seite. Flache Schlüssel mit Punkten; {name} markiert einen Parameter.
// Dieselben Schlüssel wie strings.en.mjs.
export default {
  "app.title": "Marketplace Repo Proxy",

  "view.repositories": "Repositories",

  "mrp.repo.title": "Veröffentlichte Repositories",
  "mrp.repo.caption": "Konfigurierte Repositories und ihr Sync-Zustand",
  "mrp.repo.col.repository": "Repository",
  "mrp.repo.col.status": "Status",
  "mrp.repo.col.last_sync": "Letzter Sync",
  "mrp.repo.col.head": "HEAD",
  "mrp.repo.col.addons": "Add-ons",
  "mrp.repo.branch.configured": "Branch {branch} (konfiguriert)",
  "mrp.repo.branch.upstream_default": "Branch {branch} (Upstream-Standard)",
  "mrp.repo.branch_unknown": "Upstream-Standard-Branch",
  "mrp.repo.never": "nie",
  "mrp.repo.addons.one": "{n} Add-on",
  "mrp.repo.addons.other": "{n} Add-ons",
  "mrp.repo.empty": "Keine Repositories konfiguriert. Trage sie in der Add-on-Konfiguration ein.",
  "mrp.repo.no_status": "Noch kein Status: Der erste Sync ist nicht abgeschlossen.",

  "mrp.sync.now": "Jetzt synchronisieren",
  "mrp.sync.idle": "Sync wartet",
  "mrp.sync.running": "Sync läuft",
  "mrp.sync.requested": "Sync angefordert",
  "mrp.sync.next_due": "nächster Sync {time}",
  "mrp.sync.interval": "alle {minutes} min",

  "mrp.reg.col": "Registrierung",
  "mrp.reg.registered": "Registriert",
  "mrp.reg.missing": "Nicht registriert",
  "mrp.reg.leftover": "Verwaist",
  "mrp.reg.error": "Fehler",
  "mrp.reg.leftover_note":
    "Verwaist: Der lokale Add-on-Store führt noch eine frühere Store-URL dieses Repositories. Entferne diesen Eintrag aus der Repository-Liste des Add-on-Stores, sobald kein installiertes Add-on ihn mehr nutzt.",

  "mrp.status.pending": "Ausstehend",
  "mrp.status.ok": "OK",
  "mrp.status.auth_failed": "Anmeldung fehlgeschlagen",
  "mrp.status.not_found": "Upstream nicht gefunden",
  "mrp.status.no_repository_yaml": "Keine repository.yaml",
  "mrp.status.fetch_failed": "Abruf fehlgeschlagen",
  "mrp.status.none": "Kein Status",
};
