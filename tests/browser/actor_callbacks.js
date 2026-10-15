async page => {
  const results = [];
  for (const mode of ['cdn','self']) {
    const context = await page.context().browser().newContext({deviceScaleFactor:2});
    const external=[], errors=[], messages=[];
    try {
      if(mode==='self') await context.route('**/*', route => {
        if(new URL(route.request().url()).origin==='http://127.0.0.1:8465') return route.continue();
        external.push(route.request().url()); return route.abort();
      });
      const tab=await context.newPage();
      tab.on('pageerror', error=>errors.push(String(error)));
      tab.on('console', message=>messages.push(message.text()));
      await tab.goto(`http://127.0.0.1:8465/${mode}/`);
      await tab.bringToFront();
      await tab.waitForFunction(()=>!document.getElementById('play').disabled,null,{timeout:60000});
      await tab.getByRole('button',{name:'Play',exact:true}).click();
      await tab.waitForFunction(()=>{
        window.python.PyRun_SimpleString("import asyncio,platform\nfor t in asyncio.all_tasks():\n f=getattr(t.get_coro(),'cr_frame',None)\n if f and f.f_code.co_name=='drive':\n  platform.window.document.getElementById('canvas').setAttribute('data-ready','yes')");
        return document.getElementById('canvas').getAttribute('data-ready')==='yes';
      });
      const probe=async(command='pass')=>{
        const stamp=String(Math.random());
        await tab.evaluate(code=>window.python.PyRun_SimpleString(code),`import asyncio,inspect,json,platform
for task in asyncio.all_tasks():
 f=getattr(task.get_coro(),'cr_frame',None)
 if f and f.f_code.co_name=='drive':
  s=f.f_locals['stage']
h=s.objects[0]
f=s.objects[1]
${command}
def text(actor):
 b=actor._bubble
 return None if b is None else getattr(b,'definition',b).text
platform.window.document.getElementById('canvas').setAttribute('data-actors',json.dumps({'stamp':${JSON.stringify(stamp)},'time':s.time,'x':h.x,'y':h.y,'friend':f.x,'speech':text(h),'greeting':text(f),'clicks':inspect.getclosurevars(s._draws[0]).nonlocals['clicks'],'camera':s.camera,'paused':s.paused,'actors':len(s.objects),'puppet':None if len(s.objects)<3 else text(s.objects[2])}))`);
        await tab.waitForFunction(stamp=>{const v=document.getElementById('canvas').getAttribute('data-actors');return v&&JSON.parse(v).stamp===stamp},stamp);
        return JSON.parse(await tab.locator('#canvas').getAttribute('data-actors'));
      };
      const clickActor=async(index)=>{
        await probe(`platform.window.document.getElementById('canvas').setAttribute('data-hit',json.dumps(s.to_screen(s.objects[${index}].bounds.center)))`);
        const point=JSON.parse(await tab.locator('#canvas').getAttribute('data-hit'));
        const box=await tab.locator('#canvas').boundingBox();
        await tab.mouse.click(box.x+point[0]*box.width/640,box.y+point[1]*box.height/360);
      };
      const initial=await probe();
      await tab.keyboard.down('ArrowRight');await tab.waitForTimeout(200);await tab.keyboard.up('ArrowRight');
      const moved=await probe();
      if(!(moved.x>initial.x && moved.friend>initial.friend))throw Error('Actor updates failed '+JSON.stringify(moved));
      await clickActor(0);await tab.waitForTimeout(120);
      const clicked=await probe();
      if(clicked.speech!=='You clicked me!'||clicked.greeting!==null||clicked.clicks!==1)throw Error('Actor block click '+JSON.stringify(clicked));
      await clickActor(1);await tab.waitForTimeout(80);
      const greeted=await probe();
      if(greeted.greeting!=='Left click!'||greeted.clicks!==2)throw Error('Actor callback click');
      await tab.waitForTimeout(850);
      await probe('s.camera=(80,0)');
      await tab.locator('#canvas').evaluate(canvas=>{canvas.style.width='320px';canvas.style.height='180px'});
      await clickActor(0);await tab.waitForTimeout(100);
      const scaled=await probe();
      if(scaled.speech!=='You clicked me!'||scaled.clicks!==3)throw Error('Scaled/camera click '+JSON.stringify(scaled));
      const paused=await probe('s.pause()');await tab.waitForTimeout(150);
      await clickActor(1);await tab.waitForTimeout(80);
      const held=await probe();
      if(held.time!==paused.time||held.x!==paused.x||held.friend!==paused.friend||held.clicks!==4)throw Error('Paused updates/UI clicks');
      await probe('s.resume()');
      await tab.waitForTimeout(800);
      const extra=await probe();
      if(extra.actors>2){
        await clickActor(2);await tab.waitForTimeout(120);
        const puppet=await probe();
        if(puppet.puppet!=='Puppet clicked!')throw Error('Puppet click failed');
      }
      await tab.screenshot({path:`output/playwright/actor-callbacks-${mode}.png`});
      await probe('s.stop()');
      await tab.waitForFunction(()=>{
        window.python.PyRun_SimpleString("platform.window.document.getElementById('canvas').setAttribute('data-clean',str(not s._updates and not s._clicks and not s._runs and not s.objects and s._target is None))");
        return document.getElementById('canvas').getAttribute('data-clean')==='True';
      });
      if(external.length||errors.length)throw Error(JSON.stringify({external,errors}));
      results.push({mode,initial,moved,clicked,greeted,scaled,held,cleanup:true,external,errors});
    }catch(error){throw Error(String(error)+'\n'+messages.slice(-30).join('\n'));}
    finally{await context.close();}
  }
  return results;
}
