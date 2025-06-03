import altair as alt
import pandas as pd
import streamlit as st
from agents import Agent, Runner, AsyncOpenAI, OpenAIChatCompletionsModel, RunConfig
import os
from dotenv import load_dotenv
from data import Data
import asyncio
import re
import json
import random
from datetime import datetime

# --- Load environment
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

# --- Setup AI model
external_client = AsyncOpenAI(
    api_key=API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

model = OpenAIChatCompletionsModel(
    model="gemini-1.5-flash",
    openai_client=external_client
)

config = RunConfig(
    model=model,
    model_provider=external_client,
    tracing_disabled=True
)

# --- Setup agents
explainer_agent = Agent(
    name="Explainer",
    instructions="Your job is to explain any topic in simple terms, with examples."
)

quiz_maker_agent = Agent(
    name="QuizMaker",
    instructions="""Generate a 3-question quiz on the given topic. Use MCQs with options A, B, C, and D. 
The output must follow this format:

Q1. What is Python?
A. A type of snake
B. A programming language
C. A car
D. A game
Answer: B

Q2...
"""
)

progress_tracker_agent = Agent(
    name="ProgressTracker",
    instructions="Track user’s completed topics and quiz scores."
)


mega_test_agent = Agent(
    name="MegaTestAgent",
    instructions="""
You will be given a list of MCQs. Select 5 random questions and output them in this format:

Q1. Question text?
A. Option A
B. Option B
C. Option C
D. Option D
Answer: X

Only output questions and answers in that format. Do not add any introduction or closing text.
"""
)


manager = Agent(
    name="Manager",
    instructions="Your job is to handoff tasks to relevant agents",
    handoff_description="Delegate task",
    handoffs=[explainer_agent, quiz_maker_agent, progress_tracker_agent]
)


# --- Utils
def parse_quiz(text: str):
    questions = []
    blocks = text.strip().split("Q")
    for block in blocks:
        if not block.strip():
            continue
        lines = block.strip().splitlines()
        question = lines[0][2:].strip()
        options = [line.strip() for line in lines[1:5]]
        answer_match = re.search(r"Answer: ([A-D])", block)
        answer = answer_match.group(1) if answer_match else ""
        questions.append({
            "question": question,
            "options": options,
            "answer": answer
        })
    return questions


# --- Streamlit App
st.set_page_config(page_title="Learning Assistant", layout="wide")
st.title("📚 Powered Learning Assistant")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📘 Learn", "📝 Quiz", "📊 History", "📜 Mega Test", "📈 Progress"])

with tab1:
    st.subheader("Learn Anything")
    topic = st.text_input("Enter a topic to explain:")
    if st.button("Explain") and topic:
        result = asyncio.run(Runner.run(starting_agent=explainer_agent, input=topic, run_config=config))
        st.write(result.final_output)
        Data.append_to_history("history.json", {"type": "explain", "topic": topic, "output": result.final_output})

with tab2:
    st.subheader("Generate Quiz")

    quiz_topic = st.text_input("Enter a topic for quiz:")

    if "quiz_data" not in st.session_state:
        st.session_state.quiz_data = []
        st.session_state.quiz_result = None

    if st.button("Generate Quiz") and quiz_topic:
        result = asyncio.run(Runner.run(starting_agent=quiz_maker_agent, input=quiz_topic, run_config=config))
        quiz_data = parse_quiz(result.final_output)
        st.session_state.quiz_data = quiz_data
        st.session_state.quiz_result = None

    if st.session_state.quiz_data:
        st.markdown("### Answer all questions")
        user_answers = {}
        for idx, q in enumerate(st.session_state.quiz_data):
            st.write(f"**{idx + 1}. {q['question']}**")
            choice = st.radio("Choose one:", options=q["options"], key=f"quiz_{idx}")
            user_answers[idx] = choice[0]  # Extract A/B/C/D

        if st.button("✅ Submit Quiz"):
            correct = 0
            for i, q in enumerate(st.session_state.quiz_data):
                if user_answers.get(i) == q["answer"]:
                    correct += 1
            st.session_state.quiz_result = correct
            for q in st.session_state.quiz_data:
                Data.append_to_history("quiz.json", q)

    if st.session_state.quiz_result is not None:
        st.success(f"✅ You scored {st.session_state.quiz_result} out of {len(st.session_state.quiz_data)}")

with tab3:
    st.subheader("Interaction History")
    history = Data.load_data("history.json") or []
    for entry in history[::-1]:
        st.markdown(f"**{entry['type'].capitalize()}** on **{entry['topic']}**")
        st.code(entry['output'])


with tab4:
    st.subheader("📜 Mega Test from Stored Questions")

    if st.button("🧠 Start Mega Test"):
        all_qs = Data.load_data("quiz.json")

        if not all_qs or len(all_qs) < 5:
            st.warning("Not enough questions in `quiz.json` to create a Mega Test.")
        else:
            # Sample 5 random questions
            sampled_qs = random.sample(all_qs, 5)

            # Convert to string for agent
            formatted_text = ""
            for i, q in enumerate(sampled_qs, start=1):
                formatted_text += f"Q{i}. {q['question']}\n"
                for opt in q["options"]:
                    formatted_text += f"{opt}\n"
                formatted_text += f"Answer: {q['answer']}\n\n"

            # Pass to Agent
            result = asyncio.run(Runner.run(
                starting_agent=mega_test_agent,
                input=formatted_text,
                run_config=config
            ))

            # Parse quiz and store in session
            st.session_state.mega_quiz_data = parse_quiz(result.final_output)
            st.session_state.mega_quiz_result = None

    if st.session_state.get("mega_quiz_data"):
        st.markdown("### 🧪 Mega Test Questions")
        mega_answers = {}

        for idx, q in enumerate(st.session_state.mega_quiz_data):
            st.write(f"**{idx + 1}. {q['question']}**")
            choice = st.radio("Choose one:", options=q["options"], key=f"mega_{idx}")
            mega_answers[idx] = choice[0]

        if st.button("✅ Submit Mega Test"):
            correct = 0
            for i, q in enumerate(st.session_state.mega_quiz_data):
                if mega_answers.get(i) == q["answer"]:
                    correct += 1
            st.session_state.mega_quiz_result = correct

            # Save score
            score_record = {
                "score": correct,
                "total": len(st.session_state.mega_quiz_data),
                "timestamp": datetime.now().isoformat()
            }
            Data.append_to_history("scores.json", score_record)

    if st.session_state.get("mega_quiz_result") is not None:
        st.success(f"🎉 You scored {st.session_state.mega_quiz_result} out of {len(st.session_state.mega_quiz_data)}")

with tab5:
    st.subheader("📈 Mega Test Progress Tracker")

    scores = Data.load_data("scores.json") or []

    if scores:
        # Convert to DataFrame
        df = pd.DataFrame(scores)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["percentage"] = (df["score"] / df["total"]) * 100
        df["Test #"] = range(1, len(df) + 1)

        chart = alt.Chart(df).mark_bar(size=35, cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
            x=alt.X("Test #:O", title="Mega Test Number"),
            y=alt.Y("percentage:Q", title="Score (%)"),
            tooltip=["timestamp:T", "score:Q", "total:Q", "percentage:Q"]
        ).properties(
            width=700,
            height=400
        ).configure_axis(
            labelFontSize=12,
            titleFontSize=14
        )

        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No test scores found yet. Take a Mega Test to begin tracking.")
