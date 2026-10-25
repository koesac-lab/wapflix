# Initial Docker deployment

This is local deployment scaffolding for the existing M4 LCD streaming server.

## Layout

Create the deployment directory beside the source checkout:

```text
/home/koesac/wapflix-deploy/
├── compose.yaml
└── data/
    ├── cache/
    └── state/
```

`data/cache` and `data/state` are bind-mounted into the container at `/cache` and `/state`. The current M4 server does not yet use them; they establish the deployment layout for the later bounded-cache checkpoint.

## Source boundary

The Compose file mounts this host directory read-only:

```text
/mnt/14TB/TV/Haunted Hotel -> /media
```

The initial run uses only:

```text
/media/Season 1/Haunted.Hotel.S01E01.1080p.10bit.WEBRip.6CH.x265.HEVC-PSA.mkv
```

No library-wide scan, media copy, or background conversion is performed.

## Run

From `/home/koesac/wapflix-deploy`, after copying `compose.yaml` there:

```bash
mkdir -p data/cache data/state
docker compose up --build -d
docker compose ps
docker compose logs --follow
```

Open:

```text
http://<mini-PC-LAN-or-Tailscale-IP>:8101/
```

Do not forward port 8101 to the public internet.

## Stop

```bash
docker compose down
```

This does not delete `data/cache` or `data/state`.

## ASCII dimensions

The intended initial canvas is 120 x 54 characters. The current `lcd_stream_server.py` and `lcd_chunker.py` do not yet expose width/height configuration, so a separate small code checkpoint must add that setting before this deployment can enforce it.
