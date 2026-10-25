FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

USER 1000:1000

EXPOSE 8101

ENTRYPOINT ["python3", "tools/lcd_stream_server.py"]
CMD ["--video", "/media/Season 1/Haunted.Hotel.S01E01.1080p.10bit.WEBRip.6CH.x265.HEVC-PSA.mkv", "--bind", "0.0.0.0", "--port", "8101"]
