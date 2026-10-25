from flask import Flask, request, jsonify, send_from_directory, session
import json
import os
import time
import secrets
import io
import base64
from datetime import datetime
import qrcode

app = Flask(__name__)

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

app.secret_key = "mitwpu-smart-attendance-demo-secret"

# Your laptop's Wi-Fi IPv4 address
# Change this if your IP address changes.
NETWORK_IP = "10.70.60.146"

PORT = 5000

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "students.json")

# QR validity = 2 minutes
QR_VALIDITY = 120

# Active QR sessions are kept in memory
active_sessions = {}


# ---------------------------------------------------------
# DATA FUNCTIONS
# ---------------------------------------------------------

def load_data():
    """Load faculty and student data from students.json."""

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

    except FileNotFoundError:
        data = {
            "faculty": [],
            "students": [],
            "attendance": []
        }

    # Make sure attendance exists
    if "attendance" not in data:
        data["attendance"] = []

    return data


def save_data(data):
    """Save data back to students.json."""

    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


# ---------------------------------------------------------
# BASIC PAGE ROUTES
# ---------------------------------------------------------

@app.route("/")
def home():
    """Faculty login/dashboard."""

    return send_from_directory(BASE_DIR, "index.html")


@app.route("/attendance/<session_id>")
def attendance_page(session_id):
    """Student attendance page opened after scanning QR."""

    return send_from_directory(BASE_DIR, "index.html")


@app.route("/style.css")
def style():
    return send_from_directory(BASE_DIR, "style.css")


@app.route("/script.js")
def script():
    return send_from_directory(BASE_DIR, "script.js")


# ---------------------------------------------------------
# FACULTY LOGIN
# ---------------------------------------------------------

@app.route("/api/login/faculty", methods=["POST"])
def faculty_login():

    data = request.get_json()

    faculty_id = data.get("faculty_id", "").strip()
    password = data.get("password", "").strip()

    database = load_data()

    for faculty in database.get("faculty", []):

        if (
            faculty.get("id") == faculty_id
            and faculty.get("password") == password
        ):

            session["faculty_id"] = faculty_id
            session["faculty_name"] = faculty.get("name")

            return jsonify({
                "success": True,
                "message": "Faculty login successful",
                "faculty": {
                    "id": faculty_id,
                    "name": faculty.get("name")
                }
            })

    return jsonify({
        "success": False,
        "message": "Invalid faculty ID or password."
    }), 401


# ---------------------------------------------------------
# FACULTY LOGOUT
# ---------------------------------------------------------

@app.route("/api/logout", methods=["POST"])
def logout():

    session.clear()

    return jsonify({
        "success": True,
        "message": "Logged out successfully."
    })


# ---------------------------------------------------------
# CREATE QR SESSION
# ---------------------------------------------------------

@app.route("/api/create-session", methods=["POST"])
def create_session():

    # Faculty must be logged in
    if "faculty_id" not in session:
        return jsonify({
            "success": False,
            "message": "Faculty login required."
        }), 401

    data = request.get_json()

    subject = data.get("subject", "").strip()
    division = data.get("division", "").strip()
    lecture = data.get("lecture", "").strip()

    if not subject or not division or not lecture:
        return jsonify({
            "success": False,
            "message": "Please select subject, division and lecture."
        }), 400

    # Remove expired sessions
    current_time = time.time()

    expired_sessions = [
        sid
        for sid, details in active_sessions.items()
        if details["expires_at"] < current_time
    ]

    for sid in expired_sessions:
        del active_sessions[sid]

    # Generate unique session ID
    session_id = (
        "MITWPU-"
        + str(int(time.time()))
        + "-"
        + secrets.token_hex(3).upper()
    )

    created_at = time.time()
    expires_at = created_at + QR_VALIDITY

    active_sessions[session_id] = {
        "session_id": session_id,
        "subject": subject,
        "division": division,
        "lecture": lecture,
        "created_at": created_at,
        "expires_at": expires_at
    }

    # -----------------------------------------------------
    # QR LINK
    # -----------------------------------------------------

    attendance_url = (
        f"http://{NETWORK_IP}:{PORT}"
        f"/attendance/{session_id}"
    )

    # -----------------------------------------------------
    # GENERATE QR IMAGE USING PYTHON
    # -----------------------------------------------------

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4
    )

    qr.add_data(attendance_url)
    qr.make(fit=True)

    qr_image = qr.make_image(
        fill_color="black",
        back_color="white"
    )

    image_buffer = io.BytesIO()

    qr_image.save(
        image_buffer,
        format="PNG"
    )

    image_buffer.seek(0)

    qr_base64 = base64.b64encode(
        image_buffer.getvalue()
    ).decode("utf-8")

    return jsonify({
        "success": True,

        "session": {
            "session_id": session_id,
            "subject": subject,
            "division": division,
            "lecture": lecture,
            "created_at": created_at,
            "expires_at": expires_at
        },

        "attendance_url": attendance_url,

        "qr_image":
            "data:image/png;base64,"
            + qr_base64
    })


# ---------------------------------------------------------
# GET SESSION INFORMATION
# ---------------------------------------------------------

