// Token management: hidden by default, reveal per row on demand, create and revoke. Texts come from i18n.
import {
  html,
  useState,
  useAsync,
  toast,
  Modal,
  ConfirmDialog,
  Badge,
  CopyField,
  Field,
  Loading,
} from "../vendor/admin-ui/ui.mjs";
import { get, post, del } from "../vendor/admin-ui/api.mjs";
import { useT, tError } from "../vendor/admin-ui/i18n.mjs";
import { ErrorNote, FormNotice, ScrollTable, OriginBadge, ExpiryText, TimeStamp } from "../components.mjs";
import { validDuration, validLabel, expiryState } from "../lib/model.mjs";

export const meta = { id: "tokens", titleKey: "view.tokens" };

// Expiry presets: value sent to the API (custom reads the extra input) and the text key of the option.
const PRESET_KEYS = {
  never: "tokens.preset_never",
  "1h": "tokens.preset_1h",
  "1d": "tokens.preset_1d",
  "7d": "tokens.preset_7d",
  "30d": "tokens.preset_30d",
  "90d": "tokens.preset_90d",
  custom: "tokens.preset_custom",
};
const STATE_KEYS = { never: "tokens.state_never", expired: "tokens.state_expired", active: "tokens.state_active" };
const STATE_KINDS = { never: "muted", expired: "error", active: "ok" };

function CreateToken({ users, initial, onClose, onDone }) {
  const tt = useT();
  const [user, setUser] = useState(initial || "");
  const [label, setLabel] = useState("");
  const [preset, setPreset] = useState("never");
  const [custom, setCustom] = useState("");
  const [notice, setNotice] = useState("");
  const [apiError, setApiError] = useState(null);
  const [created, setCreated] = useState(null);
  const submit = async () => {
    const expires = preset === "custom" ? custom : preset === "never" ? "" : preset;
    setApiError(null);
    if (!user) return setNotice(tt("tokens.err_user"));
    if (!validLabel(label)) return setNotice(tt("tokens.err_label"));
    if (expires && !validDuration(expires)) return setNotice(tt("tokens.err_duration"));
    setNotice("");
    try {
      const body = { user, label };
      if (expires) body.expires = expires;
      const res = await post("tokens", { body });
      setCreated(res.token);
    } catch (err) {
      setApiError(err);
    }
  };
  if (created) {
    return html`<${Modal} title=${tt("tokens.created_title")} onClose=${onDone}>
      <p>${tt("tokens.created_text")}</p>
      <${CopyField} value=${created.value} label=${tt("tokens.created_label")} />
      <div class="actions"><button class="btn" type="button" onClick=${onDone}>${tt("tokens.done")}</button></div>
    <//>`;
  }
  return html`<${Modal} title=${tt("tokens.create_title")} onClose=${onClose}>
    <${Field} id="token-user" label=${tt("tokens.field_user")}>
      <select id="token-user" value=${user} onChange=${(ev) => setUser(ev.target.value)}>
        <option value="">${tt("tokens.choose")}</option>
        ${users.map((name) => html`<option key=${name} value=${name}>${name}</option>`)}
      </select>
    <//>
    <${Field} id="token-label" label=${tt("tokens.field_label")}>
      <input id="token-label" type="text" value=${label} onInput=${(ev) => setLabel(ev.target.value)} />
    <//>
    <${Field} id="token-expires" label=${tt("tokens.field_expires")}>
      <select id="token-expires" value=${preset} onChange=${(ev) => setPreset(ev.target.value)}>
        ${Object.keys(PRESET_KEYS).map(
          (value) => html`<option key=${value} value=${value}>${tt(PRESET_KEYS[value])}</option>`,
        )}
      </select>
    <//>
    ${preset === "custom" &&
    html`<${Field} id="token-custom" label=${tt("tokens.field_custom")}>
      <input
        id="token-custom"
        type="text"
        placeholder=${tt("tokens.custom_placeholder")}
        value=${custom}
        onInput=${(ev) => setCustom(ev.target.value)}
      />
    <//>`}
    <${FormNotice}>${notice}<//>
    <${ErrorNote} error=${apiError} />
    <div class="actions">
      <button class="btn secondary" type="button" onClick=${onClose}>${tt("btn.cancel")}</button>
      <button class="btn" type="button" onClick=${submit}>${tt("tokens.create_submit")}</button>
    </div>
  <//>`;
}

