// ============================================================
// MIT-WPU SMART ATTENDANCE SYSTEM
// Flask + Dynamic QR Version
// ============================================================


// ============================================================
// GLOBAL VARIABLES
// ============================================================

let currentSessionId = null;
let countdownInterval = null;
let attendancePollingInterval = null;


// ============================================================
// PAGE INITIALIZATION
// ============================================================

document.addEventListener("DOMContentLoaded", function () {

    const path = window.location.pathname;

    // Student attendance page
    if (path.startsWith("/attendance/")) {

        const sessionId = path.split("/")[2];

        if (sessionId) {
            initializeStudentPage(sessionId);
        }

    }

    // Faculty page
    else {

        initializeFacultyPage();

    }

});


// ============================================================
// FACULTY PAGE
// ============================================================

function initializeFacultyPage() {

    const loginForm =
        document.getElementById("facultyLoginForm");

    const generateButton =
        document.getElementById("generateQRButton");

    const logoutButton =
        document.getElementById("logoutButton");


    // Faculty login
    if (loginForm) {

        loginForm.addEventListener(
            "submit",
            handleFacultyLogin
        );

    }


    // Generate QR
    if (generateButton) {

        generateButton.addEventListener(
            "click",
            generateAttendanceQR
        );

    }


    // Logout
    if (logoutButton) {

        logoutButton.addEventListener(
            "click",
            handleLogout
        );

    }

}


// ============================================================
// FACULTY LOGIN
// ============================================================

async function handleFacultyLogin(event) {

    event.preventDefault();


    const facultyId =
        document.getElementById("facultyId").value.trim();

    const password =
        document.getElementById("facultyPassword").value.trim();


    const message =
        document.getElementById("loginMessage");


    if (!facultyId || !password) {

        showMessage(
            message,
            "Please enter Faculty ID and password.",
            "error"
        );

        return;
    }


    try {

        const response = await fetch(
            "/api/login/faculty",
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({

                    faculty_id: facultyId,
                    password: password

                })
            }
        );


        const data = await response.json();

        console.log("Faculty login response:", data);
        
        if (!response.ok || !data.success) {

            showMessage(
                message,
                data.message || "Login failed.",
                "error"
            );

            return;
        }


        // Login successful

        showMessage(
            message,
            "Login successful!",
            "success"
        );


        // Display dashboard

        setTimeout(function () {

            document
                .getElementById("facultyLogin")
                .classList.add("hidden");

            document
                .getElementById("facultyDashboard")
                .classList.remove("hidden");


            document
                .getElementById("facultyWelcome")
                .textContent =
                "Welcome, " + data.faculty.name;


        }, 300);


    }

    catch (error) {

        console.error(
            "Faculty login error:",
            error
        );


        showMessage(
            message,
            "Cannot connect to Flask server.",
            "error"
        );

    }

}


// ============================================================
// GENERATE QR
// ============================================================

async function generateAttendanceQR() {

    const subject =
        document.getElementById("subject").value;

    const division =
        document.getElementById("division").value;

    const lecture =
        document.getElementById("lecture").value;


    const message =
        document.getElementById("facultyMessage");


    // Validate selections

    if (!subject || !division || !lecture) {

        showMessage(
            message,
            "Please select subject, division and lecture.",
            "error"
        );

        return;
    }


    const button =
        document.getElementById("generateQRButton");


    button.disabled = true;

    button.textContent =
        "Generating QR...";


    try {

        const response = await fetch(
            "/api/create-session",
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({

                    subject: subject,
                    division: division,
                    lecture: lecture

                })
            }
        );


        const data = await response.json();


        if (!response.ok || !data.success) {

            showMessage(
                message,
                data.message || "Could not generate QR.",
                "error"
            );

            return;
        }


        // Store current session

        currentSessionId =
            data.session.session_id;


        // Display QR

        document
            .getElementById("qrImage")
            .src = data.qr_image;


        // Display session information

        document
            .getElementById("qrSubject")
            .textContent =
            data.session.subject;


        document
            .getElementById("qrDivision")
            .textContent =
            data.session.division;


        document
            .getElementById("qrLecture")
            .textContent =
            data.session.lecture;


        // Show QR panel

        document
            .getElementById("qrPanel")
            .classList.remove("hidden");


        showMessage(
            message,
            "QR code generated successfully.",
            "success"
        );


        // Start 2-minute timer

        startCountdown(
            data.session.expires_at
        );


        // Start live attendance polling

        startAttendancePolling();


    }

    catch (error) {

        console.error(
            "QR generation error:",
            error
        );


        showMessage(
            message,
            "Cannot connect to Flask server.",
            "error"
        );

    }

    finally {

        button.disabled = false;

        button.textContent =
            "Generate Dynamic QR";

    }

}


