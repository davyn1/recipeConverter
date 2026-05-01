# RecipeVault v1

**Your personal recipe archive from Instagram.**  
Save Instagram recipe posts and reels locally — browse, search, and rewatch them anytime without the algorithm.

![RecipeVault Screenshot](./docs/screenshot.png)

---

## Features

- **Save by URL** — Paste any public Instagram post or reel link and save it instantly
- **Video download** — Downloads up to 1080p via yt-dlp, falls back to 720p via instaloader
- **Thumbnail preview** — Cover image pulled automatically from the post
- **Recipe grid** — Browse all saved recipes with author, title, and date
- **Recipe detail** — Full caption and video playback for each saved recipe
- **Full-text search** — Search by title, caption, ingredients, or hashtags
- **Background processing** — Recipes process in the background while you keep using the app
- **Local storage** — Everything stored locally via SQLite, no cloud required

## Tech Stack

- **Backend** — FastAPI, Python, SQLite, instaloader, yt-dlp
- **Frontend** — React, Vite

## Running Locally

**Backend**
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
```

Then open [http://localhost:5173](http://localhost:5173) in your browser.

---

## Planned Features

- [ ] Tag/hashtag filtering
- [ ] Delete recipes from the grid
- [ ] Support for private posts via Instagram login session
- [ ] Export recipes to PDF or notes
- [ ] Mobile-friendly layout
