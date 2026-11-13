/* bloomterm — the whole client. Command line, focus, polling. No framework. */
(() => {
  "use strict";

  const grid = document.getElementById("grid");
  const body = document.body;
  const input = document.getElementById("q");
  const form = document.getElementById("cmd");
  const hint = document.getElementById("hint");
  const clock = document.getElementById("clock");
  const help = document.getElementById("help");

  const RANGES = ["1D", "5D", "1M", "6M", "1Y"];
  let active = 0;
  let hintTimer = 0;

  const panels = () => Array.from(grid.querySelectorAll(".panel"));
  const panelAt = (i) => grid.querySelector("#panel-" + i);

  /* ------------------------------------------------------------- url state */

  function syncURL() {
    const url = new URL(location.href);
    url.searchParams.set("l", body.dataset.preset || "4");
    panels().forEach((p, i) => {
      let spec = p.dataset.fn;
      if (p.dataset.sym) spec += ":" + p.dataset.sym;
      if (p.dataset.sym && p.dataset.range) spec += ":" + p.dataset.range;
      url.searchParams.set("p" + i, spec);
    });
    history.replaceState(null, "", url);
  }

  function setActive(i, focus) {
    const ps = panels();
    if (!ps.length) return;
    active = Math.max(0, Math.min(i, ps.length - 1));
    ps.forEach((p, idx) => p.classList.toggle("active", idx === active));
    if (ps[active].dataset.fn !== "N") {
      grid.querySelectorAll(".news-row.sel").forEach((r) => r.classList.remove("sel"));
    }
    if (focus) ps[active].focus({ preventScroll: true });
    syncURL();
  }

  function replacePanel(i, html, focus) {
    const el = panelAt(i);
    if (!el) return;
    el.outerHTML = html; // same-origin fragment rendered by our own server
    setActive(i, Boolean(focus));
  }

  function say(message, bad) {
    hint.textContent = message || "";
    hint.classList.toggle("bad", Boolean(bad));
    clearTimeout(hintTimer);
    if (message) hintTimer = setTimeout(() => { hint.textContent = ""; }, 3600);
  }

  /* --------------------------------------------------------------- command */

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const q = input.value.trim();
    if (!q) return;
    const panel = panelAt(active);
    try {
      const res = await fetch("/api/command", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ q, index: active, sym: panel?.dataset.sym || "" }),
      });
      const data = await res.json();
      if (!data.ok) {
        const hintText = data.candidates?.length ? " — try " + data.candidates.join(", ") : "";
        say(data.error + hintText, true);
        return;
      }
      input.value = "";
      say("");
      replacePanel(active, data.html, false);
      input.focus(); // stay in the command line: commands come in bursts
    } catch (_) {
      say("command failed", true);
    }
  });

  /* ------------------------------------------------------- panel interaction */

  async function loadRange(i, range) {
    const panel = panelAt(i);
    if (!panel) return;
    const sym = panel.dataset.sym || "AAPL";
    try {
      const res = await fetch(
        `/api/panel?fn=GP&sym=${encodeURIComponent(sym)}&range=${encodeURIComponent(range)}&i=${i}`
      );
      if (!res.ok) return;
      replacePanel(i, await res.text(), true);
    } catch (_) {
      /* keep the old chart rather than blanking */
    }
  }

  grid.addEventListener("click", (event) => {
    help.hidden = true;
    const panel = event.target.closest(".panel");
    if (!panel) return;
    const i = Number(panel.id.slice(6));

    const row = event.target.closest(".news-row");
    if (row) {
      grid.querySelectorAll(".news-row.sel").forEach((r) => r.classList.remove("sel"));
      row.classList.add("sel");
    }

    const tab = event.target.closest(".tab");
    if (tab && panel.dataset.fn === "GP") {
      setActive(i, false);
      loadRange(i, tab.dataset.range);
      return;
    }
    setActive(i, true);
  });

  /* --------------------------------------------------------------- keyboard */

  function cycleRange(direction) {
    const panel = panelAt(active);
    if (!panel || panel.dataset.fn !== "GP") return false;
    const current = RANGES.indexOf(panel.dataset.range || "5D");
    const next = (current + direction + RANGES.length) % RANGES.length;
    loadRange(active, RANGES[next]);
    return true;
  }

  function selectNews(direction) {
    const panel = panelAt(active);
    if (!panel || panel.dataset.fn !== "N") return false;
    const rows = Array.from(panel.querySelectorAll(".news-row"));
    if (!rows.length) return false;
    let i = rows.findIndex((r) => r.classList.contains("sel"));
    if (i < 0) {
      i = direction > 0 ? 0 : rows.length - 1;
    } else {
      i = Math.max(0, Math.min(rows.length - 1, i + direction));
    }
    rows.forEach((r) => r.classList.remove("sel"));
    rows[i].classList.add("sel");
    rows[i].scrollIntoView({ block: "nearest" });
    return true;
  }

  function specOf(panel) {
    const sym = panel.dataset.sym ? panel.dataset.sym + " " : "";
    return (sym + panel.dataset.fn).trim();
  }

  document.addEventListener("keydown", (event) => {
    const typing = document.activeElement === input;

    if (event.key === "Escape") {
      if (typing) input.blur();
      else if (!help.hidden) help.hidden = true;
      else setActive(active, true);
      return;
    }

    if (!typing && (event.key === "/" || ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k"))) {
      event.preventDefault();
      input.focus();
      input.select();
      return;
    }

    if (event.altKey && /^[1-6]$/.test(event.key)) {
      event.preventDefault();
      setActive(Number(event.key) - 1, true);
      return;
    }

    if (event.key === "?" && (!typing || input.value === "")) {
      event.preventDefault();
      help.hidden = !help.hidden;
      return;
    }

    if (!typing && event.key === "Tab") {
      event.preventDefault();
      setActive((active + 1) % panels().length, true);
      return;
    }

    if (!typing && (event.key === "[" || event.key === "]")) {
      if (cycleRange(event.key === "]" ? 1 : -1)) event.preventDefault();
      return;
    }

    if (!typing && (event.key === "j" || event.key === "k")) {
      if (selectNews(event.key === "j" ? 1 : -1)) {
        event.preventDefault();
        return;
      }
    }

    if (!typing && event.key === "Enter") {
      if (document.activeElement && document.activeElement.tagName === "A") return;
      const panel = panelAt(active);
      const selected = grid.querySelector(".news-row.sel");
      if (panel && panel.dataset.fn === "N" && selected && selected.tagName === "A") {
        event.preventDefault();
        selected.click();
        return;
      }
      if (panel) {
        event.preventDefault();
        input.value = specOf(panel);
        input.focus();
        input.select();
      }
    }
  });

  /* ---------------------------------------------------------------- polling */

  function paint(row) {
    const panel = grid.querySelector('[data-fn="WATCH"]');
    if (!panel) return;
    const tr = panel.querySelector(`tr[data-sym="${row.sym}"]`);
    if (!tr) return;

    const last = tr.querySelector(".last");
    if (last && last.textContent !== row.last) {
      last.textContent = row.last;
      tr.classList.add("tick");
      setTimeout(() => tr.classList.remove("tick"), 160);
    }
    if (last) last.className = "num last " + row.dir;

    const cellClass = "num " + row.dir;
    const chg = tr.querySelector('[data-f="chg"]');
    const pct = tr.querySelector('[data-f="pct"]');
    if (chg) { chg.textContent = row.chg; chg.className = cellClass; }
    if (pct) { pct.textContent = row.pct; pct.className = cellClass; }
  }

  async function pollWatch() {
    if (document.hidden) return;
    if (!grid.querySelector('[data-fn="WATCH"]')) return;
    try {
      const res = await fetch("/api/watch");
      if (!res.ok) return;
      (await res.json()).forEach(paint);
    } catch (_) {
      /* a failed poll must never blank the screen */
    }
  }

  // the interval comes from the panel the server rendered, one source of truth
  const watchPanel = grid.querySelector('[data-fn="WATCH"]');
  const pollMs = Number(watchPanel?.dataset.poll || 15) * 1000;
  setInterval(pollWatch, pollMs);

  /* ------------------------------------------------------------------ clock */

  function tickClock() {
    if (!clock) return;
    const time = new Intl.DateTimeFormat("en-GB", {
      timeZone: "America/New_York",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }).format(new Date());
    clock.textContent = time + " ET";
  }

  setInterval(tickClock, 1000);
  tickClock();

  /* ------------------------------------------------------------------- boot */

  setActive(0, false);
  input.focus();
})();