@app.route("/api/session/<session_id>", methods=["GET"])
def get_session(session_id):

    session_data = active_sessions.get(session_id)

    if not session_data:
        return jsonify({
            "success": False,
            "message": "This QR session does not exist or has expired."
        }), 404

    current_time = time.time()

    if current_time > session_data["expires_at"]:

        del active_sessions[session_id]

        return jsonify({
            "success": False,
            "message": "This QR code has expired."
        }), 410

    return jsonify({
        "success": True,
        "session": session_data,
        "remaining_seconds":
            int(session_data["expires_at"] - current_time)
    })


# ---------------------------------------------------------
# STUDENT MARK ATTENDANCE
# ---------------------------------------------------------

@app.route("/api/attendance/<session_id>", methods=["POST"])
def mark_attendance(session_id):

    session_data = active_sessions.get(session_id)

    # -----------------------------------------------------
    # CHECK QR SESSION
    # -----------------------------------------------------

    if not session_data:
        return jsonify({
            "success": False,
            "message": "Invalid or expired QR code."
        }), 400

    current_time = time.time()

    if current_time > session_data["expires_at"]:

        del active_sessions[session_id]

        return jsonify({
            "success": False,
            "message": "This QR code has expired."
        }), 410

    # -----------------------------------------------------
    # GET STUDENT CREDENTIALS
    # -----------------------------------------------------

    data = request.get_json()

    roll = data.get("roll", "").strip()
    password = data.get("password", "").strip()

    if not roll or not password:
        return jsonify({
            "success": False,
            "message": "Please enter roll number and password."
        }), 400

    database = load_data()

    students = database.get("students", [])

    # -----------------------------------------------------
    # FIND STUDENT
    # -----------------------------------------------------

    student = None

    for item in students:

        if item.get("roll") == roll:

            student = item
            break

    if not student:

        return jsonify({
            "success": False,
            "message": "Student not found."
        }), 401

    # -----------------------------------------------------
    # CHECK PASSWORD
    # -----------------------------------------------------

    if student.get("password") != password:

        return jsonify({
            "success": False,
            "message": "Incorrect password."
        }), 401

    # -----------------------------------------------------
    # CHECK DIVISION
    # -----------------------------------------------------

    if student.get("division") != session_data["division"]:

        return jsonify({
            "success": False,
            "message":
                "You cannot mark attendance for this division."
        }), 403

    # -----------------------------------------------------
    # CHECK DUPLICATE ATTENDANCE
    # -----------------------------------------------------

    attendance_records = database.get("attendance", [])

    for record in attendance_records:

        if (
            record.get("session_id") == session_id
            and record.get("roll") == roll
        ):

            return jsonify({
                "success": False,
                "message": "Attendance already marked."
            }), 409

    # -----------------------------------------------------
    # CREATE ATTENDANCE RECORD
    # -----------------------------------------------------

    attendance_record = {

        "session_id":
            session_id,

        "roll":
            student.get("roll"),

        "name":
            student.get("name"),

        "division":
            student.get("division"),

        "subject":
            session_data.get("subject"),

        "lecture":
            session_data.get("lecture"),

        "timestamp":
            datetime.now().isoformat(timespec="seconds")
    }

    attendance_records.append(attendance_record)

    database["attendance"] = attendance_records

    save_data(database)

    # -----------------------------------------------------
    # SUCCESS
    # -----------------------------------------------------

    return jsonify({

        "success": True,

        "message":
            "Attendance marked successfully!",

        "student": {

            "roll":
                student.get("roll"),

            "name":
                student.get("name"),

            "division":
                student.get("division")
        }
    })


# ---------------------------------------------------------
# GET ATTENDANCE FOR FACULTY DASHBOARD
# ---------------------------------------------------------

@app.route("/api/attendance/<session_id>", methods=["GET"])
def get_attendance(session_id):

    # Faculty only
    if "faculty_id" not in session:
        return jsonify({
            "success": False,
            "message": "Faculty login required."
        }), 401

    session_data = active_sessions.get(session_id)

    if not session_data:

        return jsonify({
            "success": False,
            "message": "Session not found."
        }), 404

    database = load_data()

    records = [

        record
        for record in database.get("attendance", [])

        if record.get("session_id") == session_id
    ]

    total_students = sum(

        1

        for student in database.get("students", [])

        if student.get("division")
        == session_data.get("division")
    )

    present = len(records)

    absent = max(
        total_students - present,
        0
    )

    percentage = 0

    if total_students > 0:

        percentage = round(
            (present / total_students) * 100,
            2
        )

    return jsonify({

        "success": True,

        "total_students":
            total_students,

        "present":
            present,

        "absent":
            absent,

        "percentage":
            percentage,

        "records":
            records
    })


# ---------------------------------------------------------
# RUN SERVER
# ---------------------------------------------------------

if __name__ == "__main__":

    print()
    print("=" * 60)
    print("MIT-WPU SMART ATTENDANCE SYSTEM")
    print("=" * 60)
    print()
    print(
        f"Faculty Dashboard:"
        f" http://{NETWORK_IP}:{PORT}"
    )
    print()
    print(
        "Students can scan the QR code using their phone."
    )
    print()
    print("QR validity: 2 minutes")
    print()
    print("=" * 60)

    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False
    )