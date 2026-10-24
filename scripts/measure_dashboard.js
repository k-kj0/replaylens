// Paste this whole file into the browser console (F12 > Console) on the dashboard page,
// press Enter, THEN click "Load report JSON" and choose big_report.json.
// It prints how long the page kept changing after you chose the file, and the DOM node count.
(() => {
  const input = document.querySelector('input[type=file]');
  if (!input) { console.log('No file input found on this page.'); return; }

  input.addEventListener('change', () => {
    const start = performance.now();
    let last = start;
    const observer = new MutationObserver(() => { last = performance.now(); });
    observer.observe(document.body, { childList: true, subtree: true, attributes: true, characterData: true });

    const timer = setInterval(() => {
      // finished when the page has been quiet for 700 ms
      if (performance.now() - last > 700) {
        clearInterval(timer);
        observer.disconnect();
        console.log('---- ReplayLens measurement ----');
        console.log('Time until page stopped changing (ms):', Math.round(last - start));
        console.log('DOM nodes:', document.querySelectorAll('*').length);
        console.log('Table rows (tr):', document.querySelectorAll('tr').length);
      }
    }, 200);
  }, true);

  console.log('Ready. Now click "Load report JSON" and choose your file.');
})();
