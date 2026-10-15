async page => {
  const results=[];
  for(const mode of ['cdn','self']) for(const scenario of ['failure','cancellation']) {
    const context=await page.context().browser().newContext();
    const external=[];
    try {
      if(mode==='self') await context.route('**/*', route => {
        if(new URL(route.request().url()).origin==='http://127.0.0.1:8463')return route.continue();
        external.push(route.request().url());return route.abort();
      });
      const tab=await context.newPage();
      await tab.goto(`http://127.0.0.1:8463/${mode}/`);
      await tab.bringToFront();
      await tab.waitForFunction(()=>!document.getElementById('play').disabled,null,{timeout:60000});
      await tab.getByRole('button',{name:'Play',exact:true}).click();
      await tab.waitForFunction(()=>{
        window.python.PyRun_SimpleString("import asyncio,platform\nfor task in asyncio.all_tasks():\n f=getattr(task.get_coro(),'cr_frame',None)\n if f and f.f_code.co_name=='drive':\n  platform.window.document.getElementById('canvas').setAttribute('data-ready','yes')");
        return document.getElementById('canvas').hasAttribute('data-ready');
      },null,{polling:100});
      await tab.keyboard.press('Space');await tab.waitForTimeout(150);
      await tab.evaluate(code=>window.python.PyRun_SimpleString(code),`import asyncio,platform
for task in asyncio.all_tasks():
 f=getattr(task.get_coro(),'cr_frame',None)
 if f and f.f_code.co_name=='drive':
  bubble_stage=f.f_locals['stage']
  bubble_task=task
bubble_hero=bubble_stage.objects[0]
bubble_person=bubble_stage.objects[2]
assert bubble_hero._bubble is not None
bubble_person.think('cleanup me too')
def bubble_failure(dt):
 raise LookupError('deliberate bubble failure')
if '${scenario}'=='failure':
 bubble_stage.on_update(bubble_failure)
else:
 bubble_task.cancel()
platform.window.document.getElementById('canvas').setAttribute('data-triggered','yes')`);
      await tab.waitForFunction(()=>document.getElementById('canvas').hasAttribute('data-triggered'));
      if(scenario==='failure') {
        await tab.locator('#error').waitFor({state:'visible'});
        const message=await tab.locator('#error-message').innerText();
        if(!message.includes('LookupError: deliberate bubble failure')||!message.includes('Traceback'))throw Error(message);
      }
      await tab.waitForFunction(()=>{
        window.python.PyRun_SimpleString("platform.window.document.getElementById('canvas').setAttribute('data-clean',str(bubble_stage._state=='closed' and not bubble_stage._runs and not bubble_stage.objects and bubble_stage._target is None and bubble_hero._stage is None and bubble_person._stage is None and bubble_hero._bubble is None and bubble_person._bubble is None))");
        return document.getElementById('canvas').getAttribute('data-clean')==='True';
      },null,{polling:100});
      if(external.length)throw Error(JSON.stringify(external));
      results.push({mode,scenario,cleanup:true,external});
    } finally {await context.close();}
  }
  return results;
}