// The revealed value lives only in this row's state: never in the list data, never in a toast.
function Row({ t, onRevoke }) {
  const tt = useT();
  const [value, setValue] = useState(null);
  const reveal = async () => {
    try {
      const res = await post("tokens/reveal", { body: { user: t.user, id: t.id } });
      setValue(res.value);
    } catch (err) {
      toast("error", tError(err));
    }
  };
  const expiresTs = t.expires_at ? Math.floor(Date.parse(t.expires_at) / 1000) || 0 : 0;
  const state = expiryState(expiresTs);
  return html`<tr>
    <td>${t.user}</td>
    <td class="mono">${t.prefix}…</td>
    <td>${t.label || ""}</td>
    <td>
      <${ExpiryText} ts=${expiresTs} />
      <${Badge} kind=${STATE_KINDS[state]}>${tt(STATE_KEYS[state])}<//>
    </td>
    <td title=${tt("tokens.last_approx")}><${TimeStamp} ts=${t.last_access} relative=${true} /></td>
    <td><${OriginBadge} origin=${t.origin} /></td>
    <td class="actions">
      ${value === null
        ? html`<button
            class="btn small secondary"
            type="button"
            aria-label=${tt("tokens.reveal_aria", { prefix: t.prefix })}
            onClick=${reveal}
          >
            ${tt("tokens.reveal")}
          </button>`
        : html`<${CopyField} value=${value} label=${tt("tokens.value_label", { prefix: t.prefix })} />
            <button
              class="btn small secondary"
              type="button"
              aria-label=${tt("tokens.hide_aria", { prefix: t.prefix })}
              onClick=${() => setValue(null)}
            >
              ${tt("tokens.hide")}
            </button>`}
      <button
        class="btn small danger"
        type="button"
        aria-label=${tt("tokens.revoke_aria", { prefix: t.prefix, user: t.user })}
        onClick=${() => onRevoke(t)}
      >
        ${tt("tokens.revoke")}
      </button>
    </td>
  </tr>`;
}

export default function View({ params }) {
  const tt = useT();
  const [filter, setFilter] = useState((params && params.user) || "");
  const usersQ = useAsync(() => get("users"));
  const tokensQ = useAsync(() => get("tokens", { query: { user: filter || undefined } }), [filter]);
  const [modal, setModal] = useState(null);
  const [revoke, setRevoke] = useState(null);
  if (usersQ.loading && !usersQ.data) return html`<${Loading} />`;
  if (usersQ.error) return html`<${ErrorNote} error=${usersQ.error} onRetry=${usersQ.reload} />`;
  const names = (usersQ.data.users || []).filter((u) => u.name !== "everyone").map((u) => u.name);
  // A thrown error keeps the confirm dialog open and shows the localized code text.
  const doRevoke = async () => {
    await del("tokens", { query: { user: revoke.user, id: revoke.id } });
    toast("ok", tt("tokens.revoke_ok"));
    setRevoke(null);
    tokensQ.reload();
    usersQ.reload();
  };
  const tokens = (tokensQ.data && tokensQ.data.tokens) || [];
  return html`<div>
    <div class="toolbar">
      <label for="tokens-filter">${tt("tokens.filter")}</label>
      <select id="tokens-filter" value=${filter} onChange=${(ev) => setFilter(ev.target.value)}>
        <option value="">${tt("tokens.all_users")}</option>
        ${names.map((name) => html`<option key=${name} value=${name}>${name}</option>`)}
      </select>
      <span class="spacer"></span>
      <button class="btn" type="button" onClick=${() => setModal("create")}>${tt("tokens.create")}</button>
    </div>
    ${tokensQ.error && html`<${ErrorNote} error=${tokensQ.error} onRetry=${tokensQ.reload} />`}
    <div class="card">
      <${ScrollTable} caption=${tt("tokens.caption")}>
        <thead>
          <tr>
            <th scope="col">${tt("tokens.col_user")}</th>
            <th scope="col">${tt("tokens.col_token")}</th>
            <th scope="col">${tt("tokens.col_label")}</th>
            <th scope="col">${tt("tokens.col_expires")}</th>
            <th scope="col">${tt("tokens.col_last")}</th>
            <th scope="col">${tt("tokens.col_origin")}</th>
            <th scope="col"><span class="sr-only">${tt("tokens.col_actions")}</span></th>
          </tr>
        </thead>
        <tbody>
          ${tokens.map((t) => html`<${Row} key=${t.user + t.id} t=${t} onRevoke=${setRevoke} />`)}
        </tbody>
      <//>
      ${!tokensQ.loading && tokens.length === 0 && html`<div class="muted">${tt("tokens.empty")}</div>`}
    </div>
    ${modal === "create" &&
    html`<${CreateToken}
      users=${names}
      initial=${filter}
      onClose=${() => setModal(null)}
      onDone=${() => {
        setModal(null);
        tokensQ.reload();
        usersQ.reload();
      }}
    />`}
    ${revoke &&
    html`<${ConfirmDialog}
      title=${tt("tokens.revoke_title")}
      danger=${true}
      confirmLabel=${tt("tokens.revoke")}
      message=${tt("tokens.revoke_message", { prefix: revoke.prefix, user: revoke.user })}
      onCancel=${() => setRevoke(null)}
      onConfirm=${doRevoke}
    />`}
  </div>`;
}
