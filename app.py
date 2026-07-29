import os
from collections import Counter
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, abort

from config import Config
from extensions import db
from models import Kid, Chore, Completion, Redemption
from utils import save_upload, delete_upload, admin_required

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    with app.app_context():
        db.create_all()

    register_routes(app)
    return app


def register_routes(app):

    # ---------------------------------------------------------------- kid side

    @app.route("/")
    def index():
        kids = Kid.query.filter_by(active=True).order_by(Kid.name).all()
        return render_template("index.html", kids=kids)

    @app.route("/kid/<int:kid_id>")
    def kid_detail(kid_id):
        kid = Kid.query.get_or_404(kid_id)
        chores = Chore.query.filter_by(kid_id=kid.id, active=True).order_by(Chore.name).all()
        chore_status = [
            {"chore": c, "done": c.completed_this_period() is not None} for c in chores
        ]
        recent = (
            Completion.query.filter_by(kid_id=kid.id)
            .order_by(Completion.timestamp.desc())
            .limit(10)
            .all()
        )
        return render_template(
            "kid_detail.html", kid=kid, chore_status=chore_status, recent=recent
        )

    @app.route("/kid/<int:kid_id>/complete/<int:chore_id>", methods=["POST"])
    def complete_chore(kid_id, chore_id):
        chore = Chore.query.filter_by(id=chore_id, kid_id=kid_id).first_or_404()
        kid = Kid.query.get_or_404(kid_id)
        wants_json = request.accept_mimetypes.best == "application/json"

        if not chore.completed_this_period():
            completion = Completion(
                chore_id=chore.id,
                kid_id=kid_id,
                tokens_awarded=chore.tokens,
                chore_name_snapshot=chore.name,
            )
            db.session.add(completion)
            db.session.commit()
            if wants_json:
                return jsonify(
                    status="completed",
                    tokens_awarded=chore.tokens,
                    balance=kid.balance(),
                )
            flash(f"Nice work! +{chore.tokens} tokens for {chore.name}.", "success")
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
            profile_file = request.files.get("profile_image")
            new_profile = save_upload(profile_file, "kids")
            if new_profile:
                delete_upload(kid.profile_image, "kids")
                kid.profile_image = new_profile

            token_file = request.files.get("token_image")
            new_token = save_upload(token_file, "tokens")
            if new_token:
                delete_upload(kid.token_image, "tokens")
                kid.token_image = new_token
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
        delete_upload(kid.profile_image, "kids")
        delete_upload(kid.token_image, "tokens")
        for chore in kid.chores:
            delete_upload(chore.image, "chores")
        db.session.delete(kid)
        db.session.commit()
        flash("Kid removed.", "success")
        return redirect(url_for("admin_kids"))

    # --- chores CRUD ---

    @app.route("/admin/kids/<int:kid_id>/chores")
    @admin_required
    def admin_chores(kid_id):
        kid = Kid.query.get_or_404(kid_id)
        chores = Chore.query.filter_by(kid_id=kid.id).order_by(Chore.name).all()
        return render_template("admin/chores.html", kid=kid, chores=chores)

    @app.route("/admin/kids/<int:kid_id>/chores/new", methods=["GET", "POST"])
    @admin_required
    def admin_chore_new(kid_id):
        kid = Kid.query.get_or_404(kid_id)
        if request.method == "POST":
            return _save_chore(kid, None)
        return render_template("admin/chore_form.html", kid=kid, chore=None)

    @app.route("/admin/kids/<int:kid_id>/chores/<int:chore_id>/edit", methods=["GET", "POST"])
    @admin_required
    def admin_chore_edit(kid_id, chore_id):
        kid = Kid.query.get_or_404(kid_id)
        chore = Chore.query.filter_by(id=chore_id, kid_id=kid.id).first_or_404()
        if request.method == "POST":
            return _save_chore(kid, chore)
        return render_template("admin/chore_form.html", kid=kid, chore=chore)

    def _save_chore(kid, chore):
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

        is_new = chore is None
        if is_new:
            chore = Chore(kid_id=kid.id, name=name, tokens=tokens, frequency=frequency, active=active)
        else:
            chore.name = name
            chore.tokens = tokens
            chore.frequency = frequency
            chore.active = active

        try:
            image_file = request.files.get("image")
            new_image = save_upload(image_file, "chores")
            if new_image:
                delete_upload(chore.image, "chores")
                chore.image = new_image
        except ValueError as e:
            flash(str(e), "error")
            return redirect(request.url)

        if is_new:
            db.session.add(chore)
        db.session.commit()
        flash(f"Saved {chore.name}.", "success")
        return redirect(url_for("admin_chores", kid_id=kid.id))

    @app.route("/admin/kids/<int:kid_id>/chores/<int:chore_id>/delete", methods=["POST"])
    @admin_required
    def admin_chore_delete(kid_id, chore_id):
        chore = Chore.query.filter_by(id=chore_id, kid_id=kid_id).first_or_404()
        delete_upload(chore.image, "chores")
        db.session.delete(chore)
        db.session.commit()
        flash("Chore removed.", "success")
        return redirect(url_for("admin_chores", kid_id=kid_id))

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

    @app.route("/admin/api/stats/completions_by_chore")
    @admin_required
    def api_completions_by_chore():
        rows = (
            db.session.query(Chore.name, db.func.count(Completion.id))
            .join(Completion, Completion.chore_id == Chore.id)
            .group_by(Chore.id)
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
