# app/user_manager.py
from datetime import datetime
from .models import db, User
from .logger import log

def update_manager_leave_balances():
    current_year = datetime.now().strftime('%Y')

    try:
        managers = User.query.filter_by(role="Manager").all()
        for manager in managers:
            last_reset_year = manager.last_reset_month.split('-')[0]
            if last_reset_year != current_year:  # Check if the balance needs to be updated
                # Update balance to 14 + any remaining balance from the previous year
                manager.leave_balance = 14 + manager.leave_balance
                manager.last_reset_month = current_year  # Update the last reset year
                db.session.commit()
        log.info("Manager leave balances updated.")
    except Exception as e:
        log.error(f"Error updating manager leave balances: {e}")
