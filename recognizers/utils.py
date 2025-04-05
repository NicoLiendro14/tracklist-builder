import os
import yt_dlp
import logging
import difflib
from pydub import AudioSegment
from typing import Tuple, List

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

def download_audio(url: str) -> Tuple[str, str]:
    """
    Descarga el audio de una URL (YouTube, SoundCloud, etc) usando yt-dlp.
    
    Args:
        url: URL del audio/video a descargar
        
    Returns:
        Tuple con (ruta_archivo, título_video)
    """
    logger.info(f"Iniciando descarga de audio desde URL: {url}")
    ydl_opts = {
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "best",
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

def split_audio(audio_path: str, chunk_duration: int = 30) -> Tuple[List[str], int]:
    """
    Divide un archivo de audio en fragmentos de duración especificada.
    
    Args:
        audio_path: Ruta al archivo de audio
        chunk_duration: Duración en segundos de cada fragmento
        
    Returns:
        Tuple con (lista_de_chunks, duración_total_en_segundos)
    """
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
        return chunks, len(audio) // 1000  # Duración total en segundos
    except Exception as e:
        logger.error(f"Error durante la división del audio: {str(e)}")
        raise

def format_time(seconds: int) -> str:
    """
    Formatea segundos en formato de tiempo legible (HH:MM:SS o MM:SS).
    
    Args:
        seconds: Tiempo en segundos
        
    Returns:
        String con el tiempo formateado
    """
    mins, secs = divmod(seconds, 60)
    hours, mins = divmod(mins, 60)
    if hours > 0:
        return f"{hours:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"

def are_tracks_similar(track1: dict, track2: dict, similarity_threshold: float = 0.85) -> bool:
    """
    Compara dos tracks para determinar si son similares basándose en título y artista.
    
    Args:
        track1: Primer track a comparar
        track2: Segundo track a comparar
        similarity_threshold: Umbral de similitud (0-1)
        
    Returns:
        True si los tracks son similares, False en caso contrario
    """
    if not track1 or not track2:
        return False

    # Extraer título y artista según la estructura esperada
    title1 = track1.get("title", "")
    artist1 = track1.get("artist", "")
    
    title2 = track2.get("title", "")
    artist2 = track2.get("artist", "")

    # Si alguno de los campos está vacío, no podemos comparar
    if not title1 or not title2 or not artist1 or not artist2:
        return False

    # Calcular similitud
    title_similarity = difflib.SequenceMatcher(None, title1.lower(), title2.lower()).ratio()
    artist_similarity = difflib.SequenceMatcher(None, artist1.lower(), artist2.lower()).ratio()

    # Ponderación: título tiene más peso que artista
    combined_similarity = (title_similarity * 0.7) + (artist_similarity * 0.3)
    return combined_similarity >= similarity_threshold

class ExponentialBackoff:
    """
    Implementa el algoritmo de retroceso exponencial para reintentos.
    """
    def __init__(self, initial_delay=1, max_delay=60, max_retries=5, jitter=True):
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.jitter = jitter
        self.current_delay = initial_delay
        self.retry_count = 0

    def get_next_delay(self):
        """
        Calcula el próximo tiempo de espera.
        
        Returns:
            Tiempo de espera en segundos, o None si se superó el máximo de reintentos
        """
        if self.retry_count >= self.max_retries:
            return None

        # Calcular el delay exponencial
        delay = min(self.initial_delay * (2**self.retry_count), self.max_delay)

        # Agregar jitter aleatorio (±20%)
        if self.jitter:
            import random
            jitter_amount = delay * 0.2
            delay += random.uniform(-jitter_amount, jitter_amount)

        self.retry_count += 1
        return max(0.1, delay)  # Asegurar que el delay no sea menor a 0.1 segundos

    def reset(self):
        """
        Reinicia el contador de reintentos.
        """
        self.current_delay = self.initial_delay
        self.retry_count = 0 