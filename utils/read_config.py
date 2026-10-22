from pathlib import Path
import yaml

# Assumes this script is one directory below the project root
ROOT_PATH = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT_PATH / "configs" / "bq_credentials.yaml"


def load_config(file_path=DEFAULT_CONFIG_PATH):
    """Load YAML configuration from the specified file path."""
    with open(file_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)