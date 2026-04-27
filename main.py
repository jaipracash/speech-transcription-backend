import json
import asyncio
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from vosk import Model, KaldiRecognizer
from googletrans import Translator
import logging

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

if not os.path.exists(MODEL_PATH):
    logger.error(f"Model path '{MODEL_PATH}' does not exist. Please download the Vosk model and place it in the 'backend/model' directory.")
    model = None
else:
    model = Model(MODEL_PATH)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Client connected")
    
    if model is None:
        await websocket.send_json({"error": "Vosk model not found on server"})
        await websocket.close()
        return

    # Vosk recognizer expects a specific sample rate (16000 is common for small models)
    rec = KaldiRecognizer(model, 16000)
    target_lang = "ta" # Default

    try:
        while True:
            data = await websocket.receive()
            
            if "text" in data:
                # Handle configuration messages (like language change)
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
                        # We don't always translate partials to save API calls/latency
                        # but we send the partial original text
                        await websocket.send_json({
                            "original": partial_text,
                            "translated": "",
                            "is_final": False
                        })

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
