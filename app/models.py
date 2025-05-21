import enum
from sqlalchemy import Column, String, Date, Enum, ForeignKey
from sqlalchemy.orm import relationship
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class LeaveStatus(enum.Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    DECLINED = "Declined"
    CANCELLED = "Cancelled"

class User(db.Model):
    slack_id = db.Column(db.String(50), primary_key=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='Intern')  # Role can be 'Intern', 'Manager', etc.
    leave_balance = db.Column(db.Integer, default=2)  # Default leave balance
    last_reset_month = db.Column(db.String(7), nullable=False)  # To track when leave balance was last reset
    is_admin = db.Column(db.Boolean, default=False)  # To distinguish admin users
    color = db.Column(db.String(7), unique=True, nullable=True)

    # Relationships
    leave_requests = relationship("LeaveRequest", back_populates="user", foreign_keys="[LeaveRequest.user_id]")
    managed_employees = relationship("ManagerMapping", back_populates="manager", foreign_keys="[ManagerMapping.manager_id]")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.last_reset_month:
            # Set last_reset_month to current month and year if not provided
            self.last_reset_month = datetime.now().strftime('%Y-%m')

# Table for mapping employees to managers
class ManagerMapping(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(50), db.ForeignKey('user.slack_id'), nullable=False)
    manager_id = db.Column(db.String(50), db.ForeignKey('user.slack_id'), nullable=False)

    # Relationships
    employee = relationship('User', foreign_keys=[employee_id], backref='managers')
    manager = relationship('User', foreign_keys=[manager_id], back_populates="managed_employees")

# Table for leave requests
class LeaveRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), db.ForeignKey('user.slack_id'), nullable=False)  # The employee requesting leave
    manager_id = db.Column(db.String(50), db.ForeignKey('user.slack_id'), nullable=False)  # The manager overseeing this request
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    status = Column(Enum(LeaveStatus), default=LeaveStatus.PENDING, nullable=False)
    channel_id = db.Column(db.String(50), nullable=True)  
    message_ts = db.Column(db.String(50), nullable=True)  

    # Relationships
    user = relationship("User", back_populates="leave_requests", foreign_keys=[user_id])
    manager = relationship("User", foreign_keys=[manager_id])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.start_date > self.end_date:
            raise ValueError("Start date cannot be after the end date")