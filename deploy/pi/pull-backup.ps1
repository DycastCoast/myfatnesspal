# Runs on your PC: copies the Pi's latest backup here, so an SD card failure can't lose the diary.
# Needs SSH key login to the Pi (no password prompt). Schedule it once with:
#   schtasks /Create /SC DAILY /ST 12:00 /TN "MyFatnessPal backup" /TR "powershell -NoProfile -File `"$PSScriptRoot\pull-backup.ps1`""
param(
    [string]$Pi = "pi@raspberrypi",                                   # your Pi's SSH user and Tailscale name
    [string]$Folder = "$env:USERPROFILE\Documents\MyFatnessPal backups"
)
New-Item -ItemType Directory -Force -Path $Folder | Out-Null
$dest = Join-Path $Folder ("myfatnesspal-" + (Get-Date -Format "yyyy-MM-dd") + ".db")
scp -q -o BatchMode=yes "${Pi}:~/myfatnesspal/backups/latest.db" $dest
if ($LASTEXITCODE -ne 0) { Write-Error "Couldn't reach the Pi (is it on, and is Tailscale connected?)"; exit 1 }
# Keep the newest 60 copies
Get-ChildItem $Folder -Filter "myfatnesspal-*.db" | Sort-Object Name -Descending | Select-Object -Skip 60 | Remove-Item
