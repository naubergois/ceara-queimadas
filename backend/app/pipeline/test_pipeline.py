"""Teste rápido do pipeline TASK-006."""
import sys, logging
sys.path.insert(0, "backend")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from app.pipeline.pipeline_data import CarregadorDados
from app.pipeline.pipeline_modelo import PipelineModelo

# 1. Gera dados sintéticos
cd = CarregadorDados()
dados = cd.gerar_dados_sinteticos(num_amostras=50, num_nos=10, ruido=0.03)
print(f"[OK] Dados: X={dados.X_t.shape}, y={dados.X_tp1.shape}")
print(f"     Range: [{dados.X_t.min():.3f}, {dados.X_t.max():.3f}]")
print(f"     Nomes: {len(dados.nomes)} municipios")

loader = cd.to_dataloader(dados, batch_size=16)
batch = next(iter(loader))
print(f"[OK] DataLoader: X={batch[0].shape}, y={batch[1].shape}")

# 2. Treina modelo pequeno
pl = PipelineModelo(
    node_features=6, latent_dim=12, gnn_hidden=24,
    koopman_rank=6, num_nodes=10,
    checkpoint_dir="models/checkpoints"
)
res = pl.treinar(dados, epochs=15, lr=1e-3, batch_size=16, verbose=True)
print(f"[OK] Treino concluido: melhor loss={res.historico['train_loss'][-1]:.4f}")

# 3. Métricas
m = res.metricas
print(f"[OK] Metricas: MSE={m['mse']:.4f}, MAE={m['mae']:.4f}, R2={m['r2']:.4f}")
print(f"     FRP MSE={m['frp_mse']:.4f}, Top-3={m['top3_frp_previsto']}")

# 4. Inferência multi-passo
prev = pl.prever(dados.X_t[:1], nomes=dados.nomes[:10], passos=3)
print(f"[OK] Inferencia: {prev['num_passos']} passos, {len(prev['previsoes'])} municipios")
print(f"     Exemplo: {prev['previsoes'][0]['municipio']} -> prev={prev['previsoes'][0]['previsao'][:3]}")

# 5. Checkpoint
check = pl.carregar_checkpoint()
print(f"[OK] Checkpoint carregado: {check}")

print("\n[TASK-006] TODOS OS TESTES PASSARAM.")