// ============================================================
// QR COUNTDOWN
// ============================================================

function startCountdown(expiresAt) {

    // Stop previous timer

    if (countdownInterval) {

        clearInterval(countdownInterval);

    }


    function updateTimer() {

        const now =
            Math.floor(Date.now() / 1000);

        const remaining =
            Math.max(
                0,
                Math.floor(expiresAt - now)
            );


        const minutes =
            Math.floor(remaining / 60);

        const seconds =
            remaining % 60;


        const formattedTime =
            String(minutes).padStart(2, "0")
            + ":"
            + String(seconds).padStart(2, "0");


        document
            .getElementById("qrTimer")
            .textContent =
            formattedTime;


        // QR expired

        if (remaining <= 0) {

            clearInterval(countdownInterval);

            document
                .getElementById("qrTimer")
                .textContent =
                "EXPIRED";


            document
                .getElementById("qrTimer")
                .style.color =
                "#dc2626";

        }

    }


    updateTimer();


    countdownInterval =
        setInterval(
            updateTimer,
            1000
        );

}


// ============================================================
// LIVE ATTENDANCE POLLING
// ============================================================

function startAttendancePolling() {

    // Stop old polling

    if (attendancePollingInterval) {

        clearInterval(
            attendancePollingInterval
        );

    }


    // Get attendance immediately

    updateAttendanceDashboard();


    // Update every 2 seconds

    attendancePollingInterval =
        setInterval(
            updateAttendanceDashboard,
            2000
        );

}


// ============================================================
// UPDATE ATTENDANCE DASHBOARD
// ============================================================

async function updateAttendanceDashboard() {

    if (!currentSessionId) {
        return;
    }


    try {

        const response = await fetch(

            "/api/attendance/"
            + currentSessionId

        );


        if (!response.ok) {
            return;
        }


        const data =
            await response.json();


        if (!data.success) {
            return;
        }


        // Update statistics

        document
            .getElementById("totalStudents")
            .textContent =
            data.total_students;


        document
            .getElementById("presentStudents")
            .textContent =
            data.present;


        document
            .getElementById("absentStudents")
            .textContent =
            data.absent;


        document
            .getElementById("attendancePercentage")
            .textContent =
            data.percentage + "%";


        // Update table

        updateAttendanceTable(
            data.records
        );


    }

    catch (error) {

        console.error(
            "Attendance update error:",
            error
        );

    }

}


// ============================================================
// ATTENDANCE TABLE
// ============================================================

function updateAttendanceTable(records) {

    const tableBody =
        document.getElementById(
            "attendanceTableBody"
        );


    if (!records || records.length === 0) {

        tableBody.innerHTML = `

            <tr>

                <td
                    colspan="7"
                    class="empty-state"
                >

                    No attendance marked yet.

                </td>

            </tr>

        `;

        return;
    }


    tableBody.innerHTML = "";


    records.forEach(function (record, index) {

        const row =
            document.createElement("tr");


        row.innerHTML = `

            <td>
                ${index + 1}
            </td>

            <td>
                <strong>
                    ${escapeHTML(record.roll)}
                </strong>
            </td>

            <td>
                ${escapeHTML(record.name)}
            </td>

            <td>
                ${escapeHTML(record.division)}
            </td>

            <td>
                ${escapeHTML(record.subject)}
            </td>

            <td>
                ${escapeHTML(record.lecture)}
            </td>

            <td>
                ${formatDateTime(record.timestamp)}
            </td>

        `;


        tableBody.appendChild(row);

    });

}


// ============================================================
// LOGOUT
// ============================================================

async function handleLogout() {

    try {

        await fetch(
            "/api/logout",
            {
                method: "POST"
            }
        );

    }

    catch (error) {

        console.error(
            "Logout error:",
            error
        );

    }


    // Stop timers

    if (countdownInterval) {

        clearInterval(countdownInterval);

    }


    if (attendancePollingInterval) {

        clearInterval(
            attendancePollingInterval
        );

    }


    currentSessionId = null;


    // Hide dashboard

    document
        .getElementById("facultyDashboard")
        .classList.add("hidden");


    // Show login

    document
        .getElementById("facultyLogin")
        .classList.remove("hidden");


    // Reset form

    document
        .getElementById("facultyLoginForm")
        .reset();


    // Hide QR

    document
        .getElementById("qrPanel")
        .classList.add("hidden");


    // Reset QR timer

    document
        .getElementById("qrTimer")
        .textContent =
        "02:00";

}


