async page => {
  const results = [];
  for (const mode of ['cdn', 'self']) {
    const context = await page.context().browser().newContext();
    try {
      const external = [];
      if (mode === 'self') await context.route('**/*', route => {
        if (new URL(route.request().url()).origin === 'http://127.0.0.1:8464') return route.continue();
        external.push(route.request().url());
        return route.abort();
      });
      for (const visit of ['cold', 'warm']) {
        const tab = await context.newPage();
        const started = Date.now();
        await tab.goto(`http://127.0.0.1:8464/world-${mode}/`);
        await tab.bringToFront();
        await tab.waitForFunction(() => !document.getElementById('play').disabled, null, {timeout:60000});
        const readyMs = Date.now() - started;
        await tab.getByRole('button', {name:'Play',exact:true}).click();
        await tab.waitForFunction(() => document.getElementById('canvas').width === 640);
        const runningMs = Date.now() - started;
        results.push({mode,visit,readyMs,runningMs});
        await tab.close();
      }
      if (external.length) throw Error(JSON.stringify(external));
    } finally {
      await context.close();
    }
  }
  return {results, note:'Self-contained routing disables HTTP cache; its warm visit measures repeated startup with the browser runtime/compiler still warm.'};
}
