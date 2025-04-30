from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from flask_login import login_required, current_user
from models import db, Subscription
from datetime import datetime

subscription_bp = Blueprint('subscription', __name__)

@subscription_bp.route('/subscribe/add', methods=['GET', 'POST'])
@login_required
def add_subscription():
    if request.method == 'POST':
        data = request.get_json()
        new_subscription = Subscription(
            user_id=current_user.id,
            service_name=data['service_name'],
            cost=float(data['cost']),
            cycle=data['cycle'],
            payment_date=datetime.strptime(data['payment_date'], '%Y-%m-%d').date(),
            payment_method=data['payment_method']
        )
        db.session.add(new_subscription)
        db.session.commit()
        return jsonify({'message': '구독이 성공적으로 추가되었습니다.'}), 201
    return render_template('subscription/add.html')

@subscription_bp.route('/subscribe/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_subscription(id):
    subscription = Subscription.query.get_or_404(id)
    if subscription.user_id != current_user.id:
        return jsonify({'error': '권한이 없습니다.'}), 403
    
    if request.method == 'POST':
        data = request.get_json()
        subscription.service_name = data['service_name']
        subscription.cost = float(data['cost'])
        subscription.cycle = data['cycle']
        subscription.payment_date = datetime.strptime(data['payment_date'], '%Y-%m-%d').date()
        subscription.payment_method = data['payment_method']
        db.session.commit()
        return jsonify({'message': '구독이 성공적으로 수정되었습니다.'}), 200
    return render_template('subscription/edit.html', subscription=subscription)

@subscription_bp.route('/subscribe/delete/<int:id>', methods=['POST'])
@login_required
def delete_subscription(id):
    subscription = Subscription.query.get_or_404(id)
    if subscription.user_id != current_user.id:
        return jsonify({'error': '권한이 없습니다.'}), 403
    
    db.session.delete(subscription)
    db.session.commit()
    return jsonify({'message': '구독이 성공적으로 삭제되었습니다.'}), 200

@subscription_bp.route('/subscribe/list')
@login_required
def list_subscriptions():
    subscriptions = Subscription.query.filter_by(user_id=current_user.id).all()
    return render_template('subscription/list.html', subscriptions=subscriptions) 