from fastapi import FastAPI, UploadFile, File, Form
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def get_db():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT", 5432)
    )

@app.post("/upload")
async def upload_file(
    project_request_id: int = Form(...),
    file: UploadFile = File(...)
):
    file_path = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_path, "wb") as f:
        f.write(await file.read())

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO project_files
        (project_request_id, filename, stored_path, file_type, file_size)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            project_request_id,
            file.filename,
            file_path,
            file.content_type,
            os.path.getsize(file_path)
        )
    )

    conn.commit()
    cur.close()
    conn.close()

    return {
        "status": "ok",
        "filename": file.filename,
        "path": file_path
    }
