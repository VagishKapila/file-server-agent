from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
import os
import uuid
from dotenv import load_dotenv
import psycopg2
from datetime import datetime

load_dotenv()

app = FastAPI()

# -----------------------------
# Environment-safe upload root
# -----------------------------
IS_RAILWAY = os.getenv("RAILWAY_ENVIRONMENT") is not None

BASE_UPLOAD_DIR = "/data/uploads" if IS_RAILWAY else "uploads"

os.makedirs(BASE_UPLOAD_DIR, exist_ok=True)

# -----------------------------
# Database connection helper
# -----------------------------
def get_db():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

# -----------------------------
# Upload endpoint
# -----------------------------
@app.post("/upload")
async def upload_file(
    project_request_id: int = Form(...),
    file: UploadFile = File(...)
):
    try:
        project_dir = os.path.join(BASE_UPLOAD_DIR, "projects", str(project_request_id))
        os.makedirs(project_dir, exist_ok=True)

        ext = os.path.splitext(file.filename)[1]
        safe_name = f"{uuid.uuid4().hex}{ext}"
        stored_path = os.path.join(project_dir, safe_name)

        contents = await file.read()
        with open(stored_path, "wb") as f:
            f.write(contents)

        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO project_files
            (project_request_id, filename, stored_path, file_type, file_size, uploaded_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                project_request_id,
                file.filename,
                stored_path,
                file.content_type,
                len(contents),
                datetime.utcnow(),
            ),
        )

        conn.commit()
        cur.close()
        conn.close()

        public_url = f"/files/projects/{project_request_id}/{safe_name}"

        return JSONResponse(
            {
                "status": "success",
                "filename": file.filename,
                "stored_path": stored_path,
                "public_url": public_url,
            }
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)},
        )
