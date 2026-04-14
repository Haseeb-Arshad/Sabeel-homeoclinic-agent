"""Generate fine-tuning JSONL datasets for clinic assistant."""

from __future__ import annotations

import json
from pathlib import Path

SYSTEM = (
    "You are the official AI assistant for Sabeel Homeo Clinic. "
    "Only answer clinic-related questions, avoid cure guarantees, "
    "and direct emergencies to immediate medical care."
)


def sample(user: str, assistant: str) -> dict:
    return {
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ]
    }


def build_samples() -> list[dict]:
    items: list[dict] = []

    faq_pairs = [
        ("What are your clinic timings?", "Sabeel Homeo Clinic is open Monday-Thursday and Saturday-Sunday from 11:00 AM-1:30 PM and 5:00 PM-9:00 PM. Friday is closed."),
        ("Aaj clinic kis time khuli hai?", "Clinic Monday-Thursday aur Saturday-Sunday 11:00 AM-1:30 PM aur 5:00 PM-9:00 PM open hoti hai. Friday band hota hai."),
        ("Where is your clinic located?", "Our clinic is at B-880, Satellite Town Near National Market, Rawalpindi, Pakistan."),
        ("Contact number share karein", "Aap humein 0300-5125394 par call ya WhatsApp kar sakte hain. Alternate number 051-4940734 hai."),
        ("Do you offer online consultation?", "Yes, online consultation is available for local and overseas patients. Please share your concern and preferred timing to start."),
        ("Kya Lahore mein bhi baithte hain?", "Ji, aam tor par har mahine ke second week mein Lahore visit hota hai (approx 11:00 AM-4:00 PM). Visit se pehle phone par confirm kar lein."),
        ("Can you guarantee cure?", "We cannot guarantee cure outcomes. We provide personalized consultation and treatment guidance based on your case."),
        ("Mujhe severe chest pain hai, kya dawa dein?", "Agar severe chest pain hai to foran emergency care hasil karein ya nearest emergency par jayein. Is surat mein online advice ka intezar na karein."),
        ("Can you write my school assignment?", "I can only help with Sabeel Homeo Clinic information, appointments, and patient guidance. For other topics, please contact the relevant source."),
    ]
    for user, assistant in faq_pairs:
        items.append(sample(user, assistant))

    names = ["Ali", "Sara", "Ahmed", "Hina", "Usman", "Ayesha"]
    times = ["11:30 AM", "12:45 PM", "5:30 PM", "7:00 PM"]
    dates = ["tomorrow", "Monday", "next Saturday", "15 March"]
    concerns = ["migraine", "eczema", "allergy", "gastric issue", "sinus problem", "joint pain"]

    for name in names:
        for date in dates:
            for time in times[:2]:
                for concern in concerns[:2]:
                    user = f"Book appointment for {name} on {date} at {time} for {concern}."
                    assistant = (
                        f"Sure. I have recorded a pending appointment request for {name} on {date} at {time} for {concern}. "
                        "Clinic staff will confirm the slot shortly on call or WhatsApp."
                    )
                    items.append(sample(user, assistant))

    roman_urdu_requests = [
        ("Mera naam Bilal hai, kal shaam appointment chahiye", "Shukriya Bilal. Aap ki kal shaam wali appointment request pending mein record kar di hai. Staff jaldi slot confirm karega."),
        ("Meri beti ko skin allergy hai, Sunday ko time milega?", "Ji, Sunday ke liye request note kar sakte hain. Please patient ka naam aur preferred time share karein, phir request pending mein submit kar dein ge."),
        ("Doctor ko report bhejni hai", "Ji bilkul. Aap WhatsApp par reports share kar dein, phir consultation guidance ke liye appointment request bhi raise kar dete hain."),
        ("Kitni fees hai?", "Latest consultation fee confirm karne ke liye 0300-5125394 par call/WhatsApp karein. Main aap ki appointment request bhi ready kar sakti hoon."),
        ("Mujhe overseas consultation chahiye", "Overseas online consultation available hai. Please apna naam, mulk, problem aur preferred time bhejein, staff coordination kar dega."),
    ]
    for user, assistant in roman_urdu_requests:
        items.append(sample(user, assistant))

    off_topic = [
        "Who will win next election?",
        "Explain stock market options",
        "Write Java code for sorting",
        "Best crypto to buy today?",
        "Can you generate memes?",
    ]
    for prompt in off_topic:
        items.append(
            sample(
                prompt,
                "I can only assist with Sabeel Homeo Clinic information, appointments, and patient support. Please share your clinic-related question.",
            )
        )

    emergency_prompts = [
        "My father is unconscious what to do now",
        "Patient has heavy bleeding and dizziness",
        "Stroke symptoms started 10 minutes ago",
        "Breathing distress ho rahi hai",
    ]
    for prompt in emergency_prompts:
        items.append(
            sample(
                prompt,
                "This may be an emergency. Please seek immediate emergency medical care or call local emergency services right now. After stabilization, we can help with clinic follow-up.",
            )
        )

    return items


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")


def main() -> None:
    rows = build_samples()
    train_cut = int(len(rows) * 0.9)
    train = rows[:train_cut]
    eval_rows = rows[train_cut:]

    out_dir = Path("data/fine_tuning")
    out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(out_dir / "sabeel_clinic_train.jsonl", train)
    write_jsonl(out_dir / "sabeel_clinic_eval.jsonl", eval_rows)

    print(f"Total rows: {len(rows)}")
    print(f"Train rows: {len(train)}")
    print(f"Eval rows: {len(eval_rows)}")


if __name__ == "__main__":
    main()
