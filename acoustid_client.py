import acoustid
import requests
from pydub import AudioSegment
import tempfile
import os
import base64
import subprocess

ACOUSTID_API_KEY = "YjBc2sAt2S"

def generate_fingerprint(audio_path):
    """
    Genera el fingerprint usando fpcalc
    """
    try:
        # Ejecutar fpcalc sin -raw para obtener el fingerprint en formato comprimido
        result = subprocess.run(
            ['fpcalc', '-json', audio_path],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parsear salida JSON
        import json
        data = json.loads(result.stdout)
        
        # El fingerprint ya viene en el formato correcto (base64)
        return data['duration'], data['fingerprint']
    
    except subprocess.CalledProcessError as e:
        raise Exception(f"fpcalc error: {e.stderr}")
    except Exception as e:
        raise Exception(f"Error processing file: {str(e)}")

def acoustid_lookup(fingerprint, duration, meta="recordings"):
    """
    Realiza una búsqueda en la base de datos de AcoustID
    """
    params = {
        "client": "YjBc2sAt2S",
        "duration": str(int(float(duration))),
        "fingerprint": fingerprint,
        "meta": "recordings"
    }
    
    try:
        response = requests.get(
            "https://api.acoustid.org/v2/lookup",
            params=params
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"HTTP request error: {str(e)}")

def analyze_song(audio_path):
    # Procesar solo la canción completa
    duration, fingerprint = generate_fingerprint(audio_path)
    result = acoustid_lookup(fingerprint, duration)
    
    return {
        "full_track": process_results(result)
    }

def process_results(data):
    """
    Procesa los resultados de la API para extraer información relevante
    """
    if data.get("status") != "ok" or not data.get("results"):
        return None
    
    best_result = max(data["results"], key=lambda x: x.get("score", 0))
    
    # Si no hay recordings pero sí hay un ID, devolver lo que tenemos
    if not best_result.get("recordings"):
        return {
            "acoustid": best_result.get("id"),
            "score": best_result.get("score"),
            "message": "ID found but no associated metadata"
        }
    
    recording = best_result["recordings"][0]
    
    result = {
        "acoustid": best_result.get("id"),
        "score": best_result.get("score"),
        "title": recording.get("title"),
        "artists": [artist["name"] for artist in recording.get("artists", [])],
        "duration": recording.get("duration"),
        "recording_id": recording.get("id"),
        "releases": [],
        "release_groups": []
    }
    
    # Procesar información de releases
    if recording.get("releases"):
        for release in recording["releases"]:
            release_info = {
                "title": release.get("title"),
                "id": release.get("id"),
                "date": release.get("date"),
                "country": release.get("country"),
                "medium_count": release.get("medium_count"),
                "track_count": release.get("track_count")
            }
            result["releases"].append(release_info)
    
    # Procesar información de release groups
    if recording.get("releasegroups"):
        for group in recording["releasegroups"]:
            group_info = {
                "title": group.get("title"),
                "id": group.get("id"),
                "type": group.get("type")
            }
            result["release_groups"].append(group_info)
    
    return result

def lookup_by_track_id(track_id):
    """
    Búsqueda por ID de pista
    """
    params = {
        "client": "YjBc2sAt2S",
        "trackid": track_id,
        "meta": "recordings"
    }
    
    try:
        response = requests.get(
            "https://api.acoustid.org/v2/lookup",
            params=params
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"HTTP request error: {str(e)}")

# Uso ejemplo
if __name__ == "__main__":
    audio_file = r"C:\Users\Nicolas\Documents\ShazamProject\kerri_chandler_track.mp3"  # Reemplazar con tu archivo
    
    if not os.path.exists(audio_file):
        raise FileNotFoundError(f"File {audio_file} not found")
    
    results = analyze_song(audio_file)
    
    print("\nResults for complete song:")
    if results["full_track"]:
        track = results["full_track"]
        print(f"AcoustID: {track.get('acoustid')}")
        print(f"Confidence: {track.get('score'):.2%}")
        print(f"Title: {track.get('title')}")
        print(f"Artists: {', '.join(track.get('artists', []))}")
        print(f"Duration: {track.get('duration')} seconds")
        print(f"Recording ID: {track.get('recording_id')}")
        
        if track.get('releases'):
            print("\nReleases:")
            for release in track['releases']:
                print(f"- {release['title']} ({release.get('date', 'Unknown date')})")
                print(f"  Country: {release.get('country', 'Unknown')}")
                
        if track.get('release_groups'):
            print("\nRelease groups:")
            for group in track['release_groups']:
                print(f"- {group['title']} (Type: {group.get('type', 'Unknown')})")
        
        if track.get("acoustid"):
            track_id = track["acoustid"]
            id_results = lookup_by_track_id(track_id)
    else:
        print("No song identified")