// Deutsche Texte der HAOS-Monitor-Seite. Flache Schlüssel mit Punkten; {name} markiert einen Parameter.
// Dieselben Schlüssel wie strings.en.mjs.
export default {
  "app.title": "HAOS Monitor",

  "hm.verdict.ok": "OK",
  "hm.verdict.problem": "PROBLEM",
  "hm.verdict.unknown": "Unbekannt",

  "hm.reasons.label": "Gründe",
  "hm.reason.stale": "Messwerte veraltet",
  "hm.reason.io_full10": "I/O-Stau",
  "hm.reason.sda_inflight": "Anfragen an sda stauen sich",
  "hm.reason.dstate": "Blockierte Tasks",
  "hm.reason.kmsg": "Kernel-Fehler",

  "hm.values.caption": "Messwerte von {host}",
  "hm.row.age": "Alter der Messung (s)",
  "hm.row.up": "Host gestartet",
  "hm.row.up.value": "{time} ({relative})",
  "hm.row.load1": "Last (1 Min.)",
  "hm.row.io_some10": "I/O some (10 s Mittel %)",
  "hm.row.io_full10": "I/O full (10 s Mittel %)",
  "hm.row.mem_full10": "Speicher full (10 s Mittel %)",
  "hm.row.sda_inflight": "Offene Anfragen sda",
  "hm.row.mmc_inflight": "Offene Anfragen mmc",
  "hm.row.dstate": "Tasks im D-State",
  "hm.row.kmsg_errors": "Kernel-Fehler (10 Min.)",
  "hm.value.unknown": "–",
  "hm.violated": "Schwellwert überschritten",

  "hm.ports.label": "Erreichbarkeit",
  "hm.port.ping": "Ping",
  "hm.port.ssh": "SSH 22222",
  "hm.port.mqtt": "MQTT 1883",
  "hm.port.ha": "HA 8123",
  "hm.port.observer": "Observer 4357",
  "hm.port.state.up": "erreichbar",
  "hm.port.state.down": "nicht erreichbar",
  "hm.port.state.unknown": "unbekannt",

  "hm.key.label": "SSH-Schlüssel",
  "hm.key.invalid": "ungültig",

  "hm.blocked.title": "Blockierte Tasks",
  "hm.kmsg.title": "Letzter Kernel-Fehler",
  "hm.incidents.title": "Letzte Vorfälle",
  "hm.incidents.none": "keine protokolliert",

  "hm.updated": "Aktualisiert {time}",
  "hm.problems.one": "{n} Problem",
  "hm.problems.other": "{n} Probleme",
  "hm.empty": "Keine Hosts konfiguriert.",

  "errors.hosts_unavailable": "Die Hostliste ist nicht verfügbar",
  "errors.status_failed": "Der Status dieses Hosts konnte nicht ermittelt werden",
};
