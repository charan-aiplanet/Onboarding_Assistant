import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, timedelta
import os
import json
import uuid
import re
from pathlib import Path
import sqlite3
import base64
from io import BytesIO
from fpdf import FPDF

# Set page configuration
st.set_page_config(
    page_title="AI Planet Onboarding Agent",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Define paths for data storage
DATA_DIR = Path("data")
TEMPLATES_DIR = DATA_DIR / "templates"
EMPLOYEES_DIR = DATA_DIR / "employees"
FEEDBACK_DIR = DATA_DIR / "feedback"
DOCUMENTS_DIR = DATA_DIR / "documents"

# Create directories if they don't exist
for directory in [DATA_DIR, TEMPLATES_DIR, EMPLOYEES_DIR, FEEDBACK_DIR, DOCUMENTS_DIR]:
    directory.mkdir(exist_ok=True, parents=True)

# Initialize SQLite database
DB_PATH = DATA_DIR / "aiplanet.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Create employees table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS employees (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        address TEXT,
        position TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT,
        employment_type TEXT NOT NULL,
        location TEXT,
        annual_salary TEXT,
        bonus_details TEXT,
        equity_details TEXT,
        benefits TEXT,
        contingencies TEXT,
        hr_name TEXT,
        offer_sent BOOLEAN DEFAULT 0,
        offer_sent_date TEXT,
        offer_accepted BOOLEAN DEFAULT 0,
        onboarding_completed BOOLEAN DEFAULT 0,
        company_email TEXT,
        initial_password TEXT,
        reporting_manager TEXT,
        manager_email TEXT,
        buddy_name TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    ''')
    
    # Create feedback table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS feedback (
        id TEXT PRIMARY KEY,
        employee_id TEXT,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        role TEXT,
        overall_rating INTEGER,
        documentation_rating INTEGER,
        communication_rating INTEGER,
        support_rating INTEGER,
        training_rating INTEGER,
        tools_rating INTEGER,
        comments TEXT,
        suggestions TEXT,
        timestamp TEXT,
        FOREIGN KEY (employee_id) REFERENCES employees (id)
    )
    ''')
    
    # Create documents table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        role TEXT,
        file_path TEXT NOT NULL,
        uploaded_by TEXT,
        upload_date TEXT
    )
    ''')
    
    conn.commit()
    conn.close()

# Initialize the database if it doesn't exist
init_db()

# Sample company data
COMPANY_INFO = {
    "name": "AI Planet",
    "address": "CIE IIIT Hyderabad, Vindhya C4, IIIT-H Campus, Gachibowli, Telangana 500032",
    "website": "www.aiplanet.com",
    "logo_path": "assets/logo.png",
    "mission": "Revolutionizing industries through cutting-edge AI solutions",
    "vision": "To be the global leader in enterprise AI implementation and innovation",
    "legal_name": "DPhi Tech Private Limited"
}

# Initialize session state variables
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'page' not in st.session_state:
    st.session_state.page = "Dashboard"
if 'onboarding_mode' not in st.session_state:
    st.session_state.onboarding_mode = False
if 'selected_employee' not in st.session_state:
    st.session_state.selected_employee = None

# Sample roles and their documentation requirements
ROLES = {
    "Full Stack Developer": {
        "description": "Develop and maintain both frontend and backend components of our applications",
        "skills_required": ["JavaScript", "Python", "React", "Node.js", "MongoDB", "AWS"],
        "onboarding_docs": ["tech_stack.pdf", "coding_standards.pdf", "git_workflow.pdf"],
        "training_modules": ["Frontend Development", "Backend Architecture", "DevOps Basics"]
    },
    "Business Analyst": {
        "description": "Analyze business requirements and translate them into technical specifications",
        "skills_required": ["Data Analysis", "SQL", "Requirements Gathering", "Agile Methodologies"],
        "onboarding_docs": ["business_processes.pdf", "requirement_templates.pdf", "data_analysis_tools.pdf"],
        "training_modules": ["Business Requirements Analysis", "Stakeholder Management", "Agile Project Management"]
    },
    "Data Scientist": {
        "description": "Build and deploy machine learning models to solve complex business problems",
        "skills_required": ["Python", "Machine Learning", "Statistics", "Data Visualization"],
        "onboarding_docs": ["ml_pipelines.pdf", "data_governance.pdf", "model_deployment.pdf"],
        "training_modules": ["Machine Learning Fundamentals", "Model Evaluation", "Production ML Systems"]
    },
    "Product Manager": {
        "description": "Define product vision and roadmap, and work with cross-functional teams to deliver products",
        "skills_required": ["Product Strategy", "Market Research", "User Experience", "Agile/Scrum"],
        "onboarding_docs": ["product_lifecycle.pdf", "roadmap_planning.pdf", "user_research.pdf"],
        "training_modules": ["Product Strategy", "User Research", "Agile Product Management"]
    }
}

# Template for offer letter email
OFFER_EMAIL_TEMPLATE = """
Hi {Full_Name},

I am delighted to welcome you to AI Planet as a {Position} and we'd like to extend you an offer to join us. Congratulations!

We are confident that you would play a significant role in driving the vision of AI Planet forward and we look forward to having you onboard for what promises to be a rewarding journey.

The details of your offer letter in the attached PDF. Please go through the same and feel free to ask if there are any questions.

If all is in order, please sign on all 3 pages of the offer letter (including the last page), and send a scanned copy back as your acceptance latest by {Start_Date}. Also, please check the details such as address or any other relevant details.

I look forward to you joining the team and taking AI Planet to newer heights. If you have any questions, please don't hesitate to reach out to us.

Best regards,
{HR_Name}
"""

# Template for onboarding email
ONBOARDING_EMAIL_TEMPLATE = """
Dear {employee_name},

Welcome to AI Planet! We're thrilled to have you join our team.

Here's everything you need to know for your first day:

🗓️ Start Date: {start_date}
🕒 Time: 9:30 AM
📍 Location: {location}
👤 Your Manager: {manager_name} ({manager_email})

Access Details:
- Company Email: {company_email}
- Initial Password: {initial_password}
- IT Support: itsupport@aiplanet.com

Please bring the following documents:
- Government-issued ID
- Completed tax forms (sent separately)
- Direct deposit information

Your onboarding buddy, {buddy_name}, will meet you at reception.

Attached are some company resources to help you get started:
- Company Handbook
- {role_specific_docs}

We're looking forward to having you on the team!

Best regards,
HR Team
AI Planet
"""

# Function to validate email format
def is_valid_email(email):
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None

# Database functions
def get_employees():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM employees")
    rows = cur.fetchall()
    conn.close()
    
    # Convert to list of dicts
    return [dict(row) for row in rows]

def get_employee_by_id(employee_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM employees WHERE id = ?", (employee_id,))
    row = cur.fetchone()
    conn.close()
    
    return dict(row) if row else None

def save_employee(employee_data):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Check if employee exists
    cur.execute("SELECT id FROM employees WHERE id = ?", (employee_data["id"],))
    exists = cur.fetchone()
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if not exists:
        # Insert new employee
        employee_data["created_at"] = now
        employee_data["updated_at"] = now
        
        # Create columns and values list
        columns = list(employee_data.keys())
        placeholders = ["?"] * len(columns)
        values = [employee_data[col] for col in columns]
        
        query = f"INSERT INTO employees ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
        cur.execute(query, values)
    else:
        # Update existing employee
        employee_data["updated_at"] = now
        
        # Create set clause and values list
        set_items = [f"{col} = ?" for col in employee_data.keys() if col != "id"]
        values = [employee_data[col] for col in employee_data.keys() if col != "id"]
        values.append(employee_data["id"])  # for WHERE clause
        
        query = f"UPDATE employees SET {', '.join(set_items)} WHERE id = ?"
        cur.execute(query, values)
    
    conn.commit()
    conn.close()

def get_feedback():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM feedback")
    rows = cur.fetchall()
    conn.close()
    
    # Convert to list of dicts
    return [dict(row) for row in rows]

def save_feedback(feedback_data):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Insert new feedback
    columns = list(feedback_data.keys())
    placeholders = ["?"] * len(columns)
    values = [feedback_data[col] for col in columns]
    
    query = f"INSERT INTO feedback ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
    cur.execute(query, values)
    
    conn.commit()
    conn.close()

def get_documents(category=None, role=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    if category and role:
        cur.execute("SELECT * FROM documents WHERE category = ? AND role = ?", (category, role))
    elif category:
        cur.execute("SELECT * FROM documents WHERE category = ?", (category,))
    else:
        cur.execute("SELECT * FROM documents")
    
    rows = cur.fetchall()
    conn.close()
    
    # Convert to list of dicts
    return [dict(row) for row in rows]

def save_document(document_data):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Insert new document
    columns = list(document_data.keys())
    placeholders = ["?"] * len(columns)
    values = [document_data[col] for col in columns]
    
    query = f"INSERT INTO documents ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
    cur.execute(query, values)
    
    conn.commit()
    conn.close()

# PDF generation function
def generate_pdf_offer_letter(candidate_data):
    # Create a PDF object
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Set the font and colors
    pdf.set_font('Arial', '', 12)
    pdf.set_text_color(0, 0, 0)
    
    # Add company logo (if available)
    # pdf.image('assets/logo.png', x=160, y=10, w=30)
    
    # Add title
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 20, 'Offer letter with AI Planet', 0, 1, 'C')
    
    # Add date
    pdf.set_font('Arial', '', 12)
    today = datetime.now().strftime("%d %B %Y")
    pdf.cell(0, 10, f'Date: {today}', 0, 1, 'L')
    
    # Add candidate name and address
    pdf.ln(10)
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(0, 0, 150)  # Blue color
    pdf.cell(0, 10, candidate_data["name"], 0, 1, 'L')
    
    pdf.set_font('Arial', '', 12)
    pdf.set_text_color(0, 0, 0)  # Black color
    pdf.cell(0, 10, 'Address:', 0, 1, 'L')
    pdf.cell(0, 10, 'Email:', 0, 1, 'L')
    pdf.cell(0, 10, 'Phone no:', 0, 1, 'L')
    
    # Letter content
    pdf.ln(10)
    pdf.cell(0, 10, f'Dear {candidate_data["name"].split()[0]},', 0, 1, 'L')
    
    pdf.ln(5)
    pdf.set_font('Arial', '', 12)
    pdf.multi_cell(0, 6, f'I am delighted & excited to welcome you to AI Planet as a {candidate_data["position"]}. At AI Planet, we believe that our team is our biggest strength and we are looking forward to strengthening it further with your addition. We are confident that you would play a significant role in the overall success of the community that we envision to build and wish you the most enjoyable, learning packed and truly meaningful experience with AI Planet.')
    
    pdf.ln(5)
    pdf.multi_cell(0, 6, 'Your appointment will be governed by the terms and conditions presented in Annexure A.')
    
    pdf.ln(5)
    pdf.multi_cell(0, 6, 'We look forward to you joining us. Please do not hesitate to call us for any information you may need. Also, please sign the duplicate of this offer as your acceptance and forward the same to us.')
    
    pdf.ln(5)
    pdf.cell(0, 10, 'Congratulations!', 0, 1, 'L')
    
    pdf.ln(15)
    pdf.cell(0, 10, candidate_data["hr_name"], 0, 1, 'L')
    pdf.cell(0, 6, 'Founder, AI Planet (DPhi)', 0, 1, 'L')
    
    # Company footer
    pdf.ln(10)
    pdf.set_font('Arial', '', 9)
    pdf.multi_cell(0, 5, f'{COMPANY_INFO["legal_name"]} | {COMPANY_INFO["address"]}')
    
    # Annexure A - Page 2
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 20, 'Offer letter with AI Planet', 0, 1, 'C')
    
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(0, 0, 150)  # Blue color
    pdf.cell(0, 15, 'Annexure A', 0, 1, 'L')
    
    pdf.set_font('Arial', '', 12)
    pdf.set_text_color(0, 0, 0)  # Black color
    pdf.multi_cell(0, 6, 'You shall be governed by the following terms and conditions of service during your engagement with AI Planet, and those may be amended from time to time.')
    
    pdf.ln(5)
    # Numbered points
    points = [
        f'You will be working with AI Planet as a {candidate_data["position"]}. You would be responsible for aspects related to conducting market research to identify trends and AI use cases, support the sales team by qualifying leads, preparing tailored presentations, and building strong customer relationships. Additionally, you will be playing an important role in realizing the design, planning, development, and deployment platforms/solutions. Further, it may also require you to do various roles and go that extra mile in the best interest of the product.',
        f'Your date of joining is {candidate_data["start_date"]}. During your employment, we expected to devote your time and efforts solely to AI Planet work. You are also required to let your mentor know about forthcoming events (if there are any) in advance so that your work can be planned accordingly.',
        f'You will be working onsite in our Hyderabad office on all working days. There will be catch ups scheduled with your mentor to discuss work progress and overall work experience at regular intervals.',
        f'All the work that you will produce at or in relation to AI Planet will be the intellectual property of AI Planet. You are not allowed to store, copy, sell, share, and distribute it to a third party under any circumstances. Similarly, you are expected to refrain from talking about your work in public domains (both online such as blogging, social networking sites and offline among your friends, college etc.) without prior discussion and approval with your mentor.',
        f'We take data privacy and security very seriously and to maintain confidentiality of any students, customers, clients, and companies\' data and contact details that you may get access to during your engagement will be your responsibility. AI Planet operates on zero tolerance principle with regards to any breach of data security guidelines. At the completion of the engagement, you are expected to hand over all AI Planet work/data stored on your Personal Computer to your mentor and delete the same from your machine.',
        f'Under normal circumstances either the company or you may terminate this association by providing a notice of 30 days without assigning any reason. However, the company may terminate this agreement forthwith under situations of in-disciplinary behaviors.',
        f'During the appointment period you shall not engage yourselves directly or indirectly or in any capacity in any other organization (other than your college).'
    ]
    
    
    for i, point in enumerate(points, 1):
        if i > 4:  # Add remaining points to page 3
            break
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(8, 6, f'{i}.', 0, 0)
        pdf.set_font('Arial', '', 12)
        x = pdf.get_x()
        y = pdf.get_y()
        pdf.multi_cell(180, 6, point)
        pdf.ln(5)
    
    # Company footer
    pdf.ln(10)
    pdf.set_font('Arial', '', 9)
    pdf.multi_cell(0, 5, f'{COMPANY_INFO["legal_name"]} | {COMPANY_INFO["address"]}')
    
    # Page 3 with remaining points
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 20, 'Offer letter with AI Planet', 0, 1, 'C')
    
    # Continue with remaining points
    for i, point in enumerate(points[4:], 5):
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(8, 6, f'{i}.', 0, 0)
        pdf.set_font('Arial', '', 12)
        x = pdf.get_x()
        y = pdf.get_y()
        pdf.multi_cell(180, 6, point)
        pdf.ln(5)
    
    # Additional points
    extra_points = [
        f'You are expected to conduct yourself with utmost professionalism in dealing with your mentor, team members, colleagues, clients and customers and treat everyone with due respect.',
        f'AI Planet is a start-up and we love people who like to go beyond the normal call of duty and can think out of the box. Surprise us with your passion, intelligence, creativity, and hard work – and expect appreciation & rewards to follow.',
        f'Expect constant and continuous objective feedback from your mentor and other team members and we encourage you to ask for and provide feedback at every possible opportunity. It is your right to receive and give feedback – this is the ONLY way we all can continuously push ourselves to do better.',
        f'Have fun at what you do and do the right thing – both the principles are core of what AI Planet stands for and we expect you to imbibe them in your day to day actions and continuously challenge us if we are falling short of expectations on either of them.',
        f'You will be provided INR {candidate_data["annual_salary"]} /- per month as a salary. Post three months you will be considered for ESOPs. ESOPs are based on a four-year vesting schedule with a one-year cliff.'
    ]
    
    for i, point in enumerate(extra_points, len(points) + 1):
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(8, 6, f'{i}.', 0, 0)
        pdf.set_font('Arial', '', 12)
        x = pdf.get_x()
        y = pdf.get_y()
        pdf.multi_cell(180, 6, point)
        pdf.ln(5)
    
    # Signature section
    pdf.ln(5)
    pdf.set_font('Arial', '', 12)
    pdf.multi_cell(0, 6, 'I have negotiated, agreed, read and understood all the terms and conditions of this engagement letter as well as Annexure hereto and affix my signature in complete acceptance of the terms of the letter.')
    
    pdf.ln(10)
    pdf.cell(50, 10, 'Date: ________________', 0, 0, 'L')
    pdf.cell(0, 10, 'Signature: ________________', 0, 1, 'L')
    
    pdf.ln(5)
    pdf.cell(50, 10, 'Place: ________________', 0, 0, 'L')
    pdf.cell(0, 10, 'Name: ________________', 0, 1, 'L')
    
    # Company footer
    pdf.ln(10)
    pdf.set_font('Arial', '', 9)
    pdf.multi_cell(0, 5, f'{COMPANY_INFO["legal_name"]} | {COMPANY_INFO["address"]}')
    
    # Return PDF as base64 string
    return base64.b64encode(pdf.output(dest='S').encode('latin1')).decode('utf-8')

# Send email (mock function)
def send_email(to_email, subject, content, attachments=None, pdf_content=None, sender_name=None):
    st.success(f"Email would be sent to {to_email} with subject: {subject}")
    st.info("Email content:")
    st.markdown(content)
    
    if pdf_content:
        st.info("Offer letter PDF would be attached to the email.")
        
        # Display PDF preview
        pdf_display = f'<iframe src="data:application/pdf;base64,{pdf_content}" width="100%" height="600" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
    
    if attachments:
        st.info(f"Attachments: {', '.join(attachments)}")
    
    # In a real application, you would use SMTP to send the email
    # Example code (commented out):
    """
    msg = MIMEMultipart()
    msg['From'] = 'hr@aiplanet.com' if not sender_name else f"{sender_name} <hr@aiplanet.com>"
    msg['To'] = to_email
    msg['Subject'] = subject
    
    msg.attach(MIMEText(content, 'html'))
    
    if pdf_content:
        attachment = MIMEApplication(base64.b64decode(pdf_content))
        attachment['Content-Disposition'] = 'attachment; filename="AI_Planet_Offer_Letter.pdf"'
        msg.attach(attachment)
    
    if attachments:
        for attachment in attachments:
            with open(attachment, 'rb') as file:
                part = MIMEApplication(file.read(), Name=os.path.basename(attachment))
                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment)}"'
                msg.attach(part)
    
    with smtplib.SMTP('smtp.example.com', 587) as server:
        server.starttls()
        server.login('hr@aiplanet.com', 'password')
        server.send_message(msg)
    """
    
    return True

# Store feedback and adapt the system
def collect_feedback(feedback_data):
    feedback_data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    feedback_data["id"] = str(uuid.uuid4())
    save_feedback(feedback_data)
    
    # In a real agent, this would feed into a learning loop
    st.success("Feedback collected and will be used to improve the onboarding process")
    return True

# Custom CSS
def load_css():
    st.markdown("""
    <style>
        .main {
            background-color: #f8f9fa;
        }
        .stApp {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1, h2, h3 {
            color: #2E5090;
        }
        .stButton>button {
            background-color: #2E5090;
            color: white;
            border-radius: 5px;
            padding: 0.5rem 1rem;
            font-weight: bold;
        }
        .stButton>button:hover {
            background-color: #1A365D;
        }
        .success-box {
            background-color: #d4edda;
            color: #155724;
            padding: 1rem;
            border-radius: 5px;
            margin-bottom: 1rem;
        }
        .info-box {
            background-color: #d1ecf1;
            color: #0c5460;
            padding: 1rem;
            border-radius: 5px;
            margin-bottom: 1rem;
        }
        .sidebar .sidebar-content {
            background-color: #2E5090;
            color: white;
        }
        .card {
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            background-color: white;
            margin-bottom: 20px;
        }
        .action-card {
            cursor: pointer;
            transition: transform 0.3s ease;
        }
        .action-card:hover {
            transform: translateY(-5px);
        }
    </style>
    """, unsafe_allow_html=True)

# Authentication
def authenticate():
    with st.sidebar:
        st.title("🚀 AI Planet")
        st.subheader("Onboarding Agent")
        
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.button("Login"):
            # Mock authentication - in a real app, check against a database
            if username == "admin" and password == "admin":
                st.session_state.authenticated = True
                st.session_state.user_role = "HR"
                st.success("Login successful!")
            elif username == "manager" and password == "manager":
                st.session_state.authenticated = True
                st.session_state.user_role = "Manager"
                st.success("Login successful!")
            else:
                st.error("Invalid credentials")
        
        if st.session_state.authenticated:
            st.success(f"Logged in as {st.session_state.user_role}")
            if st.button("Logout"):
                st.session_state.authenticated = False
                st.session_state.user_role = None
                st.rerun()

# Main application
# The error is happening in the main() function where there's a reference to col2 without it being defined first
# Looking at line 666 in your code, this is likely in a section where columns are being created

# Here's how to fix it - look for this pattern in your main() function:

def main():
    load_css()
    authenticate()
    
    if not st.session_state.authenticated:
        st.title("Welcome to AI Planet Onboarding Agent")
        st.markdown("""
        <div class="card">
            <h2>Streamline your onboarding process</h2>
            <p>Our AI-powered onboarding agent helps you:</p>
            <ul>
                <li>Generate customized offer letters</li>
                <li>Send automated onboarding emails</li>
                <li>Provide role-specific documentation</li>
                <li>Track onboarding progress</li>
            </ul>
            <p>Please log in to access the system.</p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    # Sidebar navigation
    with st.sidebar:
        st.title("Navigation")
        nav_selection = st.radio("Go to", [
            "Dashboard", 
            "Offer Letter Generator", 
            "Onboarding Management", 
            "Documentation Library",
            "Feedback System",
            "Settings"
        ])
        
        # Update the page in session state when navigation changes
        if nav_selection != st.session_state.page:
            st.session_state.page = nav_selection
            # Reset any page-specific session state here if needed
            if nav_selection != "Onboarding Management":
                st.session_state.onboarding_mode = False
                st.session_state.selected_employee = None
    
    # Display the selected page
    if st.session_state.page == "Dashboard":
        display_dashboard()
    elif st.session_state.page == "Offer Letter Generator":
        offer_letter_generator()
    elif st.session_state.page == "Onboarding Management":
        onboarding_management()
    elif st.session_state.page == "Documentation Library":
        documentation_library()
    elif st.session_state.page == "Feedback System":
        feedback_system()
    elif st.session_state.page == "Settings":
        settings_page()

# Offer letter generator page
def offer_letter_generator():
    st.title("Offer Letter Generator")
    
    st.markdown("""
    <div class="card">
        <p>Create customized offer letters for new employees. Fill in the form below with the candidate's information.</p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.form("offer_letter_form"):
        st.subheader("Candidate Information")
        
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("Full Name")
            email = st.text_input("Email Address")
            position = st.selectbox("Position", list(ROLES.keys()))
            start_date = st.date_input("Start Date", min_value=datetime.now().date())
            location = st.text_input("Work Location", "AI Planet HQ, Hyderabad")
        
        with col2:
            address = st.text_area("Address")
            employment_type = st.selectbox("Employment Type", ["Full-time", "Intern", "Contract"])
            
            # If contract, show end date
            if employment_type == "Contract":
                contract_months = st.number_input("Contract Duration (months)", min_value=1, value=6)
                end_date = (start_date + timedelta(days=30*contract_months)).strftime("%B %d, %Y")
            else:
                end_date = None
                
            annual_salary = st.number_input("Monthly Salary (₹)", min_value=0, value=37500)
            reporting_manager = st.text_input("Reporting Manager")
        
        st.subheader("Additional Details")
        
        col1, col2 = st.columns(2)
        
        with col1:
            bonus_details = st.text_area("Bonus Details", "Performance-based annual bonus based on company performance")
            equity_details = st.text_area("Equity Details", "ESOPs based on a four-year vesting schedule with a one-year cliff")
        
        with col2:
            benefits = st.text_area("Benefits", "Health insurance; flexible work hours; remote work options")
            contingencies = st.text_area("Contingencies", "successful background check and reference verification")
        
        hr_name = st.text_input("HR Representative Name", "Chanukya Patnaik")
        
        submitted = st.form_submit_button("Generate Offer Letter")
    
    if submitted:
        if not name or not email or not address or not reporting_manager:
            st.error("Please fill in all required fields")
        elif not is_valid_email(email):
            st.error("Please enter a valid email address")
        else:
            # Generate a unique ID for the candidate
            candidate_id = str(uuid.uuid4())
            
            # Prepare candidate data
            candidate_data = {
                "id": candidate_id,
                "name": name,
                "email": email,
                "address": address,
                "position": position,
                "start_date": start_date.strftime("%B %d, %Y"),
                "end_date": end_date,
                "employment_type": employment_type,
                "location": location,
                "annual_salary": f"{annual_salary:,}",
                "bonus_details": bonus_details,
                "equity_details": equity_details,
                "benefits": benefits,
                "contingencies": contingencies,
                "hr_name": hr_name,
                "offer_sent": False,
                "offer_accepted": False,
                "onboarding_completed": False,
                "reporting_manager": reporting_manager
            }
            
            # Generate the offer letter PDF
            pdf_content = generate_pdf_offer_letter(candidate_data)
            
            # Save the candidate data
            save_employee(candidate_data)
            
            # Display success message
            st.success("Offer letter generated successfully!")
            
            # Display PDF preview
            st.subheader("Offer Letter Preview")
            pdf_display = f'<iframe src="data:application/pdf;base64,{pdf_content}" width="100%" height="500" type="application/pdf"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)
            
            # Option to send the offer letter
            if st.button("Send Offer Letter"):
                # Format email content
                email_content = OFFER_EMAIL_TEMPLATE.format(
                    Full_Name=name,
                    Position=position,
                    Start_Date=start_date.strftime("%B %d, %Y"),
                    HR_Name=hr_name
                )
                
                subject = f"Job Offer: {position} at AI Planet"
                send_email(
                    to_email=email, 
                    subject=subject, 
                    content=email_content,
                    pdf_content=pdf_content,
                    sender_name=hr_name
                )
                
                # Update the candidate data
                candidate_data["offer_sent"] = True
                candidate_data["offer_sent_date"] = datetime.now().strftime("%Y-%m-%d")
                save_employee(candidate_data)
                
                st.success(f"Offer letter sent to {email}")

def onboarding_management():
    st.title("Onboarding Management")
    
    employees = get_employees()
    
    st.markdown("""
    <div class="card">
        <p>Manage the onboarding process for new employees. Send onboarding emails, track progress, and ensure a smooth transition.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Filter options
    filter_options = ["All", "Offer Sent", "Offer Accepted", "Pending Onboarding", "Onboarding Completed"]
    filter_choice = st.selectbox("Filter by status", filter_options)
    
    # Filtered employee list
    filtered_employees = []
    
    if filter_choice == "All":
        filtered_employees = employees
    elif filter_choice == "Offer Sent":
        filtered_employees = [emp for emp in employees if emp.get("offer_sent", False)]
    elif filter_choice == "Offer Accepted":
        filtered_employees = [emp for emp in employees if emp.get("offer_accepted", False)]
    elif filter_choice == "Pending Onboarding":
        filtered_employees = [emp for emp in employees 
                            if emp.get("offer_accepted", False) and not emp.get("onboarding_completed", False)]
    elif filter_choice == "Onboarding Completed":
        filtered_employees = [emp for emp in employees if emp.get("onboarding_completed", False)]
    
    if not filtered_employees:
        st.info("No employees match the selected filter")
    else:
        # Display employee list
        for emp in filtered_employees:
            with st.expander(f"{emp['name']} - {emp['position']}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown(f"**Email:** {emp['email']}")
                    st.markdown(f"**Position:** {emp['position']}")
                    st.markdown(f"**Start Date:** {emp['start_date']}")
                    st.markdown(f"**Employment Type:** {emp['employment_type']}")
                
                with col2:
                    status = "Awaiting Offer"
                    if emp.get("onboarding_completed", False):
                        status = "Onboarding Completed"
                    elif emp.get("offer_accepted", False):
                        status = "Offer Accepted - Pending Onboarding"
                    elif emp.get("offer_sent", False):
                        status = "Offer Sent - Awaiting Response"
                    
                    st.markdown(f"**Status:** {status}")
                    
                    # Onboarding actions
                    if emp.get("offer_accepted", False) and not emp.get("onboarding_completed", False):
                        if st.button(f"Prepare Onboarding for {emp['name']}", key=f"onboard_{emp['id']}"):
                            st.session_state.selected_employee = emp['id']
                            st.session_state.onboarding_mode = True
                    
                    # Option to mark offer as accepted (for demo purposes)
                    if emp.get("offer_sent", False) and not emp.get("offer_accepted", False):
                        if st.button(f"Mark Offer as Accepted", key=f"accept_{emp['id']}"):
                            # Update employee data
                            emp["offer_accepted"] = True
                            emp["offer_accepted_date"] = datetime.now().strftime("%Y-%m-%d")
                            save_employee(emp)
                            st.success(f"Offer marked as accepted for {emp['name']}")
                            st.rerun()
    
    # Onboarding preparation form
    if hasattr(st.session_state, "onboarding_mode") and st.session_state.onboarding_mode and hasattr(st.session_state, "selected_employee"):
        emp_id = st.session_state.selected_employee
        emp_data = get_employee_by_id(emp_id)
        
        if emp_data:
            st.subheader(f"Prepare Onboarding for {emp_data['name']}")
            
            with st.form("onboarding_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    company_email = st.text_input(
                        "Company Email", 
                        value=f"{emp_data['name'].split()[0].lower()}.{emp_data['name'].split()[-1].lower()}@aiplanet.com"
                    )
                    initial_password = st.text_input("Initial Password", value="Welcome2025!")
                    manager_email = st.text_input("Manager Email")
                
                with col2:
                    buddy_name = st.text_input("Onboarding Buddy")
                    onboarding_date = st.date_input("Onboarding Date", value=datetime.strptime(emp_data['start_date'], "%B %d, %Y").date())
                    additional_notes = st.text_area("Additional Notes")
                
                submit_onboarding = st.form_submit_button("Send Onboarding Email")
                
            if submit_onboarding:
                if not company_email or not manager_email or not buddy_name:
                    st.error("Please fill in all required fields")
                elif not is_valid_email(company_email) or not is_valid_email(manager_email):
                    st.error("Please enter valid email addresses")
                else:
                    # Update employee data
                    emp_data["company_email"] = company_email
                    emp_data["initial_password"] = initial_password
                    emp_data["manager_email"] = manager_email
                    emp_data["buddy_name"] = buddy_name
                    emp_data["onboarding_date"] = onboarding_date.strftime("%B %d, %Y")
                    emp_data["additional_notes"] = additional_notes
                    
                    # Generate onboarding email
                    role_docs = ""
                    if emp_data["position"] in ROLES:
                        role_docs = ", ".join(ROLES[emp_data["position"]]["onboarding_docs"])
                    
                    onboarding_email = ONBOARDING_EMAIL_TEMPLATE.format(
                        employee_name=emp_data["name"],
                        start_date=emp_data["start_date"],
                        location=emp_data["location"],
                        manager_name=emp_data["reporting_manager"],
                        manager_email=manager_email,
                        company_email=company_email,
                        initial_password=initial_password,
                        buddy_name=buddy_name,
                        role_specific_docs=role_docs
                    )
                    
                    # Send the email
                    subject = f"Welcome to AI Planet - Onboarding Information for {emp_data['name']}"
                    attachments = []
                    if emp_data["position"] in ROLES:
                        attachments = [f"documents/{doc}" for doc in ROLES[emp_data["position"]]["onboarding_docs"]]
                    
                    send_email(emp_data["email"], subject, onboarding_email, attachments)
                    
                    # Update employee status
                    emp_data["onboarding_email_sent"] = True
                    emp_data["onboarding_email_sent_date"] = datetime.now().strftime("%Y-%m-%d")
                    save_employee(emp_data)
                    
                    st.success(f"Onboarding email sent to {emp_data['email']}")
                    
                    # Reset the onboarding mode
                    st.session_state.onboarding_mode = False
                    st.rerun()
        else:
            st.error("Employee not found")
            st.session_state.onboarding_mode = False
                
def documentation_library():
    st.title("Documentation Library")
    
    st.markdown("""
    <div class="card">
        <p>Manage and organize onboarding documents for different roles. Upload new documents or modify existing ones to ensure new employees have access to the most up-to-date information.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Document categories
    categories = ["Company-wide", "Role-specific", "Training Materials", "Policies and Procedures"]
    selected_category = st.selectbox("Select Category", categories)
    
    if selected_category == "Role-specific":
        role = st.selectbox("Select Role", list(ROLES.keys()))
        
        st.subheader(f"Documents for {role}")
        
        if role in ROLES:
            st.markdown("### Required Onboarding Documents")
            for doc in ROLES[role]["onboarding_docs"]:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.markdown(f"**{doc}**")
                with col2:
                    st.button("View", key=f"view_{doc}_{role}")
                with col3:
                    st.button("Update", key=f"update_{doc}_{role}")
            
            st.markdown("### Training Modules")
            for module in ROLES[role]["training_modules"]:
                st.markdown(f"- {module}")
            
            # Upload new document option
            st.subheader("Upload New Document")
            uploaded_file = st.file_uploader("Choose a file", type=["pdf", "docx", "pptx"])
            doc_name = st.text_input("Document Name")
            
            if uploaded_file is not None and doc_name:
                if st.button("Upload Document"):
                    # In a real application, save the file to storage
                    file_path = f"documents/{doc_name}"
                    
                    # Create document record
                    document_data = {
                        "id": str(uuid.uuid4()),
                        "name": doc_name,
                        "category": "Role-specific",
                        "role": role,
                        "file_path": file_path,
                        "uploaded_by": st.session_state.user_role,
                        "upload_date": datetime.now().strftime("%Y-%m-%d")
                    }
                    
                    # Save document data
                    save_document(document_data)
                    
                    # Update role documentation
                    ROLES[role]["onboarding_docs"].append(doc_name)
                    
                    st.success(f"Document {doc_name} uploaded for {role}")
                    st.rerun()
    
    elif selected_category == "Company-wide":
        st.subheader("Company-wide Documents")
        
        company_docs = [
            "Employee Handbook.pdf",
            "Company Policies.pdf",
            "Benefits Overview.pdf",
            "IT Security Guidelines.pdf",
            "Code of Conduct.pdf"
        ]
        
        for doc in company_docs:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.markdown(f"**{doc}**")
            with col2:
                st.button("View", key=f"view_{doc}")
            with col3:
                st.button("Update", key=f"update_{doc}")
        
        # Upload new document option
        st.subheader("Upload New Document")
        uploaded_file = st.file_uploader("Choose a file", type=["pdf", "docx", "pptx"])
        doc_name = st.text_input("Document Name")
        
        if uploaded_file is not None and doc_name:
            if st.button("Upload Document"):
                # In a real application, save the file to storage
                file_path = f"documents/{doc_name}"
                
                # Create document record
                document_data = {
                    "id": str(uuid.uuid4()),
                    "name": doc_name,
                    "category": "Company-wide",
                    "role": None,
                    "file_path": file_path,
                    "uploaded_by": st.session_state.user_role,
                    "upload_date": datetime.now().strftime("%Y-%m-%d")
                }
                
                # Save document data
                save_document(document_data)
                
                st.success(f"Document {doc_name} uploaded to company-wide documents")
                company_docs.append(doc_name)
                st.rerun()
    
    elif selected_category == "Training Materials":
        st.subheader("Training Materials")
        
        training_materials = [
            "New Employee Orientation.pptx",
            "Company Product Overview.pdf",
            "Team Collaboration Tools.pdf",
            "Company Values Workshop.pdf"
        ]
        
        for material in training_materials:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.markdown(f"**{material}**")
            with col2:
                st.button("View", key=f"view_{material}")
            with col3:
                st.button("Update", key=f"update_{material}")
        
        # Upload new training material option
        st.subheader("Upload New Training Material")
        uploaded_file = st.file_uploader("Choose a file", type=["pdf", "docx", "pptx"])
        material_name = st.text_input("Material Name")
        
        if uploaded_file is not None and material_name:
            if st.button("Upload Material"):
                # In a real application, save the file to storage
                file_path = f"documents/{material_name}"
                
                # Create document record
                document_data = {
                    "id": str(uuid.uuid4()),
                    "name": material_name,
                    "category": "Training Materials",
                    "role": None,
                    "file_path": file_path,
                    "uploaded_by": st.session_state.user_role,
                    "upload_date": datetime.now().strftime("%Y-%m-%d")
                }
                
                # Save document data
                save_document(document_data)
                
                st.success(f"Training material {material_name} uploaded")
                training_materials.append(material_name)
                st.rerun()
    
    elif selected_category == "Policies and Procedures":
        st.subheader("Policies and Procedures")
        
        policies = [
            "Remote Work Policy.pdf",
            "Expense Reimbursement Procedure.pdf",
            "Leave Policy.pdf",
            "Performance Review Process.pdf",
            "IT Equipment Policy.pdf"
        ]
        
        for policy in policies:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.markdown(f"**{policy}**")
            with col2:
                st.button("View", key=f"view_{policy}")
            with col3:
                st.button("Update", key=f"update_{policy}")
        
        # Upload new policy option
        st.subheader("Upload New Policy")
        uploaded_file = st.file_uploader("Choose a file", type=["pdf", "docx"])
        policy_name = st.text_input("Policy Name")
        
        if uploaded_file is not None and policy_name:
            if st.button("Upload Policy"):
                # In a real application, save the file to storage
                file_path = f"documents/{policy_name}"
                
                # Create document record
                document_data = {
                    "id": str(uuid.uuid4()),
                    "name": policy_name,
                    "category": "Policies and Procedures",
                    "role": None,
                    "file_path": file_path,
                    "uploaded_by": st.session_state.user_role,
                    "upload_date": datetime.now().strftime("%Y-%m-%d")
                }
                
                # Save document data
                save_document(document_data)
                
                st.success(f"Policy {policy_name} uploaded")
                policies.append(policy_name)
                st.rerun()

def feedback_system():
    st.title("Feedback System")
    
    st.markdown("""
    <div class="card">
        <p>Collect feedback from new employees about their onboarding experience. This feedback helps improve the onboarding process through our agentic learning loop.</p>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Collect Feedback", "View Feedback"])
    
    with tab1:
        st.subheader("Collect Onboarding Feedback")
        
        with st.form("feedback_form"):
            employee_name = st.text_input("Employee Name")
            employee_email = st.text_input("Employee Email")
            role = st.selectbox("Role", list(ROLES.keys()))
            
            st.markdown("### Rate your onboarding experience")
            
            col1, col2 = st.columns(2)
            
            with col1:
                overall_rating = st.slider("Overall Experience", 1, 5, 3)
                documentation_rating = st.slider("Documentation Quality", 1, 5, 3)
                communication_rating = st.slider("Communication", 1, 5, 3)
            
            with col2:
                support_rating = st.slider("Support from Team/Manager", 1, 5, 3)
                training_rating = st.slider("Training Quality", 1, 5, 3)
                tools_rating = st.slider("Access to Tools and Resources", 1, 5, 3)
            
            feedback_comments = st.text_area("Additional Comments", height=150)
            suggestions = st.text_area("Suggestions for Improvement", height=150)
            
            submit_feedback = st.form_submit_button("Submit Feedback")
        
        if submit_feedback:
            if not employee_name or not employee_email:
                st.error("Please fill in your name and email")
            elif not is_valid_email(employee_email):
                st.error("Please enter a valid email address")
            else:
                # Find employee ID if exists
                employees = get_employees()
                employee_id = None
                for emp in employees:
                    if emp['email'] == employee_email:
                        employee_id = emp['id']
                        break
                
                # Prepare feedback data
                feedback_data = {
                    "id": str(uuid.uuid4()),
                    "employee_id": employee_id,
                    "name": employee_name,
                    "email": employee_email,
                    "role": role,
                    "overall_rating": overall_rating,
                    "documentation_rating": documentation_rating,
                    "communication_rating": communication_rating,
                    "support_rating": support_rating,
                    "training_rating": training_rating,
                    "tools_rating": tools_rating,
                    "comments": feedback_comments,
                    "suggestions": suggestions,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                # Store the feedback
                save_feedback(feedback_data)
                
                st.success("Thank you for your feedback! Your input helps us improve our onboarding process.")
    
    with tab2:
        if st.session_state.user_role != "HR":
            st.warning("Only HR personnel can view feedback data")
        else:
            st.subheader("Onboarding Feedback Data")
            
            feedback_data = get_feedback()
            
            if not feedback_data:
                st.info("No feedback has been collected yet")
            else:
                # Calculate average ratings
                avg_ratings = {"overall": 0, "documentation": 0, "communication": 0, 
                              "support": 0, "training": 0, "tools": 0}
                
                for feedback in feedback_data:
                    for key in avg_ratings:
                        field_name = f"{key}_rating"
                        if field_name in feedback and feedback[field_name]:
                            avg_ratings[key] += feedback[field_name]
                
                for key in avg_ratings:
                    avg_ratings[key] /= len(feedback_data) if len(feedback_data) > 0 else 1
                
                # Display average ratings
                st.markdown("### Average Ratings")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Overall Experience", f"{avg_ratings['overall']:.1f}/5")
                    st.metric("Documentation", f"{avg_ratings['documentation']:.1f}/5")
                
                with col2:
                    st.metric("Communication", f"{avg_ratings['communication']:.1f}/5")
                    st.metric("Support", f"{avg_ratings['support']:.1f}/5")
                
                with col3:
                    st.metric("Training", f"{avg_ratings['training']:.1f}/5")
                    st.metric("Tools & Resources", f"{avg_ratings['tools']:.1f}/5")
                
                # Display individual feedback
                st.markdown("### Individual Feedback")
                
                for feedback in feedback_data:
                    with st.expander(f"{feedback['name']} - {feedback['role']}"):
                        st.markdown(f"**Date:** {feedback.get('timestamp', 'N/A')}")
                        st.markdown(f"**Email:** {feedback['email']}")
                        st.markdown(f"**Role:** {feedback['role']}")
                        
                        st.markdown("**Ratings:**")
                        ratings_fields = ['overall_rating', 'documentation_rating', 'communication_rating', 'support_rating', 'training_rating', 'tools_rating']
                        for field in ratings_fields:
                            if field in feedback and feedback[field]:
                                display_name = field.replace('_rating', '').capitalize()
                                st.markdown(f"- {display_name}: {feedback[field]}/5")
                        
                        if feedback.get("comments"):
                            st.markdown(f"**Comments:** {feedback['comments']}")
                        
                        if feedback.get("suggestions"):
                            st.markdown(f"**Suggestions:** {feedback['suggestions']}")
                
                # Learning insights (this would be generated by the AI in a real agent)
                st.subheader("Learning Insights")
                
                st.markdown("""
                <div class="card">
                    <h4>Key Improvement Areas</h4>
                    <ul>
                        <li>Documentation could be more comprehensive for technical roles</li>
                        <li>More personalized training for specific roles</li>
                        <li>Faster access provisioning for development tools</li>
                    </ul>
                    
                    <h4>Recommended Actions</h4>
                    <ul>
                        <li>Update technical documentation for Full Stack Developer role</li>
                        <li>Create role-specific welcome videos</li>
                        <li>Automate access provisioning for common tools</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)

def settings_page():
    st.title("Settings")
    
    if st.session_state.user_role != "HR":
        st.warning("Only HR personnel can access settings")
        pass  # Replace with appropriate logic if needed
    
    st.markdown("""
    <div class="card">
        <p>Configure system settings, manage templates, and customize the onboarding process.</p>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["Email Templates", "Role Management", "System Configuration"])
    
    with tab1:
        st.subheader("Email Templates")
        
        template_type = st.selectbox("Select Template", ["Offer Letter Email", "Onboarding Email", "Welcome Email"])
        
        if template_type == "Offer Letter Email":
            template_content = OFFER_EMAIL_TEMPLATE
        elif template_type == "Onboarding Email":
            template_content = ONBOARDING_EMAIL_TEMPLATE
        else:
            template_content = "Welcome to AI Planet! We're excited to have you join our team."
        
        template_editor = st.text_area("Edit Template", template_content, height=400)
        
        if st.button("Save Template"):
            # In a real application, save the template to the database
            st.success(f"{template_type} template updated successfully")
    
    with tab2:
        st.subheader("Role Management")
        
        selected_role = st.selectbox("Select Role", list(ROLES.keys()) + ["Add New Role"])
        
        if selected_role == "Add New Role":
            with st.form("new_role_form"):
                new_role_name = st.text_input("Role Title")
                new_role_description = st.text_area("Role Description")
                new_role_skills = st.text_area("Required Skills (one per line)")
                new_role_docs = st.text_area("Onboarding Documents (one per line)")
                new_role_training = st.text_area("Training Modules (one per line)")
                
                submit_role = st.form_submit_button("Add Role")
                
                if submit_role:
                    if not new_role_name or not new_role_description:
                        st.error("Please fill in the role title and description")
                    else:
                        # In a real application, add the role to the database
                        # Here we'll just add it to the ROLES dictionary
                        skills_list = [skill.strip() for skill in new_role_skills.split("\n") if skill.strip()]
                        docs_list = [doc.strip() for doc in new_role_docs.split("\n") if doc.strip()]
                        training_list = [module.strip() for module in new_role_training.split("\n") if module.strip()]
                        
                        ROLES[new_role_name] = {
                            "description": new_role_description,
                            "skills_required": skills_list,
                            "onboarding_docs": docs_list,
                            "training_modules": training_list
                        }
                        
                        st.success(f"Role '{new_role_name}' added successfully")
                        st.rerun()
        else:
            role_data = ROLES[selected_role]
            
            with st.form("edit_role_form"):
                role_description = st.text_area("Role Description", role_data["description"])
                role_skills = st.text_area("Required Skills (one per line)", "\n".join(role_data["skills_required"]))
                role_docs = st.text_area("Onboarding Documents (one per line)", "\n".join(role_data["onboarding_docs"]))
                role_training = st.text_area("Training Modules (one per line)", "\n".join(role_data["training_modules"]))
                
                update_role = st.form_submit_button("Update Role")
                
                if update_role:
                    # In a real application, update the role in the database
                    # Here we'll just update the ROLES dictionary
                    skills_list = [skill.strip() for skill in role_skills.split("\n") if skill.strip()]
                    docs_list = [doc.strip() for doc in role_docs.split("\n") if doc.strip()]
                    training_list = [module.strip() for module in role_training.split("\n") if module.strip()]
                    
                    ROLES[selected_role] = {
                        "description": role_description,
                        "skills_required": skills_list,
                        "onboarding_docs": docs_list,
                        "training_modules": training_list
                    }
                    
                    st.success(f"Role '{selected_role}' updated successfully")
    
    with tab3:
        st.subheader("System Configuration")
        
        col1, col2 = st.columns(2)
        
        with col1:
            company_name = st.text_input("Company Name", COMPANY_INFO["name"])
            company_address = st.text_input("Company Address", COMPANY_INFO["address"])
            company_website = st.text_input("Company Website", COMPANY_INFO["website"])
        
        with col2:
            company_mission = st.text_area("Company Mission", COMPANY_INFO["mission"])
            company_vision = st.text_area("Company Vision", COMPANY_INFO["vision"])
            company_logo = st.file_uploader("Company Logo", type=["png", "jpg", "jpeg"])
        
        # Email settings
        st.subheader("Email Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            email_sender = st.text_input("Sender Email", "hr@aiplanet.com")
            email_signature = st.text_area("Email Signature", "HR Team\nAI Planet\nwww.aiplanet.com")
        
        with col2:
            smtp_server = st.text_input("SMTP Server", "smtp.aiplanet.com")
            smtp_port = st.number_input("SMTP Port", value=587, min_value=1, max_value=65535)
            smtp_auth = st.checkbox("Require Authentication", value=True)
        
        if st.button("Save Configuration"):
            # In a real application, save the configuration to the database
            # Here we'll just update the COMPANY_INFO dictionary
            COMPANY_INFO["name"] = company_name
            COMPANY_INFO["address"] = company_address
            COMPANY_INFO["website"] = company_website
            COMPANY_INFO["mission"] = company_mission
            COMPANY_INFO["vision"] = company_vision
            
            st.success("System configuration updated successfully")

# Dashboard page
def display_dashboard():
    st.title("Onboarding Dashboard")
    
    # Define the main columns for the dashboard
    left_col, right_col = st.columns(2)
    
    with left_col:
        st.markdown("""
        <div class="card">
            <h3>🔍 Overview</h3>
            <p>Welcome to AI Planet's onboarding system. From here, you can manage all aspects of the employee onboarding process.</p>
        </div>
        """, unsafe_allow_html=True)
        
        employees = get_employees()
        st.markdown(f"""
        <div class="card">
            <h3>📊 Quick Stats</h3>
            <p>Total Employees: {len(employees)}</p>
            <p>Pending Onboardings: {sum(1 for emp in employees if not emp.get('onboarding_completed', False))}</p>
            <p>Completed Onboardings: {sum(1 for emp in employees if emp.get('onboarding_completed', False))}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with right_col:
        st.markdown("""
        <div class="card">
            <h3>🚀 Quick Actions</h3>
        </div>
        """, unsafe_allow_html=True)
        
        # Create clickable cards for quick actions
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            <div class="card action-card" onclick="window.location.href='#'">
                <h4>📝 Generate Offer Letter</h4>
                <p>Create and send offer letters to candidates</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Add clickable button underneath for better UX
            if st.button("Generate New Offer Letter"):
                st.session_state.page = "Offer Letter Generator"
                st.rerun()
        
        with col2:
            st.markdown("""
            <div class="card action-card" onclick="window.location.href='#'">
                <h4>👋 Manage Onboarding</h4>
                <p>Handle employee onboarding process</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Add clickable button underneath for better UX
            if st.button("Manage Onboarding"):
                st.session_state.page = "Onboarding Management"
                st.rerun()
        
        # Define another set of columns for the second row of action cards
        action_col1, action_col2 = st.columns(2)  # Use different variable names to avoid confusion
        
        with action_col1:
            st.markdown("""
            <div class="card action-card" onclick="window.location.href='#'">
                <h4>📚 Documentation Library</h4>
                <p>Access and manage documents</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Add clickable button underneath for better UX
            if st.button("View Documentation Library"):
                st.session_state.page = "Documentation Library"
                st.rerun()
        
        with action_col2:
            st.markdown("""
            <div class="card action-card" onclick="window.location.href='#'">
                <h4>📊 Feedback System</h4>
                <p>Collect and review onboarding feedback</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Add clickable button underneath for better UX
            if st.button("View Feedback"):
                st.session_state.page = "Feedback System"
                st.rerun()
    
    # Recent activities
    st.markdown("""
    <div class="card">
        <h3>📅 Recent Activities</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Get recent activities from database - in a real app, this would query database with timestamps
    employees = get_employees()
    activities = []
    
    # Sort employees by updated_at to get recent activities
    sorted_employees = sorted(employees, key=lambda x: x.get('updated_at', ''), reverse=True)[:3]
    
    for emp in sorted_employees:
        activity = {}
        activity["timestamp"] = emp.get('updated_at', datetime.now().strftime("%Y-%m-%d %H:%M"))
        
        if emp.get('onboarding_completed', False):
            activity["activity"] = f"Onboarding completed for {emp['name']}"
        elif emp.get('offer_accepted', False):
            activity["activity"] = f"Offer accepted by {emp['name']}"
        elif emp.get('offer_sent', False):
            activity["activity"] = f"Offer letter sent to {emp['name']}"
        else:
            activity["activity"] = f"Offer letter generated for {emp['name']}"
            
        activity["role"] = emp['position']
        activities.append(activity)
    
    # If no activities from database, show sample ones
    if not activities:
        activities = [
            {"timestamp": "2025-05-06 14:30", "activity": "Offer letter sent to Jane Smith", "role": "Full Stack Developer"},
            {"timestamp": "2025-05-05 11:15", "activity": "Onboarding completed for John Doe", "role": "Data Scientist"},
            {"timestamp": "2025-05-05 09:00", "activity": "New template added for Business Analyst role", "role": "Business Analyst"}
        ]
    
    for activity in activities:
        st.markdown(f"""
        <div style="padding: 10px; border-bottom: 1px solid #eee;">
            <p><strong>{activity['timestamp']}</strong>: {activity['activity']} - <span style="color: #2E5090;">{activity['role']}</span></p>
        </div>
        """, unsafe_allow_html=True)

# Run the application
if __name__ == "__main__":
    main()
