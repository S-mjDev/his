from tkinter import *
from tkinter import messagebox, ttk
import json
import os
import sys
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


def resource_path(relative_path):
    """Get absolute path to resource, supporting PyInstaller bundles."""
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# ============== DATABASE CONFIGURATION ==============
class DatabaseConnection:
    # Initialize the instance.
    def __init__(self):
        self.host = os.getenv("DB_HOST", "192.168.1.88")
        self.database = os.getenv("DB_NAME", "his_db")
        self.user = os.getenv("DB_USER", "root")
        self.password = os.getenv("DB_PASSWORD", "root")
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

# ============== THEME ==============
T = {
    "bg":        "#f0f4f8",
    "panel":     "#ffffff",
    "card":      "#ffffff",
    "sidebar":   "#1a2332",
    "sidebar2":  "#243447",
    "accent":    "#2563eb",
    "accent_h":  "#1d4ed8",
    "accent_lt": "#dbeafe",
    "text":      "#1e293b",
    "muted":     "#64748b",
    "border":    "#e2e8f0",
    "border2":   "#cbd5e1",
    "danger":    "#dc2626",
    "danger_lt": "#fee2e2",
    "warning":   "#d97706",
    "success":   "#059669",
    "success_lt":"#d1fae5",
    "white":     "#ffffff",
    "entry_bg":  "#f8fafc",
    "entry_fg":  "#1e293b",
    "row_even":  "#f8fafc",
    "row_odd":   "#ffffff",
    "row_alt":   "#f8fafc",
    "row_sel":   "#dbeafe",
    "heading_bg":"#f1f5f9",
}

FONT = {
    "h1":      ("Georgia", 18, "bold"),
    "h2":      ("Georgia", 14, "bold"),
    "h3":      ("Georgia", 11, "bold"),
    "body":    ("Calibri", 10),
    "body_b":  ("Calibri", 10, "bold"),
    "small":   ("Calibri", 9),
    "label":   ("Calibri", 9, "bold"),
    "mono":    ("Consolas", 11, "bold"),
    "nav":     ("Calibri", 10, "bold"),
    "tag":     ("Calibri", 8, "bold"),
}


def apply_styles():
    style = ttk.Style()
    style.theme_use("clam")
    # Treeview
    style.configure("Treeview",
        background=T["row_odd"], foreground=T["text"],
        fieldbackground=T["row_odd"], rowheight=34,
        font=FONT["body"], borderwidth=0,
        relief="flat")
    style.configure("Treeview.Heading",
        background=T["heading_bg"], foreground=T["muted"],
        font=FONT["label"], relief="flat", borderwidth=0,
        padding=(8, 6))
    style.map("Treeview",
        background=[("selected", T["row_sel"])],
        foreground=[("selected", T["accent"])])
    style.map("Treeview.Heading",
        background=[("active", T["border"])])
    # Scrollbar
    style.configure("Vertical.TScrollbar",
        background=T["border"], troughcolor=T["bg"],
        arrowcolor=T["muted"], borderwidth=0,
        gripcount=0, width=8)
    style.map("Vertical.TScrollbar",
        background=[("active", T["border2"])])
    # Combobox
    style.configure("TCombobox",
        fieldbackground=T["entry_bg"], background=T["panel"],
        foreground=T["entry_fg"], arrowcolor=T["accent"],
        borderwidth=1, relief="flat",
        selectbackground=T["accent_lt"],
        selectforeground=T["text"],
        padding=(8, 6))
    style.map("TCombobox",
        fieldbackground=[("readonly", T["entry_bg"])],
        foreground=[("readonly", T["entry_fg"])],
        selectbackground=[("readonly", T["accent_lt"])])


def mk_entry(parent, width=28, show=None, textvariable=None, readonly=False):
    kw = dict(
        width=width, font=FONT["body"],
        bg=T["entry_bg"], fg=T["entry_fg"],
        insertbackground=T["accent"],
        relief="flat", bd=0,
        highlightthickness=1,
        highlightbackground=T["border2"],
        highlightcolor=T["accent"],
        selectbackground=T["accent_lt"],
        selectforeground=T["text"],
    )
    if show:
        kw["show"] = show
    if textvariable:
        kw["textvariable"] = textvariable
    if readonly:
        kw["state"] = "readonly"
        kw["bg"] = T["border"]
        kw["fg"] = T["muted"]
    e = Entry(parent, **kw)
    return e


def mk_btn(parent, text, command, color=None, width=14, danger=False, secondary=False):
    if danger:
        bg, fg, abg = T["danger"], T["white"], "#b91c1c"
    elif secondary:
        bg, fg, abg = T["border"], T["text"], T["border2"]
    else:
        bg, fg, abg = (color or T["accent"]), T["white"], T["accent_h"]
    b = Button(parent, text=text, command=command,
               bg=bg, fg=fg, font=FONT["body_b"],
               activebackground=abg, activeforeground=fg,
               bd=0, relief=FLAT, width=width,
               padx=12, pady=8, cursor="hand2")
    return b


def mk_combo(parent, textvariable, values, width=27):
    cb = ttk.Combobox(parent, textvariable=textvariable,
                      values=values, width=width, state="readonly",
                      font=FONT["body"])
    return cb


def page_header(parent, title, subtitle=""):
    hf = Frame(parent, bg=T["panel"])
    hf.pack(fill=X)
    Frame(hf, bg=T["accent"], height=3).pack(fill=X)
    inner = Frame(hf, bg=T["panel"])
    inner.pack(fill=X, padx=28, pady=(16, 14))
    Label(inner, text=title, font=FONT["h1"],
          bg=T["panel"], fg=T["text"]).pack(anchor=W)
    if subtitle:
        Label(inner, text=subtitle, font=FONT["body"],
              bg=T["panel"], fg=T["muted"]).pack(anchor=W, pady=(2, 0))
    Frame(hf, bg=T["border"], height=1).pack(fill=X)


def field_card(parent, **pack_kw):
    f = Frame(parent, bg=T["panel"],
              highlightthickness=1, highlightbackground=T["border"])
    f.pack(**pack_kw)
    return f


def section_label(parent, text):
    Label(parent, text=text.upper(), font=FONT["tag"],
          bg=T["panel"], fg=T["accent"]).pack(anchor=W, padx=20, pady=(14, 2))
    Frame(parent, bg=T["border"], height=1).pack(fill=X, padx=20, pady=(0, 8))


def stat_card(parent, title, value, icon="", color=None):
    c = color or T["accent"]
    f = Frame(parent, bg=T["panel"],
              highlightthickness=1, highlightbackground=T["border"])
    top = Frame(f, bg=T["panel"])
    top.pack(fill=X, padx=20, pady=(18, 4))
    Label(top, text=icon, font=("Calibri", 18),
          bg=T["panel"], fg=c).pack(side=LEFT, padx=(0, 10))
    Label(top, text=value, font=("Georgia", 28, "bold"),
          bg=T["panel"], fg=c).pack(side=LEFT)
    Label(f, text=title, font=FONT["body_b"],
          bg=T["panel"], fg=T["text"]).pack(anchor=W, padx=20)
    Frame(f, bg=c, height=3).pack(fill=X, pady=(14, 0))
    return f


