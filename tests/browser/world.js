async page => {
  const context = await page.context().browser().newContext({ viewport: {width: 1000, height: 500}, deviceScaleFactor: 2 });
  try {
    const tab = await context.newPage();
    const external = [], errors = [], transfers = [];
    if (@@BLOCK_EXTERNAL@@) await context.route("**/*", route => {
      if (new URL(route.request().url()).origin === "http://127.0.0.1:8464") return route.continue();
      external.push(route.request().url());
      return route.abort();
    });
    tab.on("pageerror", error => errors.push(String(error)));
    tab.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    tab.on("requestfinished", request => transfers.push(request.sizes().then(size => ({url: request.url(), bytes: size.responseBodySize}))));
    const started = Date.now();
    await tab.goto("http://127.0.0.1:8464/world-@@MODE@@/");
    await tab.bringToFront();
    await tab.waitForFunction(() => !document.getElementById("play").disabled, null, {timeout: 60000});
    const readyMs = Date.now() - started;
    await tab.getByRole("button", {name: "Play", exact: true}).click();
    await tab.waitForFunction(() => document.getElementById('canvas').width === 640);
    if (await tab.title() !== 'Plocks: The Little World') throw Error('Project title was replaced during SDL startup');
    await tab.evaluate(() => window.python.PyRun_SimpleString("exec(" + JSON.stringify(`from base64 import b64decode
from PIL import Image
from pathlib import Path
from plocks import Costume
import json,platform,traceback
_formats = []
_fixtures = {'PNG': 'iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAIAAAAmkwkpAAAAEElEQVR42mP8z4AATAxEcQAz0QEH0oWRNwAAAABJRU5ErkJggg==', 'JPEG': '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAAEAAQDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAb/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAABgf/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCLAGVxf//Z', 'WEBP': 'UklGRjwAAABXRUJQVlA4IDAAAADQAQCdASoEAAQAAUAmJaACdLoB+AADsAD+8ut//NgVzXPv9//S4P0uD9Lg/9KQAAA=', 'WEBP_LOSSLESS': 'UklGRhwAAABXRUJQVlA4TA8AAAAvA8AAAAcQ/Y/+ByKi/wEA', 'WEBP_ALPHA': 'UklGRhwAAABXRUJQVlA4TA8AAAAvA8AAEAcQ/Y8CBiKi/wEA', 'WEBP_ANIM': 'UklGRoQAAABXRUJQVlA4WAoAAAACAAAAAwAAAwAAQU5JTQYAAAAAAAAAAABBTk1GKAAAAAAAAAAAAAMAAAMAAGQAAAJWUDhMDwAAAC8DwAAABxD9j/4HIqL/AQBBTk1GKAAAAAAAAAAAAAMAAAMAAGQAAABWUDhMDwAAAC8DwAAABxDR//4HIqL/AQA='}
try:
    for _format, _extension in [('PNG','png'), ('JPEG','jpg'), ('WEBP','webp')]:
        platform.window.document.getElementById('canvas').setAttribute('data-format-current', _format)
        _path = Path('/tmp/plocks-image.' + _extension)
        _path.write_bytes(b64decode(_fixtures[_format]))
        _image = Costume(_path).to_pillow()
        assert _image.size == (4,4) and _image.getpixel((0,0))[0] >= 250
        _path.unlink()
        _formats.append(_format)
    for _label in ('WEBP_LOSSLESS', 'WEBP_ALPHA', 'WEBP_ANIM'):
        platform.window.document.getElementById('canvas').setAttribute('data-format-current', _label)
        _path = Path('/tmp/plocks-extra.webp')
        _path.write_bytes(b64decode(_fixtures[_label]))
        _asset = Costume(_path)
        _image = _asset.to_pillow()
        assert _image.size == (4,4) and _image.getpixel((0,0))[0] == 255
        if _label == 'WEBP_ALPHA':
            assert _image.getpixel((0,0))[3] == 128
        if _label == 'WEBP_ANIM':
            with Image.open(_path) as _sequence:
                assert _sequence.n_frames == 2
                _sequence.seek(1)
                assert _sequence.getpixel((0,0))[2] == 255
                _sequence.seek(0)
                assert _sequence.getpixel((0,0))[0] == 255
        _image.putpixel((0,0),(0,0,0,0))
        assert _asset.to_pillow().getpixel((0,0))[0] == 255
        _path.unlink()
        _formats.append(_label)
except Exception:
    _formats.append(traceback.format_exc())
platform.window.document.getElementById('canvas').setAttribute('data-formats', json.dumps(_formats))
`) + ")"));
    await tab.waitForFunction(() => document.getElementById('canvas').hasAttribute('data-formats') || !document.getElementById('error').hidden);
    if (await tab.locator('#error').isVisible()) throw Error((await tab.locator('#error-message').innerText()) + ' codec=' + await tab.locator('#canvas').getAttribute('data-format-current'));
    const formats = JSON.parse(await tab.locator('#canvas').getAttribute('data-formats'));
    if (JSON.stringify(formats) !== JSON.stringify(['PNG','JPEG','WEBP','WEBP_LOSSLESS','WEBP_ALPHA','WEBP_ANIM'])) throw Error(JSON.stringify(formats));
    const probe = async (command = "pass") => {
      const stamp = String(Math.random());
      const code = `import asyncio,json,platform
from plocks import HumanJoint
for _task in asyncio.all_tasks():
    _frame = getattr(_task.get_coro(), 'cr_frame', None)
    if _frame and _frame.f_code.co_name == 'drive':
        _stage = _frame.f_locals['stage']
        _game = {}
        for _callback in [cb for owner,cb in _stage._updates]+_stage._draws:
            _game.update(zip(_callback.__code__.co_freevars,[cell.cell_contents for cell in (_callback.__closure__ or ())]))
        from plocks import Puppet
        _game['person'] = next(obj for obj in _stage.objects if isinstance(obj,Puppet))
        ${command}
        _result = {'stamp': ${JSON.stringify(stamp)}, 'time': _stage.time, 'x': _game['hero'].x, 'camera': _stage.camera, 'pose': _game['person'].pose.angles[HumanJoint.RIGHT_HAND], 'score': _game['score'], 'paused': _stage.paused, 'voices': len(_stage._voices)}
        platform.window.document.getElementById('canvas').setAttribute('data-proof', json.dumps(_result))
`;
      await tab.evaluate(source => window.python.PyRun_SimpleString(source), code);
      await tab.waitForFunction(token => {
        const text = document.getElementById("canvas").getAttribute("data-proof");
        return text && JSON.parse(text).stamp === token;
      }, stamp);
      return JSON.parse(await tab.locator("#canvas").getAttribute("data-proof"));
    };
    await tab.waitForTimeout(200);
    const initial = await probe();
    await tab.keyboard.down("ArrowRight");
    await tab.waitForTimeout(1600);
    await tab.keyboard.up("ArrowRight");
    const moved = await probe();
    if (moved.x < initial.x + 80 || moved.camera[0] <= 0 || moved.pose === initial.pose) throw Error("Animation/scroll failed: " + JSON.stringify({initial,moved}));
    await tab.keyboard.press("p");
    await tab.waitForTimeout(80);
    const paused = await probe();
    await tab.waitForTimeout(100);
    const held = await probe();
    if (!paused.paused || held.time !== paused.time || held.pose !== paused.pose) throw Error("Pause failed");
    await tab.keyboard.press("p");
    await tab.waitForTimeout(80);
    await tab.keyboard.press("Space");
    await tab.waitForTimeout(50);
    const sound = await probe();
    if (!sound.voices) throw Error("No live sound occurrence");
    const audio = await tab.evaluate(() => {
      const context = window.SDL2?.audioContext || window.SDL?.audioContext;
      return context ? {state: context.state, time: context.currentTime} : null;
    });
    if (audio && audio.state !== 'running') throw Error('Web Audio context did not start');
    await tab.waitForTimeout(500);
    const completedSound = await probe();
    if (completedSound.voices !== 0) throw Error('Audio did not consume the OGG occurrence');
    const wide = await tab.locator("#canvas").boundingBox();
    if (Math.abs(wide.width / wide.height - 1.6) > .01 || wide.height > 501) throw Error("Aspect ratio failure");
    await tab.mouse.click(wide.x + wide.width * .6, wide.y + wide.height * .71);
    await tab.waitForTimeout(80);
    const edited = await probe();
    if (edited.score !== 1) throw Error("High-DPI scaled click failed: " + JSON.stringify(edited));
    await tab.setViewportSize({width: 375, height: 800});
    const narrow = await tab.locator("#canvas").boundingBox();
    if (Math.abs(narrow.width / narrow.height - 1.6) > .01 || narrow.width > 376) throw Error("Narrow aspect ratio failure");
    await tab.mouse.click(narrow.x + narrow.width * .6, narrow.y + narrow.height * .71);
    await tab.waitForTimeout(80);
    const narrowEdit = await probe();
    if (narrowEdit.score !== 2) throw Error("Narrow scaled pointer failure");
    await tab.setViewportSize({width: 1000, height: 650});
    await tab.screenshot({path: "output/playwright/world-@@ENGINE@@.png"});
    const frameIntervals = await tab.evaluate(() => new Promise(resolve => {
      const gaps = []; let last;
      const sample = now => { if (last !== undefined) gaps.push(now-last); last=now; if (gaps.length < 60) requestAnimationFrame(sample); else resolve(gaps); };
      requestAnimationFrame(sample);
    }));
    const resources = await Promise.all(transfers);
    if (external.length || errors.length) throw Error(JSON.stringify({external,errors}));
    // Exercise browser task cancellation and inspect the original stage handle.
    await probe("_stage._task.cancel()");
    await tab.waitForTimeout(100);
    await tab.evaluate(() => {
      window.python.PyRun_SimpleString("platform.window.document.getElementById('canvas').setAttribute('data-closed', str((_stage._state, _stage._target, len(_stage._voices))))");
    });
    await tab.waitForFunction(() => document.getElementById("canvas").hasAttribute("data-closed"));
    const cleanup = await tab.locator("#canvas").getAttribute("data-closed");
    if (cleanup !== "('closed', None, 0)") throw Error("Cancellation cleanup failed: " + cleanup);
    const result = {readyMs, transfer: resources.filter(r=>r.url.startsWith('http')).reduce((sum,r) => sum+Math.max(0,r.bytes),0), formats,initial,moved,paused,sound,audio,completedSound,edited,narrowEdit,wide,narrow,frameIntervals,cleanup,external,errors,resources};
    return result;
  } finally {
    await context.close();
  }
}
