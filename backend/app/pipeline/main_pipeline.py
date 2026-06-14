"""
TASK-006: Pipeline Orquestrador — Integração Dados → Modelo → API
=====================================================================
Componente 3 do pipeline completo: orquestra a execução completa do
pipeline de modelagem de queimadas com o modelo NeKo-PIGNN.

Fluxo completo:
  1. Carregar/gerar dados de satélite (VIIRS, GOES-16, FIRMS)
  2. Fundir com dados climáticos (Open-Meteo)
  3. Construir dataset de treino (PipelineData)
  4. Treinar modelo NeKo-PIGNN com regularização física (Rothermel)
  5. Avaliar métricas e gerar relatório
  6. Salvar artefatos (checkpoint, relatório, figuras)
  7. Preparar para deploy na API FastAPI
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import torch

from .pipeline_data import PipelineData, CarregadorDados, N_MUNICIPIOS
from .pipeline_modelo import PipelineModelo, ResultadoTreino

logger = logging.getLogger("pipeline_orquestrador")


class PipelineOrquestrador:
    """
    Orquestrador completo do pipeline de modelagem.

    Integra:
    - CarregadorDados (coleta/pré-processamento)
    - PipelineModelo (treino/inferência)
    - Geração de relatórios e artefatos
    - Integração com API FastAPI existente
    """

    def __init__(
        self,
        data_dir: str = "backend/data/cache",
        checkpoint_dir: str = "models/checkpoints",
        output_dir: str = "backend/app/pipeline/relatorios",
    ):
        self.data_dir = Path(data_dir)
        self.checkpoint_dir = Path(checkpoint_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.carregador = CarregadorDados(data_dir=str(data_dir))
        self.pipeline_modelo: Optional[PipelineModelo] = None
        self.resultado: Optional[ResultadoTreino] = None

    # ------------------------------------------------------------------
    # Execução completa
    # ------------------------------------------------------------------

    async def executar_completo(
        self,
        modo: str = "sintetico",
        num_amostras: int = 200,
        num_nos: int = N_MUNICIPIOS,
        epochs: int = 50,
        lr: float = 5e-4,
        batch_size: int = 32,
        split_val: float = 0.2,
        verbose: bool = True,
    ) -> dict:
        """
        Executa o pipeline completo.

        Args:
            modo: 'sintetico' (offline) ou 'real' (online, tenta FIRMS+Open-Meteo)
            num_amostras: Número de amostras sintéticas
            num_nos: Número de municípios/nós
            epochs: Épocas de treino
            lr: Learning rate
            batch_size: Tamanho do batch
            split_val: Fração de validação
            verbose: Logging verbose

        Returns:
            dict com resultados completos
        """
        logger.info("=" * 60)
        logger.info("PIPELINE COMPLETO NeKo-PIGNN")
        logger.info("=" * 60)
        logger.info(f"Modo: {modo}, amostras={num_amostras}, nos={num_nos}, epochs={epochs}")

        # --- Etapa 1: Dados ---
        logger.info("\n" + "-" * 40)
        logger.info("ETAPA 1/4: Carregamento e pré-processamento de dados")
        logger.info("-" * 40)

        if modo == "real":
            try:
                focos = await self.carregador.coletar_focos_firms(dias=7)
                clima = await self.carregador.coletar_clima()
                dados = self.carregador.construir_dataset_real(focos, clima, num_timesteps=num_amostras)
                logger.info(f"Dados reais: {dados.X_t.shape[0]} amostras, {dados.X_t.shape[1]} municipios")
            except Exception as e:
                logger.warning(f"Coleta real falhou ({e}), usando sintetico")
                dados = self.carregador.gerar_dados_sinteticos(
                    num_amostras=num_amostras, num_nos=num_nos
                )
        else:
            dados = self.carregador.gerar_dados_sinteticos(
                num_amostras=num_amostras, num_nos=num_nos
            )

        # Split treino/validação
        n_train = int(dados.X_t.shape[0] * (1 - split_val))
        dados_treino = PipelineData(
            X_t=dados.X_t[:n_train], X_tp1=dados.X_tp1[:n_train],
            nomes=dados.nomes, timestamps=dados.timestamps[:n_train],
        )
        dados_val = PipelineData(
            X_t=dados.X_t[n_train:], X_tp1=dados.X_tp1[n_train:],
            nomes=dados.nomes, timestamps=dados.timestamps[n_train:],
        )
        logger.info(f"Split: {len(dados_treino.X_t)} treino / {len(dados_val.X_t)} validacao")
        logger.info(f"Features: {dados.X_t.shape[-1]}, Range: [{dados.X_t.min():.3f}, {dados.X_t.max():.3f}]")

        # --- Etapa 2: Modelo ---
        logger.info("\n" + "-" * 40)
        logger.info("ETAPA 2/4: Construcao e treino do modelo NeKo-PIGNN")
        logger.info("-" * 40)

        self.pipeline_modelo = PipelineModelo(
            node_features=dados.X_t.shape[-1],
            latent_dim=min(32, dados.X_t.shape[-1] * 4),
            gnn_hidden=64,
            koopman_rank=min(16, dados.X_t.shape[-1] * 2),
            num_nodes=dados.X_t.shape[1],
            checkpoint_dir=str(self.checkpoint_dir),
        )

        self.resultado = self.pipeline_modelo.treinar(
            dados_treino, dados_val=dados_val,
            epochs=epochs, lr=lr, batch_size=batch_size,
            verbose=verbose,
        )

        logger.info(f"\nMetricas de treino:")
        for k, v in self.resultado.metricas.items():
            logger.info(f"  {k}: {v}")

        # --- Etapa 3: Inferência ---
        logger.info("\n" + "-" * 40)
        logger.info("ETAPA 3/4: Inferencia multi-horizonte")
        logger.info("-" * 40)

        previsao = self.pipeline_modelo.prever(
            dados.X_t[:1], nomes=dados.nomes, passos=6
        )
        logger.info(f"Previsao: {previsao['num_passos']} passos, {len(previsao['previsoes'])} municipios")
        logger.info(f"Top-3 risco: {self.resultado.metricas.get('top3_frp_previsto', [])[:3]}")

        # --- Etapa 4: Relatório ---
        logger.info("\n" + "-" * 40)
        logger.info("ETAPA 4/4: Geracao de relatorio e artefatos")
        logger.info("-" * 40)

        relatorio = self._gerar_relatorio(dados, previsao)
        self._salvar_artefatos(relatorio)

        logger.info("\n" + "=" * 60)
        logger.info("PIPELINE COMPLETO — SUCESSO")
        logger.info("=" * 60)

        return relatorio

    # ------------------------------------------------------------------
    # Relatório e artefatos
    # ------------------------------------------------------------------

    def _gerar_relatorio(self, dados: PipelineData, previsao: dict) -> dict:
        """Gera relatório completo do pipeline."""
        relatorio = {
            "pipeline": "NeKo-PIGNN para Modelagem de Queimadas — TASK-006",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "concluido",
            "dados": {
                "fonte": dados.metadados.get("fonte", "sintetico"),
                "num_amostras": dados.X_t.shape[0],
                "num_municipios": dados.X_t.shape[1],
                "num_features": dados.X_t.shape[2],
                "municipios": dados.nomes[:5],
            },
            "modelo": {
                "arquitetura": "NeKo-PIGNN (Koopman Neural + PI-GNN + Rothermel)",
                "dimensao_latente": self.pipeline_modelo.latent_dim if self.pipeline_modelo else 0,
                "parametros": sum(p.numel() for p in self.resultado.modelo.parameters()) if self.resultado else 0,
            },
            "treino": {
                "epocas_totais": len(self.resultado.historico["train_loss"]) if self.resultado else 0,
                "melhor_epoch": self.resultado.melhor_epoch + 1 if self.resultado else 0,
                "tempo_total_s": round(self.resultado.tempo_treino_s, 2) if self.resultado else 0.0,
            },
            "metricas": self.resultado.metricas if self.resultado else {},
            "previsao": {
                "horizontes": previsao["num_passos"],
                "top3_risco": self.resultado.metricas.get("top3_frp_previsto", []) if self.resultado else [],
            },
            "checkpoint": str(self.resultado.checkpoint_path) if self.resultado and self.resultado.checkpoint_path else None,
        }
        return relatorio

    def _salvar_artefatos(self, relatorio: dict):
        """Salva relatório e artefatos no diretório de saída e no diretório de artefatos do kanban."""
        # Salva na saída do pipeline
        path_relatorio = self.output_dir / "relatorio_pipeline.json"
        with open(path_relatorio, "w") as f:
            json.dump(relatorio, f, indent=2, ensure_ascii=False)
        logger.info(f"Relatorio salvo: {path_relatorio}")

        # Salva no diretório de artefatos do kanban
        kanban_artifacts = Path(
            "/Users/naubergois/qclawmonitor/.stack/accounts/teams/"
            "gemeo-digital-queimadas/workspace/artifacts"
        )
        kanban_artifacts.mkdir(parents=True, exist_ok=True)
        path_kanban = kanban_artifacts / "TASK-006-pipeline-neko-pignn.json"
        with open(path_kanban, "w") as f:
            json.dump(relatorio, f, indent=2, ensure_ascii=False)
        logger.info(f"Artefato kanban salvo: {path_kanban}")

        # Relatório markdown
        path_md = self.output_dir / "relatorio_pipeline.md"
        md = self._gerar_markdown(relatorio)
        with open(path_md, "w") as f:
            f.write(md)
        logger.info(f"Relatorio MD salvo: {path_md}")

        # Markdown no kanban
        path_md_kanban = kanban_artifacts / "TASK-006-pipeline-neko-pignn.md"
        with open(path_md_kanban, "w") as f:
            f.write(md)
        logger.info(f"Artefato MD kanban salvo: {path_md_kanban}")

    def _gerar_markdown(self, relatorio: dict) -> str:
        """Gera relatório em formato Markdown."""
        m = relatorio["metricas"]
        t = relatorio["treino"]
        d = relatorio["dados"]
        linhas = [
            "# Relatório do Pipeline NeKo-PIGNN — TASK-006",
            "",
            f"**Status**: {relatorio['status']}  ",
            f"**Timestamp**: {relatorio['timestamp']}  ",
            "",
            "## Dados",
            f"- Fonte: {d['fonte']}",
            f"- Amostras: {d['num_amostras']}",
            f"- Municípios: {d['num_municipios']}",
            f"- Features: {d['num_features']} (temp, FRP, vento, umidade, NDVI, declividade)",
            "",
            "## Modelo",
            f"- Arquitetura: {relatorio['modelo']['arquitetura']}",
            f"- Dimensão latente (Koopman): {relatorio['modelo']['dimensao_latente']}",
            f"- Parâmetros: {relatorio['modelo']['parametros']:,}",
            "",
            "## Treino",
            f"- Épocas: {t['epocas_totais']} (melhor: {t['melhor_epoch']})",
            f"- Tempo: {t['tempo_total_s']:.1f}s",
            "",
            "## Métricas",
            f"- MSE: {m.get('mse', 'N/A'):.4f}",
            f"- MAE: {m.get('mae', 'N/A'):.4f}",
            f"- R²: {m.get('r2', 'N/A'):.4f}",
            f"- FRP MSE: {m.get('frp_mse', 'N/A'):.4f}",
            f"- FRP MAE: {m.get('frp_mae', 'N/A'):.4f}",
            "",
            "## Top-3 Municípios (risco previsto)",
        ]
        for i, (mun, risco) in enumerate(m.get("top3_frp_previsto", []), 1):
            linhas.append(f"{i}. **{mun}**: {risco:.4f}")

        linhas += [
            "",
            "## Previsão Multi-Horizonte",
            f"- Horizontes: {relatorio['previsao']['horizontes']} passos",
            "",
            "## Checkpoint",
            f"- {relatorio['checkpoint'] or 'N/A'}",
            "",
            "---",
            "*Gerado automaticamente pelo Pipeline Orquestrador (TASK-006)*",
        ]
        return "\n".join(linhas)

    # ------------------------------------------------------------------
    # Utilitário: executar async via CLI
    # ------------------------------------------------------------------

    @staticmethod
    async def main_async(args: argparse.Namespace):
        """Executa o pipeline via CLI (assíncrono)."""
        pipeline = PipelineOrquestrador()
        relatorio = await pipeline.executar_completo(
            modo=args.modo,
            num_amostras=args.amostras,
            num_nos=args.nos,
            epochs=args.epochs,
            lr=args.lr,
            batch_size=args.batch,
        )
        print(f"\nPipeline concluido! Metricas:")
        print(f"  MSE: {relatorio['metricas']['mse']:.4f}")
        print(f"  MAE: {relatorio['metricas']['mae']:.4f}")
        print(f"  R2:  {relatorio['metricas']['r2']:.4f}")
        return relatorio


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Pipeline NeKo-PIGNN — TASK-006")
    parser.add_argument("--modo", choices=["sintetico", "real"], default="sintetico",
                        help="Modo de dados: sintetico (offline) ou real (FIRMS+Open-Meteo)")
    parser.add_argument("--amostras", type=int, default=200, help="Numero de amostras")
    parser.add_argument("--nos", type=int, default=N_MUNICIPIOS, help="Numero de municipios/nos")
    parser.add_argument("--epochs", type=int, default=50, help="Epocas de treino")
    parser.add_argument("--lr", type=float, default=5e-4, help="Learning rate")
    parser.add_argument("--batch", type=int, default=32, help="Batch size")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    asyncio.run(PipelineOrquestrador.main_async(args))


if __name__ == "__main__":
    main()
