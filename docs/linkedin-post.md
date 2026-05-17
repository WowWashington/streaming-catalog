# LinkedIn Post — StreamingCatalog

---

I bought a movie twice last month because I couldn't remember if I already owned it.

If you've ever stared at the Fandango at Home or Movies Anywhere library page and tried to *search* for a title, you know the problem. There's no search box. No filter by year, director, or rating. Just a long, scroll-forever grid of posters. You either remember what you own, or you hit "buy" and hope for the best.

So I built StreamingCatalog — a small open-source tool that crawls your own library, pulls metadata for every title, and gives you a real searchable catalog of the movies and TV you own across both services.

What it does:
- Drives a logged-in Chrome session to harvest your library from Fandango at Home and Movies Anywhere
- Stores everything locally in a SQLite database with full-text search
- Merges titles you own on both services into a single record
- Tracks "first seen" dates so you can spot new purchases at a glance
- Flags revoked titles — yes, things you've "bought" can vanish, and now you'll know when one does
- Runs on macOS, Windows, and Linux

The whole thing is local. Your login lives in a dedicated Chrome profile on your own machine. No credentials are stored by the tool. Nothing is uploaded anywhere.

If you want to access your catalog from your phone or another laptop without exposing your home PC to the open internet, do not port-forward and do not slap on a random tunnel service. Install Tailscale on your host and on your phone. You get a private mesh network between your own devices over WireGuard, with zero ports open to the internet. Your search UI stays bound to localhost on the host, but every device in your tailnet can reach it as if it were on the LAN. It is the cleanest "remote access without the security headache" setup I have used, and it is free for personal use.

Code is on GitHub: https://github.com/WowWashington/streaming-catalog

Built as a framework — fork it, extend it to Apple TV / Prime / Plex / whatever, add watched-status, rental-availability cross-checks, recommendation engines. MIT licensed. Credit appreciated but not required.

If you have ever wondered "wait, do I already own this," this might save you a few accidental double-purchases.

#OpenSource #Python #HomeServer #Tailscale #DigitalOwnership #DataPortability
