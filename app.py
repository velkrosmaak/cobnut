import hashlib
from collections import Counter
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, Response
from sqlalchemy import inspect, text

from config import Config
from extensions import db
from models import Kid, Job, Completion, Redemption
from utils import read_image_upload, admin_required

load_dotenv()

# Columns added after the initial release, for existing jobs.db files that
# predate the switch to storing images as blobs in the database. SQLite
# supports ALTER TABLE ADD COLUMN, so this brings an older database up to
# date in place without losing any existing kid/job/history data.
REQUIRED_COLUMNS = {
    "kid": {
        "profile_image_data": "BLOB",
        "profile_image_mime": "TEXT",
        "token_image_data": "BLOB",
        "token_image_mime": "TEXT",
    },
    "job": {
        "image_data": "BLOB",
        "image_mime": "TEXT",
    },
}


def ensure_schema(engine):
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in REQUIRED_COLUMNS.items():
            if table not in existing_tables:
                continue  # db.create_all() will have created it with the right columns already
            existing_columns = {c["name"] for c in inspector.get_columns(table)}
            for name, col_type in columns.items():
                if name not in existing_columns:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {col_type}"))


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    with app.app_context():
        db.create_all()
        ensure_schema(db.engine)

    register_routes(app)
    return app


def serve_image(data, mimetype):
    if not data:
        return Response(status=404)
    response = Response(data, mimetype=mimetype or "application/octet-stream")
    response.set_etag(hashlib.md5(data).hexdigest())
    response.cache_control.public = True
    response.cache_control.max_age = 86400
    return response.make_conditional(request)


