import os
from cartesia import Cartesia

JESSICA_VOICE_ID = "25d7abcb-4d6d-4aca-adce-8a1c85620c8b"
MODEL_ID = "sonic-latest"

def synthesize_wav(text: str) -> bytes:
    api_key = os.environ.get("CARTESIA_API_KEY")
    if not api_key:
        raise ValueError("CARTESIA_API_KEY environment variable is not configured.")

    client = Cartesia(api_key=api_key)
    
    response = client.tts.generate(
        model_id=MODEL_ID,
        transcript=text,
        voice={"mode": "id", "id": JESSICA_VOICE_ID},
        output_format={
            "container": "wav",
            "encoding": "pcm_s16le",
            "sample_rate": 24000
        }
    )
    
    # BinaryAPIResponse provides .read() to fetch the full raw bytes
    if hasattr(response, "read"):
        return response.read()
    if hasattr(response, "content"):
        return response.content
    return bytes(response)