# ============== LOGIN WINDOW ==============
def create_login_window():
    login_window = Tk()
    login_window.title("Hospital Information System — Login")
    login_window.geometry("480x540")
    login_window.resizable(False, False)
    login_window.eval("tk::PlaceWindow . center")
    login_window.configure(bg=T["bg"])

    try:
        login_window.iconbitmap(resource_path("qphn.ico"))
    except Exception:
        try:
            icon = PhotoImage(file=resource_path("qphn.jpg"))
            login_window.iconphoto(True, icon)
        except Exception:
            pass

    apply_styles()

    # Subtle background
    bg_canvas = Canvas(login_window, bg=T["bg"], highlightthickness=0)
    bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
    for i in range(0, 480, 32):
        bg_canvas.create_line(i, 0, i, 540, fill=T["border"], width=1)
    for j in range(0, 540, 32):
        bg_canvas.create_line(0, j, 480, j, fill=T["border"], width=1)

    # Card
    card = Frame(login_window, bg=T["panel"],
                 highlightthickness=1, highlightbackground=T["border2"])
    card.place(relx=0.5, rely=0.5, anchor=CENTER, width=380, height=460)

    # Top accent stripe
    Frame(card, bg=T["accent"], height=4).pack(fill=X)

    # Logo area
    logo_row = Frame(card, bg=T["panel"])
    logo_row.pack(fill=X, padx=36, pady=(28, 0))
    badge = Frame(logo_row, bg=T["accent"], width=46, height=46)
    badge.pack_propagate(False)
    badge.pack(anchor=W)
    Label(badge, text="H", font=("Georgia", 20, "bold"),
          bg=T["accent"], fg=T["white"]).place(relx=0.5, rely=0.5, anchor=CENTER)

    Label(card, text="Hospital Information System",
          font=FONT["h2"], bg=T["panel"], fg=T["text"]).pack(anchor=W, padx=36, pady=(10, 2))
    Label(card, text="Sign in to your account",
          font=FONT["body"], bg=T["panel"], fg=T["muted"]).pack(anchor=W, padx=36)

    # Divider
    Frame(card, bg=T["border"], height=1).pack(fill=X, padx=36, pady=(16, 0))

    # Form
    form = Frame(card, bg=T["panel"])
    form.pack(fill=X, padx=36, pady=(16, 0))

    Label(form, text="USERNAME", font=FONT["tag"],
          bg=T["panel"], fg=T["muted"]).pack(anchor=W, pady=(0, 4))
    username_entry = mk_entry(form, width=36)
    username_entry.pack(fill=X, ipady=9, pady=(0, 14))
    username_entry.focus()

    Label(form, text="PASSWORD", font=FONT["tag"],
          bg=T["panel"], fg=T["muted"]).pack(anchor=W, pady=(0, 4))
    password_entry = mk_entry(form, width=36, show="●")
    password_entry.pack(fill=X, ipady=9, pady=(0, 22))

    def login():
        username = username_entry.get().strip()
        password = password_entry.get().strip()
        if not username or not password:
            messagebox.showerror("Error", "Please enter both username and password")
            return
        user_db = get_user_db()
        success, user_data = user_db.authenticate(username, password)
        if success:
            login_window.destroy()
            create_main_application(user_data)
        else:
            messagebox.showerror("Login Failed", "Invalid username or password")

    Button(form, text="SIGN IN", command=login,
           bg=T["accent"], fg=T["white"], font=("Calibri", 11, "bold"),
           activebackground=T["accent_h"], activeforeground=T["white"],
           bd=0, relief=FLAT, pady=12, cursor="hand2").pack(fill=X)

    login_window.bind("<Return>", lambda e: login())

    Label(card, text="Secure  ·  Role-Based Access Control",
          font=FONT["small"], bg=T["panel"], fg=T["border2"]).pack(side=BOTTOM, pady=18)

    login_window.mainloop()

# ============== USER REGISTRATION WINDOW ==============
def build_user_registration_page(parent):
    frame = Frame(parent, bg=T["bg"])
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(1, weight=1)

    page_header(frame, "Add New User", "Create a new system user account")

    # Centered scrollable body
    body = Frame(frame, bg=T["bg"])
    body.pack(fill=BOTH, expand=True)
    body.columnconfigure(0, weight=1)
    body.rowconfigure(0, weight=1)

    card = Frame(body, bg=T["panel"],
                 highlightthickness=1, highlightbackground=T["border"])
    card.pack(padx=80, pady=30, ipadx=0, ipady=0, anchor=N, fill=X)

    section_label(card, "Account Details")

    form = Frame(card, bg=T["panel"])
    form.pack(fill=X, padx=20, pady=(0, 8))
    form.columnconfigure(1, weight=1)

    def lf(label, row, show=None):
        Label(form, text=label.upper(), font=FONT["tag"],
              bg=T["panel"], fg=T["muted"]).grid(
            row=row*2, column=0, columnspan=2, sticky=W, pady=(10, 3))
        e = mk_entry(form, width=44, show=show)
        e.grid(row=row*2+1, column=0, columnspan=2, sticky=EW, ipady=8, pady=(0, 2))
        return e

    username_entry       = lf("Username", 0)
    password_entry       = lf("Password", 1, show="●")
    confirm_entry        = lf("Confirm Password", 2, show="●")

    Label(form, text="ROLE", font=FONT["tag"],
          bg=T["panel"], fg=T["muted"]).grid(row=6, column=0, columnspan=2, sticky=W, pady=(10, 3))
    role_var = StringVar(value="Staff")
    role_combo = mk_combo(form, role_var, ["Staff", "Administrator"], width=42)
    role_combo.grid(row=7, column=0, columnspan=2, sticky=EW, ipady=6, pady=(0, 2))

    # Status feedback label
    status_lbl = Label(card, text="", font=FONT["body"],
                       bg=T["panel"], fg=T["success"])
    status_lbl.pack(anchor=W, padx=20, pady=(6, 0))

    def clear_user_form():
        username_entry.delete(0, END)
        password_entry.delete(0, END)
        confirm_entry.delete(0, END)
        role_var.set("Staff")
        status_lbl.config(text="")

    def register_user():
        username = username_entry.get().strip()
        password = password_entry.get()
        confirm  = confirm_entry.get()
        role     = role_var.get()
        if not validate_username(username):
            messagebox.showerror("Error", "Username must be 3–20 chars (letters, numbers, underscores)")
            return
        if not validate_password(password):
            messagebox.showerror("Error", "Password must be at least 6 characters")
            return
        if password != confirm:
            messagebox.showerror("Error", "Passwords do not match")
            return
        user_db = get_user_db()
        success, message = user_db.add_user(username, password, role)
        if success:
            status_lbl.config(text=f"✓  User '{username}' registered as {role}", fg=T["success"])
            clear_user_form()
            status_lbl.config(text=f"✓  User '{username}' registered as {role}", fg=T["success"])
        else:
            messagebox.showerror("Error", message)

    # Buttons
    bf = Frame(card, bg=T["panel"])
    bf.pack(fill=X, padx=20, pady=(10, 20))
    mk_btn(bf, "Register User", register_user, width=16).pack(side=LEFT, padx=(0, 8))
    mk_btn(bf, "Clear", clear_user_form, secondary=True, width=10).pack(side=LEFT)

    return frame


# Show the user registration page in the application.
def open_user_registration():
    if 'user_registration' not in pages:
        pages['user_registration'] = build_user_registration_page(page_container)
    show_page('user_registration')

