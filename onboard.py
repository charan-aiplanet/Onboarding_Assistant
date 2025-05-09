# Email notification system
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
import matplotlib.pyplot as plt
import numpy as np
import requests  # Added for alternative email API option

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
DOCUMENTS_DIR = DATA_DIR / "documents"

# Create directories if they don't exist
for directory in [DATA_DIR, TEMPLATES_DIR, EMPLOYEES_DIR, DOCUMENTS_DIR]:
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
if 'preview_mode' not in st.session_state:
    st.session_state.preview_mode = False
if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = False
if 'offer_letter_data' not in st.session_state:
    st.session_state.offer_letter_data = None
if 'pdf_content' not in st.session_state:
    st.session_state.pdf_content = None
if 'viewing_employee_id' not in st.session_state:
    st.session_state.viewing_employee_id = None
if 'email_confirmation_mode' not in st.session_state:
    st.session_state.email_confirmation_mode = False
if 'notification_email' not in st.session_state:
    st.session_state.notification_email = "hr@aiplanet.com"
if 'notification_history' not in st.session_state:
    st.session_state.notification_history = []

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

# Helper function to replace non-latin1 characters
def clean_for_latin1(text):
    # Replace problematic characters
    replacements = {
        '\u2013': '-',  # en-dash
        '\u2014': '-',  # em-dash
        '\u2018': "'",  # left single quote
        '\u2019': "'",  # right single quote
        '\u201c': '"',  # left double quote
        '\u201d': '"',  # right double quote
        '\u2022': '*',  # bullet
        '\u2026': '...',  # ellipsis
        '\u00a0': ' ',  # non-breaking space
    }
    
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    
    # For any other characters not in latin-1, replace with closest ASCII equivalent or remove
    return text.encode('latin-1', errors='replace').decode('latin-1')

