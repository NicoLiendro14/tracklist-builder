import os
import asyncio
import traceback
import yt_dlp
import logging
import time
import random
import difflib
import json
import argparse
from pathlib import Path
from datetime import timedelta
from pydub import AudioSegment
from shazamio import Shazam
from aiohttp import ClientError, ContentTypeError

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class ExponentialBackoff:
    def __init__(self, initial_delay=1, max_delay=60, max_retries=5, jitter=True):
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.jitter = jitter
        self.current_delay = initial_delay
        self.retry_count = 0

    def get_next_delay(self):
        if self.retry_count >= self.max_retries:
            return None

        # Calcular el delay exponencial
        delay = min(self.initial_delay * (2**self.retry_count), self.max_delay)

        # Agregar jitter aleatorio (±20%)
        if self.jitter:
            jitter_amount = delay * 0.2
            delay += random.uniform(-jitter_amount, jitter_amount)

        self.retry_count += 1
        return max(0.1, delay)  # Asegurar que el delay no sea menor a 0.1 segundos

    def reset(self):
        self.current_delay = self.initial_delay
        self.retry_count = 0


def download_audio(url):
    logger.info(f"Iniciando descarga de audio desde URL: {url}")
    ydl_opts = {
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "outtmpl": "downloaded_audio.%(ext)s",
        "quiet": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info("Extrayendo información del video...")
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            base, ext = os.path.splitext(filename)
            final_filename = f"{base}.mp3"
            logger.info(f"Audio descargado exitosamente: {final_filename}")
            return final_filename, info.get("title", "Unknown")
    except Exception as e:
        logger.error(f"Error durante la descarga del audio: {str(e)}")
        raise


def split_audio(audio_path, chunk_duration=30):
    logger.info(f"Iniciando división del audio en chunks de {chunk_duration} segundos")
    try:
        audio = AudioSegment.from_file(audio_path)
        chunk_ms = chunk_duration * 1000
        chunks = []

        total_chunks = len(audio) // chunk_ms + (1 if len(audio) % chunk_ms else 0)
        logger.info(f"Total de chunks a crear: {total_chunks}")

        for i in range(0, len(audio), chunk_ms):
            chunk = audio[i : i + chunk_ms]
            chunk_name = f"chunk_{i//1000:04d}.mp3"
            chunk.export(chunk_name, format="mp3")
            chunks.append(chunk_name)
            logger.debug(f"Chunk creado: {chunk_name}")

        logger.info(f"División de audio completada. {len(chunks)} chunks creados")
        return chunks, len(audio) // 1000  # Return chunks and total duration in seconds
    except Exception as e:
        logger.error(f"Error durante la división del audio: {str(e)}")
        raise


async def recognize_chunk(shazam, chunk_path, backoff=None):
    logger.info(f"Iniciando reconocimiento de chunk: {chunk_path}")
    if backoff is None:
        logger.info("Creando nuevo backoff")
        backoff = ExponentialBackoff()

    try:
        logger.info("Esperando 5 segundos")
        await asyncio.sleep(5)
        logger.info("Reconociendo chunk")
        result = await shazam.recognize(chunk_path)
        logger.info("Reconocimiento completado")

        if not result or "matches" not in result or not result["matches"]:
            logger.warning(f"No se encontraron matches en {chunk_path}")
            return None

        if result and "track" in result:
            logger.info(
                f"Canción identificada en {chunk_path}: {result['track']['title']} - {result['track']['subtitle']}"
            )
            backoff.reset()
        else:
            logger.warning(f"No se pudo identificar la canción en {chunk_path}")
            logger.info(f"Result: {result}")
        return result
    except (ClientError, ContentTypeError) as e:
        next_delay = backoff.get_next_delay()
        if next_delay is not None:
            logger.warning(
                f"Error de conexión en {chunk_path}. Reintentando en {next_delay:.1f} segundos... (Intento {backoff.retry_count}/{backoff.max_retries})"
            )
            await asyncio.sleep(next_delay)
            return await recognize_chunk(shazam, chunk_path, backoff)
        else:
            logger.error(f"Error máximo de reintentos alcanzado para {chunk_path}")
            logger.error(f"Error: {str(e)}")
            logger.error(traceback.format_exc())
            return None
    except Exception as e:
        logger.error(f"Error procesando {chunk_path}: {str(e)}")
        logger.error(traceback.format_exc())
        return None


def format_time(seconds):
    mins, secs = divmod(seconds, 60)
    hours, mins = divmod(mins, 60)
    if hours > 0:
        return f"{hours:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


def are_tracks_similar(track1, track2, similarity_threshold=0.85):
    if not track1 or not track2:
        return False

    title_similarity = difflib.SequenceMatcher(
        None, track1["title"].lower(), track2["title"].lower()
    ).ratio()
    artist_similarity = difflib.SequenceMatcher(
        None, track1["artist"].lower(), track2["artist"].lower()
    ).ratio()

    combined_similarity = (title_similarity * 0.7) + (artist_similarity * 0.3)
    return combined_similarity >= similarity_threshold


def compile_tracklist(
    results, chunk_duration, min_duration_seconds=60, max_interruption_chunks=2
):
    logger.info("Iniciando compilación de tracklist mejorada")
    raw_tracks = []

    for i, result in enumerate(results):
        track = None
        if result and "track" in result and "title" in result["track"]:
            track = {
                "title": result["track"]["title"],
                "artist": result["track"]["subtitle"],
                "chunk_index": i,
                "timestamp": i * chunk_duration,
            }
            raw_tracks.append(track)

    consolidated_tracks = []
    current_group = []

    for track in raw_tracks:
        if not current_group:
            current_group.append(track)
            continue

        last_track = current_group[-1]
        chunks_between = track["chunk_index"] - last_track["chunk_index"] - 1

        if chunks_between <= max_interruption_chunks and are_tracks_similar(
            track, current_group[0]
        ):
            current_group.append(track)
        else:
            if current_group:
                consolidated_tracks.append(current_group)
            current_group = [track]

    if current_group:
        consolidated_tracks.append(current_group)

    final_tracklist = []

    for group in consolidated_tracks:
        if len(group) == 0:
            continue

        start_time = group[0]["timestamp"]
        end_time = group[-1]["timestamp"] + chunk_duration
        duration = end_time - start_time

        if duration >= min_duration_seconds:
            representative_track = group[0]
            final_tracklist.append(
                {
                    "start": start_time,
                    "end": end_time,
                    "duration": duration,
                    "track": {
                        "title": representative_track["title"],
                        "artist": representative_track["artist"],
                    },
                }
            )

    logger.info(
        f"Tracklist consolidada: {len(final_tracklist)} tracks (filtradas de {len(consolidated_tracks)} identificaciones)"
    )
    return final_tracklist


def export_tracklist_to_console(tracklist):
    """Display tracklist in the console with nice formatting"""
    logger.info("\nTracklist identificado:")

    for i, entry in enumerate(tracklist, 1):
        start = format_time(entry["start"])
        duration = format_time(entry["duration"])
        logger.info(
            f"{i:02d}. [{start}] ({duration}) - {entry['track']['title']} by {entry['track']['artist']}"
        )


def export_tracklist_to_text(tracklist, output_file, video_title=None):
    """Export tracklist to a text file"""
    with open(output_file, "w", encoding="utf-8") as f:
        if video_title:
            f.write(f"# Tracklist for: {video_title}\n\n")

        for i, entry in enumerate(tracklist, 1):
            start = format_time(entry["start"])
            f.write(
                f"{i:02d}. [{start}] {entry['track']['title']} - {entry['track']['artist']}\n"
            )

    logger.info(f"Tracklist exportado a archivo de texto: {output_file}")


def export_tracklist_to_json(tracklist, output_file, video_info=None):
    """Export tracklist to a JSON file"""
    output_data = {
        "tracks": [],
        "metadata": {
            "track_count": len(tracklist),
            "source": video_info if video_info else "Unknown source",
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
    }

    for i, entry in enumerate(tracklist, 1):
        output_data["tracks"].append(
            {
                "number": i,
                "start_time": entry["start"],
                "start_time_formatted": format_time(entry["start"]),
                "duration": entry["duration"],
                "duration_formatted": format_time(entry["duration"]),
                "title": entry["track"]["title"],
                "artist": entry["track"]["artist"],
            }
        )

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Tracklist exportado a archivo JSON: {output_file}")


def export_tracklist_to_cue(
    tracklist, output_file, audio_file_path=None, video_title=None
):
    """Export tracklist to a CUE file format for DJ software and audio players"""
    audio_file = (
        os.path.basename(audio_file_path) if audio_file_path else "AUDIOFILE.mp3"
    )
    performer = "Various Artists"
    title = video_title if video_title else "DJ Mix"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f'PERFORMER "{performer}"\n')
        f.write(f'TITLE "{title}"\n')
        f.write(f'FILE "{audio_file}" MP3\n')

        for i, entry in enumerate(tracklist, 1):
            start_time = str(timedelta(seconds=entry["start"])).replace(":", ":")
            # Ensure format is MM:SS:FF (frames)
            if "." in start_time:
                start_time = start_time.split(".")[0]
            if start_time.count(":") == 1:
                start_time = "00:" + start_time
            start_time += ":00"  # Add frames (always 00 for our resolution)

            f.write(f"  TRACK {i:02d} AUDIO\n")
            f.write(f'    TITLE "{entry["track"]["title"]}"\n')
            f.write(f'    PERFORMER "{entry["track"]["artist"]}"\n')
            f.write(f"    INDEX 01 {start_time}\n")

    logger.info(f"Tracklist exportado a archivo CUE: {output_file}")


def export_tracklist_to_html(tracklist, output_file, video_title=None, video_url=None):
    """Export tracklist to a HTML file with 1001Tracklists-like formatting"""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>DJ Set Tracklist</title>
        <style>
            body {
                font-family: 'Arial', sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
                color: #333;
            }
            h1 {
                color: #222;
                border-bottom: 2px solid #ddd;
                padding-bottom: 10px;
            }
            .track-container {
                margin-bottom: 15px;
                background: white;
                border-radius: 5px;
                padding: 15px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                display: flex;
                align-items: center;
            }
            .track-number {
                font-size: 18px;
                font-weight: bold;
                color: #555;
                margin-right: 15px;
                min-width: 30px;
            }
            .track-time {
                color: #777;
                margin-right: 15px;
                min-width: 60px;
            }
            .track-info {
                flex-grow: 1;
            }
            .track-title {
                font-weight: bold;
                margin-bottom: 5px;
                color: #222;
            }
            .track-artist {
                color: #555;
            }
            .track-duration {
                color: #888;
                font-size: 0.9em;
            }
            .footer {
                margin-top: 30px;
                text-align: center;
                font-size: 0.8em;
                color: #888;
            }
            .source-link {
                margin-top: 10px;
                text-align: center;
            }
            a {
                color: #0066cc;
                text-decoration: none;
            }
            a:hover {
                text-decoration: underline;
            }
        </style>
    </head>
    <body>
    """

    # Add title
    if video_title:
        html_content += f"<h1>Tracklist: {video_title}</h1>\n"
    else:
        html_content += "<h1>DJ Set Tracklist</h1>\n"

    # Add source link if available
    if video_url:
        html_content += f'<div class="source-link">Source: <a href="{video_url}" target="_blank">{video_url}</a></div>\n'

    # Add tracks
    for i, entry in enumerate(tracklist, 1):
        start_time = format_time(entry["start"])
        duration = format_time(entry["duration"])
        title = entry["track"]["title"]
        artist = entry["track"]["artist"]

        html_content += f"""
        <div class="track-container">
            <div class="track-number">{i:02d}</div>
            <div class="track-time">{start_time}</div>
            <div class="track-info">
                <div class="track-title">{title}</div>
                <div class="track-artist">{artist}</div>
                <div class="track-duration">Duration: {duration}</div>
            </div>
        </div>
        """

    # Add footer
    html_content += f"""
    <div class="footer">
        <p>Generated on {time.strftime('%Y-%m-%d %H:%M:%S')} by DJ Set Track Identifier</p>
    </div>
    </body>
    </html>
    """

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    logger.info(f"Tracklist exportado a archivo HTML: {output_file}")


def export_tracklist(
    tracklist,
    output_formats=None,
    base_filename=None,
    video_title=None,
    video_url=None,
    audio_file_path=None,
):
    """Export tracklist to specified formats"""
    if output_formats is None:
        output_formats = ["console"]

    if base_filename is None:
        base_filename = f"tracklist_{int(time.time())}"

    # Always display to console
    export_tracklist_to_console(tracklist)

    if "txt" in output_formats:
        output_file = f"{base_filename}.txt"
        export_tracklist_to_text(tracklist, output_file, video_title)

    if "json" in output_formats:
        output_file = f"{base_filename}.json"
        export_tracklist_to_json(tracklist, output_file, video_title)

    if "cue" in output_formats:
        output_file = f"{base_filename}.cue"
        export_tracklist_to_cue(tracklist, output_file, audio_file_path, video_title)

    if "html" in output_formats:
        output_file = f"{base_filename}.html"
        export_tracklist_to_html(tracklist, output_file, video_title, video_url)


async def main(url, chunk_duration=30, output_formats=None, output_dir=None):
    logger.info("Iniciando proceso principal")

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    base_filename = f"tracklist_{int(time.time())}"
    if output_dir:
        base_filename = os.path.join(output_dir, base_filename)

    try:
        # Descargar audio
        audio_path, video_title = await asyncio.to_thread(download_audio, url)

        # Dividir en chunks
        chunks, total_duration = split_audio(audio_path, chunk_duration)

        # Procesar reconocimiento
        logger.info("Iniciando reconocimiento de canciones con Shazam")
        shazam = Shazam()

        # Procesar chunks en grupos más pequeños para evitar sobrecarga
        chunk_size = 3
        results = []
        for i in range(0, len(chunks), chunk_size):
            chunk_group = chunks[i : i + chunk_size]
            logger.info(
                f"Procesando grupo de chunks {i//chunk_size + 1}/{(len(chunks) + chunk_size - 1)//chunk_size}"
            )
            tasks = [recognize_chunk(shazam, chunk) for chunk in chunk_group]
            group_results = await asyncio.gather(*tasks)
            results.extend(group_results)

            # Pausa entre grupos con jitter
            if i + chunk_size < len(chunks):
                delay = 2 + random.uniform(0, 2)
                await asyncio.sleep(delay)

        # Generar tracklist
        tracklist = compile_tracklist(results, chunk_duration)

        # Exportar resultado
        export_tracklist(
            tracklist,
            output_formats=output_formats,
            base_filename=base_filename,
            video_title=video_title,
            video_url=url,
            audio_file_path=audio_path,
        )

        # Limpieza
        logger.info("Iniciando limpieza de archivos temporales")
        os.remove(audio_path)
        for chunk in chunks:
            os.remove(chunk)
        logger.info("Limpieza completada")

    except Exception as e:
        logger.error(f"Error en el proceso principal: {str(e)}")
        raise


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="DJ Set Track Identifier - Identify tracks in a DJ mix video"
    )
    parser.add_argument("url", help="YouTube URL of the DJ set to analyze")
    parser.add_argument(
        "--chunk-duration",
        type=int,
        default=30,
        help="Duration of audio chunks in seconds (default: 30)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Directory to save output files (default: 'output')",
    )
    parser.add_argument(
        "--formats",
        type=str,
        default="txt,json,html,cue",
        help="Comma-separated list of output formats (options: txt,json,html,cue) (default: txt,json,html,cue)",
    )

    args = parser.parse_args()

    # Convert formats to list
    formats = [fmt.strip() for fmt in args.formats.split(",")]
    valid_formats = ["txt", "json", "html", "cue"]
    formats = [fmt for fmt in formats if fmt in valid_formats]

    # Add console output by default
    formats.append("console")

    return args.url, args.chunk_duration, formats, args.output_dir


if __name__ == "__main__":
    try:
        url, chunk_duration, output_formats, output_dir = parse_arguments()
        logger.info(f"Script iniciado con URL: {url}")
        logger.info(f"Formatos de salida: {output_formats}")
        asyncio.run(main(url, chunk_duration, output_formats, output_dir))
    except KeyboardInterrupt:
        logger.info("Proceso interrumpido por el usuario")
    except Exception as e:
        logger.error(f"Error en la ejecución del script: {str(e)}")
        logger.error(traceback.format_exc())
