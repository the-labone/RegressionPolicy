(() => {
  const button = document.querySelector('.citation-copy');
  const citation = document.querySelector('#bibtex-citation');
  const status = document.querySelector('.citation-status');
  if (!button || !citation || !status) return;
  const label = button.querySelector('span');
  let resetTimer;
  button.hidden = false;

  button.addEventListener('click', async () => {
    clearTimeout(resetTimer);
    button.disabled = true;
    status.textContent = '';
    try {
      await navigator.clipboard.writeText(citation.textContent);
      label.textContent = 'Copied!';
      status.textContent = 'BibTeX copied to clipboard.';
    } catch {
      citation.closest('pre').focus({ preventScroll: true });
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(citation);
      selection.removeAllRanges();
      selection.addRange(range);
      label.textContent = 'Copy BibTeX';
      status.textContent = 'Citation selected. Press ⌘C or Ctrl+C to copy.';
    } finally {
      button.disabled = false;
      resetTimer = setTimeout(() => {
        label.textContent = 'Copy BibTeX';
        status.textContent = '';
      }, 3000);
    }
  });
})();