# ============== USER MANAGEMENT WINDOW ==============
def build_user_management_page(parent):
    frame = Frame(parent, bg=T["bg"])

    page_header(frame, "User Management", "View and manage system user accounts")

    body = Frame(frame, bg=T["bg"])
    body.pack(fill=BOTH, expand=True, padx=24, pady=16)

    # ── Left: user table ─────────────────────────────────────
    left = Frame(body, bg=T["panel"],
                 highlightthickness=1, highlightbackground=T["border"])
    left.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 12))

    section_label(left, "All System Users")

    tf = Frame(left, bg=T["panel"])
    tf.pack(fill=BOTH, expand=True, padx=16, pady=(0, 16))

    columns = ("Username", "Role", "Created")
    tree = ttk.Treeview(tf, columns=columns, show="headings")
    tree.heading("Username", text="Username")
    tree.heading("Role",     text="Role")
    tree.heading("Created",  text="Created")
    tree.column("Username", width=180, anchor=W, minwidth=100)
    tree.column("Role",     width=130, anchor=W, minwidth=80)
    tree.column("Created",  width=200, anchor=W, minwidth=120)
    sb = ttk.Scrollbar(tf, orient=VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side=LEFT, fill=BOTH, expand=True)
    sb.pack(side=RIGHT, fill=Y)

    # ── Right: detail panel ───────────────────────────────────
    right = Frame(body, bg=T["panel"],
                  highlightthickness=1, highlightbackground=T["border"])
    right.pack(side=LEFT, fill=Y)
    right.columnconfigure(0, weight=1)

    section_label(right, "User Details")

    detail_body = Frame(right, bg=T["panel"])
    detail_body.pack(fill=BOTH, expand=True, padx=16, pady=4)

    def detail_row(label, val="—"):
        row = Frame(detail_body, bg=T["bg"],
                    highlightthickness=1, highlightbackground=T["border"])
        row.pack(fill=X, pady=3)
        Label(row, text=label.upper(), font=FONT["tag"],
              bg=T["bg"], fg=T["muted"],
              width=12, anchor=W).pack(side=LEFT, padx=(10, 6), pady=8)
        lbl = Label(row, text=val, font=FONT["body_b"],
                    bg=T["bg"], fg=T["text"], anchor=W)
        lbl.pack(side=LEFT, fill=X, expand=True, padx=(0, 10))
        return lbl

    lbl_user  = detail_row("Username")
    lbl_role  = detail_row("Role")
    lbl_cdate = detail_row("Created")
    lbl_login = detail_row("Last Login")

    def load_users():
        for item in tree.get_children():
            tree.delete(item)
        user_db = get_user_db()
        users = user_db.get_all_users()
        if not users:
            tree.insert("", END, values=("No users found", "—", "—"))
            return
        for i, (username, ud) in enumerate(users.items()):
            tag = "even" if i % 2 == 0 else "odd"
            tree.insert("", END, tags=(tag,), values=(
                username,
                ud.get("role", "N/A"),
                ud.get("created_date", "N/A")))
        tree.tag_configure("even", background=T["row_even"])
        tree.tag_configure("odd",  background=T["row_odd"])

    def on_select(event):
        sel = tree.selection()
        if not sel:
            return
        item = tree.item(sel)
        username = item["values"][0]
        if username == "No users found":
            return
        user_db = get_user_db()
        ud = user_db.get_all_users().get(username)
        if ud:
            lbl_user.config(text=username)
            lbl_role.config(text=ud.get("role", "N/A"))
            lbl_cdate.config(text=ud.get("created_date", "N/A"))
            lbl_login.config(text=ud.get("last_login") or "Never")

    tree.bind("<<TreeviewSelect>>", on_select)

    bf = Frame(right, bg=T["panel"])
    bf.pack(fill=X, padx=16, pady=(12, 16), anchor=W)
    mk_btn(bf, "⟳  Refresh List", load_users, secondary=True, width=14).pack(anchor=W)

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
_shared_user_db = None

def get_user_db():
    """Return a shared UserDatabase instance, creating it if needed."""
    global _shared_user_db
    if _shared_user_db is None:
        _shared_user_db = UserDatabase()
    return _shared_user_db

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
        user_db = get_user_db()
        total_users = len(user_db.get_all_users())
    return total_patients, total_users, recent_patients


# Create a dashboard summary card widget.
def create_card(parent, title, value, subtitle):
    return stat_card(parent, title, value, subtitle)


# Build the main dashboard page layout and summary table.
def build_dashboard_page(parent, user_data):
    frame = Frame(parent, bg=T["bg"])
    total_patients, total_users, recent_patients = create_dashboard_summary(user_data)

    page_header(frame, "Dashboard",
                f"Welcome, {user_data['username']}  ·  {user_data['role']}")

    # ── Stat cards row (pack-based) ───────────────────────────
    cards_row = Frame(frame, bg=T["bg"])
    cards_row.pack(fill=X, padx=24, pady=(18, 0))

    c1 = create_card(cards_row, "Total Patients", str(total_patients), "Registered in the system")
    c1.pack(side=LEFT, expand=True, fill=X, padx=(0, 10))

    if user_data.get("role") == "Administrator":
        c2 = create_card(cards_row, "System Users", str(total_users), "Active user accounts")
    else:
        c2 = create_card(cards_row, "Your Role", user_data.get("role", "Staff"), "Access level")
    c2.pack(side=LEFT, expand=True, fill=X, padx=(0, 10))

    c3 = create_card(cards_row, "Recent Registrations", str(len(recent_patients)), "Latest patient records")
    c3.pack(side=LEFT, expand=True, fill=X)

    # ── Recent patients table ─────────────────────────────────
    tbl_card = Frame(frame, bg=T["card"],
                     highlightthickness=1, highlightbackground=T["border"])
    tbl_card.pack(fill=BOTH, expand=True, padx=24, pady=18)

    Label(tbl_card, text="RECENT PATIENTS", font=("Helvetica", 9, "bold"),
          bg=T["card"], fg=T["accent"]).pack(anchor=W, padx=16, pady=(14, 4))
    Frame(tbl_card, bg=T["border"], height=1).pack(fill=X, padx=16, pady=(0, 8))

    tf = Frame(tbl_card, bg=T["card"])
    tf.pack(fill=BOTH, expand=True, padx=16, pady=(0, 16))

    columns = ("ID", "Name", "Age", "Gender", "Registered By")
    tree = ttk.Treeview(tf, columns=columns, show="headings", height=14)
    tree.heading("ID",            text="Patient ID")
    tree.heading("Name",          text="Full Name")
    tree.heading("Age",           text="Age")
    tree.heading("Gender",        text="Gender")
    tree.heading("Registered By", text="Registered By")
    tree.column("ID",            width=110, anchor=W)
    tree.column("Name",          width=280, anchor=W)
    tree.column("Age",           width=60,  anchor=CENTER)
    tree.column("Gender",        width=90,  anchor=CENTER)
    tree.column("Registered By", width=180, anchor=W)

    sb = ttk.Scrollbar(tf, orient=VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side=LEFT, fill=BOTH, expand=True)
    sb.pack(side=RIGHT, fill=Y)

    for i, pd in enumerate(recent_patients):
        full_name = f"{pd.get('first_name','')} {pd.get('last_name','')}".strip().upper()
        tag = "alt" if i % 2 else ""
        tree.insert("", END, tags=(tag,), values=(
            pd.get("patient_id", "N/A"), full_name,
            pd.get("age", "N/A"),
            (pd.get("gender") or "N/A").upper(),
            (pd.get("registered_by") or "N/A").upper()
        ))
    tree.tag_configure("alt", background=T["row_alt"])

    page_refreshers["dashboard"] = lambda: refresh_dashboard_frame(user_data)
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


