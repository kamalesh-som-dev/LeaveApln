from .models import db, User
import random
from .logger import log

def generate_unique_color(existing_colors):
    excluded_color = "#808080"
    while True:
        color = "#{:06x}".format(random.randint(0, 0xFFFFFF))
        if color not in existing_colors and color != excluded_color:
            return color

def assign_color_to_user(user):
    existing_colors = set(user.color for user in User.query.filter(User.color.isnot(None)).all())
    user.color = generate_unique_color(existing_colors)
    db.session.commit()

def assign_colors_to_existing_users():
    users = User.query.filter(User.color.is_(None)).all()
    existing_colors = set(user.color for user in User.query.filter(User.color.isnot(None)).all())

    for user in users:
        user.color = generate_unique_color(existing_colors)
        existing_colors.add(user.color)
        db.session.commit()

    log.info("Assigned unique colors to existing users.")