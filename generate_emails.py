import csv
import time
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

INPUT_CSV = "bars_wien.csv"
OUTPUT_CSV = "output_emails.csv"

def generate_email(name: str, note: str) -> tuple[str, str]:
    """Gibt (subject, body) zurück."""
    note = note.strip() or "eine Bar in Wien"
    name_for_text = name.strip() or "eurer Bar"

    system_msg = (
        "Du schreibst kurze, persönliche Initiativbewerbungen für Barjobs in Wien. "
        "Ton: freundlich, locker, seriös, nicht übertrieben förmlich. "
        "Schreibe auf Deutsch."
    )

    user_msg = f"""
Schreibe eine E-Mail-Bewerbung für Niklas an eine Bar.

Details:
- Name der Bar: "{name_for_text}"
- Meine Notiz zur Bar: "{note}"
- Stadt: Wien
- Niklas: Erfahrung im Bar- und Servicebereich, mag direkte Arbeit mit Gästen,
  ist abends und am Wochenende flexibel und sucht längerfristig, nicht nur Ferienjobs.

Bitte liefere:
1. Eine passende Betreffzeile.
2. Den E-Mail-Text mit:
   - Anrede: "Hallo liebes Team von {{BAR_NAME}}"
   - 2–3 Absätze
   - Hinweis auf angehängten Lebenslauf
   - freundlicher Abschluss

Format der Antwort GENAU so:

BETREFF: <Betreff hier>
TEXT:
<Mailtext hier>
"""

    completion = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=400,
        temperature=0.75,
    )

    content = completion.choices[0].message.content or ""
    subject = ""
    body_lines = []
    in_body = False
    for line in content.splitlines():
        if line.startswith("BETREFF:"):
            subject = line.replace("BETREFF:", "").strip()
        elif line.startswith("TEXT:"):
            in_body = True
        elif in_body:
            body_lines.append(line)
    body = "\n".join(body_lines).strip()
    return subject, body

def main():
    with open(INPUT_CSV, newline="", encoding="utf-8") as infile, \
         open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as outfile:

        reader = csv.DictReader(infile, delimiter=";")
        fieldnames = reader.fieldnames + ["subject", "body"]
        writer = csv.DictWriter(outfile, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()

        for row in reader:
            name = row.get("name", "")
            email = row.get("email", "")
            note = row.get("notiz", "")

            if not email:
                print(f"Überspringe ohne E-Mail: {name}")
                writer.writerow(row)
                continue

            print(f"Generiere Text für: {name} <{email}>")
            try:
                subject, body = generate_email(name, note)
                row["subject"] = subject
                row["body"] = body
                writer.writerow(row)
                print("  -> OK")
            except Exception as e:
                print(f"  -> FEHLER: {e}")
                writer.writerow(row)

            time.sleep(1)  # kleine Pause pro Anfrage

if __name__ == "__main__":
    main()