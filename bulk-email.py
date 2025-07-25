import csv
import yagmail

# === Gmail SMTP credentials ===
GMAIL_USER = "YOUR-EMAIL"        # Replace with your Gmail
GMAIL_APP_PASS = "GOOGLE-APP-PASSWORD "      # Google App Password

# === Email Subject ===

subject = "TEMPORARY PAYMENT PROCESSING DELAY - SPERNET MALL"

# === Load HTML template ===
with open("email_template.html", "r", encoding="utf-8") as f:
    email_template = f.read()

# === Load recipients from CSV ===
recipients = []
with open("recipients.csv", newline="", encoding="utf-8") as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        recipients.append(row)

print(f"✅ Loaded {len(recipients)} recipients from CSV")

# === Initialize Yagmail ===
yag = yagmail.SMTP(GMAIL_USER, GMAIL_APP_PASS)

# === Loop through recipients and send email ===
for person in recipients:
    first = person["first_name"].strip()
    last = person["last_name"].strip()
    email = person["email"].strip()

    full_name = f"{first} {last}"

    # Personalize email HTML
    html_content = email_template.format(full_name=full_name)

    try:
        yag.send(to=email, subject=subject, contents=html_content)
        print(f"✅ Sent email to {full_name} <{email}>")
    except Exception as e:
        print(f"❌ Failed to send email to {email}: {e}")

print("🎉 All emails processed!")
