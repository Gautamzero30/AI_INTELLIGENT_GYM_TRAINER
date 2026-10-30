# AI_INTELLIGENT_GYM_TRAINER

AI-integrated gym trainer with real-time pose detection and workout tracking.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run main.py
```

Set `GROQ_API_KEY` in your environment to enable AI voice coaching. Rep tracking
and pose detection do not require it. Workout history is stored locally in
`data.db`, which is intentionally excluded from Git.

The MediaPipe pose model is included under `ml_models/`.
