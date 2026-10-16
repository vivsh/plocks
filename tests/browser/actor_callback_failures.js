async page => {
  const results=[];
  for(const mode of ['cdn','self']) for(const kind of ['update','click']) {
    const context=await page.context().browser().newContext();
    const external=[];
    try {
      if(mode==='self')await context.route('**/*',route=>{
        if(new URL(route.request().url()).origin==='http://127.0.0.1:8464')return route.continue();
        external.push(route.request().url());return route.abort();
      });
      const tab=await context.newPage();
      await tab.goto(`http://127.0.0.1:8464/actions-${mode}/`);
      await tab.bringToFront();
      await tab.waitForFunction(()=>!document.getElementById('play').disabled,null,{timeout:60000});
      await tab.getByRole('button',{name:'Play',exact:true}).click();
      await tab.waitForFunction(()=>{
        window.python.PyRun_SimpleString("import asyncio,platform\nfor t in asyncio.all_tasks():\n f=getattr(t.get_coro(),'cr_frame',None)\n if f and f.f_code.co_name=='drive':\n  platform.window.document.getElementById('canvas').setAttribute('data-ready','yes')");
        return document.getElementById('canvas').getAttribute('data-ready')==='yes';
      });
      await tab.evaluate(code=>window.python.PyRun_SimpleString(code),`import asyncio,json,platform
from plocks import MouseButton
for task in asyncio.all_tasks():
 frame=getattr(task.get_coro(),'cr_frame',None)
 if frame and frame.f_code.co_name=='drive':
  callback_stage=frame.f_locals['stage']
callback_actor=callback_stage.objects[0]
callback_actor.say('cleanup this bubble')
def bad_update(dt):
 raise LookupError('deliberate actor update failure')
async def bad_click(position,button):
 await callback_stage.wait(0)
 raise LookupError('deliberate actor click failure')
if '${kind}'=='update':
 callback_actor.on_update(bad_update)
else:
 callback_actor.on_click(bad_click)
 callback_stage._pending.append((callback_actor.position,MouseButton.LEFT))
platform.window.document.getElementById('canvas').setAttribute('data-triggered','yes')`);
      await tab.locator('#error').waitFor({state:'visible'});
      const message=await tab.locator('#error-message').innerText();
      if(!message.includes(`LookupError: deliberate actor ${kind} failure`)||!message.includes('Traceback'))throw Error(message);
      await tab.waitForFunction(()=>{
        window.python.PyRun_SimpleString("platform.window.document.getElementById('canvas').setAttribute('data-clean',str(not callback_stage._updates and not callback_stage._clicks and not callback_stage._actions and not callback_stage.objects and callback_stage._target is None and callback_actor._stage is None and callback_actor._bubble is None))");
        return document.getElementById('canvas').getAttribute('data-clean')==='True';
      });
      if(external.length)throw Error(JSON.stringify(external));
      results.push({mode,kind,originalTraceback:true,cleanup:true,external});
    }finally{await context.close();}
  }
  return results;
}
