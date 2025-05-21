import requests
from .logger import log
from .models import User
from .slack_ui_manager import format_intern_users_for_modal
import os

slack_token = os.getenv("SLACK_BOT_TOKEN")

def open_intern_users_modal(trigger_id, slack_id):
    """Opens a modal displaying intern users for a given manager."""
    manager = User.query.filter_by(slack_id=slack_id).first()
    if not manager:
        log.error("Manager not found.")
        return "Manager not found."

    intern_users = [mapping.employee for mapping in manager.managed_employees]
    if not intern_users:
        log.info("No intern users found for this manager.")
        return "No intern users found for this manager."

    blocks = format_intern_users_for_modal(intern_users)
    
    response = requests.post('https://slack.com/api/views.open', headers={
        'Authorization': f'Bearer {slack_token}',
        'Content-Type': 'application/json'
    }, json={
        "trigger_id": trigger_id,
        "view": {
            "type": "modal",
            "callback_id": "intern_users_modal",
            "title": {
                "type": "plain_text",
                "text": "Intern Users"
            },
            "blocks": blocks
        }
    })
    
    if response.status_code == 200 and response.json().get('ok'):
        log.info("Modal opened successfully.")
        return "ok"
    else:
        log.error(f"Failed to open modal: {response.text}")
        return "no"
