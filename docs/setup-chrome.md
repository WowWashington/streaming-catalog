# Chrome Setup

StreamingCatalog uses a **dedicated Chrome profile** — separate from your normal Chrome browsing profile. This is intentional: Chrome 148+ enforces security restrictions that prevent Selenium from driving a browser that's also being used as your everyday browser. Using a dedicated profile sidesteps that, keeps your main browsing data untouched, and avoids weird conflicts if your normal Chrome is open at the same time.

## Where the profile lives

By default: `./chrome-profile/` inside your StreamingCatalog project directory.

That's the same on macOS, Windows, and Linux. The directory is created on first `streaming-catalog setup`. The whole `chrome-profile/` folder is gitignored, so it never gets committed.

You can override the location with an env var if you'd rather keep the profile elsewhere:

```bash
STREAMING_CATALOG_CHROME_PROFILE=/some/other/path
```

## Logging in

Run `streaming-catalog setup` (or `streaming-catalog login` if you already have a database). Chrome opens with two tabs — Fandango at Home and Movies Anywhere. Log in to both, then close Chrome. The terminal will detect the close and continue.

Your login persists in that dedicated profile across runs. You only need to re-log in when:
- The services' session cookies expire (varies, typically weeks to months)
- You delete the profile directory yourself

## "Chrome failed to start"

The most common cause: **Chrome was running when you launched `setup` or `collect`**. Even though we use a separate profile, macOS sometimes blocks Selenium from launching a new Chrome instance while another one is still running. Cmd+Q Chrome completely (close all windows, dot under the dock icon disappears) and try again.

If you killed Chrome forcefully and now `setup` complains about a lock file, delete the file shown in the error message and try again.

## Other Chromium browsers

Brave, Edge, Chromium, and similar browsers may work but aren't officially tested. The Selenium-Manager binary that selects the driver assumes Google Chrome; if you point `STREAMING_CATALOG_CHROME_PROFILE` at an Edge/Brave profile, behavior is undefined.
