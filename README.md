# PS5 stock monitor

Watches the [MTC Factory Outlet PS5 Digital Edition (CFI-1x15B, no stand)](https://mtcfactoryoutlet.com/product/playstation-5-ps5-digital-edition-console-cfi-1x15b-no-stand-included/)
listing and sends a push notification to your phone (via [ntfy](https://ntfy.sh)) when it's back in stock.

## Setup

1. Install the **ntfy** app (iOS / Android) and subscribe to a hard-to-guess topic name,
   e.g. `ps5-alert-7f3k9q`.
2. In this repo: **Settings → Secrets and variables → Actions → New repository secret**,
   name `NTFY_TOPIC`, value = your topic name.
3. **Actions** tab → enable workflows if prompted → **PS5 stock monitor** → **Run workflow**
   with "Send test alert" ticked. Your phone should buzz.
4. Done. The workflow runs every 5 minutes and checks about once a minute.

Keep the repo **public**: Actions minutes are free and unlimited for public repos. A private
repo would burn through the free 2,000 minutes/month in about a week. The topic name is stored as
a secret, so nothing sensitive is exposed.

GitHub pauses scheduled workflows after 60 days with no repo activity. If that happens,
re-enable the workflow from the Actions tab.

## Run locally instead

```
python3 ps5_stock_monitor.py --ntfy-topic your-topic
```
