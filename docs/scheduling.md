# Scheduling Automatic Syncs

StreamingCatalog doesn't bundle a scheduler. Use your OS's native scheduling mechanism to run `streaming-catalog sync --collect-first` on a regular basis.

## Linux (cron)

```bash
crontab -e
```

Add:
```
# Weekly sync: Sunday at 3 AM
0 3 * * 0 cd /path/to/streaming-catalog && /path/to/streaming-catalog sync --collect-first >> /tmp/streaming-catalog.log 2>&1
```

## macOS (launchd)

See `examples/launchd.plist` for a template. Install with:

```bash
cp examples/launchd.plist ~/Library/LaunchAgents/com.streaming-catalog.sync.plist
# Edit paths in the plist, then:
launchctl load ~/Library/LaunchAgents/com.streaming-catalog.sync.plist
```

## Windows (Task Scheduler)

See `examples/task-scheduler.xml` for a template. Import via:

```powershell
schtasks /create /tn "StreamingCatalog Sync" /xml examples\task-scheduler.xml
```

Or use Task Scheduler GUI: Action > Import Task.

## Notes

- The `collect` step opens a Chrome window — schedule it when your computer is awake but you don't need to use Chrome
- If the Chrome session expires between syncs, `collect` will return 0 items and `sync` will skip (no data loss)
- Check logs to verify syncs are completing successfully
