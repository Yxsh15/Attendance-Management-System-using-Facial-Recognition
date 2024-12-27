# Face Recognition Attendance Management System (AMS)

A Flask-based web application that uses facial recognition to automate student attendance tracking. The system captures student faces, trains a recognition model, and automatically marks attendance when registered students are detected.

## Features

- User Authentication System
- Student Registration with Face Detection
- Automatic Attendance Marking using Face Recognition
- Manual Attendance Entry Option
- Real-time Video Feed for Face Detection
- Attendance Records Viewing and Management
- Model Training Capability

## Tech Stack

- **Backend**: Flask (Python)
- **Database**: SQLite3
- **Face Recognition**: OpenCV (cv2)
- **Frontend**: HTML, CSS
- **Authentication**: Flask-Login

## Project Structure
```
AMS/
├── app/
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css
│   │   ├── faces/          # Stores captured face images
│   │   └── trainer/        # Stores trained model
│   │       └── trainner.yml
│   ├── templates/         # HTML templates
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── login.html
│   │   ├── register_student.html
│   │   ├── take_attendance.html
│   │   └── view_attendance.html
│   ├── __init__.py        # Flask app initialization
│   ├── models.py          # Database models
│   └── routes.py          # Application routes
├── instance/
│   └── attendance.db      # SQLite database file
├── config.py             # Configuration settings
└── run.py               # Application entry point
```

## Setup and Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/face-recognition-ams.git
cd face-recognition-ams
```

2. Create a virtual environment and activate it:
```bash
python -m venv myenv
source myenv/bin/activate  # On Windows: myenv\Scripts\activate
```

3. Install required packages:
```bash
pip install flask flask-sqlalchemy flask-login opencv-python numpy werkzeug
```

4. Initialize the database:
```bash
python
>>> from app import create_app, db
>>> app = create_app()
>>> with app.app_context():
...     db.create_all()
```

5. Run the application:
```bash
python run.py
```

## Database Structure

The application uses SQLite3 as its database, stored in `instance/attendance.db`. The database schema includes:

### Users Table
- `id`: Primary Key
- `username`: Unique username
- `password_hash`: Hashed password
- `is_admin`: Boolean for admin status

### Students Table
- `id`: Primary Key
- `enrollment`: Unique enrollment number
- `name`: Student name
- `created_at`: Timestamp
- `face_encodings`: JSON string of face encoding data

### Attendance Table
- `id`: Primary Key
- `student_id`: Foreign Key to Students
- `subject`: Subject name
- `date`: Attendance date
- `time`: Attendance time
- `created_at`: Timestamp
- `marked_by`: Foreign Key to Users

## Usage

1. **Register an Account**: Create a user account through the signup page
2. **Register Students**: Add students with their enrollment numbers and capture their faces
3. **Train Model**: Train the recognition model with captured face data
4. **Take Attendance**: Start the attendance session and let the system automatically detect and mark attendance
5. **View Records**: Check attendance records through the viewing interface

## Environment Variables

The application uses the following environment variables (optional):
- `SECRET_KEY`: Flask secret key (defaults to a predefined key)
- `DATABASE_URL`: SQLite database URL (defaults to `sqlite:///attendance.db`)


## Acknowledgments

- OpenCV for face detection and recognition capabilities
- Flask team for the amazing web framework
- SQLAlchemy team for the ORM
