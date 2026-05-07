from tkinter import *
from tkinter import messagebox, ttk
import json
import os
from datetime import datetime
import re
import hashlib
import mysql.connector
from mysql.connector import Error

# ============== DATABASE CONFIGURATION ==============
class DatabaseConnection:
    def __init__(self):
        self.host = "192.168.1.88"
        self.database = "his_db"
        self.user = "root"
        self.password = "root"
        self.connection = None
    
    def connect(self):
        """Establish database connection"""
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                database=self.database,
                user=self.user,
                password=self.password
            )
            if self.connection.is_connected():
                return True
        except Error as e:
            print(f"Error connecting to MySQL: {e}")
            return False
    
    def disconnect(self):
        """Close database connection"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
    
    def execute_query(self, query, params=None):
        """Execute a query and return cursor"""
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor
        except Error as e:
            print(f"Error executing query: {e}")
            return None
    
    def commit(self):
        """Commit changes"""
        if self.connection:
            self.connection.commit()
    
    def create_tables(self):
        """Create necessary database tables"""
        # Create users table
        users_table = """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL DEFAULT 'Staff',
            created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME NULL
        )
        """
        
        # Create patients table
        patients_table = """
        CREATE TABLE IF NOT EXISTS patients (
            id INT AUTO_INCREMENT PRIMARY KEY,
            patient_id VARCHAR(20) UNIQUE NOT NULL,
            first_name VARCHAR(50) NOT NULL,
            last_name VARCHAR(50) NOT NULL,
            age INT,
            gender VARCHAR(10),
            phone VARCHAR(15),
            email VARCHAR(100),
            address TEXT,
            medical_history TEXT,
            registration_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
        
        try:
            self.execute_query(users_table)
            self.execute_query(patients_table)
            self.commit()
            print("Database tables created successfully")
        except Error as e:
            print(f"Error creating tables: {e}")

# ============== USER AUTHENTICATION ==============
class UserDatabase:
    def __init__(self):
        self.db = DatabaseConnection()
        if not self.db.connect():
            raise Exception("Failed to connect to database")
        self.db.create_tables()
        self.create_default_admin()
    
    def hash_password(self, password):
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def authenticate(self, username, password):
        """Authenticate user credentials"""
        query = "SELECT * FROM users WHERE username = %s"
        cursor = self.db.execute_query(query, (username,))
        
        if cursor:
            result = cursor.fetchone()
            if result:
                stored_password = result[2]  # password column
                if stored_password == self.hash_password(password):
                    # Update last login time
                    update_query = "UPDATE users SET last_login = NOW() WHERE username = %s"
                    self.db.execute_query(update_query, (username,))
                    self.db.commit()
                    
                    user_data = {
                        'id': result[0],
                        'username': result[1],
                        'password': result[2],
                        'role': result[3],
                        'created_date': str(result[4]),
                        'last_login': str(result[5]) if result[5] else None
                    }
                    return True, user_data
        
        return False, None
    
    def add_user(self, username, password, role="Staff"):
        """Add a new user"""
        # Check if username already exists
        check_query = "SELECT COUNT(*) FROM users WHERE username = %s"
        cursor = self.db.execute_query(check_query, (username,))
        
        if cursor and cursor.fetchone()[0] > 0:
            return False, "Username already exists"
        
        # Insert new user
        insert_query = """
        INSERT INTO users (username, password, role, created_date) 
        VALUES (%s, %s, %s, NOW())
        """
        
        try:
            self.db.execute_query(insert_query, (username, self.hash_password(password), role))
            self.db.commit()
            return True, "User created successfully"
        except Error as e:
            return False, f"Error creating user: {e}"
    
    def get_all_users(self):
        """Get all users"""
        query = "SELECT * FROM users ORDER BY created_date DESC"
        cursor = self.db.execute_query(query)
        
        users = {}
        if cursor:
            for row in cursor.fetchall():
                users[row[1]] = {  # username as key
                    'id': row[0],
                    'username': row[1],
                    'password': row[2],
                    'role': row[3],
                    'created_date': str(row[4]),
                    'last_login': str(row[5]) if row[5] else None
                }
        return users
    
    def create_default_admin(self):
        """Create default admin user if not exists"""
        try:
            # Check if admin exists
            check_query = "SELECT COUNT(*) FROM users WHERE username = 'admin'"
            cursor = self.db.execute_query(check_query)
            
            if cursor and cursor.fetchone()[0] == 0:
                # Create default admin
                insert_query = """
                INSERT INTO users (username, password, role, created_date) 
                VALUES (%s, %s, %s, NOW())
                """
                self.db.execute_query(insert_query, ('admin', self.hash_password('admin123'), 'Administrator'))
                self.db.commit()
                print("Default admin user created")
        except Error as e:
            print(f"Error creating default admin: {e}")

# ============== LOGIN WINDOW ==============
def create_login_window():
    login_window = Tk()
    login_window.title("Hospital Information System - Login")
    login_window.geometry("400x350")
    login_window.resizable(False, False)
    
    # Center the window
    login_window.eval('tk::PlaceWindow . center')
    
    # Icon
    try:
        icon = PhotoImage(file='qphn.jpg')
        login_window.iconphoto(True, icon)
    except:
        pass
    
    # Title
    title_label = Label(login_window, text="Hospital Information System", 
                       font=("Arial", 18, "bold"), fg="darkblue")
    title_label.pack(pady=20)
    
    subtitle_label = Label(login_window, text="Please Login to Continue", 
                          font=("Arial", 12), fg="gray")
    subtitle_label.pack(pady=5)
    
    # Login Frame
    login_frame = Frame(login_window)
    login_frame.pack(pady=20)
    
    # Username
    username_label = Label(login_frame, text="Username:", font=("Arial", 12, "bold"))
    username_label.grid(row=0, column=0, pady=10, padx=10, sticky=E)
    
    username_entry = Entry(login_frame, width=25, font=("Arial", 12))
    username_entry.grid(row=0, column=1, pady=10, padx=10)
    username_entry.focus()  # Focus on username field
    
    # Password
    password_label = Label(login_frame, text="Password:", font=("Arial", 12, "bold"))
    password_label.grid(row=1, column=0, pady=10, padx=10, sticky=E)
    
    password_entry = Entry(login_frame, width=25, font=("Arial", 12), show="*")
    password_entry.grid(row=1, column=1, pady=10, padx=10)
    
    # Login Button
    def login():
        username = username_entry.get().strip()
        password = password_entry.get().strip()
        
        if not username or not password:
            messagebox.showerror("Error", "Please enter both username and password")
            return
        
        user_db = UserDatabase()
        success, user_data = user_db.authenticate(username, password)
        
        if success:
            login_window.destroy()
            create_main_application(user_data)
        else:
            messagebox.showerror("Login Failed", "Invalid username or password")
    
    login_btn = Button(login_frame, text="Login", command=login, 
                      bg="blue", fg="white", font=("Arial", 12, "bold"), 
                      width=20, padx=10, pady=5)
    login_btn.grid(row=2, column=0, columnspan=2, pady=20)
    
    # Bind Enter key to login
    login_window.bind('<Return>', lambda event: login())
    
    # Info label
    info_label = Label(login_window, text="Default login: admin / admin123", 
                      font=("Arial", 9), fg="gray")
    info_label.pack(pady=10)
    
    login_window.mainloop()

# ============== USER REGISTRATION WINDOW ==============
def open_user_registration():
    reg_window = Toplevel(window)
    reg_window.title("User Registration")
    reg_window.geometry("450x500")
    reg_window.resizable(False, False)
    
    # Title Label
    title = Label(reg_window, text="Add New User", font=("Arial", 18, "bold"), fg="darkblue")
    title.pack(pady=20)
    
    # Main Frame
    main_frame = Frame(reg_window)
    main_frame.pack(fill=BOTH, expand=True, padx=20, pady=10)
    
    # Username
    Label(main_frame, text="Username:", font=("Arial", 12, "bold")).grid(row=0, column=0, sticky=W, pady=10)
    username_entry = Entry(main_frame, width=30, font=("Arial", 12))
    username_entry.grid(row=0, column=1, padx=10, pady=10)
    
    # Password
    Label(main_frame, text="Password:", font=("Arial", 12, "bold")).grid(row=1, column=0, sticky=W, pady=10)
    password_entry = Entry(main_frame, width=30, font=("Arial", 12), show="*")
    password_entry.grid(row=1, column=1, padx=10, pady=10)
    
    # Confirm Password
    Label(main_frame, text="Confirm Password:", font=("Arial", 12, "bold")).grid(row=2, column=0, sticky=W, pady=10)
    confirm_password_entry = Entry(main_frame, width=30, font=("Arial", 12), show="*")
    confirm_password_entry.grid(row=2, column=1, padx=10, pady=10)
    
    # Role
    Label(main_frame, text="Role:", font=("Arial", 12, "bold")).grid(row=3, column=0, sticky=W, pady=10)
    role_var = StringVar(value="Staff")
    role_combo = ttk.Combobox(main_frame, textvariable=role_var, 
                             values=["Staff", "Administrator"], width=27, state="readonly")
    role_combo.grid(row=3, column=1, padx=10, pady=10)
    
    # Info Label
    info_label = Label(main_frame, text="", font=("Arial", 10), fg="gray")
    info_label.grid(row=4, column=0, columnspan=2, pady=10)
    
    def register_user():
        username = username_entry.get().strip()
        password = password_entry.get()
        confirm_password = confirm_password_entry.get()
        role = role_var.get()
        
        # Validation
        if not validate_username(username):
            messagebox.showerror("Error", "Username must be 3-20 characters long and contain only letters, numbers, and underscores")
            return
        
        if not validate_password(password):
            messagebox.showerror("Error", "Password must be at least 6 characters long")
            return
        
        if password != confirm_password:
            messagebox.showerror("Error", "Passwords do not match")
            return
        
        user_db = UserDatabase()
        success, message = user_db.add_user(username, password, role)
        
        if success:
            messagebox.showinfo("Success", f"User '{username}' registered successfully as {role}!")
            
            # Clear form
            username_entry.delete(0, END)
            password_entry.delete(0, END)
            confirm_password_entry.delete(0, END)
            role_var.set("Staff")
            info_label.config(text="")
        else:
            messagebox.showerror("Error", message)
    
    # Button Frame
    button_frame = Frame(reg_window)
    button_frame.pack(pady=20)
    
    register_btn = Button(button_frame, text="Register User", command=register_user, 
                         bg="green", fg="white", font=("Arial", 12, "bold"), width=15, padx=10, pady=10)
    register_btn.pack(side=LEFT, padx=5)
    
    close_btn = Button(button_frame, text="Close", command=reg_window.destroy, 
                      bg="red", fg="white", font=("Arial", 12, "bold"), width=15, padx=10, pady=10)
    close_btn.pack(side=LEFT, padx=5)

# ============== USER MANAGEMENT WINDOW ==============
def open_user_management():
    mgmt_window = Toplevel(window)
    mgmt_window.title("User Management")
    mgmt_window.geometry("700x500")
    mgmt_window.resizable(True, True)
    
    # Title Label
    title = Label(mgmt_window, text="User Management", font=("Arial", 18, "bold"), fg="darkblue")
    title.pack(pady=20)
    
    # Treeview Frame
    tree_frame = Frame(mgmt_window)
    tree_frame.pack(fill=BOTH, expand=True, padx=20, pady=10)
    
    # Create Treeview
    columns = ("Username", "Role", "Created Date")
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)
    
    # Define headings
    tree.heading("Username", text="Username")
    tree.heading("Role", text="Role")
    tree.heading("Created Date", text="Created Date")
    
    # Define column widths
    tree.column("Username", width=150)
    tree.column("Role", width=120)
    tree.column("Created Date", width=200)
    
    # Add scrollbar
    scrollbar = ttk.Scrollbar(tree_frame, orient=VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    
    tree.pack(side=LEFT, fill=BOTH, expand=True)
    scrollbar.pack(side=RIGHT, fill=Y)
    
    # Details Text Area
    details_frame = Frame(mgmt_window)
    details_frame.pack(fill=BOTH, expand=True, padx=20, pady=10)
    
    Label(details_frame, text="User Details:", font=("Arial", 12, "bold")).pack(anchor=W)
    
    details_text = Text(details_frame, wrap=WORD, font=("Arial", 10), height=6)
    details_scrollbar = Scrollbar(details_frame, command=details_text.yview)
    details_text.config(yscrollcommand=details_scrollbar.set)
    
    details_text.pack(side=LEFT, fill=BOTH, expand=True)
    details_scrollbar.pack(side=RIGHT, fill=Y)
    
    def load_users():
        # Clear existing items
        for item in tree.get_children():
            tree.delete(item)
        
        user_db = UserDatabase()
        users = user_db.users
        
        if not users:
            tree.insert("", END, values=("No users", "found", ""))
            return
        
        for username, user_data in users.items():
            tree.insert("", END, values=(
                username,
                user_data.get('role', 'N/A'),
                user_data.get('created_date', 'N/A')
            ))
    
    def on_tree_select(event):
        selected_item = tree.selection()
        if selected_item:
            item = tree.item(selected_item)
            username = item['values'][0]
            
            if username == "No users":
                details_text.delete(1.0, END)
                details_text.insert(END, "No user details available")
                return
            
            user_db = UserDatabase()
            user_data = user_db.users.get(username)
            if user_data:
                details_text.delete(1.0, END)
                details_text.insert(END, f"Username: {username}\n")
                details_text.insert(END, f"Role: {user_data.get('role', 'N/A')}\n")
                details_text.insert(END, f"Created Date: {user_data.get('created_date', 'N/A')}\n")
                details_text.insert(END, f"Last Login: {user_data.get('last_login', 'Never')}\n")
    
    tree.bind('<<TreeviewSelect>>', on_tree_select)
    
    # Button Frame
    button_frame = Frame(mgmt_window)
    button_frame.pack(pady=20)
    
    refresh_btn = Button(button_frame, text="Refresh List", command=load_users, 
                        bg="blue", fg="white", font=("Arial", 12, "bold"), width=15, padx=10, pady=10)
    refresh_btn.pack(side=LEFT, padx=5)
    
    close_btn = Button(button_frame, text="Close", command=mgmt_window.destroy, 
                      bg="red", fg="white", font=("Arial", 12, "bold"), width=15, padx=10, pady=10)
    close_btn.pack(side=LEFT, padx=5)
    
    # Load users on startup
    load_users()

# ============== MAIN APPLICATION ==============
def create_main_application(user_data):
    global window
    
    # Create the root window
    window = Tk()
    window.title(f"Hospital Information System - {user_data['role']}: {user_data['username']}")
    window.geometry("500x700")

    try:
        icon = PhotoImage(file='qphn.jpg')
        window.iconphoto(True, icon)
    except:
        pass

    # Header
    header = Label(window, text="Hospital Information System", font=("Arial", 20, "bold"), fg="darkblue")
    header.pack(pady=20)

    # User info
    user_label = Label(window, text=f"Logged in as: {user_data['username']} ({user_data['role']})", 
                      font=("Arial", 10), fg="green")
    user_label.pack(pady=5)

    # Menu Buttons
    button_frame = Frame(window)
    button_frame.pack(pady=20)

    # Patient Registration Button
    reg_btn = Button(button_frame, text="Patient Registration", command=open_patient_registration,
                    bg="blue", fg="white", font=("Arial", 14, "bold"), width=25, padx=20, pady=15)
    reg_btn.pack(pady=10)

    # Search Patient Button
    search_btn = Button(button_frame, text="Search Patient", command=open_search_patient,
                       bg="green", fg="white", font=("Arial", 14, "bold"), width=25, padx=20, pady=15)
    search_btn.pack(pady=10)

    # Patient List Button
    list_btn = Button(button_frame, text="Patient List", command=open_patient_list,
                     bg="purple", fg="white", font=("Arial", 14, "bold"), width=25, padx=20, pady=15)
    list_btn.pack(pady=10)

    # User Registration Button (Admin only)
    if user_data.get('role') == 'Administrator':
        user_reg_btn = Button(button_frame, text="User Registration", command=open_user_registration,
                             bg="orange", fg="white", font=("Arial", 14, "bold"), width=25, padx=20, pady=15)
        user_reg_btn.pack(pady=10)
        
        user_list_btn = Button(button_frame, text="User Management", command=open_user_management,
                              bg="teal", fg="white", font=("Arial", 14, "bold"), width=25, padx=20, pady=15)
        user_list_btn.pack(pady=10)

    # Exit Button
    exit_btn = Button(button_frame, text="Exit", command=window.quit,
                     bg="red", fg="white", font=("Arial", 14, "bold"), width=25, padx=20, pady=15)
    exit_btn.pack(pady=10)

    # Run the event loop
    window.mainloop()

# ============== PATIENT DATA MANAGEMENT ==============
class PatientDatabase:
    STARTING_ID = 30000
    
    def __init__(self):
        self.db = DatabaseConnection()
        if not self.db.connect():
            raise Exception("Failed to connect to database")
        self.db.create_tables()
    
    def generate_next_patient_id(self):
        """Generate the next available patient ID starting from 30000"""
        query = "SELECT MAX(CAST(patient_id AS UNSIGNED)) FROM patients WHERE CAST(patient_id AS UNSIGNED) >= %s"
        cursor = self.db.execute_query(query, (self.STARTING_ID,))
        
        if cursor:
            result = cursor.fetchone()
            if result and result[0]:
                next_id = int(result[0]) + 1
            else:
                next_id = self.STARTING_ID
        else:
            next_id = self.STARTING_ID
        
        return str(next_id)
    
    def add_patient(self, patient_id, data):
        """Add a new patient to the database"""
        insert_query = """
        INSERT INTO patients (patient_id, first_name, last_name, age, gender, phone, email, address, medical_history, registration_date) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        
        try:
            self.db.execute_query(insert_query, (
                patient_id,
                data.get('first_name', ''),
                data.get('last_name', ''),
                data.get('age', ''),
                data.get('gender', ''),
                data.get('phone', ''),
                data.get('email', ''),
                data.get('address', ''),
                data.get('medical_history', '')
            ))
            self.db.commit()
            return True
        except Error as e:
            print(f"Error adding patient: {e}")
            return False
    
    def get_patient(self, patient_id):
        """Get patient by ID"""
        query = "SELECT * FROM patients WHERE patient_id = %s"
        cursor = self.db.execute_query(query, (patient_id,))
        
        if cursor:
            result = cursor.fetchone()
            if result:
                return {
                    'id': result[0],
                    'patient_id': result[1],
                    'first_name': result[2],
                    'last_name': result[3],
                    'age': result[4],
                    'gender': result[5],
                    'phone': result[6],
                    'email': result[7],
                    'address': result[8],
                    'medical_history': result[9],
                    'registration_date': str(result[10])
                }
        return None
    
    def get_all_patients(self):
        """Get all patients"""
        query = "SELECT * FROM patients ORDER BY registration_date DESC"
        cursor = self.db.execute_query(query)
        
        patients = {}
        if cursor:
            for row in cursor.fetchall():
                patient_id = row[1]  # patient_id column
                patients[patient_id] = {
                    'id': row[0],
                    'patient_id': row[1],
                    'first_name': row[2],
                    'last_name': row[3],
                    'age': row[4],
                    'gender': row[5],
                    'phone': row[6],
                    'email': row[7],
                    'address': row[8],
                    'medical_history': row[9],
                    'registration_date': str(row[10])
                }
        return patients
    
    def patient_exists(self, patient_id):
        """Check if patient exists"""
        query = "SELECT COUNT(*) FROM patients WHERE patient_id = %s"
        cursor = self.db.execute_query(query, (patient_id,))
        
        if cursor:
            return cursor.fetchone()[0] > 0
        return False

# ============== VALIDATION FUNCTIONS ==============
def validate_phone(phone):
    pattern = r'^\d{1}$'
    return re.match(pattern, phone.replace('-', '').replace(' ', ''))

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email)

def validate_age(age):
    try:
        age_int = int(age)
        return 0 < age_int < 150
    except ValueError:
        return False

def validate_username(username):
    """Validate username: 3-20 chars, alphanumeric + underscore only"""
    if not username or len(username) < 3 or len(username) > 20:
        return False
    return re.match(r'^[a-zA-Z0-9_]+$', username) is not None

def validate_password(password):
    """Validate password: minimum 6 characters"""
    return len(password) >= 6

# ============== PATIENT REGISTRATION WINDOW ==============
def open_patient_registration():
    reg_window = Toplevel(window)
    reg_window.title("Patient Registration")
    reg_window.geometry("500x700")
    reg_window.resizable(False, False)
    
    db = PatientDatabase()
    
    # Title Label
    title = Label(reg_window, text="Patient Registration Form", font=("Arial", 18, "bold"), fg="darkblue")
    title.pack(pady=20)
    
    # Main Frame with Scrollbar
    main_frame = Frame(reg_window)
    main_frame.pack(fill=BOTH, expand=True, padx=20, pady=10)
    
    # Auto-generated Patient ID (Display Only)
    Label(main_frame, text="Patient ID:", font=("Arial", 11, "bold")).grid(row=0, column=0, sticky=W, pady=10)
    patient_id_label = Label(main_frame, text="", font=("Arial", 11, "bold"), fg="blue", bg="lightgray", relief="sunken", width=30, anchor=W)
    patient_id_label.grid(row=0, column=1, padx=10, pady=10)
    
    # Generate and display next patient ID
    next_id = db.generate_next_patient_id()
    patient_id_label.config(text=next_id)
    
    # Full Name
    Label(main_frame, text="Full Name:", font=("Arial", 11, "bold")).grid(row=1, column=0, sticky=W, pady=10)
    name_entry = Entry(main_frame, width=30, font=("Arial", 11))
    name_entry.grid(row=1, column=1, padx=10, pady=10)
    
    # Age
    Label(main_frame, text="Age:", font=("Arial", 11, "bold")).grid(row=2, column=0, sticky=W, pady=10)
    age_entry = Entry(main_frame, width=30, font=("Arial", 11))
    age_entry.grid(row=2, column=1, padx=10, pady=10)
    
    # Gender
    Label(main_frame, text="Gender:", font=("Arial", 11, "bold")).grid(row=3, column=0, sticky=W, pady=10)
    gender_var = StringVar(value="Male")
    gender_combo = ttk.Combobox(main_frame, textvariable=gender_var, values=["Male", "Female", "Other"], width=27, state="readonly")
    gender_combo.grid(row=3, column=1, padx=10, pady=10)
    
    # Phone Number
    Label(main_frame, text="Phone Number:", font=("Arial", 11, "bold")).grid(row=4, column=0, sticky=W, pady=10)
    phone_entry = Entry(main_frame, width=30, font=("Arial", 11))
    phone_entry.grid(row=4, column=1, padx=10, pady=10)
    phone_entry.insert(0, "10 digits required")
    
    # Email
    Label(main_frame, text="Email:", font=("Arial", 11, "bold")).grid(row=5, column=0, sticky=W, pady=10)
    email_entry = Entry(main_frame, width=30, font=("Arial", 11))
    email_entry.grid(row=5, column=1, padx=10, pady=10)
    
    # Address
    Label(main_frame, text="Address:", font=("Arial", 11, "bold")).grid(row=6, column=0, sticky=W, pady=10)
    address_entry = Entry(main_frame, width=30, font=("Arial", 11))
    address_entry.grid(row=6, column=1, padx=10, pady=10)
    
    # Medical Conditions
    Label(main_frame, text="Medical Conditions:", font=("Arial", 11, "bold")).grid(row=7, column=0, sticky=NW, pady=10)
    conditions_entry = Text(main_frame, width=30, height=3, font=("Arial", 11))
    conditions_entry.grid(row=7, column=1, padx=10, pady=10)
    
    # Medications
    Label(main_frame, text="Current Medications:", font=("Arial", 11, "bold")).grid(row=8, column=0, sticky=NW, pady=10)
    medications_entry = Text(main_frame, width=30, height=3, font=("Arial", 11))
    medications_entry.grid(row=8, column=1, padx=10, pady=10)
    
    # Emergency Contact
    Label(main_frame, text="Emergency Contact:", font=("Arial", 11, "bold")).grid(row=9, column=0, sticky=W, pady=10)
    emergency_entry = Entry(main_frame, width=30, font=("Arial", 11))
    emergency_entry.grid(row=9, column=1, padx=10, pady=10)
    
    def register_patient():
        # Get auto-generated patient ID
        patient_id = patient_id_label.cget("text")
        
        # Validation
        if not name_entry.get().strip():
            messagebox.showerror("Error", "Full Name is required")
            return
        
        if not validate_age(age_entry.get()):
            messagebox.showerror("Error", "Please enter a valid age (1-149)")
            return
        
        if not validate_phone(phone_entry.get()):
            messagebox.showerror("Error", "Please enter a valid 10-digit phone number")
            return
        
        if email_entry.get().strip() and not validate_email(email_entry.get()):
            messagebox.showerror("Error", "Please enter a valid email address")
            return
        
        # Create patient record
        full_name = name_entry.get().strip()
        name_parts = full_name.split(maxsplit=1)
        first_name = name_parts[0] if len(name_parts) > 0 else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        
        patient_data = {
            "first_name": first_name,
            "last_name": last_name,
            "age": age_entry.get(),
            "gender": gender_var.get(),
            "phone": phone_entry.get(),
            "email": email_entry.get(),
            "address": address_entry.get(),
            "medical_history": conditions_entry.get("1.0", END).strip()
        }
        
        db.add_patient(patient_id, patient_data)
        messagebox.showinfo("Success", f"Patient {name_entry.get()} registered successfully!\nPatient ID: {patient_id}")
        
        # Generate new patient ID for next registration
        next_id = db.generate_next_patient_id()
        patient_id_label.config(text=next_id)
        
        # Clear form
        name_entry.delete(0, END)
        age_entry.delete(0, END)
        phone_entry.delete(0, END)
        email_entry.delete(0, END)
        address_entry.delete(0, END)
        conditions_entry.delete("1.0", END)
    
    # Button Frame
    button_frame = Frame(reg_window)
    button_frame.pack(pady=20)
    
    register_btn = Button(button_frame, text="Register Patient", command=register_patient, 
                         bg="green", fg="white", font=("Arial", 12, "bold"), width=20, padx=10, pady=10)
    register_btn.pack(side=LEFT, padx=5)
    
    close_btn = Button(button_frame, text="Close", command=reg_window.destroy, 
                      bg="red", fg="white", font=("Arial", 12, "bold"), width=20, padx=10, pady=10)
    close_btn.pack(side=LEFT, padx=5)

# ============== SEARCH PATIENT WINDOW ==============
def open_search_patient():
    search_window = Toplevel(window)
    search_window.title("Search Patient")
    search_window.geometry("600x500")
    search_window.resizable(False, False)
    
    db = PatientDatabase()
    
    # Title Label
    title = Label(search_window, text="Search Patient Records", font=("Arial", 18, "bold"), fg="darkblue")
    title.pack(pady=20)
    
    # Search Frame
    search_frame = Frame(search_window)
    search_frame.pack(pady=10)
    
    Label(search_frame, text="Search by Patient ID or Name:", font=("Arial", 12, "bold")).grid(row=0, column=0, padx=10, pady=10)
    search_entry = Entry(search_frame, width=30, font=("Arial", 12))
    search_entry.grid(row=0, column=1, padx=10, pady=10)
    
    # Results Text Area
    results_frame = Frame(search_window)
    results_frame.pack(fill=BOTH, expand=True, padx=20, pady=10)
    
    results_text = Text(results_frame, wrap=WORD, font=("Arial", 10), height=15)
    scrollbar = Scrollbar(results_frame, command=results_text.yview)
    results_text.config(yscrollcommand=scrollbar.set)
    
    results_text.pack(side=LEFT, fill=BOTH, expand=True)
    scrollbar.pack(side=RIGHT, fill=Y)
    
    def search_patient():
        search_term = search_entry.get().strip().lower()
        results_text.delete(1.0, END)
        
        if not search_term:
            messagebox.showwarning("Warning", "Please enter a search term")
            return
        
        found = False
        for patient_id, patient_data in db.get_all_patients().items():
            first_name = patient_data.get('first_name', '')
            last_name = patient_data.get('last_name', '')
            full_name = f"{first_name} {last_name}".strip()
            
            if (search_term in patient_id.lower() or 
                search_term in full_name.lower()):
                
                results_text.insert(END, f"Patient ID: {patient_id}\n")
                results_text.insert(END, f"Name: {full_name if full_name else 'N/A'}\n")
                results_text.insert(END, f"Age: {patient_data.get('age', 'N/A')}\n")
                results_text.insert(END, f"Gender: {patient_data.get('gender', 'N/A')}\n")
                results_text.insert(END, f"Phone: {patient_data.get('phone', 'N/A')}\n")
                results_text.insert(END, f"Email: {patient_data.get('email', 'N/A')}\n")
                results_text.insert(END, f"Address: {patient_data.get('address', 'N/A')}\n")
                results_text.insert(END, f"Medical History: {patient_data.get('medical_history', 'None')}\n")
                results_text.insert(END, f"Registration Date: {patient_data.get('registration_date', 'N/A')}\n")
                results_text.insert(END, "="*50 + "\n\n")
                found = True
        
        if not found:
            results_text.insert(END, f"No patients found matching '{search_term}'")
    
    def clear_results():
        results_text.delete(1.0, END)
        search_entry.delete(0, END)
    
    # Button Frame
    button_frame = Frame(search_window)
    button_frame.pack(pady=20)
    
    search_btn = Button(button_frame, text="Search", command=search_patient, 
                       bg="green", fg="white", font=("Arial", 12, "bold"), width=15, padx=10, pady=10)
    search_btn.pack(side=LEFT, padx=5)
    
    clear_btn = Button(button_frame, text="Clear", command=clear_results, 
                      bg="orange", fg="white", font=("Arial", 12, "bold"), width=15, padx=10, pady=10)
    clear_btn.pack(side=LEFT, padx=5)
    
    close_btn = Button(button_frame, text="Close", command=search_window.destroy, 
                      bg="red", fg="white", font=("Arial", 12, "bold"), width=15, padx=10, pady=10)
    close_btn.pack(side=LEFT, padx=5)

# ============== PATIENT LIST WINDOW ==============
def open_patient_list():
    list_window = Toplevel(window)
    list_window.title("Patient List")
    list_window.geometry("800x600")
    list_window.resizable(True, True)
    
    db = PatientDatabase()
    
    # Title Label
    title = Label(list_window, text="All Registered Patients", font=("Arial", 18, "bold"), fg="darkblue")
    title.pack(pady=20)
    
    # Treeview Frame
    tree_frame = Frame(list_window)
    tree_frame.pack(fill=BOTH, expand=True, padx=20, pady=10)
    
    # Create Treeview
    columns = ("ID", "Name", "Age", "Gender", "Phone", "Email")
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=20)
    
    # Define headings
    tree.heading("ID", text="Patient ID")
    tree.heading("Name", text="Full Name")
    tree.heading("Age", text="Age")
    tree.heading("Gender", text="Gender")
    tree.heading("Phone", text="Phone")
    tree.heading("Email", text="Email")
    
    # Define column widths
    tree.column("ID", width=100)
    tree.column("Name", width=200)
    tree.column("Age", width=50)
    tree.column("Gender", width=80)
    tree.column("Phone", width=120)
    tree.column("Email", width=200)
    
    # Add scrollbar
    scrollbar = ttk.Scrollbar(tree_frame, orient=VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    
    tree.pack(side=LEFT, fill=BOTH, expand=True)
    scrollbar.pack(side=RIGHT, fill=Y)
    
    # Details Text Area
    details_frame = Frame(list_window)
    details_frame.pack(fill=BOTH, expand=True, padx=20, pady=10)
    
    Label(details_frame, text="Patient Details:", font=("Arial", 12, "bold")).pack(anchor=W)
    
    details_text = Text(details_frame, wrap=WORD, font=("Arial", 10), height=8)
    details_scrollbar = Scrollbar(details_frame, command=details_text.yview)
    details_text.config(yscrollcommand=details_scrollbar.set)
    
    details_text.pack(side=LEFT, fill=BOTH, expand=True)
    details_scrollbar.pack(side=RIGHT, fill=Y)
    
    def load_patients():
        # Clear existing items
        for item in tree.get_children():
            tree.delete(item)
        
        patients = db.get_all_patients()
        if not patients:
            tree.insert("", END, values=("No patients", "registered", "yet", "", "", ""))
            return
        
        for patient_id, patient_data in patients.items():
            first_name = patient_data.get('first_name', '')
            last_name = patient_data.get('last_name', '')
            full_name = f"{first_name} {last_name}".strip()
            tree.insert("", END, values=(
                patient_id,
                full_name if full_name else 'N/A',
                patient_data.get('age', 'N/A'),
                patient_data.get('gender', 'N/A'),
                patient_data.get('phone', 'N/A'),
                patient_data.get('email', 'N/A')
            ))
    
    def on_tree_select(event):
        selected_item = tree.selection()
        if selected_item:
            item = tree.item(selected_item)
            patient_id = item['values'][0]
            
            if patient_id == "No patients":
                details_text.delete(1.0, END)
                details_text.insert(END, "No patient details available")
                return
            
            patient_data = db.get_patient(patient_id)
            if patient_data:
                details_text.delete(1.0, END)
                details_text.insert(END, f"Patient ID: {patient_id}\n")
                first_name = patient_data.get('first_name', '')
                last_name = patient_data.get('last_name', '')
                full_name = f"{first_name} {last_name}".strip()
                details_text.insert(END, f"Name: {full_name if full_name else 'N/A'}\n")
                details_text.insert(END, f"Age: {patient_data.get('age', 'N/A')}\n")
                details_text.insert(END, f"Gender: {patient_data.get('gender', 'N/A')}\n")
                details_text.insert(END, f"Phone: {patient_data.get('phone', 'N/A')}\n")
                details_text.insert(END, f"Email: {patient_data.get('email', 'N/A')}\n")
                details_text.insert(END, f"Address: {patient_data.get('address', 'N/A')}\n")
                details_text.insert(END, f"Medical History: {patient_data.get('medical_history', 'None')}\n")
                details_text.insert(END, f"Registration Date: {patient_data.get('registration_date', 'N/A')}\n")
                details_text.insert(END, f"Registration Date: {patient_data.get('registration_date', 'N/A')}\n")
    
    tree.bind('<<TreeviewSelect>>', on_tree_select)
    
    # Button Frame
    button_frame = Frame(list_window)
    button_frame.pack(pady=20)
    
    refresh_btn = Button(button_frame, text="Refresh List", command=load_patients, 
                        bg="blue", fg="white", font=("Arial", 12, "bold"), width=15, padx=10, pady=10)
    refresh_btn.pack(side=LEFT, padx=5)
    
    close_btn = Button(button_frame, text="Close", command=list_window.destroy, 
                      bg="red", fg="white", font=("Arial", 12, "bold"), width=15, padx=10, pady=10)
    close_btn.pack(side=LEFT, padx=5)
    
    # Load patients on startup
    load_patients()

# ============== APPLICATION STARTUP ==============
if __name__ == "__main__":
    create_login_window()
