async page => {
 const results=[];
 for(const mode of ['cdn','self']) {
  const context=await page.context().browser().newContext();
  const errors=[],external=[],messages=[];let phase='load';
  try {
   if(mode==='self')await context.route('**/*',r=>new URL(r.request().url()).origin==='http://127.0.0.1:8464'?r.continue():(external.push(r.request().url()),r.abort()));
   const tab=await context.newPage();tab.on('pageerror',e=>errors.push(String(e)));tab.on('console',m=>messages.push(m.text()));
   await tab.goto(`http://127.0.0.1:8464/playground-${mode}/`);await tab.bringToFront();
   await tab.waitForFunction(()=>!document.getElementById('play').disabled,null,{timeout:60000});
   await tab.getByRole('button',{name:'Play',exact:true}).click();
   phase='canvas';await tab.waitForFunction(()=>document.getElementById('canvas').width===640);
   const probe=async(command='pass')=>{
    const stamp=String(Math.random());
    await tab.evaluate(code=>window.python.PyRun_SimpleString(code),`import asyncio,platform,json
for task in asyncio.all_tasks():
 f=getattr(task.get_coro(),'cr_frame',None)
 if f and f.f_code.co_name=='drive':
  playground=f.f_locals['stage']
s=playground
h=s.objects[1]
${command}
platform.window.document.getElementById('canvas').setAttribute('data-playground',json.dumps({'stamp':${JSON.stringify(stamp)},'x':h.x,'y':h.y,'grounded':h.body.grounded,'lift':s.objects[2].y,'spin':s.objects[3].body.angular_velocity}))`);
    await tab.waitForFunction(stamp=>{const v=document.getElementById('canvas').getAttribute('data-playground');return v&&JSON.parse(v).stamp===stamp},stamp);
    return JSON.parse(await tab.locator('#canvas').getAttribute('data-playground'));
   };
   phase='rest';await tab.waitForTimeout(500);const rest=await probe();
   if(!rest.grounded)throw Error('Hero did not land '+JSON.stringify(rest));
   await tab.keyboard.down('ArrowRight');await tab.keyboard.press('Space');await tab.keyboard.press('t');await tab.waitForTimeout(180);await tab.keyboard.up('ArrowRight');
   phase='moving';const moving=await probe();
   if(moving.x<=rest.x||moving.y<=rest.y+15||moving.grounded||moving.lift===rest.lift||Math.abs(moving.spin)<1)throw Error(JSON.stringify({rest,moving}));
   await tab.screenshot({path:`output/playwright/playground-${mode}.png`});
   phase='cleanup';await tab.evaluate(()=>window.python.PyRun_SimpleString("s.stop()\nplatform.window.document.getElementById('canvas').setAttribute('data-stopped','yes')"));
   await tab.waitForFunction(()=>document.getElementById('canvas').getAttribute('data-stopped')==='yes');
   await tab.waitForTimeout(100);
   await tab.waitForFunction(()=>{
    window.python.PyRun_SimpleString("platform.window.document.getElementById('canvas').setAttribute('data-clean',str(s._physics._space is None and not s._actions and not s.objects))");
    return document.getElementById('canvas').getAttribute('data-clean')==='True';
   });
   if(errors.length||external.length)throw Error(JSON.stringify({errors,external}));
   results.push({mode,rest,moving,cleanup:true,external,errors});
  }catch(error){throw Error(`${phase}: ${error}\n${messages.filter(m=>!m.startsWith('1:')).slice(-50).join('\n')}`);}finally{await context.close();}
 }
 return results;
}
