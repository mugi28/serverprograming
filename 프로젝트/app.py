from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
import traceback
from collections import defaultdict
from flask_migrate import Migrate

from models import db, User, Subscription, Notification, SharedSubscription, Budget, History

load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'mysql://root:root@localhost/subscription_db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)
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


# 구독 목록 + 공동 구독 목록
@app.route('/subscriptions')
@login_required
def subscriptions():
    # 개인 구독 조회
    personal_subscriptions = Subscription.query.filter_by(user_id=current_user.id).all()

    # 공동 구독: 사용자가 참여 중인 SharedSubscription + Subscription 조인
    shared_raw = db.session.query(SharedSubscription, Subscription, User)\
    .join(Subscription, SharedSubscription.subscription_id == Subscription.id)\
    .join(User, SharedSubscription.user_id == User.id)\
    .filter(SharedSubscription.subscription_id.in_(
        db.session.query(Subscription.id).filter_by(user_id=current_user.id)
    )).all()

    grouped_shared = defaultdict(list)

    for shared, sub, user in shared_raw:
        grouped_shared[sub.id].append({
            'username': user.username,
            'user_id': user.id,
            'payment_status': shared.payment_status
        })

    # 가공된 리스트 생성
    shared_subscriptions = []
    for sub_id, participants in grouped_shared.items():
        first_shared, first_sub, _ = next(
            ((s, sub, u) for s, sub, u in shared_raw if sub.id == sub_id), None
        )

        statuses = [p['payment_status'] for p in participants]
        all_done = all(s == '완료' for s in statuses)

        shared_subscriptions.append({
            'id': sub_id,
            'subscription_id': sub_id,
            'service_name': first_sub.service_name,
            'cost': first_sub.cost,
            'participants': participants,
            'payment_status': '완료' if all_done else '미완료'
        })

     # 🔽 사용자 전체 리스트 전달 (본인은 제외할 수도 있음)
    all_users = User.query.all()

    return render_template(
        'subscriptions.html',
        subscriptions=personal_subscriptions,
        shared_subscriptions=shared_subscriptions,
        users=all_users
    )


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
            db.session.flush()  # subscription.id를 얻기 위해

            # History에도 기록
            history = History(
                user_id=current_user.id,
                service_name=service_name,
                cost=cost,
                cycle=cycle,
                payment_date=payment_date,
                payment_method=payment_method,
                added_at=datetime.utcnow()
            )
            db.session.add(history)

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



@app.route('/visualization', methods=['GET', 'POST'])
@login_required
def visualization():
    # POST 요청: 예산 설정 처리
    if request.method == 'POST':
        budget_month = request.form.get('budget_month')  # YYYY-MM 형식
        monthly_limit = request.form.get('monthly_limit')

        # 입력 검증
        try:
            # budget_month 형식 검증 (YYYY-MM)
            year, month = map(int, budget_month.split('-'))
            datetime(year, month, 1)  # 유효한 날짜인지 확인
        except (ValueError, TypeError):
            flash('올바른 날짜 형식을 입력해주세요 (YYYY-MM).')
            return redirect(url_for('visualization'))

        try:
            monthly_limit = float(monthly_limit)
            if monthly_limit < 0:
                flash('예산은 0 이상이어야 합니다.')
                return redirect(url_for('visualization'))
        except (ValueError, TypeError):
            flash('올바른 금액을 입력해주세요.')
            return redirect(url_for('visualization'))

        # 기존 예산 조회
        budget = Budget.query.filter_by(user_id=current_user.id, budget_month=budget_month).first()
        try:
            if budget:
                # 기존 예산 수정
                budget.monthly_limit = monthly_limit
            else:
                # 새 예산 생성
                new_budget = Budget(
                    user_id=current_user.id,
                    monthly_limit=monthly_limit,
                    budget_month=budget_month
                )
                db.session.add(new_budget)
            db.session.commit()
            flash('예산이 성공적으로 설정되었습니다.')
        except Exception as e:
            db.session.rollback()
            flash('예산 설정 중 오류가 발생했습니다.')
            print("Error:", str(e))

        return redirect(url_for('visualization'))
    
    # GET 요청: 시각화 데이터 표시
    # 사용자의 구독 정보 가져오기
    subscriptions = Subscription.query.filter_by(user_id=current_user.id).all()
    
    # 오늘 날짜 (현재 날짜)
    today = datetime.now()
    
    # 최근 6개월의 월별 지출 계산
    monthly_expenses = {}
    months = []
    for i in range(5, -1, -1):  # 최근 6개월 (현재 달 포함)
        month = (today - timedelta(days=30 * i)).strftime('%Y-%m')
        months.append(month)
        monthly_expenses[month] = 0

    history_items = History.query.filter_by(user_id=current_user.id).all()
    for h in history_items:
        # h.added_at 또는 h.payment_date를 기준으로 월별 집계
        cost = h.cost if h.cycle == 'monthly' else h.cost / 12
        start_date = h.payment_date
        payment_day = start_date.day  # 결제일의 "일자"

        for month in months:
            year, month_num = map(int, month.split('-'))
            # 해당 달의 결제일 생성
            try:
                payment_date = datetime(year, month_num, payment_day)
            except ValueError:
                # 2월 29일과 같은 경우, 마지막 날로 조정
                payment_date = datetime(year, month_num, 28 if month_num == 2 else 30)

            # 구독 시작 이후이고, 오늘 날짜 이전인 경우에만 지출 추가
            # payment_date.date()로 날짜만 비교
            if start_date <= payment_date.date() and payment_date <= today:
                monthly_expenses[month] += cost

    # 월별 예산 조회
    monthly_budgets = {}
    for month in months:
        budget = Budget.query.filter_by(user_id=current_user.id, budget_month=month).first()
        monthly_budgets[month] = budget.monthly_limit if budget else 0

    return render_template('visualization.html', 
                         monthly_expenses=monthly_expenses,
                         monthly_budgets=monthly_budgets,
                         months=months)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

