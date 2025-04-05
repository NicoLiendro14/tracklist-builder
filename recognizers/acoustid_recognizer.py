import asyncio
import subprocess
import json
import logging
import requests
from typing import List, Dict, Any, Tuple, Optional

from recognizers.base_recognizer import BaseRecognizer
from recognizers.utils import download_audio, split_audio, are_tracks_similar

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

class AcoustIDRecognizer(BaseRecognizer):
    """
    Reconocedor de tracks utilizando AcoustID.
    """
    
    def __init__(self, client_api_key: str = "YjBc2sAt2S", chunk_duration: int = 60):
        """
        Inicializa el reconocedor de AcoustID.
        
        Args:
            client_api_key: Clave de API para AcoustID
            chunk_duration: Duración en segundos de cada fragmento de audio
        """
        super().__init__(chunk_duration)
        self.client_api_key = client_api_key
    
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
    
    def generate_fingerprint(self, audio_path: str) -> Tuple[int, str]:
        """
        Genera la huella digital de un archivo de audio utilizando fpcalc.
        
        Args:
            audio_path: Ruta al archivo de audio a analizar
            
        Returns:
            Tuple con (duración, huella_digital)
        """
        logger.info(f"Generando huella digital para {audio_path}")
        try:
            result = subprocess.run(
                ['fpcalc', '-json', audio_path],
                capture_output=True,
                text=True,
                check=True
            )
            
            data = json.loads(result.stdout)
            logger.info(f"Huella digital generada exitosamente")
            return data['duration'], data['fingerprint']
        
        except subprocess.CalledProcessError as e:
            raise Exception(f"Error en fpcalc: {e.stderr}")
        except Exception as e:
            raise Exception(f"Error procesando archivo: {str(e)}")
    
    def acoustid_lookup(self, fingerprint: str, duration: int) -> Dict[str, Any]:
        """
        Consulta la API de AcoustID con la huella digital generada.
        
        Args:
            fingerprint: Huella digital del audio
            duration: Duración del audio en segundos
            
        Returns:
            Resultado de la consulta a AcoustID
        """
        params = {
            "client": self.client_api_key,
            "duration": str(int(float(duration))),
            "fingerprint": fingerprint,
            "meta": "recordings"
        }
        logger.info(f"Consultando datos en AcoustID...")
        
        try:
            response = requests.get(
                "https://api.acoustid.org/v2/lookup",
                params=params
            )
            
            if response.status_code == 200:
                logger.info(f"Datos recibidos de AcoustID")
                return response.json()
            else:
                logger.error(f"Error obteniendo datos de AcoustID: {response.status_code}")
                logger.debug(f"Respuesta: {response.text}")
                return {"status": "error", "error": f"HTTP {response.status_code}"}
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error en la petición HTTP: {str(e)}")
    
    def process_acoustid_results(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Procesa los resultados de AcoustID para extraer la información relevante.
        
        Args:
            data: Datos devueltos por AcoustID
            
        Returns:
            Información procesada del track o None si no hay resultados
        """
        logger.info(f"Procesando resultados de AcoustID")
        
        if data.get("status") != "ok" or not data.get("results"):
            return None
        
        # Obtener el resultado con mayor score
        best_result = max(data["results"], key=lambda x: x.get("score", 0))
        
        if not best_result.get("recordings"):
            return {
                "acoustid": best_result.get("id"),
                "score": best_result.get("score"),
                "title": "Unknown",
                "artist": "Unknown",
                "message": "ID found but no associated metadata"
            }
        
        # Obtener la grabación con mayor puntuación
        recording = best_result["recordings"][0]
        
        # Extraer artistas si están disponibles
        artists = [artist["name"] for artist in recording.get("artists", [])]
        artist_string = ", ".join(artists) if artists else "Unknown Artist"
        
        return {
            "acoustid": best_result.get("id"),
            "score": best_result.get("score"),
            "title": recording.get("title", "Unknown Title"),
            "artist": artist_string,
            "recognizer": "acoustid"
        }
    
    async def recognize_chunk(self, chunk_path: str) -> Optional[Dict[str, Any]]:
        """
        Reconoce un fragmento de audio utilizando AcoustID.
        
        Args:
            chunk_path: Ruta al archivo de chunk a reconocer
            
        Returns:
            Diccionario con los datos del reconocimiento o None si no se reconoció
        """
        try:
            # Generar huella digital
            duration, fingerprint = self.generate_fingerprint(chunk_path)
            
            # Esperar antes de hacer la petición para no sobrecargar la API
            logger.info("Esperando 4 segundos antes de consultar AcoustID...")
            await asyncio.sleep(4)
            
            # Consultar AcoustID
            result = self.acoustid_lookup(fingerprint, duration)
            
            # Procesar resultados
            processed_result = self.process_acoustid_results(result)
            
            if processed_result:
                logger.info(f"Track identificado: {processed_result.get('title', 'Unknown')} - {processed_result.get('artist', 'Unknown')}")
            else:
                logger.warning(f"No se pudo identificar el track en {chunk_path}")
            
            return processed_result
        except Exception as e:
            logger.error(f"Error en el reconocimiento con AcoustID: {str(e)}")
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
        logger.info("Procesando resultados de AcoustID")
        raw_tracks = []
        
        # Extraer información básica de cada resultado
        for i, result in enumerate(results):
            if result and "title" in result and "artist" in result:
                # Calcular el tiempo en segundos
                timestamp = i * self.chunk_duration
                
                # Calcular confianza (score si está presente, o 0.5 por defecto)
                confidence = float(result.get("score", 0.5))
                
                track = {
                    "title": result["title"],
                    "artist": result["artist"],
                    "timestamp": timestamp,
                    "confidence": confidence,
                    "recognizer": "acoustid"
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
                # Actualizar la confianza si la nueva es mayor
                if track["confidence"] > current_track["confidence"]:
                    current_track["confidence"] = track["confidence"]
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