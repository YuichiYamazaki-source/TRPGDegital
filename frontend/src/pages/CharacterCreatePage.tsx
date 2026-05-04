import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { CoCStats } from '../types'

const INITIAL_STATS: CoCStats = {
  str: 50, con: 50, siz: 50, dex: 50,
  app: 50, int: 50, pow: 50, edu: 60,
}

const DEFAULT_SKILLS: Record<string, number> = {
  '図書館': 25, '目星': 25, '聞き耳': 20, '心理学': 10,
  '説得': 15, '言いくるめ': 5, '回避': 25, '拳銃': 20,
  '応急手当': 30, '運転（自動車）': 20, '鍵開け': 1,
  '写真術': 10, '歴史': 20, 'オカルト': 5,
}

const STAT_LABELS: { key: keyof CoCStats; label: string }[] = [
  { key: 'str', label: 'STR 筋力' },
  { key: 'con', label: 'CON 体力' },
  { key: 'siz', label: 'SIZ 体格' },
  { key: 'dex', label: 'DEX 敏捷' },
  { key: 'app', label: 'APP 外見' },
  { key: 'int', label: 'INT 知性' },
  { key: 'pow', label: 'POW 精神' },
  { key: 'edu', label: 'EDU 教育' },
]

function rollDice(count: number, sides: number): number {
  return Array.from({ length: count }, () => Math.floor(Math.random() * sides) + 1)
    .reduce((a, b) => a + b, 0)
}

function deriveStats(stats: CoCStats) {
  const hp_max = Math.floor((stats.con + stats.siz) / 10)
  const mp_max = Math.floor(stats.pow / 5)
  const san_max = stats.pow * 5
  const move = stats.str < stats.siz && stats.dex < stats.siz ? 7
    : stats.str > stats.siz && stats.dex > stats.siz ? 9 : 8
  return { hp_max, mp_max, san_max, move }
}

export default function CharacterCreatePage() {
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [occupation, setOccupation] = useState('')
  const [age, setAge] = useState(25)
  const [background, setBackground] = useState('')
  const [stats, setStats] = useState<CoCStats>(INITIAL_STATS)
  const [skills, setSkills] = useState<Record<string, number>>(DEFAULT_SKILLS)

  const derived = deriveStats(stats)

  const generateStats = () => {
    setStats({
      str: rollDice(3, 6) * 5,
      con: rollDice(3, 6) * 5,
      siz: (rollDice(2, 6) + 6) * 5,
      dex: rollDice(3, 6) * 5,
      app: rollDice(3, 6) * 5,
      int: (rollDice(2, 6) + 6) * 5,
      pow: rollDice(3, 6) * 5,
      edu: (rollDice(2, 6) + 6) * 5,
    })
  }

  const setStat = (key: keyof CoCStats, value: number) =>
    setStats((prev) => ({ ...prev, [key]: Math.min(99, Math.max(1, value)) }))
  const setSkillValue = (skill: string, value: number) =>
    setSkills((prev) => ({ ...prev, [skill]: Math.min(99, Math.max(1, value)) }))

  return (
    <div className="min-h-full p-6 max-w-4xl mx-auto">
      <div className="flex items-center gap-4 mb-8">
        <button onClick={() => navigate('/')} className="text-ash hover:text-bone text-sm">← 戻る</button>
        <h1 className="text-2xl text-gold tracking-wider">探索者作成</h1>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <section className="bg-shadow border border-mist rounded-lg p-5">
          <h2 className="text-bone mb-4 text-sm tracking-wider border-b border-mist pb-2">基本情報</h2>
          <div className="space-y-3">
            {[
              { label: '探索者名', value: name, set: setName },
              { label: '職業', value: occupation, set: setOccupation },
            ].map(({ label, value, set }) => (
              <div key={label}>
                <label className="block text-ash text-xs mb-1">{label}</label>
                <input
                  className="w-full bg-abyss border border-mist rounded px-3 py-2 text-bone focus:outline-none focus:border-gold"
                  value={value} onChange={(e) => set(e.target.value as never)}
                />
              </div>
            ))}
            <div>
              <label className="block text-ash text-xs mb-1">年齢</label>
              <input type="number" min={15} max={90}
                className="w-full bg-abyss border border-mist rounded px-3 py-2 text-bone focus:outline-none focus:border-gold"
                value={age} onChange={(e) => setAge(Number(e.target.value))}
              />
            </div>
            <div>
              <label className="block text-ash text-xs mb-1">バックグラウンド</label>
              <textarea
                className="w-full bg-abyss border border-mist rounded px-3 py-2 text-bone focus:outline-none focus:border-gold h-24 resize-none"
                value={background} onChange={(e) => setBackground(e.target.value)}
              />
            </div>
          </div>
        </section>

        <section className="bg-shadow border border-mist rounded-lg p-5">
          <div className="flex items-center justify-between border-b border-mist pb-2 mb-4">
            <h2 className="text-bone text-sm tracking-wider">能力値</h2>
            <button
              type="button"
              onClick={generateStats}
              className="text-xs bg-gold text-void px-3 py-1 rounded font-bold hover:opacity-80 transition-opacity"
            >
              ダイスで自動生成
            </button>
          </div>
          <div className="space-y-2">
            {STAT_LABELS.map(({ key, label }) => (
              <div key={key} className="flex items-center gap-3">
                <span className="text-ash text-xs w-24">{label}</span>
                <input type="number" min={1} max={99}
                  className="w-16 bg-abyss border border-mist rounded px-2 py-1 text-bone text-center focus:outline-none focus:border-gold"
                  value={stats[key]} onChange={(e) => setStat(key, Number(e.target.value))}
                />
                <div className="flex-1 h-1.5 bg-abyss rounded overflow-hidden">
                  <div className="h-full bg-gold rounded" style={{ width: `${stats[key]}%` }} />
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
            {([['HP', derived.hp_max], ['MP', derived.mp_max], ['SAN', derived.san_max], ['幸運', stats.pow * 5], ['移動力', derived.move]] as [string, number][]).map(([label, val]) => (
              <div key={label} className="bg-abyss rounded px-3 py-2 flex justify-between">
                <span className="text-ash">{label}</span>
                <span className="text-gold font-mono">{val}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="bg-shadow border border-mist rounded-lg p-5 md:col-span-2">
          <h2 className="text-bone mb-4 text-sm tracking-wider border-b border-mist pb-2">技能</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(skills).map(([skill, val]) => (
              <div key={skill} className="flex items-center gap-2">
                <span className="text-ash text-xs flex-1 truncate">{skill}</span>
                <input type="number" min={1} max={99}
                  className="w-14 bg-abyss border border-mist rounded px-2 py-1 text-bone text-center text-sm focus:outline-none focus:border-gold"
                  value={val} onChange={(e) => setSkillValue(skill, Number(e.target.value))}
                />
              </div>
            ))}
          </div>
        </section>
      </div>

      <div className="mt-6 flex justify-end">
        <button
          disabled={!name.trim()}
          className="bg-gold text-void px-8 py-3 rounded font-bold hover:opacity-80 disabled:opacity-40"
          onClick={() => navigate('/')}
        >
          探索者を登録する（MOC）
        </button>
      </div>
    </div>
  )
}