// ============================================================
// STUDENT PAGE
// ============================================================

async function initializeStudentPage(sessionId) {

    // Hide faculty login

    document
        .getElementById("facultyLogin")
        .classList.add("hidden");


    // Hide faculty dashboard

    document
        .getElementById("facultyDashboard")
        .classList.add("hidden");


    // Show student page

    document
        .getElementById("studentAttendance")
        .classList.remove("hidden");


    // Load session

    await loadStudentSession(sessionId);


    // Setup form

    const form =
        document.getElementById(
            "attendanceForm"
        );


    if (form) {

        form.addEventListener(
            "submit",
            function (event) {

                handleStudentAttendance(
                    event,
                    sessionId
                );

            }
        );

    }


    // Register cryptographic device

    const registerDeviceButton =
        document.getElementById(
            "registerDeviceButton"
        );


    if (registerDeviceButton) {

        registerDeviceButton.addEventListener(
            "click",
            handleDeviceRegistration
        );

    }

}


// ============================================================
// LOAD STUDENT SESSION
// ============================================================

async function loadStudentSession(sessionId) {

    const status =
        document.getElementById(
            "studentQRStatus"
        );


    try {

        const response = await fetch(

            "/api/session/"
            + sessionId

        );


        const data =
            await response.json();


        if (!response.ok || !data.success) {

            status.textContent =
                "EXPIRED";

            status.style.color =
                "#dc2626";


            disableAttendanceForm();

            showMessage(

                document.getElementById(
                    "attendanceMessage"
                ),

                data.message ||
                "This QR code is invalid or expired.",

                "error"

            );

            return;
        }


        const sessionData =
            data.session;


        // Display session information

        document
            .getElementById("studentSubject")
            .textContent =
            sessionData.subject;


        document
            .getElementById("studentDivision")
            .textContent =
            sessionData.division;


        document
            .getElementById("studentLecture")
            .textContent =
            sessionData.lecture;


        status.textContent =
            "ACTIVE";


        status.style.color =
            "#16a34a";


        // Start student-side countdown

        startStudentCountdown(
            sessionData.expires_at
        );

    }

    catch (error) {

        console.error(
            "Session loading error:",
            error
        );


        status.textContent =
            "ERROR";


        status.style.color =
            "#dc2626";


        showMessage(

            document.getElementById(
                "attendanceMessage"
            ),

            "Unable to connect to attendance server.",

            "error"

        );

    }

}


// ============================================================
// STUDENT COUNTDOWN
// ============================================================

function startStudentCountdown(expiresAt) {

    if (countdownInterval) {

        clearInterval(
            countdownInterval
        );

    }


    function updateStudentTimer() {

        const now =
            Math.floor(
                Date.now() / 1000
            );


        const remaining =
            Math.max(
                0,
                Math.floor(
                    expiresAt - now
                )
            );


        if (remaining <= 0) {

            document
                .getElementById(
                    "studentQRStatus"
                )
                .textContent =
                "EXPIRED";


            document
                .getElementById(
                    "studentQRStatus"
                )
                .style.color =
                "#dc2626";


            disableAttendanceForm();


            clearInterval(
                countdownInterval
            );

        }

    }


    updateStudentTimer();


    countdownInterval =
        setInterval(
            updateStudentTimer,
            1000
        );

}

async function signAttendanceMessage(
    privateKey,
    message
) {
    const encoder = new TextEncoder();
    const data = encoder.encode(message);

    const signatureBuffer = await window.crypto.subtle.sign(
        {
            name: "RSA-PSS",
            saltLength: 32
        },
        privateKey,
        data
    );

    return arrayBufferToBase64(signatureBuffer);
}


// ============================================================
// STUDENT ATTENDANCE SUBMISSION
// ============================================================

