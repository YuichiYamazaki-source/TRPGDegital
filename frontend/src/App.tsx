import { Routes, Route } from 'react-router-dom'
import LobbyPage from './pages/LobbyPage'
import CharacterCreatePage from './pages/CharacterCreatePage'
import PlayPage from './pages/PlayPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LobbyPage />} />
      <Route path="/character/new" element={<CharacterCreatePage />} />
      <Route path="/session/:sessionId" element={<PlayPage />} />
    </Routes>
  )
}