def register_routes(app):

    # ------------------------------------------------------------- media (DB-backed images)

    @app.route("/media/kid/<int:kid_id>/profile")
    def media_kid_profile(kid_id):
        kid = Kid.query.get_or_404(kid_id)
        return serve_image(kid.profile_image_data, kid.profile_image_mime)

    @app.route("/media/kid/<int:kid_id>/token")
    def media_kid_token(kid_id):
        kid = Kid.query.get_or_404(kid_id)
        return serve_image(kid.token_image_data, kid.token_image_mime)

    @app.route("/media/job/<int:job_id>/image")
    def media_job_image(job_id):
        job = Job.query.get_or_404(job_id)
        return serve_image(job.image_data, job.image_mime)

    # ---------------------------------------------------------------- kid side

    @app.route("/")
    def index():
        kids = Kid.query.filter_by(active=True).order_by(Kid.name).all()
        return render_template("index.html", kids=kids)

    @app.route("/kid/<int:kid_id>")
    def kid_detail(kid_id):
        kid = Kid.query.get_or_404(kid_id)
        jobs = Job.query.filter_by(kid_id=kid.id, active=True).order_by(Job.name).all()
        job_status = [
            {"job": c, "done": c.completed_this_period() is not None} for c in jobs
        ]
        recent = (
            Completion.query.filter_by(kid_id=kid.id)
            .order_by(Completion.timestamp.desc())
            .limit(10)
            .all()
        )
        return render_template(
            "kid_detail.html", kid=kid, job_status=job_status, recent=recent
        )

    @app.route("/kid/<int:kid_id>/complete/<int:job_id>", methods=["POST"])
    def complete_job(kid_id, job_id):
        job = Job.query.filter_by(id=job_id, kid_id=kid_id).first_or_404()
        kid = Kid.query.get_or_404(kid_id)
        wants_json = request.accept_mimetypes.best == "application/json"

        if not job.completed_this_period():
            completion = Completion(
                job_id=job.id,
                kid_id=kid_id,
                tokens_awarded=job.tokens,
                job_name_snapshot=job.name,
            )
            db.session.add(completion)
            db.session.commit()
            if wants_json:
                return jsonify(
                    status="completed",
                    tokens_awarded=job.tokens,
                    balance=kid.balance(),
                )
            flash(f"Nice work! +{job.tokens} tokens for {job.name}.", "success")
        else:
            if wants_json:
                return jsonify(status="already_done", balance=kid.balance())
            flash("Already done for this period.", "info")
        return redirect(url_for("kid_detail", kid_id=kid_id))

    # ------------------------------------------------------------------ admin

    @app.route("/admin/")
    @admin_required
    def admin_dashboard():
        kids = Kid.query.order_by(Kid.name).all()
        recent = Completion.query.order_by(Completion.timestamp.desc()).limit(15).all()
        return render_template("admin/dashboard.html", kids=kids, recent=recent)

    # --- kids CRUD ---

    @app.route("/admin/kids")
    @admin_required
    def admin_kids():
        kids = Kid.query.order_by(Kid.name).all()
        return render_template("admin/kids.html", kids=kids)

    @app.route("/admin/kids/new", methods=["GET", "POST"])
    @admin_required
    def admin_kid_new():
        if request.method == "POST":
            return _save_kid(None)
        return render_template("admin/kid_form.html", kid=None)

    @app.route("/admin/kids/<int:kid_id>/edit", methods=["GET", "POST"])
    @admin_required
    def admin_kid_edit(kid_id):
        kid = Kid.query.get_or_404(kid_id)
        if request.method == "POST":
            return _save_kid(kid)
        return render_template("admin/kid_form.html", kid=kid)

    def _save_kid(kid):
        name = request.form.get("name", "").strip()
        active = bool(request.form.get("active"))
        if not name:
            flash("Name is required.", "error")
            return redirect(request.url)

        is_new = kid is None
        if is_new:
            kid = Kid(name=name, active=active)
        else:
            kid.name = name
            kid.active = active

        try:
            profile_upload = read_image_upload(request.files.get("profile_image"))
            if profile_upload:
                kid.profile_image_data, kid.profile_image_mime = profile_upload

            token_upload = read_image_upload(request.files.get("token_image"))
            if token_upload:
                kid.token_image_data, kid.token_image_mime = token_upload
        except ValueError as e:
            flash(str(e), "error")
            return redirect(request.url)

        if is_new:
            db.session.add(kid)
        db.session.commit()
        flash(f"Saved {kid.name}.", "success")
        return redirect(url_for("admin_kids"))

    @app.route("/admin/kids/<int:kid_id>/delete", methods=["POST"])
    @admin_required
    def admin_kid_delete(kid_id):
        kid = Kid.query.get_or_404(kid_id)
        db.session.delete(kid)
        db.session.commit()
        flash("Kid removed.", "success")
        return redirect(url_for("admin_kids"))

    # --- jobs CRUD ---

    @app.route("/admin/kids/<int:kid_id>/jobs")
    @admin_required
    def admin_jobs(kid_id):
        kid = Kid.query.get_or_404(kid_id)
        jobs = Job.query.filter_by(kid_id=kid.id).order_by(Job.name).all()
        return render_template("admin/jobs.html", kid=kid, jobs=jobs)

    @app.route("/admin/kids/<int:kid_id>/jobs/new", methods=["GET", "POST"])
    @admin_required
    def admin_job_new(kid_id):
        kid = Kid.query.get_or_404(kid_id)
        if request.method == "POST":
            return _save_job(kid, None)
        return render_template("admin/job_form.html", kid=kid, job=None)

    @app.route("/admin/kids/<int:kid_id>/jobs/<int:job_id>/edit", methods=["GET", "POST"])
    @admin_required
    def admin_job_edit(kid_id, job_id):
        kid = Kid.query.get_or_404(kid_id)
        job = Job.query.filter_by(id=job_id, kid_id=kid.id).first_or_404()
        if request.method == "POST":
            return _save_job(kid, job)
        return render_template("admin/job_form.html", kid=kid, job=job)

    def _save_job(kid, job):
        name = request.form.get("name", "").strip()
        tokens = request.form.get("tokens", "1").strip()
        frequency = request.form.get("frequency", "daily")
        active = bool(request.form.get("active"))

        if not name:
            flash("Name is required.", "error")
            return redirect(request.url)
        try:
            tokens = int(tokens)
            if tokens < 0:
                raise ValueError
        except ValueError:
            flash("Tokens must be a non-negative whole number.", "error")
            return redirect(request.url)
        if frequency not in ("daily", "weekly"):
            frequency = "daily"

        is_new = job is None
        if is_new:
            job = Job(kid_id=kid.id, name=name, tokens=tokens, frequency=frequency, active=active)
        else:
            job.name = name
            job.tokens = tokens
            job.frequency = frequency
            job.active = active

        try:
            image_upload = read_image_upload(request.files.get("image"))
            if image_upload:
                job.image_data, job.image_mime = image_upload
        except ValueError as e:
            flash(str(e), "error")
            return redirect(request.url)

        if is_new:
            db.session.add(job)
        db.session.commit()
        flash(f"Saved {job.name}.", "success")
        return redirect(url_for("admin_jobs", kid_id=kid.id))

    @app.route("/admin/kids/<int:kid_id>/jobs/<int:job_id>/delete", methods=["POST"])
    @admin_required
    def admin_job_delete(kid_id, job_id):
        job = Job.query.filter_by(id=job_id, kid_id=kid_id).first_or_404()
        db.session.delete(job)
        db.session.commit()
        flash("Job removed.", "success")
        return redirect(url_for("admin_jobs", kid_id=kid_id))

    # --- redemptions ---

    @app.route("/admin/kids/<int:kid_id>/redeem", methods=["POST"])
    @admin_required
    def admin_redeem(kid_id):
        kid = Kid.query.get_or_404(kid_id)
        description = request.form.get("description", "").strip() or "Reward redeemed"
        tokens_spent = request.form.get("tokens_spent", "0").strip()
        try:
            tokens_spent = int(tokens_spent)
            if tokens_spent <= 0:
                raise ValueError
        except ValueError:
            flash("Tokens spent must be a positive whole number.", "error")
            return redirect(url_for("admin_kids"))

        db.session.add(Redemption(kid_id=kid.id, description=description, tokens_spent=tokens_spent))
        db.session.commit()
        flash(f"Recorded redemption for {kid.name}.", "success")
        return redirect(url_for("admin_kids"))

    # --- stats ---

    @app.route("/admin/stats")
    @admin_required
    def admin_stats():
        kids = Kid.query.order_by(Kid.name).all()
        return render_template("admin/stats.html", kids=kids)

    @app.route("/admin/api/stats/tokens_per_kid")
    @admin_required
    def api_tokens_per_kid():
        kids = Kid.query.order_by(Kid.name).all()
        return jsonify({
            "labels": [k.name for k in kids],
            "earned": [k.total_earned() for k in kids],
            "balance": [k.balance() for k in kids],
        })

    @app.route("/admin/api/stats/completions_by_hour")
    @admin_required
    def api_completions_by_hour():
        rows = Completion.query.all()
        counts = Counter(c.timestamp.hour for c in rows)
        return jsonify({"labels": list(range(24)), "counts": [counts.get(h, 0) for h in range(24)]})

    @app.route("/admin/api/stats/completions_by_weekday")
    @admin_required
    def api_completions_by_weekday():
        rows = Completion.query.all()
        counts = Counter(c.timestamp.weekday() for c in rows)
        labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        return jsonify({"labels": labels, "counts": [counts.get(i, 0) for i in range(7)]})

    @app.route("/admin/api/stats/completions_by_job")
    @admin_required
    def api_completions_by_job():
        rows = (
            db.session.query(Job.name, db.func.count(Completion.id))
            .join(Completion, Completion.job_id == Job.id)
            .group_by(Job.id)
            .order_by(db.func.count(Completion.id).desc())
            .limit(15)
            .all()
        )
        return jsonify({"labels": [r[0] for r in rows], "counts": [r[1] for r in rows]})

    @app.errorhandler(413)
    def too_large(e):
        flash("That image is too large (max 8MB).", "error")
        return redirect(request.referrer or url_for("index"))


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
