# PDF Test Portal (Python + HTML + CSS)

Flask server PDF ko watermark wali images mein badal kar dikhata hai. Asli PDF phone tak kabhi nahi jaata.

## Render par deploy
1. Telegram: @BotFather se bot banao (token), bot ko ek message bhejo, @userinfobot se apni chat id lo.
2. GitHub par **private** repo banao, ye poora folder upload karo (papers/ mein 3 PDF: Maths.pdf, Science.pdf, English.pdf).
3. render.com > New > Web Service > repo chuno. Settings:
   - Runtime: Python 3
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app --workers 1 --threads 4 --timeout 60`  (workers 1 hi rakhna)
   - Instance Type: Free
4. Environment variables: SECRET_KEY (lamba random text), STUDENT_PASSWORD, STUDENT_NAME (watermark mein aayega), TG_TOKEN, TG_CHAT_ID. Optional: TEST_MINUTES (default 60).
5. UptimeRobot (free): HTTP monitor `https://<app>.onrender.com/health`, 5 min interval (app ke andar ka self-ping ke saath backup).

## PDF upload / delete
GitHub repo > papers folder > Add file > Upload (ya PDF kholo > trash icon > Commit). Render khud redeploy karta hai.
Subject ka naam = file ka naam. Naya hafta: purani PDFs delete karke nayi daalo.