# Build the patient list page showing all registered patients.
def build_patient_list_page(parent):
    frame = Frame(parent, bg=T["bg"])
    db = PatientDatabase()

    page_header(frame, "Patient List", "All registered patient records")

    toolbar = Frame(frame, bg=T["bg"])
    toolbar.pack(fill=X, padx=24, pady=(12, 0))
    mk_btn(toolbar, "Refresh", lambda: load_patients(), width=12).pack(side=LEFT)

    tbl_card = Frame(frame, bg=T["panel"],
                     highlightthickness=1, highlightbackground=T["border"])
    tbl_card.pack(fill=BOTH, expand=True, padx=24, pady=16)

    section_label(tbl_card, "All Patients")

    tf = Frame(tbl_card, bg=T["panel"])
    tf.pack(fill=BOTH, expand=True, padx=16, pady=(0, 16))

    columns = ("ID", "Name", "Age", "Gender", "Birth Date", "Phone", "Registered By", "Date Registered")
    tree = ttk.Treeview(tf, columns=columns, show="headings")
    tree.heading("ID",              text="Patient ID")
    tree.heading("Name",            text="Full Name")
    tree.heading("Age",             text="Age")
    tree.heading("Gender",          text="Gender")
    tree.heading("Birth Date",      text="Birth Date")
    tree.heading("Phone",           text="Phone")
    tree.heading("Registered By",   text="Registered By")
    tree.heading("Date Registered", text="Date Registered")
    tree.column("ID",              width=100, anchor=W,      minwidth=70)
    tree.column("Name",            width=210, anchor=W,      minwidth=120)
    tree.column("Age",             width=55,  anchor=CENTER, minwidth=40)
    tree.column("Gender",          width=80,  anchor=CENTER, minwidth=55)
    tree.column("Birth Date",      width=105, anchor=CENTER, minwidth=80)
    tree.column("Phone",           width=125, anchor=W,      minwidth=80)
    tree.column("Registered By",   width=140, anchor=W,      minwidth=80)
    tree.column("Date Registered", width=160, anchor=W,      minwidth=100)
    sb = ttk.Scrollbar(tf, orient=VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side=LEFT, fill=BOTH, expand=True)
    sb.pack(side=RIGHT, fill=Y)

    def load_patients():
        for item in tree.get_children():
            tree.delete(item)
        patients = db.get_all_patients()
        if not patients:
            tree.insert("", END, values=("No patients found","","","","","","",""))
            return
        for i, pd2 in enumerate(patients.values()):
            full_name = " ".join([
                pd2.get("first_name",""), pd2.get("middle_name",""), pd2.get("last_name","")
            ]).strip().upper()
            tag = "even" if i % 2 == 0 else "odd"
            tree.insert("", END, tags=(tag,), values=(
                pd2.get("patient_id","N/A"), full_name or "N/A",
                pd2.get("age","N/A"),
                (pd2.get("gender") or "N/A").upper(),
                pd2.get("birth_date","N/A"),
                (pd2.get("phone") or "N/A").upper(),
                (pd2.get("registered_by") or "N/A").upper(),
                pd2.get("registration_date","N/A")
            ))
        tree.tag_configure("even", background=T["row_even"])
        tree.tag_configure("odd",  background=T["row_odd"])

    page_refreshers["patient_list"] = lambda: (
        pages.__setitem__("patient_list", build_patient_list_page(parent)) or show_page("patient_list")
    )
    load_patients()
    return frame


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
    window.title(f"Hospital Information System  —  {user_data['username']}")
    window.geometry("1280x800")
    window.minsize(960, 640)
    window.configure(bg=T["bg"])
    window.resizable(True, True)

    try:
        window.iconbitmap(resource_path("qphn.ico"))
    except Exception:
        try:
            icon = PhotoImage(file=resource_path("qphn.jpg"))
            window.iconphoto(True, icon)
        except Exception:
            pass

    apply_styles()

    # ── Top bar ──────────────────────────────────────────────
    topbar = Frame(window, bg=T["panel"],
                   highlightthickness=1, highlightbackground=T["border"])
    topbar.pack(fill=X)

    Frame(topbar, bg=T["accent"], width=4).pack(side=LEFT, fill=Y)

    badge = Frame(topbar, bg=T["accent"], width=36, height=36)
    badge.pack_propagate(False)
    badge.pack(side=LEFT, padx=(14, 12), pady=10)
    Label(badge, text="H", font=("Georgia", 15, "bold"),
          bg=T["accent"], fg=T["white"]).place(relx=0.5, rely=0.5, anchor=CENTER)

    Label(topbar, text="Hospital Information System",
          font=("Georgia", 13, "bold"),
          bg=T["panel"], fg=T["text"]).pack(side=LEFT)

    # Right side of topbar
    right_bar = Frame(topbar, bg=T["panel"])
    right_bar.pack(side=RIGHT, padx=20, pady=8)

    role_badge = Frame(right_bar, bg=T["accent_lt"],
                       highlightthickness=1, highlightbackground=T["accent"])
    role_badge.pack(side=RIGHT, padx=(8, 0))
    Label(role_badge, text=user_data.get("role", "Staff"),
          font=FONT["tag"], bg=T["accent_lt"], fg=T["accent"],
          padx=8, pady=3).pack()

    Label(right_bar, text=user_data["username"],
          font=FONT["body_b"], bg=T["panel"], fg=T["text"]).pack(side=RIGHT)
    Label(right_bar, text="Logged in as  ",
          font=FONT["small"], bg=T["panel"], fg=T["muted"]).pack(side=RIGHT)

    # ── Body ─────────────────────────────────────────────────
    body = Frame(window, bg=T["bg"])
    body.pack(fill=BOTH, expand=True)
    body.rowconfigure(0, weight=1)
    body.columnconfigure(1, weight=1)

    # ── Sidebar ──────────────────────────────────────────────
    sidebar = Frame(body, bg=T["sidebar"], width=228)
    sidebar.pack(side=LEFT, fill=Y)
    sidebar.pack_propagate(False)
    sidebar.rowconfigure(99, weight=1)  # pushes exit to bottom

    # Sidebar header
    sh = Frame(sidebar, bg=T["sidebar"])
    sh.pack(fill=X, padx=16, pady=(18, 6))
    Label(sh, text="NAVIGATION", font=FONT["tag"],
          bg=T["sidebar"], fg="#4a6080").pack(anchor=W)

    Frame(sidebar, bg="#2a3f5c", height=1).pack(fill=X, padx=16, pady=(0, 8))

    active_nav = [None]

    def nav_btn(text, icon, command, section=False, danger=False):
        if section:
            Frame(sidebar, bg="#2a3f5c", height=1).pack(fill=X, padx=16, pady=(8, 4))
            Label(sidebar, text=text.upper(), font=FONT["tag"],
                  bg=T["sidebar"], fg="#4a6080").pack(anchor=W, padx=18, pady=(2, 4))
            return None

        norm_bg  = T["sidebar"]
        hover_bg = T["sidebar2"]
        act_bg   = T["accent"]

        f = Frame(sidebar, bg=norm_bg, cursor="hand2")
        f.pack(fill=X, padx=8, pady=2)

        accent_bar = Frame(f, bg=norm_bg, width=3)
        accent_bar.pack(side=LEFT, fill=Y)

        inner = Frame(f, bg=norm_bg)
        inner.pack(fill=X, padx=(8, 12), pady=9)

        ic_color = T["danger"] if danger else "#7ba7cc"
        tx_color = T["danger"] if danger else "#c8d8e8"

        ic_lbl = Label(inner, text=icon, font=("Calibri", 12),
                       bg=norm_bg, fg=ic_color)
        ic_lbl.pack(side=LEFT)
        tx_lbl = Label(inner, text=text, font=FONT["nav"],
                       bg=norm_bg, fg=tx_color)
        tx_lbl.pack(side=LEFT, padx=(10, 0))

        def on_enter(e):
            if active_nav[0] is not f:
                for w in [f, inner, ic_lbl, tx_lbl, accent_bar]:
                    w.config(bg=hover_bg)
        def on_leave(e):
            if active_nav[0] is not f:
                for w in [f, inner, ic_lbl, tx_lbl, accent_bar]:
                    w.config(bg=norm_bg)
        def on_click(e=None):
            # Deactivate previous
            if active_nav[0] and active_nav[0] is not f:
                prev = active_nav[0]
                for w in prev.winfo_children():
                    w.config(bg=norm_bg)
                    for ww in w.winfo_children():
                        try: ww.config(bg=norm_bg)
                        except: pass
                prev.config(bg=norm_bg)
            # Activate this
            if not danger:
                active_nav[0] = f
                for w in [f, inner, ic_lbl, tx_lbl]:
                    w.config(bg=act_bg)
                accent_bar.config(bg=T["white"])
                tx_lbl.config(fg=T["white"])
                ic_lbl.config(fg=T["white"])
            command()

        for w in [f, inner, ic_lbl, tx_lbl, accent_bar]:
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            w.bind("<Button-1>", on_click)

        return f

    db_btn  = nav_btn("Dashboard",            "⊞", lambda: open_dashboard(user_data))
    reg_btn = nav_btn("Patient Registration", "＋", lambda: open_patient_registration(user_data))
    srch_btn= nav_btn("Search Patient",       "⌕", open_search_patient)
    list_btn= nav_btn("Patient List",         "≡", open_patient_list)

    if user_data.get("role") == "Administrator":
        nav_btn("Administration", "", None, section=True)
        nav_btn("User Registration", "⊕", open_user_registration)
        nav_btn("User Management",   "⊞", open_user_management)

    # Spacer to push exit down
    Frame(sidebar, bg=T["sidebar"]).pack(fill=BOTH, expand=True)
    Frame(sidebar, bg="#2a3f5c", height=1).pack(fill=X, padx=16, pady=(0, 4))
    nav_btn("Exit Application", "⏻", window.quit, danger=True)
    Frame(sidebar, bg=T["sidebar"], height=8).pack(fill=X)

    # ── Content area ─────────────────────────────────────────
    content = Frame(body, bg=T["bg"])
    content.pack(side=LEFT, fill=BOTH, expand=True)
    content.rowconfigure(0, weight=1)
    content.columnconfigure(0, weight=1)

    page_container = Frame(content, bg=T["bg"])
    page_container.pack(fill=BOTH, expand=True)
    page_container.rowconfigure(0, weight=1)
    page_container.columnconfigure(0, weight=1)

    pages["dashboard"]            = build_dashboard_page(page_container, user_data)
    pages["patient_registration"] = build_patient_registration_page(page_container, user_data)
    pages["search_patient"]       = build_search_patient_page(page_container)
    if user_data.get("role") == "Administrator":
        pages["user_registration"] = build_user_registration_page(page_container)
        pages["user_management"]   = build_user_management_page(page_container)

    # Activate dashboard nav button
    if db_btn:
        db_btn.event_generate("<Button-1>")

    show_page("dashboard")
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
    frame = Frame(parent, bg=T["bg"])
    frame.rowconfigure(1, weight=1)
    frame.columnconfigure(0, weight=1)
    db = PatientDatabase()

    page_header(frame, "Patient Registration", "Register a new patient into the system")

    # Scrollable canvas
    canvas = Canvas(frame, bg=T["bg"], highlightthickness=0)
    sb = ttk.Scrollbar(frame, orient=VERTICAL, command=canvas.yview)
    sb.pack(side=RIGHT, fill=Y)
    canvas.pack(side=LEFT, fill=BOTH, expand=True)
    canvas.configure(yscrollcommand=sb.set)

    cf = Frame(canvas, bg=T["bg"])
    cw = canvas.create_window((0, 0), window=cf, anchor="nw")

    def _resize_cf(e): canvas.configure(scrollregion=canvas.bbox("all"))
    def _resize_cw(e): canvas.itemconfig(cw, width=e.width)
    cf.bind("<Configure>", _resize_cf)
    canvas.bind("<Configure>", _resize_cw)
    canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    outer = Frame(cf, bg=T["bg"])
    outer.pack(fill=BOTH, expand=True, padx=24, pady=16)
    outer.columnconfigure(0, weight=1)

    # ── Patient ID badge ──────────────────────────────────────
    id_card = Frame(outer, bg=T["panel"],
                    highlightthickness=1, highlightbackground=T["border"])
    id_card.pack(fill=X, pady=(0, 14))
    id_inner = Frame(id_card, bg=T["panel"])
    id_inner.pack(fill=X, padx=20, pady=12)
    Label(id_inner, text="AUTO-ASSIGNED PATIENT ID",
          font=FONT["tag"], bg=T["panel"], fg=T["muted"]).pack(side=LEFT, padx=(0, 16))
    patient_id_label = Label(id_inner, text="",
                             font=FONT["mono"],
                             bg=T["accent_lt"], fg=T["accent"],
                             padx=14, pady=4,
                             highlightthickness=1, highlightbackground=T["accent"])
    patient_id_label.pack(side=LEFT)
    next_id = db.generate_next_patient_id()
    patient_id_label.config(text=next_id)

    # ── Section helper ────────────────────────────────────────
    def section(title):
        c = Frame(outer, bg=T["panel"],
                  highlightthickness=1, highlightbackground=T["border"])
        c.pack(fill=X, pady=(0, 12))
        section_label(c, title)
        g = Frame(c, bg=T["panel"])
        g.pack(fill=X, padx=20, pady=(0, 16))
        g.columnconfigure(1, weight=1)
        g.columnconfigure(3, weight=1)
        return g

    def fld(grid, label, row, col=0, combo_var=None, combo_vals=None, show=None, date=False):
        c = col
        Label(grid, text=label.upper(), font=FONT["tag"],
              bg=T["panel"], fg=T["muted"]).grid(
            row=row*2, column=c, sticky=W, pady=(10, 3), padx=(0 if c == 0 else 16, 8))
        if combo_var and combo_vals:
            w = mk_combo(grid, combo_var, combo_vals, width=24)
            w.grid(row=row*2+1, column=c, sticky=EW, ipady=6,
                   padx=(0 if c == 0 else 16, 16))
        elif date and DateEntry:
            w = DateEntry(grid, width=24, date_pattern="yyyy-mm-dd", font=FONT["body"],
                          background=T["accent"], foreground=T["white"],
                          headersbackground=T["accent"])
            w.grid(row=row*2+1, column=c, sticky=EW,
                   padx=(0 if c == 0 else 16, 16))
        else:
            w = mk_entry(grid, width=24, show=show)
            w.grid(row=row*2+1, column=c, sticky=EW, ipady=7,
                   padx=(0 if c == 0 else 16, 16))
            if not show and not date:
                w.bind("<KeyRelease>", lambda e, x=w: uppercase_entry_widget(x))
            if date and not DateEntry:
                w.bind("<KeyRelease>", lambda e, x=w: format_birthdate_entry(x))
        return w

    # Personal info
    g1 = section("Personal Information")
    name_entry        = fld(g1, "First Name",   0, 0)
    middle_name_entry = fld(g1, "Middle Name",  0, 2)
    last_name_entry   = fld(g1, "Last Name",    1, 0)
    age_entry         = fld(g1, "Age",          1, 2)
    gender_var        = StringVar(value="MALE")
    fld(g1, "Gender",       2, 0, combo_var=gender_var, combo_vals=["MALE","FEMALE","OTHER"])
    civil_status_var  = StringVar(value="SINGLE")
    fld(g1, "Civil Status", 2, 2, combo_var=civil_status_var,
        combo_vals=["SINGLE","MARRIED","WIDOWED","DIVORCED"])
    nationality_entry = fld(g1, "Nationality",  3, 0)
    birth_date_entry  = fld(g1, "Birth Date",   3, 2, date=True)
    birth_place_entry = fld(g1, "Birth Place",  4, 0)

    # Contact info
    g2 = section("Contact Information")
    phone_entry     = fld(g2, "Phone Number",      0, 0)
    email_entry     = fld(g2, "Email Address",     0, 2)
    address_entry   = fld(g2, "Address",           1, 0)
    emergency_entry = fld(g2, "Emergency Contact", 1, 2)

    def clear_patient_form():
        for w in [name_entry, middle_name_entry, last_name_entry, age_entry,
                  phone_entry, email_entry, address_entry, birth_place_entry,
                  nationality_entry, emergency_entry]:
            w.delete(0, END)
        if hasattr(birth_date_entry, "set_date"):
            birth_date_entry.set_date(datetime.today())
        else:
            birth_date_entry.delete(0, END)
        civil_status_var.set("SINGLE")
        gender_var.set("MALE")

    def register_patient(force=False):
        patient_id = patient_id_label.cget("text")
        first_name = name_entry.get().strip()
        last_name  = last_name_entry.get().strip()

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
            messagebox.showerror("Error", "Birth date must be in YYYY-MM-DD format")
            return

        patient_data = {
            "first_name":    first_name.upper(),
            "middle_name":   middle_name_entry.get().strip().upper(),
            "last_name":     last_name.upper(),
            "age":           age_entry.get(),
            "gender":        gender_var.get().upper(),
            "birth_date":    birth_date_value or None,
            "birth_place":   birth_place_entry.get().strip().upper(),
            "civil_status":  civil_status_var.get().upper(),
            "nationality":   nationality_entry.get().strip().upper(),
            "registered_by": (user_data.get("username") if user_data else "").upper(),
            "phone":         phone_entry.get().strip().upper(),
            "email":         email_entry.get().strip().upper(),
            "address":       address_entry.get().strip().upper(),
            "medical_history": ""
        }

        if not force and db.has_duplicate_patient(patient_data):
            messagebox.showwarning("Duplicate Patient",
                "A patient with the same name/birth date already exists.\n"
                "Use Save Anyway to proceed.")
            return
        if force and not messagebox.askyesno("Confirm", "Duplicate detected. Save anyway?"):
            return

        db.add_patient(patient_id, patient_data)
        messagebox.showinfo("Registered",
            f"Patient {first_name} {last_name} registered.\nID: {patient_id}")

        for key in ("patient_list", "dashboard"):
            r = page_refreshers.get(key)
            if r: r()

        patient_id_label.config(text=db.generate_next_patient_id())
        clear_patient_form()

    # ── Action buttons ────────────────────────────────────────
    bf = Frame(outer, bg=T["bg"])
    bf.pack(pady=(4, 20), anchor=W)
    mk_btn(bf, "Register Patient", register_patient, width=18).pack(side=LEFT, padx=(0, 8))
    mk_btn(bf, "Save Anyway", lambda: register_patient(force=True),
           color=T["warning"], width=14).pack(side=LEFT, padx=(0, 8))
    mk_btn(bf, "Clear Form", clear_patient_form, secondary=True, width=12).pack(side=LEFT)

    return frame


