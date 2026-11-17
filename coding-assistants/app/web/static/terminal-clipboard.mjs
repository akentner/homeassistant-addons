// Receive herdr's pane-only selections through xterm's public OSC 52 parser API and write them to the browser
// clipboard. Best effort: a browser that blocks clipboard writes inside ingress simply keeps its own selection.
export function installTerminalClipboard() {
  const frame = document.getElementById('frameTerminal');
  let generation = 0;
  let retry;
  let registration;
  let copyTask = Promise.resolve();

  function copy(text) {
    // Serialize writes so a slower, older selection cannot overwrite a newer one.
    copyTask = copyTask.then(async () => {
      try {
        await navigator.clipboard?.writeText(text);
      } catch {
        // No permission without a user gesture; nothing to fall back to.
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
    try {
      const bytes = Uint8Array.from(atob(encoded), character => character.charCodeAt(0));
      const text = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
      if (text) copy(text);
    } catch {
      // Malformed payload: ignore.
    }
    return true;
  }

  function reset() {
    const currentGeneration = ++generation;
    clearTimeout(retry);
    registration?.dispose();
    registration = undefined;
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

  frame.addEventListener('load', reset);
  if (frame.contentDocument?.readyState === 'complete') reset();
  return {
    dispose() {
      generation++;
      clearTimeout(retry);
      registration?.dispose();
      frame.removeEventListener('load', reset);
    },
  };
}
