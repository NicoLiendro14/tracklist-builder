# DJ Set Track Identifier

A Python script that automatically generates tracklists from DJ sets on YouTube using Shazam audio recognition.

## Description

This tool allows you to:
- Download a set from YouTube using yt-dlp
- Split the audio into configurable duration segments (chunks)
- Analyze each segment using the Shazam API
- Consolidate the results into a clean and accurate tracklist
- Export the results in multiple formats (TXT, JSON, HTML, CUE)

Ideal for DJs, music enthusiasts, and content creators who want to identify songs in long sets without having to manually recognize each track.

## Requirements

```
python >= 3.8
yt-dlp
pydub
ffmpeg
shazamio
```

## Installation

```bash
pip install yt-dlp pydub shazamio
# Install ffmpeg according to your operating system
```

## Usage

```bash
# Basic usage
python main.py [YOUTUBE_URL]

# Advanced usage with options
python main.py [YOUTUBE_URL] --chunk-duration 30 --output-dir my_tracklists --formats txt,json,html,cue
```

### Command line arguments

- `url`: YouTube URL of the DJ set to analyze
- `--chunk-duration`: Duration of audio chunks in seconds (default: 30)
- `--output-dir`: Directory to save output files (default: 'output')
- `--formats`: Comma-separated list of output formats (default: txt,json,html,cue)

## Export Formats

The tool can export tracklists in multiple formats:

- **TXT**: Simple text format with track numbers, timestamps, titles, and artists.
- **JSON**: Structured data format with metadata for integration with other applications.
- **HTML**: Visual presentation similar to 1001Tracklist with a modern, responsive design.
- **CUE**: Standard format for DJ software and media players with precise timestamps.

## Implemented Features

- **Intelligent Result Consolidation**: Uses a text similarity-based algorithm (difflib) to correctly group fragmented identifications of the same track. Allows brief interruptions and compares both title and artist with custom weighting.

- **Minimum Duration Filtering**: Automatically discards tracks identified with duration less than a configurable threshold (currently 60 seconds), eliminating false positives and partial detections.

- **Multiple Export Formats**: Exports tracklists in various formats (TXT, JSON, HTML, CUE) for different use cases and applications.

- **Robust Error Handling**: Implements exponential backoff with jitter to handle API rate limits and network issues.

## Planned Improvements (TODO)

### Short-Term Improvements
- [ ] **Similarity Threshold Adjustment**: Reduce the threshold (currently 0.85) to improve consolidation of tracks with variations in names
- [ ] **Max Interruption Adjustment**: Expand tolerance for gaps between detections of the same track
- [x] **Improved Output Format**: Implement format similar to 1001Tracklist with numbering
- [ ] **Chunk Duration Adjustment**: Experiment with different values (15, 20, 30 seconds) to optimize accuracy
- [ ] **Audio Preprocessing**: Normalize volume and equalization to improve recognition rates
- [ ] **Metadata Correction**: Unify artist/track names with small variations

### Intermediate Improvements
- [ ] **Confidence Scoring System**: Implement logic to value consistent identifications
- [ ] **Enriched Metadata**: Integrate with additional APIs for information such as year, genre, and BPM
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

## Contributions

Contributions are welcome. Please open an issue to discuss major changes before submitting a pull request.

## License

MIT 