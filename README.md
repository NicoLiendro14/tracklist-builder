# DJ Set Track Identifier

A Python tool that automatically generates tracklists from DJ sets on YouTube using Shazam and AcoustID audio recognition services.

## Description

This tool allows you to:
- Download a set from YouTube using yt-dlp
- Split the audio into configurable duration segments (chunks)
- Analyze each segment using the Shazam API or AcoustID
- Consolidate the results into a clean and accurate tracklist
- Export the results in multiple formats (TXT, JSON, HTML, CUE)
- Search and enrich track metadata using the Discogs API
- Get detailed release information from Discogs

Ideal for DJs, music enthusiasts, and content creators who want to identify songs in long sets without having to manually recognize each track.

## Requirements

```
python >= 3.8
yt-dlp
pydub
ffmpeg
shazamio
fpcalc (Chromaprint)
```

## Installation

```bash
pip install -r requirements.txt

# Install ffmpeg according to your operating system

# Install fpcalc/Chromaprint
# On Ubuntu/Debian:
sudo apt-get install libchromaprint-tools

# On macOS:
brew install chromaprint

# On Windows:
# Download from https://acoustid.org/chromaprint and add to PATH
```

## Configuration

Create a `.env` file in the root directory with your Discogs API credentials:

```env
DISCOGS_USER_AGENT=YourAppName/1.0 +http://your-website.com
DISCOGS_CONSUMER_KEY=your_consumer_key_here
DISCOGS_CONSUMER_SECRET=your_consumer_secret_here
```

You can get these credentials by registering your application at https://www.discogs.com/settings/developers

## Usage

```bash
# Using Shazam for identification
python shazam_track_identifier.py [YOUTUBE_URL]

# Using AcoustID for identification
python acoustid_track_identifier.py [YOUTUBE_URL]

# Advanced usage with options (Shazam)
python shazam_track_identifier.py [YOUTUBE_URL] --chunk-duration 30 --output-dir my_tracklists --formats txt,json,html,cue
```

### Command line arguments

- `url`: YouTube URL of the DJ set to analyze
- `--chunk-duration`: Duration of audio chunks in seconds (default: 30 for Shazam, 60 for AcoustID)
- `--output-dir`: Directory to save output files (default: 'output')
- `--formats`: Comma-separated list of output formats (default: txt,json,html,cue)

## API Endpoints

The tool provides a FastAPI-based REST API with the following endpoints:

- `POST /api/tracks/identify/url`: Identify tracks from a YouTube URL
- `POST /api/discogs/search`: Search for tracks in the Discogs database
- `GET /api/discogs/releases/{release_id}`: Get detailed information about a specific release

### Discogs Search Example

```bash
curl -X POST "http://localhost:8000/api/discogs/search" \
     -H "Content-Type: application/json" \
     -d '{"query": "Daft Punk", "type": "release", "per_page": 10, "page": 1}'
```

### Discogs Release Details Example

```bash
# Get release details
curl "http://localhost:8000/api/discogs/releases/8115398"

# Get release details with specific currency
curl "http://localhost:8000/api/discogs/releases/8115398?curr_abbr=USD"
```

The release details endpoint returns comprehensive information including:
- Basic release information (title, artists, year)
- Tracklist with durations
- Format details
- Images and videos
- Community data (ratings, wants, haves)
- Marketplace information
- Additional metadata (notes, identifiers, etc.)

## Audio Recognition Services

This tool supports two recognition services:

- **Shazam**: Excellent for mainstream music and recent releases. Uses the shazamio library.
- **AcoustID**: Open-source fingerprinting system with a large library of tracks. Requires fpcalc (Chromaprint).
- **Discogs**: Integration with Discogs API for track metadata enrichment and search.

## Export Formats

The tool can export tracklists in multiple formats:

- **TXT**: Simple text format with track numbers, timestamps, titles, and artists.
- **JSON**: Structured data format with metadata for integration with other applications.
- **HTML**: Visual presentation similar to 1001Tracklist with a modern, responsive design.
- **CUE**: Standard format for DJ software and media players with precise timestamps.

## Implemented Features

- **Multiple Recognition Services**: Supports both Shazam and AcoustID for better coverage and accuracy.
- **Discogs Integration**: Search and enrich track metadata using the Discogs API.
- **Detailed Release Information**: Get comprehensive release details from Discogs.
- **Intelligent Result Consolidation**: Uses a text similarity-based algorithm (difflib) to correctly group fragmented identifications of the same track.
- **Minimum Duration Filtering**: Automatically discards tracks identified with duration less than a configurable threshold.
- **Multiple Export Formats**: Exports tracklists in various formats (TXT, JSON, HTML, CUE) for different use cases.
- **Robust Error Handling**: Implements exponential backoff with jitter to handle API rate limits and network issues.
- **Environment Configuration**: Uses .env files for secure credential management.

## Planned Improvements (TODO)

### Short-Term Improvements
- [ ] **Service Integration**: Combine results from both Shazam and AcoustID for improved accuracy
- [ ] **Similarity Threshold Adjustment**: Reduce the threshold to improve consolidation of tracks with variations in names
- [ ] **Max Interruption Adjustment**: Expand tolerance for gaps between detections of the same track
- [x] **Improved Output Format**: Implement format similar to 1001Tracklist with numbering
- [ ] **Chunk Duration Adjustment**: Experiment with different values to optimize accuracy
- [ ] **Audio Preprocessing**: Normalize volume and equalization to improve recognition rates

### Intermediate Improvements
- [ ] **Confidence Scoring System**: Implement logic to value consistent identifications
- [x] **Enriched Metadata**: Integrate with Discogs API for additional track information
- [ ] **Recognition Cache**: Store previous results to improve performance in future analyses
- [x] **DJ Format Exports**: Generate files compatible with popular DJ software

### Advanced Improvements
- [ ] **Unidentified Section Interpolation**: Algorithms to make reasonable assumptions about unidentified parts
- [ ] **Manual Labeling**: Interface to manually correct or label problematic sections
- [ ] **Remix Detection**: Identify when a song is a remix of another and group them appropriately
- [ ] **Cross-Verification**: Compare results with other music identification APIs
- [ ] **Transition Detection**: Analysis of audio characteristics to identify changes between songs

## Current Results

The script currently significantly reduces the number of erroneous and duplicate identifications. In tests with one-hour sets:
- Reduction from ~60 raw detections to ~17 consolidated tracks
- Correct identification of most major tracks
- Some remaining duplicates requiring fine parameter tuning
- Beautiful HTML output with professional formatting
- JSON structure for programmatic access
- CUE files for direct import into DJ software
- Rich metadata from Discogs integration

## Contributions

Contributions are welcome. Please open an issue to discuss major changes before submitting a pull request.

## License

MIT 