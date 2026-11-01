// Tracer shell: health badge plus users table. Relative URLs only (the page lives below an ingress token path).

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = String(text);
  if (className) node.className = className;
  return node;
}

async function getJson(url) {
  const resp = await fetch(url, { headers: { Accept: "application/json" } });
  if (!resp.ok) throw new Error(`${url}: HTTP ${resp.status}`);
  return resp.json();
}

function renderUsers(root, users) {
  const card = el("section", null, "card");
  card.append(el("h2", "Users"));
  const table = el("table");
  const head = el("tr");
  for (const title of ["Name", "Role", "Tier"]) head.append(el("th", title));
  table.append(head);
  for (const user of users) {
    const row = el("tr");
    row.append(el("td", user.name), el("td", user.role), el("td", user.tier || "-"));
    table.append(row);
  }
  card.append(table);
  root.append(card);
}

async function main() {
  const root = document.getElementById("app");
  const badge = document.getElementById("badge");
  try {
    const health = await getJson("api/health");
    badge.textContent = health.status;
    badge.className = `badge ${health.status}`;
    const info = el("section", null, "card");
    info.append(el("h2", "Health"));
    info.append(el("div", `ntfy ${health.ntfy.healthy ? "healthy" : "not healthy"}, add-on ${health.addon_version}`));
    info.append(el("div", `auth.db schema ${health.db.schema_version} (${health.db.supported ? "supported" : "unsupported"})`));
    root.append(info);
  } catch (err) {
    badge.textContent = "error";
    badge.className = "badge error";
    root.append(el("p", `Health unavailable: ${err.message}`, "notice"));
  }
  try {
    const data = await getJson("api/users");
    renderUsers(root, data.users);
  } catch (err) {
    root.append(el("p", `Users unavailable: ${err.message}`, "notice"));
  }
}

main();
