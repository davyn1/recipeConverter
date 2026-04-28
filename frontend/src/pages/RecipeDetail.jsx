import { useState, useEffect } from 'react'
import { fetchRecipe, deleteRecipe, mediaUrl } from '../api.js'
import './RecipeDetail.css'

export default function RecipeDetail({ id, onBack }) {
  const [recipe, setRecipe] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchRecipe(id)
      .then(setRecipe)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  async function handleDelete() {
    if (!confirm('Remove this recipe from your vault?')) return
    await deleteRecipe(id)
    onBack()
  }

  function formatDate(iso) {
    if (!iso) return ''
    try {
      return new Date(iso).toLocaleDateString('en-US', {
        weekday: 'long', month: 'long', day: 'numeric', year: 'numeric'
      })
    } catch { return '' }
  }

  function parseTags(raw) {
    if (!raw) return []
    try { return JSON.parse(raw) } catch { return [] }
  }

  function formatCaption(caption) {
    if (!caption) return []
    // Split into paragraphs on double newlines, or every ~3 single newlines
    return caption.split(/\n{2,}/).map(p => p.trim()).filter(Boolean)
  }

  if (loading) return (
    <div className="detail-page">
      <button className="back-btn" onClick={onBack}>← Back</button>
      <div className="detail-loading">Loading recipe…</div>
    </div>
  )

  if (error) return (
    <div className="detail-page">
      <button className="back-btn" onClick={onBack}>← Back</button>
      <div className="detail-error">{error}</div>
    </div>
  )

  const tags = parseTags(recipe.tags)
  const paragraphs = formatCaption(recipe.caption)
  const videoSrc = mediaUrl(recipe.video_path)
  const thumbSrc = mediaUrl(recipe.thumbnail_path)

  return (
    <div className="detail-page">
      <div className="detail-topbar">
        <button className="back-btn" onClick={onBack}>← Back to Vault</button>
        <div className="detail-actions">
          <a
            className="ig-link"
            href={recipe.instagram_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            View on Instagram ↗
          </a>
          <button className="delete-recipe-btn" onClick={handleDelete}>Remove</button>
        </div>
      </div>

      <div className="detail-inner">
        {/* Media */}
        <div className="detail-media">
          {videoSrc ? (
            <video
              src={videoSrc}
              poster={thumbSrc || undefined}
              controls
              playsInline
              className="detail-video"
            />
          ) : thumbSrc ? (
            <img src={thumbSrc} alt={recipe.title} className="detail-thumb" />
          ) : (
            <div className="detail-no-media">🍽️</div>
          )}
        </div>

        {/* Info */}
        <div className="detail-info">
          <p className="detail-author">@{recipe.author}</p>
          <h1 className="detail-title">{recipe.title}</h1>
          <p className="detail-date">{formatDate(recipe.post_date)}</p>

          {tags.length > 0 && (
            <div className="detail-tags">
              {tags.map(t => <span key={t} className="tag">#{t}</span>)}
            </div>
          )}

          <div className="detail-caption-section">
            <h2 className="caption-heading">Caption</h2>
            {paragraphs.length > 0 ? (
              <div className="caption-body">
                {paragraphs.map((p, i) => (
                  <p key={i} className="caption-para">{p}</p>
                ))}
              </div>
            ) : (
              <p className="caption-empty">No caption available.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
