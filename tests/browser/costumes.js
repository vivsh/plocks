async page => {
  const results = [];
  for (const mode of ["cdn", "self"]) {
    const context = await page.context().browser().newContext({ deviceScaleFactor: 2 });
    try {
      const external = [];
      const errors = [];
      if (mode === "self") {
        await context.route("**/*", route => {
          if (new URL(route.request().url()).origin === "http://127.0.0.1:8465") {
            return route.continue();
          }
          external.push(route.request().url());
          return route.abort();
        });
      }
      const tab = await context.newPage();
      tab.on("pageerror", error => errors.push(String(error)));
      tab.on("console", message => {
        if (message.type() === "error") errors.push(message.text());
      });
      await tab.goto(`http://127.0.0.1:8465/${mode}/`);
      await tab.bringToFront();
      await tab.waitForFunction(() => !document.getElementById("play").disabled, null, { timeout: 60000 });
      await tab.getByRole("button", { name: "Play", exact: true }).click();
      try {
        await tab.waitForFunction(() => document.getElementById("canvas").width === 480, null, { timeout: 30000 });
      } catch (error) {
        throw Error(JSON.stringify({ mode, external, errors, page: await tab.locator("body").innerText(), cause: String(error) }));
      }
      await tab.waitForFunction(() => {
        if (!window.python) return false;
        window.python.PyRun_SimpleString(`
import asyncio, json, platform
for task in asyncio.all_tasks():
    frame = getattr(task.get_coro(), 'cr_frame', None)
    if frame and frame.f_code.co_name == 'drive':
        stage = frame.f_locals['stage']
        proof = {'verified': stage._draws[0].__globals__['verified'], 'actors': len(stage.objects)}
        platform.window.document.getElementById('canvas').setAttribute('data-costumes', json.dumps(proof))
`);
        return document.getElementById("canvas").hasAttribute("data-costumes");
      }, null, { timeout: 30000 });
      const proof = JSON.parse(await tab.locator("#canvas").getAttribute("data-costumes"));
      if (!proof.verified || proof.actors !== 7 || external.length || errors.length) {
        throw Error(JSON.stringify({ mode, proof, external, errors }));
      }
      await tab.screenshot({ path: `output/playwright/costumes-${mode}.png` });
      results.push({ mode, proof, external, errors });
    } finally {
      await context.close();
    }
  }
  return results;
}
