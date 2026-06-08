import { useState } from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { Flame, Map, BarChart3, Bell, MessageSquare, FileText, Satellite } from 'lucide-react'
import MascoteGuia, { NOME_MASCOTE } from './components/MascoteGuia'
import DashboardPage from './pages/DashboardPage'
import InovacaoPage from './pages/InovacaoPage'
import MapaPage from './pages/MapaPage'
import MapaRealPage from './pages/MapaRealPage'
import AlertasPage from './pages/AlertasPage'
import ChatPage from './pages/ChatPage'
import BoletimPage from './pages/BoletimPage'
import DialogoGuiaPesquisa from './components/DialogoGuiaPesquisa'
import { clsx } from 'clsx'

const navItems = [
  { to: '/',          label: 'Dashboard',    icon: BarChart3 },
  { to: '/mapa-real', label: 'Mapa Real',    icon: Satellite },
  { to: '/mapa',      label: 'Mapa',         icon: Map },
  { to: '/alertas',   label: 'Alertas',      icon: Bell },
  { to: '/inovacao',  label: 'Predição IA',  icon: Flame },
  { to: '/chat',      label: 'Chat IA',      icon: MessageSquare },
  { to: '/boletim',   label: 'Boletim',      icon: FileText },
]

function AppShell() {
  const [guiaAberto, setGuiaAberto] = useState(false)

  const navClass = (isActive: boolean) =>
    clsx(
      'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all',
      isActive
        ? 'bg-fire-600 text-white shadow-sm'
        : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
    )

  return (
    <div className="flex h-screen overflow-hidden bg-surface-page">
      <aside className="w-16 lg:w-60 bg-white border-r border-slate-200 flex flex-col shrink-0 shadow-sm z-10">
        <div className="flex items-center gap-3 px-4 py-5 border-b border-slate-100">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-fire-500 to-fire-700 flex items-center justify-center shadow-sm shrink-0">
            <Flame className="text-white" size={22} />
          </div>
          <span className="hidden lg:block font-semibold text-sm text-slate-900 leading-tight">
            Gêmeo Digital
            <span className="block text-fire-600 font-medium text-xs mt-0.5">Ceará Queimadas</span>
          </span>
        </div>

        <nav className="flex-1 py-4 space-y-1 px-2">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => navClass(isActive)}>
              <Icon size={18} className="shrink-0" />
              <span className="hidden lg:block">{label}</span>
            </NavLink>
          ))}

          <div className="pt-2 mt-2 border-t border-slate-100">
            <button
              type="button"
              onClick={() => setGuiaAberto(true)}
              className={clsx(
                'w-full rounded-2xl border-2 transition-all text-left overflow-hidden',
                guiaAberto
                  ? 'border-violet-500 bg-violet-600 shadow-md'
                  : 'border-violet-200 bg-gradient-to-br from-violet-50 via-white to-orange-50 hover:border-violet-400 hover:shadow-soft',
              )}
              aria-label={`Abrir guia com ${NOME_MASCOTE}`}
            >
              <div className="flex items-center gap-2 px-2 py-2.5 lg:px-3 lg:py-3">
                <MascoteGuia
                  size={40}
                  animado={!guiaAberto}
                  className="shrink-0 drop-shadow-sm"
                />
                <div className="hidden lg:block min-w-0 flex-1">
                  <p
                    className={clsx(
                      'text-sm font-bold leading-tight',
                      guiaAberto ? 'text-white' : 'text-violet-900',
                    )}
                  >
                    {NOME_MASCOTE}
                  </p>
                  <p
                    className={clsx(
                      'text-[11px] font-medium leading-tight mt-0.5',
                      guiaAberto ? 'text-violet-100' : 'text-violet-600',
                    )}
                  >
                    Guia cearense
                  </p>
                </div>
                <span
                  className={clsx(
                    'hidden lg:inline text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full shrink-0',
                    guiaAberto
                      ? 'bg-white/20 text-white'
                      : 'bg-violet-600 text-white',
                  )}
                >
                  Ajuda
                </span>
              </div>
            </button>
          </div>
        </nav>

        <div className="px-3 pb-3">
          <div className="hidden lg:flex items-center gap-2 bg-emerald-50 border border-emerald-200 rounded-xl px-3 py-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shrink-0" />
            <span className="text-xs text-emerald-800 font-medium">Dados em tempo real</span>
          </div>
        </div>

        <div className="px-4 py-4 border-t border-slate-100">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span className="hidden lg:block text-xs text-slate-500">Sistema ativo</span>
          </div>
        </div>
      </aside>

      <main className="flex-1 overflow-auto min-w-0">
        <Routes>
          <Route path="/"          element={<DashboardPage />} />
          <Route path="/mapa-real" element={<MapaRealPage />} />
          <Route path="/mapa"      element={<MapaPage />} />
          <Route path="/alertas"   element={<AlertasPage />} />
          <Route path="/chat"      element={<ChatPage />} />
          <Route path="/boletim"   element={<BoletimPage />} />
          <Route path="/inovacao"  element={<InovacaoPage />} />
        </Routes>
      </main>

      <DialogoGuiaPesquisa
        aberto={guiaAberto}
        onAbrir={() => setGuiaAberto(true)}
        onFechar={() => setGuiaAberto(false)}
      />
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  )
}