# Open the patient registration page.
def open_patient_registration(user_data=None):
    if 'patient_registration' not in pages:
        pages['patient_registration'] = build_patient_registration_page(page_container, user_data)
    show_page('patient_registration')


# Build the patient search user interface page.
def build_search_patient_page(parent):
    frame = Frame(parent, bg=T["bg"])
    frame.rowconfigure(3, weight=1)
    frame.columnconfigure(0, weight=1)
    db = PatientDatabase()
    selected_patient_id = StringVar(value="")

    page_header(frame, "Search Patient Records", "Find, view and edit patient records")

    # ── Search card ────────────────────────────────────────────
    sc = Frame(frame, bg=T["panel"],
               highlightthickness=1, highlightbackground=T["border"])
    sc.pack(fill=X, padx=24, pady=(14, 0))
    sc.columnconfigure(0, weight=2)
    sc.columnconfigure(1, weight=1)
    sc.columnconfigure(2, weight=1)
    sc.columnconfigure(3, weight=0)

    section_label(sc, "Search Filters")

    si = Frame(sc, bg=T["panel"])
    si.pack(fill=X, padx=20, pady=(0, 16))
    si.columnconfigure(0, weight=2)
    si.columnconfigure(1, weight=1)
    si.columnconfigure(2, weight=1)

    def sf(label, col):
        Label(si, text=label.upper(), font=FONT["tag"],
              bg=T["panel"], fg=T["muted"]).grid(
            row=0, column=col, sticky=W, pady=(0, 4),
            padx=(0 if col == 0 else 12, 8))
        e = mk_entry(si, width=24)
        e.grid(row=1, column=col, sticky=EW, ipady=8,
               padx=(0 if col == 0 else 12, 12))
        e.bind("<KeyRelease>", lambda ev: uppercase_entry_widget(e))
        e.bind("<Return>", lambda ev: search_patient())
        return e

    search_entry    = sf("ID or Full Name", 0)
    firstname_entry = sf("First Name", 1)
    lastname_entry  = sf("Last Name",  2)

    btn_row = Frame(sc, bg=T["panel"])
    btn_row.pack(anchor=W, padx=20, pady=(0, 14))
    mk_btn(btn_row, "Search", lambda: search_patient(), width=12).pack(side=LEFT, padx=(0, 8))
    mk_btn(btn_row, "Clear",  lambda: clear_search(), secondary=True, width=10).pack(side=LEFT)

    # ── Results table ──────────────────────────────────────────
    tbl_card = Frame(frame, bg=T["panel"],
                     highlightthickness=1, highlightbackground=T["border"])
    tbl_card.pack(fill=BOTH, expand=True, padx=24, pady=(10, 0))
    tbl_card.rowconfigure(2, weight=1)
    tbl_card.columnconfigure(0, weight=1)

    # Results count label
    results_lbl = Label(tbl_card, text="RESULTS", font=FONT["tag"],
                        bg=T["panel"], fg=T["accent"])
    results_lbl.pack(anchor=W, padx=20, pady=(12, 2))
    Frame(tbl_card, bg=T["border"], height=1).pack(fill=X, padx=20, pady=(0, 6))

    rf = Frame(tbl_card, bg=T["panel"])
    rf.pack(fill=BOTH, expand=True, padx=16, pady=(0, 8))
    rf.rowconfigure(0, weight=1)
    rf.columnconfigure(0, weight=1)

    columns = ("ID", "Name", "Age", "Gender", "Birth Date", "Nationality", "Phone", "Email", "Registered")
    results_tree = ttk.Treeview(rf, columns=columns, show="headings", height=7)
    for col in columns:
        results_tree.heading(col, text=col)
    results_tree.column("ID",          width=95,  anchor=W,      minwidth=70)
    results_tree.column("Name",        width=175, anchor=W,      minwidth=100)
    results_tree.column("Age",         width=50,  anchor=CENTER, minwidth=35)
    results_tree.column("Gender",      width=70,  anchor=CENTER, minwidth=50)
    results_tree.column("Birth Date",  width=95,  anchor=CENTER, minwidth=70)
    results_tree.column("Nationality", width=110, anchor=W,      minwidth=70)
    results_tree.column("Phone",       width=110, anchor=W,      minwidth=70)
    results_tree.column("Email",       width=170, anchor=W,      minwidth=100)
    results_tree.column("Registered",  width=130, anchor=W,      minwidth=80)


    results_sb = ttk.Scrollbar(rf, orient=VERTICAL, command=results_tree.yview)
    results_tree.configure(yscrollcommand=results_sb.set)
    results_tree.pack(side=LEFT, fill=BOTH, expand=True)
    results_sb.pack(side=RIGHT, fill=Y)

    # ── Edit panel (scrollable) ────────────────────────────────
    edit_card = Frame(frame, bg=T["panel"],
                      highlightthickness=1, highlightbackground=T["border"])
    edit_card.pack(fill=X, padx=24, pady=(10, 16))
    edit_card.columnconfigure(0, weight=1)

    section_label(edit_card, "Edit Selected Patient")

    # Scrollable canvas wrapper
    edit_canvas = Canvas(edit_card, bg=T["panel"], highlightthickness=0, height=260)
    edit_sb = ttk.Scrollbar(edit_card, orient=VERTICAL, command=edit_canvas.yview)
    edit_sb.pack(side=RIGHT, fill=Y, padx=(0, 4), pady=(0, 8))
    edit_canvas.pack(side=LEFT, fill=BOTH, expand=True, padx=(4, 0), pady=(0, 8))
    edit_canvas.configure(yscrollcommand=edit_sb.set)

    edit_frame = Frame(edit_canvas, bg=T["panel"])
    edit_frame_id = edit_canvas.create_window((0, 0), window=edit_frame, anchor="nw")

    def _edit_resize(e):
        edit_canvas.configure(scrollregion=edit_canvas.bbox("all"))
    def _edit_canvas_resize(e):
        edit_canvas.itemconfig(edit_frame_id, width=e.width)
    edit_frame.bind("<Configure>", _edit_resize)
    edit_canvas.bind("<Configure>", _edit_canvas_resize)
    edit_canvas.bind("<Enter>", lambda e: edit_canvas.bind_all(
        "<MouseWheel>", lambda ev: edit_canvas.yview_scroll(int(-1*(ev.delta/120)), "units")))
    edit_canvas.bind("<Leave>", lambda e: edit_canvas.unbind_all("<MouseWheel>"))

    for ci in (1, 3, 5, 7):
        edit_frame.columnconfigure(ci, weight=1)

    def ef(label, row, col=0, combo_var=None, combo_vals=None, readonly=False, date=False):
        Label(edit_frame, text=label.upper(), font=FONT["tag"],
              bg=T["panel"], fg=T["muted"]).grid(
            row=row*2, column=col, sticky=W, pady=(8, 3),
            padx=(0 if col == 0 else 14, 6))
        if combo_var and combo_vals:
            w = mk_combo(edit_frame, combo_var, combo_vals, width=18)
            w.grid(row=row*2+1, column=col, sticky=EW, ipady=5,
                   padx=(0 if col == 0 else 14, 14))
        elif date and DateEntry:
            w = DateEntry(edit_frame, width=18, date_pattern="yyyy-mm-dd", font=FONT["body"],
                          background=T["accent"], foreground=T["white"],
                          headersbackground=T["accent"])
            w.grid(row=row*2+1, column=col, sticky=EW,
                   padx=(0 if col == 0 else 14, 14))
        else:
            w = mk_entry(edit_frame, width=20, readonly=readonly)
            if readonly:
                kw2 = dict(textvariable=selected_patient_id)
                w.config(**kw2)
            w.grid(row=row*2+1, column=col, sticky=EW, ipady=6,
                   padx=(0 if col == 0 else 14, 14))
            if not readonly and not date:
                w.bind("<KeyRelease>", lambda e, x=w: uppercase_entry_widget(x))
            if date and not DateEntry:
                w.bind("<KeyRelease>", lambda e, x=w: format_birthdate_entry(x))
        return w

    patient_id_entry      = ef("Patient ID",    0, 0, readonly=True)
    edit_first_name       = ef("First Name",    0, 2)
    edit_middle_name      = ef("Middle Name",   0, 4)
    edit_last_name        = ef("Last Name",     0, 6)
    edit_age              = ef("Age",           1, 0)
    edit_gender_var       = StringVar(value="MALE")
    ef("Gender",        1, 2, combo_var=edit_gender_var, combo_vals=["MALE","FEMALE","OTHER"])
    edit_birth_date       = ef("Birth Date",    1, 4, date=True)
    edit_birth_place      = ef("Birth Place",   1, 6)
    edit_civil_status_var = StringVar(value="SINGLE")
    ef("Civil Status",  2, 0, combo_var=edit_civil_status_var,
       combo_vals=["SINGLE","MARRIED","WIDOWED","DIVORCED"])
    edit_nationality      = ef("Nationality",   2, 2)
    edit_phone            = ef("Phone",         2, 4)
    edit_email            = ef("Email",         2, 6)
    edit_address          = ef("Address",       3, 0)
    edit_medical_history  = ef("Medical History", 3, 2)

    registered_by_label = Label(edit_frame, text="Registered By: N/A",
                                font=FONT["small"], bg=T["panel"], fg=T["muted"])
    registered_by_label.grid(row=8, column=0, columnspan=8, sticky=W, pady=(6, 0))

    def clear_edit_form():
        selected_patient_id.set("")
        for w in [edit_first_name, edit_middle_name, edit_last_name, edit_age,
                  edit_birth_place, edit_nationality, edit_phone, edit_email,
                  edit_address, edit_medical_history]:
            try:
                w.config(state="normal")
            except Exception:
                pass
            w.delete(0, END)
        edit_gender_var.set("MALE")
        if hasattr(edit_birth_date, "set_date"):
            edit_birth_date.set_date(datetime.today())
        else:
            edit_birth_date.delete(0, END)
        edit_civil_status_var.set("SINGLE")
        registered_by_label.config(text="Registered By: N/A")

