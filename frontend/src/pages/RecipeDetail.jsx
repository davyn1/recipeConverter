import { useState, useEffect, useRef } from 'react'
import { fetchRecipe, deleteRecipe, fetchLabels, createLabel, setRecipeLabels, updateRecipeTitle, updateRecipeCaption, mediaUrl } from '../api.js'
import RichTextEditor from '../components/RichTextEditor.jsx'
import './RecipeDetail.css'

function toHTML(text) {
  if (!text) return ''
  if (text.trimStart().startsWith('<')) return text
  return text.split('\n')
    .map(line => {
      const escaped = line.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      return `<p>${escaped || '<br>'}</p>`
    })
    .join('')
}

export default function RecipeDetail({ id, onBack }) {
  const [recipe, setRecipe] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [allLabels, setAllLabels] = useState([])
  const [recipeLabels, setRecipeLabelsState] = useState([])
  const [editingTitle, setEditingTitle] = useState(false)
  const [titleDraft, setTitleDraft] = useState('')
  const [showPicker, setShowPicker] = useState(false)
  const [newLabelInput, setNewLabelInput] = useState('')
  const [creatingLabel, setCreatingLabel] = useState(false)
  const [editingCaption, setEditingCaption] = useState(false)
  const [captionDraft, setCaptionDraft] = useState('')
  const [savingCaption, setSavingCaption] = useState(false)
  const pickerRef = useRef(null)

  useEffect(() => {
    fetchRecipe(id)
      .then(r => {
        setRecipe(r)
        setRecipeLabelsState(r.labels || [])
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

  async function handleSaveTitle() {
    const trimmed = titleDraft.trim()
    if (!trimmed || trimmed === recipe.title) { setEditingTitle(false); return }
    await updateRecipeTitle(id, trimmed)
    setRecipe(r => ({ ...r, title: trimmed }))
    setEditingTitle(false)
  }

  function handleTitleKeyDown(e) {
    if (e.key === 'Enter') { e.preventDefault(); handleSaveTitle() }
    if (e.key === 'Escape') { e.preventDefault(); setEditingTitle(false) }
  }

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

  async function handleCreateLabel(e) {
    e.preventDefault()
    const name = newLabelInput.trim()
    if (!name) return
    setCreatingLabel(true)
    try {
      const created = await createLabel(name)
      const newIds = [...recipeLabels.map(l => l.id), created.id]
      const updated = await setRecipeLabels(id, newIds)
      setRecipeLabelsState(updated)
      setAllLabels(prev => [...prev, created].sort((a, b) => a.name.localeCompare(b.name)))
      setNewLabelInput('')
      setShowPicker(false)
    } catch {
      // duplicate label names are rejected by the server — silently ignore
    } finally {
      setCreatingLabel(false)
    }
  }

  function startEditCaption() {
    setCaptionDraft(toHTML(recipe.caption || ''))
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
          {editingTitle ? (
            <textarea
              className="detail-title-input"
              value={titleDraft}
              rows={1}
              onChange={e => {
                setTitleDraft(e.target.value)
                e.target.style.height = 'auto'
                e.target.style.height = e.target.scrollHeight + 'px'
              }}
              onBlur={handleSaveTitle}
              onKeyDown={handleTitleKeyDown}
              autoFocus
            />
          ) : (
            <h1
              className="detail-title detail-title-editable"
              onClick={() => { setTitleDraft(recipe.title); setEditingTitle(true) }}
              title="Click to edit title"
            >{recipe.title}</h1>
          )}
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
                    {unassigned.length > 0 && <div className="label-picker-divider" />}
                    <form className="label-picker-new" onSubmit={handleCreateLabel}>
                      <input
                        className="label-picker-input"
                        type="text"
                        placeholder="New label…"
                        value={newLabelInput}
                        onChange={e => setNewLabelInput(e.target.value)}
                        autoFocus={unassigned.length === 0}
                      />
                      <button
                        type="submit"
                        className="label-picker-create-btn"
                        disabled={!newLabelInput.trim() || creatingLabel}
                      >
                        {creatingLabel ? '…' : 'Create'}
                      </button>
                    </form>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="detail-caption-section">
            <div className="caption-heading-row">
              <h2 className="caption-heading">Instructions</h2>
              {!editingCaption && (
                <button className="caption-edit-btn" onClick={startEditCaption}>Edit</button>
              )}
            </div>
            {editingCaption ? (
              <div className="caption-edit">
                <RichTextEditor content={captionDraft} onChange={setCaptionDraft} />
                <div className="caption-edit-actions">
                  <button className="caption-save-btn" onClick={handleSaveCaption} disabled={savingCaption}>
                    {savingCaption ? 'Saving…' : 'Save'}
                  </button>
                  <button className="caption-cancel-btn" onClick={cancelEditCaption}>Cancel</button>
                </div>
              </div>
            ) : recipe.caption ? (
              <div className="caption-body caption-html" dangerouslySetInnerHTML={{ __html: toHTML(recipe.caption) }} />
            ) : (
              <p className="caption-empty">No instructions yet.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
