async page => {
  const results = [];
  const names = ['mario', 'platformer', 'fruit_ninja', 'geometry_dash', 'snake_run', 'scrolling_world'];
  for (const name of names) for (const mode of ['cdn', 'self']) {
    const context = await page.context().browser().newContext({deviceScaleFactor: 2});
    const external = [], errors = [], consoleLines = [];
    try {
      if (mode === 'self') await context.route('**/*', route => {
        if (new URL(route.request().url()).origin === 'http://127.0.0.1:8464') return route.continue();
        external.push(route.request().url()); return route.abort();
      });
      const tab = await context.newPage();
      tab.on('pageerror', error => errors.push(String(error)));
      tab.on('console', message => consoleLines.push(message.text()));
      await tab.goto(`http://127.0.0.1:8464/${name}-${mode}/`);
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
from plocks import Sprite, TileMap
for task in asyncio.all_tasks():
 f=getattr(task.get_coro(),'cr_frame',None)
 if f and f.f_code.co_name=='drive':
  s=f.f_locals['stage']
v=dict(s._updates[0][1].__globals__)
h=v.get('hero',v.get('head'))
${command}
data={k:v[k] for k in ('score','outcome','saved','falls','distance','over','selected') if k in v}
data.update({'stamp':${JSON.stringify(stamp)},'time':s.time,'x':h.x if h else None,'y':h.y if h else None,'running':s.running,'objects':len(s.objects),'camera':s.camera[0],'actions':len(s._actions)})
platform.window.document.getElementById('canvas').setAttribute('data-game',json.dumps(data))`;
        await tab.evaluate(code => window.python.PyRun_SimpleString(code), source);
        await tab.waitForFunction(stamp => {
          const raw = document.getElementById('canvas').getAttribute('data-game');
          return raw && JSON.parse(raw).stamp === stamp;
        }, stamp);
        const result = JSON.parse(await tab.locator('#canvas').getAttribute('data-game'));
        if (command !== 's.stop()' && !result.running) throw Error('Game stopped unexpectedly');
        return result;
      };
      const first = await probe();
      let played;
      if (name === 'mario' || name === 'platformer') {
        await tab.waitForTimeout(350);
        await tab.keyboard.down('ArrowRight');
        await tab.keyboard.press('Space');
        await tab.waitForTimeout(180);
        await tab.keyboard.up('ArrowRight');
        played = await probe();
        if (!(played.x > first.x && played.y > first.y + 10)) throw Error('Jump/move failed');
        if (name === 'platformer') {
          await probe('h.position=(180,62)\nh.body.velocity=(0,0)');
          await tab.waitForTimeout(80);
          if (!(await probe()).saved) throw Error('Checkpoint failed');
        }
      } else if (name === 'fruit_ninja') {
        // Put a real loaded fruit on a known swipe path; exercise actual browser mouse input.
        await probe("costumes=v['costumes']\nfruit=Sprite(costumes['apple'])\ns.add(fruit)\nv['flying'].append((fruit,0,120,0,'apple'))");
        const box = await tab.locator('#canvas').boundingBox();
        await tab.mouse.move(box.x + box.width * .35, box.y + box.height * .5);
        await tab.mouse.down();
        await tab.waitForTimeout(40);
        await tab.mouse.move(box.x + box.width * .65, box.y + box.height * .5, {steps: 3});
        await tab.mouse.up();
        await tab.waitForTimeout(80);
        played = await probe();
        if (played.score < 1) throw Error('Swipe did not slice');
      } else if (name === 'geometry_dash') {
        await tab.keyboard.press('Space');
        await tab.waitForTimeout(180);
        played = await probe();
        if (!(played.x > first.x && played.y > first.y + 10)) throw Error('Auto-run/jump failed');
      } else if (name === 'snake_run') {
        await tab.waitForTimeout(1600);
        played = await probe();
        if (!(played.distance > 160 && played.score >= 1)) throw Error('Snake did not collect');
        await tab.keyboard.down('ArrowRight'); await tab.waitForTimeout(150); await tab.keyboard.up('ArrowRight');
        if (!((await probe()).x > 0)) throw Error('Snake steering failed');
      } else {
        await probe('h.x=450'); await tab.waitForTimeout(60);
        await tab.keyboard.press('3');
        const box = await tab.locator('#canvas').boundingBox();
        await tab.mouse.click(box.x + box.width/2, box.y + box.height/2);
        await tab.waitForTimeout(80);
        played = await probe("world=next(obj for obj in s.objects if isinstance(obj,TileMap))\nassert world.get_tile(row=7,column=26)=='S'");
        if (!(played.camera > 400 && played.selected === 'S')) throw Error('Camera/paint failed');
      }
      await tab.locator('#canvas').screenshot({path:`output/playwright/learning-${name}-${mode}.png`});
      if (name !== 'scrolling_world') {
        await tab.keyboard.press('r'); await tab.waitForTimeout(80);
        const reset = await probe();
        if (reset.over || (reset.outcome && reset.outcome !== 'playing') || reset.saved) throw Error('Restart failed');
      }
      await probe('s.stop()');
      await tab.waitForFunction(() => {
        window.python.PyRun_SimpleString("platform.window.document.getElementById('canvas').setAttribute('data-clean',str(not s._actions and not s.objects and not s._voices and s._target is None))");
        return document.getElementById('canvas').getAttribute('data-clean') === 'True';
      });
      if (await tab.locator('#error').isVisible()) throw Error(await tab.locator('#error-message').innerText());
      if (external.length || errors.length) throw Error(JSON.stringify({external, errors}));
      results.push({name,mode,first,played,cleanup:true,external,errors});
    } catch (error) {
      throw Error(`${name}/${mode}: ${error}\n${consoleLines.slice(-25).join('\n')}`);
    } finally { await context.close(); }
  }
  return results;
}
