// ttyd exposes its xterm instance as window.term. Send the same LF as Ctrl+J:
// legacy terminal keyboard encoding otherwise turns Shift+Enter into plain Enter.
export function installTerminalInput(frame) {
  const attached = new WeakSet();

  function attach() {
    const terminalDocument = frame.contentDocument;
    if (!terminalDocument || attached.has(terminalDocument)) return;
    attached.add(terminalDocument);
    terminalDocument.addEventListener('keydown', event => {
      if (event.key !== 'Enter' || !event.shiftKey || event.ctrlKey || event.altKey || event.metaKey ||
          event.isComposing || !event.target?.classList?.contains('xterm-helper-textarea')) return;
      const terminal = frame.contentWindow?.term;
      if (typeof terminal?.input !== 'function') return;
      event.preventDefault();
      event.stopImmediatePropagation();
      terminal.input('\n', true);
    }, true);
  }

  frame.addEventListener('load', attach);
  if (frame.contentDocument?.readyState === 'complete') attach();
  return () => frame.removeEventListener('load', attach);
}
