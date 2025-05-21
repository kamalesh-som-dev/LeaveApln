from .models import db, User, LeaveRequest, LeaveStatus, ManagerMapping
from .color_manager import assign_color_to_user
from app.models import db, User, LeaveRequest
from .slack_message_manager import update_message, send_message_from_manager
from .logger import log

def create_manager(slack_id, name):
    try:
        user = User.query.filter_by(slack_id=slack_id).first()
        if user:
            return "User already exists."
        new_manager = User(slack_id=slack_id, name=name, role="Manager",leave_balance=14)
        db.session.add(new_manager)
        assign_color_to_user(new_manager)
        db.session.commit()
        return f"Manager user created successfully: {name} (Slack ID: {slack_id})"
    
    except Exception as e:
        return f"An error occurred: {e}"
    
def view_all_pending_leaves_ui(manager_id):
    log.info("Manager id: %s",manager_id)
    pending_leaves = LeaveRequest.query.filter_by(
            status=LeaveStatus.PENDING,
            manager_id=manager_id
        ).all()
    if not pending_leaves:
        return [{
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "No pending leave requests found."
            }
        }]
    
    blocks = []
    for leave in pending_leaves:
        user = User.query.get(leave.user_id)
        leave_id = leave.id
        user_name = user.name
        start_date = leave.start_date.strftime('%Y-%m-%d')
        end_date = leave.end_date.strftime('%Y-%m-%d')
        reason = leave.reason
        
        blocks.append({
            "type": "section",
            "block_id": f"pending_leave_{leave_id}",
            "text": {
                "type": "mrkdwn",
                "text": (f"*User:* {user_name}\n"
                         f"*Start Date:* {start_date}\n"
                         f"*End Date:* {end_date}\n"
                         f"*Reason:* {reason}")
            }
        })

        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Approve"
                    },
                    "action_id": "approve",
                    "value": str(leave_id)
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Decline"
                    },
                    "action_id": "decline",
                    "value": str(leave_id)
                }
            ]
        })
    
    return blocks

def view_all_pending_leaves():
    pending_leaves = LeaveRequest.query.filter_by(status=LeaveStatus.PENDING).all()
    if not pending_leaves:
        return "No pending leave requests found."

    response = "Pending leave requests:\n"
    for index, leave in enumerate(pending_leaves, start=1):
        user = User.query.get(leave.user_id)
        response += (f"{index}. Leave ID: {leave.id} - User: {user.name} - "
                     f"From {leave.start_date} to {leave.end_date} - Reason: {leave.reason}\n")
    return response

def make_manager(intern_id):
    try:
        intern = User.query.filter_by(slack_id=intern_id).first()
        if not intern:
            return f"Intern with ID {intern_id} not found."
        if intern.role == 'Manager':
            return f"User with ID {intern_id} is already a manager."
        intern.role = 'Manager'
        intern.leave_balance=14
        db.session.commit()

        return f"Intern {intern.name} (ID: {intern.slack_id}) has been promoted to Manager."

    except Exception as e:
        db.session.rollback()
        return f"An error occurred while promoting the intern to manager: {e}"

def approve_or_decline_leave(user_id, leave_id, action):
    try:
        manager = User.query.filter_by(slack_id=user_id, role='Manager').first()
        if not manager:
            return "Only managers can approve or decline leave requests."

        leave_request = LeaveRequest.query.filter_by(id=leave_id).first()
        if not leave_request:
            return "Leave request not found."
        leave_days = (leave_request.end_date - leave_request.start_date).days + 1
        intern = leave_request.user
        if action.lower() == 'approve':
            leave_request.status = LeaveStatus.APPROVED
        elif action.lower() == 'decline':
            leave_request.status = LeaveStatus.DECLINED
            intern.leave_balance = min(intern.leave_balance + leave_days, 2)
        else:
            return "Invalid action. Please specify 'approve' or 'decline'."
        db.session.commit()
        # Notify the intern
        send_message_from_manager(leave_request.user.slack_id, f"Your leave request from {leave_request.start_date} to {leave_request.end_date} has been {leave_request.status.value.lower()}.")

        return f"Leave request has been {leave_request.status.value.lower()}."

    except Exception as e:
        return f"An error occurred: {e}"
    
def view_intern_leave_history(intern_id,manager_id):
    manager = User.query.filter_by(slack_id=manager_id).first()
    if not manager:
        return "Manager not found."
    intern = User.query.filter_by(slack_id=intern_id).first()
    if not intern:
        return "Intern not found."
    if not ManagerMapping.query.filter_by(employee_id=intern.slack_id, manager_id=manager.slack_id).first():
        return "You do not have permission to view this intern's leave history."
    leave_requests = LeaveRequest.query.filter_by(user_id=intern.slack_id).all()
    if not leave_requests:
        return f"No leave history found for {intern.name}."
    leave_history = [
        f"Leave ID: {lr.id} - From {lr.start_date} to {lr.end_date}: {lr.status.name}" for lr in leave_requests
    ]
    return "\n".join(leave_history)