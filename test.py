import requests
import json

BASE_URL = "http://127.0.0.1:50021"

# Cấu trúc tham số truyền vào URL
query_payload = {
    "text": "こんにちは、世界", # Xin chào thế giới
    "speaker": 1
}

# Gửi POST request
response_query = requests.post(f"{BASE_URL}/audio_query", params=query_payload)

# Trích xuất dữ liệu JSON từ phản hồi của server
audio_query_data = response_query.json()

synth_payload = {
    "speaker": 1
}

# Lần này, audio_query_data được truyền vào tham số 'json' (body)
response_synth = requests.post(
    f"{BASE_URL}/synthesis", 
    params=synth_payload, 
    json=audio_query_data
)

# response_synth.content chứa dữ liệu nhị phân của âm thanh
with open("output.wav", "wb") as f:
    f.write(response_synth.content)