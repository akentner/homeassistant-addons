// Receive herdr's pane-only selections through xterm's public OSC 52 parser API.
// Browsers can require another user gesture for clipboard writes inside ingress.
export function installTerminalClipboard(translate) {
  const frame = document.getElementById('frameTerminal');
  const button = document.getElementById('copySelection');
  const status = document.getElementById('clipboardStatus');
  const dialog = document.getElementById('clipboardDialog');
  const textArea = document.getElementById('clipboardText');
  let selection = '';
  let revision = 0;
  let generation = 0;
  let retry;
  let registration;
  let copyTask = Promise.resolve();
  let statusKey = '';

  function setStatus(key) {
    statusKey = key;
    status.textContent = key ? translate(key) : '';
  }

  function legacyCopy(text) {
    // This fallback needs the explicit Copy button click, not terminal output.
    const activeElement = document.activeElement;
    const helper = document.createElement('textarea');
    helper.value = text;
    helper.readOnly = true;
    helper.className = 'clipboard-helper';
    document.body.appendChild(helper);
    helper.select();
    try {
      return document.execCommand('copy');
    } finally {
      helper.remove();
      activeElement?.focus();
    }
  }

  function copy(manual) {
    const text = selection;
    const currentRevision = revision;
    if (!text) return;
    // Serialize writes so a slower, older selection cannot overwrite a newer one.
    copyTask = copyTask.then(async () => {
      if (currentRevision !== revision) return;
      let copied = false;
      try {
        if (navigator.clipboard?.writeText) {
          await navigator.clipboard.writeText(text);
          copied = true;
        }
      } catch {
        // An explicit button click can supply the missing browser permission.
      }
      if (currentRevision !== revision) return;
      if (!copied && manual) {
        try { copied = legacyCopy(text); } catch { /* Use selectable text below. */ }
      }
      setStatus(copied ? 'ca.clipboard.copied' : 'ca.clipboard.ready');
      if (!copied && manual) {
        textArea.value = text;
        if (!dialog.open) dialog.showModal();
        textArea.focus();
        textArea.select();
      }
    });
  }

  function receive(data) {
    const separator = data.indexOf(';');
    const target = data.slice(0, separator);
    const encoded = data.slice(separator + 1);
    // Never answer clipboard-read queries. Only accept bounded clipboard writes.
    if (separator < 0 || (target !== '' && target !== 'c') || !encoded || encoded === '?' ||
        encoded.length > 1024 * 1024 || frame.classList.contains('hidden')) return true;
    let text;
    try {
      const bytes = Uint8Array.from(atob(encoded), character => character.charCodeAt(0));
      text = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
    } catch {
      return true;
    }
    if (!text) return true;
    selection = text;
    revision++;
    button.disabled = false;
    setStatus('ca.clipboard.ready');
    // An already-open manual view must not keep showing an older selection.
    if (dialog.open) textArea.value = text;
    copy(false);
    return true;
  }

  function reset() {
    const currentGeneration = ++generation;
    clearTimeout(retry);
    registration?.dispose();
    registration = undefined;
    selection = '';
    revision++;
    button.disabled = true;
    setStatus('');
    textArea.value = '';
    if (dialog.open) dialog.close();
    function attach() {
      if (currentGeneration !== generation) return;
      const terminal = frame.contentWindow?.term;
      if (!terminal) {
        retry = setTimeout(attach, 100);
        return;
      }
      registration = terminal.parser.registerOscHandler(52, receive);
    }
    attach();
  }

  const onCopy = () => copy(true);
  const onClose = () => dialog.close();
  const closeButton = document.getElementById('closeClipboard');
  button.addEventListener('click', onCopy);
  closeButton.addEventListener('click', onClose);
  frame.addEventListener('load', reset);
  if (frame.contentDocument?.readyState === 'complete') reset();
  return {
    refreshLabels() { setStatus(statusKey); },
    dispose() {
      generation++;
      revision++;
      clearTimeout(retry);
      registration?.dispose();
      button.removeEventListener('click', onCopy);
      closeButton.removeEventListener('click', onClose);
      frame.removeEventListener('load', reset);
    },
  };
}
