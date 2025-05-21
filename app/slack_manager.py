# app/slack_manager.py
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from .models import db, User
from .logger import log
from .color_manager import assign_color_to_user
import requests

def set_first_admin(client):
    existing_admin = User.query.filter_by(is_admin=True).first()
    if existing_admin:
        log.info(f"Admin already set - {existing_admin.name}({existing_admin.slack_id})")
        return f"Admin already set - {existing_admin.name}"
    try:
        response = client.users_list()
        if response.get("ok"):
            members = response.get("members", [])
            primary_owner = next((user for user in members if user.get('is_primary_owner')), None)
            if primary_owner:
                user_id = primary_owner['id']
                user_name = primary_owner['real_name']
                user = User.query.filter_by(slack_id=user_id).first()
                if user:
                    if not user.is_admin:
                        user.is_admin = True
                        db.session.commit()
                        log.info(f"{user_name} is already in the database and has been set as the default admin.")
                    else:
                        log.info(f"{user_name} is already in the database and is already an admin.")
                    return f"{user_name} is already set as the default admin."
                else:
                    new_user = User(slack_id=user_id, name=user_name, is_admin=True, role="Manager", leave_balance=14)
                    db.session.add(new_user)
                    assign_color_to_user(new_user)
                    db.session.commit()
                    log.info(f"{user_name} has been added and set as the default admin.")
                    return f"{user_name} has been added and set as the default admin."
            else:
                log.warning("No primary owner found.")
                return "No primary owner found."
        else:
            log.warning("Failed to retrieve user list from Slack.")
            return "Failed to retrieve user list from Slack."
    except SlackApiError as e:
        log.error(f"Slack API error: {str(e)}")
        return f"Slack API error: {str(e)}"

def get_slack_user_info(user_id,slack_token):
    url = f"https://slack.com/api/users.info"
    headers = {
        'Authorization': f'Bearer {slack_token}',
        'Content-Type': 'application/json'
    }
    params = {
        'user': user_id
    }
    response = requests.get(url, headers=headers, params=params)
    data = response.json()
    
    if data.get('ok'):
        return data.get('user', {})
    else:
        return None
    