import os
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError
import base64
from openai import OpenAI
import yaml
from flask import Flask
from flask import render_template, request
from dotenv import load_dotenv

load_dotenv()
credentials_path = os.getenv("CREDENTIALS_PATH")

client = OpenAI()

def load_prompts(path):
    filepath = f"{path}.yaml"
    with open(filepath, 'r') as file:
        return yaml.safe_load(file)

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def summarize_email(subject,email_body,sender):
    email = f"email:{email_body}, the subject is {subject}, the sender is {sender}"

    config = load_prompts('system')
    system_prompt = config['system_prompt']

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": email}
        ],
        max_tokens=60,
        temperature=0.7
    )

    summary = response.choices[0].message.content
    return summary

def categorize_email(subject,email_body,sender):
    config = load_prompts('system')
    category_prompt = config['category']

    email = f"email:{email_body}, the subject is {subject}, the sender is {sender}"

    response = client.chat.completions.create(
        model = "gpt-4o-mini",
        messages=[
            {"role": "system", "content": category_prompt},
            {"role": "user", "content": email}
        ],
        max_tokens=60,
        temperature=0.7
    )

    category = response.choices[0].message.content
    return category


def main():
    creds = None
    
    flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
    creds = flow.run_local_server(port=0)

    try:
        service = build("gmail", "v1", credentials=creds)
        results = service.users().messages().list(userId='me', maxResults=10).execute()
        messages = results.get('messages', [])

    except HttpError as error:
        return f"An error occurred: {error}"

    email_info = []

    if not messages:
        return "No messages found."
    else:
        for msg in messages:
            current_msg = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
            payload = current_msg.get('payload')
            headers = payload.get('headers')
            
            for head in headers:
                if head["name"] == "From":
                    from_header = head
                    break
            sender = from_header["value"]
            
            for head in headers:
                if head["name"] == "Subject":
                    subject_header = head
            subject = subject_header["value"]

            body_data = None
            if 'parts' in payload:
                for part in payload['parts']:
                    if part['mimeType'] == 'text/plain':
                        body_data = part['body'].get('data')
                        if body_data:
                            break
            else:
                body_data = payload.get('body', {}).get('data')
        
            email_body = ""
            if body_data:
                email_body = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')
        
            summary = summarize_email(subject,email_body,sender)
            category = categorize_email(subject,email_body,sender)
            
            email_info.append(f"<strong>Category: </strong>{category} <br> <strong>From: </strong>{sender} <br> <strong>Subject:</strong> {subject} <br> <strong>TLDR:</strong> {summary}")

        return email_info
    
app = Flask(__name__)

@app.route('/', methods = ['GET','POST'])
def display():

    email_info = []

    if request.method == 'POST':
        user_email = request.form.get('user_email')
        email_info = main() 

    return render_template('index.html', messages=email_info)

if __name__ == '__main__':
    app.run(debug=True, port=5000)