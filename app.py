from flask import Flask, request, jsonify, send_from_directory, session
import json
import os
import time
import secrets
import io
import base64
from datetime import datetime
import qrcode

from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding

app = Flask(__name__)

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

app.secret_key = "mitwpu-smart-attendance-demo-secret"

# Your laptop's Wi-Fi IPv4 address
# Change this if your IP address changes.
NETWORK_IP = "10.148.246.146"

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
# DIGITAL SIGNATURE VERIFICATION
# ---------------------------------------------------------

def verify_student_signature(
    public_key_pem,
    message,
    signature_base64
):
    try:
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode("utf-8")
        )

        signature = base64.b64decode(
            signature_base64
        )

        public_key.verify(
            signature,
            message.encode("utf-8"),
            padding.PSS(
                mgf=padding.MGF1(
                    hashes.SHA256()
                ),
                salt_length=32
            ),
            hashes.SHA256()
        )

        return True

    except Exception:
        return False

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

    current_time = time.time()

    expired_sessions = [
        sid
        for sid, details in active_sessions.items()
        if details["expires_at"] < current_time
    ]

    for sid in expired_sessions:
        del active_sessions[sid]

    session_id = (
        "MITWPU-"
        + str(int(time.time()))
        + "-"
        + secrets.token_hex(3).upper()
    )

    created_at = time.time()
    expires_at = created_at + QR_VALIDITY
    challenge = secrets.token_urlsafe(32)

    active_sessions[session_id] = {
        "session_id": session_id,
        "subject": subject,
        "division": division,
        "lecture": lecture,
        "created_at": created_at,
        "expires_at": expires_at,
        "challenge": challenge,
        "challenge_started_at": created_at
    }

    attendance_url = (
        f"http://{NETWORK_IP}:{PORT}"
        f"/attendance/{session_id}"
    )

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
    qr_image.save(image_buffer, format="PNG")
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
        "qr_image": "data:image/png;base64," + qr_base64
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

    public_session = {
        "session_id": session_data["session_id"],
        "subject": session_data["subject"],
        "division": session_data["division"],
        "lecture": session_data["lecture"],
        "created_at": session_data["created_at"],
        "expires_at": session_data["expires_at"]
    }

    return jsonify({
        "success": True,
        "session": public_session,
        "remaining_seconds": int(session_data["expires_at"] - current_time)
    })


# ---------------------------------------------------------
# GET CURRENT SHORT-LIVED CHALLENGE
# ---------------------------------------------------------

CHALLENGE_VALIDITY = 30


@app.route("/api/session/<session_id>/challenge", methods=["GET"])
def get_challenge(session_id):

    session_data = active_sessions.get(session_id)

    if not session_data:
        return jsonify({
            "success": False,
            "message": "Invalid or expired session."
        }), 404

    current_time = time.time()

    if current_time > session_data["expires_at"]:
        del active_sessions[session_id]
        return jsonify({
            "success": False,
            "message": "Attendance session has expired."
        }), 410

    challenge_age = current_time - session_data["challenge_started_at"]

    if challenge_age >= CHALLENGE_VALIDITY:
        session_data["challenge"] = secrets.token_urlsafe(32)
        session_data["challenge_started_at"] = current_time

    return jsonify({
        "success": True,
        "challenge": session_data["challenge"],
        "expires_in": int(
            CHALLENGE_VALIDITY
            - (current_time - session_data["challenge_started_at"])
        )
    })


# ---------------------------------------------------------
# STUDENT PUBLIC KEY REGISTRATION
# ---------------------------------------------------------

@app.route("/api/register-device", methods=["POST"])
def register_device():

    data = request.get_json(silent=True) or {}

    roll = str(data.get("roll", "")).strip()
    password = data.get("password", "").strip()
    public_key = data.get("public_key", "").strip()

    if not roll or not password or not public_key:
        return jsonify({
            "success": False,
            "message": "Roll number, password and public key are required."
        }), 400

    database = load_data()

    student = next(
        (
            student
            for student in database.get("students", [])
            if str(student.get("roll")) == roll
        ),
        None
    )

    if not student:
        return jsonify({
            "success": False,
            "message": "Student not found."
        }), 404

    if student.get("password") != password:
        return jsonify({
            "success": False,
            "message": "Incorrect password."
        }), 401

    # Do not silently replace an existing registered key.
    if student.get("public_key"):
        return jsonify({
            "success": False,
            "message": "This student already has a registered device."
        }), 409

    try:
        # Validate that the received key is actually a valid public key.
        serialization.load_pem_public_key(
            public_key.encode("utf-8")
        )

    except Exception:
        return jsonify({
            "success": False,
            "message": "Invalid public key."
        }), 400

    student["public_key"] = public_key

    save_data(database)

    return jsonify({
        "success": True,
        "message": "Device registered successfully.",
        "roll": roll
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
    signature = data.get("signature", "").strip()
    challenge = data.get("challenge", "").strip()

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
    # CHECK DIGITAL SIGNATURE
    # -----------------------------------------------------

    if not signature or not challenge:

        return jsonify({
            "success": False,
            "message": "Digital signature and challenge are required."
        }), 400
    # The challenge must match the current session challenge.
    if challenge != session_data.get("challenge"):

        return jsonify({
            "success": False,
            "message": "Invalid or expired security challenge."
        }), 401

    public_key = student.get("public_key")

    if not public_key:

        return jsonify({
            "success": False,
            "message": "No registered device found for this student."
        }), 403

    signed_message = (
        session_id
        + "|"
        + roll
        + "|"
        + challenge
    )

    signature_valid = verify_student_signature(
        public_key,
        signed_message,
        signature
    )

    if not signature_valid:

        return jsonify({
            "success": False,
            "message": "Invalid device signature."
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
