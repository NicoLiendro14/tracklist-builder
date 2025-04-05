import asyncio
import logging
from typing import List, Dict, Any, Optional, Union, Tuple
import uuid
import os
from datetime import datetime

from recognizers.base_recognizer import BaseRecognizer
from recognizers.factory import RecognizerFactory

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

class TrackRecognitionManager:
    """
    Gestor principal para el reconocimiento de tracks.
    Permite usar múltiples reconocedores y combinar sus resultados.
    """
    
    def __init__(self, output_dir: str = "output"):
        """
        Inicializa el gestor de reconocimiento.
        
        Args:
            output_dir: Directorio donde se guardarán los resultados
        """
        self.output_dir = output_dir
        self._ensure_output_dir()
    
    def _ensure_output_dir(self) -> None:
        """
        Asegura que exista el directorio de salida.
        """
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            logger.info(f"Directorio de salida creado: {self.output_dir}")
    
    async def identify_tracks(
        self, 
        url: str, 
        recognizer_types: Union[str, List[str]] = "shazam",
        recognizer_params: Dict[str, Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Identifica tracks en una URL utilizando uno o varios reconocedores.
        
        Args:
            url: URL del audio/video a analizar
            recognizer_types: Tipo o lista de tipos de reconocedores a utilizar
            recognizer_params: Parámetros específicos para cada reconocedor
            
        Returns:
            Diccionario con resultados del reconocimiento
        """
        # Normalizar la entrada
        if isinstance(recognizer_types, str):
            recognizer_types = [recognizer_types]
        
        if recognizer_params is None:
            recognizer_params = {}
        
        # Generar ID único para esta sesión
        session_id = str(uuid.uuid4())
        logger.info(f"Iniciando sesión de reconocimiento: {session_id}")
        
        # Resultados para cada reconocedor
        all_results = {}
        combined_results = []
        errors = []
        
        # Crear y ejecutar cada reconocedor
        for recognizer_type in recognizer_types:
            try:
                # Obtener parámetros específicos para este reconocedor
                params = recognizer_params.get(recognizer_type, {})
                
                # Crear reconocedor
                recognizer = RecognizerFactory.get_recognizer(recognizer_type, **params)
                
                if not recognizer:
                    errors.append(f"No se pudo crear el reconocedor '{recognizer_type}'")
                    continue
                
                # Ejecutar reconocimiento
                logger.info(f"Iniciando reconocimiento con {recognizer_type}")
                tracks = await recognizer.identify_tracks(url)
                
                # Guardar resultados
                all_results[recognizer_type] = tracks
                
                # Agregar a los resultados combinados
                for track in tracks:
                    # Asegurarnos de que el track tiene el campo de reconocedor
                    if "recognizer" not in track:
                        track["recognizer"] = recognizer_type
                    combined_results.append(track)
                
                logger.info(f"Reconocimiento con {recognizer_type} completado: {len(tracks)} tracks encontrados")
                
            except Exception as e:
                error_msg = f"Error en el reconocedor '{recognizer_type}': {str(e)}"
                logger.error(error_msg)
                import traceback
                logger.error(traceback.format_exc())
                errors.append(error_msg)
        
        # Ordenar resultados combinados por timestamp
        combined_results = self._sort_and_deduplicate_tracks(combined_results)
        
        # Crear resultado final
        result = {
            "id": session_id,
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "recognizers_used": recognizer_types,
            "individual_results": all_results,
            "combined_results": combined_results,
            "errors": errors,
            "total_tracks": len(combined_results)
        }
        
        # Guardar resultados
        self._save_results(result, session_id)
        
        return result
    
    def _sort_and_deduplicate_tracks(self, tracks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Ordena y elimina duplicados de la lista de tracks.
        
        Args:
            tracks: Lista de tracks a procesar
            
        Returns:
            Lista de tracks ordenada y sin duplicados
        """
        if not tracks:
            return []
        
        # Primero convertimos los timestamps a segundos para poder ordenar
        for track in tracks:
            if isinstance(track["timestamp"], str):
                parts = track["timestamp"].split(":")
                if len(parts) == 2:  # MM:SS
                    mins, secs = parts
                    track["_timestamp_seconds"] = int(mins) * 60 + int(secs)
                elif len(parts) == 3:  # HH:MM:SS
                    hours, mins, secs = parts
                    track["_timestamp_seconds"] = int(hours) * 3600 + int(mins) * 60 + int(secs)
                else:
                    track["_timestamp_seconds"] = 0
            else:
                track["_timestamp_seconds"] = track["timestamp"]
        
        # Ordenar por tiempo
        sorted_tracks = sorted(tracks, key=lambda x: x["_timestamp_seconds"])
        
        # Eliminar duplicados cercanos (mismo título y artista en timestamps cercanos)
        deduped_tracks = []
        window_size = 30  # segundos de ventana para considerar duplicados
        
        for track in sorted_tracks:
            # Si la lista está vacía, agregamos el primer track
            if not deduped_tracks:
                deduped_tracks.append(track)
                continue
            
            # Verificar si el track es similar a alguno reciente dentro de la ventana
            last_track = deduped_tracks[-1]
            time_diff = abs(track["_timestamp_seconds"] - last_track["_timestamp_seconds"])
            
            # Si el tiempo es cercano y el título/artista son similares, actualizamos la confianza
            from recognizers.utils import are_tracks_similar
            if time_diff <= window_size and are_tracks_similar(track, last_track):
                # Si el nuevo track tiene mayor confianza, actualizamos la información
                if track.get("confidence", 0) > last_track.get("confidence", 0):
                    # Actualizamos la información pero mantenemos el timestamp original
                    for key in ["title", "artist", "confidence", "recognizer"]:
                        if key in track:
                            last_track[key] = track[key]
            else:
                # Si no es similar o está fuera de la ventana, lo agregamos como nuevo track
                deduped_tracks.append(track)
        
        # Eliminar el campo temporal de segundos
        for track in deduped_tracks:
            if "_timestamp_seconds" in track:
                del track["_timestamp_seconds"]
        
        return deduped_tracks
    
    def _save_results(self, result: Dict[str, Any], session_id: str) -> None:
        """
        Guarda los resultados en un archivo JSON.
        
        Args:
            result: Resultados a guardar
            session_id: ID de la sesión
        """
        try:
            import json
            from datetime import datetime
            
            # Crear nombre de archivo con timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.output_dir}/tracklist_{session_id}_{timestamp}.json"
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Resultados guardados en: {filename}")
        except Exception as e:
            logger.error(f"Error al guardar resultados: {str(e)}")
    
    @staticmethod
    def get_available_recognizers() -> List[str]:
        """
        Devuelve la lista de reconocedores disponibles.
        
        Returns:
            Lista de nombres de reconocedores disponibles
        """
        return RecognizerFactory.get_available_recognizers()
    
    @staticmethod
    def add_recognizer(name: str, recognizer_class: type) -> None:
        """
        Agrega un nuevo tipo de reconocedor.
        
        Args:
            name: Nombre para el nuevo reconocedor
            recognizer_class: Clase del reconocedor
        """
        RecognizerFactory.register_recognizer(name, recognizer_class) 