from datetime import datetime, timedelta

from extensions import db


class Kid(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    profile_image = db.Column(db.String(255))  # filename in static/uploads/kids
    token_image = db.Column(db.String(255))    # filename in static/uploads/tokens
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    chores = db.relationship(
        "Chore", backref="kid", lazy=True, cascade="all, delete-orphan",
        order_by="Chore.name",
    )
    completions = db.relationship(
        "Completion", backref="kid", lazy=True, cascade="all, delete-orphan"
    )
    redemptions = db.relationship(
        "Redemption", backref="kid", lazy=True, cascade="all, delete-orphan"
    )

    def total_earned(self):
        return sum(c.tokens_awarded for c in self.completions)

    def total_spent(self):
        return sum(r.tokens_spent for r in self.redemptions)

    def balance(self):
        return self.total_earned() - self.total_spent()


class Chore(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kid_id = db.Column(db.Integer, db.ForeignKey("kid.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    tokens = db.Column(db.Integer, nullable=False, default=1)
    frequency = db.Column(db.String(10), nullable=False, default="daily")  # daily|weekly
    image = db.Column(db.String(255))  # filename in static/uploads/chores
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    completions = db.relationship(
        "Completion", backref="chore", lazy=True, cascade="all, delete-orphan"
    )

    def period_start(self, now=None):
        now = now or datetime.utcnow()
        if self.frequency == "weekly":
            start_date = (now - timedelta(days=now.weekday())).date()
        else:
            start_date = now.date()
        return datetime(start_date.year, start_date.month, start_date.day)

    def completed_this_period(self, now=None):
        start = self.period_start(now)
        return Completion.query.filter(
            Completion.chore_id == self.id, Completion.timestamp >= start
        ).first()

    def next_reset_label(self):
        return "tomorrow" if self.frequency == "daily" else "next Monday"


class Completion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chore_id = db.Column(db.Integer, db.ForeignKey("chore.id"), nullable=False)
    kid_id = db.Column(db.Integer, db.ForeignKey("kid.id"), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    tokens_awarded = db.Column(db.Integer, nullable=False)
    # snapshot of the chore name at completion time, so history stays readable
    # even if the chore is later renamed or deleted
    chore_name_snapshot = db.Column(db.String(120))


class Redemption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kid_id = db.Column(db.Integer, db.ForeignKey("kid.id"), nullable=False)
    description = db.Column(db.String(255))
    tokens_spent = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
