const BASE = 'http://localhost:8000'

export async function fetchRecipes(search = '', labelId = null) {
  const params = new URLSearchParams()
  if (search) params.set('search', search)
  if (labelId != null) params.set('label_id', labelId)
  const q = params.toString() ? `?${params}` : ''
  const res = await fetch(`${BASE}/api/recipes${q}`)
  if (!res.ok) throw new Error('Failed to fetch recipes')
  return res.json()
}

export async function fetchRecipe(id) {
  const res = await fetch(`${BASE}/api/recipes/${id}`)
  if (!res.ok) throw new Error('Recipe not found')
  return res.json()
}

export async function addRecipe(url) {
  const res = await fetch(`${BASE}/api/recipes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to add recipe')
  }
  return res.json()
}

export async function deleteRecipe(id) {
  const res = await fetch(`${BASE}/api/recipes/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('Failed to delete recipe')
  return res.json()
}

export function mediaUrl(path) {
  if (!path) return null
  if (path.startsWith('http')) return path
  return `${BASE}${path}`
}

export async function fetchLabels() {
  const res = await fetch(`${BASE}/api/labels`)
  if (!res.ok) throw new Error('Failed to fetch labels')
  return res.json()
}

export async function createLabel(name) {
  const res = await fetch(`${BASE}/api/labels`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to create label')
  }
  return res.json()
}

export async function deleteLabel(id) {
  const res = await fetch(`${BASE}/api/labels/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('Failed to delete label')
  return res.json()
}

export async function setRecipeLabels(recipeId, labelIds) {
  const res = await fetch(`${BASE}/api/recipes/${recipeId}/labels`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ label_ids: labelIds }),
  })
  if (!res.ok) throw new Error('Failed to update labels')
  return res.json()
}

export async function updateRecipeTags(recipeId, tags) {
  const res = await fetch(`${BASE}/api/recipes/${recipeId}/tags`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tags }),
  })
  if (!res.ok) throw new Error('Failed to update tags')
  return res.json()
}
