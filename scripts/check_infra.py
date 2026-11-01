"""Valida a sintaxe da infraestrutura sem Docker: YAML do compose, referências a arquivos e variáveis do .env.example."""
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
dc = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
errors = []
for name, svc in dc["services"].items():
    b = svc.get("build")
    if b and not (ROOT / b["dockerfile"]).exists():
        errors.append(f"{name}: dockerfile ausente {b['dockerfile']}")
    for v in svc.get("volumes", []):
        src = v.split(":")[0]
        if src.startswith("./") and not (ROOT / src).exists():
            errors.append(f"{name}: volume ausente {src}")
    for dep in (svc.get("depends_on") or {}):
        if dep not in dc["services"]:
            errors.append(f"{name}: depends_on desconhecido {dep}")
env_vars = set(re.findall(r"^([A-Z_]+)=", (ROOT / ".env.example").read_text(), re.M))
used = set(re.findall(r"\$\{([A-Z_]+)", (ROOT / "docker-compose.yml").read_text()))
missing = used - env_vars
if missing:
    errors.append(f"variáveis do compose sem exemplo em .env.example: {sorted(missing)}")
for f in ("frontend/package-lock.json", "infra/nginx.conf", "infra/init.sql", "backend/requirements.txt", "sample_data/demo_dem_glo30.tif"):
    if not (ROOT / f).exists():
        errors.append(f"arquivo exigido ausente: {f}")
print("OK: compose válido, arquivos e variáveis consistentes" if not errors else "\n".join(errors))
sys.exit(1 if errors else 0)
