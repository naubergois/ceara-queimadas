import { useState } from "react";
import { motion } from "framer-motion";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, AreaChart, Area, BarChart, Bar,
} from "recharts";

const modelComparisonData = [
  { time: "t+1", rothermel: 0.72, cnn: 0.81, gnn: 0.85, neko: 0.92 },
  { time: "t+2", rothermel: 0.65, cnn: 0.76, gnn: 0.81, neko: 0.89 },
  { time: "t+3", rothermel: 0.58, cnn: 0.70, gnn: 0.77, neko: 0.86 },
  { time: "t+4", rothermel: 0.50, cnn: 0.63, gnn: 0.72, neko: 0.83 },
  { time: "t+5", rothermel: 0.42, cnn: 0.55, gnn: 0.66, neko: 0.79 },
  { time: "t+6", rothermel: 0.35, cnn: 0.48, gnn: 0.60, neko: 0.75 },
];

const modosKoopmanData = [
  { name: "Modo-1 (64%)", value: 64 },
  { name: "Modo-2 (18%)", value: 18 },
  { name: "Modo-3 (8%)", value: 8 },
  { name: "Modo-4 (5%)", value: 5 },
  { name: "Modo-5 (3%)", value: 3 },
  { name: "Outros (2%)", value: 2 },
];

const FadeIn = ({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) => (
  <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay }}>
    {children}
  </motion.div>
);

