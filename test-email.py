import yagmail

GMAIL_USER = "nyagahdev@gmail.com"
GMAIL_APP_PASS = "sfsykkzqjqgeptiu"

# Gmail SMTP (SSL on 465)
yag = yagmail.SMTP(
    user=GMAIL_USER,
    password=GMAIL_APP_PASS,
    host="smtp.gmail.com",
    port=465,
    smtp_ssl=True
)

# Load the HTML email template
with open("email_template.html", "r", encoding="utf-8") as f:
    html_content = f.read()

# Send a test email
yag.send(
    to="nyagahdev@gmail.com",
    subject="Important Notice: Temporary Payment Processing Delay",
    contents=html_content
)

print("✅ HTML Email sent successfully!")
