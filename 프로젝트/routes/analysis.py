from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from models import db, Subscription
from sqlalchemy import func
from datetime import datetime, timedelta

analysis_bp = Blueprint('analysis', __name__)

@analysis_bp.route('/analysis')
@login_required
def analysis_dashboard():
    return render_template('analysis/dashboard.html')

@analysis_bp.route('/analysis/monthly')
@login_required
def monthly_analysis():
    # 현재 월의 구독 지출 분석
    current_month = datetime.now().replace(day=1)
    next_month = (current_month + timedelta(days=32)).replace(day=1)
    
    monthly_data = db.session.query(
        func.sum(Subscription.cost).label('total_cost'),
        func.count(Subscription.id).label('subscription_count')
    ).filter(
        Subscription.user_id == current_user.id,
        Subscription.payment_date.between(current_month, next_month)
    ).first()
    
    return jsonify({
        'total_cost': float(monthly_data.total_cost or 0),
        'subscription_count': monthly_data.subscription_count
    })

@analysis_bp.route('/analysis/yearly')
@login_required
def yearly_analysis():
    # 연간 구독 지출 분석
    current_year = datetime.now().year
    yearly_data = db.session.query(
        func.date_format(Subscription.payment_date, '%Y-%m').label('month'),
        func.sum(Subscription.cost).label('monthly_cost')
    ).filter(
        Subscription.user_id == current_user.id,
        func.year(Subscription.payment_date) == current_year
    ).group_by('month').all()
    
    return jsonify([{
        'month': data.month,
        'cost': float(data.monthly_cost)
    } for data in yearly_data])

@analysis_bp.route('/analysis/category')
@login_required
def category_analysis():
    # 서비스 카테고리별 지출 분석
    category_data = db.session.query(
        Subscription.service_name,
        func.sum(Subscription.cost).label('total_cost')
    ).filter(
        Subscription.user_id == current_user.id
    ).group_by(Subscription.service_name).all()
    
    return jsonify([{
        'service': data.service_name,
        'cost': float(data.total_cost)
    } for data in category_data])

@analysis_bp.route('/analysis/trend')
@login_required
def spending_trend():
    # 지출 추세 분석 (최근 6개월)
    six_months_ago = datetime.now() - timedelta(days=180)
    
    trend_data = db.session.query(
        func.date_format(Subscription.payment_date, '%Y-%m').label('month'),
        func.sum(Subscription.cost).label('monthly_cost')
    ).filter(
        Subscription.user_id == current_user.id,
        Subscription.payment_date >= six_months_ago
    ).group_by('month').order_by('month').all()
    
    return jsonify([{
        'month': data.month,
        'cost': float(data.monthly_cost)
    } for data in trend_data]) 