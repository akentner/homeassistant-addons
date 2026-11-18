// English texts of the Marketplace Repo Proxy page. Flat dotted keys; {name} marks a parameter.
// Same keys as strings.de.mjs.
export default {
  "app.title": "Marketplace Repo Proxy",

  "view.repositories": "Repositories",

  "mrp.repo.title": "Published repositories",
  "mrp.repo.caption": "Configured repositories and their sync state",
  "mrp.repo.col.repository": "Repository",
  "mrp.repo.col.status": "Status",
  "mrp.repo.col.last_sync": "Last sync",
  "mrp.repo.col.head": "HEAD",
  "mrp.repo.col.addons": "Add-ons",
  "mrp.repo.branch.configured": "Branch {branch} (configured)",
  "mrp.repo.branch.upstream_default": "Branch {branch} (upstream default)",
  "mrp.repo.branch_unknown": "Upstream default branch",
  "mrp.repo.never": "never",
  "mrp.repo.addons.one": "{n} add-on",
  "mrp.repo.addons.other": "{n} add-ons",
  "mrp.repo.empty": "No repositories are configured. Add them in the add-on configuration.",
  "mrp.repo.no_status": "No status yet: the first sync has not finished.",

  "mrp.sync.now": "Sync now",
  "mrp.sync.idle": "Sync idle",
  "mrp.sync.running": "Sync running",
  "mrp.sync.requested": "Sync requested",
  "mrp.sync.next_due": "next sync {time}",
  "mrp.sync.interval": "every {minutes} min",

  "mrp.reg.col": "Registration",
  "mrp.reg.registered": "Registered",
  "mrp.reg.missing": "Not registered",
  "mrp.reg.leftover": "Leftover",
  "mrp.reg.error": "Error",
  "mrp.reg.leftover_note":
    "Leftover: the local add-on store still lists an earlier store URL of this repository. Remove that entry from the add-on store's repository list once no installed add-on uses it.",

  "mrp.status.pending": "Pending",
  "mrp.status.ok": "OK",
  "mrp.status.auth_failed": "Authentication failed",
  "mrp.status.not_found": "Not found upstream",
  "mrp.status.no_repository_yaml": "No repository.yaml",
  "mrp.status.fetch_failed": "Fetch failed",
  "mrp.status.none": "No status",
};
