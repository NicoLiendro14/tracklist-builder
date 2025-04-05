import logging
from typing import Dict, Type, Optional, List

from recognizers.base_recognizer import BaseRecognizer
from recognizers.shazam_recognizer import ShazamRecognizer
from recognizers.acoustid_recognizer import AcoustIDRecognizer
from recognizers.executable_recognizer import ExecutableRecognizer

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

class RecognizerFactory:
    """
    Fábrica para crear instancias de los diferentes reconocedores.
    Sigue el patrón Factory Method.
    """
    
    # Registro de reconocedores disponibles
    _recognizers: Dict[str, Type[BaseRecognizer]] = {
        "shazam": ShazamRecognizer,
        "acoustid": AcoustIDRecognizer,
        "executable": ExecutableRecognizer,
        "track_finder": ExecutableRecognizer  # Alias para el reconocedor basado en track_finder.exe
    }
    
    @classmethod
    def get_recognizer(cls, recognizer_type: str, **kwargs) -> Optional[BaseRecognizer]:
        """
        Crea y devuelve una instancia del reconocedor solicitado.
        
        Args:
            recognizer_type: Tipo de reconocedor a crear
            **kwargs: Argumentos específicos para el reconocedor
            
        Returns:
            Instancia del reconocedor solicitado o None si no existe
        """
        recognizer_class = cls._recognizers.get(recognizer_type.lower())
        
        if not recognizer_class:
            logger.error(f"Reconocedor '{recognizer_type}' no encontrado")
            return None
        
        try:
            # Mostrar los parámetros recibidos para ayudar a depurar
            logger.info(f"Creando reconocedor de tipo '{recognizer_type}' con parámetros: {kwargs}")
            return recognizer_class(**kwargs)
        except Exception as e:
            logger.error(f"Error al crear reconocedor '{recognizer_type}': {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    @classmethod
    def get_available_recognizers(cls) -> List[str]:
        """
        Devuelve la lista de reconocedores disponibles.
        
        Returns:
            Lista de nombres de reconocedores disponibles
        """
        return list(cls._recognizers.keys())
    
    @classmethod
    def register_recognizer(cls, name: str, recognizer_class: Type[BaseRecognizer]) -> None:
        """
        Registra un nuevo tipo de reconocedor.
        
        Args:
            name: Nombre para el nuevo reconocedor
            recognizer_class: Clase del reconocedor
        """
        if not issubclass(recognizer_class, BaseRecognizer):
            logger.error(f"La clase {recognizer_class.__name__} no es subclase de BaseRecognizer")
            return
        
        cls._recognizers[name.lower()] = recognizer_class
        logger.info(f"Reconocedor '{name}' registrado correctamente") 