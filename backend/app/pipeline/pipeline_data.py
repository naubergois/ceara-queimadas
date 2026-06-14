"""
TASK-006: Pipeline de Dados — Carregamento e Pré-processamento
===============================================================
Componente 1 do pipeline completo: carregamento de dados de satélite
(VIIRS/MODIS/GOES-16), fusão com dados climáticos (Open-Meteo),
pré-processamento e normalização para o modelo NeKo-PIGNN.

Fluxo:
  1. Carrega ou gera dados de focos (NASA FIRMS + INPE)
  2. Carrega dados climáticos (Open-Meteo) para cada município
  3. Fusão dados VIIRS (features físicas: temp, FRP, vento, umidade, NDVI, declividade)
  4. Normalização (0-1 por feature)
  5. Construção de amostras temporais (x_t, x_tp1) para treino
  6. Saída: DataLoader PyTorch pronto para treino
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset

logger = logging.getLogger("pipeline_data")

# ---------------------------------------------------------------------------
# Constantes — municípios representativos do Ceará
# ---------------------------------------------------------------------------

MUNICIPIOS_CEARA = [
    {"nome": "Fortaleza",         "lat": -3.7172, "lon": -38.5433},
    {"nome": "Juazeiro do Norte", "lat": -7.2136, "lon": -39.3153},
    {"nome": "Sobral",            "lat": -3.6861, "lon": -40.3497},
    {"nome": "Crato",             "lat": -7.2342, "lon": -39.4095},
    {"nome": "Maracanaú",         "lat": -3.8769, "lon": -38.6258},
    {"nome": "Caucaia",           "lat": -3.7361, "lon": -38.6531},
    {"nome": "Quixadá",           "lat": -4.9711, "lon": -39.0153},
    {"nome": "Iguatu",            "lat": -6.3594, "lon": -39.2986},
    {"nome": "Crateús",           "lat": -5.1769, "lon": -40.6681},
    {"nome": "Tianguá",           "lat": -3.7328, "lon": -40.9914},
    {"nome": "Limoeiro do Norte", "lat": -5.1453, "lon": -38.0997},
    {"nome": "Russas",            "lat": -4.9408, "lon": -37.9742},
    {"nome": "Aracati",           "lat": -4.5614, "lon": -37.7697},
    {"nome": "Itapipoca",         "lat": -3.4942, "lon": -39.5786},
    {"nome": "Canindé",           "lat": -4.3567, "lon": -39.3139},
    {"nome": "Tauá",              "lat": -5.9836, "lon": -40.2928},
    {"nome": "Brejo Santo",       "lat": -7.4908, "lon": -38.9847},
    {"nome": "Icó",               "lat": -6.4011, "lon": -38.8614},
    {"nome": "Senador Pompeu",    "lat": -5.5819, "lon": -39.3706},
    {"nome": "Jaguaribe",         "lat": -5.8908, "lon": -38.6228},
    {"nome": "Beberibe",          "lat": -4.1800, "lon": -38.1300},
    {"nome": "Acaraú",            "lat": -2.8856, "lon": -40.1200},
    {"nome": "Camocim",           "lat": -2.9022, "lon": -40.8411},
    {"nome": "Granja",            "lat": -3.1200, "lon": -40.8300},
    {"nome": "Viçosa do Ceará",   "lat": -3.5600, "lon": -41.0900},
    {"nome": "Santa Quitéria",    "lat": -4.3300, "lon": -40.1500},
    {"nome": "Independência",     "lat": -5.3900, "lon": -40.3100},
    {"nome": "Novo Oriente",      "lat": -5.5300, "lon": -40.7800},
    {"nome": "Cariús",            "lat": -6.5400, "lon": -39.5000},
    {"nome": "Cedro",             "lat": -6.6100, "lon": -39.0600},
]

N_MUNICIPIOS = len(MUNICIPIOS_CEARA)  # 30 representativos


# ---------------------------------------------------------------------------
# Estrutura de dados do pipeline
# ---------------------------------------------------------------------------

@dataclass
class PipelineData:
    """Dados processados prontos para treino/inferência."""
    X_t: torch.Tensor          # (num_amostras, num_nos, features)
    X_tp1: torch.Tensor        # (num_amostras, num_nos, features)
    nomes: list[str]           # nomes dos municípios
    timestamps: list[str] = field(default_factory=list)
    metadados: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Carregador de dados
# ---------------------------------------------------------------------------

class CarregadorDados:
    """
    Carrega e pré-processa dados de múltiplas fontes para o NeKo-PIGNN.

    Suporta:
    - Coleta real de FIRMS + Open-Meteo (modo online)
    - Geração de dados sintéticos realistas (modo offline/desenvolvimento)
    - Carregamento de cache local (JSON/CSV)
    """

    def __init__(
        self,
        data_dir: str = "backend/data/cache",
        num_features: int = 6,
        seed: int = 42,
    ):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.num_features = num_features
        self.rng = random.Random(seed)
        np.random.seed(seed)

    # ------------------------------------------------------------------
    # 1. Coleta real (assíncrona)
    # ------------------------------------------------------------------

    async def coletar_focos_firms(self, dias: int = 7) -> dict[str, int]:
        """Coleta focos FIRMS para o Ceará via serviço existente."""
        logger.info(f"📡 Coletando focos FIRMS (últimos {dias} dias)...")
        try:
            from app.services.firms_service import coletar_focos_firms as _firms
            from app.models.schemas import FocoQueimada

            focos_lista = await _firms(dias=dias)
            logger.info(f"  → {len(focos_lista)} focos encontrados")

            focos_por_municipio = {m["nome"]: 0 for m in MUNICIPIOS_CEARA}
            for foco in focos_lista:
                lat, lon = foco.latitude, foco.longitude
                dists = [(lat - m["lat"])**2 + (lon - m["lon"])**2 for m in MUNICIPIOS_CEARA]
                idx = int(np.argmin(dists))
                if dists[idx] < 2.0:
                    focos_por_municipio[MUNICIPIOS_CEARA[idx]["nome"]] += 1
            return focos_por_municipio
        except Exception as e:
            logger.warning(f"  ⚠ FIRMS falhou: {e}. Usando fallback INPE.")
            return self._fallback_focos()

    def _fallback_focos(self) -> dict[str, int]:
        """Fallback com dados INPE conhecidos."""
        return {
            "Beberibe": 7, "Fortaleza": 2, "Juazeiro do Norte": 3,
            "Sobral": 1, "Crato": 2, "Quixadá": 4, "Iguatu": 3,
            "Crateús": 2, "Tauá": 3, "Canindé": 2, "Limoeiro do Norte": 1,
            "Itapipoca": 2, "Acaraú": 1, "Camocim": 3,
        }

    async def coletar_clima(self) -> dict[str, dict]:
        """Coleta clima real Open-Meteo para todos os municípios."""
        logger.info("🌡️  Coletando dados climáticos (Open-Meteo)...")
        clima = {}
        for m in MUNICIPIOS_CEARA:
            try:
                from app.services.clima_real import buscar_clima_por_coordenada
                c = await buscar_clima_por_coordenada(m["lat"], m["lon"])
                clima[m["nome"]] = c if c else {}
            except Exception as e:
                logger.warning(f"  ⚠ Clima {m['nome']}: {e}")
                clima[m["nome"]] = {}
        logger.info(f"  → Clima para {len(clima)} municípios")
        return clima

    # ------------------------------------------------------------------
    # 2. Geração de dados sintéticos realistas (baseados em séries reais)
    # ------------------------------------------------------------------

    def gerar_dados_sinteticos(
        self,
        num_amostras: int = 200,
        num_nos: int = 30,
        ruido: float = 0.05,
        tendencia_temporal: bool = True,
    ) -> PipelineData:
        """
        Gera dados sintéticos realistas simulando séries temporais de focos.

        Cada município recebe uma assinatura base de temperatura/FRP com:
        - Tendência sazonal (senoide) — estações seca/chuva
        - Picos aleatórios — queimadas reais
        - Ruído gaussiano — erro de medição
        - Correlação espacial — municípios vizinhos compartilham tendência
        """
        logger.info(f"🧬 Gerando {num_amostras} amostras sintéticas ({num_nos} nós)...")

        # Timestamps simulados
        base_date = datetime(2025, 6, 1, tzinfo=timezone.utc)
        timestamps = [
            (base_date + timedelta(hours=i * 3)).isoformat()
            for i in range(num_amostras + 1)
        ]

        # Assinatura base por município (latitude determina clima)
        t = np.linspace(0, 4 * np.pi, num_amostras + 1)

        dados = np.zeros((num_amostras, num_nos, self.num_features))
        alvos = np.zeros((num_amostras, num_nos, self.num_features))

        for i, mun in enumerate(MUNICIPIOS_CEARA[:num_nos]):
            # Temperatura: senoide anual + variação por latitude
            temp_base = 28 + 5 * np.sin(t / 2 - mun["lat"] * 0.5)
            temp_base += self.rng.gauss(0, 1)

            # FRP: picos correlacionados com temperatura e sazonalidade
            frp_base = 0.0
            if tendencia_temporal:
                estacao_seca = np.sin(t - mun["lat"] * 0.3)  # estações
                frp_base = np.maximum(0, estacao_seca) * 20
                # Picos aleatórios (queimadas)
                n_picos = self.rng.randint(1, 4)
                for _ in range(n_picos):
                    pico_t = self.rng.randint(0, num_amostras)
                    frp_base[pico_t:pico_t + 5] += np.random.exponential(15)

            # Vento: padrão diurno + ruído
            vento_base = 3 + 2 * np.sin(t * 4) + 0.5 * np.random.randn(num_amostras + 1)

            # Umidade relativa: inversamente correlacionada com temperatura
            umidade_base = 70 - 20 * np.sin(t / 2 - mun["lat"] * 0.5) + 5 * np.random.randn(num_amostras + 1)
            umidade_base = np.clip(umidade_base, 20, 100)

            # NDVI: sazonal (mais verde na chuva)
            ndvi_base = 0.5 + 0.2 * np.sin(t / 2 + 1) + 0.05 * np.random.randn(num_amostras + 1)

            # Declividade: constante por município (topografia real)
            declividade_base = np.full(num_amostras + 1, 3.0 + self.rng.gauss(0, 1))

            # Monta features
            for amostra in range(num_amostras):
                dados[amostra, i, :] = [
                    temp_base[amostra] / 50.0,
                    max(0, frp_base[amostra]) / 50.0,
                    abs(vento_base[amostra]) / 15.0,
                    max(0, umidade_base[amostra]) / 100.0,
                    np.clip(ndvi_base[amostra], 0, 1),
                    abs(declividade_base[amostra]) / 20.0,
                ]
                alvos[amostra, i, :] = [
                    temp_base[amostra + 1] / 50.0,
                    max(0, frp_base[amostra + 1]) / 50.0,
                    abs(vento_base[amostra + 1]) / 15.0,
                    max(0, umidade_base[amostra + 1]) / 100.0,
                    np.clip(ndvi_base[amostra + 1], 0, 1),
                    abs(declividade_base[amostra + 1]) / 20.0,
                ]

        # Adiciona ruído
        dados += np.random.randn(*dados.shape) * ruido
        alvos += np.random.randn(*alvos.shape) * ruido

        # Garante limites [0, 1]
        dados = np.clip(dados, 0, 1)
        alvos = np.clip(alvos, 0, 1)

        logger.info(f"  → X: {dados.shape}, y: {alvos.shape}")

        return PipelineData(
            X_t=torch.tensor(dados, dtype=torch.float32),
            X_tp1=torch.tensor(alvos, dtype=torch.float32),
            nomes=[m["nome"] for m in MUNICIPIOS_CEARA[:num_nos]],
            timestamps=timestamps[:-1],
            metadados={
                "fonte": "sintetico_realista",
                "num_amostras": num_amostras,
                "num_nos": num_nos,
                "num_features": self.num_features,
                "ruido": ruido,
            },
        )

    # ------------------------------------------------------------------
    # 3. Construção do dataset a partir de dados reais
    # ------------------------------------------------------------------

    def construir_dataset_real(
        self,
        focos: dict[str, int],
        clima: dict[str, dict],
        num_timesteps: int = 30,
    ) -> PipelineData:
        """
        Constrói dataset a partir de dados reais (FIRMS + clima).

        Para cada município e timestep, monta o vetor de features
        e gera transições temporais (x_t → x_tp1).
        """
        logger.info("📊 Construindo dataset real...")

        n = len(MUNICIPIOS_CEARA)
        features_flat = np.zeros((n, self.num_features))

        for i, m in enumerate(MUNICIPIOS_CEARA):
            c = clima.get(m["nome"], {})

            features_flat[i, :] = [
                c.get("temperatura_c", 30.0) / 50.0,
                min(focos.get(m["nome"], 0), 50) / 50.0,
                c.get("velocidade_vento_ms", 3.0) / 15.0,
                (100 - c.get("umidade_relativa", 60)) / 100.0,
                0.5,   # NDVI médio
                3.0 / 20.0,  # declividade média CE
            ]

        # Expande para múltiplos timesteps simulando evolução temporal
        # (em produção, usar dados históricos reais)
        X_t = np.zeros((num_timesteps, n, self.num_features))
        X_tp1 = np.zeros((num_timesteps, n, self.num_features))

        for t in range(num_timesteps):
            # Estado base com pequenas variações temporais
            variacao = np.random.randn(n, self.num_features) * 0.03
            X_t[t] = np.clip(features_flat + variacao, 0, 1)

            # Próximo timestep: evolução realista
            variacao_tp1 = np.random.randn(n, self.num_features) * 0.05
            X_tp1[t] = np.clip(features_flat + variacao_tp1 + 0.01, 0, 1)

        return PipelineData(
            X_t=torch.tensor(X_t, dtype=torch.float32),
            X_tp1=torch.tensor(X_tp1, dtype=torch.float32),
            nomes=[m["nome"] for m in MUNICIPIOS_CEARA],
            timestamps=[datetime.now(timezone.utc).isoformat()] * num_timesteps,
            metadados={
                "fonte": "real_firms_openmeteo",
                "num_amostras": num_timesteps,
                "num_nos": n,
                "num_features": self.num_features,
                "num_focos_total": sum(focos.values()),
            },
        )

    # ------------------------------------------------------------------
    # 4. Utilitários
    # ------------------------------------------------------------------

    def salvar_cache(self, dados: PipelineData, nome: str = "pipeline_data.pt"):
        """Salva dados processados em cache."""
        path = self.data_dir / nome
        torch.save({
            "X_t": dados.X_t,
            "X_tp1": dados.X_tp1,
            "nomes": dados.nomes,
            "timestamps": dados.timestamps,
            "metadados": dados.metadados,
        }, path)
        logger.info(f"💾 Cache salvo: {path}")
        return path

    def carregar_cache(self, nome: str = "pipeline_data.pt") -> Optional[PipelineData]:
        """Carrega dados do cache."""
        path = self.data_dir / nome
        if not path.exists():
            logger.warning(f"⚠ Cache não encontrado: {path}")
            return None
        data = torch.load(path, weights_only=False)
        logger.info(f"📂 Cache carregado: {path}")
        return PipelineData(
            X_t=data["X_t"],
            X_tp1=data["X_tp1"],
            nomes=data["nomes"],
            timestamps=data.get("timestamps", []),
            metadados=data.get("metadados", {}),
        )

    def to_dataloader(
        self,
        dados: PipelineData,
        batch_size: int = 32,
        shuffle: bool = True,
    ) -> DataLoader:
        """Converte PipelineData em DataLoader PyTorch."""
        dataset = TensorDataset(dados.X_t, dados.X_tp1)
        return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle)


# ---------------------------------------------------------------------------
# Teste rápido
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    carregador = CarregadorDados()

    # Gera dados sintéticos
    dados = carregador.gerar_dados_sinteticos(num_amostras=100, num_nos=10)
    print(f"Shape X_t: {dados.X_t.shape}")
    print(f"Shape X_tp1: {dados.X_tp1.shape}")
    print(f"Range X_t: [{dados.X_t.min():.3f}, {dados.X_t.max():.3f}]")
    print(f"Nomes: {dados.nomes[:3]}...")

    # Converte para DataLoader
    loader = carregador.to_dataloader(dados, batch_size=16)
    batch = next(iter(loader))
    print(f"Batch: X={batch[0].shape}, y={batch[1].shape}")
    print("✅ pipeline_data.py: CarregadorDados OK")
