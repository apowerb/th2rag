# thaink² RAG as a service how to


## 📚 API Documentation

### Authentication
- `POST /auth/login` - Login and get tokens
- `POST /auth/refresh-token` - Refresh access token

### Users
- `GET /users` - List users (admin)
- `POST /users` - Create user
- `GET /users/me` - Get current user
- `GET /users/{id}` - Get user by ID
- `DELETE /users/{id}` - Delete user

### Conversations
- `GET /conversations` - List conversations
- `POST /conversations` - Create conversation
- `GET /conversations/{id}` - Get conversation details
- `DELETE /conversations/{id}` - Delete conversation

### Messages
- `GET /conversations/{id}/messages` - List messages
- `POST /conversations/{id}/messages` - Send message and get AI response
- `POST /conversations/{id}/messages/{message_id}/feedback` - Add feedback

### Knowledge Documents
- `GET /knowledge` - List documents
- `POST /knowledge` - Upload documents (PDFs, JSONs)
- `GET /knowledge/{id}` - Get document details
- `DELETE /knowledge/{id}` - Delete document and vectors

### Datasets
- `GET /datasets` - List datasets
- `POST /datasets` - Create dataset
- `PUT /datasets/{id}` - Update dataset
- `DELETE /datasets/{id}` - Delete dataset

For detailed API schemas, visit: https://rag.thaink2.fr/docs

---

# End to End process

## Instantiate a knowledge Base

First upload your documents into using


```python
from pathlib import Path
FILES_DIRECTORY = "./json_to_upload"  # ← Change this path to wherever your files are
directory = Path(FILES_DIRECTORY).expanduser()

files = list(Path(directory).glob("*.json")) + list(Path(directory).glob("*.pdf"))

if not files:
    print(f" No JSON or PDF files found in {directory}!")
    exit(1)

print(f"Found {len(files)} file(s):")
for f in files:
    print(f"  • {f.name}")

files_to_upload = []
for file_path in files:
    content_type = 'application/json' if file_path.suffix == '.json' else 'application/pdf'
    with open(file_path, 'rb') as f:
        files_to_upload.append(('files', (file_path.name, f.read(), content_type)))
```

* Create a knowledge base from the files

POST /knowledge

below is a python script to programatically do it

```python

import requests

# Configuration
API_BASE_URL = "https://rag.thaink2.fr"
ACCESS_TOKEN = "your_access_token_here"

# Prepare headers
headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}"
}

# Upload document
data = {
    "name": "jds json",
    "description": "Optional description of the document",
    "prompt": "You are a helpful assistant that answers questions based on the provided knowledge base. Be precise and answer in max two sentences"
}

response = requests.post(
    f"{API_BASE_URL}/knowledge",
    headers=headers,
    files=files_to_upload,
    data=data
)

if response.status_code == 201:
    knowledge_data = response.json()
    knowledge_id = knowledge_data["result"]["knowledge_id"]
    print(f"Document uploaded successfully! Knowledge ID: {knowledge_id}")
else:
    print(f"Error: {response.status_code} - {response.text}")

```

The api request will return 201 status with knowledge_id to be used later when starting the conversation.


A process in background will be triggered to upload your files and proceed to indexing

i. parsing
ii. OCR
iii. Chunking
iv. Embedding

* You can check the if the knowledge is ready by sending the request to the `/knowledge/{id}`

## Create a conversation

Once your knowledge base is ready, create a conversation that will use this knowledge:

```python
# Prepare headers
headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

# Create conversation with knowledge base
data = {
    "title": "My RAG Conversation",
    "knowledge_id": knowledge_id
}

response = requests.post(
    f"{API_BASE_URL}/conversations",
    headers=headers,
    json=data
)

if response.status_code == 201:
    conversation_data = response.json()
    conversation_id = conversation_data["conversation_id"]
    print(f"Conversation created! ID: {conversation_id}")
else:
    print(f"Error: {response.status_code} - {response.text}")

```

## Start a chat

Now you can send messages to the conversation and receive AI-powered responses based on your knowledge base:
```python
# Prepare headers
headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

# Send a message
data = {
    "content": "donnes moi le contenu de l'article qui parle urgence climatique? réponds en français",
    "sender": "USER"
}

response = requests.post(
    f"{API_BASE_URL}/conversations/{conversation_id}/messages",
    headers=headers,
    json=data
)

if response.status_code == 200:
    message_data = response.json()
    ai_response = message_data["content"]
    print(f"AI Response: {ai_response}")
    # Optional: Add feedback to the response
    message_id = message_data["message_id"]
else:
    print(f"Error: {response.status_code} - {response.text}")
```
