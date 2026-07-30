from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="", tags=["welcome"])

@router.get("/health")
async def health_check():
    return {"status": "OK"}


@router.get("/", response_class=HTMLResponse)
async def welcome():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Thaink² LLM API</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: linear-gradient(135deg, #0f172a, #020617);
            color: #e5e7eb;
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
            margin: 0;
        }
        .container {
            background: #020617;
            padding: 3rem 4rem;
            border-radius: 14px;
            box-shadow: 0 25px 60px rgba(0,0,0,0.5);
            max-width: 640px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.08);
        }
        .logo {
            margin-bottom: 1.5rem;
        }
        .logo img {
            max-width: 180px;
            height: auto;
        }
        h1 {
            margin-bottom: 0.75rem;
            font-size: 2rem;
            font-weight: 600;
        }
        p {
            font-size: 1.05rem;
            color: #cbd5f5;
            margin-bottom: 2rem;
            line-height: 1.6;
        }
        a {
            color: #93c5fd;
            text-decoration: none;
            font-weight: 500;
        }
        a:hover {
            text-decoration: underline;
        }
        footer {
            margin-top: 2.5rem;
            font-size: 0.85rem;
            color: #94a3b8;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">
            <img 
              src="https://static.wixstatic.com/media/9aacb8_de7e42b7cf094efbb06af7031ff3b2c4~mv2.png/v1/fill/w_195,h_46,al_c,q_85,usm_0.66_1.00_0.01,enc_avif,quality_auto/thaink2-logo-white-small.png"
              alt="Thaink² logo"
            />
        </div>

        <h1>Welcome to Thaink² LLM API</h1>
        <p>
            Secure, scalable and sovereign Large Language Model API services<br/>
            built for data-driven organizations.
        </p>

        <p>
            Start exploring the <a href="/docs">API documentation</a>.
        </p>

        <footer>
            © Thaink² — Data & AI, done right.
        </footer>
    </div>
</body>
</html>
"""
