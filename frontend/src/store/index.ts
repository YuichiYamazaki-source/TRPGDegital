import { create } from 'zustand'
import type { Session, Character, Token } from '../types'

interface AppStore {
  sessions: Session[]
  setSessions: (s: Session[]) => void

  currentSession: Session | null
  setCurrentSession: (s: Session | null) => void

  characters: Character[]
  setCharacters: (c: Character[]) => void

  tokens: Token[]
  setTokens: (t: Token[]) => void
  moveToken: (id: string, x: number, y: number) => void
}

export const useAppStore = create<AppStore>((set) => ({
  sessions: [],
  setSessions: (sessions) => set({ sessions }),

  currentSession: null,
  setCurrentSession: (currentSession) => set({ currentSession }),

  characters: [],
  setCharacters: (characters) => set({ characters }),

  tokens: [],
  setTokens: (tokens) => set({ tokens }),
  moveToken: (id, x, y) =>
    set((state) => ({
      tokens: state.tokens.map((t) => (t.id === id ? { ...t, x, y } : t)),
    })),
}))
