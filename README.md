# AcadTrack

Student Assignment & Academic Progress Management System

AcadTrack is a Django web application for a department that needs one place to publish assignments, collect student work, request revisions, and record marks. Students see only the work assigned to them. Faculty manage their own subjects and assignments. Administrators maintain users, groups, and records in Django Admin.

The application runs locally with Django templates, the Django ORM, and SQLite. It does not depend on a separate frontend, Redis, Celery, or a paid cloud service.

## Problem statement

Assignment work is often scattered across email, chat, and shared drives. Deadlines are easy to miss, resubmissions overwrite the original file, and students cannot see a consistent record of feedback. Faculty also lack a single view of who has submitted and whose work is still waiting for marks.

AcadTrack keeps the assignment lifecycle in the database: draft, publish, submit, review, revision, and completion. Each attempt is stored separately, so a correction does not erase the previous submission or its feedback.

## Objectives

- Give students a personal dashboard of assigned, pending, overdue, and completed work.
- Let faculty publish assignments to an entire subject or to selected enrolled students.
- Accept text and file submissions with server-side validation.
- Preserve every attempt and attach marks and comments to that attempt.
- Enforce student, faculty, and administrator access on the server.
- Cover the INT253 Django syllabus with working features, not only documentation.

## Features

- Student registration, login with username or email, logout, and profile editing.
- Faculty and administrator accounts are not created by the public registration form.
- Subject catalogue, faculty ownership, and enrollment with a uniqueness constraint.
- Assignment drafts, publication, archival, and deletion when no submissions exist.
- Audience rules: all active enrollments, or an explicit student list.
- Search, filters, sorting, and pagination for assignments and submissions.
- Text and file submission, late-submission rules, and resubmission only after a revision request when the assignment allows it.
- Faculty review with marks, comments, accept, revision request, and an optional “under review” step.
- Student and faculty dashboards calculated from the database.
- Light/dark preference stored in a cookie.
- Login session with a role-based redirect.
- Django Admin for institutional data.
- Custom 403, 404, and 500 pages.
- A four-digit archive route implemented with `re_path()`.

## Technology stack

| Area | Choice |
| --- | --- |
| Language | Python 3 |
| Backend | Django 6 |
| UI | Django templates, HTML, CSS, JavaScript |
| Layout | Bootstrap 5 and Bootstrap Icons, stored under `static/vendor/` |
| Database | SQLite |
| Auth | Django authentication, sessions, groups, and password hashing |
| Tests | Django `TestCase` |

Bootstrap and icon files are vendored in the repository so the interface does not depend on a CDN at runtime.

## Architecture and app structure

```text
AcadTrack/
├── manage.py
├── requirements.txt
├── acadtrack/          Project settings, URLs, upload rules, form styling
├── accounts/           User, student profile, registration, login, groups
├── subjects/           Subjects and enrollments
├── assignments/        Assignment lifecycle, search, archive route
├── submissions/        Attempts, evaluation, authorized downloads
├── dashboard/          Landing page, dashboards, error handlers, template tags
├── templates/
├── static/
└── media/              Uploaded files (not served as a public directory)
```

Authorization helpers live in `accounts/decorators.py` and `accounts/roles.py`. Assignment visibility is centralized in `assignments/queries.py`. Creating an attempt and recording an evaluation run inside database transactions in `submissions/services.py`.

Uploaded source code is stored and downloaded as an attachment. The application never executes it.

## Database models

`accounts.User` extends Django’s user and makes email unique. Passwords are stored with Django’s password hashers.

| Model | Purpose | Important relationships and rules |
| --- | --- | --- |
| `StudentProfile` | Roll number, department, semester | One-to-one with `User`. Roll number is unique. |
| `Subject` | Course offered by the department | Many-to-many with faculty users. Subject code is unique. |
| `Enrollment` | Student membership in a subject | Unique together on student and subject. `is_active` controls visibility. |
| `Assignment` | Coursework created by a faculty member | Foreign keys to subject and creator. Many-to-many targeted students. Drafts are never student-visible. |
| `Submission` | One record per student and assignment | Unique together on student and assignment. Holds the current status and attempt number. |
| `SubmissionAttempt` | One immutable attempt | Unique attempt number within a submission. Stores text, file, timestamp, and late flag. |
| `Evaluation` | Marks and decision for one attempt | One-to-one with the attempt. Marks cannot exceed the assignment maximum. |

