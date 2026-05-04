export interface Session {
  id: string
  name: string
  created_at: string
}

export interface CoCStats {
  str: number
  con: number
  siz: number
  dex: number
  app: number
  int: number
  pow: number
  edu: number
}

export interface CoCCharacter {
  // Basic info
  name: string
  occupation: string
  age: number
  background: string

  // Stats
  stats: CoCStats

  // Derived values
  hp: number
  hp_max: number
  mp: number
  mp_max: number
  san: number
  san_max: number
  luck: number
  move: number

  // Skills: key = skill name, value = percentage
  skills: Record<string, number>
}

export interface Character {
  id: string
  session_id: string | null
  name: string
  data: CoCCharacter
  created_at: string
}

export interface Token {
  id: string
  character_id: string | null
  name: string
  x: number
  y: number
  color: string
}
