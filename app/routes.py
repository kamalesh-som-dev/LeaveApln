from flask import Blueprint, request, jsonify, render_template
from sqlalchemy import or_
from .intern import apply_leave, cancel_leave_request, view_past_leaves, view_leave_balance, view_pending_leaves
from .manager import approve_or_decline_leave, view_intern_leave_history, view_all_pending_leaves, make_manager
from .models import User,db, ManagerMapping, LeaveRequest, LeaveStatus
from .color_manager import assign_color_to_user
from .slack_manager import get_slack_user_info
from .slack_ui_manager import update_home_manager_ui, update_home_ui
from .slack_message_manager import send_dm_message, get_user_name, update_message
from .slack_modal_manager import open_intern_users_modal
from .slack_interaction_manager import handle_interactive_message, handle_interactive_message_calendar
from .logger import log
import json
import requests
import os
from datetime import timedelta

bp = Blueprint('routes', __name__)
slack_token = os.getenv("SLACK_BOT_TOKEN")
calendar_url = os.getenv("CALENDAR_URL")

@bp.route('/')
def home():
    return "Welcome to the Leave Bot Application!!"

@bp.route('/calendar')
def calendar():
    slack_id = request.args.get('slack_id')
    log.info("Current user_id viewing calendar: %s",slack_id)
    return render_template('calendar.html',slack_id=slack_id)

@bp.route('/api/leave-events/<string:slack_id>', methods=['GET'])
def get_leave_events(slack_id):
    manager = User.query.filter_by(slack_id=slack_id).first()
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    leave_requests = LeaveRequest.query.filter(
        or_(
            LeaveRequest.user_id == manager.slack_id,  
            LeaveRequest.manager_id == manager.slack_id      
        )
    ).filter(
        LeaveRequest.status.in_([LeaveStatus.APPROVED, LeaveStatus.PENDING])
    ).all()
    events = []
    for request in leave_requests:
        event = {
            'id': request.id,
            'title': f"{request.user.name} - {request.reason}",
            'start': request.start_date.isoformat(),
            'end': (request.end_date + timedelta(days=1)).isoformat(), 
            'backgroundColor': request.user.color if request.status == LeaveStatus.APPROVED else '#808080',  # Grey for pending
            'borderColor': '#808080' if request.status == LeaveStatus.PENDING else request.user.color,
            'textColor': '#ffffff' if request.status == LeaveStatus.PENDING else '#000000',
            'status': request.status.value
        }
        events.append(event)
    return jsonify(events)

@bp.route('/api/update-leave-status/<int:leave_id>', methods=['POST'])
def update_leave_status(leave_id):
    data = request.get_json()
    response = handle_interactive_message_calendar(data["status"],leave_id)
    leave_request = LeaveRequest.query.filter_by(id=leave_id).one()
    manager_id=leave_request.manager_id
    update_response = update_home_manager_ui(manager_id, slack_token)
    if "error" in response or update_response.status_code != 200:
            return jsonify({"status": "error", "message": "Failed to update the home UI or send DM."}), 500
    return jsonify({'success': True})

@bp.route('/slack/apps_home', methods=['POST'])
def app_home():

    # # to enable link
    # if request.json.get('type') == 'url_verification':
    #     return jsonify(challenge=request.json.get('challenge'))

    log.info("HOME UI Loading...")
    data = request.json
    log.info("Home UI Data: %s ",data)

    user_id = data.get('event', {}).get('user') or data.get('event', {}).get('message', {}).get('user') or data.get('event', {}).get('edited', {}).get('user')
    if not user_id:
        return jsonify({"status": "error", "message": "User ID not found"}), 400
    
    user = User.query.filter_by(slack_id=user_id).first()
    log.info("Current User: %s",user)
    
    if not user:
        slack_user_info = get_slack_user_info(user_id,slack_token)
        log.info("Slack user info: %s",slack_user_info)
        user_name = slack_user_info.get('profile', {}).get('real_name', 'Unknown')
        user = User(slack_id=user_id, name=user_name)
        db.session.add(user)
        assign_color_to_user(user)
        db.session.commit()

    is_intern = user.role == 'Intern'
    is_manager = user.role == 'Manager'

    if is_intern:
        update_home_ui(user_id,slack_token)

    elif is_manager:
        update_home_manager_ui(user_id,slack_token)
     
    return jsonify({"status": "ok"})

