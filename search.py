import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk


# 1. Database Setup & Data Fetching
def init_db():
    """Creates a temporary in-memory database and populates it."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    """
    )
    # Insert sample data
    sample_users = [("Alice",), ("Bob",), ("Charlie",), ("David",)]
    cursor.executemany("INSERT INTO users (name) VALUES (?)", sample_users)
    conn.commit()
    return conn


def fetch_users(conn):
    """Fetches all usernames from the database."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM users")
    # cursor.fetchall() returns a list of tuples: [('Alice',), ('Bob',), ...]
    # We use a list comprehension to flatten it into a list of strings: ['Alice', 'Bob', ...]
    return [row[0] for row in cursor.fetchall()]


# 2. Tkinter Event Handlers
def handle_dropdown_selection(event):
    """Triggers instantly when an item is chosen in the dropdown."""
    selected_name = combo.get()
    messagebox.showinfo("Dropdown Event", f"You chose: {selected_name}")


def handle_listbox_selection():
    """Triggers when clicking the button next to the listbox."""
    selected_indices = listbox.curselection()
    if not selected_indices:
        messagebox.showwarning("Warning", "Please select a user first!")
        return

    selected_names = [listbox.get(i) for i in selected_indices]
    messagebox.showinfo("Listbox Selection", f"Selected: {', '.join(selected_names)}")


# 3. Application Main Window
# Initialize database and get data
db_connection = init_db()
user_list = fetch_users(db_connection)

root = tk.Tk()
root.title("Tkinter Database Selection")
root.geometry("400x350")

# --- SECTION 1: Combobox (Dropdown) ---
lbl_dropdown = tk.Label(root, text="Select User (Dropdown):", font=("Arial", 10, "bold"))
lbl_dropdown.pack(pady=(15, 2))

# Pass the fetched user_list directly into the values parameter
combo = ttk.Combobox(root, values=user_list, state="readonly", width=25)
combo.current(0)
combo.pack(pady=5)

# Bind the selection event to trigger a function instantly
combo.bind("<<ComboboxSelected>>", handle_dropdown_selection)


# --- SECTION 2: Listbox (Vertical List) ---
lbl_listbox = tk.Label(root, text="Select User(s) from List:", font=("Arial", 10, "bold"))
lbl_listbox.pack(pady=(25, 2))

listbox = tk.Listbox(root, selectmode="extended", height=5, width=25)
listbox.pack(pady=5)

# Loop through the database records and insert them into the listbox
for user in user_list:
    listbox.insert(tk.END, user)

btn_listbox = tk.Button(root, text="Confirm List Selection", command=handle_listbox_selection)
btn_listbox.pack(pady=5)

# Run the app, close DB connection when the app closes
root.mainloop()
db_connection.close()
