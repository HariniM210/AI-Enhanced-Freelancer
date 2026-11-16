/* Mounts the shell (sidebar / nav / auth guard) and then loads the page scripts in order.
   Page scripts are listed in the data-scripts attribute of this tag. */
(function () {
  "use strict";
  if (!window.UI || !window.UI.mount()) return;       // false → redirecting (not signed in / wrong role)
  var list = (document.currentScript.getAttribute("data-scripts") || "").split(",").filter(Boolean);
  list.forEach(function (name) {
    var s = document.createElement("script");
    s.src = "js/" + name.trim(); s.async = false;
    document.body.appendChild(s);
  });
})();
