from flask import Flask, render_template, request, jsonify
import sqlite3
import face_recognition
import numpy as np
import base64
import io
from PIL import Image
from datetime import datetime
import os

app = Flask(__name__)

DATABASE = 'attendance.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS attendees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                face_encoding BLOB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attendee_id INTEGER NOT NULL,
                marked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (attendee_id) REFERENCES attendees (id)
            )
        ''')
        conn.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create-attendee')
def create_attendee_page():
    return render_template('create_attendee.html')

@app.route('/mark-attendance')
def mark_attendance_page():
    return render_template('mark_attendance.html')

@app.route('/view-attendance')
def view_attendance_page():
    return render_template('view_attendance.html')

@app.route('/api/create-attendee', methods=['POST'])
def create_attendee():
    try:
        data = request.json
        name = data.get('name', '').strip()
        image_data = data.get('image')

        if not name or not image_data:
            return jsonify({'success': False, 'message': 'Name and image are required'}), 400

        image_data = image_data.split(',')[1]
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        image_array = np.array(image)

        face_encodings = face_recognition.face_encodings(image_array)

        if len(face_encodings) == 0:
            return jsonify({'success': False, 'message': 'No face detected in the image'}), 400

        face_encoding = face_encodings[0]

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT name FROM attendees WHERE name = ?', (name,))
            existing = cursor.fetchone()

            if existing:
                return jsonify({'success': False, 'message': 'Already Exists'}), 400

            encoding_blob = face_encoding.tobytes()
            cursor.execute(
                'INSERT INTO attendees (name, face_encoding) VALUES (?, ?)',
                (name, encoding_blob)
            )
            conn.commit()

        return jsonify({'success': True, 'message': f'Attendee {name} created successfully'})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/mark-attendance', methods=['POST'])
def mark_attendance():
    try:
        data = request.json
        image_data = data.get('image')

        if not image_data:
            return jsonify({'success': False, 'message': 'Image is required'}), 400

        image_data = image_data.split(',')[1]
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        image_array = np.array(image)

        face_encodings = face_recognition.face_encodings(image_array)

        if len(face_encodings) == 0:
            return jsonify({'success': False, 'message': 'No face detected in the image'}), 400

        captured_encoding = face_encodings[0]

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, name, face_encoding FROM attendees')
            attendees = cursor.fetchall()

            if not attendees:
                return jsonify({'success': False, 'message': 'No attendees registered'}), 400

            matched_attendee = None

            for attendee in attendees:
                stored_encoding = np.frombuffer(attendee['face_encoding'], dtype=np.float64)
                match = face_recognition.compare_faces([stored_encoding], captured_encoding, tolerance=0.6)

                if match[0]:
                    matched_attendee = attendee
                    break

            if not matched_attendee:
                return jsonify({'success': False, 'message': 'Face not recognized'}), 400

            today = datetime.now().date()
            cursor.execute('''
                SELECT COUNT(*) as count FROM attendance
                WHERE attendee_id = ? AND DATE(marked_at) = ?
            ''', (matched_attendee['id'], today))

            result = cursor.fetchone()

            if result['count'] > 0:
                return jsonify({
                    'success': False,
                    'message': f'{matched_attendee["name"]} has already marked attendance today'
                }), 400

            cursor.execute(
                'INSERT INTO attendance (attendee_id) VALUES (?)',
                (matched_attendee['id'],)
            )
            conn.commit()

        return jsonify({
            'success': True,
            'message': f'Attendance marked for {matched_attendee["name"]}'
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/attendance-records', methods=['GET'])
def get_attendance_records():
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT
                    attendees.name,
                    attendance.marked_at
                FROM attendance
                JOIN attendees ON attendance.attendee_id = attendees.id
                ORDER BY attendance.marked_at DESC
            ''')

            records = cursor.fetchall()

            attendance_list = []
            for record in records:
                attendance_list.append({
                    'name': record['name'],
                    'marked_at': record['marked_at']
                })

            return jsonify({'success': True, 'records': attendance_list})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
