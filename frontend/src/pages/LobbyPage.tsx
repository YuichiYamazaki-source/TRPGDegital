import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { sessions as sessionsApi } from '../api/client'
import { useAppStore } from '../store'
import type { Session } from '../types'

export default function LobbyPage() {
  const navigate = useNavigate()
  const { sessions, setSessions, setCurrentSession } = useAppStore()
  const [newName, setNewName] = useState('')
  const [loading, setLoading] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  useEffect(() => {
    sessionsApi.list().then((r) => setSessions(r.data)).catch(console.error)
  }, [setSessions])

  const deleteSession = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    if (!confirm('このセッションを削除しますか？')) return
    setDeletingId(id)
    try {
      await sessionsApi.delete(id)
      setSessions(sessions.filter((s) => s.id !== id))
    } catch (err) {
      console.error('削除失敗:', err)
      alert('削除に失敗しました。もう一度お試しください。')
    } finally {
      setDeletingId(null)
    }
  }

  const createSession = async () => {
    if (!newName.trim()) return
    setLoading(true)
    try {
      const r = await sessionsApi.create(newName.trim())
      const session: Session = r.data
      setSessions([session, ...sessions])
      setNewName('')
    } finally {
      setLoading(false)
    }
  }

  const joinSession = (session: Session) => {
    setCurrentSession(session)
    navigate(`/session/${session.id}`)
  }

  return (
    <div className="min-h-full flex flex-col items-center justify-center p-8">
      <h1 className="text-4xl font-serif text-gold mb-2 tracking-widest">TRPG VTT</h1>
      <p className="text-ash mb-12 text-sm tracking-wider">VIRTUAL TABLETOP</p>

      {/* Create session */}
      <div className="bg-shadow border border-mist rounded-lg p-6 w-full max-w-md mb-8">
        <h2 className="text-bone text-lg mb-4">新しいセッション</h2>
        <div className="flex gap-2">
          <input
            className="flex-1 bg-abyss border border-mist rounded px-3 py-2 text-bone placeholder-ash focus:outline-none focus:border-gold"
            placeholder="セッション名"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && createSession()}
          />
          <button
            className="bg-gold text-void px-4 py-2 rounded font-bold hover:opacity-80 disabled:opacity-40"
            onClick={createSession}
            disabled={loading || !newName.trim()}
          >
            作成
          </button>
        </div>
      </div>

      {/* Session list */}
      {sessions.length > 0 && (
        <div className="w-full max-w-md">
          <h2 className="text-ash text-sm mb-3 tracking-wider">既存のセッション</h2>
          <ul className="space-y-2">
            {sessions.map((s) => (
              <li key={s.id} className="flex gap-2">
                <button
                  className="flex-1 text-left bg-shadow border border-mist rounded px-4 py-3 hover:border-gold transition-colors"
                  onClick={() => joinSession(s)}
                >
                  <p className="text-bone">{s.name}</p>
                  <p className="text-ash text-xs mt-1">{new Date(s.created_at).toLocaleString('ja-JP')}</p>
                </button>
                <button
                  className="px-3 bg-shadow border border-mist rounded text-ash hover:border-crimson hover:text-crimson transition-colors disabled:opacity-40"
                  onClick={(e) => deleteSession(e, s.id)}
                  disabled={deletingId === s.id}
                  title="削除"
                >
                  {deletingId === s.id ? '...' : '✕'}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <button
        className="mt-8 text-ash text-sm underline hover:text-bone"
        onClick={() => navigate('/character/new')}
      >
        キャラクターを作成する
      </button>
    </div>
  )
}
