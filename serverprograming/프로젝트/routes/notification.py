from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import db, Notification, Subscription
from datetime import datetime, timedelta

notification_bp = Blueprint('notification', __name__)

@notification_bp.route('/notifications', methods=['GET', 'POST'])
@login_required
def manage_notifications():
    if request.method == 'POST':
        data = request.get_json()
        subscription = Subscription.query.get_or_404(data['subscription_id'])
        
        if subscription.user_id != current_user.id:
            return jsonify({'error': '권한이 없습니다.'}), 403
        
        new_notification = Notification(
            subscription_id=subscription.id,
            type=data['type'],
            alert_date=datetime.strptime(data['alert_date'], '%Y-%m-%d %H:%M:%S')
        )
        db.session.add(new_notification)
        db.session.commit()
        return jsonify({'message': '알림이 성공적으로 설정되었습니다.'}), 201
    
    notifications = Notification.query.join(Subscription).filter(
        Subscription.user_id == current_user.id
    ).all()
    return render_template('notification/manage.html', notifications=notifications)

@notification_bp.route('/notifications/upcoming')
@login_required
def upcoming_payments():
    # 다음 7일 내의 결제 예정 알림 조회
    today = datetime.now()
    week_later = today + timedelta(days=7)
    
    upcoming = Notification.query.join(Subscription).filter(
        Subscription.user_id == current_user.id,
        Notification.alert_date.between(today, week_later)
    ).all()
    
    return jsonify([{
        'service_name': n.subscription.service_name,
        'cost': n.subscription.cost,
        'payment_date': n.alert_date.strftime('%Y-%m-%d'),
        'type': n.type
    } for n in upcoming])

@notification_bp.route('/notifications/settings/<int:id>', methods=['PUT'])
@login_required
def update_notification_settings(id):
    notification = Notification.query.get_or_404(id)
    subscription = Subscription.query.get(notification.subscription_id)
    
    if subscription.user_id != current_user.id:
        return jsonify({'error': '권한이 없습니다.'}), 403
    
    data = request.get_json()
    notification.alert_date = datetime.strptime(data['alert_date'], '%Y-%m-%d %H:%M:%S')
    db.session.commit()
    
    return jsonify({'message': '알림 설정이 업데이트되었습니다.'}), 200 