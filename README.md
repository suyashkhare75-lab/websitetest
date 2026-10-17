# Student Test Portal

Responsive Flask website for phone, tablet and laptop. No admin dashboard. PDFs are added/removed by committing files to the GitHub repository. Students sign in using a PIN configured as an environment variable in Render.

## 1) Add PDFs
Put these files in `papers/`:
- `subject1.pdf`
- `subject2.pdf`
- `subject3.pdf`

Edit the names in `SUBJECTS` inside `app.py` if you want labels such as Physics, Chemistry and Biology. Keep each `file` value aligned with the PDF filename.

**Repository privacy:** If the GitHub repository is public, anyone may be able to fetch the PDFs. For private test papers, keep the repo private and check your hosting deployment's access permissions. PDFs served to an authenticated student can still be captured or downloaded; a normal website cannot provide DRM.

## 2) Run locally
Python 3.10+ recommended.
```bash
pip install -r requirements.txt
```
Set environment variables:
- `SECRET_KEY`: long random secret
- `STUDENT_PIN`: test PIN shared with the student
- `PAPERS_DIR`: optional; defaults to `papers`

Run:
```bash
python app.py
```
Visit `http://127.0.0.1:10000`.

## 3) Deploy to Render
1. Push the files to GitHub.
2. In Render choose **New + > Blueprint**, connect the repository, and deploy the `render.yaml`.
3. In Render Environment set `STUDENT_PIN` to a strong/unpredictable PIN. `SECRET_KEY` is generated from the Blueprint.
4. Open your Render URL. It redirects to `/student/login`.
5. To replace/remove a paper, commit the changed PDF file in GitHub and let Render redeploy. To remove a paper, delete the matching PDF and push; the card will show it as unavailable after redeploy.
6. The app exposes `/healthz` and Render checks this path for service health. A health check is not a keep-awake ping.

## What monitoring does
- Best-effort events for page hidden/visible, page exit, copy, context menu, and fullscreen exit.
- Events are stored in SQLite under `data/activity.sqlite3`; this starter has no admin dashboard or external notification delivery. For a practical monitor, add a private alert channel or log viewing endpoint with authentication.
- There is no mechanism to guarantee that alerts arrive on your phone from this website as currently written.
- The Wake Lock API requests the screen stay awake after a tap. Browser/device can refuse or revoke it.
- Cannot reliably block screenshots, screen recording, external camera photos, app switching, split-screen or OS-level controls.
- A normal website cannot enforce a secure exam kiosk. Use Android Enterprise kiosk/lock-task mode or a dedicated managed exam app on a device you administer if strict device lockdown is needed.
- Render Free web services spin down after 15 minutes without inbound traffic and have ephemeral storage. An in-app timer cannot keep a sleeping service awake because it stops when the process sleeps, and a health check does not override the Free plan's sleep policy. Use a paid always-on web service for dependable availability. External uptime monitoring can check `/healthz` and alert on outages, but should not be treated as a guarantee that a Free service stays awake.
- Local SQLite logs may be lost on redeploy/restart/spin-down on the Free plan. Use a persistent database/storage for durable logs.
