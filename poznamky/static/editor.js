// Sdílené formátování pro contenteditable editory (rychlý blok, poznámky).
// initFormatting(pad, toolbar, onChange) – toolbar tlačítka s data-cmd
// spouštějí execCommand, tlačítko s data-link vkládá odkaz; Tab/Shift+Tab
// odsazuje, vložení čistého textu, samotná URL se stane odkazem,
// klik na odkaz ho otevře v novém okně.
function initFormatting(pad, toolbar, onChange) {
  // mousedown nesmí sebrat výběr/kurzor z editoru
  toolbar.addEventListener('mousedown', (e) => e.preventDefault());
  toolbar.querySelectorAll('button[data-cmd]').forEach((btn) => {
    btn.addEventListener('click', () => {
      pad.focus();
      document.execCommand(btn.dataset.cmd);
      onChange();
    });
  });
  const linkBtn = toolbar.querySelector('button[data-link]');
  if (linkBtn) linkBtn.addEventListener('click', () => {
    pad.focus();
    let url = prompt('Adresa odkazu:', 'https://');
    if (!url || url === 'https://') return;
    if (!/^https?:\/\//.test(url)) url = 'https://' + url;
    const sel = window.getSelection();
    if (sel && !sel.isCollapsed) {
      document.execCommand('createLink', false, url);
    } else {
      const a = document.createElement('a');
      a.href = url;
      a.textContent = url;
      document.execCommand('insertHTML', false, a.outerHTML);
    }
    onChange();
  });
  // Tab / Shift+Tab = odsazení
  pad.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') {
      e.preventDefault();
      document.execCommand(e.shiftKey ? 'outdent' : 'indent');
      onChange();
    }
  });
  // vkládání: čistý text; samotná URL se rovnou stane odkazem
  pad.addEventListener('paste', (e) => {
    e.preventDefault();
    const text = (e.clipboardData || window.clipboardData).getData('text/plain');
    const trimmed = text.trim();
    if (/^https?:\/\/\S+$/.test(trimmed)) {
      const a = document.createElement('a');
      a.href = trimmed;
      a.textContent = trimmed;
      document.execCommand('insertHTML', false, a.outerHTML);
    } else {
      document.execCommand('insertText', false, text);
    }
    onChange();
  });
  // klik na odkaz ho otevře v novém okně
  pad.addEventListener('click', (e) => {
    const a = e.target.closest('a');
    if (a && a.href) { e.preventDefault(); window.open(a.href, '_blank'); }
  });
}
