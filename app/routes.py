from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, jsonify
from flask_login import login_user, logout_user, login_required, current_user
import cv2
import numpy as np
from datetime import datetime
import json
from app import db
from app.models import User, Student, Attendance
import os
from threading import Thread, Lock
import threading
import time
import queue
from flask import current_app

main = Blueprint('main', __name__)
auth = Blueprint('auth', __name__)

# Global variables for frame sharing between threads
frame_queue = queue.Queue(maxsize=10)
current_frame = None
frame_lock = threading.Lock()

# Authentication routes
@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return redirect(url_for('auth.signup'))

        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('auth.signup'))

        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Account created successfully', 'success')
        return redirect(url_for('auth.login'))

    return render_template('login.html', mode='signup')

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.index'))
        else:
            flash('Invalid username or password', 'error')

    return render_template('login.html', mode='login')

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

# Main routes
@main.route('/')
@login_required
def index():
    return render_template('index.html')

@main.route('/register_student', methods=['GET', 'POST'])
@login_required
def register_student():
    if request.method == 'POST':
        enrollment = request.form.get('enrollment')
        name = request.form.get('name')

        if Student.query.filter_by(enrollment=enrollment).first():
            flash('Enrollment number already exists', 'error')
            return redirect(url_for('main.register_student'))

        student = Student(enrollment=enrollment, name=name)
        db.session.add(student)
        db.session.commit()

        return redirect(url_for('main.capture_images', student_id=student.id))

    return render_template('register_student.html')

def background_attendance_processor(app, subject):
    with app.app_context():
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        try:
            recognizer.read('app/static/trainer/trainner.yml')
        except:
            print("Model not trained")
            return

        while True:
            with frame_lock:
                if current_frame is None:
                    time.sleep(0.1)
                    continue
                
                frame = current_frame.copy()

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
            faces = face_cascade.detectMultiScale(gray, 1.3, 5)

            for (x, y, w, h) in faces:
                face_roi = gray[y:y+h, x:x+w]
                try:
                    student_id, confidence = recognizer.predict(face_roi)
                    if confidence < 70:  # Lower confidence value means better match
                        student = Student.query.get(student_id)
                        if student:
                            # Check if attendance already marked
                            existing_attendance = Attendance.query.filter_by(
                                student_id=student.id,
                                subject=subject,
                                date=datetime.now().date()
                            ).first()

                            if not existing_attendance:
                                attendance = Attendance(
                                    student_id=student.id,
                                    subject=subject,
                                    date=datetime.now().date(),
                                    time=datetime.now().time()
                                )
                                db.session.add(attendance)
                                db.session.commit()

                                # Add to frame queue for UI update
                                attendance_data = {
                                    'student_name': student.name,
                                    'enrollment': student.enrollment,
                                    'time': datetime.now().strftime('%H:%M:%S')
                                }
                                try:
                                    frame_queue.put_nowait(attendance_data)
                                except queue.Full:
                                    pass

                except Exception as e:
                    print(f"Recognition error: {e}")

            time.sleep(0.1)  # Small delay to prevent CPU overuse

@main.route('/take_attendance', methods=['GET', 'POST'])
@login_required
def take_attendance():
    if request.method == 'POST':
        subject = request.form.get('subject')
        if not subject:
            flash('Subject is required', 'error')
            return redirect(url_for('main.take_attendance'))
        
        # Start background thread for continuous attendance
        attendance_thread = Thread(target=background_attendance_processor, 
                                 args=(current_app._get_current_object(), subject))
        attendance_thread.daemon = True
        attendance_thread.start()
        
        return render_template('take_attendance.html', subject=subject)
        
    return render_template('take_attendance.html')

@main.route('/mark_manual_attendance', methods=['POST'])
@login_required
def mark_manual_attendance():
    enrollment = request.form.get('enrollment')
    name = request.form.get('name')
    subject = request.form.get('subject')

    if not all([enrollment, name, subject]):
        return jsonify({
            'success': False,
            'message': 'All fields are required'
        })

    # Check if student exists
    student = Student.query.filter_by(enrollment=enrollment).first()
    
    # If student doesn't exist, create a new one
    if not student:
        student = Student(enrollment=enrollment, name=name)
        db.session.add(student)
        db.session.commit()

    # Check if attendance already marked
    existing_attendance = Attendance.query.filter_by(
        student_id=student.id,
        subject=subject,
        date=datetime.now().date()
    ).first()

    if existing_attendance:
        return jsonify({
            'success': False,
            'message': 'Attendance already marked for this student today'
        })

    # Mark attendance
    attendance = Attendance(
        student_id=student.id,
        subject=subject,
        date=datetime.now().date(),
        time=datetime.now().time()
    )
    db.session.add(attendance)
    db.session.commit()

    return jsonify({
        'success': True,
        'student_name': student.name,
        'enrollment': student.enrollment,
        'time': datetime.now().strftime('%H:%M:%S')
    })

