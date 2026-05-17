import { useState } from 'react'
import RecipeGrid from './pages/RecipeGrid.jsx'
import RecipeDetail from './pages/RecipeDetail.jsx'
import './App.css'

export default function App() {
  const [view, setView] = useState('grid')   // 'grid' | 'detail'
  const [selectedId, setSelectedId] = useState(null)

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
