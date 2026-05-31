/**
 * ChatPage — interface de chat com o agente LangChain ReAct.
 */

import ChatAgente from '../components/ChatAgente'

export default function ChatPage() {
  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-800">
        <h1 className="text-lg font-bold text-white">Chat com Agente IA</h1>
        <p className="text-sm text-gray-400">
          Consulte focos, riscos, GOES-16 e dados climáticos em linguagem natural
        </p>
      </div>

      {/* Chat */}
      <div className="flex-1 overflow-hidden">
        <ChatAgente />
      </div>
    </div>
  )
}
