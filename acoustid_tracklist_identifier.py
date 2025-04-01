import os
import asyncio
import traceback
import yt_dlp
import logging
import time
import random
import subprocess
import requests
from pydub import AudioSegment

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def generate_fingerprint(audio_path):
    logger.info(f"Generating fingerprint for {audio_path}")
    try:
        result = subprocess.run(
            ['fpcalc', '-json', audio_path],
            capture_output=True,
            text=True,
            check=True
        )
        
        import json
        data = json.loads(result.stdout)
        logger.info(f"Fingerprint generated successfully")
        return data['duration'], data['fingerprint']
    
    except subprocess.CalledProcessError as e:
        raise Exception(f"fpcalc error: {e.stderr}")
    except Exception as e:
        raise Exception(f"Error processing file: {str(e)}")

def acoustid_lookup(fingerprint, duration):
    params = {
        "client": "YjBc2sAt2S",
        "duration": str(int(float(duration))),
        "fingerprint": fingerprint,
        "meta": "recordings"
    }
    logger.info(f"Trying to get data from acoustid...")
    try:
        response = requests.get(
            "https://api.acoustid.org/v2/lookup",
            params=params
        )
        logger.info(f"Response is {response.text}")
        if response.status_code == 200:
            logger.info(f"Data received from acoustid")
            return response.json()
        else:
            logger.error(f"Error getting data from acoustid: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        raise Exception(f"HTTP request error: {str(e)}")

def process_acoustid_results(data):
    logger.info(f"Processing acoustid results")
    if data.get("status") != "ok" or not data.get("results"):
        return None
    
    best_result = max(data["results"], key=lambda x: x.get("score", 0))
    
    if not best_result.get("recordings"):
        return {
            "acoustid": best_result.get("id"),
            "score": best_result.get("score"),
            "message": "ID found but no associated metadata"
        }
    
    recording = best_result["recordings"][0]
    
    return {
        "acoustid": best_result.get("id"),
        "score": best_result.get("score"),
        "title": recording.get("title"),
        "artists": [artist["name"] for artist in recording.get("artists", [])]
    }

async def recognize_with_acoustid(chunk_path):
    try:
        duration, fingerprint = generate_fingerprint(chunk_path)
        logger.info("Waiting 4 seconds before making request...")
        await asyncio.sleep(4)
        result = acoustid_lookup(fingerprint, duration)
        processed_result = process_acoustid_results(result)
        
        if processed_result:
            print("\nAcoustID Result:")
            print(f"Score: {processed_result.get('score', 0):.2%}")
            print(f"Title: {processed_result.get('title', 'Unknown')}")
            print(f"Artists: {', '.join(processed_result.get('artists', ['Unknown']))}")
        
        return processed_result
    except Exception as e:
        logger.error(f"Error in AcoustID recognition: {str(e)}")
        return None

def download_audio(url):
    logger.info(f"Starting audio download from URL: {url}")
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': 'downloaded_audio.%(ext)s',
        'quiet': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            base, ext = os.path.splitext(filename)
            final_filename = f"{base}.mp3"
            logger.info(f"Audio downloaded to: {final_filename}")
            return final_filename, info.get('title', 'Unknown')
    except Exception as e:
        logger.error(f"Error during audio download: {str(e)}")
        raise

def split_audio(audio_path, chunk_duration=60):
    logger.info(f"Splitting audio from {audio_path} into chunks of {chunk_duration} seconds")
    try:
        audio = AudioSegment.from_file(audio_path)
        chunk_ms = chunk_duration * 1000
        chunks = []
        
        for i in range(0, len(audio), chunk_ms):
            chunk = audio[i:i + chunk_ms]
            chunk_name = f"chunk_{i//1000:04d}.mp3"
            chunk.export(chunk_name, format="mp3")
            chunks.append(chunk_name)
        logger.info(f"Split audio into {len(chunks)} chunks")
        return chunks, len(audio) // 1000
    except Exception as e:
        logger.error(f"Error splitting audio: {str(e)}")
        raise

async def process_chunk(chunk_path):
    result = await recognize_with_acoustid(chunk_path)
    print(f"\nResults for chunk {chunk_path}:")
    print("=" * 50)
    return result

async def main(url, chunk_duration=60):
    try:
        audio_path, video_title = await asyncio.to_thread(download_audio, url)
        chunks, total_duration = split_audio(audio_path, chunk_duration)
        
        print(f"\nProcessing {len(chunks)} chunks of {chunk_duration} seconds each...")
        for chunk in chunks:
            await process_chunk(chunk)
        
        # Cleanup
        os.remove(audio_path)
        for chunk in chunks:
            os.remove(chunk)
            
    except Exception as e:
        logger.error(f"Error in main process: {str(e)}")
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    # Prueba con Around the World de Daft Punk
    url = "https://youtu.be/GVQISdz0qnA?si=DijOLeQSX2ESt4wc"
    asyncio.run(main(url))
