"""Run after migrations, with the same environment as the API."""
import argparse
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'services/api'))
from app.gmail_jobs import run_once
p=argparse.ArgumentParser();p.add_argument('--once',action='store_true');args=p.parse_args()
while True:
 try:worked=run_once()
 except KeyboardInterrupt:break
 except Exception:
  # Never print provider errors, credentials, message content or SQL parameters.
  print('Worker could not access the queue. Check database availability.',file=sys.stderr);worked=False
  if args.once:raise SystemExit(1)
 if args.once:break
 if not worked:time.sleep(2)
