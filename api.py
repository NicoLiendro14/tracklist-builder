from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import List, Optional
import asyncio
from shazam_tracklist_identifier import main as identify_tracks
import uuid
import logging
import traceback
import requests
from datetime import datetime
import os
from dotenv import load_dotenv
import discogs_client

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
DISCOGS_USER_AGENT = os.getenv("DISCOGS_USER_AGENT")
DISCOGS_CONSUMER_KEY = os.getenv("DISCOGS_CONSUMER_KEY")
DISCOGS_CONSUMER_SECRET = os.getenv("DISCOGS_CONSUMER_SECRET")

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

class Track(BaseModel):
    timestamp: str
    title: str
    artist: str
    label: Optional[str] = None
    confidence: float

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
    try:
        logger.info(f"Iniciando identificación de tracks para URL: {request.url}")
        logger.info(f"Plataforma: {request.platform}")
        
        identification_id = str(uuid.uuid4())
        logger.info(f"ID de identificación: {identification_id}")
        
        results = await identify_tracks(
            str(request.url),
            chunk_duration=30,
            output_formats=["json"],
            output_dir="output"
        )
        
        if not results:
            logger.warning("No se encontraron tracks en el resultado")
            return TrackIdentificationResponse(
                id=identification_id,
                tracks=[],
                totalTracks=0
            )
        
        tracks = []
        for track in results:
            try:
                tracks.append(Track(
                    timestamp=format_time(track["start"]),
                    title=track["track"]["title"],
                    artist=track["track"]["artist"],
                    confidence=1.0
                ))
            except Exception as e:
                logger.error(f"Error procesando track: {str(e)}")
                logger.error(traceback.format_exc())
                continue
        
        logger.info(f"Identificación completada. {len(tracks)} tracks encontrados")
        
        return TrackIdentificationResponse(
            id=identification_id,
            tracks=tracks,
            totalTracks=len(tracks)
        )
        
    except Exception as e:
        logger.error(f"Error en la identificación de tracks: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error en la identificación de tracks: {str(e)}"
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

def format_time(seconds):
    """Formatea segundos a formato MM:SS"""
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes:02d}:{seconds:02d}"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 