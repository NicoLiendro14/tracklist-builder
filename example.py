#!/usr/bin/env python3
"""
Script de ejemplo para demostrar el uso de la nueva arquitectura de reconocimiento de tracks.
"""

import asyncio
import json
import argparse
import sys
import logging
import os
from typing import List, Dict, Any, Optional, Union

from recognizers.manager import TrackRecognitionManager
from recognizers.factory import RecognizerFactory

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

def parse_arguments():
    """
    Parsea los argumentos de línea de comandos.
    
    Returns:
        args: Argumentos parseados
    """
    parser = argparse.ArgumentParser(description='Reconocedor de tracks de audio')
    
    parser.add_argument(
        '--url', '-u',
        type=str,
        required=True,
        help='URL del audio/video a analizar'
    )
    
    parser.add_argument(
        '--recognizers', '-r',
        type=str,
        default='shazam',
        help='Reconocedores a utilizar (separados por comas)'
    )
    
    parser.add_argument(
        '--chunk-duration', '-c',
        type=int,
        default=30,
        help='Duración en segundos de cada fragmento de audio'
    )
    
    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        default='output',
        help='Directorio donde se guardarán los resultados'
    )
    
    parser.add_argument(
        '--executable-path', '-e',
        type=str,
        help='Ruta al ejecutable externo para el reconocedor "executable" o "track_finder"'
    )
    
    parser.add_argument(
        '--acoustid-key',
        type=str,
        default='YjBc2sAt2S',
        help='Clave de API para AcoustID'
    )
    
    parser.add_argument(
        '--list-recognizers',
        action='store_true',
        help='Muestra la lista de reconocedores disponibles y sale'
    )
    
    return parser.parse_args()

async def main():
    """
    Función principal del script.
    """
    args = parse_arguments()
    
    # Mostrar reconocedores disponibles si se solicita
    if args.list_recognizers:
        print("Reconocedores disponibles:")
        for recognizer in RecognizerFactory.get_available_recognizers():
            print(f"  - {recognizer}")
        return
    
    # Verificar que se proporcionó una URL
    if not args.url:
        print("Error: Se requiere una URL para analizar")
        sys.exit(1)
    
    # Preparar los tipos de reconocedores
    recognizer_types = [r.strip() for r in args.recognizers.split(',')]
    
    # Verificar si necesitamos ejecutables pero no se proporcionaron
    needs_executable = any(r in ["executable", "track_finder"] for r in recognizer_types)
    if needs_executable and not args.executable_path:
        # Intentar buscar track_finder.exe en el directorio actual y en recognizers/
        exe_paths = ["track_finder.exe", "recognizers/track_finder.exe", "./track_finder.exe", "./recognizers/track_finder.exe"]
        found = False
        
        for exe_path in exe_paths:
            if os.path.exists(exe_path):
                print(f"Se encontró track_finder.exe en: {exe_path}")
                args.executable_path = os.path.abspath(exe_path)
                found = True
                break
                
        if not found:
            print("Error: Se requiere especificar --executable-path para los reconocedores 'executable' o 'track_finder'")
            sys.exit(1)
    
    # Preparar parámetros específicos para cada reconocedor
    recognizer_params = {}
    
    # Parámetros para todos los reconocedores
    for recognizer_type in recognizer_types:
        recognizer_params[recognizer_type] = {
            "chunk_duration": args.chunk_duration
        }
    
    # Parámetros específicos para AcoustID
    if "acoustid" in recognizer_types and args.acoustid_key:
        recognizer_params["acoustid"]["client_api_key"] = args.acoustid_key
    
    # Parámetros específicos para los reconocedores basados en ejecutables
    if args.executable_path:
        if "executable" in recognizer_types:
            recognizer_params["executable"]["executable_path"] = args.executable_path
        
        if "track_finder" in recognizer_types:
            recognizer_params["track_finder"]["executable_path"] = args.executable_path
    
    try:
        # Crear el gestor de reconocimiento
        manager = TrackRecognitionManager(output_dir=args.output_dir)
        
        # Identificar tracks
        print(f"Iniciando reconocimiento de tracks en {args.url}")
        print(f"Utilizando reconocedores: {', '.join(recognizer_types)}")
        
        # Imprimir la configuración para depuración
        print(f"Ruta del ejecutable: {args.executable_path}")
        for recognizer, params in recognizer_params.items():
            print(f"Parámetros para {recognizer}: {params}")
        
        results = await manager.identify_tracks(
            url=args.url,
            recognizer_types=recognizer_types,
            recognizer_params=recognizer_params
        )
        
        # Mostrar resultados
        print("\n=== RESULTADOS ===")
        print(f"ID de sesión: {results['id']}")
        print(f"Reconocedores utilizados: {', '.join(results['recognizers_used'])}")
        print(f"Total de tracks identificados: {results['total_tracks']}")
        
        if results['errors']:
            print("\nErrores durante el proceso:")
            for error in results['errors']:
                print(f"  - {error}")
        
        print("\nTracks identificados:")
        for i, track in enumerate(results['combined_results'], 1):
            print(f"{i}. [{track['timestamp']}] {track['title']} - {track['artist']} (confianza: {track.get('confidence', 'N/A')}, reconocedor: {track.get('recognizer', 'desconocido')})")
        
        print(f"\nResultados guardados en: {args.output_dir}/tracklist_{results['id']}_*.json")
        
    except Exception as e:
        print(f"Error durante el reconocimiento: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 