async function handleStudentAttendance(event, sessionId) {
    event.preventDefault();

    const roll = document
        .getElementById("studentRoll")
        .value
        .trim();

    const password = document
        .getElementById("studentPassword")
        .value
        .trim();

    const message = document.getElementById("attendanceMessage");
    const button = document.getElementById("markAttendanceButton");

    if (!roll || !password) {
        showMessage(
            message,
            "Please enter roll number and password.",
            "error"
        );

        return;
    }

    const privateKey = await getPrivateKey(roll);

    if (!privateKey) {
        showMessage(
            message,
            "No registered device found. Please register this device first.",
            "error"
        );

        return;
    }

    button.disabled = true;
    button.textContent = "Verifying...";

    try {
        const challengeResponse = await fetch(
            "/api/session/" + sessionId + "/challenge"
        );

        const challengeData = await challengeResponse.json();

        if (!challengeResponse.ok || !challengeData.success) {
            showMessage(
                message,
                challengeData.message || "Unable to get security challenge.",
                "error"
            );

            return;
        }

        const challenge = challengeData.challenge;
        const signedMessage = sessionId + "|" + roll + "|" + challenge;
        const signature = await signAttendanceMessage(
            privateKey,
            signedMessage
        );

        const response = await fetch(
            "/api/attendance/" + sessionId,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    roll: roll,
                    password: password,
                    challenge: challenge,
                    signature: signature
                })
            }
        );

        const data = await response.json();

        if (!response.ok || !data.success) {
            showMessage(
                message,
                data.message || "Attendance could not be marked.",
                "error"
            );

            return;
        }

        // SUCCESS
        showMessage(
            message,
            "Attendance marked successfully! Welcome, " + data.student.name,
            "success"
        );

        // Disable form after successful attendance
        document.getElementById("studentRoll").disabled = true;
        document.getElementById("studentPassword").disabled = true;

        button.disabled = true;
        button.textContent = "Attendance Marked ✓";

    } catch (error) {
        console.error("Attendance submission error:", error);

        showMessage(
            message,
            "Unable to connect to server.",
            "error"
        );
    } finally {
        if (!button.disabled) {
            button.textContent = "Mark Attendance";
        }
    }

}
// ============================================================

function disableAttendanceForm() {

    const roll =
        document.getElementById(
            "studentRoll"
        );

    const password =
        document.getElementById(
            "studentPassword"
        );

    const button =
        document.getElementById(
            "markAttendanceButton"
        );


    if (roll) {
        roll.disabled = true;
    }


    if (password) {
        password.disabled = true;
    }


    if (button) {

        button.disabled = true;

        button.textContent =
            "QR Code Expired";

    }

}


// ============================================================
// MESSAGE HELPER
// ============================================================

function showMessage(
    element,
    text,
    type
) {

    if (!element) {
        return;
    }


    element.textContent = text;


    element.className =
        "message show " + type;

}


// ============================================================
// DATE/TIME FORMATTER
// ============================================================

function formatDateTime(timestamp) {

    if (!timestamp) {
        return "-";
    }

    try {

        const date = new Date(timestamp);

        return date.toLocaleTimeString("en-IN", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit"
        });

    } catch (error) {

        return timestamp;

    }

}


// ============================================================
// BASIC HTML ESCAPING
// ============================================================

function escapeHTML(value) {

    if (value === null || value === undefined) {
        return "";
    }

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");

}


// ============================================================
// PHASE 2 - WEB CRYPTO DEVICE REGISTRATION
// ============================================================

const DEVICE_DB_NAME = "MIT-WPU-Smart-Attendance";
const DEVICE_DB_VERSION = 1;
const DEVICE_STORE_NAME = "deviceKeys";

/*
 * Open IndexedDB database.
 */
function openDeviceDatabase() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(
            DEVICE_DB_NAME,
            DEVICE_DB_VERSION
        );

        request.onupgradeneeded = function (event) {
            const db = event.target.result;

            if (!db.objectStoreNames.contains(DEVICE_STORE_NAME)) {
                db.createObjectStore(DEVICE_STORE_NAME);
            }
        };

        request.onsuccess = function (event) {
            resolve(event.target.result);
        };

        request.onerror = function () {
            reject(request.error);
        };
    });
}


/*
 * Save the private key in IndexedDB.
 *
 * The private key is generated as non-extractable,
 * so JavaScript cannot export the actual private key material.
 */
async function savePrivateKey(privateKey, roll) {
    const db = await openDeviceDatabase();

    return new Promise((resolve, reject) => {
        const transaction = db.transaction(
            DEVICE_STORE_NAME,
            "readwrite"
        );

        const store = transaction.objectStore(DEVICE_STORE_NAME);

        const request = store.put(
            privateKey,
            "privateKey_" + roll
        );

        request.onsuccess = function () {
            resolve();
        };

        request.onerror = function () {
            reject(request.error);
        };
    });
}


