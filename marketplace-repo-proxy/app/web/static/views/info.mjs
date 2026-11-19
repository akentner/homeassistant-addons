// Info view: static, translated setup notes (D-23, MRP-16): how to add a store URL in Home Assistant, what a reverse
// proxy in front of the add-on must do, and how to rotate a store URL. No API call, no state, no action; every text
// comes from t() and is rendered as a text node (R-03, R-06).
import { html } from "../vendor/admin-ui/ui.mjs";
import { useT } from "../vendor/admin-ui/i18n.mjs";

export default function Info() {
  const tt = useT();
  return html`<div class="info-view">
    <section class="card info-card">
      <h2>${tt("mrp.info.setup.title")}</h2>
      <ol>
        <li>${tt("mrp.info.setup.copy")}</li>
        <li>${tt("mrp.info.setup.add")}</li>
      </ol>
      <ul>
        <li>${tt("mrp.info.setup.host")}</li>
        <li>${tt("mrp.info.setup.internal")}</li>
        <li>${tt("mrp.info.setup.secret")}</li>
      </ul>
    </section>
    <section class="card info-card">
      <h2>${tt("mrp.info.proxy.title")}</h2>
      <p>${tt("mrp.info.proxy.intro")}</p>
      <ul>
        <li>${tt("mrp.info.proxy.tls")}</li>
        <li>${tt("mrp.info.proxy.cache")}</li>
        <li>${tt("mrp.info.proxy.log")}</li>
      </ul>
      <p>${tt("mrp.info.proxy.later")}</p>
    </section>
    <section class="card info-card">
      <h2>${tt("mrp.info.rotation.title")}</h2>
      <p>${tt("mrp.info.rotation.intro")}</p>
      <ol>
        <li>${tt("mrp.info.rotation.backup")}</li>
        <li>${tt("mrp.info.rotation.rotate")}</li>
        <li>${tt("mrp.info.rotation.replace")}</li>
        <li>${tt("mrp.info.rotation.restore")}</li>
      </ol>
    </section>
  </div>`;
}
