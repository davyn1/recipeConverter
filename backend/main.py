from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from pathlib import Path
import mimetypes
import re
import sqlite3
import os
import json
from downloader import extract_post_data

app = FastAPI(title="RecipeVault API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Expose range headers so the browser can seek cross-origin videos
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
)

DB_PATH = "recipevault.db"
MEDIA_DIR = "media"
os.makedirs(MEDIA_DIR, exist_ok=True)


# --- Database helpers ---

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Required per-connection — SQLite disables FK enforcement by default
    conn.execute("PRAGMA foreign_keys = ON")
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
            tags TEXT,           -- JSON array of Instagram hashtags
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- Full-text search index over the fields users are likely to search
        CREATE VIRTUAL TABLE IF NOT EXISTS recipes_fts
        USING fts5(
            title,
            caption,
            author,
            tags,
            content='recipes',
            content_rowid='id'
        );

        -- Keep FTS in sync with the recipes table
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

        -- User-defined labels (e.g. "Asian", "Quick Meals") — separate from Instagram hashtags
        CREATE TABLE IF NOT EXISTS labels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- Many-to-many: a recipe can have multiple labels, a label can apply to many recipes
        CREATE TABLE IF NOT EXISTS recipe_labels (
            recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
            label_id INTEGER NOT NULL REFERENCES labels(id) ON DELETE CASCADE,
            PRIMARY KEY (recipe_id, label_id)
        );
    """)
    conn.commit()
    conn.close()


def attach_labels(conn, recipes: list) -> list:
    """Fetch labels for a batch of recipes and attach them in-place.

    One query for the whole batch instead of N queries avoids the N+1 problem.
    """
    if not recipes:
        return recipes
    ids = [r["id"] for r in recipes]
    placeholders = ",".join("?" * len(ids))
    rows = conn.execute(
        f"""SELECT rl.recipe_id, l.id, l.name
            FROM recipe_labels rl
            JOIN labels l ON l.id = rl.label_id
            WHERE rl.recipe_id IN ({placeholders})
            ORDER BY l.name""",
        ids,
    ).fetchall()
    label_map: dict = {}
    for row in rows:
        label_map.setdefault(row["recipe_id"], []).append({"id": row["id"], "name": row["name"]})
    for r in recipes:
        r["labels"] = label_map.get(r["id"], [])
    return recipes


init_db()


# --- Request models ---

class AddRecipeRequest(BaseModel):
    url: str

class CreateLabelRequest(BaseModel):
    name: str

class SetRecipeLabelsRequest(BaseModel):
    label_ids: List[int]

class UpdateTagsRequest(BaseModel):
    tags: List[str]

class UpdateCaptionRequest(BaseModel):
    caption: str


# --- Recipe endpoints ---

@app.post("/api/recipes")
async def add_recipe(req: AddRecipeRequest, background_tasks: BackgroundTasks):
    """Enqueue a new recipe for download. Returns immediately with the new ID so
    the frontend can start polling for status before the download finishes."""
    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT id FROM recipes WHERE instagram_url = ?", (req.url,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Recipe already saved")

        # Placeholder row — title "Processing..." signals in-progress to the frontend
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
    """Background task: run the downloader and write results back to the DB.
    On failure, the title is set to an error string so the frontend can surface it."""
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
def list_recipes(search: str = "", label_id: Optional[int] = None, limit: int = 50, offset: int = 0):
    """List recipes with optional full-text search and/or label filter.
    Query is built dynamically so each filter only adds a JOIN when needed."""
    conn = get_db()
    try:
        params: list = []
        joins = ""
        wheres: list = []

        if search.strip():
            joins += " JOIN recipes_fts fts ON r.id = fts.rowid"
            wheres.append("recipes_fts MATCH ?")
            params.append(search)

        if label_id is not None:
            joins += " JOIN recipe_labels rl ON r.id = rl.recipe_id"
            wheres.append("rl.label_id = ?")
            params.append(label_id)

        where = f"WHERE {' AND '.join(wheres)}" if wheres else ""
        query = f"SELECT r.* FROM recipes r{joins} {where} ORDER BY r.created_at DESC LIMIT ? OFFSET ?"
        params += [limit, offset]

        rows = conn.execute(query, params).fetchall()
        recipes = [dict(row) for row in rows]
        return attach_labels(conn, recipes)
    finally:
        conn.close()


@app.get("/api/recipes/{recipe_id}")
def get_recipe(recipe_id: int):
    """Get a single recipe by ID, including its user labels."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM recipes WHERE id = ?", (recipe_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Recipe not found")
        recipe = dict(row)
        attach_labels(conn, [recipe])
        return recipe
    finally:
        conn.close()


@app.delete("/api/recipes/{recipe_id}")
def delete_recipe(recipe_id: int):
    conn = get_db()
    try:
        conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
        conn.commit()
        return {"status": "deleted"}
    finally:
        conn.close()


@app.get("/api/recipes/{recipe_id}/status")
def get_recipe_status(recipe_id: int):
    """Lightweight poll endpoint — the frontend calls this every 2.5s while a
    recipe is downloading to know when it's ready without re-fetching full data."""
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


@app.put("/api/recipes/{recipe_id}/tags")
def update_recipe_tags(recipe_id: int, req: UpdateTagsRequest):
    """Replace the hashtag list for a recipe. Used when the user removes individual
    Instagram hashtags they don't want to keep.
    Rebuilds the FTS index after the update — safe even if FTS was previously out of sync."""
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM recipes WHERE id = ?", (recipe_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Recipe not found")
        conn.execute(
            "UPDATE recipes SET tags = ? WHERE id = ?",
            (json.dumps(req.tags), recipe_id),
        )
        # Full rebuild keeps FTS consistent regardless of prior state.
        # Safe for small vaults; revisit if recipe count grows large.
        conn.execute("INSERT INTO recipes_fts(recipes_fts) VALUES('rebuild')")
        conn.commit()
        return {"tags": req.tags}
    finally:
        conn.close()