/*
 * Retrieve the student's private key from IndexedDB.
 */
async function getPrivateKey(roll) {
    const db = await openDeviceDatabase();

    return new Promise((resolve, reject) => {
        const transaction = db.transaction(
            DEVICE_STORE_NAME,
            "readonly"
        );

        const store = transaction.objectStore(DEVICE_STORE_NAME);

        const request = store.get("privateKey_" + roll);

        request.onsuccess = function () {
            resolve(request.result || null);
        };

        request.onerror = function () {
            reject(request.error);
        };
    });
}


/*
 * Generate an RSA-PSS key pair for this device.
 *
 * The private key is deliberately non-extractable.
 */
async function generateDeviceKeyPair() {
    return await window.crypto.subtle.generateKey(
        {
            name: "RSA-PSS",
            modulusLength: 2048,
            publicExponent: new Uint8Array([1, 0, 1]),
            hash: "SHA-256"
        },
        false,
        ["sign", "verify"]
    );
}


/*
 * Convert an ArrayBuffer into Base64.
 *
 * The public key will be sent to Flask as Base64.
 */
function arrayBufferToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = "";

    for (let i = 0; i < bytes.byteLength; i++) {
        binary += String.fromCharCode(bytes[i]);
    }

    return btoa(binary);
}


/*
 * Export only the PUBLIC key.
 *
 * The private key is never exported.
 */
async function exportPublicKey(publicKey) {
    const publicKeyBuffer =
        await window.crypto.subtle.exportKey(
            "spki",
            publicKey
        );

    const bytes =
        new Uint8Array(publicKeyBuffer);

    let binary = "";

    for (let i = 0; i < bytes.byteLength; i++) {
        binary += String.fromCharCode(bytes[i]);
    }

    const base64 =
        btoa(binary);

    const lines =
        base64.match(/.{1,64}/g) || [];

    return (
        "-----BEGIN PUBLIC KEY-----\n" +
        lines.join("\n") +
        "\n-----END PUBLIC KEY-----"
    );
}

async function handleDeviceRegistration() {

    const roll =
        document
            .getElementById("studentRoll")
            .value
            .trim();

    const password =
        document
            .getElementById("studentPassword")
            .value
            .trim();

    const message =
        document.getElementById(
            "attendanceMessage"
        );


    if (!roll || !password) {

        showMessage(
            message,
            "Please enter roll number and password first.",
            "error"
        );

        return;
    }


    const result =
        await registerCryptographicDevice(
            roll,
            password
        );


    if (result.success) {

        showMessage(
            message,
            result.message ||
            "This device has been registered successfully.",
            "success"
        );

    } else {

        showMessage(
            message,
            result.message ||
            "Could not register this device.",
            "error"
        );

    }

}


/*
 * Create and register a cryptographic device.
 *
 * This function:
 *
 * 1. Generates RSA-PSS key pair
 * 2. Keeps private key inside browser
 * 3. Stores private key in IndexedDB
 * 4. Exports ONLY the public key
 * 5. Sends public key to Flask
 */
async function registerCryptographicDevice(roll, password) {

    try {

        console.log("Starting cryptographic device registration...");

        // Check whether this browser already has a key.
        const existingKey = await getPrivateKey(roll);

        if (existingKey) {
            console.log(
                "A cryptographic key already exists for roll:",
                roll
            );

            return {
                success: true,
                alreadyRegistered: true
            };
        }

        // Generate a new RSA-PSS key pair.
        const keyPair = await generateDeviceKeyPair();

        console.log("RSA-PSS key pair generated.");

        // Save PRIVATE key locally.
        await savePrivateKey(keyPair.privateKey, roll);

        console.log("Private key stored in IndexedDB.");

        // Export ONLY the public key.
        const publicKeyBase64 = await exportPublicKey(keyPair.publicKey);

        console.log("Public key exported.");

        // Send public key to Flask.
        const response = await fetch("/api/register-device", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                roll: roll,
                password: password,
                public_key: publicKeyBase64
            })
        });

        const result = await response.json();

        if (!response.ok) {
            console.error("Device registration failed:", result);

            return {
                success: false,
                message: result.message || "Device registration failed."
            };
        }

        console.log("Device registration successful.");

        return {
            success: true,
            alreadyRegistered: false,
            message: result.message || "Device registered successfully."
        };

    } catch (error) {

        console.error("Cryptographic device registration error:", error);

        return {
            success: false,
            message: "Could not register this device."
        };
    }
}