async page => {
 const results=[];
 for(const mode of ['cdn','self']) {
  const ctx=await page.context().browser().newContext();
  const external=[],errors=[],requests=[];
  if(mode==='self')await ctx.route('**/*',r=>new URL(r.request().url()).origin==='http://127.0.0.1:8464'?r.continue():(external.push(r.request().url()),r.abort()));
  try {
   const tab=await ctx.newPage();tab.on('pageerror',e=>errors.push(String(e)));tab.on('request',r=>requests.push(r.url()));
   await tab.goto(`http://127.0.0.1:8464/physics-${mode}/`);await tab.bringToFront();
   await tab.waitForFunction(()=>!document.getElementById('play').disabled,null,{timeout:60000});
   await tab.getByRole('button',{name:'Play',exact:true}).click();
   await tab.waitForFunction(()=>document.getElementById('canvas').width===480);
   const probe=async(command='pass')=>{
    const stamp=String(Math.random());
    await tab.evaluate(code=>window.python.PyRun_SimpleString(code),`import asyncio,json,platform
for task in asyncio.all_tasks():
 f=getattr(task.get_coro(),'cr_frame',None)
 if f and f.f_code.co_name=='drive':
  s=f.f_locals['stage']
  hero=s.objects[1]
  ${command}
  platform.window.document.getElementById('canvas').setAttribute('data-physics',json.dumps({'stamp':${JSON.stringify(stamp)},'y':hero.y,'grounded':hero.body.grounded,'friend':s.objects[2].x,'bubble':hero._bubble is not None,'time':s.time}))`);
    await tab.waitForFunction(stamp=>{const v=document.getElementById('canvas').getAttribute('data-physics');return v&&JSON.parse(v).stamp===stamp},stamp);
    return JSON.parse(await tab.locator('#canvas').getAttribute('data-physics'));
   };
   await tab.waitForTimeout(1400);const rest=await probe();
   if(!rest.grounded||Math.abs(rest.y+90)>.3)throw Error('Contact failed '+JSON.stringify(rest));
   await tab.keyboard.press('Space');await tab.waitForTimeout(200);const jumping=await probe();
   if(jumping.grounded||jumping.y<-60||!jumping.bubble||jumping.friend===rest.friend)throw Error('Impulse/concurrency failed '+JSON.stringify(jumping));
   const paused=await probe('s.pause()');await tab.waitForTimeout(150);const held=await probe();
   if(held.y!==paused.y||held.time!==paused.time)throw Error('Paused body moved');
   await probe('s.resume()');await tab.waitForTimeout(1000);const landed=await probe();
   if(!landed.grounded||landed.bubble)throw Error('Landing or bubble cleanup failed');
   await tab.screenshot({path:`output/playwright/physics-${mode}.png`});
   if(errors.length||external.length)throw Error(JSON.stringify({errors,external}));
   results.push({mode,rest,jumping,landed,external,errors,requests:requests.length});
  } finally {await ctx.close();}
 }
 return results;
}
