/**
 * GuiaPage — chat que explica a pesquisa e o funcionamento da aplicação (FAISS + RAG).
 */

import ChatPesquisa from '../components/ChatPesquisa'

export default function GuiaPage() {
  return (
    <div className="flex flex-col h-full">
      <div className="px-6 py-4 border-b border-gray-800">
        <h1 className="text-lg font-bold text-white">Guia da Aplicação</h1>
        <p className="text-sm text-gray-400">
          Chat com índice FAISS sobre a pesquisa, arquitetura, fontes de dados e uso do gêmeo digital
        </p>
      </div>
      <div className="flex-1 overflow-hidden">
        <ChatPesquisa />
      </div>
    </div>
  )
}
