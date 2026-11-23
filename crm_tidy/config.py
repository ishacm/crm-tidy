import yaml

from crm_tidy import ROOT

CONFIG = yaml.safe_load((ROOT / "config.yaml").read_text())
