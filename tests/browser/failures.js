async page => {
  const results=[];
  for (const name of ["startup", "callback"]) {
    const context = await page.context().browser().newContext();
    await context.route("**/*", route => new URL(route.request().url()).origin === "http://127.0.0.1:8463" ? route.continue() : route.abort());
    const tab = await context.newPage();
    await tab.goto(`http://127.0.0.1:8463/${name}/dist/web/`);
    await tab.bringToFront();
    await tab.waitForFunction(()=>!document.getElementById("play").disabled,null,{timeout:45000});
    await tab.getByRole("button", {name:"Play",exact:true}).click();
    await tab.locator("#error").waitFor({state:"visible"});
    const message=await tab.locator("#error-message").innerText();
    if (!message.includes(`deliberate ${name} failure`) || !message.includes("Traceback")) throw Error(message);
    let cleanup = null;
    if(name === "callback") {
      await tab.evaluate(()=>window.python.PyRun_SimpleString("import builtins,platform; platform.window.document.getElementById('canvas').setAttribute('data-closed', str((builtins.proof_stage._state, builtins.proof_stage._target, len(builtins.proof_stage._voices))))"));
      await tab.waitForFunction(()=>document.getElementById('canvas').hasAttribute('data-closed'));
      cleanup=await tab.locator('#canvas').getAttribute('data-closed');
      if(cleanup !== "('closed', None, 0)") throw Error(cleanup);
    }
    results.push({name,message,cleanup});
    await context.close();
  }
  return results;
}
