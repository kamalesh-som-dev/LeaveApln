from .logger import log
from .manager import view_all_pending_leaves_ui
from .intern import view_pending_leaves_ui
import requests

def default_home_ui():
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Hello, How can I help you today?"
            }
        },
        {
            "type": "divider"
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Apply leave",
                        "emoji": True
                    },
                    "action_id": "apply_leave",
                    "style": "primary"  
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View leave history",
                        "emoji": True
                    },
                    "action_id": "view_leave_history"
                }
            ]
        }
    ]
    return blocks

def default_home_manager_ui():
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Hello, How can I help you today?"
            }
        },
        {
            "type": "divider"
        }
    ]
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Apply leave",
                    "emoji": True
                },
                "action_id": "apply_leave",
                "style": "primary"
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "View Users",
                    "emoji": True
                },
                "action_id": "view_users",
                "style": "primary"
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "View Users Leave History",
                    "emoji": True
                },
                "action_id": "view_user_leave_history"
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "View calendar",
                    "emoji": True
                },
                "action_id": "view_calendar"
            },
            {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View my leave history",
                        "emoji": True
                    },
                    "action_id": "view_leave_history"
                }
        ]
    })
    return blocks
    
def update_home_manager_ui(user_id, slack_token):
    existing_blocks = default_home_manager_ui().copy()
    existing_blocks.append({
        "type": "section",
        "block_id": "pending_leaves_header",
        "text": {
            "type": "plain_text",
            "text": "Pending Leave Requests"
        }
    })
    pending_leaves_blocks = view_all_pending_leaves_ui(user_id)
    existing_blocks = existing_blocks + pending_leaves_blocks
    existing_blocks.append({
        "type": "section",
        "block_id": "manager_pending_leaves_header",
        "text": {
            "type": "plain_text",
            "text": "Your Pending Leaves"
        }
    })

    manager_pending_leaves = view_pending_leaves_ui(user_id)
    updated_blocks = existing_blocks + manager_pending_leaves
    response = requests.post(
        'https://slack.com/api/views.publish',
        headers={
            'Authorization': f'Bearer {slack_token}',
            'Content-Type': 'application/json'
        },
        json={
            'user_id': user_id,
            'view': {
                'type': 'home',
                'blocks': updated_blocks
            }
        }
    )
    return response

def update_home_ui(user_id, slack_token):
    existing_blocks = default_home_ui().copy()
    existing_blocks.append({
        "type": "section",
        "block_id": "pending_leaves_header",
        "text": {
            "type": "plain_text",
            "text": "Pending Leaves"
        }
    })
    pending_leaves_blocks = view_pending_leaves_ui(user_id)
    updated_blocks = existing_blocks + pending_leaves_blocks 
    response = requests.post(
        'https://slack.com/api/views.publish',
        headers={
            'Authorization': f'Bearer {slack_token}',
            'Content-Type': 'application/json'
        },
        json={
            'user_id': user_id,
            'view': {
                'type': 'home',
                'blocks': updated_blocks
            }
        }
    )
    return response

def format_intern_users_for_modal(intern_users):
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*List of Intern Users:*"
            }
        },
        {"type": "divider"}
    ]
    for user in intern_users:
        blocks.append({
            "type": "section",
            "block_id": f"user_{user.slack_id}",
            "text": {
                "type": "mrkdwn",
                "text": (f"*User ID:* {user.slack_id}\n"
                         f"*User Name:* {user.name}\n"
                         f"*No. of leaves remaining:* {user.leave_balance}")
            }
        })
    return blocks
