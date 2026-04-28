from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import sqlite3
import os
import json
from datetime import datetime
from downloader import extract_post_data

app = FastAPI(title="RecipeVault API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "recipevault.db"
MEDIA_DIR = "media"
os.makedirs(MEDIA_DIR, exist_ok=True)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instagram_url TEXT UNIQUE NOT NULL,
            shortcode TEXT UNIQUE,
            title TEXT,
            caption TEXT,
            author TEXT,
            post_date TEXT,
            video_path TEXT,
            thumbnail_path TEXT,
            tags TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS recipes_fts
        USING fts5(
            title,
            caption,
            author,
            tags,
            content='recipes',
            content_rowid='id'
        );

        CREATE TRIGGER IF NOT EXISTS recipes_ai
        AFTER INSERT ON recipes BEGIN
            INSERT INTO recipes_fts(rowid, title, caption, author, tags)
            VALUES (new.id, new.title, new.caption, new.author, new.tags);
        END;

        CREATE TRIGGER IF NOT EXISTS recipes_ad
        AFTER DELETE ON recipes BEGIN
            INSERT INTO recipes_fts(recipes_fts, rowid, title, caption, author, tags)
            VALUES ('delete', old.id, old.title, old.caption, old.author, old.tags);
        END;
    """)
    conn.commit()
    conn.close()


init_db()


class AddRecipeRequest(BaseModel):
    url: str


class RecipeStatus(BaseModel):
    id: int
    status: str
    message: str


@app.post("/api/recipes")
async def add_recipe(req: AddRecipeRequest, background_tasks: BackgroundTasks):
    """Add a new recipe from an Instagram URL."""
    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT id FROM recipes WHERE instagram_url = ?", (req.url,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Recipe already saved")

        # Insert a placeholder row so the frontend can poll for status
        cursor = conn.execute(
            "INSERT INTO recipes (instagram_url, title, caption) VALUES (?, ?, ?)",
            (req.url, "Processing...", "")
        )
        recipe_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()

    background_tasks.add_task(process_recipe, recipe_id, req.url)
    return {"id": recipe_id, "status": "processing"}


def process_recipe(recipe_id: int, url: str):
    """Background task: download video + extract metadata, update DB."""
    conn = get_db()
    try:
        data = extract_post_data(url, MEDIA_DIR)
        conn.execute("""
            UPDATE recipes SET
                shortcode = ?,
                title = ?,
                caption = ?,
                author = ?,
                post_date = ?,
                video_path = ?,
                thumbnail_path = ?,
                tags = ?
            WHERE id = ?
        """, (
            data.get("shortcode"),
            data.get("title", "Untitled Recipe"),
            data.get("caption", ""),
            data.get("author", ""),
            data.get("post_date", ""),
            data.get("video_path"),
            data.get("thumbnail_path"),
            json.dumps(data.get("tags", [])),
            recipe_id
        ))
        conn.commit()
    except Exception as e:
        conn.execute(
            "UPDATE recipes SET title = ? WHERE id = ?",
            (f"Error: {str(e)[:100]}", recipe_id)
        )
        conn.commit()
    finally:
        conn.close()


@app.get("/api/recipes")
def list_recipes(search: str = "", limit: int = 50, offset: int = 0):
    """List all recipes, with optional full-text search."""
    conn = get_db()
    try:
        if search.strip():
            rows = conn.execute("""
                SELECT r.* FROM recipes r
                JOIN recipes_fts fts ON r.id = fts.rowid
                WHERE recipes_fts MATCH ?
                ORDER BY r.created_at DESC
                LIMIT ? OFFSET ?
            """, (search, limit, offset)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM recipes ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@app.get("/api/recipes/{recipe_id}")
def get_recipe(recipe_id: int):
    """Get a single recipe by ID."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM recipes WHERE id = ?", (recipe_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Recipe not found")
        return dict(row)
    finally:
        conn.close()


@app.delete("/api/recipes/{recipe_id}")
def delete_recipe(recipe_id: int):
    """Delete a recipe."""
    conn = get_db()
    try:
        conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
        conn.commit()
        return {"status": "deleted"}
    finally:
        conn.close()


# Serve saved media files
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

@app.get("/api/recipes/{recipe_id}/status")
def get_recipe_status(recipe_id: int):
    """Lightweight poll endpoint — returns processing status."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, title FROM recipes WHERE id = ?", (recipe_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Recipe not found")
        title = row["title"]
        is_processing = title == "Processing..."
        is_error = title.startswith("Error:")
        return {
            "id": recipe_id,
            "status": "processing" if is_processing else ("error" if is_error else "done"),
            "title": title,
        }
    finally:
        conn.close()


@app.get("/api/health")
def health():
    return {"status": "ok"}
