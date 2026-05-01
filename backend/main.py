from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
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

        CREATE TABLE IF NOT EXISTS labels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS recipe_labels (
            recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
            label_id INTEGER NOT NULL REFERENCES labels(id) ON DELETE CASCADE,
            PRIMARY KEY (recipe_id, label_id)
        );
    """)
    conn.commit()
    conn.close()


def attach_labels(conn, recipes: list) -> list:
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


class AddRecipeRequest(BaseModel):
    url: str


class RecipeStatus(BaseModel):
    id: int
    status: str
    message: str


class CreateLabelRequest(BaseModel):
    name: str


class SetRecipeLabelsRequest(BaseModel):
    label_ids: List[int]


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
def list_recipes(search: str = "", label_id: Optional[int] = None, limit: int = 50, offset: int = 0):
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
    """Delete a recipe."""
    conn = get_db()
    try:
        conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
        conn.commit()
        return {"status": "deleted"}
    finally:
        conn.close()


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
    conn = get_db()
    try:
        conn.execute("DELETE FROM labels WHERE id = ?", (label_id,))
        conn.commit()
        return {"status": "deleted"}
    finally:
        conn.close()


@app.put("/api/recipes/{recipe_id}/labels")
def set_recipe_labels(recipe_id: int, req: SetRecipeLabelsRequest):
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
