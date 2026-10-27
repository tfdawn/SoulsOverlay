// The look chosen on the settings page (/settings), applied to an overlay.
// The settings and their defaults come from /overlay/settings.json; only the
// changed ones are saved. They're written as CSS variables in a <style> just
// before data/overlay.css, so a hand-written overlay.css still wins.
window.DCStyle = (function () {
  "use strict";
  let schema = [];
  let byKey = {};
  let values = {};
  let target = "";
  let root = null;
  let extraHides = new Set();  // from ?hide= in the URL, kept on top of the settings

  function setSchema(s) {
    schema = s || [];
    byKey = {};
    for (const f of schema) byKey[f.key] = f;
  }

  function value(key) {
    return key in values ? values[key] : (byKey[key] ? byKey[key].default : undefined);
  }
  const text = (key) => String(value(key) ?? "");

  // A value that would close the declaration is dropped, whatever sent it.
  const safe = (v) => !/[;{}<>\\]/.test(String(v));

  function cssValue(f, v) {
    if (f.type === "number") return v + (f.unit || "");
    if (f.type === "enum") {
      const o = f.options.find((x) => x.value === v);
      return o && o.css;
    }
    return v;
  }

  function styleEl() {
    let el = document.getElementById("dc-style");
    if (!el) {
      el = document.createElement("style");
      el.id = "dc-style";
      const custom = document.querySelector('link[href="/overlay/custom.css"]');
      if (custom) custom.before(el); else document.head.appendChild(el);
    }
    return el;
  }

  function apply(newValues) {
    if (newValues) values = { ...newValues };
    const decls = [];
    for (const f of schema) {
      if (f.target !== target) continue;
      const v = value(f.key);
      if (f.var && f.key in values) {
        const css = cssValue(f, v);
        if (css != null && safe(css)) decls.push(`${f.var}: ${css};`);
      }
      if (f.hide) root.classList.toggle("hide-" + f.hide, v === false || extraHides.has(f.hide));
      if (f.cls) {
        for (const o of f.options) root.classList.toggle(f.cls + o.value, o.value === v);
      }
      if (f.type === "text") {
        for (const el of root.querySelectorAll(`[data-label="${f.key}"]`)) el.textContent = v;
      }
    }
    styleEl().textContent = decls.length ? `:root { ${decls.join(" ")} }` : "";
  }

  async function load(t, el, hides) {
    target = t;
    root = el;
    extraHides = new Set(hides || []);
    try {
      const res = await fetch("/overlay/settings.json", { cache: "no-store" });
      const data = await res.json();
      setSchema(data.schema);
      values = data.values || {};
    } catch (_) {
      // An older agent or no server: the CSS defaults stand.
    }
    apply();
    return values;
  }

  return { load, apply, value, text, get schema() { return schema; } };
})();
