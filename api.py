from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import List, Optional
import asyncio
from shazam_tracklist_identifier import main as identify_tracks
import uuid
import logging
import traceback

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


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

def format_time(seconds):
    """Formatea segundos a formato MM:SS"""
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes:02d}:{seconds:02d}"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 