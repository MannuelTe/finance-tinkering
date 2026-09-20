"""PURPOSE: configuration for the blocked-validation overfitting study of the HMM method.
INPUTS: none.
OUTPUTS: OverfitConfig, the paper replication config plus blocked-CV and 2019 OOS settings.
"""

from dataclasses import dataclass
from pathlib import Path

from wasserstein_hmm.config import ReplicationConfig

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class OverfitConfig(ReplicationConfig):
    oos_start: str = "2019-01-01"
    holdout_days: int = 80  # the most recent days of history are always a test block
    block_len: int = 80  # length of each random test block
    random_blocks: int = 3  # number of random test blocks besides the final holdout
    gap_days: int = 60  # purge on both sides of every test block (= volatility_window)
    min_segment: int = 120  # shortest admissible train segment (HMM needs some context)
