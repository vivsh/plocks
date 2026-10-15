async page => {
  const results = [];
  for (const mode of ['cdn', 'self']) {
    const context = await page.context().browser().newContext();
    const external = [], errors = [], messages = [];
    try {
      if (mode === 'self') await context.route('**/*', route => {
        if (new URL(route.request().url()).origin === 'http://127.0.0.1:8464') return route.continue();
        external.push(route.request().url()); return route.abort();
      });
      const tab = await context.newPage();
      tab.on('pageerror', error => errors.push(String(error)));
      tab.on('console', message => messages.push(message.text()));
      await tab.goto(`http://127.0.0.1:8464/${mode}/`);
      await tab.bringToFront();
      await tab.waitForFunction(() => !document.getElementById('play').disabled, null, {timeout:60000});
      await tab.getByRole('button', {name:'Play', exact:true}).click();
      await tab.waitForFunction(() => {
        window.python.PyRun_SimpleString("import asyncio,platform\nfor t in asyncio.all_tasks():\n f=getattr(t.get_coro(),'cr_frame',None)\n if f and f.f_code.co_name=='drive':\n  platform.window.document.getElementById('canvas').setAttribute('data-ready','yes')");
        return document.getElementById('canvas').getAttribute('data-ready') === 'yes';
      });
      const probe = async (command='pass') => {
        const stamp = String(Math.random());
        const source = `import asyncio,inspect,json,platform
for task in asyncio.all_tasks():
 f=getattr(task.get_coro(),'cr_frame',None)
 if f and f.f_code.co_name=='drive':
  s=f.f_locals['stage']
v=dict(inspect.getclosurevars(s._updates[0][1]).nonlocals)
v.update(inspect.getclosurevars(s._draws[0]).nonlocals)
h=v['hero']
${command}
platform.window.document.getElementById('canvas').setAttribute('data-game',json.dumps({'stamp':${JSON.stringify(stamp)},'time':s.time,'x':h.x,'y':h.y,'health':v['health'],'defeated':v['defeated'],'enemies':len(v['enemies']),'shots':len(v['shots']),'friendly':sum(item[2] for item in v['shots']),'camera':s.camera[0]}))`;
        await tab.evaluate(code => window.python.PyRun_SimpleString(code), source);
        await tab.waitForFunction(stamp => {
          const data = document.getElementById('canvas').getAttribute('data-game');
          return data && JSON.parse(data).stamp === stamp;
        }, stamp);
        return JSON.parse(await tab.locator('#canvas').getAttribute('data-game'));
      };
      const initial = await probe();
      await tab.keyboard.down('ArrowRight');
      await tab.keyboard.down('x');
      await tab.keyboard.press('Space');
      await tab.waitForTimeout(230);
      const airborne = await probe();
      if (!(airborne.x>initial.x && airborne.y>initial.y && airborne.friendly>0)) throw Error('Run/jump/fire '+JSON.stringify(airborne));
      await tab.locator('#canvas').screenshot({path:`output/playwright/jungle-run-airborne-${mode}.png`});
      await tab.keyboard.up('ArrowRight'); await tab.keyboard.up('x');
      await tab.waitForTimeout(800);
      const landed = await probe();
      if (landed.y !== -150) throw Error('Landing '+JSON.stringify(landed));
      await tab.keyboard.press('r');
      await tab.waitForTimeout(80);
      await probe('h.x=150');
      await tab.keyboard.press('Space');
      await tab.waitForTimeout(1050);
      const platform = await probe();
      if (platform.y !== -86) throw Error('Platform '+JSON.stringify(platform));
      await tab.keyboard.press('r'); await tab.waitForTimeout(60);
      await probe('h.x=-100');
      await tab.keyboard.down('x'); await tab.waitForTimeout(1000); await tab.keyboard.up('x');
      const combat = await probe();
      if (!(combat.defeated>=1 && combat.enemies<6)) throw Error('Shooting '+JSON.stringify(combat));
      await tab.keyboard.press('r'); await tab.waitForTimeout(80);
      const restarted = await probe();
      if (restarted.enemies!==6 || restarted.health!==3 || restarted.defeated!==0 || restarted.x!==-300) throw Error('Restart '+JSON.stringify(restarted));
      await probe('h.x=650'); await tab.waitForTimeout(120);
      const scrolled = await probe();
      if (scrolled.camera<500) throw Error('Camera did not scroll');
      await tab.locator('#canvas').screenshot({path:`output/playwright/jungle-run-level-${mode}.png`});
      await tab.keyboard.press('p');
      await tab.waitForFunction(() => {
        window.python.PyRun_SimpleString("platform.window.document.getElementById('canvas').setAttribute('data-paused',str(s.paused))");
        return document.getElementById('canvas').getAttribute('data-paused') === 'True';
      });
      const paused = await probe();
      await tab.waitForTimeout(150); const held = await probe();
      if (held.time!==paused.time) throw Error('Pause advanced simulation');
      await tab.keyboard.press('p');
      await probe('s.stop()');
      await tab.waitForFunction(() => {
        window.python.PyRun_SimpleString("platform.window.document.getElementById('canvas').setAttribute('data-clean',str(not s._runs and not s.objects and s._target is None))");
        return document.getElementById('canvas').getAttribute('data-clean') === 'True';
      });
      if (external.length || errors.length) throw Error(JSON.stringify({external,errors}));
      results.push({mode,initial,airborne,landed,platform,combat,restarted,scrolled,cleanup:true,external,errors});
    } catch(error) {
      throw Error(String(error)+'\n'+messages.slice(-25).join('\n'));
    } finally { await context.close(); }
  }
  return results;
}
