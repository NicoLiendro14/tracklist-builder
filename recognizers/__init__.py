"""
Paquete para el reconocimiento de tracks de audio utilizando diversos servicios.

Este paquete proporciona una arquitectura flexible y extensible para reconocer
tracks de audio utilizando diferentes servicios como Shazam, AcoustID y otros
reconocedores personalizados.
"""

from recognizers.base_recognizer import BaseRecognizer
from recognizers.shazam_recognizer import ShazamRecognizer
from recognizers.acoustid_recognizer import AcoustIDRecognizer
from recognizers.executable_recognizer import ExecutableRecognizer
from recognizers.factory import RecognizerFactory
from recognizers.manager import TrackRecognitionManager

__all__ = [
    'BaseRecognizer',
    'ShazamRecognizer',
    'AcoustIDRecognizer',
    'ExecutableRecognizer',
    'RecognizerFactory',
    'TrackRecognitionManager'
] 