@bp.route('/slack/interactions', methods=['POST'])
def handle_interactions():
    if request.content_type != 'application/x-www-form-urlencoded':
        return jsonify({"error": "Unsupported Media Type"}), 415
    payload = request.form.get('payload')
    if not payload:
        return jsonify({"error": "No payload found"}), 400
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON in payload"}), 400

    action_id = data.get('actions', [{}])[0].get('action_id')
    log.info("Current action in handle/interaction: %s",action_id)
    leave_id = data.get('actions', [{}])[0].get('value')
    user_id = data.get('user', {}).get('id')
    if data.get('type') == 'view_submission':
        callback_id = data.get('view', {}).get('callback_id')
        values = data.get('view', {}).get('state', {}).get('values', {})
        view_id = data.get('view', {}).get('id')
        if callback_id == 'apply_leave_modal':
            start_date = values.get('start_date', {}).get('start_date', {}).get('selected_date')
            end_date = values.get('end_date', {}).get('end_date', {}).get('selected_date')
            reason = values.get('reason', {}).get('reason', {}).get('value')
            user_name = get_user_name(user_id)
            response_message = apply_leave(user_id, start_date, end_date, reason, user_name)
            update_modal_view = {
                "type": "modal",
                "callback_id": "apply_leave_modal",
                "title": {
                    "type": "plain_text",
                    "text": "Apply for Leave"
                },
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": response_message
                        }
                    }
                ]
            }
            response = requests.post(
                'https://slack.com/api/views.update',
                headers={
                    'Authorization': f'Bearer {slack_token}',
                    'Content-Type': 'application/json; charset=utf-8'
                },
                json={
                    'view_id': view_id,
                    'view': update_modal_view
                }
            )
            if response.status_code != 200:
                return jsonify({"status": "error", "message": response.text}), response.status_code
            return jsonify({"status": "ok"})
        if callback_id == 'intern_leave_history_request':
            slack_id = values.get('slack_id_block', {}).get('slack_id_input', {}).get('value')
            log.info("Requested leave history user: %s",slack_id)
            user = User.query.filter_by(slack_id=slack_id).first()
            if not user:
                return "User not found."
            manager_mapping = ManagerMapping.query.filter_by(employee_id=slack_id).first()
            if not manager_mapping:
                return "No manager assigned to this user."
            manager = User.query.filter_by(slack_id=manager_mapping.manager_id).first()
            if not manager:
                return "Manager not found."
            leave_balance_message = view_leave_balance(slack_id)
            leave_history = view_intern_leave_history(slack_id,manager.slack_id)
            leave_history_message = f"Leave History for {user.name}:\n\n" + leave_history
            update_modal_view = {
                "type": "modal",
                "callback_id": "intern_leave_history_request",
                "title": {
                    "type": "plain_text",
                    "text": "Leave History"
                },
                "blocks": [
                     {
                        "type": "section",
                        "block_id": "leave_balance",
                        "text": {
                            "type": "mrkdwn",
                            "text": leave_balance_message
                        }
                    },
                    {
                        "type": "divider"
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": leave_history_message
                        }
                    }
                ]
            }
            response = requests.post(
                'https://slack.com/api/views.update',
                headers={
                    'Authorization': f'Bearer {slack_token}',
                    'Content-Type': 'application/json; charset=utf-8'
                },
                json={
                    'view_id': view_id,
                    'view': update_modal_view
                }
            )
            if response.status_code != 200:
                return jsonify({"status": "error", "message": response.text}), response.status_code
            return jsonify({"status": "ok"})
    if action_id == "open_calendar":
        return jsonify({"status": "ok"})
    if action_id == 'view_calendar':
        slack_id=user_id
        log.info("User who accessed Calender: %s",slack_id)
        response = requests.post(
            'https://slack.com/api/views.open',
            headers={
                'Authorization': f'Bearer {slack_token}',
                'Content-Type': 'application/json'
            },
            json={
                "trigger_id": data['trigger_id'],
                "view": {
                    "type": "modal",
                    "callback_id": "calendar_modal",
                    "title": {
                        "type": "plain_text",
                        "text": "Leave Calendar"
                    },
                    "blocks": [
                        {
                            "type": "section",
                            "block_id": "calendar_block",
                            "text": {
                                "type": "mrkdwn",
                                "text": "Here is the leave calendar:"
                            },
                            "accessory": {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "Open Calendar",
                                    "emoji": True
                                },
                                "action_id": "open_calendar",
                                "url": f"{calendar_url}/calendar?slack_id={slack_id}"
                            }
                        }
                    ]
                }
            }
        )
        if response.status_code != 200:
            log.error(f"Error opening modal: {response.text}")
        return jsonify({"status": "ok"})
    if action_id == 'view_user_leave_history':
        trigger_id = data.get('trigger_id')
        log.info("Trigger id of view_user_leave_history: %s",trigger_id)
        modal_view = {
            "type": "modal",
            "callback_id": "intern_leave_history_request",
            "title": {
                "type": "plain_text",
                "text": "Leave History"
            },
            "blocks": [
                {
                    "type": "input",
                    "block_id": "slack_id_block",
                    "label": {
                        "type": "plain_text",
                        "text": "Enter User ID"
                    },
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "slack_id_input",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "e.g., U07GHFFEHDH"
                        }
                    },
                    "optional": False  
                }
            ],
            "submit": {
                "type": "plain_text",
                "text": "Submit"
            },
            "close": {
                "type": "plain_text",
                "text": "Cancel"
            }
        }
        response = requests.post('https://slack.com/api/views.open', headers={
            'Authorization': f'Bearer {slack_token}',
            'Content-Type': 'application/json'
        }, json={
            "trigger_id": trigger_id,
            "view": modal_view
        })
        callback_id = data.get('view', {}).get('callback_id')
        user_id = data.get('user', {}).get('id')
        return jsonify({"status": "ok"})
    if action_id == "view_users":
        trigger_id = data.get('trigger_id')
        log.info("TriggerId of view_users: %s", trigger_id)
        response = open_intern_users_modal(trigger_id, user_id)
        if response == "ok":
            return jsonify({"status": "ok"})
        else:
            error_message = response
            error_response = requests.post('https://slack.com/api/views.open', headers={
                'Authorization': f'Bearer {slack_token}',
                'Content-Type': 'application/json'
            }, json={
                "trigger_id": trigger_id,
                "view": {
                    "type": "modal",
                    "callback_id": "error_modal",
                    "title": {
                        "type": "plain_text",
                        "text": "Error"
                    },
                    "blocks": [
                        {
                            "type": "section",
                            "block_id": "error_message",
                            "text": {
                                "type": "plain_text",
                                "text": error_message
                            }
                        }
                    ]
                }
            })
            
            if error_response.status_code == 200 and error_response.json().get('ok'):
                return jsonify({"status": "error", "message": error_message})
            else:
                return jsonify({"status": "error", "message": "Failed to display error message"}), 500
    if action_id in ["approve","decline"]:
        response = handle_interactive_message(data)
        update_response = update_home_manager_ui(user_id, slack_token)
        if "error" in response or update_response.status_code != 200:
                return jsonify({"status": "error", "message": "Failed to update the home UI or send DM."}), 500
        return jsonify({"status": "ok"})
    if action_id == 'apply_leave': 
        trigger_id = data.get('trigger_id')  
        log.info("Opening leave modal")
        modal_view = {
            "type": "modal",
            "callback_id": "apply_leave_modal",
            "title": {
                "type": "plain_text",
                "text": "Apply for Leave"
            },
            "blocks": [
                {
                    "type": "input",
                    "block_id": "start_date",
                    "label": {
                        "type": "plain_text",
                        "text": "Start Date"
                    },
                    "element": {
                        "type": "datepicker",
                        "action_id": "start_date"
                    },
                    "optional": False
                },
                {
                    "type": "input",
                    "block_id": "end_date",
                    "label": {
                        "type": "plain_text",
                        "text": "End Date"
                    },
                    "element": {
                        "type": "datepicker",
                        "action_id": "end_date"
                    },
                    "optional": False
                },
                {
                    "type": "input",
                    "block_id": "reason",
                    "label": {
                        "type": "plain_text",
                        "text": "Reason for Leave"
                    },
                    "element": {
                        "type": "plain_text_input",
                        "multiline": True,
                        "action_id": "reason"
                    },
                    "optional": False
                }
            ],
            "submit": {
                "type": "plain_text",
                "text": "Submit"
            }
        }
        response = requests.post(
            'https://slack.com/api/views.open',
            headers={
                'Authorization': f'Bearer {slack_token}',
                'Content-Type': 'application/json; charset=utf-8'
            },
            json={
                'trigger_id': trigger_id,
                'view': modal_view
            }
        )
        callback_id = data.get('view', {}).get('callback_id')
        user_id = data.get('user', {}).get('id')
        values = data.get('view', {}).get('state', {}).get('values', {})
        return jsonify({"status": "ok"})
    if action_id == "view_leave_history":
        trigger_id = data.get('trigger_id')
        user_id = data.get('user', {}).get('id')  
        log.info("Opening leave history modal")
        leave_balance_message = view_leave_balance(user_id)
        leave_history = view_past_leaves(user_id)
        leave_entries = leave_history.split('\n')
        blocks = [
            {
                "type": "section",
                "block_id": "leave_balance",
                "text": {
                    "type": "mrkdwn",
                    "text": leave_balance_message
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "block_id": "leave_history_header",
                "text": {
                    "type": "plain_text",
                    "text": "Here is your leave history:"
                }
            }
        ]
        for idx, entry in enumerate(leave_entries):
            blocks.append({
                "type": "section",
                "block_id": f"leave_entry_{idx}",
                "text": {
                    "type": "mrkdwn",
                    "text": entry
                }
            })
        modal_view = {
            "type": "modal",
            "callback_id": "leave_history_modal",
            "title": {
                "type": "plain_text",
                "text": "Leave History"
            },
            "blocks": blocks
        }
        response = requests.post(
            'https://slack.com/api/views.open',
            headers={
                'Authorization': f'Bearer {slack_token}',
                'Content-Type': 'application/json; charset=utf-8'
            },
            json={
                'trigger_id': trigger_id,
                'view': modal_view
            }
        )
        if response.status_code != 200:
            return jsonify({"status": "error", "message": response.text}), response.status_code
        return jsonify({"status": "ok"})
    if action_id.startswith('cancel_'):
        leave_id = int(action_id.split('_')[1])
        result = cancel_leave_request(user_id, leave_id)
        user = User.query.filter_by(slack_id=user_id).first()
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404
        if user.role == 'Manager':
            update_response = update_home_manager_ui(user_id, slack_token)
        else:
            update_response = update_home_ui(user_id, slack_token)
        response_message = f"Leave request (ID: {leave_id}) cancelled successfully. Leave days added back to your balance."
        dm_response = send_dm_message(user_id, response_message)
        if 'error' in dm_response or update_response.status_code != 200:
            return jsonify({"status": "error", "message": "Failed to update the home UI or send DM."}), 500
        
        return jsonify({"status": "ok", "message": response_message})

@bp.route('/slack/admin',methods=['POST'])
def admin_stuffs():
    def make_admin(user_id):
        try:
            user = User.query.filter_by(id=user_id).first()
            if not user:
                return f"User with ID {user_id} not found."
            user.is_admin = True
            db.session.commit()
            return f"User {user.name} (ID: {user.id}) has been promoted to Admin."
        except Exception as e:
            db.session.rollback()
            return f"An error occurred while promoting user: {e}"

    def is_admin(user_id):
        user = User.query.filter_by(slack_id=user_id).first()
        return user.is_admin if user else False

    data = request.form
    user_id = data.get('user_id')
    user_name = data.get('user_name')
    command = data.get('command')
    text = data.get('text', '').strip()

    if not is_admin(user_id):
        return "Access denied. Only admins can use this command."
    
    if command == '/viewmanagers':
        managers = User.query.filter_by(role='Manager').with_entities(User.slack_id, User.name).all()
        manager_list = [f"Slack ID: {manager.slack_id} - Name: {manager.name}" for manager in managers]
        return "\n".join(manager_list)
    
    elif command == '/assignmanager':
        try:
            texts=text.split()
            if len(texts) != 2:
                return "Invalid format. Please use the format: /command intern_id manager_id"
            intern_id=texts[0]
            manager_id=texts[1]
            intern = User.query.filter_by(slack_id=intern_id).first()
            manager = User.query.filter_by(slack_id=manager_id).first()
            if not intern:
                return f"Intern with ID {intern_id} not found."
            if not manager:
                return f"Manager with ID {manager_id} not found."
            if manager.role != 'Manager':
                return f"User with ID {manager_id} is not a manager."
            existing_mapping = ManagerMapping.query.filter_by(employee_id=intern_id).first()
            if existing_mapping:
                db.session.delete(existing_mapping)
            new_mapping = ManagerMapping(employee_id=intern_id, manager_id=manager_id)
            db.session.add(new_mapping)
            db.session.commit()
            return f"Manager {manager.name} (ID: {manager.slack_id}) successfully assigned to {intern.name} (ID: {intern.slack_id})."

        except Exception as e:
            db.session.rollback() 
            return f"An error occurred while assigning manager: {e}"
        
    elif command == '/makemanager':
        try:
            intern_id = text
            return make_manager(intern_id)
        except ValueError:
            return "Please provide a valid intern ID."
    
    elif command == '/makeadmin':
        try:
            user_to_promote_id = int(text)
            return make_admin(user_to_promote_id)
        except ValueError:
            return "Please provide a valid user ID."
        
    elif command == '/viewadmins':
        admins = User.query.filter_by(is_admin=True).with_entities(User.slack_id, User.name, User.role).all()
        if not admins:
            return "No admins found."
        admin_list = [f"Slack ID: {admin[0]} - Name: {admin[1]} - Role: {admin[2]}" for admin in admins]
        return "\n".join(admin_list)

    elif command == '/viewallusers':
        users = db.session.query(
            User.slack_id,
            User.name,
            User.role,
            ManagerMapping.manager_id
        ).outerjoin(
            ManagerMapping, User.slack_id == ManagerMapping.employee_id
        ).with_entities(
            User.slack_id,
            User.name,
            User.role,
            ManagerMapping.manager_id
        ).all()
        if not users:
            return "No users found."
        user_list = [
            f"Slack ID: {user[0]} - Name: {user[1]} - Role: {user[2]} - Manager ID: {user[3] or 'None'}"
            for user in users
        ]
        return "\n".join(user_list)
    
    else:
        response = "Unknown command."

    return jsonify(response_type='ephemeral', text=response)
        
@bp.route('/slack/leave', methods=['POST'])
def handle_leave():
    data = request.form
    user_id = data.get('user_id')
    user_name = data.get('user_name')
    command = data.get('command')
    text = data.get('text', '').strip()

    #just to check bot connectivity
    # if request.json.get('type') == 'url_verification':
    #     return jsonify(challenge=request.json.get('challenge'))
    
    if command == '/applyleave':
        try:
            start_date, end_date, reason = text.split(" ", 2)
            response = apply_leave(user_id, start_date, end_date, reason, user_name)
        except ValueError:
            response = "Please provide the start date, end date, and reason in the format: 'start_date end_date reason'."
    
    elif command == "/calendar":
        response =  "You can view the leave calendar here: "+calendar_url+"/calendar?slack_id="+user_id
    
    elif command == '/pendingleave':
        response = view_pending_leaves(user_id)

    elif command == '/cancelleave':
        if text == "":
            response = view_pending_leaves(user_id)
        else:
            try:
                selection_number = int(text)
                response = cancel_leave_request(user_id, selection_number)
            except ValueError:
                response = "Please provide a valid number corresponding to the leave you want to cancel."

    elif command == '/pastleaves':
        response = view_past_leaves(user_id)

    elif command == '/leavebalance':
        response = view_leave_balance(user_id)

    elif command in ['/approve', '/decline']:
        try:
            leave_id = int(text.split()[0]) 
            action = command.strip('/') 
            response = approve_or_decline_leave(user_id, leave_id, action)
            leave_request = LeaveRequest.query.filter_by(id=leave_id).one()
            channel_id = leave_request.channel_id
            message_ts = leave_request.message_ts
            updated_text = f"Leave request {leave_id} has been {action}d by <@{user_id}>."
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
        except ValueError:
            response = "Please provide a valid leave ID."

    elif command == '/leavehistory':
        intern_id = text.strip()
        manager_mapping = ManagerMapping.query.filter_by(employee_id=intern_id).first()
        if not manager_mapping:
            response="Manager not found"
        else:
            response = view_intern_leave_history(intern_id,manager_mapping.manager_id)

    elif command == '/viewpendingleaves':
        manager = User.query.filter_by(slack_id=user_id, role='Manager').first()
        if not manager:
            response = "You must be a manager to view pending leave requests."
        else:
            response = view_all_pending_leaves()

    else:
        response = "Unknown command."

    return jsonify(response_type='ephemeral', text=response)

def register_routes(app):
    app.register_blueprint(bp)