Audience rules:

- **All enrolled:** every student with an active enrollment in the subject can see a published or archived assignment.
- **Selected:** only the chosen students, and only if they are still actively enrolled.

Student-facing status:

| Status | Rule |
| --- | --- |
| Not Submitted | No submission, deadline still ahead |
| Overdue | No submission, deadline has passed |
| Submitted | Work is in and waiting for evaluation |
| Under Review | Faculty has started review |
| Revision Requested | Faculty asked for a correction |
| Completed | Faculty accepted the latest evaluated attempt |

A late submission has a submission row, so it is not shown as an unsubmitted overdue assignment.

Completion percentages use this denominator: assignments the person is actually eligible to access. Drafts and another student’s private targeting are excluded. For faculty, the completion rate is accepted pairs divided by eligible student–assignment pairs on published and archived assignments that faculty member created.

## Installation

From the project directory in PowerShell:

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo
python manage.py runserver
```

If activation is blocked, allow local scripts for the current user and try again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

`seed_demo` runs only when `DEBUG` is true. It resets the demonstration account passwords to the value printed by the command. It does not create the superuser. Create that separately and do not reuse the demonstration password for a real administrator.

### Demonstration accounts

These accounts exist only after `seed_demo`. They are not created by production settings.

| Person | Username | Password | Role |
| --- | --- | --- | --- |
| Meera Iyer | `faculty.demo` | `AcadTrack@123` | Faculty |
| Aarav Shah | `student.demo` | `AcadTrack@123` | Student, roll `AT2026001` |
| Priya Nair | `student.priya` | `AcadTrack@123` | Student, roll `AT2026002` |
| Rohan Das | `student.rohan` | `AcadTrack@123` | Student, roll `AT2026003` |

Seeded coursework:

- `CS301` Database Systems and `CS302` Software Engineering, with all three students enrolled.
- **Relational Schema Design** is published to the whole subject. Rohan has one text submission waiting for review.
- **Indexing Exercise** is published only to Aarav and Priya. Rohan cannot see it.
- **Normalization Worksheet** is published and already past its deadline, with late submission turned off.
- **Sprint Planning Draft** stays hidden from students.

To promote a user to faculty, sign in to `/admin/`, add them to the **Faculty** group, and remove the **Students** group if they should not keep a student dashboard. Public registration cannot do this.

## Sample workflow

1. Sign in as `faculty.demo` and open the faculty dashboard.
2. Open **Indexing Exercise** or create a new assignment on `CS301`, set a future deadline, and publish it.
3. Sign out. Sign in as `student.demo`.
4. Open the assignment, read the deadline, and submit text or an allowed file.
5. Sign back in as faculty, open the submission list, and accept the work or request a revision with marks and comments.
6. As the student, open the assignment again. The feedback is on that attempt.
7. If a revision was requested and the assignment allows resubmission, submit again. Attempt 1 and its feedback remain.

A student who opens `/faculty/dashboard/` receives 403. A student who opens another student’s submission or file receives 403. Faculty who did not create an assignment cannot edit or evaluate it.

## INT253 syllabus mapping

### Unit I — Introduction to Django

The repository is a Django project (`acadtrack`) with five installed apps. `manage.py` provides `runserver`, `makemigrations`, `migrate`, `createsuperuser`, `check`, and `test`. Settings configure SQLite, templates, static files, media, authentication backends, and the custom user model. Apps are registered in `INSTALLED_APPS`.

### Unit II — Views and URLs

Views are function-based. Routes use `path()` for normal pages and `re_path()` for `/assignments/archive/2026/` style years. Views read `GET` for search and `POST` for changes, then redirect after a successful change. Missing records return 404. Unauthorized records return 403. The project defines handlers for 403, 404, and 500.

### Unit III — Templates, debugging, and testing

`templates/base.html` loads static files and is extended by the other pages. Templates use variables, `for`, `if`, filters such as `date` and `linebreaks`, and includes for the sidebar, messages, pagination, and form fields. Dashboard numbers come from querysets. `python manage.py test` runs the Django test suite. With `DEBUG` true, unhandled exceptions show Django’s debug page. Set `DJANGO_DEBUG=false` to see the branded 404 and 500 pages. The 403 page is used whenever a signed-in user is denied access.

### Unit IV — Forms

`StudentRegistrationForm`, profile forms, `SubjectForm`, `AssignmentForm`, `AssignmentSubmissionForm`, and `EvaluationForm` validate on the server. Forms use `clean_<field>()` and `clean()`. Templates render field errors and non-field errors. POST forms include the CSRF token. Successful creates and updates redirect instead of re-rendering the POST.

### Unit V — Models, migrations, and Admin

Models use foreign keys, one-to-one links, and many-to-many links, plus uniqueness constraints and indexes. Schema changes go through migrations. Django Admin registers every main model with `list_display`, `list_filter`, `search_fields`, `list_select_related`, fieldsets, and readonly identity fields on historical attempts. Groups **Students** and **Faculty** are created on migrate. The shell can be used for inspection:

```powershell
python manage.py shell
```

### Unit VI — Cookies, sessions, and authentication

Login creates a Django session. Logout requires POST and clears that session. Protected views redirect anonymous users to the login page. The account menu sets `acadtrack_theme` through the response. The cookie lasts one year, is HTTP-only, uses `SameSite=Lax`, and is marked Secure on HTTPS requests. It stores only `light` or `dark`. The server reads it on the next request and applies `data-theme` on the page. The session stores a display name for the greeting. Authorization still uses groups, not the session label.

## Testing

```powershell
venv\Scripts\Activate.ps1
python manage.py check
python manage.py test
```

The suite covers registration and rejection of invalid registration, login, a wrong password, logout, role redirects, faculty and student page denial, theme cookies, CSRF rejection, subject enrollment uniqueness, draft hiding, selected-student targeting, submission validation, late submissions, resubmission limits, preserved attempts, marks limits, evaluation permissions, and dashboard counts.

During tests, Django’s MD5 password hasher is selected so the suite stays fast. Normal `runserver` use keeps Django’s default password hashers.

## Screenshots

Capture these while demonstrating, after `runserver`:

1. Landing page at `/`.
2. Student registration and login.
3. Student dashboard with live counts.
4. Assignment list filters and an assignment detail page.
5. Submission form and submission history.
6. Academic progress page.
7. Faculty dashboard and assignment form.
8. Submission monitoring and evaluation, including an earlier attempt.
9. Profile page and the light/dark control.
10. Django Admin index.
11. 403 page, by visiting `/faculty/dashboard/` as a student.

The landing page uses a navy hero, white content cards, and indigo actions. Signed-in pages use a fixed sidebar on desktop and an off-canvas menu on smaller screens. Tables stack into labeled rows below 720px wide.

## Security notes

- CSRF middleware stays enabled.
- Passwords are hashed by Django. The development `SECRET_KEY` is marked `django-insecure` and is used only when `DEBUG` is true.
- For a non-debug process, set `DJANGO_SECRET_KEY`. `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE` turn on when `DEBUG` is false.
- Views check the group and the specific object. Hiding a link is not the access check.
- Submission and reference files are downloaded through views that check the current user. `/media/` is not mounted as a public URL.
- Allowed submission extensions: pdf, doc, docx, txt, zip, java, py, html, css, js. Maximum size is 5 MB.
- Production responses from the 500 handler do not include exception details.

## Known limitations

- SQLite is the intended database for local demonstration, not for concurrent production traffic.
- There is no email notification when feedback is published.
- File checks use the extension and size. They do not inspect the file contents.
- A faculty member evaluates and edits assignments they created. A superuser can also do so. A colleague on the same subject can view the subject, but cannot evaluate someone else’s assignment.
- Department and semester can be updated by the student. Roll number and role cannot.
- Branded 404 and 500 pages appear when `DEBUG` is false. With `DEBUG` true, unknown URLs show Django’s debug 404, which is useful while developing.
