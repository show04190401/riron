#!/bin/bash
# queue.txt の各行（app voice vvm sid）を上から順に作る。作り終えた行は done.txt に書く。
source /home/claude/tts/.venv/bin/activate
cd /home/claude/work
while true; do
  job=$(grep -vxF -f <(cat done.txt 2>/dev/null; echo "__none__") queue.txt | head -1)
  [ -z "$job" ] && { echo "QUEUE EMPTY $(date +%T)"; break; }
  echo "START $job $(date +%T)"
  python -I gen.py $job || { echo "FAIL $job"; sleep 30; continue; }
  echo "$job" >> done.txt
done
