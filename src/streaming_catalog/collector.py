"""Browser-based library ID/slug collector using Selenium.

Drives a Chrome instance (using the user's persistent profile where they are
already logged in) to scroll the Vudu and Movies Anywhere library pages and
harvest content IDs/slugs.

Requirements:
- Chrome must be installed
- User must be logged in to both services in their Chrome profile
- Chrome window must be visible (not headless) — virtual scroll triggers
  depend on a real viewport
"""
from __future__ import annotations
import logging
import os
import time
from pathlib import Path

from streaming_catalog.config import resolve_chrome_profile, resolve_data_dir

log = logging.getLogger(__name__)

VUDU_MOVIES_URL = "https://athome.fandango.com/content/browse/mymovies"
VUDU_TV_URL = "https://athome.fandango.com/content/browse/mytv"
MA_URL = "https://moviesanywhere.com/my-movies"

VUDU_SCROLL_JS = """
return new Promise(resolve => {
  const ids = new Set();
  function harvest() {
    document.querySelectorAll('a[href*="/content/browse/details/"]').forEach(a => {
      const m = a.href.match(/\\/details\\/[^\\/]+\\/(\\d+)/);
      if (m) ids.add(m[1]);
    });
  }
  harvest();
  const container = Array.from(document.querySelectorAll('*')).find(el => {
    const s = getComputedStyle(el);
    return (s.overflowY === 'auto' || s.overflowY === 'scroll')
      && el.scrollHeight > el.clientHeight + 500;
  });
  if (!container) { resolve(Array.from(ids)); return; }
  const step = 1200;
  const max = container.scrollHeight;
  (async function loop() {
    for (let p = 0; p <= max; p += step) {
      container.scrollTop = p;
      container.dispatchEvent(new Event('scroll', {bubbles: true}));
      await new Promise(r => setTimeout(r, 700));
      harvest();
    }
    for (let p = max; p >= 0; p -= 800) {
      container.scrollTop = p;
      container.dispatchEvent(new Event('scroll', {bubbles: true}));
      await new Promise(r => setTimeout(r, 600));
      harvest();
    }
    resolve(Array.from(ids));
  })();
});
"""

MA_SCROLL_JS = """
return new Promise(resolve => {
  function getMain() {
    return document.querySelector('main') || document.body;
  }

  const allSlugs = new Set();
  function harvest() {
    const root = getMain();
    root.querySelectorAll('a[href*="/movie/"]').forEach(a => {
      const m = a.href.match(/\\/movie\\/([^?#"]+)/);
      if (m) allSlugs.add(m[1]);
    });
  }

  async function pageDownToEnd(maxIter) {
    let stable = 0, lastH = 0;
    for (let i = 0; i < maxIter; i++) {
      document.dispatchEvent(new KeyboardEvent('keydown', {
        key: 'PageDown', code: 'PageDown', keyCode: 34, which: 34,
        bubbles: true, cancelable: true,
      }));
      window.scrollBy({top: window.innerHeight, behavior: 'instant'});
      await new Promise(r => setTimeout(r, 800));
      harvest();
      const h = document.documentElement.scrollHeight;
      if (h === lastH) {
        stable++;
        if (stable >= 3) break;
      } else {
        stable = 0;
      }
      lastH = h;
    }
  }

  (async function() {
    window.scrollTo(0, 0);
    await new Promise(r => setTimeout(r, 500));
    harvest();
    await pageDownToEnd(80);
    resolve(Array.from(allSlugs));
  })();
});
"""


def _restrict_perms(path: Path) -> None:
    """
    Best-effort chmod 0700 on the given directory (no-op on Windows or any
    filesystem that doesn't support POSIX perms). The Chrome profile holds
    session cookies, so we don't want it world-readable on shared systems.
    """
    try:
        if os.name == "posix":
            path.chmod(0o700)
    except OSError:
        pass


def collect_via_selenium(
    services: list[str] | None = None,
    timeout: int = 120,
) -> dict:
    """
    Selenium-driven collection using the user's persistent Chrome profile.
    Returns counts dict and writes ID/slug files to the data directory.
    """
    if services is None:
        services = ["vudu", "ma"]

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except ImportError as e:
        raise RuntimeError(
            "selenium not installed. Run: pip install streaming-catalog[collect]"
        ) from e

    profile_dir = resolve_chrome_profile()
    profile_dir.mkdir(parents=True, exist_ok=True)
    _restrict_perms(profile_dir)
    data_dir = resolve_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    opts = Options()
    opts.add_argument(f"--user-data-dir={str(profile_dir)}")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")

    log.info("Opening Chrome with profile: %s", profile_dir)
    try:
        driver = webdriver.Chrome(options=opts)
    except Exception as e:
        msg = str(e)
        lock_file = profile_dir / "SingletonLock"
        hint = ""
        if lock_file.exists():
            hint = f"\n  - Found stale lock file. Delete it and try again:\n      {lock_file}"
        raise RuntimeError(
            f"Chrome failed to start. Common causes:\n"
            f"  - Chrome is already running (quit it first)\n"
            f"  - A previous session crashed and left a lock file{hint}\n"
            f"\nProfile: {profile_dir}\n"
            f"Error: {msg[:200]}"
        ) from e
    driver.set_script_timeout(timeout)

    try:
        results = {}

        if "vudu" in services:
            results["vudu"] = _collect_vudu(driver, data_dir)

        if "ma" in services:
            results["movies_anywhere"] = _collect_ma(driver, data_dir)

        return results
    finally:
        driver.quit()


def _collect_vudu(driver, data_dir: Path) -> dict:
    """Collect Vudu movie + TV IDs."""
    log.info("Loading Vudu /mymovies")
    driver.get(VUDU_MOVIES_URL)
    time.sleep(5)
    movie_ids = driver.execute_script(VUDU_SCROLL_JS) or []
    log.info("Collected %d Vudu movie IDs", len(movie_ids))

    log.info("Loading Vudu /mytv")
    driver.get(VUDU_TV_URL)
    time.sleep(5)
    tv_ids = driver.execute_script(VUDU_SCROLL_JS) or []
    log.info("Collected %d Vudu TV IDs", len(tv_ids))

    if tv_ids:
        (data_dir / "vudu_tv_ids.txt").write_text(",".join(tv_ids))

    all_ids = list({*movie_ids, *tv_ids})
    if all_ids:
        (data_dir / "vudu_ids.txt").write_text(",".join(all_ids))

    return {"movies": len(movie_ids), "tv": len(tv_ids), "total": len(all_ids)}


def _collect_ma(driver, data_dir: Path) -> int:
    """Collect Movies Anywhere slugs."""
    log.info("Loading Movies Anywhere library page")
    driver.get(MA_URL)
    time.sleep(5)
    slugs = driver.execute_script(MA_SCROLL_JS) or []

    if slugs:
        (data_dir / "ma_slugs.txt").write_text("\n".join(slugs) + "\n")
        log.info("Saved %d MA slugs", len(slugs))
    else:
        log.warning("MA collected 0 slugs — session may have expired")

    return len(slugs)
