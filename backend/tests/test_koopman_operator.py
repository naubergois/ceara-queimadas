"""TASK-007: Testes para NeuralKoopmanOperator (INOV-001)."""
import sys
from pathlib import Path

import pytest
import torch

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def set_seed():
    torch.manual_seed(42)


class TestNeuralKoopmanOperator:
    """Validação completa do pipeline NeuralKoopmanOperator."""

    def test_import(self):
        from app.models.inovacao.koopman_operator import (
            NeuralKoopmanOperator,
            train_koopman,
            EncoderMLP,
            DecoderMLP,
        )
        assert NeuralKoopmanOperator is not None
        assert train_koopman is not None

    def test_construct_default(self):
        from app.models.inovacao.koopman_operator import NeuralKoopmanOperator

        m = NeuralKoopmanOperator()
        assert m.K_matrix.shape == (32, 32)
        params = sum(p.numel() for p in m.parameters())
        assert params > 0

    def test_construct_custom(self):
        from app.models.inovacao.koopman_operator import NeuralKoopmanOperator

        m = NeuralKoopmanOperator(input_dim=8, latent_dim=16, koopman_rank=8)
        assert m.latent_dim == 16
        assert m.K_matrix.shape == (16, 16)

    def test_forward_pass(self):
        from app.models.inovacao.koopman_operator import NeuralKoopmanOperator

        m = NeuralKoopmanOperator(input_dim=6, latent_dim=16)
        m.eval()
        x_t = torch.randn(8, 6)
        x_tp1 = torch.randn(8, 6)
        with torch.no_grad():
            o = m(x_t, x_tp1)

        for k in ("loss", "recon_loss", "kl_loss", "pred_loss", "x_recon", "x_pred", "z_t"):
            assert k in o, f"Missing key {k}"
        assert o["x_recon"].shape == (8, 6)
        assert o["x_pred"].shape == (8, 6)
        assert o["loss"].item() > 0

    def test_multistep_propagation(self):
        from app.models.inovacao.koopman_operator import NeuralKoopmanOperator

        m = NeuralKoopmanOperator(input_dim=6, latent_dim=16)
        m.eval()
        z0 = torch.randn(4, 16)
        with torch.no_grad():
            z1 = m.forward_koopman(z0, 1)
            z5 = m.forward_koopman(z0, 5)
        assert z1.shape == z5.shape == (4, 16)
        assert not torch.allclose(z1, z5), "step1 should differ from step5"

    def test_training_2_epochs(self):
        from app.models.inovacao.koopman_operator import (
            NeuralKoopmanOperator,
            train_koopman,
        )

        seq_len, input_dim = 20, 6
        t = torch.linspace(0, 4 * 3.14159, seq_len)
        x = torch.stack(
            [
                torch.sin(t) + 0.1 * torch.randn(seq_len),
                0.5 * (torch.sin(t) + 1) + 0.05 * torch.randn(seq_len),
                0.3 * torch.sin(2 * t) + 0.1 * torch.randn(seq_len),
                0.4 + 0.1 * torch.randn(seq_len),
                0.6 + 0.05 * torch.randn(seq_len),
                0.2 * torch.sin(t) + 0.05 * torch.randn(seq_len),
            ],
            dim=1,
        )
        ds = torch.utils.data.TensorDataset(x[:-1], x[1:])
        loader = torch.utils.data.DataLoader(ds, batch_size=4, shuffle=True)

        m = NeuralKoopmanOperator(input_dim=6, latent_dim=16, koopman_rank=8)
        h = train_koopman(m, loader, epochs=5, verbose=False)
        assert len(h["train_loss"]) == 5
        loss0, lossN = h["train_loss"][0], h["train_loss"][-1]
        assert lossN <= loss0 + 5.0, f"Loss should not diverge: {loss0:.4f} -> {lossN:.4f}"
