from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Dict, Any
import asyncio
import uuid
import logging
import traceback
import requests
from datetime import datetime
import os
from dotenv import load_dotenv
import discogs_client

# Importamos nuestra nueva arquitectura
from recognizers.manager import TrackRecognitionManager

# Cargar variables de entorno
load_dotenv()

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Configuración de Discogs
DISCOGS_API_URL = "https://api.discogs.com/database/search"
DISCOGS_RELEASE_URL = "https://api.discogs.com/releases"
DISCOGS_USER_AGENT = os.getenv("DISCOGS_USER_AGENT")
DISCOGS_CONSUMER_KEY = os.getenv("DISCOGS_CONSUMER_KEY")
DISCOGS_CONSUMER_SECRET = os.getenv("DISCOGS_CONSUMER_SECRET")

# Configuración del track_finder.exe
TRACK_FINDER_PATH = os.getenv("TRACK_FINDER_PATH", "./track_finder.exe")

d = discogs_client.Client(
    DISCOGS_USER_AGENT,
    consumer_key=DISCOGS_CONSUMER_KEY,
    consumer_secret=DISCOGS_CONSUMER_SECRET
)

app = FastAPI(
    title="DJ Track Identifier API",
    description="API para identificar tracks en mixes y sets de DJ",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # URL de tu frontend Next.js
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos los métodos HTTP
    allow_headers=["*"],  # Permite todos los headers
)

class TrackIdentificationRequest(BaseModel):
    url: HttpUrl
    platform: str
    recognizers: Optional[List[str]] = ["shazam"]  # Por defecto usa solo Shazam
    chunk_duration: Optional[int] = 30

class Track(BaseModel):
    timestamp: str
    title: str
    artist: str
    label: Optional[str] = None
    confidence: float
    recognizer: Optional[str] = None

class TrackIdentificationResponse(BaseModel):
    id: str
    tracks: List[Track]
    totalTracks: int

class DiscogsSearchRequest(BaseModel):
    query: str
    type: Optional[str] = "release"
    per_page: Optional[int] = 10
    page: Optional[int] = 1

class DiscogsTrack(BaseModel):
    title: str
    artist: str
    year: Optional[str] = None
    country: Optional[str] = None
    format: Optional[List[str]] = None
    label: Optional[List[str]] = None
    genre: Optional[List[str]] = None
    style: Optional[List[str]] = None
    resource_url: str
    id: int

class DiscogsSearchResponse(BaseModel):
    pagination: dict
    results: List[DiscogsTrack]

class DiscogsArtist(BaseModel):
    id: int
    name: str
    resource_url: str
    anv: Optional[str] = ""
    join: Optional[str] = ""
    role: Optional[str] = ""
    tracks: Optional[str] = ""

class DiscogsCommunity(BaseModel):
    have: int
    want: int
    rating: Dict[str, float]
    status: str
    submitter: Dict[str, str]
    data_quality: str
    contributors: List[Dict[str, str]]

class DiscogsCompany(BaseModel):
    id: int
    name: str
    resource_url: str
    catno: Optional[str] = ""
    entity_type: Optional[str] = ""
    entity_type_name: Optional[str] = ""

class DiscogsFormat(BaseModel):
    name: str
    qty: str
    descriptions: List[str]

class DiscogsIdentifier(BaseModel):
    type: str
    value: str

class DiscogsImage(BaseModel):
    height: int
    width: int
    resource_url: str
    type: str
    uri: str
    uri150: str

class DiscogsLabel(BaseModel):
    id: int
    name: str
    resource_url: str
    catno: Optional[str] = ""
    entity_type: Optional[str] = ""

class DiscogsTrack(BaseModel):
    position: str
    title: str
    duration: Optional[str] = None
    type_: Optional[str] = None

class DiscogsVideo(BaseModel):
    description: str
    duration: int
    embed: bool
    title: str
    uri: str

class DiscogsReleaseResponse(BaseModel):
    id: int
    title: str
    artists: List[DiscogsArtist]
    data_quality: str
    thumb: str
    community: DiscogsCommunity
    companies: List[DiscogsCompany]
    country: str
    date_added: str
    date_changed: str
    estimated_weight: Optional[int] = None
    extraartists: List[DiscogsArtist]
    format_quantity: int
    formats: List[DiscogsFormat]
    genres: List[str]
    identifiers: List[DiscogsIdentifier]
    images: List[DiscogsImage]
    labels: List[DiscogsLabel]
    lowest_price: Optional[float] = None
    master_id: Optional[int] = None
    master_url: Optional[str] = None
    notes: Optional[str] = None
    num_for_sale: Optional[int] = None
    released: str
    released_formatted: str
    resource_url: str
    series: List[Any] = []
    status: str
    styles: List[str]
    tracklist: List[DiscogsTrack]
    uri: str
    videos: List[DiscogsVideo]
    year: int

