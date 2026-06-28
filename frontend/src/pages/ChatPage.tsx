/**
 * ChatPage — interface de chat com o agente LangChain ReAct.
 */

import ChatAgente from '../components/ChatAgente'

export default function ChatPage() {
  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-200">
        <h1 className="text-lg font-bold text-slate-900">AI Agent Chat</h1>
        <p className="text-sm text-slate-500">
          Query hotspots, risks, GOES-16, and weather data in natural language
        </p>
      </div>

      {/* Chat */}
      <div className="flex-1 overflow-hidden">
        <ChatAgente />
      </div>
    </div>
  )
}
