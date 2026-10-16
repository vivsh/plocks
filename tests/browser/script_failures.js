async page => {
  const results = [];
  for (const failure of ['script', 'callback']) {
    const context = await page.context().browser().newContext();
    try {
      const external = [];
      await context.route('**/*', route => {
        if (new URL(route.request().url()).origin === 'http://127.0.0.1:8464') return route.continue();
        external.push(route.request().url());
        return route.abort();
      });
      const tab = await context.newPage();
      await tab.goto('http://127.0.0.1:8464/world-self/');
      await tab.bringToFront();
      await tab.waitForFunction(() => !document.getElementById('play').disabled, null, {timeout: 60000});
      await tab.getByRole('button', {name: 'Play', exact: true}).click();
      await tab.waitForFunction(() => document.getElementById('canvas').width === 640);
      await tab.evaluate(source => window.python.PyRun_SimpleString(source), `import asyncio,platform
from plocks import Message,Puppet,Sprite
for task in asyncio.all_tasks():
    f=getattr(task.get_coro(),'cr_frame',None)
    if f and f.f_code.co_name=='drive':
        proof_stage=f.f_locals['stage']
        proof_hero=next(a for a in proof_stage.objects if isinstance(a,Sprite))
        proof_person=next(a for a in proof_stage.objects if isinstance(a,Puppet))
async def fail_script():
    await proof_stage.wait(0)
    raise LookupError('deliberate script failure')
def fail_callback(data):
    raise LookupError('deliberate callback failure')
if '${failure}' == 'script':
    from plocks import Key
    proof_hero.on_key_down(Key.F)(fail_script)
    proof_stage._pending.append(Key.F)
else:
    proof_message=Message[int]('failure proof')
    proof_stage.on_message(proof_message)(fail_callback)
    proof_stage.broadcast(proof_message,1)
`);
      await tab.locator('#error').waitFor({state:'visible'});
      const message = await tab.locator('#error-message').innerText();
      if (!message.includes(`deliberate ${failure} failure`) || !message.includes('Traceback')) throw Error(message);
      await tab.evaluate(() => window.python.PyRun_SimpleString(`from plocks import Costume,Pose
proof_clean=(proof_stage._state=='closed' and proof_stage._target is None and not proof_stage._actions and not proof_stage._voices and not proof_stage._messages and proof_hero._stage is None and proof_person._stage is None and isinstance(proof_hero._visual,Costume) and isinstance(proof_person._pose,Pose))
platform.window.document.getElementById('canvas').setAttribute('data-clean',str(proof_clean))`));
      await tab.waitForFunction(() => document.getElementById('canvas').hasAttribute('data-clean'));
      const cleanup = await tab.locator('#canvas').getAttribute('data-clean');
      if (cleanup !== 'True' || external.length) throw Error(JSON.stringify({cleanup,external}));
      results.push({failure,message,cleanup,external});
    } finally {
      await context.close();
    }
  }
  return results;
}
