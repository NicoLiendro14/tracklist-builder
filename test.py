import requests

url = "http://localhost:8000/api/tracks/identify/url"
data = {
    "url": "https://www.youtube.com/watch?v=rSu4NtLg0aw",
    "platform": "youtube"
}

response = requests.post(url, json=data)
print(response.json())
