async page => {
  const context = await page.context().browser().newContext({ deviceScaleFactor: 2 });
  try {
    const tab = await context.newPage();
    const external = [];
    const errors = [];
    const transfers = [];
    const started = Date.now();
    if (@@BLOCK_EXTERNAL@@) {
      await context.route("**/*", route => {
        const url = new URL(route.request().url());
        if (url.origin === "http://127.0.0.1:8461") return route.continue();
        external.push(url.href);
        return route.abort();
      });
    }
    tab.on("pageerror", error => errors.push(String(error)));
    tab.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    tab.on("requestfinished", request => transfers.push(request.sizes().then(size => ({ url: request.url(), bytes: size.responseBodySize }))));
    await tab.goto("http://127.0.0.1:8461/");
    await tab.bringToFront();
    await tab.waitForFunction(() => !document.getElementById("play").disabled, { timeout: 45000 });
    const readyMs = Date.now() - started;
    await tab.getByRole("button", { name: "Play", exact: true }).click();
    await tab.waitForFunction(() => document.getElementById("canvas").width === 480 && document.getElementById("canvas").height === 360);
    const probe = async (command = "pass") => {
      const token = String(Math.random());
      const source = `import asyncio,json,platform
for _task in asyncio.all_tasks():
    _frame = getattr(_task.get_coro(), 'cr_frame', None)
    if _frame and _frame.f_code.co_name == 'drive':
        _stage = _frame.f_locals['stage']
        ${command}
        _result = {'stamp': ${JSON.stringify(token)}, 'time': _stage.time, 'x': _stage.objects[0].x, 'y': _stage.objects[0].y, 'sounds': _stage._updates[0].__globals__['sounds'], 'paused': _stage.paused, 'voices': len(_stage._voices)}
        platform.window.document.getElementById('canvas').setAttribute('data-proof', json.dumps(_result))
`;
      await tab.evaluate(code => window.python.PyRun_SimpleString(code), source);
      await tab.waitForFunction(stamp => {
        const text = document.getElementById("canvas").getAttribute("data-proof");
        return text && JSON.parse(text).stamp === stamp;
      }, token);
      return JSON.parse(await tab.locator("#canvas").getAttribute("data-proof"));
    };
    await tab.waitForTimeout(150);
    const initial = await probe();
    await tab.keyboard.down("ArrowRight");
    await tab.waitForTimeout(350);
    await tab.keyboard.up("ArrowRight");
    const moved = await probe();
    if (moved.x <= initial.x + 10 || moved.time <= initial.time) throw Error(JSON.stringify({ initial, moved }));
    const paused = await probe("_stage.pause()");
    await tab.waitForTimeout(120);
    const held = await probe();
    if (held.time !== paused.time || !held.paused) throw Error("Pause failed");
    await probe("_stage.resume()");
    await tab.keyboard.press("Space");
    await tab.waitForTimeout(80);
    const sound = await probe();
    if (sound.sounds !== 1 || sound.voices < 1) throw Error("Sound did not start: " + JSON.stringify(sound));
    const box = await tab.locator("#canvas").boundingBox();
    await tab.mouse.click(box.x + box.width * .75, box.y + box.height * .25);
    await tab.waitForTimeout(80);
    const clicked = await probe();
    if (Math.abs(clicked.x - 120) > 2 || Math.abs(clicked.y - 90) > 2 || clicked.sounds !== 2) throw Error("Scaled pointer mismatch: " + JSON.stringify(clicked));
    if (external.length || errors.length) throw Error(JSON.stringify({ external, errors }));
    await tab.screenshot({ path: "output/playwright/proof-browser.png" });
    const resources = await Promise.all(transfers);
    const transfer = resources.filter(resource => resource.url.startsWith('http')).reduce((sum, resource) => sum + Math.max(0, resource.bytes), 0);
    const result = { readyMs, transfer, resources, initial, moved, paused, sound, clicked, external, errors };
    return result;
  } finally {
    await context.close();
  }
}
