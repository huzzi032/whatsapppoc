from fastapi import FastAPI, Request
from typing import Optional
import requests
import os
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

print("Server starting...")

app = FastAPI()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")

if not AZURE_OPENAI_API_KEY or not AZURE_OPENAI_ENDPOINT:
    raise ValueError("Azure OpenAI API key and endpoint must be set")

client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version="2024-02-01",
    azure_endpoint=AZURE_OPENAI_ENDPOINT
)


@app.get("/")
def root():
    return {"message": "WhatsApp Agent POC is running"}

@app.get("/webhook")
def verify_webhook(
    hub_mode: Optional[str] = None,
    hub_challenge: Optional[str] = None,
    hub_verify_token: Optional[str] = None,
    
):
    print("Webhook verification request received")
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN and hub_challenge is not None:
        print("Webhook verified successfully")
        return int(hub_challenge)
    print("Webhook verification failed")
    return "Verification failed"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhook")
async def receive_message(request: Request):
    data = await request.json()
    print("Message received:", data)

    try:
        message = data["entry"][0]["changes"][0]["value"]["messages"][0]
        sender = message["from"]
        user_text = message["text"]["body"]

        reply = ai_reply(user_text)
        send_whatsapp_message(sender, reply)

    except Exception as e:
        print("Error:", e)

    return {"status": "ok"}




def ai_reply(user_message: str) -> str:
    print("Generating AI reply for:", user_message)
    if not AZURE_OPENAI_DEPLOYMENT:
        return "Error: Azure OpenAI deployment not configured"
    
    response = client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        messages=[{"role": "user", "content": user_message}]
    )
    result = response.choices[0].message.content
    if result is None:
        result = "Sorry, I couldn't generate a response."
    print("AI reply generated:", result)
    return result




def send_whatsapp_message(to: str, text: str):
    print("Sending message to:", to)
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }

    response = requests.post(url, headers=headers, json=payload)
    print("Message sent, response status:", response.status_code)
