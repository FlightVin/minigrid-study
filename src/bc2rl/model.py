"""Feed-forward actor and separate critic over the symbolic StageTask observation.

Encoder: per-channel categorical embeddings (object type, color, state, agent marker), three 3x3
convolutions (16/32/32, padding 1, ReLU), flatten (keeps position), concatenate scalar state
(direction one-hot, carried type and color one-hot, normalized remaining time), 128-unit hidden
layer. The actor ends in 7 logits; the critic in one value. They share no parameters.
"""
import torch
from torch import nn

from minigrid.core.constants import COLOR_TO_IDX, OBJECT_TO_IDX

from bc2rl import task as T

N_TYPES, N_COLORS, N_STATES, N_MARKS = len(OBJECT_TO_IDX), len(COLOR_TO_IDX), 3, 5
EMB = 8
N_SCALARS = 4 + N_TYPES + (N_COLORS + 1) + 1


class Encoder(nn.Module):
    def __init__(self, hidden=128):
        super().__init__()
        self.emb = nn.ModuleList([nn.Embedding(n, EMB) for n in (N_TYPES, N_COLORS, N_STATES, N_MARKS)])
        self.conv = nn.Sequential(
            nn.Conv2d(4 * EMB, 16, 3, padding=1), nn.ReLU(),
            nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(),
            nn.Conv2d(32, 32, 3, padding=1), nn.ReLU(),
        )
        self.fc = nn.Sequential(nn.Linear(32 * T.WIDTH * T.HEIGHT + N_SCALARS, hidden), nn.ReLU())

    def forward(self, grid, aux, time):
        # grid: (B, W, H, 4) integer; aux: (B, 3) integer; time: (B, 1) float
        g = grid.long()
        x = torch.cat([e(g[..., i]) for i, e in enumerate(self.emb)], dim=-1)   # (B, W, H, 4*EMB)
        x = self.conv(x.permute(0, 3, 1, 2)).flatten(1)
        a = aux.long()
        s = torch.cat([nn.functional.one_hot(a[:, 0], 4), nn.functional.one_hot(a[:, 1], N_TYPES),
                       nn.functional.one_hot(a[:, 2], N_COLORS + 1)], dim=1).float()
        return self.fc(torch.cat([x, s, time.float()], dim=1))


class Actor(nn.Module):
    def __init__(self):
        super().__init__()
        self.enc = Encoder()
        self.head = nn.Linear(128, T.N_ACTIONS)

    def forward(self, grid, aux, time):
        return self.head(self.enc(grid, aux, time))   # logits


class Critic(nn.Module):
    def __init__(self):
        super().__init__()
        self.enc = Encoder()
        self.head = nn.Linear(128, 1)

    def forward(self, grid, aux, time):
        return self.head(self.enc(grid, aux, time)).squeeze(-1)


def n_params(m):
    return sum(p.numel() for p in m.parameters())


def obs_to_torch(obs, device):
    """obs: dict of numpy arrays with a leading batch axis."""
    return (torch.as_tensor(obs["grid"], device=device), torch.as_tensor(obs["aux"], device=device),
            torch.as_tensor(obs["time"], device=device))
