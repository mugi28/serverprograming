from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    subscriptions = db.relationship('Subscription', backref='user', lazy=True)

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    service_name = db.Column(db.String(100), nullable=False)
    cost = db.Column(db.Float, nullable=False)
    cycle = db.Column(db.String(20), nullable=False)  # monthly/yearly
    payment_date = db.Column(db.Date, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)

    def update_payment_date(self):
        """결제일이 현재 날짜보다 이전이면 다음 결제일로 업데이트"""
        today = datetime.now().date()
        if self.payment_date < today:
            if self.cycle == 'monthly':
                self.payment_date = self.payment_date + timedelta(days=30)
            elif self.cycle == 'yearly':
                self.payment_date = self.payment_date + timedelta(days=365)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscription.id'), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # push/email/sms
    alert_date = db.Column(db.DateTime, nullable=False)

class SharedSubscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscription.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    split_amount = db.Column(db.Float, nullable=False)

class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    monthly_limit = db.Column(db.Float, nullable=False)

