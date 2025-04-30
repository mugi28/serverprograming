from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import db, SharedSubscription, Subscription, Budget
from datetime import datetime, timedelta
from sqlalchemy import func

shared_bp = Blueprint('shared', __name__)

@shared_bp.route('/shared', methods=['GET', 'POST'])
@login_required
def manage_shared():
    if request.method == 'POST':
        data = request.get_json()
        subscription = Subscription.query.get_or_404(data['subscription_id'])
        
        if subscription.user_id != current_user.id:
            return jsonify({'error': '권한이 없습니다.'}), 403
        
        new_shared = SharedSubscription(
            subscription_id=subscription.id,
            user_id=data['shared_user_id'],
            split_amount=float(data['split_amount'])
        )
        db.session.add(new_shared)
        db.session.commit()
        return jsonify({'message': '공동 구독이 성공적으로 설정되었습니다.'}), 201
    
    shared_subscriptions = SharedSubscription.query.join(Subscription).filter(
        Subscription.user_id == current_user.id
    ).all()
    return render_template('shared/manage.html', shared_subscriptions=shared_subscriptions)

@shared_bp.route('/shared/recommend')
@login_required
def get_recommendations():
    # 사용자의 구독 패턴을 기반으로 추천 서비스 제공
    user_subscriptions = Subscription.query.filter_by(user_id=current_user.id).all()
    
    # 간단한 추천 로직 (실제로는 더 복잡한 알고리즘 사용)
    recommendations = []
    for sub in user_subscriptions:
        if 'streaming' in sub.service_name.lower():
            recommendations.append({
                'service': 'Disney+',
                'reason': '엔터테인먼트 구독 패턴 감지',
                'estimated_savings': 5000
            })
        elif 'music' in sub.service_name.lower():
            recommendations.append({
                'service': 'Apple Music',
                'reason': '음악 구독 패턴 감지',
                'estimated_savings': 3000
            })
    
    return jsonify(recommendations)

@shared_bp.route('/budget', methods=['GET', 'POST'])
@login_required
def manage_budget():
    if request.method == 'POST':
        data = request.get_json()
        budget = Budget.query.filter_by(user_id=current_user.id).first()
        
        if budget:
            budget.monthly_limit = float(data['monthly_limit'])
        else:
            budget = Budget(
                user_id=current_user.id,
                monthly_limit=float(data['monthly_limit'])
            )
            db.session.add(budget)
        
        db.session.commit()
        return jsonify({'message': '예산이 성공적으로 설정되었습니다.'}), 201
    
    budget = Budget.query.filter_by(user_id=current_user.id).first()
    return render_template('shared/budget.html', budget=budget)

@shared_bp.route('/budget/status')
@login_required
def budget_status():
    budget = Budget.query.filter_by(user_id=current_user.id).first()
    if not budget:
        return jsonify({'error': '예산이 설정되지 않았습니다.'}), 404
    
    # 현재 월의 총 지출 계산
    current_month = datetime.now().replace(day=1)
    next_month = (current_month + timedelta(days=32)).replace(day=1)
    
    total_spent = db.session.query(func.sum(Subscription.cost)).filter(
        Subscription.user_id == current_user.id,
        Subscription.payment_date.between(current_month, next_month)
    ).scalar() or 0
    
    return jsonify({
        'monthly_limit': float(budget.monthly_limit),
        'total_spent': float(total_spent),
        'remaining': float(budget.monthly_limit - total_spent),
        'percentage_used': (total_spent / budget.monthly_limit) * 100 if budget.monthly_limit > 0 else 0
    }) 