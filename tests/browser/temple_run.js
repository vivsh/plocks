async page => {
  const results = [];
  for (const mode of ['cdn', 'self']) {
    const context = await page.context().browser().newContext({
      deviceScaleFactor: 2, viewport: {width: 680, height: 620},
    });
    const external = [], errors = [], consoleLines = [];
    try {
      if (mode === 'self') await context.route('**/*', route => {
        if (new URL(route.request().url()).origin === 'http://127.0.0.1:8464') return route.continue();
        external.push(route.request().url()); return route.abort();
      });
      const tab = await context.newPage();
      tab.on('pageerror', error => errors.push(String(error)));
      tab.on('console', message => consoleLines.push(message.text()));
      await tab.goto(`http://127.0.0.1:8464/temple_run-${mode}/`);
      await tab.bringToFront();
      await tab.waitForFunction(() => !document.getElementById('play').disabled, null, {timeout: 60000});
      await tab.getByRole('button', {name: 'Play', exact: true}).click();
      await tab.waitForFunction(() => {
        if (!window.python) return false;
        window.python.PyRun_SimpleString("import asyncio,platform\nfor t in asyncio.all_tasks():\n f=getattr(t.get_coro(),'cr_frame',None)\n if f and f.f_code.co_name=='drive':\n  platform.window.document.getElementById('canvas').setAttribute('data-ready','yes')");
        return document.getElementById('canvas').getAttribute('data-ready') === 'yes';
      }, null, {timeout: 30000});
      const probe = async (command='pass') => {
        const stamp = String(Math.random());
        const source = `import asyncio,json,platform
for task in asyncio.all_tasks():
 f=getattr(task.get_coro(),'cr_frame',None)
 if f and f.f_code.co_name=='drive':
  s=f.f_locals['stage']
v=dict(s._updates[0][1].__globals__)
h=v['hero']
${command}
data={k:v[k] for k in ('score','outcome','distance')}
data.update({'stamp':${JSON.stringify(stamp)},'time':s.time,'x':h.x,'y':h.y,'height':h.costume.height,'running':s.running,'actions':len(s._actions),'course':[(loc,lane,kind) for _,loc,lane,kind in v['objects']]})
platform.window.document.getElementById('canvas').setAttribute('data-game',json.dumps(data))`;
        await tab.evaluate(code => window.python.PyRun_SimpleString(code), source);
        await tab.waitForFunction(stamp => {
          const raw = document.getElementById('canvas').getAttribute('data-game');
          return raw && JSON.parse(raw).stamp === stamp;
        }, stamp);
        const value = JSON.parse(await tab.locator('#canvas').getAttribute('data-game'));
        if (command !== 's.stop()' && !value.running) throw Error('Game stopped unexpectedly');
        if (await tab.locator('#error').isVisible()) throw Error(await tab.locator('#error-message').innerText());
        return value;
      };
      const sent = new Set(), captures = new Set();
      let value = await probe();
      const started = Date.now();
      while (value.outcome === 'playing') {
        if (Date.now() - started > 45000) throw Error('Course timed out');
        const event = value.course[0];
        if (event) {
          const [location, lane, kind] = event;
          const ahead = location - value.distance;
          let key;
          if (kind === 'coin' && value.x !== lane * 145) key = value.x < lane * 145 ? 'ArrowRight' : 'ArrowLeft';
          if (ahead <= 40 && kind === 'hurdle') key = 'Space';
          if (ahead <= 55 && kind === 'arch') key = 'ArrowDown';
          if (ahead <= 55 && (kind === 'left' || kind === 'right')) key = kind === 'left' ? 'ArrowLeft' : 'ArrowRight';
          if (key && !sent.has(location)) {
            await tab.keyboard.press(key);
            // A two-lane change needs two separate key transitions.
            if (kind === 'coin' && Math.abs(value.x - lane * 145) > 145) await tab.keyboard.press(key);
            sent.add(location);
          }
        }
        const label = value.distance > 211 && value.distance < 240 ? 'jump'
          : value.distance > 452 && value.distance < 480 ? 'slide'
          : value.distance > 601 && value.distance < 625 ? 'turn' : null;
        if (label && !captures.has(label)) {
          await tab.locator('#canvas').screenshot({path:`output/playwright/temple-${mode}-${label}.png`});
          captures.add(label);
        }
        await tab.waitForTimeout(35);
        value = await probe();
      }
      if (value.outcome !== 'Temple reached! Well run.' || value.score !== 8) throw Error(JSON.stringify(value));
      const completed = value;
      await tab.keyboard.press('r'); await tab.waitForTimeout(60);
      const restarted = await probe();
      if (restarted.outcome !== 'playing' || restarted.score !== 0 || restarted.distance > 40) throw Error('Restart failed');
      await tab.waitForTimeout(2400);
      const failed = await probe();
      if (!failed.outcome.startsWith('Jump over')) throw Error('Unattended obstacle did not stop runner');
      await probe('s.stop()');
      await tab.waitForFunction(() => {
        window.python.PyRun_SimpleString("platform.window.document.getElementById('canvas').setAttribute('data-clean',str(not s._actions and not s.objects and not s._voices and s._target is None))");
        return document.getElementById('canvas').getAttribute('data-clean') === 'True';
      });
      if (await tab.locator('#error').isVisible()) throw Error('Browser error after cleanup');
      if (external.length || errors.length) throw Error(JSON.stringify({external,errors}));
      results.push({mode,completed,restarted,failed,cleanup:true,external,errors,captures:[...captures]});
    } catch (error) {
      throw Error(`${mode}: ${error}\n${consoleLines.slice(-25).join('\n')}`);
    } finally { await context.close(); }
  }
  return results;
}