#공동 구독 추가
@app.route('/shared_subscriptions/add', methods=['POST'])
@login_required
def add_shared_subscription():
    try:
        subscription_id = int(request.form.get('subscription_id'))
        shared_user_ids = request.form.getlist('shared_user_ids')
        payment_status = request.form.get('payment_status', '미완료')

        existing = SharedSubscription.query.filter(
            SharedSubscription.subscription_id == subscription_id,
            SharedSubscription.user_id.in_(shared_user_ids)
        ).all()

        if existing:
            flash('이미 등록된 공동 구독입니다.')
            return redirect(url_for('subscriptions'))

        subscription = Subscription.query.get_or_404(subscription_id)
        num_users = len(shared_user_ids)

        if num_users == 0:
            flash('참여자를 한 명 이상 선택해주세요.')
            return redirect(url_for('subscriptions'))

        per_user_amount = round(subscription.cost / num_users, 2)

        for user_id in shared_user_ids:
            shared = SharedSubscription(
                subscription_id=subscription_id,
                user_id=int(user_id),
                split_amount=per_user_amount,
                payment_status=payment_status
            )
            db.session.add(shared)

        db.session.commit()
        flash('공동 구독이 추가되었습니다.')
    except Exception as e:
        db.session.rollback()
        flash('공동 구독 추가 중 오류가 발생했습니다.')
        print("Error:", str(e))

    return redirect(url_for('subscriptions'))


#공동 구독 상태 수정
@app.route('/shared_subscriptions/update_status/<int:subscription_id>', methods=['POST'])
@login_required
def update_shared_status(subscription_id):
    try:
        user_id = request.form.get('user_id')
        new_status = request.form.get('payment_status')

        shared = SharedSubscription.query.filter_by(subscription_id=subscription_id, user_id=user_id).first()
        if not shared:
            flash('공동 구독 항목을 찾을 수 없습니다.')
            return redirect(url_for('subscriptions'))

        shared.payment_status = new_status
        db.session.commit()
        flash('송금 상태가 업데이트되었습니다.')
    except Exception as e:
        db.session.rollback()
        flash('상태 업데이트 중 오류가 발생했습니다.')
        print("Error:", str(e))

    return redirect(url_for('subscriptions'))

# 공동 구독 수정
@app.route('/shared_subscriptions/edit/<int:subscription_id>', methods=['POST'])
@login_required
def edit_shared_subscription(subscription_id):
    try:
        shared_user_ids = request.form.getlist('shared_user_ids')
        payment_status = request.form.get('payment_status', '미완료')

        # 기존 참여자 삭제
        SharedSubscription.query.filter_by(subscription_id=subscription_id).delete()

        # 해당 구독 정보 조회
        subscription = Subscription.query.get_or_404(subscription_id)
        per_amount = round(subscription.cost / len(shared_user_ids), 2)

        for uid in shared_user_ids:
            new_shared = SharedSubscription(
                subscription_id=subscription_id,
                user_id=int(uid),
                split_amount=per_amount,
                payment_status=payment_status
            )
            db.session.add(new_shared)

        db.session.commit()
        flash('공동 구독이 성공적으로 수정되었습니다.')
    except Exception as e:
        db.session.rollback()
        flash('수정 중 오류 발생: ' + str(e))
        print("Error:", e)

    return redirect(url_for('subscriptions'))


#공동 구독 삭제

@app.route('/shared_subscriptions/delete/<int:subscription_id>', methods=['POST'])
@login_required
def delete_shared_subscription(subscription_id):
    try:
        # 해당 구독의 모든 참여 항목 삭제
        SharedSubscription.query.filter_by(subscription_id=subscription_id).delete()
        db.session.commit()
        flash('공동 구독이 삭제되었습니다.')
    except Exception as e:
        db.session.rollback()
        flash('삭제 중 오류가 발생했습니다.')
        print("Error:", str(e))

    return redirect(url_for('subscriptions'))



if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 

# app.py
from flask import Flask
from models import db

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///books.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()
