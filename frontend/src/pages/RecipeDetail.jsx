import { useState, useEffect, useRef } from 'react'
import { fetchRecipe, deleteRecipe, fetchLabels, setRecipeLabels, updateRecipeTags, updateRecipeCaption, mediaUrl } from '../api.js'
import './RecipeDetail.css'

export default function RecipeDetail({ id, onBack }) {
  const [recipe, setRecipe] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [allLabels, setAllLabels] = useState([])
  const [recipeLabels, setRecipeLabelsState] = useState([])
  const [showPicker, setShowPicker] = useState(false)
  const [recipeTags, setRecipeTags] = useState([])
  const [editingCaption, setEditingCaption] = useState(false)
  const [captionDraft, setCaptionDraft] = useState('')
  const [savingCaption, setSavingCaption] = useState(false)
  const pickerRef = useRef(null)

  useEffect(() => {
    fetchRecipe(id)
      .then(r => {
        setRecipe(r)
        setRecipeLabelsState(r.labels || [])
        setRecipeTags(r.tags ? JSON.parse(r.tags) : [])
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
    fetchLabels().then(setAllLabels).catch(() => {})
  }, [id])

  useEffect(() => {
    if (!showPicker) return
    function handleClick(e) {
      if (pickerRef.current && !pickerRef.current.contains(e.target)) setShowPicker(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [showPicker])

  async function handleRemoveLabel(labelId) {
    const newIds = recipeLabels.filter(l => l.id !== labelId).map(l => l.id)
    const updated = await setRecipeLabels(id, newIds)
    setRecipeLabelsState(updated)
  }

  async function handleAddLabel(label) {
    const newIds = [...recipeLabels.map(l => l.id), label.id]
    const updated = await setRecipeLabels(id, newIds)
    setRecipeLabelsState(updated)
    setShowPicker(false)
  }

  function startEditCaption() {
    setCaptionDraft(recipe.caption || '')
    setEditingCaption(true)
  }

  function cancelEditCaption() {
    setEditingCaption(false)
  }

  async function handleSaveCaption() {
    setSavingCaption(true)
    try {
      await updateRecipeCaption(id, captionDraft)
      setRecipe(r => ({ ...r, caption: captionDraft }))
      setEditingCaption(false)
    } finally {
      setSavingCaption(false)
    }
  }

  async function handleRemoveTag(tag) {
    const newTags = recipeTags.filter(t => t !== tag)
    await updateRecipeTags(id, newTags)
    setRecipeTags(newTags)
  }

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

  function formatCaption(caption) {
    if (!caption) return []
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

  const paragraphs = formatCaption(recipe.caption)
  const videoSrc = mediaUrl(recipe.video_path)
  const thumbSrc = mediaUrl(recipe.thumbnail_path)
  const unassigned = allLabels.filter(l => !recipeLabels.find(rl => rl.id === l.id))

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

        <div className="detail-info">
          <p className="detail-author">@{recipe.author}</p>
          <h1 className="detail-title">{recipe.title}</h1>
          <p className="detail-date">{formatDate(recipe.post_date)}</p>

          {/* User labels */}
          <div className="detail-labels-section">
            <div className="detail-labels">
              {recipeLabels.map(l => (
                <span key={l.id} className="detail-label-chip">
                  {l.name}
                  <button
                    className="label-chip-remove"
                    onClick={() => handleRemoveLabel(l.id)}
                    title="Remove label"
                  >×</button>
                </span>
              ))}
              {allLabels.length > 0 && unassigned.length > 0 && (
                <div className="label-add-wrapper" ref={pickerRef}>
                  <button
                    className="label-add-btn"
                    onClick={() => setShowPicker(v => !v)}
                  >
                    + Add
                  </button>
                  {showPicker && (
                    <div className="label-picker">
                      {unassigned.map(l => (
                        <button
                          key={l.id}
                          className="label-picker-item"
                          onClick={() => handleAddLabel(l)}
                        >
                          {l.name}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
              {allLabels.length === 0 && (
                <span className="labels-hint">Create labels from the vault to organise recipes.</span>
              )}
            </div>
          </div>

          {recipeTags.length > 0 && (
            <div className="detail-tags">
              {recipeTags.map(t => (
                <span key={t} className="tag-chip">
                  #{t}
                  <button
                    className="tag-chip-remove"
                    onClick={() => handleRemoveTag(t)}
                    title="Remove hashtag"
                  >×</button>
                </span>
              ))}
            </div>
          )}

          <div className="detail-caption-section">
            <div className="caption-heading-row">
              <h2 className="caption-heading">Instructions</h2>
              {!editingCaption && (
                <button className="caption-edit-btn" onClick={startEditCaption}>Edit</button>
              )}
            </div>
            {editingCaption ? (
              <div className="caption-edit">
                <textarea
                  className="caption-textarea"
                  value={captionDraft}
                  onChange={e => setCaptionDraft(e.target.value)}
                  rows={12}
                />
                <div className="caption-edit-actions">
                  <button className="caption-save-btn" onClick={handleSaveCaption} disabled={savingCaption}>
                    {savingCaption ? 'Saving…' : 'Save'}
                  </button>
                  <button className="caption-cancel-btn" onClick={cancelEditCaption}>Cancel</button>
                </div>
              </div>
            ) : paragraphs.length > 0 ? (
              <div className="caption-body">
                {paragraphs.map((p, i) => (
                  <p key={i} className="caption-para">{p}</p>
                ))}
              </div>
            ) : (
              <p className="caption-empty">No instructions yet.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
