# MyFatnessPal

A calorie counter for me and my friends. FastAPI + SQLite, server-rendered pages,
installable on phones. Runs on Scott's montlab cluster at https://dycast-myfatnesspal.montlab.cc.

## Run it on your laptop

```powershell
docker build -t myfatnesspal .
docker run --rm -p 8080:8080 -e DEV_MODE=1 --read-only --tmpfs /tmp -v mfp-data:/data myfatnesspal
```

Then open http://localhost:8080. `DEV_MODE=1` logs you in as `dev@localhost` (never set it on the cluster).

## Deploy

1. `git push`, then wait for **test** and **build** to go green on the Actions tab.
2. Deploy that exact commit (not just "latest"):

```powershell
kubectl set image deployment/myfatnesspal app=ghcr.io/dycastcoast/myfatnesspal:$(git rev-parse HEAD) -n dycast
kubectl rollout status deployment/myfatnesspal -n dycast
```

Something broke? Go back to the previous version:

```powershell
kubectl rollout undo deployment/myfatnesspal -n dycast
```

Which version is running: `kubectl get deployment myfatnesspal -n dycast -o jsonpath="{..image}"`

Note: re-applying `k8s/app.yaml` sets the image back to `:latest`. Run the `set image` line again afterwards.

## UK generic foods (CoFID)

1. Download the spreadsheet from https://www.gov.uk/government/publications/composition-of-foods-integrated-dataset-cofid
2. `pip install openpyxl` then `python scripts/import_cofid.py "C:\path\to\the.xlsx"`
3. Commit `app/data/cofid.csv` and deploy. The app loads it once, on first start.

## Login

Cloudflare Access, configured by `k8s/cloudflare.yaml` (git-ignored: it lists people's emails).
To let a friend in, add their email to the `include` list and `kubectl apply -n dycast -f k8s\cloudflare.yaml`.

## Backups

Settings → Download backup (first user / `ADMIN_EMAILS` only). Downloads the whole SQLite database.

## Tests

`pip install -r requirements.txt -r requirements-dev.txt` then `pytest`. They also run in GitHub Actions before every build.
