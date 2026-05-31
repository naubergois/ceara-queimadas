import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { Flame, Map, BarChart3, Bell, MessageSquare, FileText, Satellite, BookOpen } from 'lucide-react'
import DashboardPage from './pages/DashboardPage'
import MapaPage from './pages/MapaPage'
import MapaRealPage from './pages/MapaRealPage'
import AlertasPage from './pages/AlertasPage'
import ChatPage from './pages/ChatPage'
import GuiaPage from './pages/GuiaPage'
import BoletimPage from './pages/BoletimPage'
import { clsx } from 'clsx'

const navItems = [
  { to: '/',          label: 'Dashboard',    icon: BarChart3 },
  { to: '/mapa-real', label: 'Mapa Real',    icon: Satellite },
  { to: '/mapa',      label: 'Mapa',         icon: Map },
  { to: '/alertas',   label: 'Alertas',      icon: Bell },
  { to: '/guia',       label: 'Guia',         icon: BookOpen },
  { to: '/chat',      label: 'Chat IA',      icon: MessageSquare },
  { to: '/boletim',   label: 'Boletim',      icon: FileText },
]

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen overflow-hidden">
        {/* Sidebar */}
        <aside className="w-16 lg:w-56 bg-gray-900 border-r border-gray-800 flex flex-col shrink-0">
          {/* Logo */}
          <div className="flex items-center gap-2 px-4 py-5 border-b border-gray-800">
            <Flame className="text-orange-500 shrink-0" size={24} />
            <span className="hidden lg:block font-bold text-sm text-white leading-tight">
              Gêmeo Digital<br />
              <span className="text-orange-400 font-normal">Ceará Queimadas</span>
            </span>
          </div>

          {/* Nav */}
          <nav className="flex-1 py-4 space-y-1 px-2">
            {navItems.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  clsx(
                    'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors',
                    isActive
                      ? 'bg-orange-600 text-white'
                      : 'text-gray-400 hover:bg-gray-800 hover:text-white',
                  )
                }
              >
                <Icon size={18} className="shrink-0" />
                <span className="hidden lg:block">{label}</span>
              </NavLink>
            ))}
          </nav>

          {/* Badge "Dados Reais" */}
          <div className="px-3 pb-2">
            <div className="hidden lg:flex items-center gap-1.5 bg-green-950 border border-green-800 rounded-lg px-2 py-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse shrink-0" />
              <span className="text-xs text-green-400 font-medium">Dados Reais</span>
            </div>
          </div>

          {/* Status */}
          <div className="px-4 py-3 border-t border-gray-800">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
              <span className="hidden lg:block text-xs text-gray-400">Sistema ativo</span>
            </div>
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-auto bg-gray-950">
          <Routes>
            <Route path="/"          element={<DashboardPage />} />
            <Route path="/mapa-real" element={<MapaRealPage />} />
            <Route path="/mapa"      element={<MapaPage />} />
            <Route path="/alertas"   element={<AlertasPage />} />
            <Route path="/guia"       element={<GuiaPage />} />
            <Route path="/chat"      element={<ChatPage />} />
            <Route path="/boletim"   element={<BoletimPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
