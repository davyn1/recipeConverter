const BASE = 'http://localhost:8000'

export async function fetchRecipes(search = '') {
  const q = search ? `?search=${encodeURIComponent(search)}` : ''
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
