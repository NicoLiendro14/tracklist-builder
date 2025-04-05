import requests

url = "http://localhost:8000/api/tracks/identify/url"
data = {
    "url": "https://www.youtube.com/watch?v=rSu4NtLg0aw",
    "platform": "youtube"
}

response = requests.post(url, json=data)
print(response.json())

 
""" import requests

url = "http://localhost:8000/api/discogs/search"
data = {
    "query": "Kerri Chandler Rain",
    "type": "release",
    "per_page": 10,
    "page": 1
}

response = requests.post(url, json=data)
print(response.json()) """

# Test para obtener detalles de un release en Discogs
""" import requests

# ID del release "Kerri Chandler - Rain" en Discogs
release_id = 8115398

# URL del endpoint
url = f"http://localhost:8000/api/discogs/releases/{release_id}"

# Realizar la petición GET
response = requests.get(url)

# Imprimir la respuesta
print("Status Code:", response.status_code)
print("\nRespuesta:")
print(response.json()) """