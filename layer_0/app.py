import streamlit as st
import os
import json

from .gemini_utils import analyze_lyrics, load_config
from .music_gen import generate_music_from_prompt
from .video_gen import generate_placeholder_video
from .composer import compose_video


st.title("10s Animated Musical Video Generator 🎬🎵")
st.write("Enter lyrics, and I'll generate a short video with subtitles + music.")

lyrics = st.text_area("Lyrics", "In the midnight light, I’m chasing dreams through neon skies.")
duration = st.slider("Duration (sec)", 5, 15, 10)

if st.button("Generate Video"):
    with st.spinner("Running pipeline..."):
        config = load_config("config.json")
        gemini_out = analyze_lyrics(lyrics)
        music_prompt = gemini_out.get("music_prompt", "dreamy ambient")
        video_prompt = gemini_out.get("video_prompt", "dreamy animated city with neon lights")
        mubert_key = config.get("MUBERT_API_KEY")

        music_path = generate_music_from_prompt(music_prompt, duration_sec=duration, output_path="outputs/music.wav",
                                                mubert_api_key=mubert_key)
        video_path = generate_placeholder_video(video_prompt, duration_sec=duration, output_path="outputs/video.mp4")
        final_path = compose_video(video_path, music_path, lyrics, output_path="outputs/final.mp4")

    st.success("Done!")
    st.video(final_path)
    st.write("File saved at:", final_path)