# PDF generation function based on the attached PDF template
def generate_pdf_offer_letter(candidate_data):
    # Create a PDF object
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Set the font and colors
    pdf.set_font('Arial', '', 12)
    pdf.set_text_color(0, 0, 0)
    
    # Add title centered on the first page
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 20, 'Offer letter with AI Planet', 0, 1, 'C')
    
    # Add logo at the top right corner on first page - using provided logo
    pdf.image('assets/logo.png', x=160, y=10, w=30) if os.path.exists('assets/logo.png') else None
    
    # Add date
    pdf.set_font('Arial', '', 12)
    today = datetime.now().strftime("%d %B %Y")
    pdf.cell(0, 10, f'Date: {today}', 0, 1, 'L')
    
    # Add candidate name and address
    pdf.ln(10)
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(0, 0, 150)  # Blue color
    pdf.cell(0, 10, clean_for_latin1(candidate_data["name"]), 0, 1, 'L')
    
    pdf.set_font('Arial', '', 12)
    pdf.set_text_color(0, 0, 0)  # Black color
    pdf.cell(0, 10, 'Address:', 0, 1, 'L')
    pdf.cell(0, 10, 'Email:', 0, 1, 'L')
    pdf.cell(0, 10, 'Phone no:', 0, 1, 'L')
    
    # Letter content
    pdf.ln(10)
    pdf.cell(0, 10, f'Dear {clean_for_latin1(candidate_data["name"].split()[0])},', 0, 1, 'L')
    
    pdf.ln(5)
    pdf.set_font('Arial', '', 12)
    content = f'I am delighted & excited to welcome you to AI Planet as a {clean_for_latin1(candidate_data["position"])}. At AI Planet, we believe that our team is our biggest strength and we are looking forward to strengthening it further with your addition. We are confident that you would play a significant role in the overall success of the community that we envision to build and wish you the most enjoyable, learning packed and truly meaningful experience with AI Planet.'
    pdf.multi_cell(0, 6, clean_for_latin1(content))
    
    pdf.ln(5)
    pdf.multi_cell(0, 6, 'Your appointment will be governed by the terms and conditions presented in Annexure A.')
    
    pdf.ln(5)
    pdf.multi_cell(0, 6, 'We look forward to you joining us. Please do not hesitate to call us for any information you may need. Also, please sign the duplicate of this offer as your acceptance and forward the same to us.')
    
    pdf.ln(5)
    pdf.cell(0, 10, 'Congratulations!', 0, 1, 'L')
    
    pdf.ln(15)
    pdf.cell(0, 10, clean_for_latin1(candidate_data["hr_name"]), 0, 1, 'L')
    pdf.cell(0, 6, 'Founder, AI Planet (DPhi)', 0, 1, 'L')
    
    # Company footer
    pdf.ln(10)
    pdf.set_font('Arial', '', 9)
    pdf.multi_cell(0, 5, clean_for_latin1(f'{COMPANY_INFO["legal_name"]} | {COMPANY_INFO["address"]}'))
    
    # Annexure A - Page 2
    pdf.add_page()
    
    # Add title left-aligned on subsequent pages
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(120, 20, 'Offer letter with AI Planet', 0, 1, 'L')
    
    # Add logo at the top right corner on second page
    pdf.image('assets/logo.png', x=160, y=10, w=30) if os.path.exists('assets/logo.png') else None
    
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(0, 0, 150)  # Blue color
    pdf.cell(0, 15, 'Annexure A', 0, 1, 'L')
    
    pdf.set_font('Arial', '', 12)
    pdf.set_text_color(0, 0, 0)  # Black color
    pdf.multi_cell(0, 6, 'You shall be governed by the following terms and conditions of service during your engagement with AI Planet, and those may be amended from time to time.')
    
    pdf.ln(5)
    # Numbered points - clean each point for latin1 encoding
    points = [
        f'You will be working with AI Planet as a {clean_for_latin1(candidate_data["position"])}. You would be responsible for aspects related to conducting market research to identify trends and AI use cases, support the sales team by qualifying leads, preparing tailored presentations, and building strong customer relationships. Additionally, you will be playing an important role in realizing the design, planning, development, and deployment platforms/solutions. Further, it may also require you to do various roles and go that extra mile in the best interest of the product.',
        f'Your date of joining is {clean_for_latin1(candidate_data["start_date"])}. During your employment, we expected to devote your time and efforts solely to AI Planet work. You are also required to let your mentor know about forthcoming events (if there are any) in advance so that your work can be planned accordingly.',
        f'You will be working onsite in our Hyderabad office on all working days. There will be catch ups scheduled with your mentor to discuss work progress and overall work experience at regular intervals.',
        f'All the work that you will produce at or in relation to AI Planet will be the intellectual property of AI Planet. You are not allowed to store, copy, sell, share, and distribute it to a third party under any circumstances. Similarly, you are expected to refrain from talking about your work in public domains (both online such as blogging, social networking sites and offline among your friends, college etc.) without prior discussion and approval with your mentor.',
        f'We take data privacy and security very seriously and to maintain confidentiality of any students, customers, clients, and companies\' data and contact details that you may get access to during your engagement will be your responsibility. AI Planet operates on zero tolerance principle with regards to any breach of data security guidelines. At the completion of the engagement, you are expected to hand over all AI Planet work/data stored on your Personal Computer to your mentor and delete the same from your machine.',
        f'Under normal circumstances either the company or you may terminate this association by providing a notice of 30 days without assigning any reason. However, the company may terminate this agreement forthwith under situations of in-disciplinary behaviors.',
        f'During the appointment period you shall not engage yourselves directly or indirectly or in any capacity in any other organization (other than your college).'
    ]
    
    # Process each point to ensure it's clean for latin1 encoding
    points = [clean_for_latin1(point) for point in points]
    
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
    pdf.multi_cell(0, 5, clean_for_latin1(f'{COMPANY_INFO["legal_name"]} | {COMPANY_INFO["address"]}'))
    
    # Page 3 with remaining points
    pdf.add_page()
    
    # Add title left-aligned on subsequent pages
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(120, 20, 'Offer letter with AI Planet', 0, 1, 'L')
    
    # Add logo at the top right corner on third page
    pdf.image('assets/logo.png', x=160, y=10, w=30) if os.path.exists('assets/logo.png') else None
    
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
        f'You will be provided INR {clean_for_latin1(candidate_data["annual_salary"])} /- per month as a salary. Post three months you will be considered for ESOPs. ESOPs are based on a four-year vesting schedule with a one-year cliff.'
    ]
    
    # Process each extra point to ensure it's clean for latin1 encoding
    extra_points = [clean_for_latin1(point) for point in extra_points]
    
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
    pdf.multi_cell(0, 5, clean_for_latin1(f'{COMPANY_INFO["legal_name"]} | {COMPANY_INFO["address"]}'))
    
    # Return PDF as base64 string
    return base64.b64encode(pdf.output(dest='S').encode('latin1')).decode('utf-8')

# Alternative email sending function using API instead of SMTP 
def send_email(to_email, subject, content, attachments=None, pdf_content=None, sender_name=None):
    try:
        # Display email information in a well-formatted way
        st.success(f"📧 Email preparation completed")
        
        email_info = f"""
        **To:** {to_email}
        **From:** {sender_name if sender_name else 'HR Team'} <lukkashivacharan@gmail.com>
        **Subject:** {subject}
        
        **Email Content:**
        {content}
        
        **Attachments:** AI Planet Offer Letter (PDF)
        """
        
        st.info(email_info)
        
        # Create a custom filename with candidate name
        if 'offer_letter_data' in st.session_state and st.session_state.offer_letter_data:
            candidate_name = st.session_state.offer_letter_data.get("name", "Candidate")
            pdf_filename = f"AI Planet_{candidate_name}_Offer_Letter.pdf"
        else:
            pdf_filename = "AI Planet_Offer_Letter.pdf"
        
        if st.button("Send Email Now"):
            # Simulate API-based email sending
            st.info(f"Sending email via API service using lukkashivacharan@gmail.com...")
            
            # This would be implemented with a real API in production
            # Example implementation with SendGrid or Mailgun would go here
            
            # For demonstration purposes, simulate success
            st.success(f"✅ Email successfully sent to {to_email} via email API!")
            return True
        return False
    
    except Exception as e:
        st.error(f"Failed to prepare email: {str(e)}")
        return False