@app.patch("/api/recipes/{recipe_id}/caption")
def update_recipe_caption(recipe_id: int, req: UpdateCaptionRequest):
    """Update the instructions/caption text for a recipe after manual editing."""
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM recipes WHERE id = ?", (recipe_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Recipe not found")
        conn.execute(
            "UPDATE recipes SET caption = ? WHERE id = ?",
            (req.caption, recipe_id),
        )
        conn.execute("INSERT INTO recipes_fts(recipes_fts) VALUES('rebuild')")
        conn.commit()
        return {"caption": req.caption}
    finally:
        conn.close()


# --- Label endpoints ---

@app.get("/api/labels")
def list_labels():
    conn = get_db()
    try:
        rows = conn.execute("SELECT id, name FROM labels ORDER BY name").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@app.post("/api/labels", status_code=201)
def create_label(req: CreateLabelRequest):
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Label name cannot be empty")
    conn = get_db()
    try:
        cursor = conn.execute("INSERT INTO labels (name) VALUES (?)", (name,))
        conn.commit()
        return {"id": cursor.lastrowid, "name": name}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Label already exists")
    finally:
        conn.close()


@app.delete("/api/labels/{label_id}")
def delete_label(label_id: int):
    """Deleting a label cascades to recipe_labels via the FK constraint."""
    conn = get_db()
    try:
        conn.execute("DELETE FROM labels WHERE id = ?", (label_id,))
        conn.commit()
        return {"status": "deleted"}
    finally:
        conn.close()


@app.put("/api/recipes/{recipe_id}/labels")
def set_recipe_labels(recipe_id: int, req: SetRecipeLabelsRequest):
    """Replace all labels on a recipe with the supplied set.
    Delete-then-insert is simpler than diffing additions and removals."""
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM recipes WHERE id = ?", (recipe_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Recipe not found")
        conn.execute("DELETE FROM recipe_labels WHERE recipe_id = ?", (recipe_id,))
        for lid in req.label_ids:
            conn.execute(
                "INSERT OR IGNORE INTO recipe_labels (recipe_id, label_id) VALUES (?, ?)",
                (recipe_id, lid),
            )
        conn.commit()
        rows = conn.execute(
            """SELECT l.id, l.name FROM labels l
               JOIN recipe_labels rl ON l.id = rl.label_id
               WHERE rl.recipe_id = ? ORDER BY l.name""",
            (recipe_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# --- Media serving & health ---

@app.get("/media/{filepath:path}")
async def serve_media(filepath: str, request: Request):
    """Serve media files as a proper FastAPI route so CORS middleware applies.
    Handles Range requests explicitly to support video seeking in the browser."""
    file_path = Path(MEDIA_DIR) / filepath
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404)

    file_size = file_path.stat().st_size
    content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"

    range_header = request.headers.get("range")
    if range_header:
        match = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if match:
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else file_size - 1
            end = min(end, file_size - 1)
            length = end - start + 1

            def iter_chunk():
                with open(file_path, "rb") as f:
                    f.seek(start)
                    remaining = length
                    while remaining > 0:
                        data = f.read(min(65536, remaining))
                        if not data:
                            break
                        remaining -= len(data)
                        yield data

            return StreamingResponse(
                iter_chunk(),
                status_code=206,
                media_type=content_type,
                headers={
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(length),
                },
            )

    def iter_file():
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                yield chunk

    return StreamingResponse(
        iter_file(),
        media_type=content_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
        },
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}
