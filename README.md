# 🧠 RAG Backend API

A production-ready Retrieval-Augmented Generation (RAG) system built with FastAPI, featuring document processing, vector search, and conversational AI capabilities.

## 📋 Table of Contents

- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Running the Application](#-running-the-application)
- [Testing](#-testing)
- [Development Workflow](#-development-workflow)
- [Project Structure](#-project-structure)
- [API Documentation](#-api-documentation)
- [ContrXuting](#-contrXuting)

---

## ✨ Features

- 🔐 JWT-based authentication with refresh tokens
- 📄 PDF document processing and vectorization
- 🗃️ Vector similarity search using LanceDB
- 💬 Conversational AI with context retrieval
- 📊 Dataset management and metadata tracking
- ☁️ S3-compatXle storage integration
- 🐳 Full Docker support with health checks
- 🧪 Comprehensive test suite

---

## 🛠️ Tech Stack

- **Language**: Python 3.12+
- **Framework**: FastAPI
- **Package Manager**: UV (modern Python package manager)
- **ORM**: SQLAlchemy 2.0
- **Database**: PostgreSQL
- **Vector Store**: LanceDB
- **Embeddings**: Sentence Transformers (gtr-t5-large)
- **LLM**: Mistral AI
- **Document Processing**: Docling
- **Storage**: S3-compatXle (Scaleway, AWS, etc.)
- **Containerization**: Docker + Docker Compose

---

## 📦 Prerequisites

### System Requirements

#### Windows Users 🪟

```powershell
# 1. Install Chocolatey (Package Manager) - Run as Administrator
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# 2. Install Python 3.12
choco install python312 -y

# 3. Install PostgreSQL (for local development)
choco install postgresql15 -y

# 4. Install Visual C++ Build Tools (required for some Python packages)
choco install visualstudio2022buildtools -y

# 5. Restart your terminal
```

#### macOS Users 🍎

```bash
# 1. Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. Install Python 3.12
brew install python@3.12

# 3. Install PostgreSQL (for local development)
brew install postgresql@15

# 4. Install OpenCV (required for document processing)
brew install opencv

# 5. Restart your terminal
```

### Install UV Package Manager

#### Windows 🪟

```powershell
# Install UV using PowerShell (Run as Administrator)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Close and reopen your terminal, then verify
uv --version
```

#### macOS/Linux 🍎🐧

```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Reload shell configuration
source ~/.zshrc  # or ~/.bashrc for bash users

# Verify installation
uv --version
```

### Install Git (If Not Already Installed)

#### Windows 🪟

```powershell
# Install Git
choco install git -y

# Configure Git (replace with your info)
git config --global user.name "Your Name"
git config --global user.email "your.email@company.com"
```

#### macOS 🍎

```bash
# Install Git
brew install git

# Configure Git (replace with your info)
git config --global user.name "Your Name"
git config --global user.email "your.email@company.com"
```

### Install Docker (Optional but Recommended)

- **Windows**: [Download Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
- **macOS**: [Download Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/)

---

## 🚀 Installation

### 1. Clone the Repository

```bash
# Clone the repository
git clone <repository-url>
cd rag-backend-api

# Switch to development branch (if applicable)
git checkout develop
```

### 2. Create Virtual Environment

#### Windows 🪟

```powershell
# Create UV virtual environment with Python 3.12
uv venv --python 3.12

# Activate virtual environment
.venv\Scripts\activate

# Verify Python version
python --version  # Should show Python 3.12.x
```

#### macOS/Linux 🍎🐧

```bash
# Create UV virtual environment with Python 3.12
uv venv --python 3.12

# Activate virtual environment
source .venv/bin/activate

# Verify Python version
python --version  # Should show Python 3.12.x
```

### 3. Install Dependencies

```bash
# Install all dependencies (including dev dependencies)
uv sync

# For production only (without dev dependencies)
uv sync --no-dev
```

#### Platform-Specific Troubleshooting

**Windows 🪟**

```powershell
# If psycopg2-binary fails
# Make sure PostgreSQL is installed, then:
$env:PATH += ";C:\Program Files\PostgreSQL\15\bin"
uv pip install psycopg2-binary

# If Visual C++ errors occur
# Install Visual Studio Build Tools from:
# https://visualstudio.microsoft.com/visual-cpp-build-tools/
```

**macOS ARM (M1/M2/M3) 🍎**

```bash
# If PyTorch installation fails
uv pip install torch==2.6.0 torchvision==0.21.0

# If psycopg2 fails
brew install postgresql@15
export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"
uv pip install psycopg2-binary
```

---

## ⚙️ Configuration

### 1. Create Environment File

#### Windows 🪟

```powershell
# Copy example configuration
Copy-Item .env.example .env

# Edit with notepad
notepad .env
```

#### macOS/Linux 🍎🐧

```bash
# Copy example configuration
cp .env.example .env

# Edit with your preferred editor
nano .env  # or vim, code, etc.
```

### 2. Configure Environment Variables

Update the `.env` file with your actual values:

```env
# Application Mode
WORKING_MODE=development

# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=rag_db
DB_USER=your_db_user
DB_PASSWORD=your_secure_password
DB_SCHEMA=public

# S3 Storage Configuration
S3_REGION=eu-west-3
S3_ACCESS_KEY=your_access_key
S3_ACCESS_KEY_SECRET=your_secret_key
S3_ENDPOINT=https://s3.eu-west-3.amazonaws.com
S3_BUCKET_NAME=your_bucket_name

# Mistral AI API
MISTRAL_API_KEY=your_mistral_api_key
MISTRAL_API_URL=https://api.mistral.ai/v1

# JWT Authentication
SECRET_KEY=your-super-secret-key-minimum-32-characters
ACCESS_TOKEN_EXPIRE_MINUTES=60
ALGORITHM=HS256

# Password Encryption
ENCRYPT_KEY=your-encryption-key

# Development Settings (optional)
ECHO_SQL=false
```

> ⚠️ **Security Warning**: Never commit `.env` files to version control!

### 3. Initialize Database

```bash
# Run database migrations
alembic upgrade head
```

---

## 🔐 Database Access (Important)

The PostgreSQL database is **IP-whitelisted** for security reasons.

➡️ **Before running the application**, you must ask the project owner/admin to add your public IP address to the database whitelist.

⚠️ If your IP is not whitelisted, the database connection will fail.

---

### 📡 How to Get Your Public IP Address

#### macOS / Linux 🍎🐧
```bash
curl ifconfig.me
```
or
```bash
curl https://api.ipify.org
```

#### Windows 🪟 (PowerShell)
```powershell
curl ifconfig.me
```
or
```powershell
(Invoke-WebRequest -uri "https://api.ipify.org").Content
```

---

### 📌 Next Steps
Send the resulting IP address to the administrator so it can be approved and added to the whitelist.

> ⚠️ **Note:** If you are on a dynamic network (VPN, mobile hotspot, etc.), your IP may change and need to be re-approved.

## 🎯 Running the Application

### Option 1: Local Development (Recommended) ⚡

#### Windows 🪟

```powershell
# Activate virtual environment
.venv\Scripts\activate

# Start the API server with auto-reload
uv run uvicorn th2rag.main:app --reload --host 0.0.0.0 --port 8000
```

#### macOS/Linux 🍎🐧

```bash
# Activate virtual environment
source .venv/bin/activate

# Start the API server with auto-reload
uv run uvicorn th2rag.main:app --reload --host 0.0.0.0 --port 8000
```

**Access Points:**
- 📚 Swagger UI: http://localhost:8000/docs
- 📖 ReDoc: http://localhost:8000/redoc
- ❤️ Health Check: http://localhost:8000/health

### Option 2: Docker (Production-like) 🐳

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

#### Updating Environment Variables in Docker

```bash
# Important: Restart does NOT reload .env!
# You must stop and recreate containers:

docker-compose down
docker-compose up -d
docker-compose logs -f api
```

---

## 🧪 Testing

### Run Tests Locally

#### Windows 🪟

```powershell
# Activate virtual environment
.venv\Scripts\activate

# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest test\test_auth.py

# Run with coverage
uv run pytest --cov=src --cov-report=html
uv run pytest --cov=src --cov-report=term-missing

# Open coverage report
start htmlcov\index.html
```

#### macOS/Linux 🍎🐧

```bash
# Activate virtual environment
source .venv/bin/activate

# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest test/test_auth.py

# Run with coverage
uv run pytest --cov=src --cov-report=html
uv run pytest --cov=src --cov-report=term-missing

# Open coverage report
open htmlcov/index.html
```

### Run Tests in Docker

```bash
# Ensure containers are running
docker-compose up -d

# Run tests inside container
docker-compose exec api pytest -v
```

---

## 🔄 Development Workflow

### Branch Strategy

This project follows a Git workflow with feature branches:

```bash
# 1. Create a new feature branch from main/develop
git checkout -b feature/your-feature-name

# 2. Make your changes and commit regularly
git add .
git commit -m "feat: description of your changes"

# 3. Push to remote
git push origin feature/your-feature-name

# 4. Create a Pull Request on GitHub
```

### Pre-commit Setup (Code Quality Checks)

Pre-commit hooks automatically check your code before each commit.

#### 1. Install Pre-commit

**Windows 🪟**
```powershell
uv pip install pre-commit
```

**macOS/Linux 🍎🐧**
```bash
uv pip install pre-commit
```

#### 2. Install Git Hooks

```bash
# Install the pre-commit hooks
pre-commit install

# (Optional) Run against all files to test
pre-commit run --all-files
```

#### 3. Create Pre-commit Configuration

Create `.pre-commit-config.yaml` in your project root:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: ['--maxkb=1000']
      - id: check-json
      - id: check-merge-conflict
      - id: detect-private-key

  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black
        language_version: python3.12

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
        args: [--ignore-missing-imports]
```

### Commit Message Convention

Follow conventional commits for clear history:

```bash
# Format: <type>(<scope>): <subject>

git commit -m "feat(auth): add refresh token endpoint"
git commit -m "fix(database): resolve connection pool issue"
git commit -m "docs(readme): update installation instructions"
git commit -m "test(auth): add JWT validation tests"
git commit -m "chore(deps): update dependencies"
```

**Commit Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

### Pushing Your X Branch

#### Step-by-Step Guide

**1. Check your current status**

```bash
# See what files have changed
git status

# See the actual changes
git diff
```

**2. Stage your changes**

```bash
# Stage specific files
git add pyproject.toml
git add .pre-commit-config.yaml
git add docker-compose.yml
git add README.md
git add .env.example

# OR stage all changes
git add .
```

**3. Commit your changes**

```bash
# Commit with a descriptive message
git commit -m "feat(migration): migrate to UV package manager and update documentation"
```

**4. Create and push your branch**

**Windows 🪟**
```powershell
# Create and switch to X branch
git checkout -b X

# Push to remote repository
git push -u origin X
```

**macOS/Linux 🍎🐧**
```bash
# Create and switch to X branch
git checkout -b X

# Push to remote repository
git push -u origin X
```

**5. Create a Pull Request**

- Go to your GitHub repository
- Click "Compare & pull request" button
- Select base branch (usually `main` or `develop`)
- Add description of your changes
- Assign reviewers from your team
- Submit the pull request

### Daily Workflow Example

```bash
# 1. Start of day - update your branch
git checkout X
git pull origin X

# 2. Make changes to files
# ... edit code ...

# 3. Check what changed
git status
git diff

# 4. Run tests before committing
uv run pytest

# 5. Pre-commit will automatically run when you commit
git add .
git commit -m "feat(rag): improve document chunking algorithm"

# 6. Push changes
git push origin X

# 7. If you need to sync with main branch
git checkout main
git pull origin main
git checkout X
git merge main
# Resolve any conflicts if they occur
git push origin X
```

### Handling Pre-commit Failures

If pre-commit hooks fail:

```bash
# Pre-commit will show what failed
# Fix the issues, then:

git add .
git commit -m "your message"

# If automatic fixes were applied, stage them:
git add .
git commit --amend --no-edit
```

---

## 📁 Project Structure

```
.
├── .github/                 # GitHub workflows and templates
├── alembic/                 # Database migrations
│   ├── versions/           # Migration scripts
│   └── env.py             # Alembic environment
├── data/                   # LanceDB vector storage
├── src/                    # Main application source
│   ├── auth/              # JWT authentication
│   ├── clients/           # S3 client integration
│   ├── conversations/     # Conversation management
│   ├── dataset/           # Dataset handling
│   ├── knowledge/         # Document management
│   ├── messages/          # Message operations
│   ├── rag/              # RAG pipeline
│   │   ├── chunkers/     # Document chunking
│   │   ├── converters/   # Format conversion
│   │   ├── embeddings/   # Vector embeddings
│   │   ├── generation/   # LLM generation
│   │   ├── retrieval/    # Vector search
│   │   ├── services/     # RAG orchestration
│   │   └── tasks/        # Background jobs
│   ├── users/            # User management
│   ├── utils/            # Utilities
│   └── main.py           # Application entry
├── test/                  # Test suite
├── .env.example          # Environment template
├── .gitignore           # Git ignore rules
├── .pre-commit-config.yaml  # Pre-commit hooks
├── alembic.ini          # Alembic config
├── docker-compose.yml   # Docker services
├── Dockerfile           # Container definition
├── pyproject.toml       # Project dependencies
└── README.md           # This file
```

---

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
- `POST /knowledge` - Upload PDF document
- `GET /knowledge/{id}` - Get document details
- `DELETE /knowledge/{id}` - Delete document and vectors

### Datasets
- `GET /datasets` - List datasets
- `POST /datasets` - Create dataset
- `PUT /datasets/{id}` - Update dataset
- `DELETE /datasets/{id}` - Delete dataset

For detailed API schemas, visit: http://localhost:8000/docs

---

## 🧠 RAG Engine

The `rag/` module is responsible for the core Retrieval-Augmented Generation (RAG) pipeline. It orchestrates document conversion, chunking, embedding, retrieval, and final answer generation.

### 📄 1. Document Conversion

* **`converters/pdf_converter.py`**: Converts PDF files (local or S3) to an internal `Document` format using `docling`.

```python
convert_pdf(source: str) -> dict
```

### 🛫 2. Chunking

* **`chunkers/hybrid_chunker.py`**: Wraps `docling`'s `HybridChunker` to split documents into semantic chunks.

```python
HybridTextChunker.chunk_document(dl_doc) -> list
```

### 🖐️ 3. Embeddings

* **`embeddings/sentence_transformer.py`**: Uses `sentence-transformers/gtr-t5-large` to convert text chunks into dense vectors.

```python
SentenceTransformerEmbedding.encode(text: str) -> List[float]
```

### 🗆️ 4. Vector Store (LanceDB)

* **`retrieval/lancedb/lancedb_storage.py`**: Manages chunk storage/retrieval in LanceDB.
* **`retrieval/lancedb/schemas.py`**: Pydantic schema definitions for LanceDB.

```python
LanceDBStorage.add_chunks(chunks)
LanceDBStorage.query(query_vector, doc_id, limit)
```

### 🔍 5. Retrieval

* **`retrieval/lancedb/lancedb_retriever.py`**: Retrieves similar document chunks using LanceDB + embeddings.

```python
LanceDBRetriever.retrieve(query: str, doc_id: int, limit: int) -> List[Dict]
```

### 📏 6. Generation

* **`generation/mistral_generator.py`**: Calls Mistral API to generate responses using retrieved context.

```python
MistralGenerator.generate(question, retrieved_context, prompt, history) -> str
```

### ⚖️ 7. RAG Service

* **`services/rag_service.py`**: Orchestrates the full RAG pipeline.
* **`services/rag_service_builder.py`**: Builds the RAG service with configurable components.

```python
RAGService.answer_question(question, doc_id, limit, prompt, history)
```

### ⚙️ 8. Background Processing

* **`tasks/process_pdf.py`**: Asynchronously handles PDF-to-vector pipeline including download, convert, chunk, embed, and store.

```python
process_pdf_background(doc_id, source)
```

---

## 🤝 ContrXuting

### Code Review Checklist

Before submitting a PR, ensure:

- ✅ All tests pass (`uv run pytest`)
- ✅ Pre-commit hooks pass
- ✅ Code is documented with docstrings
- ✅ New features have tests
- ✅ README updated if needed
- ✅ Commit messages follow convention
- ✅ No sensitive data in commits

### Adding New Features

**1. Database Changes**
```bash
# Edit src/models.py
# Generate migration
alembic revision --autogenerate -m "add new feature"
# Review and apply
alembic upgrade head
```

**2. New Embedding Model**
```python
# src/rag/embeddings/custom_embedding.py
from th2rag.rag.embeddings.base import BaseEmbedding

class CustomEmbedding(BaseEmbedding):
    def encode(self, text: str) -> List[float]:
        # Implementation
        pass
```

**3. New LLM Generator**
```python
# src/rag/generation/custom_generator.py
from th2rag.rag.generation.base import BaseGenerator

class CustomGenerator(BaseGenerator):
    def generate(self, question: str, context: str) -> str:
        # Implementation
        pass
```

---

## 🆘 Troubleshooting

### Windows-Specific Issues 🪟

**Port already in use:**
```powershell
# Find process
netstat -ano | findstr :8000
# Kill process (replace PID)
taskkill /PID <PID> /F
```

**Python not found:**
```powershell
# Add Python to PATH
$env:Path += ";C:\Python312;C:\Python312\Scripts"
```

**Permission errors:**
```powershell
# Run PowerShell as Administrator
# Or adjust execution policy
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### macOS-Specific Issues 🍎

**Port already in use:**
```bash
# Find and kill process
lsof -ti:8000 | xargs kill -9
```

**SSL certificate errors:**
```bash
# Update certificates
pip install --upgrade certifi
```

### Common Issues (All Platforms)

**Database connection failed:**
- Verify PostgreSQL is running
- Check credentials in `.env`
- Ensure database exists

**Docker container won't start:**
```bash
docker-compose logs api
docker-compose down -v
docker-compose up -d --build
```

**Pre-commit hooks fail:**
```bash
# Update hooks
pre-commit autoupdate
pre-commit run --all-files
```

---

## 📞 Support

- 📧 Email: your-team@company.com
- 💬 Slack: #rag-backend-support
- 🐛 Issues: [GitHub Issues](link-to-issues)
- 📖 Wiki: [Project Wiki](link-to-wiki)

---

## 📄 License

[Specify your license here]