# Respuesta hardcodeada para pruebas
HARDCODED_RESPONSE = {
    "id": "d2f7baea-f6d1-4baa-b25a-32905b1d848f",
    "tracks": [
        {
            "timestamp": "01:00",
            "title": "Sexy Bitch (feat. Akon)",
            "artist": "David Guetta & Akon",
            "label": None,
            "confidence": 1.0
        },
        {
            "timestamp": "02:00",
            "title": "Sexy Bitch (70s Disco Remix)",
            "artist": "David Guetta",
            "label": None,
            "confidence": 1.0
        },
        {
            "timestamp": "03:00",
            "title": "Sexy Bitch (feat. Akon)",
            "artist": "David Guetta & Akon",
            "label": None,
            "confidence": 1.0
        },
        {
            "timestamp": "04:30",
            "title": "Let Me Think About It",
            "artist": "Ida Corr",
            "label": None,
            "confidence": 1.0
        },
        {
            "timestamp": "06:30",
            "title": "Lose Control (Stonebridge Mix)",
            "artist": "Missy Elliott Feat. Ciara & Fatman Scoop",
            "label": None,
            "confidence": 1.0
        },
        {
            "timestamp": "11:00",
            "title": "I've Got the Music In Me (Original Mix)",
            "artist": "Boogie Pimps",
            "label": None,
            "confidence": 1.0
        },
        {
            "timestamp": "15:30",
            "title": "I've Got the Music In Me (Original Mix)",
            "artist": "Boogie Pimps",
            "label": None,
            "confidence": 1.0
        }
    ],
    "totalTracks": 7
}

@app.post("/api/tracks/identify/url/test", response_model=TrackIdentificationResponse)
async def identify_tracks_from_url_test(request: TrackIdentificationRequest):
    """Endpoint de prueba que devuelve una respuesta hardcodeada"""
    logger.info(f"Endpoint de prueba llamado con URL: {request.url}")
    return HARDCODED_RESPONSE

@app.post("/api/tracks/identify/url", response_model=TrackIdentificationResponse)
async def identify_tracks_from_url(request: TrackIdentificationRequest):
    """
    Identifica tracks en una URL utilizando los reconocedores especificados.
    """
    try:
        logger.info(f"Iniciando identificación de tracks para URL: {request.url}")
        logger.info(f"Plataforma: {request.platform}")
        logger.info(f"Reconocedores: {request.recognizers}")
        logger.info(f"Duración de chunks: {request.chunk_duration}")
        
        # Verificar si la URL es válida
        if not request.url:
            raise HTTPException(status_code=400, detail="URL inválida")
        
        # Configurar parámetros específicos para reconocedores
        recognizer_params = {}
        for recognizer in request.recognizers:
            recognizer_params[recognizer] = {
                "chunk_duration": request.chunk_duration
            }
            
            # Parámetros específicos para track_finder si se usa
            if recognizer == "track_finder":
                if not os.path.exists(TRACK_FINDER_PATH):
                    raise HTTPException(
                        status_code=500, 
                        detail=f"El ejecutable 'track_finder.exe' no se encuentra en la ruta: {TRACK_FINDER_PATH}"
                    )
                recognizer_params[recognizer]["executable_path"] = TRACK_FINDER_PATH
                
            # Parámetros específicos para executable si se usa
            elif recognizer == "executable":
                executable_path = os.getenv("EXECUTABLE_RECOGNIZER_PATH")
                if not executable_path:
                    raise HTTPException(
                        status_code=500, 
                        detail="Falta configuración para el reconocedor 'executable'. Configura EXECUTABLE_RECOGNIZER_PATH en .env"
                    )
                recognizer_params[recognizer]["executable_path"] = executable_path
        
        # Crear el gestor de reconocimiento
        manager = TrackRecognitionManager(output_dir="output")
        
        # Iniciar el proceso de reconocimiento
        logger.info(f"Iniciando reconocimiento con {', '.join(request.recognizers)} para URL: {request.url}")
        result = await manager.identify_tracks(
            url=str(request.url),
            recognizer_types=request.recognizers,
            recognizer_params=recognizer_params
        )
        
        # Crear respuesta en el formato esperado por la API
        tracks = []
        for track_data in result["combined_results"]:
            track = Track(
                timestamp=track_data["timestamp"],
                title=track_data["title"],
                artist=track_data["artist"],
                label=track_data.get("label"),
                confidence=track_data.get("confidence", 1.0),
                recognizer=track_data.get("recognizer")
            )
            tracks.append(track)
        
        response = TrackIdentificationResponse(
            id=result["id"],
            tracks=tracks,
            totalTracks=len(tracks)
        )
        
        logger.info(f"Reconocimiento completado: {len(tracks)} tracks identificados")
        return response
        
    except Exception as e:
        logger.error(f"Error en el reconocimiento: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error en el procesamiento: {str(e)}"
        )