export default function InovacaoPage() {
  const [vento, setVento] = useState(5);
  const [vegetacao, setVegetacao] = useState(70);
  const [riscoSimulado, setRiscoSimulado] = useState<number | null>(null);

  const simularIntervencao = () => {
    const base = 0.45;
    const ventoFactor = (vento - 5) * 0.04;
    const vegFactor = (70 - vegetacao) * 0.005;
    const risco = Math.min(0.95, Math.max(0.05, base + ventoFactor + vegFactor));
    setRiscoSimulado(risco);
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-gradient-to-br from-[#0a0a1a] via-[#0d1117] to-[#0a0a1a] text-white p-6">
      {/* Header */}
      <FadeIn>
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-[#f5c518] to-[#e94560] flex items-center justify-center text-lg font-bold">
            I
          </div>
          <div>
            <h1 className="text-2xl font-bold">Inovação — NeKo-PIGNN</h1>
            <p className="text-gray-400 text-sm">Neural Koopman + Physics-Informed GNN para Gêmeo Digital de Queimadas</p>
          </div>
        </div>
      </FadeIn>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 mb-6">
        {/* Card: Métricas */}
        <FadeIn delay={0.1}>
          <div className="bg-[#111122] border border-gray-800 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Métricas do Modelo</h2>
            <div className="grid grid-cols-2 gap-4">
              {[
                { label: "RMSE", value: "0.124", color: "text-green-400" },
                { label: "MAE", value: "0.087", color: "text-green-400" },
                { label: "R²", value: "0.892", color: "text-blue-400" },
                { label: "IoU", value: "0.763", color: "text-yellow-400" },
                { label: "F1-Score", value: "0.914", color: "text-purple-400" },
                { label: "Inferência", value: "43ms", color: "text-cyan-400" },
              ].map((m) => (
                <div key={m.label} className="bg-[#0d1117] rounded-lg p-3 text-center">
                  <div className="text-xs text-gray-500">{m.label}</div>
                  <div className={`text-xl font-bold ${m.color}`}>{m.value}</div>
                </div>
              ))}
            </div>
          </div>
        </FadeIn>

        {/* Card: Modos Coerentes */}
        <FadeIn delay={0.2}>
          <div className="bg-[#111122] border border-gray-800 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Modos Coerentes de Koopman</h2>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={modosKoopmanData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis type="number" tick={{ fill: "#9ca3af", fontSize: 11 }} domain={[0, 100]} />
                <YAxis type="category" dataKey="name" tick={{ fill: "#9ca3af", fontSize: 10 }} width={80} />
                <Tooltip contentStyle={{ backgroundColor: "#1a1a2e", border: "1px solid #333", borderRadius: 8 }} />
                <Bar dataKey="value" fill="#f5c518" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
            <p className="text-xs text-gray-500 mt-2">Auto-funções de Koopman — Modo-1 captura 64% da variância</p>
          </div>
        </FadeIn>

        {/* Card: Simulador Causal */}
        <FadeIn delay={0.3}>
          <div className="bg-[#111122] border border-gray-800 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Simulador "E se...?"</h2>
            <div className="space-y-4">
              <div>
                <label className="text-xs text-gray-400">Velocidade do Vento: {vento} m/s</label>
                <input type="range" min={0} max={15} value={vento} onChange={(e) => setVento(Number(e.target.value))}
                  className="w-full accent-yellow-500" />
              </div>
              <div>
                <label className="text-xs text-gray-400">Cobertura Vegetal: {vegetacao}%</label>
                <input type="range" min={10} max={100} value={vegetacao} onChange={(e) => setVegetacao(Number(e.target.value))}
                  className="w-full accent-green-500" />
              </div>
              <button onClick={simularIntervencao}
                className="w-full py-2 bg-gradient-to-r from-[#f5c518] to-[#e94560] rounded-lg font-semibold text-sm hover:opacity-90 transition">
                Simular Intervenção
              </button>
              {riscoSimulado !== null && (
                <div className="text-center p-3 bg-[#0d1117] rounded-lg">
                  <span className="text-xs text-gray-400">Risco Predito:</span>
                  <div className={`text-2xl font-bold ${riscoSimulado > 0.7 ? 'text-red-400' : riscoSimulado > 0.4 ? 'text-yellow-400' : 'text-green-400'}`}>
                    {(riscoSimulado * 100).toFixed(1)}%
                  </div>
                </div>
              )}
            </div>
          </div>
        </FadeIn>
      </div>

      {/* Timeline de Propagação */}
      <FadeIn delay={0.4}>
        <div className="bg-[#111122] border border-gray-800 rounded-xl p-5 mb-6">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Timeline de Propagação — Previsão NeKo-PIGNN</h2>
          <div className="flex items-center gap-2 mb-4">
            {["Agora", "+2h", "+4h", "+6h", "+8h", "+10h", "+12h"].map((label, i) => {
              const intensity = 0.2 + i * 0.1;
              return (
                <div key={label} className="flex-1 text-center">
                  <div className="h-20 rounded-lg bg-gradient-to-t" style={{
                    background: `linear-gradient(to top, rgba(233,69,96,${intensity}), rgba(245,197,24,${intensity * 0.3}))`,
                    opacity: 0.6 + i * 0.05,
                  }} />
                  <div className="text-xs text-gray-500 mt-1">{label}</div>
                </div>
              );
            })}
          </div>
        </div>
      </FadeIn>

      {/* Comparação de Modelos */}
      <FadeIn delay={0.5}>
        <div className="bg-[#111122] border border-gray-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Comparação de Modelos (F1 × Tempo)</h2>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={modelComparisonData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="time" tick={{ fill: "#9ca3af", fontSize: 11 }} />
              <YAxis domain={[0, 1]} tick={{ fill: "#9ca3af", fontSize: 11 }} />
              <Tooltip contentStyle={{ backgroundColor: "#1a1a2e", border: "1px solid #333", borderRadius: 8 }} />
              <Legend />
              <Line type="monotone" dataKey="rothermel" stroke="#8884d8" strokeWidth={2} dot={{ r: 3 }} name="Rothermel" />
              <Line type="monotone" dataKey="cnn" stroke="#82ca9d" strokeWidth={2} dot={{ r: 3 }} name="CNN U-Net" />
              <Line type="monotone" dataKey="gnn" stroke="#ffc658" strokeWidth={2} dot={{ r: 3 }} name="GNN pura" />
              <Line type="monotone" dataKey="neko" stroke="#e94560" strokeWidth={3} dot={{ r: 4 }} name="NeKo-PIGNN" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </FadeIn>
    </div>
  );
}
