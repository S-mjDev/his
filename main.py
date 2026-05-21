from tkinter import *
from tkinter import messagebox, ttk
import json
import os
from datetime import datetime
import re
import hashlib
import mysql.connector
# FORCE PYINSTALLER TO TRACK THE AUTHENTICATION PLUGINS
from mysql.connector.plugins import mysql_native_password
from mysql.connector.plugins import caching_sha2_password
from mysql.connector import Error

try:
    from tkcalendar import DateEntry
except ImportError:
    DateEntry = None

# ============== DATABASE CONFIGURATION ==============
class DatabaseConnection:
    # Initialize the instance.
    def __init__(self):
        self.host = "192.168.1.88"
        self.database = "his_db"
        self.user = "root"
        self.password = "root"
        self.connection = None



    
    # Open a connection to the MySQL database.
    def connect(self):
        """Establish database connection"""
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                database=self.database,
                user=self.user,
                password=self.password,
                auth_plugin='mysql_native_password',
                use_pure=True
            )
            if self.connection.is_connected():
                return True
        except Error as e:
            print(f"Error connecting to MySQL: {e}")
            return False
    
    # Close the MySQL database connection.
    def disconnect(self):
        """Close database connection"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
    
    # Run a SQL query and return the cursor object.
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
    
    # Commit the current transaction to the database.
    def commit(self):
        """Commit changes"""
        if self.connection:
            self.connection.commit()
    
    # Create required database tables if they do not exist.
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
            middle_name VARCHAR(50) NOT NULL,
            last_name VARCHAR(50) NOT NULL,
            age INT,
            gender VARCHAR(10),
            birth_date DATE,
            birth_place VARCHAR(100),
            civil_status VARCHAR(20),
            nationality VARCHAR(50),
            registered_by VARCHAR(50),
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
            # Ensure existing schema includes nationality and registered_by columns
            cursor = self.execute_query("SHOW COLUMNS FROM patients LIKE 'nationality'")
            if cursor and not cursor.fetchone():
                self.execute_query("ALTER TABLE patients ADD COLUMN nationality VARCHAR(50)")
            cursor = self.execute_query("SHOW COLUMNS FROM patients LIKE 'registered_by'")
            if cursor and not cursor.fetchone():
                self.execute_query("ALTER TABLE patients ADD COLUMN registered_by VARCHAR(50)")
            self.commit()
            print("Database tables created successfully")
        except Error as e:
            print(f"Error creating tables: {e}")

# ============== USER AUTHENTICATION ==============
class UserDatabase:
    # Initialize the instance.
    def __init__(self):
        self.db = DatabaseConnection()
        if not self.db.connect():
            raise Exception("Failed to connect to database")
        self.db.create_tables()
        self.create_default_admin()
    
    # Hash a password string using SHA-256.
    def hash_password(self, password):
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    # Verify user credentials and return authenticated user data.
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
    
    # Add a new user account to the database.
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
    
    # Retrieve all user accounts from the database.
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
    
    # Create a default administrator account if none exists.
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
    login_window.geometry("420x380")
    login_window.resizable(False, False)
    
    # Center the window
    login_window.eval('tk::PlaceWindow . center')
    
    # Icon
    try:
        icon = PhotoImage(file='qphn.jpg')
        login_window.iconphoto(True, icon)
    except:
        pass
    
    login_window.configure(bg="#eef2f7")

    content_frame = Frame(login_window, bg="white", bd=0, relief=SOLID)
    content_frame.place(relx=0.5, rely=0.5, anchor=CENTER, width=380, height=320)

    header_frame = Frame(content_frame, bg="white")
    header_frame.pack(fill=X, pady=(20, 10))

    Label(header_frame, text="Welcome Back", font=("Arial", 18, "bold"), bg="white", fg="#1b4f72").pack()
    Label(header_frame, text="Enter your credentials to continue", font=("Arial", 11), bg="white", fg="#5d6d7e").pack()

    login_frame = Frame(content_frame, bg="white")
    login_frame.pack(pady=10)

    username_label = Label(login_frame, text="Username", font=("Arial", 11, "bold"), bg="white", fg="#34495e")
    username_label.grid(row=0, column=0, pady=10, padx=10, sticky=W)
    username_entry = Entry(login_frame, width=28, font=("Arial", 12), bd=1, relief=SOLID)
    username_entry.grid(row=0, column=1, pady=10, padx=10)
    username_entry.focus()

    password_label = Label(login_frame, text="Password", font=("Arial", 11, "bold"), bg="white", fg="#34495e")
    password_label.grid(row=1, column=0, pady=10, padx=10, sticky=W)
    password_entry = Entry(login_frame, width=28, font=("Arial", 12), bd=1, relief=SOLID, show="*")
    password_entry.grid(row=1, column=1, pady=10, padx=10)

    button_frame = Frame(content_frame, bg="white")
    button_frame.pack(pady=15)

    # Handle the login button click and authenticate the user.
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

    login_btn = Button(button_frame, text="Login", command=login,
                       bg="#2e86c1", fg="white", font=("Arial", 12, "bold"),
                       width=28, padx=10, pady=8, bd=0, relief=FLAT)
    login_btn.pack()

    login_window.bind('<Return>', lambda event: login())

    footer_label = Label(content_frame, text="Secure access to hospital management", 
                         font=("Arial", 9), bg="white", fg="#95a5a6")
    footer_label.pack(side=BOTTOM, pady=12)

    login_window.mainloop()

# ============== USER REGISTRATION WINDOW ==============
def build_user_registration_page(parent):
    frame = Frame(parent, bg="#f7fbff")

    Label(frame, text="Add New User", font=("Arial", 20, "bold"), fg="#1b4f72", bg="#f7fbff").pack(pady=20)

    main_frame = Frame(frame, bg="#f7fbff")
    main_frame.pack(fill=BOTH, expand=True, padx=20, pady=10)

    Label(main_frame, text="Username:", font=("Arial", 12, "bold"), bg="#f7fbff").grid(row=0, column=0, sticky=W, pady=10)
    username_entry = Entry(main_frame, width=30, font=("Arial", 12))
    username_entry.grid(row=0, column=1, padx=10, pady=10)

    Label(main_frame, text="Password:", font=("Arial", 12, "bold"), bg="#f7fbff").grid(row=1, column=0, sticky=W, pady=10)
    password_entry = Entry(main_frame, width=30, font=("Arial", 12), show="*")
    password_entry.grid(row=1, column=1, padx=10, pady=10)

    Label(main_frame, text="Confirm Password:", font=("Arial", 12, "bold"), bg="#f7fbff").grid(row=2, column=0, sticky=W, pady=10)
    confirm_password_entry = Entry(main_frame, width=30, font=("Arial", 12), show="*")
    confirm_password_entry.grid(row=2, column=1, padx=10, pady=10)

    Label(main_frame, text="Role:", font=("Arial", 12, "bold"), bg="#f7fbff").grid(row=3, column=0, sticky=W, pady=10)
    role_var = StringVar(value="Staff")
    role_combo = ttk.Combobox(main_frame, textvariable=role_var,
                              values=["Staff", "Administrator"], width=27, state="readonly")
    role_combo.grid(row=3, column=1, padx=10, pady=10)

    info_label = Label(main_frame, text="", font=("Arial", 10), fg="gray", bg="#f7fbff")
    info_label.grid(row=4, column=0, columnspan=2, pady=10)

    # Clear the input fields on the new user form.
    def clear_user_form():
        username_entry.delete(0, END)
        password_entry.delete(0, END)
        confirm_password_entry.delete(0, END)
        role_var.set("Staff")
        info_label.config(text="")

    # Validate and submit the new user registration data.
    def register_user():
        username = username_entry.get().strip()
        password = password_entry.get()
        confirm_password = confirm_password_entry.get()
        role = role_var.get()

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
            clear_user_form()
        else:
            messagebox.showerror("Error", message)

    button_frame = Frame(frame, bg="#f7fbff")
    button_frame.pack(pady=20)

    register_btn = Button(button_frame, text="Register User", command=register_user,
                          bg="#1f618d", fg="white", font=("Arial", 12, "bold"), width=16, padx=10, pady=10)
    register_btn.pack(side=LEFT, padx=6)

    reset_btn = Button(button_frame, text="Clear", command=clear_user_form,
                       bg="#85929e", fg="white", font=("Arial", 12, "bold"), width=12, padx=10, pady=10)
    reset_btn.pack(side=LEFT, padx=6)

    return frame


# Show the user registration page in the application.
def open_user_registration():
    if 'user_registration' not in pages:
        pages['user_registration'] = build_user_registration_page(page_container)
    show_page('user_registration')

# ============== USER MANAGEMENT WINDOW ==============
def build_user_management_page(parent):
    frame = Frame(parent, bg="#f7fbff")

    Label(frame, text="User Management", font=("Arial", 20, "bold"), fg="#1b4f72", bg="#f7fbff").pack(pady=20)

    tree_frame = Frame(frame, bg="#f7fbff")
    tree_frame.pack(fill=BOTH, expand=True, padx=20, pady=10)

    columns = ("Username", "Role", "Created Date")
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)
    tree.heading("Username", text="Username")
    tree.heading("Role", text="Role")
    tree.heading("Created Date", text="Created Date")
    tree.column("Username", width=180)
    tree.column("Role", width=140)
    tree.column("Created Date", width=220)

    scrollbar = ttk.Scrollbar(tree_frame, orient=VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    tree.pack(side=LEFT, fill=BOTH, expand=True)
    scrollbar.pack(side=RIGHT, fill=Y)

    details_frame = Frame(frame, bg="#f7fbff")
    details_frame.pack(fill=BOTH, expand=True, padx=20, pady=10)

    Label(details_frame, text="User Details:", font=("Arial", 12, "bold"), bg="#f7fbff").pack(anchor=W)
    details_text = Text(details_frame, wrap=WORD, font=("Arial", 10), height=6)
    details_scrollbar = Scrollbar(details_frame, command=details_text.yview)
    details_text.config(yscrollcommand=details_scrollbar.set)
    details_text.pack(side=LEFT, fill=BOTH, expand=True)
    details_scrollbar.pack(side=RIGHT, fill=Y)

    # Load user records into the user management table.
    def load_users():
        for item in tree.get_children():
            tree.delete(item)
        user_db = UserDatabase()
        users = user_db.get_all_users()
        if not users:
            tree.insert("", END, values=("No users", "found", ""))
            return
        for username, user_data in users.items():
            tree.insert("", END, values=(username, user_data.get('role', 'N/A'), user_data.get('created_date', 'N/A')))

    # Show details for the selected patient in the list page.
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
            user_data = user_db.get_all_users().get(username)
            if user_data:
                details_text.delete(1.0, END)
                details_text.insert(END, f"Username: {username}\n")
                details_text.insert(END, f"Role: {user_data.get('role', 'N/A')}\n")
                details_text.insert(END, f"Created Date: {user_data.get('created_date', 'N/A')}\n")
                details_text.insert(END, f"Last Login: {user_data.get('last_login', 'Never')}\n")

    tree.bind('<<TreeviewSelect>>', on_tree_select)

    button_frame = Frame(frame, bg="#f7fbff")
    button_frame.pack(pady=20)

    refresh_btn = Button(button_frame, text="Refresh List", command=load_users,
                         bg="#1f618d", fg="white", font=("Arial", 12, "bold"), width=15, padx=10, pady=10)
    refresh_btn.pack(side=LEFT, padx=6)

    load_users()
    return frame


# Display the user management page.
def open_user_management():
    if 'user_management' not in pages:
        pages['user_management'] = build_user_management_page(page_container)
    show_page('user_management')

# ============== MAIN APPLICATION ==============

window = None
page_container = None
pages = {}
page_refreshers = {}

# Remove all widgets from a frame.
def clear_frame(frame):
    for widget in frame.winfo_children():
        widget.destroy()

# Hide every page in the main page container.
def hide_all_pages():
    for page in pages.values():
        page.pack_forget()

# Show a specific page in the main application container.
def show_page(page_name):
    hide_all_pages()
    page = pages.get(page_name)
    if page:
        page.pack(fill=BOTH, expand=True)


# Collect dashboard summary numbers and recent patient records.
def create_dashboard_summary(user_data):
    db = PatientDatabase()
    patients = db.get_all_patients()
    total_patients = len(patients)
    recent_patients = sorted(
        patients.values(),
        key=lambda item: item.get('registration_date') or '',
        reverse=True
    )[:10]
    total_users = 0
    if user_data.get('role') == 'Administrator':
        user_db = UserDatabase()
        total_users = len(user_db.get_all_users())
    return total_patients, total_users, recent_patients


# Create a dashboard summary card widget.
def create_card(parent, title, value, subtitle):
    card = Frame(parent, bg="white", bd=1, relief=SOLID, padx=16, pady=14)
    Label(card, text=title, font=("Arial", 11, "bold"), bg="white", fg="#2c3e50").pack(anchor=W)
    Label(card, text=value, font=("Arial", 22, "bold"), bg="white", fg="#1f618d").pack(anchor=W, pady=(8, 2))
    Label(card, text=subtitle, font=("Arial", 10), bg="white", fg="#566573").pack(anchor=W)
    return card


# Build the main dashboard page layout and summary table.
def build_dashboard_page(parent, user_data):
    frame = Frame(parent, bg="#f7fbff")
    total_patients, total_users, recent_patients = create_dashboard_summary(user_data)

    top_cards = Frame(frame, bg="#f7fbff")
    top_cards.pack(fill=X, pady=(0, 12), padx=20)

    card1 = create_card(top_cards, "Total Patients", str(total_patients), "Registered in the system")
    card1.pack(side=LEFT, expand=True, fill=X, padx=6)

    if user_data.get('role') == 'Administrator':
        card2 = create_card(top_cards, "Total Users", str(total_users), "Active user accounts")
    else:
        card2 = create_card(top_cards, "Role", user_data.get('role', 'Staff'), "User permissions")
    card2.pack(side=LEFT, expand=True, fill=X, padx=6)

    card3 = create_card(top_cards, "Recent Activity", f"{len(recent_patients)} records", "Latest patient registrations")
    card3.pack(side=LEFT, expand=True, fill=X, padx=6)

    table_frame = Frame(frame, bg="#f7fbff", bd=1, relief=SOLID)
    table_frame.pack(fill=BOTH, expand=True, padx=20, pady=(0, 20))

    Label(table_frame, text="Recent Patients", font=("Arial", 16, "bold"), bg="#f7fbff", fg="#1b2631").pack(anchor=W, padx=16, pady=(16, 8))

    columns = ("ID", "Name", "Age", "Gender", "Registered")
    tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
    tree.heading("ID", text="Patient ID")
    tree.heading("Name", text="Name")
    tree.heading("Age", text="Age")
    tree.heading("Gender", text="Gender")
    tree.heading("Registered", text="Registered")

    tree.column("ID", width=110, anchor=W)
    tree.column("Name", width=220, anchor=W)
    tree.column("Age", width=60, anchor=CENTER)
    tree.column("Gender", width=90, anchor=CENTER)
    tree.column("Registered", width=160, anchor=W)

    scrollbar = ttk.Scrollbar(table_frame, orient=VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    tree.pack(side=LEFT, fill=BOTH, expand=True, padx=(16, 0), pady=(0, 16))
    scrollbar.pack(side=RIGHT, fill=Y, pady=(0, 16), padx=(0, 16))

    for patient_data in recent_patients:
        patient_id = patient_data.get('patient_id', 'N/A')
        first_name = patient_data.get('first_name', '')
        last_name = patient_data.get('last_name', '')
        full_name = f"{first_name} {last_name}".strip().upper()
        tree.insert("", END, values=(
            patient_id,
            full_name,
            patient_data.get('age', 'N/A'),
            patient_data.get('gender', 'N/A').upper(),
            patient_data.get('registered_by', 'N/A')
        ))

    page_refreshers['dashboard'] = lambda: refresh_dashboard_frame(user_data)
    return frame


# Rebuild and refresh the dashboard page content.
def refresh_dashboard_frame(user_data):
    if 'dashboard' in pages:
        pages['dashboard'].destroy()
        pages['dashboard'] = build_dashboard_page(page_container, user_data)


# Refresh the dashboard and display it.
def refresh_dashboard(user_data):
    refresh_dashboard_frame(user_data)
    show_page('dashboard')


# Refresh the patient list page if already built.
def refresh_patient_list():
    refresher = page_refreshers.get('patient_list')
    if refresher:
        refresher()


# Open or refresh the dashboard page.
def open_dashboard(user_data):
    if 'dashboard' not in pages:
        pages['dashboard'] = build_dashboard_page(page_container, user_data)
    else:
        refresher = page_refreshers.get('dashboard')
        if refresher:
            refresher()
    show_page('dashboard')


# Open or refresh the patient list page.
def open_patient_list():
    if 'patient_list' not in pages:
        pages['patient_list'] = build_patient_list_page(page_container)
    else:
        refresh_patient_list()
    show_page('patient_list')


# Create the main application window and navigation layout.
def create_main_application(user_data):
    global window, page_container

    window = Tk()
    window.title(f"Hospital Information System - {user_data['role']}: {user_data['username']}")
    window.geometry("1920x1080")
    window.configure(bg="#e9eff5")
    window.resizable(True, True)

    try:
        icon = PhotoImage(file='qphn.jpg')
        window.iconphoto(True, icon)
    except:
        pass

    menu_bar = Menu(window)
    file_menu = Menu(menu_bar, tearoff=0)
    file_menu.add_command(label="Dashboard", command=lambda: open_dashboard(user_data))
    file_menu.add_command(label="Patient Registration", command=lambda: open_patient_registration(user_data))
    file_menu.add_command(label="Search Patient", command=open_search_patient)
    file_menu.add_command(label="Patient List", command=open_patient_list)
    if user_data.get('role') == 'Administrator':
        file_menu.add_separator()
        file_menu.add_command(label="User Registration", command=open_user_registration)
        file_menu.add_command(label="User Management", command=open_user_management)
    file_menu.add_separator()
    file_menu.add_command(label="Exit", command=window.quit)
    menu_bar.add_cascade(label="File", menu=file_menu)

    view_menu = Menu(menu_bar, tearoff=0)
    view_menu.add_command(label="Refresh Dashboard", command=lambda: refresh_dashboard(user_data))
    menu_bar.add_cascade(label="View", menu=view_menu)

    help_menu = Menu(menu_bar, tearoff=0)
    help_menu.add_command(label="About", command=lambda: messagebox.showinfo(
        "About",
        "Hospital Information System\nElegant dashboard design with quick access controls and patient summaries."
    ))
    menu_bar.add_cascade(label="Help", menu=help_menu)
    window.config(menu=menu_bar)

    header_frame = Frame(window, bg="#e9eff5")
    header_frame.pack(fill=X, padx=20, pady=(18, 6))

    Label(header_frame, text="Hospital Information System", font=("Arial", 26, "bold"), bg="#e9eff5", fg="#1b4f72").pack(anchor=W)
    Label(header_frame, text="Welcome to your dashboard. Use the menu on the left to navigate quickly.",
          font=("Arial", 12), bg="#e9eff5", fg="#566573").pack(anchor=W, pady=(4, 0))
    Label(header_frame, text=f"Logged in as: {user_data['username']} ({user_data['role']})",
          font=("Arial", 10, "italic"), bg="#e9eff5", fg="#117864").pack(anchor=W, pady=(6, 0))

    body_frame = Frame(window, bg="#e9eff5")
    body_frame.pack(fill=BOTH, expand=True, padx=20, pady=10)

    sidebar = Frame(body_frame, bg="#ffffff", bd=1, relief=SOLID)
    sidebar.pack(side=LEFT, fill=Y, padx=(0, 12), pady=0)
    sidebar.pack_propagate(False)
    sidebar.configure(width=260)

    content = Frame(body_frame, bg="#f7fbff")
    content.pack(side=RIGHT, fill=BOTH, expand=True)

    Label(sidebar, text="Quick Menu", font=("Arial", 14, "bold"), bg="#ffffff", fg="#1b2631").pack(anchor=W, padx=20, pady=(20, 8))
    ttk.Separator(sidebar, orient=HORIZONTAL).pack(fill=X, padx=20, pady=(0, 12))

    button_style = {"bg": "#1f618d", "fg": "white", "font": ("Arial", 11, "bold"), "activebackground": "#2874a6", "activeforeground": "white", "bd": 0, "relief": FLAT, "width": 22, "padx": 10, "pady": 10}

    Button(sidebar, text="Dashboard", command=lambda: open_dashboard(user_data), **button_style).pack(pady=6)
    Button(sidebar, text="Patient Registration", command=lambda: open_patient_registration(user_data), **button_style).pack(pady=6)
    Button(sidebar, text="Search Patient", command=open_search_patient, **button_style).pack(pady=6)
    Button(sidebar, text="Patient List", command=open_patient_list, **button_style).pack(pady=6)
    if user_data.get('role') == 'Administrator':
        Button(sidebar, text="User Registration", command=open_user_registration, **button_style).pack(pady=6)
        Button(sidebar, text="User Management", command=open_user_management, **button_style).pack(pady=6)
    Button(sidebar, text="Exit Application", command=window.quit, bg="#c0392b", fg="white",
           font=("Arial", 11, "bold"), activebackground="#e74c3c", activeforeground="white",
           bd=0, relief=FLAT, width=22, padx=10, pady=10).pack(pady=14)

    page_container = Frame(content, bg="#f7fbff")
    page_container.pack(fill=BOTH, expand=True)

    pages['dashboard'] = build_dashboard_page(page_container, user_data)
    pages['patient_registration'] = build_patient_registration_page(page_container, user_data)
    pages['search_patient'] = build_search_patient_page(page_container)
    pages['patient_list'] = build_patient_list_page(page_container)
    if user_data.get('role') == 'Administrator':
        pages['user_registration'] = build_user_registration_page(page_container)
        pages['user_management'] = build_user_management_page(page_container)

    show_page('dashboard')
    window.mainloop()

# ============== PATIENT DATA MANAGEMENT ==============
class PatientDatabase:
    STARTING_ID = 30000
    
    # Initialize the instance.
    def __init__(self):
        self.db = DatabaseConnection()
        if not self.db.connect():
            raise Exception("Failed to connect to database")
        self.db.create_tables()
    
    # Compute the next available patient ID.
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
    
    # Insert a new patient record into the database.
    def add_patient(self, patient_id, data):
        """Add a new patient to the database"""
        insert_query = """
        INSERT INTO patients (patient_id, first_name, middle_name, last_name, age, gender, birth_date, birth_place, civil_status, nationality, registered_by, phone, email, address, medical_history, registration_date) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        
        birth_date_value = data.get('birth_date') or None
        try:
            self.db.execute_query(insert_query, (
                patient_id,
                data.get('first_name', ''),
                data.get('middle_name', ''),
                data.get('last_name', ''),
                data.get('age', ''),
                data.get('gender', ''),
                birth_date_value,
                data.get('birth_place', ''),
                data.get('civil_status', ''),
                data.get('nationality', ''),
                data.get('registered_by', ''),
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
    
    # Map a raw patient row tuple into a dictionary.
    def _map_patient_row(self, row):
        return {
            'id': row[0],
            'patient_id': row[1],
            'first_name': row[2],
            'middle_name': row[3],
            'last_name': row[4],
            'age': row[5],
            'gender': row[6],
            'birth_date': str(row[7]) if row[7] else None,
            'birth_place': row[8],
            'civil_status': row[9],
            'nationality': row[10],
            'registered_by': row[11],
            'phone': row[12],
            'email': row[13],
            'address': row[14],
            'medical_history': row[15],
            'registration_date': str(row[16]) if row[16] else None
        }

    # Retrieve a single patient record by patient ID.
    def get_patient(self, patient_id):
        """Get patient by ID"""
        query = (
            "SELECT id, patient_id, first_name, middle_name, last_name, age, gender, birth_date, "
            "birth_place, civil_status, nationality, registered_by, phone, email, address, medical_history, registration_date "
            "FROM patients WHERE patient_id = %s"
        )
        cursor = self.db.execute_query(query, (patient_id,))
        
        if cursor:
            result = cursor.fetchone()
            if result:
                return self._map_patient_row(result)
        return None

    # Retrieve all patient records ordered by registration date.
    def get_all_patients(self):
        """Get all patients"""
        query = (
            "SELECT id, patient_id, first_name, middle_name, last_name, age, gender, birth_date, "
            "birth_place, civil_status, nationality, registered_by, phone, email, address, medical_history, registration_date "
            "FROM patients ORDER BY registration_date DESC"
        )
        cursor = self.db.execute_query(query)
        
        patients = {}
        if cursor:
            for row in cursor.fetchall():
                patient_id = row[1]
                patients[patient_id] = self._map_patient_row(row)
        return patients

    # Search patient records by patient ID, first name, middle name, or last name.
    def search_patients(self, search_term):
        """Search patients using ID or name."""
        like_term = f"%{search_term}%"
        query = (
            "SELECT id, patient_id, first_name, middle_name, last_name, age, gender, birth_date, "
            "birth_place, civil_status, nationality, registered_by, phone, email, address, medical_history, registration_date "
            "FROM patients "
            "WHERE UPPER(patient_id) LIKE %s "
            "OR UPPER(first_name) LIKE %s "
            "OR UPPER(middle_name) LIKE %s "
            "OR UPPER(last_name) LIKE %s "
            "OR UPPER(CONCAT(first_name, ' ', last_name)) LIKE %s "
            "OR UPPER(CONCAT(last_name, ' ', first_name)) LIKE %s "
            "ORDER BY registration_date DESC"
        )
        cursor = self.db.execute_query(query, (like_term, like_term, like_term, like_term, like_term, like_term))
        patients = {}
        if cursor:
            for row in cursor.fetchall():
                patient_id = row[1]
                patients[patient_id] = self._map_patient_row(row)
        return patients

    # Update an existing patient record.
    def update_patient(self, patient_id, data):
        """Update patient record by ID."""
        query = (
            "UPDATE patients SET first_name = %s, middle_name = %s, last_name = %s, age = %s, "
            "gender = %s, birth_date = %s, birth_place = %s, civil_status = %s, nationality = %s, "
            "phone = %s, email = %s, address = %s, medical_history = %s "
            "WHERE patient_id = %s"
        )
        try:
            self.db.execute_query(query, (
                data.get('first_name', ''),
                data.get('middle_name', ''),
                data.get('last_name', ''),
                data.get('age', ''),
                data.get('gender', ''),
                data.get('birth_date') or None,
                data.get('birth_place', ''),
                data.get('civil_status', ''),
                data.get('nationality', ''),
                data.get('phone', ''),
                data.get('email', ''),
                data.get('address', ''),
                data.get('medical_history', ''),
                patient_id
            ))
            self.db.commit()
            return True
        except Error as e:
            print(f"Error updating patient: {e}")
            return False

    # Delete a patient record by patient ID.
    def delete_patient(self, patient_id):
        """Delete a patient record by ID."""
        try:
            self.db.execute_query("DELETE FROM patients WHERE patient_id = %s", (patient_id,))
            self.db.commit()
            return True
        except Error as e:
            print(f"Error deleting patient: {e}")
            return False

    # Check whether a patient record exists by patient ID.
    def patient_exists(self, patient_id):
        """Check if patient exists"""
        query = "SELECT COUNT(*) FROM patients WHERE patient_id = %s"
        cursor = self.db.execute_query(query, (patient_id,))
        
        if cursor:
            return cursor.fetchone()[0] > 0
        return False

    # Detect duplicate patient records using key identity fields.
    def has_duplicate_patient(self, data):
        """Check if a patient with the same name, birth date, phone, or email already exists."""
        conditions = []
        params = []

        if data.get('first_name') and data.get('last_name') and data.get('birth_date'):
            conditions.append("(first_name = %s AND last_name = %s AND birth_date <=> %s)")
            params.extend([data['first_name'], data['last_name'], data['birth_date']])

        if not conditions:
            return False

        query = f"SELECT COUNT(*) FROM patients WHERE {' OR '.join(conditions)}"
        cursor = self.db.execute_query(query, tuple(params))
        if cursor:
            return cursor.fetchone()[0] > 0
        return False

# ============== VALIDATION FUNCTIONS ==============
def validate_phone(phone):
    pattern = r'^\d{1}$'
    return re.match(pattern, phone.replace('-', '').replace(' ', ''))

# Validate email address format.
def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email)

# Validate that age is within a valid range.
def validate_age(age):
    try:
        age_int = int(age)
        return 0 < age_int < 150
    except ValueError:
        return False

# Validate a date string in YYYY-MM-DD format.
def validate_date(date_text):
    try:
        datetime.strptime(date_text, "%Y-%m-%d")
        return True
    except ValueError:
        return False

# Automatically format birth date input with hyphens.
def format_birthdate_entry(entry_widget):
    current = entry_widget.get()
    digits = re.sub(r'[^0-9]', '', current)
    formatted = digits
    if len(digits) > 4:
        formatted = digits[:4] + '-' + digits[4:]
    if len(digits) > 6:
        formatted = digits[:4] + '-' + digits[4:6] + '-' + digits[6:8]
    formatted = formatted[:10]

    if formatted != current:
        cursor = entry_widget.index(INSERT)
        old_hyphens = current[:cursor].count('-')
        entry_widget.delete(0, END)
        entry_widget.insert(0, formatted)
        new_hyphens = formatted[:cursor].count('-')
        new_cursor = cursor + (new_hyphens - old_hyphens)
        if new_cursor > len(formatted):
            new_cursor = len(formatted)
        entry_widget.icursor(new_cursor)


# Validate username rules for registration.
def validate_username(username):
    """Validate username: 3-20 chars, alphanumeric + underscore only"""
    if not username or len(username) < 3 or len(username) > 20:
        return False
    return re.match(r'^[a-zA-Z0-9_]+$', username) is not None

# Validate password length requirements.
def validate_password(password):
    """Validate password: minimum 6 characters"""
    return len(password) >= 6

# Convert text widget input to uppercase.
def uppercase_text_widget(text_widget):
    current = text_widget.get("1.0", END)
    upper = current.upper()
    if current != upper:
        cursor = text_widget.index(INSERT)
        text_widget.delete("1.0", END)
        text_widget.insert("1.0", upper)
        try:
            text_widget.mark_set(INSERT, cursor)
        except TclError:
            pass

# Convert entry widget input to uppercase.
def uppercase_entry_widget(entry_widget):
    current = entry_widget.get()
    upper = current.upper()
    if current != upper:
        pos = entry_widget.index(INSERT)
        entry_widget.delete(0, END)
        entry_widget.insert(0, upper)
        entry_widget.icursor(pos)

# Build the patient registration page and form.
def build_patient_registration_page(parent, user_data=None):
    frame = Frame(parent, bg="#f7fbff")
    db = PatientDatabase()

    Label(frame, text="Patient Registration Form", font=("Arial", 20, "bold"), fg="#1b4f72", bg="#f7fbff").pack(pady=20)

    canvas = Canvas(frame, bg="#f7fbff", highlightthickness=0)
    scrollbar = ttk.Scrollbar(frame, orient=VERTICAL, command=canvas.yview)
    scrollbar.pack(side=RIGHT, fill=Y)
    canvas.pack(side=LEFT, fill=BOTH, expand=True)
    canvas.configure(yscrollcommand=scrollbar.set)

    content_frame = Frame(canvas, bg="#f7fbff")
    canvas_window = canvas.create_window((0, 0), window=content_frame, anchor="nw")

    # Adjust scrolling region when content changes size.
    def on_content_resize(event):
        canvas.configure(scrollregion=canvas.bbox("all"))

    # Update canvas window width on resize events.
    def on_canvas_resize(event):
        canvas.itemconfig(canvas_window, width=event.width)

    content_frame.bind("<Configure>", on_content_resize)
    canvas.bind("<Configure>", on_canvas_resize)

    # Enable mouse wheel scrolling for the registration form.
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    main_frame = Frame(content_frame, bg="#f7fbff")
    main_frame.pack(fill=BOTH, expand=True, padx=20, pady=10)
    main_frame.grid_columnconfigure(0, weight=1)
    main_frame.grid_columnconfigure(1, weight=1)

    Label(main_frame, text="Patient ID:", font=("Arial", 11, "bold"), bg="#f7fbff").grid(row=0, column=0, sticky=W, pady=10)
    patient_id_label = Label(main_frame, text="", font=("Arial", 11, "bold"), fg="blue", bg="lightgray", relief="sunken", width=30, anchor=W)
    patient_id_label.grid(row=0, column=1, padx=10, pady=10)

    next_id = db.generate_next_patient_id()
    patient_id_label.config(text=next_id)

    Label(main_frame, text="First Name:", font=("Arial", 11, "bold"), bg="#f7fbff").grid(row=1, column=0, sticky=W, pady=10)
    name_entry = Entry(main_frame, width=30, font=("Arial", 11))
    name_entry.grid(row=1, column=1, padx=10, pady=10)
    name_entry.bind('<KeyRelease>', lambda event: uppercase_entry_widget(name_entry))

    Label(main_frame, text="Middle Name:", font=("Arial", 11, "bold"), bg="#f7fbff").grid(row=2, column=0, sticky=W, pady=10)
    middle_name_entry = Entry(main_frame, width=30, font=("Arial", 11))
    middle_name_entry.grid(row=2, column=1, padx=10, pady=10)
    middle_name_entry.bind('<KeyRelease>', lambda event: uppercase_entry_widget(middle_name_entry))

    Label(main_frame, text="Last Name:", font=("Arial", 11, "bold"), bg="#f7fbff").grid(row=3, column=0, sticky=W, pady=10)
    last_name_entry = Entry(main_frame, width=30, font=("Arial", 11))
    last_name_entry.grid(row=3, column=1, padx=10, pady=10)
    last_name_entry.bind('<KeyRelease>', lambda event: uppercase_entry_widget(last_name_entry))

    Label(main_frame, text="Age:", font=("Arial", 11, "bold"), bg="#f7fbff").grid(row=4, column=0, sticky=W, pady=10)
    age_entry = Entry(main_frame, width=30, font=("Arial", 11))
    age_entry.grid(row=4, column=1, padx=10, pady=10)

    Label(main_frame, text="Gender:", font=("Arial", 11, "bold"), bg="#f7fbff").grid(row=5, column=0, sticky=W, pady=10)
    gender_var = StringVar(value="MALE")
    gender_combo = ttk.Combobox(main_frame, textvariable=gender_var, values=["MALE", "FEMALE", "OTHER"], width=27, state="readonly")
    gender_combo.grid(row=5, column=1, padx=10, pady=10)

    Label(main_frame, text="Birth Date (YYYY-MM-DD):", font=("Arial", 11, "bold"), bg="#f7fbff").grid(row=6, column=0, sticky=W, pady=10)
    if DateEntry:
        birth_date_entry = DateEntry(main_frame, width=27, date_pattern='yyyy-mm-dd', font=("Arial", 11))
    else:
        birth_date_entry = Entry(main_frame, width=30, font=("Arial", 11))
    birth_date_entry.grid(row=6, column=1, padx=10, pady=10)
    birth_date_entry.bind('<KeyRelease>', lambda event: format_birthdate_entry(birth_date_entry))

    Label(main_frame, text="Birth Place:", font=("Arial", 11, "bold"), bg="#f7fbff").grid(row=7, column=0, sticky=W, pady=10)
    birth_place_entry = Entry(main_frame, width=30, font=("Arial", 11))
    birth_place_entry.grid(row=7, column=1, padx=10, pady=10)
    birth_place_entry.bind('<KeyRelease>', lambda event: uppercase_entry_widget(birth_place_entry))

    Label(main_frame, text="Civil Status:", font=("Arial", 11, "bold"), bg="#f7fbff").grid(row=8, column=0, sticky=W, pady=10)
    civil_status_var = StringVar(value="SINGLE")
    civil_status_combo = ttk.Combobox(main_frame, textvariable=civil_status_var, values=["SINGLE", "MARRIED", "WIDOWED", "DIVORCED"], width=27, state="readonly")
    civil_status_combo.grid(row=8, column=1, padx=10, pady=10)

    Label(main_frame, text="Nationality:", font=("Arial", 11, "bold"), bg="#f7fbff").grid(row=9, column=0, sticky=W, pady=10)
    nationality_entry = Entry(main_frame, width=30, font=("Arial", 11))
    nationality_entry.grid(row=9, column=1, padx=10, pady=10)
    nationality_entry.bind('<KeyRelease>', lambda event: uppercase_entry_widget(nationality_entry))

    Label(main_frame, text="Phone Number:", font=("Arial", 11, "bold"), bg="#f7fbff").grid(row=10, column=0, sticky=W, pady=10)
    phone_entry = Entry(main_frame, width=30, font=("Arial", 11))
    phone_entry.grid(row=10, column=1, padx=10, pady=10)
    phone_entry.bind('<KeyRelease>', lambda event: uppercase_entry_widget(phone_entry))

    Label(main_frame, text="Email:", font=("Arial", 11, "bold"), bg="#f7fbff").grid(row=11, column=0, sticky=W, pady=10)
    email_entry = Entry(main_frame, width=30, font=("Arial", 11))
    email_entry.grid(row=11, column=1, padx=10, pady=10)
    email_entry.bind('<KeyRelease>', lambda event: uppercase_entry_widget(email_entry))

    Label(main_frame, text="Address:", font=("Arial", 11, "bold"), bg="#f7fbff").grid(row=12, column=0, sticky=W, pady=10)
    address_entry = Entry(main_frame, width=30, font=("Arial", 11))
    address_entry.grid(row=12, column=1, padx=10, pady=10)
    address_entry.bind('<KeyRelease>', lambda event: uppercase_entry_widget(address_entry))

    Label(main_frame, text="Emergency Contact:", font=("Arial", 11, "bold"), bg="#f7fbff").grid(row=13, column=0, sticky=W, pady=10)
    emergency_entry = Entry(main_frame, width=30, font=("Arial", 11))
    emergency_entry.grid(row=13, column=1, padx=10, pady=10)
    emergency_entry.bind('<KeyRelease>', lambda event: uppercase_entry_widget(emergency_entry))

    # Clear all patient registration form fields.
    def clear_patient_form():
        name_entry.delete(0, END)
        middle_name_entry.delete(0, END)
        last_name_entry.delete(0, END)
        age_entry.delete(0, END)
        phone_entry.delete(0, END)
        email_entry.delete(0, END)
        address_entry.delete(0, END)
        if hasattr(birth_date_entry, 'set_date'):
            birth_date_entry.set_date(datetime.today())
        else:
            birth_date_entry.delete(0, END)
        birth_place_entry.delete(0, END)
        nationality_entry.delete(0, END)
        emergency_entry.delete(0, END)
        civil_status_var.set("Single")
        gender_var.set("Male")

    # Validate and save a new patient record.
    def register_patient(force=False):
        patient_id = patient_id_label.cget("text")
        first_name = name_entry.get().strip()
        last_name = last_name_entry.get().strip()

        if not first_name or not last_name:
            messagebox.showerror("Error", "First Name and Last Name are required")
            return

        if not validate_age(age_entry.get()):
            messagebox.showerror("Error", "Please enter a valid age (1-149)")
            return

        if not validate_phone(phone_entry.get()):
            messagebox.showerror("Error", "Please enter a valid phone number")
            return

        if email_entry.get().strip() and not validate_email(email_entry.get()):
            messagebox.showerror("Error", "Please enter a valid email address")
            return

        birth_date_value = birth_date_entry.get().strip()
        if birth_date_value and not validate_date(birth_date_value):
            messagebox.showerror("Error", "Please enter a valid birth date in YYYY-MM-DD format")
            return

        patient_data = {
            "first_name": first_name.upper(),
            "middle_name": middle_name_entry.get().strip().upper(),
            "last_name": last_name.upper(),
            "age": age_entry.get(),
            "gender": gender_var.get().upper(),
            "birth_date": birth_date_value or None,
            "birth_place": birth_place_entry.get().strip().upper(),
            "civil_status": civil_status_var.get().upper(),
            "nationality": nationality_entry.get().strip().upper(),
            "registered_by": (user_data.get('username') if user_data else '').upper(),
            "phone": phone_entry.get().strip().upper(),
            "email": email_entry.get().strip().upper(),
            "address": address_entry.get().strip().upper(),
            "medical_history": ""
        }

        if not force and db.has_duplicate_patient(patient_data):
            messagebox.showwarning(
                "Duplicate Patient",
                "A patient with the same name/birth date/phone/email already exists.\n"
                "Use Save Anyway to continue regardless."
            )
            return

        if force and not messagebox.askyesno(
            "Confirm Save Anyway",
            "A duplicate patient was detected. Are you sure you want to save this record anyway?"
        ):
            return

        db.add_patient(patient_id, patient_data)
        messagebox.showinfo("Success", f"Patient {first_name} {last_name} registered successfully!\nPatient ID: {patient_id}")

        if 'patient_list' in pages:
            refresher = page_refreshers.get('patient_list')
            if refresher:
                refresher()

        if 'dashboard' in pages:
            dashboard_refresher = page_refreshers.get('dashboard')
            if dashboard_refresher:
                dashboard_refresher()

        next_id = db.generate_next_patient_id()
        patient_id_label.config(text=next_id)
        clear_patient_form()

    button_frame = Frame(frame, bg="#f7fbff")
    button_frame.pack(pady=20)

    register_btn = Button(button_frame, text="Register Patient", command=register_patient,
                          bg="#1f618d", fg="white", font=("Arial", 12, "bold"), width=18, padx=10, pady=10)
    register_btn.pack(side=LEFT, padx=6)

    save_anyway_btn = Button(button_frame, text="Save Anyway", command=lambda: register_patient(force=True),
                             bg="#f39c12", fg="white", font=("Arial", 12, "bold"), width=18, padx=10, pady=10)
    save_anyway_btn.pack(side=LEFT, padx=6)

    clear_btn = Button(button_frame, text="Clear", command=clear_patient_form,
                       bg="#85929e", fg="white", font=("Arial", 12, "bold"), width=14, padx=10, pady=10)
    clear_btn.pack(side=LEFT, padx=6)

    return frame


# Open the patient registration page.
def open_patient_registration(user_data=None):
    if 'patient_registration' not in pages:
        pages['patient_registration'] = build_patient_registration_page(page_container, user_data)
    show_page('patient_registration')


# Build the patient search user interface page.
def build_search_patient_page(parent):
    frame = Frame(parent, bg="#f7fbff")
    db = PatientDatabase()
    selected_patient_id = StringVar(value="")

    Label(frame, text="Search Patient Records", font=("Arial", 20, "bold"), fg="#1b4f72", bg="#f7fbff").pack(pady=20)

    search_frame = Frame(frame, bg="#f7fbff")
    search_frame.pack(pady=10, fill=X, padx=20)

    Label(search_frame, text="Search by Patient ID or Name:", font=("Arial", 12, "bold"), bg="#f7fbff").grid(row=0, column=0, padx=10, pady=10, sticky=W)
    search_entry = Entry(search_frame, width=30, font=("Arial", 12))
    search_entry.grid(row=0, column=1, padx=10, pady=10)
    search_entry.bind('<KeyRelease>', lambda event: uppercase_entry_widget(search_entry))

    search_button = Button(search_frame, text="Search", command=lambda: search_patient(),
                           bg="#1f618d", fg="white", font=("Arial", 12, "bold"), width=15, padx=10, pady=10)
    search_button.grid(row=0, column=2, padx=6)

    clear_search_button = Button(search_frame, text="Clear Search", command=lambda: clear_search(),
                                 bg="#85929e", fg="white", font=("Arial", 12, "bold"), width=15, padx=10, pady=10)
    clear_search_button.grid(row=0, column=3, padx=6)

    results_frame = Frame(frame, bg="#f7fbff")
    results_frame.pack(fill=BOTH, expand=True, padx=20, pady=10)

    columns = ("ID", "Name", "Age", "Gender", "Birth Date", "Nationality", "Phone", "Email", "Registered")
    results_tree = ttk.Treeview(results_frame, columns=columns, show="headings", height=10)
    for col in columns:
        results_tree.heading(col, text=col)
    results_tree.column("ID", width=100, anchor=W)
    results_tree.column("Name", width=180, anchor=W)
    results_tree.column("Age", width=60, anchor=CENTER)
    results_tree.column("Gender", width=80, anchor=CENTER)
    results_tree.column("Birth Date", width=100, anchor=CENTER)
    results_tree.column("Nationality", width=120, anchor=W)
    results_tree.column("Phone", width=120, anchor=W)
    results_tree.column("Email", width=180, anchor=W)
    results_tree.column("Registered", width=140, anchor=W)

    results_scrollbar = ttk.Scrollbar(results_frame, orient=VERTICAL, command=results_tree.yview)
    results_tree.configure(yscrollcommand=results_scrollbar.set)
    results_tree.pack(side=LEFT, fill=BOTH, expand=True)
    results_scrollbar.pack(side=RIGHT, fill=Y)

    edit_frame = LabelFrame(frame, text="Edit Selected Patient", bg="#f7fbff", fg="#1b4f72", font=("Arial", 12, "bold"))
    edit_frame.pack(fill=BOTH, expand=True, padx=20, pady=10)

    Label(edit_frame, text="Patient ID:", font=("Arial", 11, "bold"), bg="#f7fbff").grid(row=0, column=0, sticky=W, pady=6)
    patient_id_entry = Entry(edit_frame, width=28, font=("Arial", 11), state='readonly', textvariable=selected_patient_id)
    patient_id_entry.grid(row=0, column=1, padx=10, pady=6)

    Label(edit_frame, text="First Name:", font=("Arial", 11, "bold"), bg="#f7fbff").grid(row=0, column=2, sticky=W, pady=6)
    edit_first_name = Entry(edit_frame, width=28, font=("Arial", 11))
    edit_first_name.grid(row=0, column=3, padx=10, pady=6)
    edit_first_name.bind('<KeyRelease>', lambda event: uppercase_entry_widget(edit_first_name))

    Label(edit_frame, text="Middle Name:", font=("Arial", 11, "bold"), bg="#f7fbff").grid(row=1, column=0, sticky=W, pady=6)
    edit_middle_name = Entry(edit_frame, width=28, font=("Arial", 11))
    edit_middle_name.grid(row=1, column=1, padx=10, pady=6)
    edit_middle_name.bind('<KeyRelease>', lambda event: uppercase_entry_widget(edit_middle_name))

    Label(edit_frame, text="Last Name:", font=("Arial", 11, "bold"), bg="#f7fbff").grid(row=1, column=2, sticky=W, pady=6)
    edit_last_name = Entry(edit_frame, width=28, font=("Arial", 11))
    edit_last_name.grid(row=1, column=3, padx=10, pady=6)
    edit_last_name.bind('<KeyRelease>', lambda event: uppercase_entry_widget(edit_last_name))

    Label(edit_frame, text="Age:", font=("Arial", 11, "bold"), bg="#f7fbff").grid(row=2, column=0, sticky=W, pady=6)
    edit_age = Entry(edit_frame, width=28, font=("Arial", 11))
    edit_age.grid(row=2, column=1, padx=10, pady=6)

    Label(edit_frame, text="Gender:", font=("Arial", 11, "bold"), bg="#f7fbff").grid(row=2, column=2, sticky=W, pady=6)
    edit_gender_var = StringVar(value="MALE")
    edit_gender = ttk.Combobox(edit_frame, textvariable=edit_gender_var, values=["MALE", "FEMALE", "OTHER"], width=26, state="readonly")
    edit_gender.grid(row=2, column=3, padx=10, pady=6)

    Label(edit_frame, text="Birth Date:", font=("Arial", 11, "bold"), bg="#f7fbff").grid(row=3, column=0, sticky=W, pady=6)
    if DateEntry:
        edit_birth_date = DateEntry(edit_frame, width=26, date_pattern='yyyy-mm-dd', font=("Arial", 11))
    else:
        edit_birth_date = Entry(edit_frame, width=28, font=("Arial", 11))
    edit_birth_date.grid(row=3, column=1, padx=10, pady=6)
    edit_birth_date.bind('<KeyRelease>', lambda event: format_birthdate_entry(edit_birth_date))

    Label(edit_frame, text="Birth Place:", font=("Arial", 11, "bold"), bg="#f7fbff").grid(row=3, column=2, sticky=W, pady=6)
    edit_birth_place = Entry(edit_frame, width=28, font=("Arial", 11))
    edit_birth_place.grid(row=3, column=3, padx=10, pady=6)
    edit_birth_place.bind('<KeyRelease>', lambda event: uppercase_entry_widget(edit_birth_place))

    Label(edit_frame, text="Civil Status:", font=("Arial", 11, "bold"), bg="#f7fbff").grid(row=4, column=0, sticky=W, pady=6)
    edit_civil_status_var = StringVar(value="SINGLE")
    edit_civil_status = ttk.Combobox(edit_frame, textvariable=edit_civil_status_var, values=["SINGLE", "MARRIED", "WIDOWED", "DIVORCED"], width=26, state="readonly")
    edit_civil_status.grid(row=4, column=1, padx=10, pady=6)

    Label(edit_frame, text="Nationality:", font=("Arial", 11, "bold"), bg="#f7fbff").grid(row=4, column=2, sticky=W, pady=6)
    edit_nationality = Entry(edit_frame, width=28, font=("Arial", 11))
    edit_nationality.grid(row=4, column=3, padx=10, pady=6)
    edit_nationality.bind('<KeyRelease>', lambda event: uppercase_entry_widget(edit_nationality))

    Label(edit_frame, text="Phone:", font=("Arial", 11, "bold"), bg="#f7fbff").grid(row=5, column=0, sticky=W, pady=6)
    edit_phone = Entry(edit_frame, width=28, font=("Arial", 11))
    edit_phone.grid(row=5, column=1, padx=10, pady=6)
    edit_phone.bind('<KeyRelease>', lambda event: uppercase_entry_widget(edit_phone))

    Label(edit_frame, text="Email:", font=("Arial", 11, "bold"), bg="#f7fbff").grid(row=5, column=2, sticky=W, pady=6)
    edit_email = Entry(edit_frame, width=28, font=("Arial", 11))
    edit_email.grid(row=5, column=3, padx=10, pady=6)

    Label(edit_frame, text="Address:", font=("Arial", 11, "bold"), bg="#f7fbff").grid(row=6, column=0, sticky=W, pady=6)
    edit_address = Entry(edit_frame, width=28, font=("Arial", 11))
    edit_address.grid(row=6, column=1, padx=10, pady=6)
    edit_address.bind('<KeyRelease>', lambda event: uppercase_entry_widget(edit_address))

    Label(edit_frame, text="Medical History:", font=("Arial", 11, "bold"), bg="#f7fbff").grid(row=6, column=2, sticky=W, pady=6)
    edit_medical_history = Entry(edit_frame, width=28, font=("Arial", 11))
    edit_medical_history.grid(row=6, column=3, padx=10, pady=6)
    edit_medical_history.bind('<KeyRelease>', lambda event: uppercase_entry_widget(edit_medical_history))

    registered_by_label = Label(edit_frame, text="Registered By: N/A", font=("Arial", 10, "italic"), bg="#f7fbff", fg="#566573")
    registered_by_label.grid(row=7, column=0, columnspan=4, sticky=W, padx=10, pady=(8, 6))

    def clear_edit_form():
        selected_patient_id.set("")
        edit_first_name.delete(0, END)
        edit_middle_name.delete(0, END)
        edit_last_name.delete(0, END)
        edit_age.delete(0, END)
        edit_gender_var.set("MALE")
        if hasattr(edit_birth_date, 'set_date'):
            edit_birth_date.set_date(datetime.today())
        else:
            edit_birth_date.delete(0, END)
        edit_birth_place.delete(0, END)
        edit_civil_status_var.set("SINGLE")
        edit_nationality.delete(0, END)
        edit_phone.delete(0, END)
        edit_email.delete(0, END)
        edit_address.delete(0, END)
        edit_medical_history.delete(0, END)
        registered_by_label.config(text="Registered By: N/A")

    def load_results(patients):
        for item in results_tree.get_children():
            results_tree.delete(item)

        if not patients:
            results_tree.insert("", END, values=("No results found", "", "", "", "", "", "", "", ""))
            return

        for patient_id, patient_data in patients.items():
            full_name = " ".join([patient_data.get('first_name', ''), patient_data.get('middle_name', ''), patient_data.get('last_name', '')]).strip().upper()
            if not full_name:
                full_name = 'N/A'
            results_tree.insert("", END, values=(
                patient_id,
                full_name,
                patient_data.get('age', 'N/A'),
                (patient_data.get('gender') or 'N/A').upper(),
                patient_data.get('birth_date', 'N/A'),
                (patient_data.get('nationality') or 'N/A').upper(),
                (patient_data.get('phone') or 'N/A').upper(),
                (patient_data.get('email') or 'N/A').upper(),
                (patient_data.get('registered_by') or 'N/A').upper()
            ))

    def search_patient():
        search_term = search_entry.get().strip().upper()
        if not search_term:
            messagebox.showwarning("Warning", "Please enter a search term")
            return

        patients = db.search_patients(search_term)
        load_results(patients)
        clear_edit_form()

    def clear_search():
        search_entry.delete(0, END)
        load_results({})
        clear_edit_form()

    def load_selected_patient(patient_data):
        clear_edit_form()
        selected_patient_id.set(patient_data.get('patient_id', ''))
        edit_first_name.insert(0, patient_data.get('first_name', ''))
        edit_middle_name.insert(0, patient_data.get('middle_name', ''))
        edit_last_name.insert(0, patient_data.get('last_name', ''))
        edit_age.insert(0, patient_data.get('age', ''))
        edit_gender_var.set(patient_data.get('gender', 'MALE').upper())
        if hasattr(edit_birth_date, 'set_date'):
            try:
                edit_birth_date.set_date(patient_data.get('birth_date') or datetime.today())
            except Exception:
                edit_birth_date.delete(0, END)
                edit_birth_date.insert(0, patient_data.get('birth_date', ''))
        else:
            edit_birth_date.delete(0, END)
            edit_birth_date.insert(0, patient_data.get('birth_date', ''))
        edit_birth_place.insert(0, patient_data.get('birth_place', ''))
        edit_civil_status_var.set(patient_data.get('civil_status', 'SINGLE').upper())
        edit_nationality.insert(0, patient_data.get('nationality', ''))
        edit_phone.insert(0, patient_data.get('phone', ''))
        edit_email.insert(0, patient_data.get('email', ''))
        edit_address.insert(0, patient_data.get('address', ''))
        edit_medical_history.insert(0, patient_data.get('medical_history', ''))
        registered_by_label.config(text=f"Registered By: {(patient_data.get('registered_by') or 'N/A').upper()}")

    def on_tree_select(event):
        selected = results_tree.selection()
        if not selected:
            return
        item = results_tree.item(selected)
        patient_id = item['values'][0]
        if patient_id == "No results found":
            return

        patient_data = db.get_patient(patient_id)
        if patient_data:
            load_selected_patient(patient_data)

    def update_patient():
        patient_id = selected_patient_id.get()
        if not patient_id:
            messagebox.showwarning("Warning", "Select a patient record before updating")
            return

        if not edit_first_name.get().strip() or not edit_last_name.get().strip():
            messagebox.showerror("Error", "First Name and Last Name are required")
            return

        if not validate_age(edit_age.get()):
            messagebox.showerror("Error", "Please enter a valid age (1-149)")
            return

        if edit_phone.get().strip() and not validate_phone(edit_phone.get()):
            messagebox.showerror("Error", "Please enter a valid phone number")
            return

        if edit_email.get().strip() and not validate_email(edit_email.get()):
            messagebox.showerror("Error", "Please enter a valid email address")
            return

        birth_date_value = edit_birth_date.get().strip()
        if birth_date_value and not validate_date(birth_date_value):
            messagebox.showerror("Error", "Please enter a valid birth date in YYYY-MM-DD format")
            return

        patient_data = {
            'first_name': edit_first_name.get().strip().upper(),
            'middle_name': edit_middle_name.get().strip().upper(),
            'last_name': edit_last_name.get().strip().upper(),
            'age': edit_age.get().strip(),
            'gender': edit_gender_var.get().upper(),
            'birth_date': birth_date_value or None,
            'birth_place': edit_birth_place.get().strip().upper(),
            'civil_status': edit_civil_status_var.get().upper(),
            'nationality': edit_nationality.get().strip().upper(),
            'phone': edit_phone.get().strip().upper(),
            'email': edit_email.get().strip().upper(),
            'address': edit_address.get().strip().upper(),
            'medical_history': edit_medical_history.get().strip().upper()
        }

        if db.update_patient(patient_id, patient_data):
            messagebox.showinfo("Success", f"Patient {patient_id} updated successfully")
            if search_entry.get().strip():
                search_patient()
            else:
                load_results({})
            if 'patient_list' in pages:
                refresher = page_refreshers.get('patient_list')
                if refresher:
                    refresher()
            if 'dashboard' in pages:
                refresher = page_refreshers.get('dashboard')
                if refresher:
                    refresher()
        else:
            messagebox.showerror("Error", "Unable to update patient record")

    def delete_patient():
        patient_id = selected_patient_id.get()
        if not patient_id:
            messagebox.showwarning("Warning", "Select a patient record before deleting")
            return

        if not messagebox.askyesno("Confirm Delete", f"Delete patient record {patient_id}? This cannot be undone."):
            return

        if db.delete_patient(patient_id):
            messagebox.showinfo("Deleted", f"Patient {patient_id} deleted successfully")
            clear_edit_form()
            if search_entry.get().strip():
                search_patient()
            else:
                load_results({})
            if 'patient_list' in pages:
                refresher = page_refreshers.get('patient_list')
                if refresher:
                    refresher()
            if 'dashboard' in pages:
                refresher = page_refreshers.get('dashboard')
                if refresher:
                    refresher()
        else:
            messagebox.showerror("Error", "Unable to delete patient record")

    results_tree.bind('<<TreeviewSelect>>', on_tree_select)

    action_frame = Frame(edit_frame, bg="#f7fbff")
    action_frame.grid(row=8, column=0, columnspan=4, pady=12)

    update_btn = Button(action_frame, text="Update Record", command=update_patient,
                        bg="#1f618d", fg="white", font=("Arial", 12, "bold"), width=16, padx=10, pady=10)
    update_btn.pack(side=LEFT, padx=6)

    delete_btn = Button(action_frame, text="Delete Record", command=delete_patient,
                        bg="#c0392b", fg="white", font=("Arial", 12, "bold"), width=16, padx=10, pady=10)
    delete_btn.pack(side=LEFT, padx=6)

    clear_btn = Button(action_frame, text="Clear Form", command=clear_edit_form,
                       bg="#85929e", fg="white", font=("Arial", 12, "bold"), width=16, padx=10, pady=10)
    clear_btn.pack(side=LEFT, padx=6)

    load_results({})
    return frame


# Open the patient search page.
def open_search_patient():
    if 'search_patient' not in pages:
        pages['search_patient'] = build_search_patient_page(page_container)
    show_page('search_patient')


# Build the page that shows all registered patients.
def build_patient_list_page(parent):
    frame = Frame(parent, bg="#f7fbff")
    db = PatientDatabase()

    Label(frame, text="All Registered Patients", font=("Arial", 20, "bold"), fg="#1b4f72", bg="#f7fbff").pack(pady=20)

    tree_frame = Frame(frame, bg="#f7fbff")
    tree_frame.pack(fill=BOTH, expand=True, padx=20, pady=10)

    columns = ("ID", "Name", "Age", "Gender", "Nationality", "Phone", "Email")
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=18)
    tree.heading("ID", text="Patient ID")
    tree.heading("Name", text="Name")
    tree.heading("Age", text="Age")
    tree.heading("Gender", text="Gender")
    tree.heading("Nationality", text="Nationality")
    tree.heading("Phone", text="Phone")
    tree.heading("Email", text="Email")
    tree.column("ID", width=100)
    tree.column("Name", width=180)
    tree.column("Age", width=60, anchor=CENTER)
    tree.column("Gender", width=80, anchor=CENTER)
    tree.column("Nationality", width=120)
    tree.column("Phone", width=120)
    tree.column("Email", width=180)

    scrollbar = ttk.Scrollbar(tree_frame, orient=VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    tree.pack(side=LEFT, fill=BOTH, expand=True)
    scrollbar.pack(side=RIGHT, fill=Y)

    details_frame = Frame(frame, bg="#f7fbff")
    details_frame.pack(fill=BOTH, expand=True, padx=20, pady=10)

    Label(details_frame, text="Patient Details:", font=("Arial", 12, "bold"), bg="#f7fbff").pack(anchor=W)
    details_text = Text(details_frame, wrap=WORD, font=("Arial", 10), height=8)
    details_scrollbar = Scrollbar(details_frame, command=details_text.yview)
    details_text.config(yscrollcommand=details_scrollbar.set)
    details_text.pack(side=LEFT, fill=BOTH, expand=True)
    details_scrollbar.pack(side=RIGHT, fill=Y)

    # Load patient records into the list page tree view.
    def load_patients():
        for item in tree.get_children():
            tree.delete(item)

        patients = db.get_all_patients()
        if not patients:
            tree.insert("", END, values=("No patients", "registered", "yet", "", "", ""))
            return

        for patient_id, patient_data in patients.items():
            if not patient_data:
                continue
            first = patient_data.get('first_name', '') or ''
            middle = patient_data.get('middle_name', '') or ''
            last = patient_data.get('last_name', '') or ''
            full_name = f"{last}, {first}".strip().replace(" ,", "").upper()
            gender = (patient_data.get('gender') or 'N/A').upper()
            nationality = (patient_data.get('nationality') or 'N/A').upper()
            phone = (patient_data.get('phone') or 'N/A').upper()
            email = (patient_data.get('email') or 'N/A').upper()
            tree.insert("", END, values=(
                patient_id,
                full_name,
                patient_data.get('age', 'N/A'),
                gender,
                nationality,
                phone,
                email
            ))

    # Show details for the selected patient in the list page.
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
                middle_name = patient_data.get('middle_name', '')
                last_name = patient_data.get('last_name', '')
                name_parts = [part for part in [first_name, middle_name, last_name] if part]
                full_name = " ".join(name_parts).strip().upper()
                details_text.insert(END, f"Name: {full_name if full_name else 'N/A'}\n")
                details_text.insert(END, f"Age: {patient_data.get('age', 'N/A')}\n")
                details_text.insert(END, f"Gender: {(patient_data.get('gender') or 'N/A').upper()}\n")
                details_text.insert(END, f"Phone: {(patient_data.get('phone') or 'N/A').upper()}\n")
                details_text.insert(END, f"Email: {(patient_data.get('email') or 'N/A').upper()}\n")
                details_text.insert(END, f"Address: {(patient_data.get('address') or 'N/A').upper()}\n")
                details_text.insert(END, f"Nationality: {(patient_data.get('nationality') or 'N/A').upper()}\n")
                details_text.insert(END, f"Medical History: {(patient_data.get('medical_history') or 'None').upper()}\n")
                details_text.insert(END, f"Registration Date: {patient_data.get('registration_date', 'N/A')}\n")

    tree.bind('<<TreeviewSelect>>', on_tree_select)

    button_frame = Frame(frame, bg="#f7fbff")
    button_frame.pack(pady=20)

    refresh_btn = Button(button_frame, text="Refresh List", command=load_patients,
                         bg="#1f618d", fg="white", font=("Arial", 12, "bold"), width=15, padx=10, pady=10)
    refresh_btn.pack(side=LEFT, padx=6)

    page_refreshers['patient_list'] = load_patients
    load_patients()
    return frame


# Open or refresh the patient list page.
def open_patient_list():
    if 'patient_list' not in pages:
        pages['patient_list'] = build_patient_list_page(page_container)
    else:
        refresher = page_refreshers.get('patient_list')
        if refresher:
            refresher()
    show_page('patient_list')

# ============== APPLICATION STARTUP ==============
if __name__ == "__main__":
    create_login_window()
