async page => {
  const results = [];
  for (const mode of ['cdn', 'self']) {
    const context = await page.context().browser().newContext({deviceScaleFactor:2});
    const external = [], errors = [], consoleMessages = [];
    try {
      if (mode === 'self') await context.route('**/*', route => {
        if (new URL(route.request().url()).origin === 'http://127.0.0.1:8463') return route.continue();
        external.push(route.request().url()); return route.abort();
      });
      const tab = await context.newPage();
      tab.on('pageerror', error => errors.push(String(error)));
      tab.on('console', message => consoleMessages.push(message.text()));
      await tab.goto(`http://127.0.0.1:8463/${mode}/`);
      await tab.bringToFront();
      await tab.waitForFunction(() => !document.getElementById('play').disabled, null, {timeout:60000});
      await tab.getByRole('button', {name:'Play',exact:true}).click();
      await tab.waitForFunction(() => document.getElementById('canvas').width === 480);
      await tab.waitForFunction(() => {
        window.python.PyRun_SimpleString("import asyncio,platform\nfor task in asyncio.all_tasks():\n f=getattr(task.get_coro(),'cr_frame',None)\n if f and f.f_code.co_name=='drive':\n  platform.window.document.getElementById('canvas').setAttribute('data-game-ready','yes')");
        return document.getElementById('canvas').getAttribute('data-game-ready') === 'yes';
      }, null, {polling:100});
      const probe = async (command='pass') => {
        const stamp = String(Math.random());
        const source = `import asyncio,json,platform
from plocks import Say,Think
for task in asyncio.all_tasks():
 f=getattr(task.get_coro(),'cr_frame',None)
 if f and f.f_code.co_name=='drive':
  bubble_stage=f.f_locals['stage']
s=bubble_stage
h=s.objects[0]
${command}
b=h._bubble
d=getattr(b,'definition',b)
white=sum(s._target.get_at((x,y))[:3]==(255,255,255) for x in range(480) for y in range(90,170,2)) if s._target else 0
platform.window.document.getElementById('canvas').setAttribute('data-bubble',json.dumps({'stamp':${JSON.stringify(stamp)},'time':s.time,'x':h.x,'friend':s.objects[1].x,'text':None if d is None else d.text,'runs':len(s._runs),'white':white,'mouse':s.mouse.position,'puppet':None if s.objects[2]._bubble is None else getattr(s.objects[2]._bubble,'definition',s.objects[2]._bubble).text}))`;
        await tab.evaluate(code => window.python.PyRun_SimpleString(code), source);
        await tab.waitForFunction(stamp => {const v=document.getElementById('canvas').getAttribute('data-bubble');return v&&JSON.parse(v).stamp===stamp},stamp);
        return JSON.parse(await tab.locator('#canvas').getAttribute('data-bubble'));
      };
      const initial=await probe();
      await tab.keyboard.press('Space');await tab.waitForTimeout(220);
      const moving=await probe();
      if(!(moving.x>initial.x && moving.friend>initial.friend && moving.text==='Watch me walk!' && moving.white>100)) throw Error(JSON.stringify({initial,moving}));
      await tab.screenshot({path:`output/playwright/bubbles-final-${mode}.png`});
      await tab.keyboard.press('Space');
      const paused=await probe('s.pause()');await tab.waitForTimeout(150);
      const held=await probe();
      if(held.time!==paused.time||held.x!==paused.x||held.text!==paused.text)throw Error('Pause failed');
      await probe('s.resume()');await tab.waitForTimeout(1000);
      const done=await probe();
      if(Math.abs(done.x)>0.001||done.text!==null||done.runs!==0)throw Error('Completion/busy failed '+JSON.stringify(done));
      await tab.keyboard.press('Space');await tab.waitForTimeout(120);
      await probe('h.act(Say("Replacement",seconds=0.4))');await tab.waitForTimeout(100);
      const replaced=await probe();
      await tab.waitForTimeout(450);const ended=await probe();
      if(replaced.text!=='Replacement'||ended.text!==null||ended.x!==replaced.x)throw Error('Replacement did not cancel movement root');
      await tab.keyboard.press('Space');await tab.waitForTimeout(100);
      await tab.keyboard.press('c');await tab.waitForTimeout(100);const canceled=await probe();
      if(canceled.text!==null||canceled.runs!==0)throw Error('Cancellation failed');
      await tab.keyboard.press('t');await tab.waitForTimeout(150);
      const thought=await probe('h.say("Persistent speech")');
      if(thought.puppet!=='Where next?'||thought.text!=='Persistent speech')throw Error('Puppet thought or persistent speech failed');
      await probe('s.bubble_text_size=28');
      await tab.evaluate(() => {const c=document.getElementById('canvas');c.style.width='360px';c.style.height='270px';});
      const box=await tab.locator('#canvas').boundingBox();
      await tab.mouse.click(box.x+box.width/4,box.y+box.height/4);
      await tab.waitForTimeout(100);
      const scaled=await probe();
      if(Math.abs(scaled.mouse[0]+120)>2||Math.abs(scaled.mouse[1]-90)>2)throw Error('Scaled pointer '+JSON.stringify(scaled));
      await tab.screenshot({path:`output/playwright/bubbles-scaled-${mode}.png`});
      await probe('h.clear_bubble()');
      await tab.waitForTimeout(2200);
      const quiet=await probe();
      if(quiet.text!==null||quiet.puppet!==null)throw Error('Clear or thought expiry failed');
      await tab.evaluate(() => window.python.PyRun_SimpleString("s.stop()\nplatform.window.document.getElementById('canvas').setAttribute('data-stopped','yes')"));
      await tab.waitForFunction(() => document.getElementById('canvas').hasAttribute('data-stopped'));
      await tab.waitForTimeout(100);
      await tab.evaluate(() => window.python.PyRun_SimpleString("platform.window.document.getElementById('canvas').setAttribute('data-clean',str(not s._runs and not s.objects and s._target is None and h._stage is None and h._bubble is None))"));
      await tab.waitForFunction(() => document.getElementById('canvas').hasAttribute('data-clean'));
      const cleanup=await tab.locator('#canvas').getAttribute('data-clean');
      if(cleanup!=='True'||external.length||errors.length)throw Error(JSON.stringify({cleanup,external,errors}));
      results.push({mode,initial,moving,paused,done,replaced,ended,canceled,thought,scaled,quiet,cleanup,external,errors});
    } catch(error) { throw Error(String(error) + '\n' + consoleMessages.slice(-35).join('\n')); } finally {await context.close();}
  }
  return results;
}
