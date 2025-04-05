# Proyecto de Reconocimiento de Tracks de Audio

Este proyecto proporciona una arquitectura para reconocer tracks de audio utilizando diferentes servicios como Shazam, AcoustID y ejecutables externos.

## Características

- **Arquitectura modular y extensible**: Diseñada con principios SOLID y POO.
- **Soporte para múltiples reconocedores**:
  - **Shazam**: Reconocimiento a través de ShazamIO.
  - **AcoustID**: Reconocimiento basado en huellas de audio con fpcalc.
  - **track_finder**: Reconocimiento a través del ejecutable track_finder.exe.
  - **Ejecutables personalizados**: Soporte para otros ejecutables que generen JSON.
- **Conversión automática de formatos**: Convierte automáticamente los archivos de audio al formato requerido por cada reconocedor.
- **Combinación de resultados**: Puede utilizar múltiples reconocedores y combinar sus resultados.
- **API REST**: Expone los servicios a través de una API REST con FastAPI.

## Estructura del Proyecto

```
├── recognizers/               # Paquete principal para reconocedores
│   ├── __init__.py            # Exporta las clases principales
│   ├── base_recognizer.py     # Clase base abstracta para reconocedores
│   ├── shazam_recognizer.py   # Implementación para Shazam
│   ├── acoustid_recognizer.py # Implementación para AcoustID
│   ├── executable_recognizer.py # Implementación para ejecutables externos
│   ├── factory.py             # Fábrica para crear reconocedores
│   ├── manager.py             # Gestor para orquestar reconocedores
│   ├── track_finder.exe       # Ejecutable para reconocimiento de tracks
│   └── utils.py               # Funciones de utilidad comunes
├── api.py                     # API REST con FastAPI
├── example.py                 # Script de ejemplo de uso
├── __init__.py                # Archivo de inicialización del módulo
└── requirements.txt           # Dependencias del proyecto
```

## Requisitos

- Python 3.6 o superior
- ffmpeg (para manipulación de audio)
- fpcalc (para AcoustID)
- track_finder.exe (debe estar en la carpeta `recognizers/`)

## Instalación

1. Clona este repositorio:
   ```
   git clone https://github.com/yourusername/audio-track-recognition.git
   cd audio-track-recognition
   ```

2. Crea un entorno virtual e instala las dependencias:
   ```
   python -m venv venv
   source venv/bin/activate  # En Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Asegúrate de que el ejecutable track_finder.exe esté en la carpeta `recognizers/`:
   ```
   # En Windows, puedes copiarlo con:
   copy C:\ruta\a\track_finder.exe recognizers\
   
   # En Linux/MacOS:
   cp /ruta/a/track_finder.exe recognizers/
   ```

4. Configura las variables de entorno (opcional):
   ```
   cp .env.example .env
   ```
   Edita el archivo `.env` para personalizar configuraciones si es necesario.

## Uso

### Como script independiente

```python
import asyncio
from recognizers import TrackRecognitionManager

async def main():
    # Crear gestor de reconocimiento
    manager = TrackRecognitionManager(output_dir="output")
    
    # Reconocer tracks con múltiples reconocedores incluyendo track_finder
    results = await manager.identify_tracks(
        url="https://www.youtube.com/watch?v=ejemplo",
        recognizer_types=["shazam", "acoustid", "track_finder"],
        recognizer_params={
            "shazam": {"chunk_duration": 30},
            "acoustid": {"chunk_duration": 60},
            "track_finder": {
                "executable_path": "recognizers/track_finder.exe",
                "chunk_duration": 15
            }
        }
    )
    
    # Imprimir resultados
    for track in results["combined_results"]:
        print(f"[{track['timestamp']}] {track['title']} - {track['artist']} ({track['recognizer']})")

if __name__ == "__main__":
    asyncio.run(main())
```

### Como servicio API

1. Inicia el servidor API:
   ```
   uvicorn api:app --reload
   ```

2. La API estará disponible en `http://localhost:8000`

3. Endpoints principales:
   - `POST /api/tracks/identify/url`: Identifica tracks en una URL con los reconocedores especificados
   - `POST /api/discogs/search`: Busca información en Discogs
   - `GET /api/discogs/releases/{id}`: Obtiene detalles de un release

### Uso del reconocedor track_finder

El reconocedor track_finder utiliza el ejecutable track_finder.exe, que analiza archivos de audio y devuelve resultados en formato JSON. Para utilizarlo:

1. Asegúrate de que track_finder.exe esté en la carpeta `recognizers/` del proyecto:
   ```
   recognizers/track_finder.exe
   ```

2. Al realizar la llamada a la API o usar el script example.py, especifica "track_finder" como reconocedor:
   ```json
   {
     "url": "https://www.youtube.com/watch?v=ejemplo",
     "platform": "youtube",
     "recognizers": ["shazam", "track_finder"],
     "chunk_duration": 30
   }
   ```

3. El sistema automáticamente:
   - Buscará el ejecutable en la carpeta recognizers/
   - Convertirá los archivos MP3 a WAV (requerido por track_finder.exe)
   - Procesará el resultado JSON y lo normalizará
   - Combinará los resultados con los de otros reconocedores

4. Nota: track_finder.exe requiere archivos en formato WAV. El sistema convertirá automáticamente los chunks de audio a WAV antes de enviarlos al ejecutable.

## Uso del script de ejemplo

Para el reconocimiento con track_finder, usa:

```bash
python example.py --url "https://www.youtube.com/watch?v=ejemplo" --recognizers "track_finder" --executable-path "recognizers/track_finder.exe"
```

Incluso si no especificas la ruta completa, el sistema intentará encontrar automáticamente el ejecutable en varias ubicaciones comunes:

```bash
python example.py --url "https://www.youtube.com/watch?v=ejemplo" --recognizers "track_finder"
```

Para usar múltiples reconocedores a la vez:

```bash
python example.py --url "https://www.youtube.com/watch?v=ejemplo" --recognizers "shazam,acoustid,track_finder" 
```

Para ver todas las opciones disponibles:
```bash
python example.py --help
```

## Extendiendo la arquitectura

### Creando un nuevo reconocedor

1. Crea una nueva clase heredando de `BaseRecognizer`:

```python
from recognizers.base_recognizer import BaseRecognizer

class MiReconocedor(BaseRecognizer):
    async def download_audio(self, url):
        # Implementa la descarga de audio
        ...
    
    def split_audio(self, audio_path):
        # Implementa la división de audio
        ...
    
    async def recognize_chunk(self, chunk_path):
        # Implementa el reconocimiento de chunks
        ...
    
    def process_results(self, results):
        # Implementa el procesamiento de resultados
        ...
```

2. Registra tu reconocedor:

```python
from recognizers import TrackRecognitionManager
from mi_modulo import MiReconocedor

# Registrar el nuevo reconocedor
TrackRecognitionManager.add_recognizer("mi_reconocedor", MiReconocedor)

# Usar el nuevo reconocedor
manager = TrackRecognitionManager()
results = await manager.identify_tracks(
    url="https://ejemplo.com/audio.mp3",
    recognizer_types=["mi_reconocedor"]
)
```

## Contribuir

Las contribuciones son bienvenidas. Por favor, abre un issue o un pull request si tienes alguna mejora o corrección.

## Licencia

MIT 