async page => {
  const results = [];
  for (const mode of ['cdn', 'self']) {
    const context = await page.context().browser().newContext();
    const external = [], errors = [];
    try {
      if (mode === 'self') await context.route('**/*', route => {
        if (new URL(route.request().url()).origin === 'http://127.0.0.1:8462') return route.continue();
        external.push(route.request().url()); return route.abort();
      });
      const tab = await context.newPage();
      tab.on('pageerror', e => errors.push(String(e)));
      await tab.goto(`http://127.0.0.1:8462/${mode}/`);
      await tab.bringToFront();
      await tab.waitForFunction(() => !document.getElementById('play').disabled, null, {timeout:60000});
      await tab.getByRole('button', {name:'Play',exact:true}).click();
      await tab.waitForFunction(() => document.getElementById('canvas').width === 480);
      const probe = async (command='pass') => {
        const stamp = String(Math.random());
        await tab.evaluate(code => window.python.PyRun_SimpleString(code), `import asyncio,json,platform\nfor task in asyncio.all_tasks():\n f=getattr(task.get_coro(),'cr_frame',None)\n if f and f.f_code.co_name=='drive':\n  s=f.f_locals['stage']\n  ${command}\n  platform.window.document.getElementById('canvas').setAttribute('data-proof',json.dumps({'stamp':${JSON.stringify(stamp)},'time':s.time,'y':s.objects[0].y,'x':s.objects[1].x,'runs':len(s._runs),'paused':s.paused}))`);
        await tab.waitForFunction(stamp => {const data=document.getElementById('canvas').getAttribute('data-proof');return data&&JSON.parse(data).stamp===stamp},stamp);
        return JSON.parse(await tab.locator('#canvas').getAttribute('data-proof'));
      };
      await tab.waitForTimeout(200);
      const initial=await probe();
      await tab.keyboard.press('Space');await tab.waitForTimeout(200);
      const moving=await probe();
      if(!(moving.y>initial.y && moving.y<0 && moving.x>initial.x && moving.runs===1)) throw Error(JSON.stringify({initial,moving}));
      await tab.keyboard.press('Space');
      const paused=await probe('s.pause()');await tab.waitForTimeout(150);const held=await probe();
      if(held.time!==paused.time||held.y!==paused.y)throw Error('Pause failed');
      await probe('s.resume()');await tab.waitForTimeout(650);const done=await probe();
      if(Math.abs(done.y)>0.001||done.runs!==0)throw Error('Busy/completion failed '+JSON.stringify(done));
      await tab.keyboard.press('a');await tab.waitForTimeout(700);const asyncDone=await probe();
      if(Math.abs(asyncDone.y+100)>0.001||asyncDone.runs!==0)throw Error('Async handler failed');
      if(external.length||errors.length)throw Error(JSON.stringify({external,errors}));
      await tab.screenshot({path:`output/playwright/blocks-${mode}.png`});
      results.push({mode,initial,moving,paused,done,asyncDone,external,errors});
    } finally {await context.close();}
  }
  return results;
}
