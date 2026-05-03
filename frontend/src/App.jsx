import { useState, useEffect } from 'react'
import RecipeGrid from './pages/RecipeGrid.jsx'
import RecipeDetail from './pages/RecipeDetail.jsx'
import './App.css'

export default function App() {
  const [view, setView] = useState('grid')   // 'grid' | 'detail'
  const [selectedId, setSelectedId] = useState(null)

  useEffect(() => {
    const down = () => document.body.classList.add('is-clicking')
    const up = () => document.body.classList.remove('is-clicking')
    document.addEventListener('mousedown', down)
    document.addEventListener('mouseup', up)
    return () => {
      document.removeEventListener('mousedown', down)
      document.removeEventListener('mouseup', up)
    }
  }, [])

  function openRecipe(id) {
    setSelectedId(id)
    setView('detail')
  }

  function goBack() {
    setView('grid')
    setSelectedId(null)
  }

  return (
    <div className="app">
      {view === 'grid' ? (
        <RecipeGrid onOpen={openRecipe} />
      ) : (
        <RecipeDetail id={selectedId} onBack={goBack} />
      )}
    </div>
  )
}
