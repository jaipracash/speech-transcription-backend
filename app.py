import json
import asyncio
import os
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from vosk import Model, KaldiRecognizer
from googletrans import Translator

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

translator = Translator()

# Path to Vosk model
MODEL_PATH = "model"

# --- Model Download Logic for Hugging Face ---
if not os.path.exists(MODEL_PATH):
    logger.info("Model not found. Downloading small English model...")
    try:
        # Using a reliable mirror for the small model
        os.system("wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip")
        os.system("unzip vosk-model-small-en-us-0.15.zip")
        os.rename("vosk-model-small-en-us-0.15", MODEL_PATH)
        os.remove("vosk-model-small-en-us-0.15.zip")
        logger.info("Model downloaded and extracted successfully.")
    except Exception as e:
        logger.error(f"Failed to download model: {e}")

# Load model
if os.path.exists(MODEL_PATH):
    model = Model(MODEL_PATH)
else:
    logger.error("Vosk model could not be loaded.")
    model = None

@app.get("/")
def read_root():
    return {"status": "Vosk Backend Running", "model_loaded": model is not None}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Client connected via WebSocket")
    
    if model is None:
        await websocket.send_json({"error": "Vosk model not found on server"})
        await websocket.close()
        return

    # Vosk recognizer (16000 is standard)
    rec = KaldiRecognizer(model, 16000)
    target_lang = "ta" # Default to Tamil

    try:
        while True:
            data = await websocket.receive()
            
            if "text" in data:
                config = json.loads(data["text"])
                if "target_lang" in config:
                    target_lang = config["target_lang"]
                    logger.info(f"Target language updated to: {target_lang}")
                continue

            if "bytes" in data:
                audio_chunk = data["bytes"]
                
                if rec.AcceptWaveform(audio_chunk):
                    result = json.loads(rec.Result())
                    text = result.get("text", "")
                    if text:
                        try:
                            translation = translator.translate(text, dest=target_lang).text
                            await websocket.send_json({
                                "original": text,
                                "translated": translation,
                                "is_final": True
                            })
                        except Exception as e:
                            logger.error(f"Translation error: {e}")
                            await websocket.send_json({
                                "original": text,
                                "translated": "[Translation Error]",
                                "is_final": True
                            })
                else:
                    partial = json.loads(rec.PartialResult())
                    partial_text = partial.get("partial", "")
                    if partial_text:
                        await websocket.send_json({
                            "original": partial_text,
                            "translated": "",
                            "is_final": False
                        })

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        try:
            await websocket.close()
        except:
            pass

if __name__ == "__main__":
    import uvicorn
    # Local test run
    uvicorn.run(app, host="0.0.0.0", port=7860)
