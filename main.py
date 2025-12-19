from fastapi import FastAPI, Request, Query
from fastapi.responses import PlainTextResponse
from typing import Optional
import requests
import os
from openai import AzureOpenAI
from dotenv import load_dotenv
import json

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


@app.get("/")
def root():
    return {"message": "WhatsApp Agent POC is running"}

@app.get("/webhook")
def verify_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    
):
    print("Webhook verification request received")
    print(f"hub_mode: {hub_mode}, hub_verify_token: {hub_verify_token}, hub_challenge: {hub_challenge}")
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN and hub_challenge is not None:
        print("Webhook verified successfully")
        return PlainTextResponse(content=hub_challenge)
    print("Webhook verification failed")
    return PlainTextResponse(content="Verification failed", status_code=403)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhook")
async def receive_message(request: Request):
    data = await request.json()
    print("Webhook payload received:")
    print(json.dumps(data, indent=2))

    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        if "messages" in value:
            # Handle incoming message
            message = value["messages"][0]
            sender = message["from"]
            user_text = message["text"]["body"]

            reply = ai_reply(user_text)
            send_whatsapp_message(sender, reply)
        elif "statuses" in value:
            # Handle message status update (e.g., sent, delivered, read)
            status = value["statuses"][0]
            print(f"Message status update: {status['status']} for message ID {status['id']}")
        else:
            print("Unknown webhook event type")

    except Exception as e:
        print("Error processing webhook:", e)

    return {"status": "ok"}




def ai_reply(user_message: str) -> str:
    print("Generating AI reply for:", user_message)
    if not AZURE_OPENAI_DEPLOYMENT:
        return "Error: Azure OpenAI deployment not configured"
    
    assert AZURE_OPENAI_API_KEY is not None
    assert AZURE_OPENAI_ENDPOINT is not None
    
    # Disable proxies to avoid httpx issues
    os.environ['HTTP_PROXY'] = ''
    os.environ['HTTPS_PROXY'] = ''
    os.environ['http_proxy'] = ''
    os.environ['https_proxy'] = ''
    
    try:
        client = AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            api_version="2024-08-01-preview",
            azure_endpoint=AZURE_OPENAI_ENDPOINT
        )
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[{"role": "user", "content": user_message}]
        )
        result = response.choices[0].message.content
        if result is None:
            result = "Sorry, I couldn't generate a response."
        print("AI reply generated:", result)
        return result
    except Exception as e:
        print("Error generating AI reply:", e)
        return "Sorry, there was an error generating the response."




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
