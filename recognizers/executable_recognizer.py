import asyncio
import subprocess
import json
import logging
import os
import tempfile
from typing import List, Dict, Any, Tuple, Optional

from recognizers.base_recognizer import BaseRecognizer
from recognizers.utils import download_audio, split_audio, are_tracks_similar
from pydub import AudioSegment

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

class ExecutableRecognizer(BaseRecognizer):
    """
    Reconocedor de tracks utilizando un ejecutable externo que genera un JSON.
    Especialmente adaptado para manejar el formato de track_finder.exe.
    """
    
    def __init__(self, executable_path: str, chunk_duration: int = 30):
        """
        Inicializa el reconocedor basado en un ejecutable externo.
        
        Args:
            executable_path: Ruta al ejecutable que realiza el reconocimiento
            chunk_duration: Duración en segundos de cada fragmento de audio
        """
        super().__init__(chunk_duration)
        self.executable_path = executable_path
        
        # Verificar que el ejecutable exista
        logger.info(f"Verificando existencia del ejecutable en: {executable_path}")
        
        if not os.path.exists(executable_path):
            logger.error(f"El ejecutable no existe en la ruta: {executable_path}")
            logger.error(f"Directorio actual: {os.getcwd()}")
            
            # Verificar si existe en rutas relativas comunes para ayudar al usuario
            common_paths = [
                os.path.join(os.getcwd(), executable_path),
                os.path.join(os.getcwd(), "recognizers", os.path.basename(executable_path)),
                os.path.join(os.getcwd(), os.path.basename(executable_path))
            ]
            
            # Buscar en rutas alternativas
            found_path = None
            for path in common_paths:
                if os.path.exists(path):
                    logger.info(f"El ejecutable se encontró en: {path}")
                    logger.info(f"Usando esta ruta en lugar de la original")
                    found_path = path
                    break
            
            if found_path:
                # Usar la ruta donde se encontró el ejecutable
                self.executable_path = found_path
                logger.info(f"Se actualizó la ruta del ejecutable a: {self.executable_path}")
            else:
                # No se encontró en ninguna ruta alternativa
                import pdb; pdb.set_trace()
                raise FileNotFoundError(f"El ejecutable no existe en la ruta: {executable_path}")
        else:
            logger.info(f"Ejecutable encontrado correctamente en: {executable_path}")
    
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
    
    def _convert_to_wav(self, mp3_path: str) -> str:
        """
        Convierte un archivo de audio MP3 a formato WAV.
        
        Args:
            mp3_path: Ruta al archivo MP3
            
        Returns:
            Ruta al nuevo archivo WAV
        """
        try:
            # Crear nombre para archivo wav
            wav_path = os.path.splitext(mp3_path)[0] + ".wav"
            
            # Convertir mp3 a wav usando pydub
            audio = AudioSegment.from_file(mp3_path)
            audio.export(wav_path, format="wav")
            
            logger.info(f"Archivo convertido de MP3 a WAV: {wav_path}")
            return wav_path
        except Exception as e:
            logger.error(f"Error al convertir MP3 a WAV: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return mp3_path  # Retornar el archivo original en caso de error
    
    async def recognize_chunk(self, chunk_path: str) -> Optional[Dict[str, Any]]:
        """
        Reconoce un fragmento de audio utilizando el ejecutable externo.
        
        Args:
            chunk_path: Ruta al archivo de chunk a reconocer
            
        Returns:
            Diccionario con los datos del reconocimiento o None si no se reconoció
        """
        logger.info(f"Iniciando reconocimiento con ejecutable para: {chunk_path}")
        logger.info(f"Usando ejecutable: {self.executable_path}")
        
        # Verificar que el ejecutable existe antes de continuar
        if not os.path.exists(self.executable_path):
            logger.error(f"El ejecutable no se encuentra en la ruta especificada: {self.executable_path}")
            return None
        
        # Verificar si es necesario convertir el archivo a WAV
        # track_finder.exe requiere archivos WAV
        file_ext = os.path.splitext(chunk_path)[1].lower()
        input_file = chunk_path
        
        if file_ext != '.wav':
            logger.info(f"Convirtiendo archivo {file_ext} a formato WAV requerido por track_finder.exe")
            input_file = self._convert_to_wav(chunk_path)
        
        try:
            # Crear comando con parámetros para el ejecutable
            # Adaptado para track_finder.exe que usa --search y --json como parámetros
            command = [
                self.executable_path,
                "--search", 
                input_file,
                "--json"
            ]
            
            logger.info(f"Ejecutando comando: {' '.join(command)}")
            
            # Ejecutar el proceso de reconocimiento como una tarea asincrónica
            # para no bloquear el bucle de eventos
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Esperar a que termine el proceso y obtener la salida
            stdout, stderr = await process.communicate()
            
            # Verificar si hubo algún error
            if process.returncode != 0:
                stderr_text = stderr.decode().strip() if stderr else "No stderr output"
                logger.error(f"Error en el ejecutable (código {process.returncode}): {stderr_text}")
                return None
            
            # Intentar parsear la salida como JSON
            try:
                output = stdout.decode().strip()
                # Guardar la salida en un archivo para depuración si es necesario
                with open(f"track_finder_output_{os.path.basename(input_file)}.json", "w") as f:
                    f.write(output)
                    
                logger.info(f"Salida del ejecutable guardada en track_finder_output_{os.path.basename(input_file)}.json")
                
                result = json.loads(output)
                logger.info(f"Reconocimiento exitoso con ejecutable")
                
                # Verificar si el resultado contiene información de track
                if self._validate_result(result):
                    # Transformar el resultado al formato interno estándar
                    return self._transform_result(result)
                else:
                    logger.warning("El resultado no contiene información de track válida o no hizo match")
                    logger.info(f"Resultado recibido: {output[:200]}...")  # Mostrar inicio del resultado
                    return None
                
            except json.JSONDecodeError:
                logger.error("La salida del ejecutable no es un JSON válido")
                logger.error(f"Salida: {stdout.decode().strip()}")
                return None
                
        except Exception as e:
            logger.error(f"Error en el reconocimiento con ejecutable: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
        finally:
            # Limpiar: eliminar el archivo wav si es diferente del chunk original
            if input_file != chunk_path and os.path.exists(input_file):
                try:
                    os.remove(input_file)
                    logger.debug(f"Archivo WAV temporal eliminado: {input_file}")
                except Exception as e:
                    logger.warning(f"No se pudo eliminar el archivo WAV temporal: {str(e)}")
    
    def _validate_result(self, result: Dict[str, Any]) -> bool:
        """
        Valida que el resultado contenga los campos necesarios según el formato de track_finder.exe.
        
        Args:
            result: Resultado del reconocimiento
            
        Returns:
            True si el resultado es válido y contiene match, False en caso contrario
        """
        # Verificamos que el resultado sea exitoso y haya match
        if not result.get("success", False) or not result.get("matched", False):
            return False
        
        # Verificamos que exista la sección 'audio' con la información del track
        if "audio" not in result:
            return False
        
        # Verificamos los campos mínimos necesarios en la sección 'audio'
        audio = result["audio"]
        required_fields = ["title", "artist", "confidence"]
        return all(field in audio for field in required_fields)
    
    def _transform_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transforma el resultado del ejecutable al formato interno utilizado por los reconocedores.
        
        Args:
            result: Resultado del reconocimiento en formato del ejecutable
            
        Returns:
            Resultado transformado al formato interno
        """
        audio = result["audio"]
        
        # Crear un resultado en el formato interno
        transformed_result = {
            "title": audio["title"],
            "artist": audio["artist"],
            "confidence": audio["confidence"],
            "trackId": audio.get("trackId", ""),
            # Podemos agregar más campos que sean útiles
            "mediaType": audio.get("mediaType", ""),
            "trackStartsAt": audio.get("trackStartsAt", 0),
            "trackLength": audio.get("trackLength", 0),
            "recognizer": "executable"
        }
        
        return transformed_result
    
    def process_results(self, results: List[Optional[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        Procesa los resultados de reconocimiento para crear un tracklist.
        
        Args:
            results: Lista de resultados de reconocimiento
            
        Returns:
            Lista de tracks identificados con su información
        """
        logger.info("Procesando resultados del reconocedor ejecutable")
        raw_tracks = []
        
        # Extraer información básica de cada resultado
        for i, result in enumerate(results):
            if result:
                # Los resultados ya están transformados al formato interno
                track = {
                    "title": result["title"],
                    "artist": result["artist"],
                    "timestamp": i * self.chunk_duration,
                    "confidence": result["confidence"],
                    "recognizer": "track_finder"  # Nombre más específico
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