# Load search results into the treeview, handling empty results and formatting data.
    def load_results(patients):
        for item in results_tree.get_children():
            results_tree.delete(item)
        if not patients:
            results_tree.insert("", END, values=("No results found","","","","","","","",""))
            results_lbl.config(text="RESULTS  ·  0 records")
            return
        for i, (pid, pd) in enumerate(patients.items()):
            full_name = " ".join([pd.get("first_name",""), pd.get("middle_name",""),
                                  pd.get("last_name","")]).strip().upper() or "N/A"
            tag = "even" if i % 2 == 0 else "odd"
            results_tree.insert("", END, tags=(tag,), values=(
                pid, full_name,
                pd.get("age","N/A"),
                (pd.get("gender") or "N/A").upper(),
                pd.get("birth_date","N/A"),
                (pd.get("nationality") or "N/A").upper(),
                (pd.get("phone") or "N/A").upper(),
                (pd.get("email") or "N/A").upper(),
                (pd.get("registered_by") or "N/A").upper()
            ))
        results_tree.tag_configure("even", background=T["row_even"])
        results_tree.tag_configure("odd",  background=T["row_odd"])
        results_lbl.config(text=f"RESULTS  ·  {len(patients)} record{'s' if len(patients) != 1 else ''}")

# Search for patient records based on ID or name, and display results.
    def search_patient():
        search_term      = search_entry.get().strip().upper()
        first_name_term  = firstname_entry.get().strip().upper()
        last_name_term   = lastname_entry.get().strip().upper()

        if not search_term and not first_name_term and not last_name_term:
            messagebox.showwarning("Warning", "Please enter a search term")
            return

        if first_name_term or last_name_term:
            combined = f"{first_name_term} {last_name_term}".strip()
            patients = db.search_patients(combined)
            if first_name_term and last_name_term:
                patients = {pid: p for pid, p in patients.items()
                            if first_name_term in (p.get("first_name") or "").upper()
                            and last_name_term in (p.get("last_name") or "").upper()}
            elif first_name_term:
                patients = {pid: p for pid, p in patients.items()
                            if first_name_term in (p.get("first_name") or "").upper()}
            else:
                patients = {pid: p for pid, p in patients.items()
                            if last_name_term in (p.get("last_name") or "").upper()}
            if search_term:
                patients.update(db.search_patients(search_term))
        else:
            patients = db.search_patients(search_term)

        load_results(patients)
        clear_edit_form()

    def clear_search():
        search_entry.delete(0, END)
        firstname_entry.delete(0, END)
        lastname_entry.delete(0, END)
        load_results({})
        clear_edit_form()
        results_lbl.config(text="RESULTS")

    def load_selected_patient(patient_data):
        clear_edit_form()
        selected_patient_id.set(patient_data.get("patient_id", ""))
        for w, key in [
            (edit_first_name,       "first_name"),
            (edit_middle_name,      "middle_name"),
            (edit_last_name,        "last_name"),
            (edit_age,              "age"),
            (edit_birth_place,      "birth_place"),
            (edit_phone,            "phone"),
            (edit_email,            "email"),
            (edit_address,          "address"),
            (edit_medical_history,  "medical_history"),
            (edit_nationality,      "nationality"),
        ]:
            try:
                w.config(state="normal")
            except Exception:
                pass
            w.delete(0, END)
            w.insert(0, patient_data.get(key, "") or "")
        edit_gender_var.set((patient_data.get("gender") or "MALE").upper())
        edit_civil_status_var.set((patient_data.get("civil_status") or "SINGLE").upper())
        if hasattr(edit_birth_date, "set_date"):
            try:
                edit_birth_date.set_date(patient_data.get("birth_date") or datetime.today())
            except Exception:
                edit_birth_date.delete(0, END)
                edit_birth_date.insert(0, patient_data.get("birth_date", "") or "")
        else:
            edit_birth_date.delete(0, END)
            edit_birth_date.insert(0, patient_data.get("birth_date", "") or "")
        registered_by_label.config(
            text=f"Registered By: {(patient_data.get('registered_by') or 'N/A').upper()}")

    def on_tree_select(event):
        sel = results_tree.selection()
        if not sel:
            return
        item = results_tree.item(sel)
        pid = item["values"][0]
        if pid == "No results found":
            return
        pd2 = db.get_patient(pid)
        if pd2:
            load_selected_patient(pd2)

    def update_patient():
        pid = selected_patient_id.get()
        if not pid:
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
        bv = edit_birth_date.get().strip()
        if bv and not validate_date(bv):
            messagebox.showerror("Error", "Please enter a valid birth date in YYYY-MM-DD format")
            return

        patient_data = {
            "first_name":      edit_first_name.get().strip().upper(),
            "middle_name":     edit_middle_name.get().strip().upper(),
            "last_name":       edit_last_name.get().strip().upper(),
            "age":             edit_age.get().strip(),
            "gender":          edit_gender_var.get().upper(),
            "birth_date":      bv or None,
            "birth_place":     edit_birth_place.get().strip().upper(),
            "civil_status":    edit_civil_status_var.get().upper(),
            "nationality":     edit_nationality.get().strip().upper(),
            "phone":           edit_phone.get().strip().upper(),
            "email":           edit_email.get().strip().upper(),
            "address":         edit_address.get().strip().upper(),
            "medical_history": edit_medical_history.get().strip().upper()
        }

        if db.update_patient(pid, patient_data):
            messagebox.showinfo("Success", f"Patient {pid} updated successfully")
            if search_entry.get().strip():
                search_patient()
            else:
                load_results({})
            for key in ("patient_list", "dashboard"):
                r = page_refreshers.get(key)
                if r: r()
        else:
            messagebox.showerror("Error", "Unable to update patient record")

    def delete_patient():
        pid = selected_patient_id.get()
        if not pid:
            messagebox.showwarning("Warning", "Select a patient record before deleting")
            return
        if not messagebox.askyesno("Confirm Delete",
                f"Delete patient record {pid}?\nThis cannot be undone."):
            return
        if db.delete_patient(pid):
            messagebox.showinfo("Deleted", f"Patient {pid} deleted successfully")
            clear_edit_form()
            if search_entry.get().strip():
                search_patient()
            else:
                load_results({})
            for key in ("patient_list", "dashboard"):
                r = page_refreshers.get(key)
                if r: r()
        else:
            messagebox.showerror("Error", "Unable to delete patient record")

    results_tree.bind("<<TreeviewSelect>>", on_tree_select)

    # Action buttons
    af = Frame(edit_card, bg=T["panel"])
    af.pack(fill=X, padx=20, pady=(0, 16))
    mk_btn(af, "Update Record", update_patient, width=16).pack(side=LEFT, padx=(0, 8))
    mk_btn(af, "Delete Record", delete_patient, danger=True, width=14).pack(side=LEFT, padx=(0, 8))
    mk_btn(af, "Clear Form",    clear_edit_form, secondary=True, width=12).pack(side=LEFT)

    load_results({})
    return frame


# Open the patient search page.
def open_search_patient():
    if 'search_patient' not in pages:
        pages['search_patient'] = build_search_patient_page(page_container)
    show_page('search_patient')

# ============== APPLICATION STARTUP ==============
if __name__ == "__main__":
    create_login_window()
