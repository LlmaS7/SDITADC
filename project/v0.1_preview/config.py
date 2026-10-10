"""Preview parameters. Simulation time is measured in integer ticks."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "outputs"
WIDTH, HEIGHT = 32, 24
DEFAULT_SEED = 20261010
LOAD_TICKS = UNLOAD_TICKS = 2
INITIAL_TASKS = 9
AUTO_INTERVAL = 45
WAIT_WARNING = 120
PLAN_SECONDS = 2.0
PLAN_HORIZON = 260
CBS_NODE_LIMIT = 6000
CELL = 26
WINDOW = (1296, 850)
ROBOT_COLORS = ((48, 153, 246), (255, 172, 66), (115, 202, 157))

