async page => {
  const results = [];
  for (const failure of ['script', 'factory']) {
    const context = await page.context().browser().newContext();
    try {
      const external = [];
      await context.route('**/*', route => {
        if (new URL(route.request().url()).origin === 'http://127.0.0.1:8462') return route.continue();
        external.push(route.request().url());
        return route.abort();
      });
      const tab = await context.newPage();
      await tab.goto('http://127.0.0.1:8462/world-self/');
      await tab.bringToFront();
      await tab.waitForFunction(() => !document.getElementById('play').disabled, null, {timeout: 60000});
      await tab.getByRole('button', {name: 'Play', exact: true}).click();
      await tab.waitForFunction(() => document.getElementById('canvas').width === 640);
      await tab.evaluate(source => window.python.PyRun_SimpleString(source), `import asyncio,platform
from plocks import Script,Message
for task in asyncio.all_tasks():
    f=getattr(task.get_coro(),'cr_frame',None)
    if f and f.f_code.co_name=='drive':
        proof_stage=f.f_locals['stage']
        proof_game=proof_stage._updates[0].__globals__
        proof_hero=proof_game['hero']
        proof_person=proof_game['person']
async def fail_script(actor):
    await proof_stage.wait(0)
    raise LookupError('deliberate script failure')
def fail_factory(data):
    raise LookupError('deliberate factory failure')
if '${failure}' == 'script':
    proof_hero.act(Script(fail_script))
else:
    proof_message=Message[int]('failure proof')
    proof_stage.on_message(proof_message,proof_hero,fail_factory)
    proof_stage.broadcast(proof_message,1)
`);
      await tab.locator('#error').waitFor({state:'visible'});
      const message = await tab.locator('#error-message').innerText();
      if (!message.includes(`deliberate ${failure} failure`) || !message.includes('Traceback')) throw Error(message);
      await tab.evaluate(() => window.python.PyRun_SimpleString(`from plocks import Costume,Pose
proof_clean=(proof_stage._state=='closed' and proof_stage._target is None and not proof_stage._runs and not proof_stage._voices and not proof_stage._messages and proof_hero._stage is None and proof_person._stage is None and isinstance(proof_hero._visual,Costume) and isinstance(proof_person._pose,Pose))
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
