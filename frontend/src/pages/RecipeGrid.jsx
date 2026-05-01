import { useState, useEffect, useCallback } from 'react'
import { fetchRecipes, addRecipe, deleteRecipe, fetchLabels, createLabel, deleteLabel, mediaUrl } from '../api.js'
import './RecipeGrid.css'

export default function RecipeGrid({ onOpen }) {
  const [recipes, setRecipes] = useState([])
  const [search, setSearch] = useState('')
  const [url, setUrl] = useState('')
  const [adding, setAdding] = useState(false)
  const [addError, setAddError] = useState('')
  const [addSuccess, setAddSuccess] = useState('')
  const [loading, setLoading] = useState(true)
  const [labels, setLabels] = useState([])
  const [activeLabel, setActiveLabel] = useState(null)
  const [showManage, setShowManage] = useState(false)
  const [newLabelName, setNewLabelName] = useState('')
  const [labelError, setLabelError] = useState('')

  const loadLabels = useCallback(async () => {
    try { setLabels(await fetchLabels()) } catch (e) { console.error(e) }
  }, [])

  useEffect(() => { loadLabels() }, [loadLabels])

  const load = useCallback(async () => {
    try {
      const data = await fetchRecipes(search, activeLabel)
      setRecipes(data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [search, activeLabel])

  useEffect(() => {
    setLoading(true)
    const timer = setTimeout(load, 300)
    return () => clearTimeout(timer)
  }, [load])

  useEffect(() => {
    const processing = recipes.some(r => r.title === 'Processing...')
    if (!processing) return
    const interval = setInterval(load, 2500)
    return () => clearInterval(interval)
  }, [recipes, load])

  async function handleAdd(e) {
    e.preventDefault()
    if (!url.trim()) return
    setAdding(true)
    setAddError('')
    setAddSuccess('')
    try {
      await addRecipe(url.trim())
      setUrl('')
      setAddSuccess('Recipe is being saved — this takes 10–30 seconds.')
      setTimeout(() => setAddSuccess(''), 5000)
      load()
    } catch (err) {
      setAddError(err.message)
    } finally {
      setAdding(false)
    }
  }

  async function handleDelete(e, id) {
    e.stopPropagation()
    if (!confirm('Remove this recipe?')) return
    await deleteRecipe(id)
    setRecipes(r => r.filter(x => x.id !== id))
  }

  async function handleCreateLabel(e) {
    e.preventDefault()
    const name = newLabelName.trim()
    if (!name) return
    setLabelError('')
    try {
      await createLabel(name)
      setNewLabelName('')
      loadLabels()
    } catch (err) {
      setLabelError(err.message)
    }
  }

  async function handleDeleteLabel(id) {
    if (!confirm('Delete this label? It will be removed from all recipes.')) return
    await deleteLabel(id)
    if (activeLabel === id) setActiveLabel(null)
    loadLabels()
    load()
  }

  function formatDate(iso) {
    if (!iso) return ''
    try {
      return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    } catch { return '' }
  }

  function parseTags(raw) {
    if (!raw) return []
    try { return JSON.parse(raw).slice(0, 4) } catch { return [] }
  }

  return (
    <div className="grid-page">
      <header className="grid-header">
        <div className="header-inner">
          <div className="wordmark">
            <span className="wordmark-icon">🍳</span>
            <h1>RecipeVault</h1>
          </div>
          <p className="tagline">Your personal recipe archive from Instagram</p>
        </div>
      </header>

      <main className="grid-main">
        <section className="add-section">
          <form className="add-form" onSubmit={handleAdd}>
            <input
              className="url-input"
              type="url"
              placeholder="Paste an Instagram post or reel URL…"
              value={url}
              onChange={e => setUrl(e.target.value)}
              disabled={adding}
            />
            <button className="add-btn" type="submit" disabled={adding || !url.trim()}>
              {adding ? 'Saving…' : 'Save Recipe'}
            </button>
          </form>
          {addError && <p className="msg error">{addError}</p>}
          {addSuccess && <p className="msg success">{addSuccess}</p>}
        </section>

        <section className="search-section">
          <input
            className="search-input"
            type="text"
            placeholder="Search recipes, ingredients, hashtags…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          {search && (
            <button className="clear-search" onClick={() => setSearch('')}>✕</button>
          )}
        </section>

        <section className="label-bar">
          <div className="label-chips">
            {labels.map(label => (
              <button
                key={label.id}
                className={`label-chip${activeLabel === label.id ? ' active' : ''}`}
                onClick={() => setActiveLabel(activeLabel === label.id ? null : label.id)}
              >
                {label.name}
              </button>
            ))}
          </div>
          <button className="manage-btn" onClick={() => setShowManage(true)}>
            {labels.length === 0 ? '+ Create Labels' : 'Manage'}
          </button>
        </section>

        {loading ? (
          <div className="state-msg">Loading your vault…</div>
        ) : recipes.length === 0 ? (
          <div className="state-msg empty">
            {search
              ? 'No recipes match your search.'
              : activeLabel
              ? 'No recipes with this label yet.'
              : 'No recipes yet. Paste an Instagram URL above to get started!'}
          </div>
        ) : (
          <div className="recipe-grid">
            {recipes.map(recipe => {
              const isProcessing = recipe.title === 'Processing...'
              const isError = recipe.title?.startsWith('Error:')
              const thumb = mediaUrl(recipe.thumbnail_path)
              const tags = parseTags(recipe.tags)

              return (
                <div
                  key={recipe.id}
                  className={`recipe-card ${isProcessing ? 'processing' : ''} ${isError ? 'errored' : ''}`}
                  onClick={() => !isProcessing && !isError && onOpen(recipe.id)}
                >
                  <div className="card-thumb">
                    {thumb ? (
                      <img src={thumb} alt={recipe.title} />
                    ) : (
                      <div className="thumb-placeholder">
                        {isProcessing ? <span className="spinner" /> : '🍽️'}
                      </div>
                    )}
                    {recipe.video_path && (
                      <span className="video-badge">▶</span>
                    )}
                    <button
                      className="delete-btn"
                      onClick={e => handleDelete(e, recipe.id)}
                      title="Remove recipe"
                    >✕</button>
                  </div>
                  <div className="card-body">
                    <p className="card-author">@{recipe.author || 'unknown'}</p>
                    <h3 className="card-title">{recipe.title}</h3>
                    {recipe.labels?.length > 0 && (
                      <div className="card-labels">
                        {recipe.labels.map(l => (
                          <span key={l.id} className="card-label">{l.name}</span>
                        ))}
                      </div>
                    )}
                    {tags.length > 0 && (
                      <div className="card-tags">
                        {tags.map(t => <span key={t} className="tag">#{t}</span>)}
                      </div>
                    )}
                    <p className="card-date">{formatDate(recipe.post_date || recipe.created_at)}</p>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </main>

      {showManage && (
        <div className="modal-overlay" onClick={() => setShowManage(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Labels</h2>
              <button className="modal-close" onClick={() => setShowManage(false)}>✕</button>
            </div>
            <form className="modal-add-form" onSubmit={handleCreateLabel}>
              <input
                className="modal-input"
                type="text"
                placeholder="New label name…"
                value={newLabelName}
                onChange={e => setNewLabelName(e.target.value)}
                autoFocus
              />
              <button className="modal-add-btn" type="submit" disabled={!newLabelName.trim()}>
                Add
              </button>
            </form>
            {labelError && <p className="modal-error">{labelError}</p>}
            <ul className="modal-label-list">
              {labels.length === 0 ? (
                <li className="modal-empty">No labels yet.</li>
              ) : labels.map(label => (
                <li key={label.id} className="modal-label-item">
                  <span>{label.name}</span>
                  <button
                    className="modal-label-delete"
                    onClick={() => handleDeleteLabel(label.id)}
                    title="Delete label"
                  >✕</button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}
