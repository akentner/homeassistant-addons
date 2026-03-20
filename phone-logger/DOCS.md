# Phone Logger Add-on – Konfigurationsreferenz

## Übersicht
Dieses Add-on ermöglicht die flexible Konfiguration von Telefon-Logging und Adapter-Integration für Home Assistant.

## Konfigurationsoptionen

### input_adapters (Liste)
- type (str, Pflichtfeld)
- name (str, Pflichtfeld)
- enabled (bool, Pflichtfeld)
- config (Objekt, optional, je nach Typ)

### resolver_adapters (Liste)
- type: "json_file" | "sqlite" | "tellows"
  - json_file: config.path (str, Pflichtfeld)
  - sqlite: keine Konfiguration, immer aktiv
  - tellows: enabled (bool), config.ttl_days (int)

### output_adapters (Liste)
- type: "call_log" (immer aktiv, nicht konfigurierbar)
- type: "webhook"
  - url (str, Pflichtfeld)

### pbx
- lines (Liste von Objekten mit id)
- trunks (Liste von Objekten mit id, type, label)
- msns (Liste von Objekten mit number, label)
- devices (Liste von Objekten mit id, extension, name, type)

### phone
- country_code (str, Pflichtfeld)
- local_area_code (str, Pflichtfeld)

### Weitere Felder
- data_path (str, Standard: "/data")
- ingress_port (int, Standard: 8080)
- log_level (str, Standard: "INFO", erlaubt: "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
- timezone (str, Standard: "Europe/Berlin")

## Beispielkonfiguration
```yaml
input_adapters:
  - type: fritz
    name: fritz
    enabled: true
    config:
      host: "192.168.178.1"
      port: 1012
      reconnect_delay: 10
resolver_adapters:
  - type: json_file
    config:
      path: "contacts.json"
  - type: sqlite
  - type: tellows
    enabled: true
    config:
      ttl_days: 7
output_adapters:
  - type: call_log
  - type: webhook
    url: "https://webhook.site/xyz"
pbx:
  lines:
    - id: 0
    - id: 1
  trunks:
    - id: "SIP0"
      type: "sip"
      label: "Telekom 1"
  msns:
    - number: "990133"
      label: "Am Berghof 24"
  devices:
    - id: "600"
      extension: "**600"
      name: "AB 22"
      type: "voicebox"
phone:
  country_code: "49"
  local_area_code: "6181"
data_path: "/data"
ingress_port: 8080
log_level: "INFO"
timezone: "Europe/Berlin"
```

