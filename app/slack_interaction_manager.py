import requests
from .models import LeaveRequest
from .slack_message_manager import update_message
from .manager import approve_or_decline_leave

def handle_interactive_message(payload):
    try:
        actions = payload.get('actions', [])
        if not actions:
            return "No actions found in the payload."
        action = actions[0] 
        action_id = action.get('action_id')
        value = action.get('value')
        leave_id = int(value)
        channel_id = payload.get('channel', {}).get('id')
        message_ts = payload.get('message', {}).get('ts')
        if not channel_id or not message_ts:
            leave_request = LeaveRequest.query.filter_by(id=leave_id).one()
            channel_id = leave_request.channel_id
            message_ts = leave_request.message_ts
        if action_id in ['approve', 'decline']:
            action_type = 'approve' if action_id == 'approve' else 'decline'
            response = approve_or_decline_leave(payload['user']['id'], leave_id, action_type)
            updated_text = f"Leave request {leave_id} has been {action_type}d by <@{payload['user']['id']}>."
            updated_blocks = [
                {
                    "type": "section",
                    "block_id": "section-identifier",
                    "text": {
                        "type": "mrkdwn",
                        "text": updated_text
                    }
                },
                {
                    "type": "section",
                    "block_id": "status-identifier",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Status:* {'Approved' if action_id == 'approve' else 'Declined'}"
                    }
                }
            ]
            update_message(channel_id, message_ts, updated_text, updated_blocks)
            return response
        else:
            return "Unknown action."
    except Exception as e:
        return f"An error occurred: {e}"

def handle_interactive_message_calendar(action,leave_id):
    try:
        leave_request = LeaveRequest.query.filter_by(id=leave_id).one()
        channel_id = leave_request.channel_id
        message_ts = leave_request.message_ts
        manager_id = leave_request.manager_id
        if action in ['approve', 'decline']:
            action_type = 'approve' if action == 'approve' else 'decline'
            response = approve_or_decline_leave(manager_id, leave_id, action_type)
            updated_text = f"Leave request {leave_id} has been {action_type}d by <@{manager_id}>."
            updated_blocks = [
                {
                    "type": "section",
                    "block_id": "section-identifier",
                    "text": {
                        "type": "mrkdwn",
                        "text": updated_text
                    }
                },
                {
                    "type": "section",
                    "block_id": "status-identifier",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Status:* {'Approved' if action == 'approve' else 'Declined'}"
                    }
                }
            ]
            update_message(channel_id, message_ts, updated_text, updated_blocks)
            return response
        else:
            return "Unknown action."
    except Exception as e:
        return f"An error occurred: {e}"