import requests

# Function to add a flashcard to Anki
def add_anki_card(front, back, audio_file=None):
    payload = {
        "action": "addNote",
        "version": 6,
        "params": {
            "note": {
                "deckName": "Danish",
                "modelName": "Basic",
                "fields": {
                    "Front": front,
                    "Back": back
                },
                "audio": [{
                    "path": audio_file,
                    "filename": audio_file.split('/')[-1],
                    "fields": ["Back"]
                }] if audio_file else []
            }
        }
    }
    
    response = requests.post("http://localhost:8765", json=payload)
    if response.status_code != 200:
        raise Exception(f"Anki request failed: {response.text}")
    return response.json()

