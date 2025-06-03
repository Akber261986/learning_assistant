import json
import os
from datetime import datetime

class Data:

    @staticmethod
    def load_data(file_name: str):
        if os.path.exists(file_name):
            try:
                with open(file_name, "r") as file:
                    return json.load(file)
            except json.JSONDecodeError:
                print(f"Warning: Failed to decode JSON in {file_name}. Returning empty list.")
                return []
        return []

    @staticmethod
    def save_data(file_name: str, data: dict | list):
        with open(file_name, "w") as file:
            json.dump(data, file, indent=4)

    @staticmethod
    def append_to_history(file_name, entry):
        data = Data.load_data(file_name) or []
        data.append(entry)
        Data.save_data(file_name, data)


    @staticmethod
    def save_quiz(topic: str, quiz: list, user_answers: list):
        full_quiz = []
        correct = 0

        for q, user_ans in zip(quiz, user_answers):
            is_correct = user_ans == q.get("correct_answer")
            if is_correct:
                correct += 1
            full_quiz.append({
                "question": q["question"],
                "options": q["options"],
                "correct_answer": q["correct_answer"],
                "user_answer": user_ans
            })

        quiz_entry = {
            "topic": topic,
            "quiz": full_quiz,
            "score": f"{correct}/{len(quiz)}",
            "timestamp": datetime.now().isoformat()
        }

        Data.append_to_history("quiz.json", quiz_entry)