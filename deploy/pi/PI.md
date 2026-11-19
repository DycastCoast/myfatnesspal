# Running MyFatnessPal on the Raspberry Pi (private, over Tailscale)

Nothing is on the public internet. Only devices signed in to **your own** tailnet can open it,
and only the logins in `.env` get past the door.

## 1. Save your diary from montlab

While it's still running: open https://dycast-myfatnesspal.montlab.cc → **Settings → Download backup**.
You get a `.db` file. That's your whole history.

## 2. Set up the Pi

Make sure the Pi is on your personal tailnet (the same one as your phone), not Scott's.

```sh
# Docker, if it isn't installed yet (log out and back in afterwards)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

mkdir -p ~/myfatnesspal/data && cd ~/myfatnesspal
# copy compose.yaml, .env.example and backup.sh from this folder into ~/myfatnesspal, then:
cp .env.example .env && nano .env          # fill in your logins (see the comments)
```

Copy the `.db` from step 1 to `~/myfatnesspal/data/myfatnesspal.db` (e.g. `scp` from your PC), then:

```sh
sudo chown -R 10001:10001 data             # the app runs as user 10001
chmod +x backup.sh
docker compose up -d
curl -s localhost:8085/healthz             # should print {"ok":true}
```

## 3. Put it on your tailnet

```sh
tailscale serve status                     # check nothing else is already served at /
sudo tailscale serve --bg 8085
```

It prints an address like `https://raspberrypi.tail1234.ts.net`. Open that on your phone and
**Add to Home screen**. HTTPS from Tailscale means the barcode camera works.
(If `tailscale serve` says HTTPS isn't enabled: admin console → DNS → turn on MagicDNS and HTTPS Certificates.)

Paste the same address into the MyFatnessPal card on your hub.

## 4. Backups

On the Pi: `crontab -e` and add
```
15 3 * * * /home/pi/myfatnesspal/backup.sh
```
(use your real home folder). On your PC, set up SSH key login to the Pi once, then schedule
`pull-backup.ps1` with the `schtasks` line at the top of that file.

To restore: stop the app (`docker compose down`), copy a backup over `data/myfatnesspal.db`,
`sudo chown 10001:10001 data/myfatnesspal.db`, `docker compose up -d`.

## 5. Take it off montlab

Only once the Pi version shows your history:

```powershell
kubectl delete deployment,service,ingress myfatnesspal -n dycast
kubectl delete pvc myfatnesspal-data -n dycast      # deletes the copy on montlab for good
```

Then remove `dycast-myfatnesspal.montlab.cc` from the `dycast-cloudflare` ConfigMap
(`k8s/cloudflare.yaml`) and apply it again.

## Updating

Push to GitHub as usual (the image still builds there), then on the Pi:
`docker compose pull && docker compose up -d`.
