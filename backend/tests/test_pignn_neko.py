"""TASK-007: Testes para PhysicsInformedGNN (INOV-002) e NeKo-PIGNN (INOV-003)."""
import sys
from pathlib import Path

import pytest
import torch

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def set_seed():
    torch.manual_seed(42)


class TestPhysicsInformedGNN:
    """Validação do PI-GNN com Rothermel Loss."""

    def test_rothermel_loss_import(self):
        from app.models.inovacao.pignn import RothermelLoss, rothermel_spread_rate
        assert RothermelLoss is not None
        assert rothermel_spread_rate is not None

    def test_rothermel_spread_rate(self):
        from app.models.inovacao.pignn import rothermel_spread_rate

        w = torch.tensor([[5.0]])
        s = torch.tensor([[0.1]])
        m = torch.tensor([[0.3]])
        r = rothermel_spread_rate(w, s, m)
        assert r.shape == (1, 1)
        assert r.item() >= 0.0

    def test_rothermel_loss_forward(self):
        from app.models.inovacao.pignn import RothermelLoss

        loss_fn = RothermelLoss()
        batch, nodes, feat = 2, 5, 3
        u_pred = torch.rand(batch, nodes, feat)
        u_target = torch.rand(batch, nodes, feat)
        u_t = torch.rand(batch, nodes, feat)
        u_tp1 = torch.rand(batch, nodes, feat)
        wind = torch.rand(batch, nodes, 1)
        slope = torch.rand(batch, nodes, 1)
        fuel = torch.rand(batch, nodes, 1)

        losses = loss_fn(u_pred, u_target, u_t, u_tp1, wind, slope, fuel)
        for k in ("loss", "data_loss", "pde_loss"):
            assert k in losses, f"Missing key {k}"
            assert losses[k].item() >= 0

    def test_pignn_forward(self):
        from app.models.inovacao.pignn import PhysicsInformedGNN

        num_nodes, batch, feat = 10, 4, 8
        model = PhysicsInformedGNN(
            node_features=feat, hidden_dim=32, num_layers=3, output_dim=3
        )
        params = sum(p.numel() for p in model.parameters())
        edge_index = torch.randint(0, num_nodes, (2, 20))
        edge_attr = torch.rand(20, 4)
        x = torch.rand(batch, num_nodes, feat)
        out = model(x, edge_index, edge_attr)
        assert out.shape == (batch, num_nodes, 3), f"Expected (4,10,3) got {out.shape}"
        assert params > 0


class TestNeKoPIGNN:
    """Validação do modelo híbrido NeKo-PIGNN."""

    def test_import(self):
        from app.models.inovacao.neko_pignn import NeKoPIGNN, build_ceara_graph, train_neko_pignn
        assert NeKoPIGNN is not None
        assert build_ceara_graph is not None
        assert train_neko_pignn is not None

    def test_build_ceara_graph(self):
        from app.models.inovacao.neko_pignn import build_ceara_graph

        num_nodes = 184
        knn = 5
        edge_index, edge_attr = build_ceara_graph(
            num_nodes=num_nodes, knn=knn, noise=0.1
        )
        assert edge_index.shape[0] == 2
        expected_edges = num_nodes * knn
        assert edge_index.shape[1] == expected_edges
        assert edge_attr.shape[0] == expected_edges
        assert edge_attr.shape[1] == 3

    def test_neko_pignn_forward(self):
        from app.models.inovacao.neko_pignn import NeKoPIGNN, build_ceara_graph

        batch, nodes, feat = 2, 5, 6
        model = NeKoPIGNN(
            node_features=6,
            latent_dim=16,
            gnn_hidden=32,
            num_nodes=nodes,
            koopman_rank=8,
        )
        params = sum(p.numel() for p in model.parameters())
        x_t = torch.randn(batch, nodes, feat)
        x_tp1 = torch.randn(batch, nodes, feat)
        edge_index, edge_attr = build_ceara_graph(
            num_nodes=nodes, knn=3, noise=0.5
        )
        out = model(
            x_t, x_tp1=x_tp1, edge_index=edge_index, edge_attr=edge_attr
        )
        for k in ("loss", "recon_loss", "pred_loss", "kl_loss", "gnn_loss", "x_recon", "x_pred"):
            assert k in out, f"Missing key {k}"
        assert out["x_pred"].shape == (batch, nodes, feat)
        assert out["loss"].item() > 0
        assert params > 0

    def test_neko_pignn_with_physics(self):
        """Testa forward com todos os parâmetros físicos."""
        from app.models.inovacao.neko_pignn import NeKoPIGNN, build_ceara_graph

        batch, nodes, feat = 2, 5, 6
        model = NeKoPIGNN(
            node_features=6,
            latent_dim=16,
            gnn_hidden=32,
            num_nodes=nodes,
            koopman_rank=8,
            lambda_pde=0.5,
        )
        x_t = torch.randn(batch, nodes, feat)
        x_tp1 = torch.randn(batch, nodes, feat)
        edge_index, edge_attr = build_ceara_graph(
            num_nodes=nodes, knn=3, noise=0.5
        )
        wind = torch.rand(batch, nodes, 1)
        slope = torch.rand(batch, nodes, 1)
        fuel = torch.rand(batch, nodes, 1)
        out = model(
            x_t,
            x_tp1=x_tp1,
            edge_index=edge_index,
            edge_attr=edge_attr,
            wind=wind,
            slope=slope,
            fuel_moisture=fuel,
        )
        assert "pde_loss" in out
        assert out["pde_loss"].item() >= 0