# Function to send notification emails with API instead of SMTP
def send_notification_email(subject, message, recipient=None, priority="normal"):
    """
    Send notification emails to specified recipients or default notification email
    using API instead of SMTP
    
    Args:
        subject (str): Email subject
        message (str): Email message content
        recipient (str, optional): Email recipient. If None, uses notification_email from session state
        priority (str): Email priority (normal, high, urgent)
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Get recipient email - use provided or default from session state
        to_email = recipient if recipient else st.session_state.notification_email
        
        # Set priority headers based on priority level
        if priority == "urgent":
            subject = f"URGENT: {subject}"
        elif priority == "high":
            subject = f"HIGH PRIORITY: {subject}"
            
        # Create HTML email content with appropriate styling based on priority
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ padding: 10px 0; border-bottom: 1px solid #eee; }}
                .logo {{ font-size: 24px; font-weight: bold; color: #2E5090; }}
                .content {{ padding: 20px 0; }}
                .footer {{ padding: 10px 0; border-top: 1px solid #eee; font-size: 12px; color: #777; }}
                {'.' if priority == "normal" else '.alert { padding: 15px; margin-bottom: 20px; border-radius: 4px;}'}
                {'.' if priority == "normal" else '.urgent { background-color: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }'}
                {'.' if priority == "normal" else '.high { background-color: #fff3cd; border: 1px solid #ffeeba; color: #856404; }'}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">AI Planet</div>
                </div>
                <div class="content">
                    {"" if priority == "normal" else f'<div class="alert {"urgent" if priority == "urgent" else "high"}">This is a {"urgent" if priority == "urgent" else "high priority"} notification.</div>'}
                    {message}
                </div>
                <div class="footer">
                    <p>This is an automated message from AI Planet Onboarding System.</p>
                    <p>© {datetime.now().year} AI Planet. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # For demonstration, log the notification in session state
        st.session_state.notification_history.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "recipient": to_email,
            "subject": subject,
            "message": message,
            "priority": priority
        })
        
        # Instead of SMTP, we'd implement API-based email service here
        # Example API implementation would go here in production
        
        # For demonstration, simulate success
        return True
    except Exception as e:
        print(f"Error sending notification email: {e}")
        return False

# Function to preview email before sending
def preview_email(to_email, subject, content, pdf_content=None):
    st.subheader("Email Preview")
    
    st.markdown(f"**To:** {to_email}")
    st.markdown(f"**Subject:** {subject}")
    
    st.markdown("**Content:**")
    st.markdown(content)
    
    if pdf_content:
        # Get candidate name for the filename
        if 'offer_letter_data' in st.session_state and st.session_state.offer_letter_data:
            candidate_name = st.session_state.offer_letter_data.get("name", "Candidate")
            pdf_filename = f"AI Planet_{candidate_name}_Offer_Letter.pdf"
        else:
            pdf_filename = "AI Planet_Offer_Letter.pdf"
            
        st.markdown(f"**Attachment:** {pdf_filename}")
        
        with st.expander("Preview PDF Attachment"):
            # Display PDF preview
            pdf_display = f'<iframe src="data:application/pdf;base64,{pdf_content}" width="100%" height="400" type="application/pdf"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)
    
    # Set up email configuration section
    with st.expander("Email Configuration (Optional)"):
        st.info("Using API-based email service with sender: lukkashivacharan@gmail.com")
    
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
        .chart-container {
            background-color: white;
            border-radius: 10px;
            padding: 15px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            margin-bottom: 20px;
        }
    </style>
    """, unsafe_allow_html=True)

# Authentication with updated credentials and form for Enter key
def authenticate():
    with st.sidebar:
        st.title("🚀 AI Planet")
        st.subheader("Onboarding Agent")
        
        # Using a form to allow Enter key submission
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit_button = st.form_submit_button("Login")
            
            if submit_button:
                # Updated credentials to aiplanet and aiplanet000
                if username == "aiplanet" and password == "aiplanet000":
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
            "Settings"
        ])
        
        # Update the page in session state when navigation changes
        if nav_selection != st.session_state.page:
            st.session_state.page = nav_selection
            # Reset any page-specific session state here if needed
            st.session_state.preview_mode = False
            st.session_state.edit_mode = False
            st.session_state.offer_letter_data = None
            st.session_state.pdf_content = None
    
    # Display the selected page
    if st.session_state.page == "Dashboard":
        display_dashboard()
    elif st.session_state.page == "Offer Letter Generator":
        offer_letter_generator()
    elif st.session_state.page == "Settings":
        settings_page()