@main.route('/get_latest_attendance')
def get_latest_attendance():
    try:
        attendance_data = frame_queue.get_nowait()
        return jsonify({'success': True, **attendance_data})
    except queue.Empty:
        return jsonify({'success': False})

@main.route('/stop_attendance')
@login_required
def stop_attendance():
    # Clear the frame queue
    while not frame_queue.empty():
        try:
            frame_queue.get_nowait()
        except queue.Empty:
            break
    
    return redirect(url_for('main.take_attendance'))

@main.route('/capture_images/<int:student_id>')
@login_required
def capture_images(student_id):
    student = Student.query.get_or_404(student_id)
    enrollment_folder = os.path.join('app/static/faces', str(student.enrollment))

    # Create a folder for the student if it doesn't already exist
    if not os.path.exists(enrollment_folder):
        os.makedirs(enrollment_folder)

    # Initialize camera
    camera = cv2.VideoCapture(0)
    face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
    count = 0
    face_encodings = []

    while count < 30:
        success, frame = camera.read()
        if not success:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)

        for (x, y, w, h) in faces:
            count += 1
            face_roi = gray[y:y+h, x:x+w]
            face_encodings.append(face_roi.tolist())

            # Save the image in the student's folder
            image_path = os.path.join(enrollment_folder, f'{count}.jpg')
            cv2.imwrite(image_path, face_roi)

            # Draw a rectangle around the face
            cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)

        # Show the frame to the user
        cv2.imshow('Capturing Images', frame)

        # Break loop on 'q' key press or after 30 images
        if cv2.waitKey(1) & 0xFF == ord('q') or count >= 30:
            break

    # Release camera and close window
    camera.release()
    cv2.destroyAllWindows()

    # Save encodings and redirect
    student.face_encodings = json.dumps(face_encodings)
    db.session.commit()

    flash(f'Student {student.name} registered successfully!', 'success')
    return redirect(url_for('main.index'))

@main.route('/finish_capture/<int:student_id>')
@login_required
def finish_capture(student_id):
    student = Student.query.get_or_404(student_id)
    flash(f'Student {student.name} registered successfully!', 'success')
    return redirect(url_for('main.index'))

def generate_frames(app):
    with app.app_context():
        camera = cv2.VideoCapture(0)
        face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
        recognizer = cv2.face.LBPHFaceRecognizer_create()

        try:
            recognizer.read('app/static/trainer/trainner.yml')
        except Exception as e:
            print(f"Error loading model: {e}")
            return "Model not trained"

        while True:
            success, frame = camera.read()
            if not success:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.3, 5)

            for (x, y, w, h) in faces:
                face_roi = gray[y:y+h, x:x+w]
                try:
                    student_id, confidence = recognizer.predict(face_roi)
                    if confidence < 70:
                        student = Student.query.get(student_id)
                        if student:
                            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                            cv2.putText(frame, f'{student.name}', (x, y-10),
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                            with frame_lock:
                                global current_frame
                                current_frame = frame.copy()
                except Exception as e:
                    print(f"Recognition error: {e}")

            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@main.route('/video_feed')
def video_feed():
    app = current_app._get_current_object()
    return Response(generate_frames(app),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@main.route('/view_attendance')
@login_required
def view_attendance():
    attendances = Attendance.query.order_by(Attendance.created_at.desc()).all()
    # Get unique subjects for the filter dropdown
    subjects = db.session.query(Attendance.subject).distinct().order_by(Attendance.subject).all()
    subjects = [subject[0] for subject in subjects]  # Convert from tuple to list
    return render_template('view_attendance.html', attendances=attendances, subjects=subjects)

@main.route('/train_model')
@login_required
def train_model():
    students = Student.query.all()
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    face_samples = []
    student_ids = []

    for student in students:
        if student.face_encodings:
            encodings = json.loads(student.face_encodings)
            for encoding in encodings:
                face_samples.append(np.array(encoding))
                student_ids.append(student.id)

    if face_samples:
        recognizer.train(face_samples, np.array(student_ids))
        recognizer.save('app/static/trainer/trainner.yml')
        flash('Model trained successfully', 'success')
    else:
        flash('No face data available for training', 'error')

    return redirect(url_for('main.index'))