# Chrome Profile Setup

StreamingCatalog uses your existing Chrome browser profile to access your library pages. You must be logged in to both services before running `streaming-catalog collect`.

## Finding your Chrome profile path

The tool auto-detects your Chrome profile location per OS:

| OS | Default path |
|----|-------------|
| macOS | `~/Library/Application Support/Google/Chrome` |
| Windows | `%LOCALAPPDATA%\Google\Chrome\User Data` |
| Linux | `~/.config/google-chrome` |

Override with: `STREAMING_CATALOG_CHROME_PROFILE=/path/to/chrome/user-data`

## Multiple profiles

If you use multiple Chrome profiles, set the profile name:

```bash
STREAMING_CATALOG_CHROME_PROFILE_NAME="Profile 2"
```

The default is `"Default"` (Chrome's first/main profile).

## Verifying you're logged in

Before running `collect`, verify manually:

1. Open Chrome and navigate to `https://athome.fandango.com/content/browse/mymovies`
   - You should see your movie library grid
2. Navigate to `https://moviesanywhere.com/my-movies`
   - You should see "X Movies" in the header with your library below

If either page asks you to log in, do so in Chrome first.

## Important notes

- Chrome must not be running in the background when `collect` starts (Selenium needs to open it fresh with your profile)
- The Chrome window must be visible — headless mode is not supported
- Do not interact with the Chrome window during collection (~30-60 seconds)
- If collection returns 0 items, your session likely expired — log in again in Chrome

## Chromium / Brave / Edge

These browsers use similar profile structures but different paths. Set `STREAMING_CATALOG_CHROME_PROFILE` to point at your browser's user-data directory. Chromium-based browsers generally work, but only Chrome is officially tested.
