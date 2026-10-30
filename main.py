import os
import time
from pathlib import Path

import streamlit as st
from groq import Groq
from streamlit_autorefresh import st_autorefresh
from streamlit_webrtc import WebRtcMode, webrtc_streamer

from services.auth.login_wall import render_login_wall
from services.coaching.llm import LLMCoach
from services.coaching.tts import TextToSpeech
from services.coaching.voice_pipeline import VoicePipeline, autoplay_audio
from services.config.workout_config import EXERCISE_OPTIONS, METRICS_FIELDS
from services.persistence.exercise_repository import get_users_exercises, init_db
from services.state.session_defaults import initial_session_defaults
from services.tracking.metrics import sync_metrics_update
from services.ui.style_loader import (
    inject_local_font,
    inject_webrtc_styles,
    load_css,
)
from services.vision.exercise_video_processor import VideoProcessorClass

PROJECT_DIR = Path(__file__).resolve().parent


def main():
    st.set_page_config(
        page_icon="🏋️‍♀️",
        page_title="AI Real-time GYM coach",
        initial_sidebar_state="expanded",
        layout="centered",
    )

    # Load custom styles & scripts
    load_css(str(PROJECT_DIR / "static" / "style.css"))
    inject_local_font(
        str(PROJECT_DIR / "static" / "adobeclean.otf"), "Adobeclean"
    )
    inject_webrtc_styles()

    # Initialize Database
    init_db()

    if not render_login_wall():
        return

    initial_session_defaults()
    if st.session_state.voice_pipeline is None:
        api_key = os.getenv("GROQ_API_KEY")
        if api_key:
            st.session_state.voice_pipeline = VoicePipeline(
                LLMCoach(Groq(api_key=api_key)),
                TextToSpeech(),
            )

    workout_started = st.session_state.get("workout_started", False)

    # ==========================================
    # SIDEBAR
    # ==========================================
    with st.sidebar:
        st.title("🏋️‍♀️ Apna AI Coach")
        if st.session_state.get("username"):
            st.caption(f"👨🏻‍💻 Logged in as {st.session_state.username}")

        st.divider()
        st.subheader("Workout Plan")

        if not workout_started:
            st.selectbox(
                "Exercise",
                options=EXERCISE_OPTIONS,
                key="plan_exercise",
                placeholder="Enter your exercise preferred",
            )
            st.number_input(
                "Sets", min_value=0, max_value=50, key="plan_sets", step=1
            )
            st.number_input(
                "Reps per Set",
                min_value=0,
                max_value=50,
                key="plan_reps",
                step=1,
            )

            st.markdown("")
            start_session_button = st.button(
                "Start Session",
                use_container_width=True,
                key="start_session_button",
            )

            if start_session_button:
                exercise = st.session_state["plan_exercise"]
                st.session_state["exercise_type"] = exercise
                st.session_state["target_sets"] = st.session_state["plan_sets"]
                st.session_state["reps_per_set"] = st.session_state["plan_reps"]
                st.session_state["reps"] = 0
                st.session_state["sets_completed"] = 0
                st.session_state["current_set_reps"] = 0
                st.session_state["workout_completed"] = False
                st.session_state["last_notified_workout_complete"] = False
                st.session_state["last_saved_sets_completed"] = 0
                st.session_state["set_cycle_started_at"] = time.time()
                st.session_state["workout_instance"] += 1
                for key, default in METRICS_FIELDS[exercise].items():
                    st.session_state[key] = default

                st.session_state["workout_started"] = True
                pipeline = st.session_state.get("voice_pipeline")
                if pipeline:
                    result = pipeline.process_event(
                        "workout_started", exercise, {}
                    )
                    if result:
                        st.session_state.audio_to_play, st.session_state.coach_feedback = result
                st.rerun()
        else:
            exercise = st.session_state.get("plan_exercise")
            sets = st.session_state.get("plan_sets")
            reps = st.session_state.get("plan_reps")

            st.info(f"**{exercise}** -- {sets} Sets / {reps} Reps")

            end_session_button = st.button(
                "End Workout",
                key="end_session_button",
                use_container_width=True,
            )

            if end_session_button:
                st.session_state["workout_started"] = False
                st.rerun()

        if workout_started:
            st.divider()

            exercise = st.session_state.get("plan_exercise")
            total_reps = st.session_state.get("reps", 0)
            current_set_reps = st.session_state.get("current_set_reps", 0)
            reps_per_set = st.session_state.get("plan_reps", 0)
            sets_completed = st.session_state.get("sets_completed", 0)

            st.subheader("Progress")
            st.metric("Total Reps", f"{total_reps}")
            st.metric(
                "Current Set Reps", f"{current_set_reps}/{reps_per_set}"
            )
            st.metric("Sets Completed", f"{sets_completed}")

            st.divider()

            if exercise == "Squats":
                st.subheader("Squat Metrics")
                st.metric("Knee Angle", f"{st.session_state.get('knee_angle', 0)}°")
                st.metric("Back Angle", f"{st.session_state.get('back_angle', 0)}°")
                st.metric("Depth Status", st.session_state.get("depth_status", "N/A"))

            elif exercise == "Push-ups":
                st.subheader("Push-up Metrics")
                st.metric("Elbow Angle", f"{st.session_state.get('elbow_angle', 0)}°")
                st.metric("Body Alignment", st.session_state.get("body_alignment", "N/A"))
                st.metric("Hip Position", st.session_state.get("hip_status", "N/A"))

            elif exercise == "Biceps Curls (Dumbbell)":
                st.subheader("Curl Metrics")
                st.metric("Elbow Angle", f"{st.session_state.get('elbow_angle', 0)}°")
                st.metric("Shoulder Stability", st.session_state.get("shoulder_status", "N/A"))
                st.metric("Swing Detection", st.session_state.get("swing_status", "N/A"))

            elif exercise == "Shoulder Press":
                st.subheader("Shoulder Press Metrics")
                st.metric("Elbow Angle", f"{st.session_state.get('elbow_angle', 0)}°")
                st.metric("Arm Extension", st.session_state.get("extension_status", "N/A"))
                st.metric("Back Arch", st.session_state.get("back_arch_status", "N/A"))

            elif exercise == "Lunges":
                st.subheader("Lunge Metrics")
                st.metric("Front Knee Angle", f"{st.session_state.get('front_knee_angle', 0)}°")
                st.metric("Torso Angle", f"{st.session_state.get('torso_angle', 0)}°")
                st.metric("Balance Status", st.session_state.get("balance_status", "N/A"))

    # ==========================================
    # MAIN PAGE CONTENT
    # ==========================================
    st.title("AI Real-time GYM Coach")
    st.caption("Real-time pose detection with proactive AI voice coaching")

    if not workout_started:
        st.markdown(
            """
            <div style="
                border: 10px dashed #444;
                border-radius: 0px;
                padding: 48px 32px;
                text-align: center;
                color: #888;
                margin-top: 32px;
            ">
                <h2 style="color:#ccc; margin-bottom:8px;">👉 Set your workout plan</h2>
                <p style="font-size:1.05rem;">
                    Choose your exercise, sets and reps in the sidebar,<br>
                    then click <strong>Start Workout</strong> to activate the camera and AI coach.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        if not st.session_state.get("voice_pipeline"):
            st.warning(
                "Set GROQ_API_KEY to enable AI voice coaching. Rep tracking "
                "does not require it."
            )

        model_path = PROJECT_DIR / "ml_models" / "pose_landmarker_full.task"
        if not model_path.is_file():
            st.error(
                "Pose detection is unavailable because the model file is missing: "
                f"{model_path}"
            )
        else:
            context = webrtc_streamer(
                key=f"exercise-analysis-{st.session_state.workout_instance}",
                mode=WebRtcMode.SENDRECV,
                video_processor_factory=VideoPr ocessorClass,
                rtc_configuration={
                    "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
                },
                media_stream_constraints={
                    "video": True,
                    "audio": False,
                },
                async_processing=True,
            )
            sync_metrics_update(context)
            if context.state.playing:
                st_autorefresh(interval=1000, key="workout_refresh")

    audio = st.session_state.pop("audio_to_play", None)
    if audio:
        autoplay_audio(audio)
        feedback = st.session_state.pop("coach_feedback", None)
        if feedback:
            st.caption(feedback)

    st.markdown("##### Workout History")
    user_id = st.session_state.get("user_id")

    if user_id:
        history = get_users_exercises(user_id)
        if history:
            formatted_data = [
                {
                    "Exercise": row["exercise_name"],
                    "Reps": row["reps"],
                    "Sets": row["sets"],
                    "Time (sec)": row["time"],
                    "Logged At": row["created_at"],
                }
                for row in history
            ]
            st.dataframe(formatted_data, use_container_width=True)
        else:
            st.caption("No workout history recorded yet.")


if __name__ == "__main__":
    main()