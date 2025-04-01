import os
import asyncio
import traceback
import yt_dlp
import logging
import time
import random
import difflib
from pydub import AudioSegment
from shazamio import Shazam
from aiohttp import ClientError, ContentTypeError

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
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
        delay = min(self.initial_delay * (2 ** self.retry_count), self.max_delay)
        
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
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': 'downloaded_audio.%(ext)s',
        'quiet': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info("Extrayendo información del video...")
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            base, ext = os.path.splitext(filename)
            final_filename = f"{base}.mp3"
            logger.info(f"Audio descargado exitosamente: {final_filename}")
            return final_filename
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
            chunk = audio[i:i + chunk_ms]
            chunk_name = f"chunk_{i//1000:04d}.mp3"
            chunk.export(chunk_name, format="mp3")
            chunks.append(chunk_name)
            logger.debug(f"Chunk creado: {chunk_name}")
        
        logger.info(f"División de audio completada. {len(chunks)} chunks creados")
        return chunks
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
        if result and 'track' in result:
            logger.info(f"Canción identificada en {chunk_path}: {result['track']['title']} - {result['track']['subtitle']}")
            backoff.reset()  # Resetear el backoff si la solicitud fue exitosa
        else:
            logger.warning(f"No se pudo identificar la canción en {chunk_path}")
        return result
    except (ClientError, ContentTypeError) as e:
        next_delay = backoff.get_next_delay()
        if next_delay is not None:
            logger.warning(f"Error de conexión en {chunk_path}. Reintentando en {next_delay:.1f} segundos... (Intento {backoff.retry_count}/{backoff.max_retries})")
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
    return f"{mins:02d}:{secs:02d}"

def are_tracks_similar(track1, track2, similarity_threshold=0.85):
    if not track1 or not track2:
        return False
    
    title_similarity = difflib.SequenceMatcher(None, track1['title'].lower(), track2['title'].lower()).ratio()
    artist_similarity = difflib.SequenceMatcher(None, track1['artist'].lower(), track2['artist'].lower()).ratio()
    
    combined_similarity = (title_similarity * 0.7) + (artist_similarity * 0.3)
    return combined_similarity >= similarity_threshold

def compile_tracklist(results, chunk_duration, min_duration_seconds=60, max_interruption_chunks=2):
    logger.info("Iniciando compilación de tracklist mejorada")
    raw_tracks = []
    
    for i, result in enumerate(results):
        track = None
        if result and 'track' in result and 'title' in result['track']:
            track = {
                'title': result['track']['title'],
                'artist': result['track']['subtitle'],
                'chunk_index': i,
                'timestamp': i * chunk_duration
            }
            raw_tracks.append(track)
    
    consolidated_tracks = []
    current_group = []
    
    for track in raw_tracks:
        if not current_group:
            current_group.append(track)
            continue
        
        last_track = current_group[-1]
        chunks_between = track['chunk_index'] - last_track['chunk_index'] - 1
        
        if chunks_between <= max_interruption_chunks and are_tracks_similar(track, current_group[0]):
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
            
        start_time = group[0]['timestamp']
        end_time = group[-1]['timestamp'] + chunk_duration
        duration = end_time - start_time
        
        if duration >= min_duration_seconds:
            representative_track = group[0]
            final_tracklist.append({
                'start': start_time,
                'end': end_time,
                'duration': duration,
                'track': {
                    'title': representative_track['title'],
                    'artist': representative_track['artist']
                }
            })
    
    logger.info(f"Tracklist consolidada: {len(final_tracklist)} tracks (filtradas de {len(consolidated_tracks)} identificaciones)")
    return final_tracklist

async def main(url, chunk_duration=30):
    logger.info("Iniciando proceso principal")
    try:
        # Descargar audio
        audio_path = await asyncio.to_thread(download_audio, url)
        
        # Dividir en chunks
        chunks = split_audio(audio_path, chunk_duration)
        
        # Procesar reconocimiento
        logger.info("Iniciando reconocimiento de canciones con Shazam")
        shazam = Shazam()
        
        # Procesar chunks en grupos más pequeños para evitar sobrecarga
        chunk_size = 3  # Reducido a 3 para ser más conservador
        results = []
        for i in range(0, len(chunks), chunk_size):
            chunk_group = chunks[i:i + chunk_size]
            logger.info(f"Procesando grupo de chunks {i//chunk_size + 1}/{(len(chunks) + chunk_size - 1)//chunk_size}")
            tasks = [recognize_chunk(shazam, chunk) for chunk in chunk_group]
            group_results = await asyncio.gather(*tasks)
            results.extend(group_results)
            
            # Pausa entre grupos con jitter
            if i + chunk_size < len(chunks):
                delay = 2 + random.uniform(0, 2)  # Delay entre 2-4 segundos
                await asyncio.sleep(delay)
        
        # Generar tracklist
        tracklist = compile_tracklist(results, chunk_duration)
        
        # Mostrar resultados
        logger.info("\nTracklist identificado:")
        for entry in tracklist:
            start = format_time(entry['start'])
            duration = format_time(entry['duration'])
            logger.info(f"{start} ({duration}) - {entry['track']['title']} by {entry['track']['artist']}")
        
        # Limpieza
        logger.info("Iniciando limpieza de archivos temporales")
        os.remove(audio_path)
        for chunk in chunks:
            os.remove(chunk)
        logger.info("Limpieza completada")
        
    except Exception as e:
        logger.error(f"Error en el proceso principal: {str(e)}")
        raise

if __name__ == "__main__":
    """     import sys
    if len(sys.argv) != 2:
        logger.error("Uso incorrecto del script")
        print("Uso: python script.py <URL de YouTube>")
        sys.exit(1)
    
    url = sys.argv[1] """
    url = "https://www.youtube.com/watch?v=iwew9TzWY3M"
    logger.info(f"Script iniciado con URL: {url}")
    asyncio.run(main(url, chunk_duration=30))