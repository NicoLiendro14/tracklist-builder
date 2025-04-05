import asyncio
import logging
from typing import List, Dict, Any, Tuple, Optional

from shazamio import Shazam
from aiohttp import ClientError, ContentTypeError

from recognizers.base_recognizer import BaseRecognizer
from recognizers.utils import download_audio, split_audio, ExponentialBackoff, are_tracks_similar

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

class ShazamRecognizer(BaseRecognizer):
    """
    Reconocedor de tracks utilizando la API de Shazam.
    """
    
    def __init__(self, chunk_duration: int = 30):
        """
        Inicializa el reconocedor de Shazam.
        
        Args:
            chunk_duration: Duración en segundos de cada fragmento de audio
        """
        super().__init__(chunk_duration)
        self.shazam = Shazam()
    
    async def download_audio(self, url: str) -> Tuple[str, str]:
        """
        Descarga el audio de la URL proporcionada.
        
        Args:
            url: URL del audio/video a descargar
            
        Returns:
            Tuple con (ruta_archivo, título_video)
        """
        return download_audio(url)
    
    def split_audio(self, audio_path: str) -> Tuple[List[str], int]:
        """
        Divide el archivo de audio en fragmentos para su análisis.
        
        Args:
            audio_path: Ruta al archivo de audio a dividir
            
        Returns:
            Tuple con (lista_de_chunks, duración_total_en_segundos)
        """
        return split_audio(audio_path, self.chunk_duration)
    
    async def recognize_chunk(self, chunk_path: str) -> Optional[Dict[str, Any]]:
        """
        Reconoce un fragmento de audio utilizando Shazam.
        
        Args:
            chunk_path: Ruta al archivo de chunk a reconocer
            
        Returns:
            Diccionario con los datos del reconocimiento o None si no se reconoció
        """
        logger.info(f"Iniciando reconocimiento de chunk con Shazam: {chunk_path}")
        backoff = ExponentialBackoff()
        
        try:
            # Esperar un poco para no sobrecargar la API
            await asyncio.sleep(5)
            
            # Realizar el reconocimiento
            result = await self.shazam.recognize(chunk_path)
            
            if not result or "matches" not in result or not result["matches"]:
                logger.warning(f"No se encontraron matches en {chunk_path}")
                return None
            
            if "track" in result:
                logger.info(
                    f"Canción identificada en {chunk_path}: {result['track']['title']} - {result['track']['subtitle']}"
                )
                return result
            else:
                logger.warning(f"No se pudo identificar la canción en {chunk_path}")
                return None
                
        except (ClientError, ContentTypeError) as e:
            next_delay = backoff.get_next_delay()
            if next_delay is not None:
                logger.warning(
                    f"Error de conexión en {chunk_path}. Reintentando en {next_delay:.1f} segundos... (Intento {backoff.retry_count}/{backoff.max_retries})"
                )
                await asyncio.sleep(next_delay)
                return await self.recognize_chunk(chunk_path)
            else:
                logger.error(f"Error máximo de reintentos alcanzado para {chunk_path}")
                logger.error(f"Error: {str(e)}")
                return None
        except Exception as e:
            logger.error(f"Error procesando {chunk_path}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def process_results(self, results: List[Optional[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        Procesa los resultados de reconocimiento para crear un tracklist.
        
        Args:
            results: Lista de resultados de reconocimiento
            
        Returns:
            Lista de tracks identificados con su información
        """
        logger.info("Procesando resultados de Shazam")
        raw_tracks = []
        
        # Extraer información básica de cada resultado
        for i, result in enumerate(results):
            if result and "track" in result and "title" in result["track"]:
                track = {
                    "title": result["track"]["title"],
                    "artist": result["track"]["subtitle"],
                    "timestamp": i * self.chunk_duration,
                    "confidence": 1.0,  # Shazam no proporciona un valor de confianza
                    "recognizer": "shazam"
                }
                raw_tracks.append(track)
        
        # Consolidar tracks (eliminar duplicados consecutivos)
        consolidated_tracks = []
        current_track = None
        
        for track in raw_tracks:
            if not current_track:
                current_track = track
                continue
            
            # Si el track actual es similar al anterior, lo ignoramos
            if are_tracks_similar(current_track, track):
                continue
            else:
                # Si es diferente, guardamos el anterior y actualizamos el actual
                consolidated_tracks.append(current_track)
                current_track = track
        
        # Agregar el último track si existe
        if current_track:
            consolidated_tracks.append(current_track)
        
        # Formatear los timestamps como strings (MM:SS o HH:MM:SS)
        for track in consolidated_tracks:
            seconds = track["timestamp"]
            mins, secs = divmod(seconds, 60)
            hours, mins = divmod(mins, 60)
            if hours > 0:
                track["timestamp"] = f"{hours:02d}:{mins:02d}:{secs:02d}"
            else:
                track["timestamp"] = f"{mins:02d}:{secs:02d}"
        
        logger.info(f"Se procesaron {len(consolidated_tracks)} tracks únicos")
        return consolidated_tracks 