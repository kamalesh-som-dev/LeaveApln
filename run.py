from app import create_app
from app.logger import log 

log.info("Creating Flask app...")
app = create_app()
log.info("Flask app created successfully.")

if __name__ == "__main__":
    log.info("Starting Flask app...")
    app.run(debug=True)