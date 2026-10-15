/* The runtime configuration is read by the pinned Pygbag loader. */
window.config = {
  user_canvas: 1, user_canvas_managed: 1, gui_divider: 1, gui_debug: 1,
  ume_block: 0, can_close: 1, archive: "game", autorun: 0, PYBUILD: "3.12",
  fb_width: 480, fb_height: 360, quiet: true
};
window.plocksStarted = false;
window.custom_onload = function() {
  // Pygbag invokes this before CPython startup reads its environment arguments.
  window.Module.PyConfig.orig_argv.push("PYGPI=" + new URL("runtime-index/", location.href).href);
};
window.plocksError = function(message) {
  document.getElementById("transfer").hidden = true;
  document.getElementById("error-message").textContent = String(message);
  document.getElementById("error").hidden = false;
  console.error(message);
};
window.plocksReady = function() {
  document.getElementById("status").textContent = "Ready";
  document.getElementById("infobox").textContent = "Press Play to start.";
  document.getElementById("progress").hidden = true;
  document.getElementById("play").disabled = false;
};
window.addEventListener("error", event => window.plocksError(event.message));
window.addEventListener("unhandledrejection", event => window.plocksError(event.reason));
window.addEventListener("DOMContentLoaded", () => {
  document.getElementById("reload").addEventListener("click", () => location.reload());
  document.getElementById("play").addEventListener("click", () => {
    window.plocksStarted = true;
    if (window.MM) window.MM.UME = 1;
    document.getElementById("transfer").hidden = true;
    document.getElementById("canvas").focus();
  });
  document.getElementById("canvas").addEventListener("contextmenu", event => event.preventDefault());
  const loader = document.createElement("script");
  loader.id = "site";
  loader.type = "module";
  loader.dataset.python = "python3.12";
  loader.dataset.os = "gui";
  loader.textContent = document.getElementById("plocks-bootstrap").textContent;
  loader.src = "@@CDN@@pythons.js";
  document.body.appendChild(loader);
});