@app.post("/api/discogs/search", response_model=DiscogsSearchResponse)
async def search_discogs(request: DiscogsSearchRequest):
    """Busca tracks en Discogs"""
    try:
        logger.info(f"Buscando en Discogs: {request.query}")
        
        headers = {
            "User-Agent": DISCOGS_USER_AGENT,
            "Accept": "application/json",
            "Authorization": f"Discogs key={DISCOGS_CONSUMER_KEY}, secret={DISCOGS_CONSUMER_SECRET}"
        }
        
        params = {
            "q": request.query,
            "type": request.type,
            "per_page": request.per_page,
            "page": request.page
        }
        
        logger.info(f"Realizando petición a Discogs con headers: {headers}")
        logger.info(f"Parámetros de búsqueda: {params}")
        
        response = requests.get(
            DISCOGS_API_URL,
            headers=headers,
            params=params
        )
        
        logger.info(f"Respuesta de Discogs - Status Code: {response.status_code}")
        logger.info(f"Headers de respuesta: {response.headers}")
        
        if response.status_code != 200:
            logger.error(f"Error en la búsqueda de Discogs: {response.status_code}")
            logger.error(f"Respuesta de error: {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Error en la búsqueda de Discogs: {response.text}"
            )
        
        data = response.json()
        
        tracks = []
        for item in data.get("results", []):
            try:
                title_parts = item.get("title", "").split(" - ", 1)
                artist = title_parts[0] if len(title_parts) > 1 else "Unknown"
                title = title_parts[1] if len(title_parts) > 1 else title_parts[0]
                
                tracks.append(DiscogsTrack(
                    title=title,
                    artist=artist,
                    year=item.get("year"),
                    country=item.get("country"),
                    format=item.get("format", []),
                    label=item.get("label", []),
                    genre=item.get("genre", []),
                    style=item.get("style", []),
                    resource_url=item.get("resource_url", ""),
                    id=item.get("id", 0)
                ))
            except Exception as e:
                logger.error(f"Error procesando resultado de Discogs: {str(e)}")
                continue
        
        logger.info(f"Búsqueda completada. {len(tracks)} resultados encontrados")
        
        return DiscogsSearchResponse(
            pagination=data.get("pagination", {}),
            results=tracks
        )
        
    except Exception as e:
        logger.error(f"Error en la búsqueda de Discogs: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error en la búsqueda de Discogs: {str(e)}"
        )

@app.get("/api/discogs/releases/{release_id}", response_model=DiscogsReleaseResponse)
async def get_discogs_release(release_id: int, curr_abbr: Optional[str] = None):
    """Obtiene información detallada de un release de Discogs"""
    try:
        logger.info(f"Obteniendo información del release {release_id}")
        
        headers = {
            "User-Agent": DISCOGS_USER_AGENT,
            "Accept": "application/json",
            "Authorization": f"Discogs key={DISCOGS_CONSUMER_KEY}, secret={DISCOGS_CONSUMER_SECRET}"
        }
        
        params = {}
        if curr_abbr:
            params["curr_abbr"] = curr_abbr
        
        logger.info(f"Realizando petición a Discogs con headers: {headers}")
        logger.info(f"Parámetros: {params}")
        
        response = requests.get(
            f"{DISCOGS_RELEASE_URL}/{release_id}",
            headers=headers,
            params=params
        )
        
        logger.info(f"Respuesta de Discogs - Status Code: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"Error al obtener el release: {response.status_code}")
            logger.error(f"Respuesta de error: {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Error al obtener el release: {response.text}"
            )
        
        data = response.json()
        logger.info(f"Release obtenido correctamente: {data.get('title')}")
        
        return data
        
    except Exception as e:
        logger.error(f"Error al obtener el release: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener el release: {str(e)}"
        )

def format_time(seconds):
    """Formatea segundos a formato MM:SS"""
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes:02d}:{seconds:02d}"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 