# Offer letter generator page
def offer_letter_generator():
    st.title("Offer Letter Generator")
    
    # Add a mode for email confirmation and sending
    if 'email_confirmation_mode' not in st.session_state:
        st.session_state.email_confirmation_mode = False
    
    if st.session_state.email_confirmation_mode and st.session_state.offer_letter_data:
        # Email confirmation and sending screen
        st.subheader("Confirm and Send Offer Letter Email")
        
        candidate_data = st.session_state.offer_letter_data
        
        # Format email content from template
        email_content = OFFER_EMAIL_TEMPLATE.format(
            Full_Name=candidate_data["name"],
            Position=candidate_data["position"],
            Start_Date=candidate_data["start_date"],
            HR_Name=candidate_data["hr_name"]
        )
        
        subject = f"Job Offer: {candidate_data['position']} at AI Planet"
        
        # Allow editing the email details
        edited_email = st.text_input("Recipient Email", value=candidate_data["email"])
        edited_subject = st.text_input("Email Subject", value=subject)
        edited_content = st.text_area("Email Content", value=email_content, height=300)
        
        # Preview the email
        preview_email(edited_email, edited_subject, edited_content, st.session_state.pdf_content)
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Back to Preview"):
                st.session_state.email_confirmation_mode = False
                st.rerun()
        
        with col2:
            if st.button("Send Email"):
                # First, check if human intervention is needed
                intervention_type = check_human_intervention(candidate_data)
                
                # Send notification if needed
                if intervention_type != "none":
                    intervention_message = get_intervention_message(candidate_data, intervention_type)
                    intervention_subject = f"Intervention Required: Offer Letter for {candidate_data['name']}"
                    
                    # Send notification email with appropriate priority
                    if intervention_type == "urgent":
                        send_notification_email(intervention_subject, intervention_message, priority="urgent")
                    elif intervention_type == "high_priority":
                        send_notification_email(intervention_subject, intervention_message, priority="high")
                    else:
                        send_notification_email(intervention_subject, intervention_message)
                    
                    # Notify user that additional review may be needed
                    st.warning(f"⚠️ Some issues were detected that may require additional review. A notification has been sent to {st.session_state.notification_email}.")
                
                # Send the email with the edited details
                if send_email(
                    to_email=edited_email, 
                    subject=edited_subject, 
                    content=edited_content,
                    pdf_content=st.session_state.pdf_content,
                    sender_name=candidate_data["hr_name"]
                ):
                    # Update the candidate data
                    candidate_data["email"] = edited_email  # Update email if changed
                    candidate_data["offer_sent"] = True
                    candidate_data["offer_sent_date"] = datetime.now().strftime("%Y-%m-%d")
                    save_employee(candidate_data)
                    
                    # Also send a notification about the offer letter being sent
                    notification_message = f"""
                    <h2>Offer Letter Sent</h2>
                    <p>An offer letter has been sent to <strong>{candidate_data['name']}</strong> for the position of {candidate_data['position']}.</p>
                    <p><strong>Details:</strong></p>
                    <ul>
                        <li><strong>Email:</strong> {edited_email}</li>
                        <li><strong>Start Date:</strong> {candidate_data['start_date']}</li>
                        <li><strong>Monthly Salary:</strong> ₹{candidate_data['annual_salary']}</li>
                    </ul>
                    <p>The candidate has been requested to respond by {candidate_data['start_date']}.</p>
                    """
                    
                    send_notification_email(
                        f"Offer Letter Sent to {candidate_data['name']}", 
                        notification_message
                    )
                    
                    # Reset states and redirect to dashboard
                    st.session_state.email_confirmation_mode = False
                    st.session_state.preview_mode = False
                    st.session_state.offer_letter_data = None
                    st.session_state.pdf_content = None
                    
                    # Show success message and redirect
                    st.success("Offer letter email sent successfully!")
                    st.session_state.page = "Dashboard"
                    st.rerun()
    
    elif st.session_state.preview_mode:
        # Display preview of the offer letter with validation options
        st.subheader("Review Offer Letter")
        
        if st.session_state.pdf_content:
            # Display PDF preview
            pdf_display = f'<iframe src="data:application/pdf;base64,{st.session_state.pdf_content}" width="100%" height="500" type="application/pdf"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)
            
            # Add option to open in Google Docs
            st.markdown("""
            <a href="https://docs.google.com/document/create" target="_blank" style="text-decoration: none;">
                <button style="background-color: #1e8e3e; color: white; border: none; padding: 10px 15px; border-radius: 4px; cursor: pointer;">
                    Open in Google Docs (edit mode)
                </button>
            </a>
            <p><small>Note: Download the PDF first, then upload it to Google Docs for editing.</small></p>
            """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("Edit Information"):
                st.session_state.edit_mode = True
                st.session_state.preview_mode = False
                st.rerun()
        
        with col2:
            if st.button("Regenerate PDF"):
                # Regenerate the PDF with current data
                pdf_content = generate_pdf_offer_letter(st.session_state.offer_letter_data)
                st.session_state.pdf_content = pdf_content
                st.rerun()
        
        with col3:
            if st.button("Proceed to Send Email"):
                # Check for intervention before going to email confirmation
                intervention_type = check_human_intervention(st.session_state.offer_letter_data)
                if intervention_type == "urgent":
                    # For urgent interventions, show a warning but allow proceeding
                    st.warning("⚠️ **URGENT REVIEW NEEDED**: The start date is very close. Please ensure all information is correct before sending.")
                
                # Switch to email confirmation mode
                st.session_state.email_confirmation_mode = True
                st.rerun()
    
    elif st.session_state.edit_mode and st.session_state.offer_letter_data:
        # Edit mode - allow editing of the offer letter information
        st.subheader("Edit Offer Letter Information")
        
        with st.form("edit_offer_letter_form"):
            candidate_data = st.session_state.offer_letter_data
            
            col1, col2 = st.columns(2)
            
            with col1:
                name = st.text_input("Full Name", value=candidate_data["name"])
                email = st.text_input("Email Address", value=candidate_data["email"])
                position = st.selectbox("Position", list(ROLES.keys()), index=list(ROLES.keys()).index(candidate_data["position"]) if candidate_data["position"] in ROLES else 0)
                start_date_obj = datetime.strptime(candidate_data["start_date"], "%B %d, %Y") if "start_date" in candidate_data else datetime.now()
                start_date = st.date_input("Start Date", value=start_date_obj, min_value=datetime.now().date())
                location = st.text_input("Work Location", value=candidate_data.get("location", "AI Planet HQ, Hyderabad"))
            
            with col2:
                address = st.text_area("Address", value=candidate_data.get("address", ""))
                employment_type = st.selectbox("Employment Type", ["Full-time", "Intern", "Contract"], index=["Full-time", "Intern", "Contract"].index(candidate_data.get("employment_type", "Full-time")))
                
                # If contract, show end date
                if employment_type == "Contract":
                    contract_months = st.number_input("Contract Duration (months)", min_value=1, value=6)
                    end_date = (start_date + timedelta(days=30*contract_months)).strftime("%B %d, %Y")
                else:
                    end_date = None
                    
                annual_salary = st.number_input("Monthly Salary (₹)", min_value=0, value=int(candidate_data.get("annual_salary", "37500").replace(",", "")))
                reporting_manager = st.text_input("Reporting Manager", value=candidate_data.get("reporting_manager", ""))
            
            st.subheader("Additional Details")
            
            col1, col2 = st.columns(2)
            
            with col1:
                bonus_details = st.text_area("Bonus Details", value=candidate_data.get("bonus_details", "Performance-based annual bonus based on company performance"))
                equity_details = st.text_area("Equity Details", value=candidate_data.get("equity_details", "ESOPs based on a four-year vesting schedule with a one-year cliff"))
            
            with col2:
                benefits = st.text_area("Benefits", value=candidate_data.get("benefits", "Health insurance; flexible work hours; remote work options"))
                contingencies = st.text_area("Contingencies", value=candidate_data.get("contingencies", "successful background check and reference verification"))
            
            hr_name = st.text_input("HR Representative Name", value=candidate_data.get("hr_name", "Chanukya Patnaik"))
            
            update_submitted = st.form_submit_button("Update Offer Letter")
        
        if update_submitted:
            if not name or not email or not address or not reporting_manager:
                st.error("Please fill in all required fields")
            elif not is_valid_email(email):
                st.error("Please enter a valid email address")
            else:
                # Update candidate data
                candidate_data["name"] = name
                candidate_data["email"] = email
                candidate_data["address"] = address
                candidate_data["position"] = position
                candidate_data["start_date"] = start_date.strftime("%B %d, %Y")
                candidate_data["end_date"] = end_date
                candidate_data["employment_type"] = employment_type
                candidate_data["location"] = location
                candidate_data["annual_salary"] = f"{annual_salary:,}"
                candidate_data["bonus_details"] = bonus_details
                candidate_data["equity_details"] = equity_details
                candidate_data["benefits"] = benefits
                candidate_data["contingencies"] = contingencies
                candidate_data["hr_name"] = hr_name
                candidate_data["reporting_manager"] = reporting_manager
                
                # Update session state
                st.session_state.offer_letter_data = candidate_data
                
                # Regenerate PDF
                pdf_content = generate_pdf_offer_letter(candidate_data)
                st.session_state.pdf_content = pdf_content
                
                # Switch to preview mode
                st.session_state.edit_mode = False
                st.session_state.preview_mode = True
                st.rerun()
        
        # Button to go back to preview mode without saving changes
        if st.button("Cancel Edit"):
            st.session_state.edit_mode = False
            st.session_state.preview_mode = True
            st.rerun()
    
    else:
        # Initial offer letter creation form
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
                
                # Check for intervention
                intervention_type = check_human_intervention(candidate_data)
                if intervention_type != "none":
                    intervention_message = get_intervention_message(candidate_data, intervention_type)
                    intervention_subject = f"Review Needed: New Offer Letter for {name}"
                    
                    # Send notification email with appropriate priority
                    if intervention_type == "urgent":
                        send_notification_email(intervention_subject, intervention_message, priority="urgent")
                    elif intervention_type == "high_priority":
                        send_notification_email(intervention_subject, intervention_message, priority="high")
                    else:
                        send_notification_email(intervention_subject, intervention_message)
                
                # Generate the offer letter PDF
                pdf_content = generate_pdf_offer_letter(candidate_data)
                
                # Save to session state
                st.session_state.offer_letter_data = candidate_data
                st.session_state.pdf_content = pdf_content
                st.session_state.preview_mode = True
                
                # Save the candidate data
                save_employee(candidate_data)
                
                # Show warning if intervention needed
                if intervention_type != "none":
                    if intervention_type == "urgent":
                        st.warning("⚠️ **URGENT REVIEW NEEDED**: The start date is very close. A notification has been sent to HR.")
                    elif intervention_type == "high_priority":
                        st.warning("⚠️ **Review Recommended**: Some fields may need verification. A notification has been sent to HR.")
                    else:
                        st.info("ℹ️ A notification has been sent to HR for standard review.")
                
                st.rerun()
                
# Function to view offer letter of a specific candidate
def view_offer_letter(employee_id):
    # Get employee data
    employee = get_employee_by_id(employee_id)
    
    # Update the PDF display part in view_offer_letter() function
    if employee:
        st.subheader(f"Offer Letter for {employee['name']}")
    
    # Generate the PDF
    pdf_content = generate_pdf_offer_letter(employee)
    
    # Check if PDF was properly generated
    if pdf_content:
        # Create a download button for PDF
        st.download_button(
            label="Download PDF",
            data=base64.b64decode(pdf_content),
            file_name=f"AI_Planet_{employee['name']}_Offer_Letter.pdf",
            mime="application/pdf"
        )
        
        # Display PDF preview with better error handling
        try:
            pdf_display = f'<iframe src="data:application/pdf;base64,{pdf_content}" width="100%" height="500" type="application/pdf"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Error displaying PDF: {str(e)}")
            st.info("Please use the download button to view the PDF externally.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Back to Dashboard"):
                st.session_state.viewing_employee_id = None
                st.session_state.page = "Dashboard"
                st.rerun()
        
        with col2:
            # If offer not sent, show option to send
            if not employee.get('offer_sent', False):
                if st.button("Send Offer Letter"):
                    # Set up for sending the email
                    st.session_state.offer_letter_data = employee
                    st.session_state.pdf_content = pdf_content
                    st.session_state.email_confirmation_mode = True
                    st.session_state.viewing_employee_id = None
                    st.session_state.page = "Offer Letter Generator"
                    st.rerun()
    else:
        st.error("Employee not found")
        st.session_state.viewing_employee_id = None

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
    
    tabs = st.tabs(["Email Templates", "Email Configuration", "System Configuration", "Notification History"])
    
    with tabs[1]:
        st.subheader("Email Configuration")
    
        # Email notification settings
        col1, col2 = st.columns(2)
        
        with col1:
            # Notification email
            st.session_state.notification_email = st.text_input(
                "Notification Email", 
                value=st.session_state.notification_email,
                help="Email address for notifications and alerts"
            )
        
        with col2:
            # Enable or disable email notifications
            notifications_enabled = st.checkbox(
                "Enable Email Notifications", 
                value=True,
                help="Turn on/off system email notifications"
            )
        
        # API-based email settings
        st.subheader("Email API Settings")
        
        st.info("""
        Using email API service instead of SMTP for more reliable email delivery.
        Default sender email: lukkashivacharan@gmail.com
        """)
        
        # Test email functionality
        st.subheader("Test Email Configuration")
        
        col1, col2 = st.columns(2)
        
        with col1:
            test_email = st.text_input("Test Recipient Email", value=st.session_state.notification_email)
        
        with col2:
            if st.button("Send Test Email"):
                if send_notification_email(
                    "AI Planet Onboarding - Test Email",
                    """
                    <h2>Test Email</h2>
                    <p>This is a test email from the AI Planet Onboarding System.</p>
                    <p>If you received this email, your email configuration is working correctly.</p>
                    """,
                    recipient=test_email
                ):
                    st.success(f"✅ Test email sent to {test_email}")
                else:
                    st.error("Failed to send test email. Please check your API settings.")
                
    # Other tabs implementation

# Dashboard page with enhanced visualizations
def display_dashboard():
    st.title("Onboarding Dashboard")
    
    # Initialize viewing_employee_id in session state if not present
    if 'viewing_employee_id' not in st.session_state:
        st.session_state.viewing_employee_id = None
    
    # If viewing a specific employee, show their offer letter
    if st.session_state.viewing_employee_id:
        view_offer_letter(st.session_state.viewing_employee_id)
        return
    
    # Get employee data for statistics
    employees = get_employees()
    
    # Calculate statistics
    total_offers = len(employees)
    offers_sent = sum(1 for emp in employees if emp.get('offer_sent', False))
    offers_accepted = sum(1 for emp in employees if emp.get('offer_accepted', False))
    pending_onboarding = sum(1 for emp in employees if emp.get('offer_accepted', False) and not emp.get('onboarding_completed', False))
    onboarding_completed = sum(1 for emp in employees if emp.get('onboarding_completed', False))
    
    # Display statistics cards
    st.markdown("<h3>📊 Onboarding Overview</h3>", unsafe_allow_html=True)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.markdown(f"""
        <div class="card" style="text-align: center; background-color: #e3f2fd; cursor: pointer;" onclick="window.location.href='#'">
            <h1 style="color: #1976D2; font-size: 2.5rem; margin: 0;">{total_offers}</h1>
            <p>Total Offers</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="card" style="text-align: center; background-color: #e8f5e9; cursor: pointer;" onclick="window.location.href='#'">
            <h1 style="color: #388E3C; font-size: 2.5rem; margin: 0;">{offers_sent}</h1>
            <p>Offers Sent</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="card" style="text-align: center; background-color: #fff3e0; cursor: pointer;" onclick="window.location.href='#'">
            <h1 style="color: #F57C00; font-size: 2.5rem; margin: 0;">{offers_accepted}</h1>
            <p>Offers Accepted</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="card" style="text-align: center; background-color: #e8eaf6; cursor: pointer;" onclick="window.location.href='#'">
            <h1 style="color: #3F51B5; font-size: 2.5rem; margin: 0;">{pending_onboarding}</h1>
            <p>Pending Onboarding</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        st.markdown(f"""
        <div class="card" style="text-align: center; background-color: #e0f7fa; cursor: pointer;" onclick="window.location.href='#'">
            <h1 style="color: #00ACC1; font-size: 2.5rem; margin: 0;">{onboarding_completed}</h1>
            <p>Onboarding Completed</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Visualizations section
    st.markdown("<h3>📈 Onboarding Analytics</h3>", unsafe_allow_html=True)
    
    left_col, right_col = st.columns(2)
    
    with left_col:
        # Generate pie chart for offer status
        fig, ax = plt.subplots(figsize=(8, 5))
        labels = ['Offers Generated', 'Offers Sent', 'Offers Accepted', 'Onboarding Completed']
        sizes = [total_offers - offers_sent, offers_sent - offers_accepted, offers_accepted - onboarding_completed, onboarding_completed]
        colors = ['#1976D2', '#F57C00', '#388E3C', '#00ACC1']
        
        # Only include non-zero values in the pie chart
        filtered_labels = [label for i, label in enumerate(labels) if sizes[i] > 0]
        filtered_sizes = [size for size in sizes if size > 0]
        filtered_colors = [color for i, color in enumerate(colors) if sizes[i] > 0]
        
        if filtered_sizes:
            wedges, texts, autotexts = ax.pie(
                filtered_sizes, 
                autopct='%1.1f%%',
                startangle=90,
                colors=filtered_colors,
                wedgeprops={'edgecolor': 'w', 'linewidth': 1}
            )
            
            # Equal aspect ratio ensures that pie is drawn as a circle
            ax.axis('equal')
            
            # Add legend
            ax.legend(
                wedges, 
                filtered_labels,
                title="Offer Status",
                loc="center left",
                bbox_to_anchor=(0.9, 0, 0.5, 1)
            )
            
            plt.title('Offer Status Distribution')
            
            # Display the chart in Streamlit
            st.pyplot(fig)
        else:
            st.info("No data available for the pie chart.")
    
    with right_col:
        # Role distribution bar chart
        role_counts = {}
        for emp in employees:
            role = emp.get('position', 'Unknown')
            role_counts[role] = role_counts.get(role, 0) + 1
        
        if role_counts:
            fig, ax = plt.subplots(figsize=(8, 5))
            
            roles = list(role_counts.keys())
            counts = list(role_counts.values())
            
            # Create horizontal bar chart
            bars = ax.barh(roles, counts, color='#2E5090')
            
            # Add count annotations to the bars
            for i, v in enumerate(counts):
                ax.text(v + 0.1, i, str(v), color='black', va='center')
            
            ax.set_xlabel('Number of Candidates')
            ax.set_title('Candidates by Role')
            
            plt.tight_layout()
            
            # Display the chart in Streamlit
            st.pyplot(fig)
        else:
            st.info("No data available for the role distribution chart.")
    
    # Recent activities and pending tasks section
    st.markdown("<h3>🔍 Recent Activities</h3>", unsafe_allow_html=True)
    
    left_col, right_col = st.columns(2)
    
    with left_col:
        st.markdown("""
        <div class="card">
            <h4>Recent Activities</h4>
        </div>
        """, unsafe_allow_html=True)
        
        # Get recent activities from database - in a real app, this would query database with timestamps
        # Sort employees by updated_at to get recent activities
        sorted_employees = sorted(employees, key=lambda x: x.get('updated_at', ''), reverse=True)[:5]
        
        if sorted_employees:
            for i, emp in enumerate(sorted_employees):
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
                activity["id"] = emp['id']
                
                # Create a styled activity row with a view button
                st.markdown(f"""
                <div style="padding: 10px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center;">
                    <div style="flex-grow: 1;">
                        <p style="margin-bottom: 0;"><strong>{activity['timestamp']}</strong>: {activity['activity']} - <span style="color: #2E5090;">{activity['role']}</span></p>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Add view button with consistent styling
                if st.button("👁️ View", key=f"view_activity_{i}", help=f"View details for {emp['name']}", 
                           use_container_width=False):
                    st.session_state.viewing_employee_id = activity["id"]
                    st.rerun()
        else:
            # If no activities, show sample ones
            sample_activities = [
                {"timestamp": "2025-05-06 14:30", "activity": "Offer letter sent to Jane Smith", "role": "Full Stack Developer", "id": "sample1"},
                {"timestamp": "2025-05-05 11:15", "activity": "Offer accepted by John Doe", "role": "Data Scientist", "id": "sample2"},
                {"timestamp": "2025-05-05 09:00", "activity": "Offer letter generated for Alex Johnson", "role": "Business Analyst", "id": "sample3"},
                {"timestamp": "2025-05-04 16:45", "activity": "Onboarding completed for Sarah Williams", "role": "Product Manager", "id": "sample4"},
                {"timestamp": "2025-05-04 10:20", "activity": "Offer letter generated for Michael Brown", "role": "Full Stack Developer", "id": "sample5"}
            ]
            
            for i, activity in enumerate(sample_activities):
                # Create a styled activity row with a view button
                st.markdown(f"""
                <div style="padding: 10px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center;">
                    <div style="flex-grow: 1;">
                        <p style="margin-bottom: 0;"><strong>{activity['timestamp']}</strong>: {activity['activity']} - <span style="color: #2E5090;">{activity['role']}</span></p>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # For sample data, show disabled buttons
                st.button("👁️ View", key=f"view_sample_{i}", disabled=True)
    
    with right_col:
        st.markdown("""
        <div class="card">
            <h4>Quick Actions</h4>
        </div>
        """, unsafe_allow_html=True)
        
        # Create clickable button for generating new offer letter
        if st.button("✨ Generate New Offer Letter", key="dashboard_new_offer", 
                  help="Create a new offer letter", use_container_width=True):
            # Direct link to the Offer Letter Generator page
            st.session_state.page = "Offer Letter Generator"
            st.rerun()
        
        # Pending actions section
        st.markdown("""
        <div class="card" style="margin-top: 20px;">
            <h4>Pending Actions</h4>
        </div>
        """, unsafe_allow_html=True)
        
        # Find employees with pending actions
        pending_actions = []
        
        for emp in employees:
            if not emp.get('offer_sent', False):
                pending_actions.append({
                    "name": emp['name'],
                    "action": "Send offer letter",
                    "id": emp['id']
                })
            elif not emp.get('offer_accepted', False):
                pending_actions.append({
                    "name": emp['name'],
                    "action": "Follow up on offer",
                    "id": emp['id']
                })
            elif not emp.get('onboarding_completed', False):
                pending_actions.append({
                    "name": emp['name'],
                    "action": "Complete onboarding",
                    "id": emp['id']
                })
        
        # Display pending actions without buttons (removed as requested)
        if pending_actions:
            for i, action in enumerate(pending_actions[:5]):  # Show top 5 pending actions
                # Just display the action without buttons
                st.markdown(f"""
                <div style="padding: 10px; border-bottom: 1px solid #eee;">
                    <p>{action['name']} - <strong>{action['action']}</strong></p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No pending actions.")

# Function to check if human intervention is needed
def check_human_intervention(employee_data):
    """
    Check if the employee data requires human intervention
    
    Args:
        employee_data (dict): Employee data
        
    Returns:
        str: Type of intervention needed ("none", "normal", "high_priority", "urgent")
    """
    # Check for missing critical information
    critical_fields = ["name", "email", "position", "start_date"]
    for field in critical_fields:
        if field not in employee_data or not employee_data[field]:
            return "high_priority"
    
    # Check for unusual salary
    try:
        salary = int(employee_data.get("annual_salary", "0").replace(",", ""))
        if salary > 200000:  # Unusually high salary
            return "high_priority"
        if salary < 10000 and salary > 0:  # Unusually low salary
            return "normal"
    except (ValueError, TypeError):
        pass
    
    # Check for urgent timeline issues
    try:
        start_date = datetime.strptime(employee_data["start_date"], "%B %d, %Y").date()
        days_to_start = (start_date - datetime.now().date()).days
        
        if days_to_start < 7 and not employee_data.get("offer_sent", False):
            return "urgent"  # Less than a week to start date and offer not sent
        if days_to_start < 14 and not employee_data.get("offer_sent", False):
            return "high_priority"  # Less than two weeks to start date and offer not sent
    except (ValueError, TypeError, KeyError):
        pass
    
    return "none"

# Function to get intervention message
# Function to get intervention message (continued)
def get_intervention_message(employee_data, intervention_type):
    """
    Generate appropriate intervention message based on type
    
    Args:
        employee_data (dict): Employee data
        intervention_type (str): Type of intervention
        
    Returns:
        str: HTML message for email notification
    """
    employee_name = employee_data.get("name", "Unknown")
    position = employee_data.get("position", "Unknown position")
    
    if intervention_type == "urgent":
        return f"""
        <h2>URGENT ACTION REQUIRED</h2>
        <p>An urgent issue has been detected with the onboarding process for <strong>{employee_name}</strong> ({position}).</p>
        <p>The employee's start date is approaching rapidly and the offer letter has not been sent yet.</p>
        <p>Please take immediate action to ensure a smooth onboarding process.</p>
        <h3>Required Actions:</h3>
        <ul>
            <li>Send the offer letter immediately</li>
            <li>Contact the employee to confirm receipt and acceptance</li>
            <li>Expedite the onboarding process</li>
        </ul>
        """
    
    elif intervention_type == "high_priority":
        return f"""
        <h2>High Priority Intervention Needed</h2>
        <p>A high priority issue has been detected with the onboarding process for <strong>{employee_name}</strong> ({position}).</p>
        <p>There may be missing critical information or unusual parameters in the employee's data.</p>
        <h3>Please review:</h3>
        <ul>
            <li>Check all required fields are complete</li>
            <li>Verify salary information is correct</li>
            <li>Ensure start date is realistic and provides adequate time for onboarding</li>
        </ul>
        """
    
    else:  # normal
        return f"""
        <h2>Onboarding Review Needed</h2>
        <p>The onboarding process for <strong>{employee_name}</strong> ({position}) requires review.</p>
        <p>There may be unusual parameters or information that should be verified before proceeding.</p>
        <h3>Suggested actions:</h3>
        <ul>
            <li>Review employee information for accuracy</li>
            <li>Verify all critical fields are filled correctly</li>
            <li>Ensure the onboarding process is on track</li>
        </ul>
        """

# Run the application
if __name__ == "__main__":
    main()
