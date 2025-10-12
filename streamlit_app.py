# ========================== app.py (Laundry v2.1) - Dengan Login Admin ==========================
import streamlit as st
from streamlit_option_menu import option_menu
import Order, Report, Setting, Admin, Expense, Pelanggan

# ---------------------- KONFIGURASI HALAMAN ----------------------
st.set_page_config(
    page_title="TR Laundry",
    page_icon="🧺",
    layout="centered"
)

# ---------------------- KONFIGURASI LOGIN ----------------------
# Username dan password admin
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "12345"

# Inisialisasi status login
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ---------------------- FUNGSI LOGIN ----------------------
def login_form():
    st.subheader("🔐 Login Admin")
    username = st.text_input("Username", key="login_user")
    password = st.text_input("Password", type="password", key="login_pass")
    if st.button("Login", use_container_width=True):
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            st.session_state.logged_in = True
            st.success("✅ Login berhasil!")
            st.rerun()
        else:
            st.error("❌ Username atau password salah!")

# ---------------------- FUNGSI LOGOUT ----------------------
def logout_button():
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.success("Berhasil logout.")
        st.rerun()

# ---------------------- SIDEBAR MENU ----------------------
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2933/2933180.png", width=80)
    st.markdown("## 🧺 TR Laundry")
    st.markdown("### ✨ Bersih | Wangi | Rapi")

    if not st.session_state.logged_in:
        # Menu untuk user biasa
        selected = option_menu(
            "Menu Utama",
            [
                "🧾 Order Laundry",
                "✅ Pelanggan",
                "🔐 Login Admin"
            ],
            icons=[
                "file-earmark-plus",
                "person-check",
                "lock"
            ],
            menu_icon="shop",
            default_index=0
        )
    else:
        # Menu untuk admin
        selected = option_menu(
            "Menu Admin",
            [
                "🧾 Order Laundry",
                "✅ Pelanggan",
                "💸 Pengeluaran",   # Hanya admin
                "📈 Report",
                "📦 Admin",
                "⚙️ Setting",
                "🚪 Logout"
            ],
            icons=[
                "file-earmark-plus",
                "person-check",
                "cash-coin",
                "bar-chart-line",
                "box-seam",
                "gear",
                "door-closed"
            ],
            menu_icon="shop",
            default_index=0
        )

# ---------------------- ROUTING HALAMAN ----------------------
if not st.session_state.logged_in:
    if selected == "🧾 Order Laundry":
        Order.show()
    elif selected == "✅ Pelanggan":
        Pelanggan.show()
    elif selected == "🔐 Login Admin":
        login_form()
else:
    if selected == "🧾 Order Laundry":
        Order.show()
    elif selected == "✅ Pelanggan":
        Pelanggan.show()
    elif selected == "💸 Pengeluaran":
        Expense.show()  # Admin akses Pengeluaran
    elif selected == "📈 Report":
        Report.show()
    elif selected == "📦 Admin":
        Admin.show()
    elif selected == "⚙️ Setting":
        Setting.show()
    elif selected == "🚪 Logout":
        logout_button()
