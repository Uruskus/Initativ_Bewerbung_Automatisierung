import csv
import time
import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

INPUT_CSV = "bars_wien.csv"
OUTPUT_CSV = "output_emails.csv"
CV_PATH = "LebenslaufNG25_1.pdf"

PROFILE_TEXT = """
Kurzprofil von Niklas:
- 24 Jahre alt, geboren und aufgewachsen in Wien.
- Kontakt: niklas.geispitzheim3@gmail.com, 0677 64127769.

Berufserfahrung:
- März 2025 – Februar 2025: Koch & Service bei Extra_Würstel.
- August 2022 – Januar 2023: Barkeeper bei Mamas Bar.
- September 2021 – Januar 2022: Servicemitarbeiter im Restaurant Konstantin Filippou.
- September 2020 – September 2020: Praktikum bei Mraz & Sohn.

Ausbildung:
- September 2020 – Juli 2021: Ausbildung zum Fachsozialbetreuer Behindertenarbeit.
- September 2017 – Juli 2018: Gretel-Bergmann-Schule Hamburg (Abschluss Mittlere Reife).
- September 2015 – Juni 2016: MS Afritschgasse Wien (Abschluss Pflichtschule AT).
- September 2011 – Juli 2015: EWMS Karlsplatz.

Besondere Interessen:
- Kunst, Film und andere Arten von Kultur.
"""


def generate_email(name: str, note: str) -> tuple[str, str]:
    """Gibt (subject, body) zurück."""
    note = (note or "").strip() or "eine Bar in Wien"
    name_for_text = (name or "").strip() or "eurer Bar"

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

Hier ist Niklas' Profil (Auszug aus seinem Lebenslauf):
{PROFILE_TEXT}

Zusammenfassung von Niklas:
- Erfahrung im Bar- und Servicebereich, mag direkte Arbeit mit Gästen,
  ist abends und am Wochenende flexibel und sucht längerfristig, nicht nur Ferienjobs.
- Stärken: zuverlässig, teamorientiert, kommunikativ, behält auch in stressigen Nächten den Überblick
  und lernt neue Karten und Abläufe schnell.

Wichtige inhaltliche Wünsche:
- Gehe spürbar auf Niklas' persönliche Fähigkeiten, Stärken und Motivation ein.
- Stelle klar heraus, welchen Mehrwert Niklas für das Team und die Gäste bringt.
- Beziehe dich konkret auf die Besonderheiten der Bar (aus der Notiz) und verknüpfe das mit Niklas' Profil.
- Nutze die Notiz nur als Inspiration: formuliere mit eigenen Worten, übernimm keine Sätze oder Aufzählungen 1:1.
- Der Text darf ruhig etwas ausführlicher sein (mindestens ca. 150 Wörter).

Bitte liefere:
1. Eine passende Betreffzeile.
2. Den E-Mail-Text mit:
   - Anrede: "Hallo liebes Team von {{BAR_NAME}}"
   - 3–5 Absätze
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
        max_tokens=700,
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


def send_email(to_email: str, subject: str, body: str, bar_name: str) -> None:
    """Versendet eine E-Mail mit optional angehängtem Lebenslauf."""
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    sender_email = os.getenv("SENDER_EMAIL", smtp_user or "")

    if not smtp_user or not smtp_password or not sender_email:
        raise RuntimeError(
            "SMTP_USERNAME / SMTP_PASSWORD / SENDER_EMAIL in .env nicht korrekt gesetzt."
        )

    msg = EmailMessage()
    msg["From"] = sender_email
    msg["To"] = to_email
    msg["Subject"] = subject or f"Initiativbewerbung für Barjob bei {bar_name or 'eurer Bar'}"
    msg.set_content(body)

    if os.path.exists(CV_PATH):
        with open(CV_PATH, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype="application",
                subtype="pdf",
                filename=os.path.basename(CV_PATH),
            )
    else:
        print(f"  -> WARNUNG: Lebenslauf '{CV_PATH}' nicht gefunden, sende ohne Anhang.")

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)


def _detect_columns(fieldnames: list[str]) -> tuple[str | None, str | None, str | None]:
    """Versucht, die Spalten für Name, E-Mail und Notiz robust zu erkennen."""
    norm_map = {name.strip().lower(): name for name in fieldnames}

    def find(candidates: list[str]) -> str | None:
        for cand in candidates:
            if cand in norm_map:
                return norm_map[cand]
        return None

    name_col = find(["name", "bar", "barname", "spalte1"])
    email_col = find(["email", "e-mail", "mail", "e-mail adresse", "e-mail"])
    note_col = find(["notiz", "notizen", "notes", "beschreibung"])
    return name_col, email_col, note_col


def main():
    # DRY-RUN-Modus: nur Texte generieren, aber keine E-Mails wirklich versenden
    dry_run = os.getenv("DRY_RUN", "false").strip().lower() in ("1", "true", "yes", "y")

    # Die CSV wurde offenbar in Windows-1252 gespeichert -> dieses Encoding nutzen
    with open(INPUT_CSV, newline="", encoding="cp1252") as infile, \
         open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as outfile:

        # Zuerst echte Kopfzeile finden (bei dir: Zeile mit "Spalte1;E-mail ;Notizen")
        raw_reader = csv.reader(infile, delimiter=";")
        header: list[str] | None = None
        for row in raw_reader:
            if any(cell.strip() for cell in row):
                header = row
                break

        if not header:
            raise RuntimeError("Keine Kopfzeile in der CSV gefunden.")

        # Spalten anhand der gefundenen Kopfzeile erkennen
        name_col, email_col, note_col = _detect_columns(header)

        # DictReader ab der aktuellen Position weiterverwenden, mit expliziten fieldnames
        reader = csv.DictReader(infile, fieldnames=header, delimiter=";")

        fieldnames = header + ["subject", "body", "sent_status"]
        writer = csv.DictWriter(outfile, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()

        for row in reader:
            # Leere Zeilen überspringen
            if not any((str(v).strip() if v is not None else "") for v in row.values()):
                continue

            name = row.get(name_col, "") if name_col else ""
            email = row.get(email_col, "") if email_col else ""
            note = row.get(note_col, "") if note_col else ""

            if not email:
                print(f"Überspringe ohne E-Mail: {name}")
                writer.writerow(row)
                continue

            print(f"Generiere Text für: {name} <{email}>")
            try:
                subject, body = generate_email(name, note)
                row["subject"] = subject
                row["body"] = body

                if dry_run:
                    print("  -> DRY RUN: E-Mail NICHT gesendet, nur in CSV gespeichert.")
                    row["sent_status"] = "DRY_RUN"
                else:
                    print("  -> Sende E-Mail ...")
                    try:
                        send_email(email, subject, body, name)
                        row["sent_status"] = "OK"
                        print("  -> E-Mail gesendet")
                    except Exception as mail_err:
                        row["sent_status"] = f"MAIL_FEHLER: {mail_err}"
                        print(f"  -> MAIL-FEHLER: {mail_err}")

                writer.writerow(row)
            except Exception as e:
                print(f"  -> FEHLER bei Textgenerierung: {e}")
                row["sent_status"] = f"TEXT_FEHLER: {e}"
                writer.writerow(row)

            time.sleep(1)  # kleine Pause pro Anfrage


if __name__ == "__main__":
    main()