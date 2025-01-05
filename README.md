# JellyMuxy

Automatic media library processor that scans for H.265 (HEVC) .mkv files, processes series and movies, handles subtitles/audio with fuzzy matching, and provides a web status interface.

## Features

- Scans media library for H.265 .mkv files
- Processes series and movies with proper naming
- Fuzzy-matches subtitles and audio tracks
- Automatic muxing with mkvmerge
- Real-time status web interface
- SQLite state tracking
- Docker-ready

## Requirements

- H.265 .mkv files in series/movies folders
- Directory structure:
  ```
  /data/
    ├── series/
    ├── movies/
    ├── anime_series/
    └── anime_movies/
  ```

## Quick Start

### Docker Run

```bash
docker run -d \
  --name media-processor \
  -v /path/to/media:/data \
  -v /path/to/config:/config \
  -p 8080:8080 \
  ghcr.io/Albatrosicks/JellyMuxy:latest
```

### Docker Compose

```yaml
version: "3.8"
services:
  media-processor:
    container_name: media-processor
    image: ghcr.io/JellyMuxy/JellyMuxy:latest
    volumes:
      - /path/to/media:/data
      - /path/to/config:/config
    ports:
      - "8080:8080"
    restart: unless-stopped
```

Save as `docker-compose.yml` and run:
```bash
docker-compose up -d
```

## Configuration

- Media files mount: `/data`
- Database location: `/config/media.db`
- Web interface: `http://localhost:8080`

## Features

### Series Processing

- Renames to: `Series Name - S01E02.mkv`
- Matches subtitles and audio
- Creates Extra/ and Fonts/ folders
- Supports multiple languages with tags: [ENG], [RUS], etc.

### Movies Processing

- Renames to match parent folder
- Moves to movies root after processing
- Handles multi-language tracks
- Removes empty source folders

## Building

```bash
git clone https://github.com/Albatrosicks/JellyMuxy
cd media-processor
docker build -t media-processor .
```

