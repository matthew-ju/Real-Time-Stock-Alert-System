PYTHON_SCRIPT_PATH="spy_alert_system.py"

run_python_script() {
  echo "Running Python script at $(date)"
  python3 "$PYTHON_SCRIPT_PATH"
}

schedule_script() {
  day_of_week=$(date +%u)
  
  current_hour=$(date +%H)
  current_minutes=$(date +%M)
  
  if [[ "$day_of_week" -ge 1 && "$day_of_week" -le 5 ]]; then
    if [[ "$current_hour" -eq 1 && "$current_minutes" -ge 42 ]]; then
      run_python_script
    elif [[ "$current_hour" -gt 1 && "$current_hour" -lt 16 ]]; then
      run_python_script
    elif [[ "$current_hour" -eq 16 && "$current_minutes" -le 0 ]]; then
      run_python_script
    fi
  fi
}

while true; do
  schedule_script
  sleep 60
done