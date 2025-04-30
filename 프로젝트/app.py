from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
import traceback

from models import db, User, Subscription, Notification, SharedSubscription, Budget

load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'mysql://root:0328@localhost/subscription_db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 라우트
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('이메일 또는 비밀번호가 올바르지 않습니다.')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not username or not email or not password or not confirm_password:
            flash('모든 필드를 입력해주세요.')
            return redirect(url_for('register'))

        if password != confirm_password:
            flash('비밀번호가 일치하지 않습니다.')
            return redirect(url_for('register'))

        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            flash('이미 등록된 이메일입니다.')
            return redirect(url_for('register'))

        try:
            hashed_password = generate_password_hash(password)
            new_user = User(username=username, email=email, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            print("Error:", str(e))
            print(traceback.format_exc())
            flash('회원가입 중 오류가 발생했습니다. 다시 시도해주세요.')
            return redirect(url_for('register'))
            
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    subscriptions = Subscription.query.filter_by(user_id=current_user.id).all()
    total_cost = sum(sub.cost if sub.cycle == 'monthly' else sub.cost / 12 for sub in subscriptions)
    today = datetime.now().date()

    # 현재 날짜 이후의 결제일만 고려
    next_payment = min(
        (sub.payment_date for sub in subscriptions if sub.payment_date >= today),
        default=None
    )

    return render_template('dashboard.html', 
                           total_cost=total_cost,
                           subscription_count=len(subscriptions),
                           next_payment=next_payment,
                           today=today)

@app.route('/subscriptions')
@login_required
def subscriptions():
    subscriptions = Subscription.query.filter_by(user_id=current_user.id).all()
    return render_template('subscriptions.html', subscriptions=subscriptions)

@app.route('/subscriptions/add', methods=['GET', 'POST'])
@login_required
def add_subscription():
    if request.method == 'POST':
        try:
            service_name = request.form.get('service_name')
            cost = float(request.form.get('cost'))
            cycle = request.form.get('cycle')
            payment_date = datetime.strptime(request.form.get('payment_date'), '%Y-%m-%d').date()
            payment_method = request.form.get('payment_method')

            subscription = Subscription(
                user_id=current_user.id,
                service_name=service_name,
                cost=cost,
                cycle=cycle,
                payment_date=payment_date,
                payment_method=payment_method
            )

            db.session.add(subscription)
            db.session.commit()
            flash('구독이 성공적으로 추가되었습니다.')
            return redirect(url_for('subscriptions'))
        except Exception as e:
            db.session.rollback()
            flash('구독 추가 중 오류가 발생했습니다.')
            print("Error:", str(e))
            return redirect(url_for('add_subscription'))

    return render_template('subscription_add.html')

@app.route('/subscriptions/edit/<int:subscription_id>', methods=['GET', 'POST'])
@login_required
def edit_subscription(subscription_id):
    subscription = Subscription.query.get_or_404(subscription_id)
    if subscription.user_id != current_user.id:
        flash('접근 권한이 없습니다.')
        return redirect(url_for('subscriptions'))

    if request.method == 'POST':
        try:
            subscription.service_name = request.form.get('service_name')
            subscription.cost = float(request.form.get('cost'))
            subscription.cycle = request.form.get('cycle')
            subscription.payment_date = datetime.strptime(request.form.get('payment_date'), '%Y-%m-%d').date()
            subscription.payment_method = request.form.get('payment_method')

            db.session.commit()
            flash('구독 정보가 수정되었습니다.')
            return redirect(url_for('subscriptions'))
        except Exception as e:
            db.session.rollback()
            flash('구독 수정 중 오류가 발생했습니다.')
            print("Error:", str(e))
            return redirect(url_for('edit_subscription', subscription_id=subscription_id))

    return render_template('subscription_edit.html', subscription=subscription)

@app.route('/subscriptions/delete/<int:subscription_id>', methods=['GET', 'POST'])
@login_required
def delete_subscription(subscription_id):
    subscription = Subscription.query.get_or_404(subscription_id)
    if subscription.user_id != current_user.id:
        flash('접근 권한이 없습니다.')
        return redirect(url_for('subscriptions'))

    try:
        db.session.delete(subscription)
        db.session.commit()
        flash('구독이 삭제되었습니다.')
    except Exception as e:
        db.session.rollback()
        flash('구독 삭제 중 오류가 발생했습니다.')
        print("Error:", str(e))

    return redirect(url_for('subscriptions'))

@app.route('/visualization')
@login_required
def visualization():
    subscriptions = Subscription.query.filter_by(user_id=current_user.id).all()
    
    # 월간 구독과 연간 구독을 월 단위로 통일
    subscription_data = []
    for sub in subscriptions:
        monthly_cost = sub.cost if sub.cycle == 'monthly' else sub.cost / 12
        subscription_data.append({
            'name': sub.service_name,
            'cost': monthly_cost
        })
    
    # 총 월간 비용 계산
    total_monthly_cost = sum(item['cost'] for item in subscription_data)
    
    # 비율 계산
    for item in subscription_data:
        item['percentage'] = (item['cost'] / total_monthly_cost * 100) if total_monthly_cost > 0 else 0
    
    return render_template('visualization.html', 
                         subscription_data=subscription_data,
                         total_monthly_cost=total_monthly_cost)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 