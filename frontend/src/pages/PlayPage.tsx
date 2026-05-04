import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

interface Token {
  id: string
  name: string
  x: number
  y: number
  color: string
}

interface DiceResult {
  dice: string
  result: number
  success?: boolean
}

const GRID = 20
const CELL = 40

export default function PlayPage() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const [tokens, setTokens] = useState<Token[]>([
    { id: '1', name: 'PC1', x: 2, y: 2, color: '#c9a84c' },
    { id: '2', name: 'NPC', x: 10, y: 8, color: '#8b1a1a' },
  ])
  const [dragging, setDragging] = useState<string | null>(null)
  const [chat, setChat] = useState<{ sender: string; text: string }[]>([
    { sender: 'System', text: 'セッション開始' },
  ])
  const [chatInput, setChatInput] = useState('')
  const [diceLog, setDiceLog] = useState<DiceResult[]>([])
  const [initiative, setInitiative] = useState<{ name: string; val: number }[]>([])
  const [sanValue, setSanValue] = useState(60)

  const rollDice = (sides: number) => {
    const result = Math.floor(Math.random() * sides) + 1
    const entry: DiceResult = { dice: `d${sides}`, result }
    if (sides === 100) entry.success = result <= sanValue
    setDiceLog((prev) => [entry, ...prev].slice(0, 20))
    setChat((prev) => [...prev, {
      sender: 'Dice',
      text: `d${sides}: ${result}${entry.success !== undefined ? (entry.success ? ' ✓成功' : ' ✗失敗') : ''}`,
    }])
  }

  const sendChat = () => {
    if (!chatInput.trim()) return
    setChat((prev) => [...prev, { sender: 'Player', text: chatInput.trim() }])
    setChatInput('')
  }

  const handleCellClick = (x: number, y: number) => {
    if (dragging) {
      setTokens((prev) => prev.map((t) => t.id === dragging ? { ...t, x, y } : t))
      setDragging(null)
    }
  }

  const addToInitiative = (name: string) => {
    const val = Math.floor(Math.random() * 100) + 1
    setInitiative((prev) => [...prev, { name, val }].sort((a, b) => b.val - a.val))
  }

  return (
    <div className="h-screen flex flex-col bg-void text-bone overflow-hidden">
      <header className="flex items-center gap-4 px-4 py-2 bg-abyss border-b border-mist shrink-0">
        <button onClick={() => navigate('/')} className="text-ash hover:text-bone text-sm">←</button>
        <span className="text-gold text-sm tracking-wider">SESSION: {sessionId?.slice(0, 8)}</span>
        <div className="ml-auto flex items-center gap-3 text-xs text-ash">
          <span>SAN</span>
          <input type="number" min={0} max={99}
            className="w-12 bg-shadow border border-mist rounded px-1 py-0.5 text-bone text-center focus:outline-none focus:border-gold"
            value={sanValue} onChange={(e) => setSanValue(Number(e.target.value))}
          />
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Map canvas */}
        <div className="flex-1 overflow-auto bg-void p-4">
          <div
            className="relative"
            style={{
              width: GRID * CELL,
              height: GRID * CELL,
              backgroundImage: `linear-gradient(rgba(42,42,61,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(42,42,61,0.5) 1px, transparent 1px)`,
              backgroundSize: `${CELL}px ${CELL}px`,
            }}
          >
            {Array.from({ length: GRID }, (_, y) =>
              Array.from({ length: GRID }, (_, x) => (
                <div
                  key={`${x}-${y}`}
                  className="absolute cursor-pointer hover:bg-mist hover:bg-opacity-30"
                  style={{ left: x * CELL, top: y * CELL, width: CELL, height: CELL }}
                  onClick={() => handleCellClick(x, y)}
                />
              ))
            )}
            {tokens.map((token) => (
              <div
                key={token.id}
                className={`absolute flex items-center justify-center rounded-full text-xs font-bold cursor-pointer border-2 transition-all select-none ${dragging === token.id ? 'opacity-50 scale-110' : 'hover:scale-105'}`}
                style={{
                  left: token.x * CELL + 4,
                  top: token.y * CELL + 4,
                  width: CELL - 8,
                  height: CELL - 8,
                  backgroundColor: token.color + '33',
                  borderColor: token.color,
                  color: token.color,
                }}
                onClick={(e) => { e.stopPropagation(); setDragging(dragging === token.id ? null : token.id) }}
              >
                {token.name.slice(0, 2)}
              </div>
            ))}
          </div>
        </div>

        {/* Right panel */}
        <div className="w-72 flex flex-col border-l border-mist bg-abyss shrink-0">
          {/* Dice roller */}
          <div className="p-3 border-b border-mist">
            <p className="text-ash text-xs mb-2 tracking-wider">DICE ROLLER</p>
            <div className="flex flex-wrap gap-1">
              {[4, 6, 8, 10, 12, 20, 100].map((d) => (
                <button
                  key={d}
                  className="bg-shadow border border-mist rounded px-2 py-1 text-xs hover:border-gold hover:text-gold transition-colors"
                  onClick={() => rollDice(d)}
                >
                  d{d}
                </button>
              ))}
            </div>
            {diceLog[0] && (
              <div className={`mt-2 text-center text-lg font-mono ${diceLog[0].success === true ? 'text-green-400' : diceLog[0].success === false ? 'text-crimson' : 'text-gold'}`}>
                {diceLog[0].dice}: {diceLog[0].result}
                {diceLog[0].success !== undefined && (
                  <span className="text-sm ml-2">{diceLog[0].success ? '成功' : '失敗'}</span>
                )}
              </div>
            )}
          </div>

          {/* Initiative tracker */}
          <div className="p-3 border-b border-mist">
            <p className="text-ash text-xs mb-2 tracking-wider">INITIATIVE</p>
            <div className="space-y-1 mb-2 max-h-24 overflow-y-auto">
              {initiative.map((entry, i) => (
                <div key={i} className="flex justify-between text-xs bg-shadow rounded px-2 py-1">
                  <span className="text-bone">{entry.name}</span>
                  <span className="text-gold font-mono">{entry.val}</span>
                </div>
              ))}
            </div>
            <div className="flex gap-1 flex-wrap">
              {tokens.map((t) => (
                <button
                  key={t.id}
                  className="text-xs bg-shadow border border-mist rounded px-2 py-1 hover:border-gold transition-colors"
                  style={{ color: t.color }}
                  onClick={() => addToInitiative(t.name)}
                >
                  {t.name}
                </button>
              ))}
              {initiative.length > 0 && (
                <button className="text-xs text-ash hover:text-crimson ml-auto" onClick={() => setInitiative([])}>
                  リセット
                </button>
              )}
            </div>
          </div>

          {/* Chat */}
          <div className="flex-1 flex flex-col overflow-hidden p-3">
            <p className="text-ash text-xs mb-2 tracking-wider">CHAT</p>
            <div className="flex-1 overflow-y-auto space-y-1 mb-2">
              {chat.map((msg, i) => (
                <div key={i} className="text-xs">
                  <span className="text-ash">{msg.sender}: </span>
                  <span className={msg.sender === 'Dice' ? 'text-gold' : 'text-bone'}>{msg.text}</span>
                </div>
              ))}
            </div>
            <div className="flex gap-1">
              <input
                className="flex-1 bg-shadow border border-mist rounded px-2 py-1 text-bone text-xs focus:outline-none focus:border-gold"
                placeholder="メッセージ..."
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && sendChat()}
              />
              <button onClick={sendChat} className="text-xs bg-gold text-void rounded px-2 py-1 hover:opacity-80">
                送信
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
