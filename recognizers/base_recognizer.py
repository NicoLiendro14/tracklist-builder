import os
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple, Optional

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

class BaseRecognizer(ABC):
    """
    Clase base abstracta para todos los reconocedores de tracks.
    Define la interfaz común que todos los reconocedores deben implementar.
    """
    
    def __init__(self, chunk_duration: int = 30):
        """
        Inicializa el reconocedor con la duración de chunk predeterminada.
        
        Args:
            chunk_duration: Duración en segundos de cada fragmento de audio a analizar
        """
        self.chunk_duration = chunk_duration
        self.name = self.__class__.__name__
    
    @abstractmethod
    async def download_audio(self, url: str) -> Tuple[str, str]:
        """
        Descarga el audio de la URL proporcionada.
        
        Args:
            url: URL del audio/video a descargar
            
        Returns:
            Tuple con (ruta_archivo, título_video)
        """
        pass
    
    @abstractmethod
    def split_audio(self, audio_path: str) -> Tuple[List[str], int]:
        """
        Divide el archivo de audio en fragmentos para su análisis.
        
        Args:
            audio_path: Ruta al archivo de audio a dividir
            
        Returns:
            Tuple con (lista_de_chunks, duración_total_en_segundos)
        """
        pass
    
    @abstractmethod
    async def recognize_chunk(self, chunk_path: str) -> Optional[Dict[str, Any]]:
        """
        Reconoce un fragmento de audio utilizando el servicio correspondiente.
        
        Args:
            chunk_path: Ruta al archivo de chunk a reconocer
            
        Returns:
            Diccionario con los datos del reconocimiento o None si no se reconoció
        """
        pass
    
    @abstractmethod
    def process_results(self, results: List[Optional[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        Procesa los resultados de reconocimiento para crear un tracklist.
        
        Args:
            results: Lista de resultados de reconocimiento
            
        Returns:
            Lista de tracks identificados con su información
        """
        pass
    
    def cleanup(self, audio_path: str, chunks: List[str]) -> None:
        """
        Limpia los archivos temporales creados durante el proceso.
        
        Args:
            audio_path: Ruta al archivo de audio original
            chunks: Lista de rutas a los fragmentos de audio
        """
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
                logger.info(f"Removed audio file: {audio_path}")
            
            for chunk in chunks:
                if os.path.exists(chunk):
                    os.remove(chunk)
            logger.info(f"Removed {len(chunks)} chunk files")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
    
    async def identify_tracks(self, url: str) -> List[Dict[str, Any]]:
        """
        Proceso completo de identificación de tracks.
        
        Args:
            url: URL del audio/video a analizar
            
        Returns:
            Lista de tracks identificados con su información
        """
        try:
            logger.info(f"Starting track identification with {self.name}")
            
            # Descargar audio
            audio_path, video_title = await self.download_audio(url)
            logger.info(f"Audio downloaded: {audio_path}")
            
            # Dividir en chunks
            chunks, total_duration = self.split_audio(audio_path)
            logger.info(f"Audio split into {len(chunks)} chunks")
            
            # Reconocer cada chunk
            results = []
            for chunk in chunks:
                result = await self.recognize_chunk(chunk)
                results.append(result)
                
            # Procesar resultados
            tracklist = self.process_results(results)
            
            # Limpiar archivos temporales
            self.cleanup(audio_path, chunks)
            
            return tracklist
            
        except Exception as e:
            logger.error(f"Error in {self.name} track identification: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return [] 