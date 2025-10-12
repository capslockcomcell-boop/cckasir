# ===================== ADMIN.PY (Master Data Laundry) =====================
import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ============ KONFIGURASI ============
SPREADSHEET_ID = "1v_3sXsGw9lNmGPSbIHytYzHzPTxa4yp4HhfS9tgXweA"
SHEET_ADMIN = "Admin"

# ============ AUTH GOOGLE ============
def authenticate_google():
    creds_dict = st.secrets["gcp_service_account"]
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(credentials)
    return client

def get_worksheet(sheet_name):
    client = authenticate_google()
    sh = client.open_by_key(SPREADSHEET_ID)
    return sh.worksheet(sheet_name)

# ============ UI ADMIN ============
def show():
    st.title("⚙️ Master Data Laundry")

    ws = get_worksheet(SHEET_ADMIN)
    df = pd.DataFrame(ws.get_all_records())

    # Kalau sheet masih kosong, buat header default
    if df.empty:
        df = pd.DataFrame(columns=["Jenis Pakaian", "Jenis Layanan", "Harga per Kg", "Parfum"])

    st.subheader("📄 Data Harga & Pilihan")
    st.dataframe(df, use_container_width=True)

    st.markdown("---")
    st.subheader("➕ Tambah / Edit Data")

    jenis_pakaian = st.text_input("Jenis Pakaian")
    jenis_layanan = st.text_input("Jenis Layanan")
    harga_per_kg = st.number_input("Harga per Kg", min_value=0.0, step=500.0)
    parfum = st.text_input("Parfum")

    if st.button("💾 Simpan Data"):
        if not jenis_pakaian or not jenis_layanan or harga_per_kg <= 0:
            st.error("⚠️ Jenis pakaian, layanan, dan harga wajib diisi.")
        else:
            new_row = [jenis_pakaian, jenis_layanan, harga_per_kg, parfum]

            # Tambah ke Google Sheet
            ws.append_row(new_row, value_input_option="USER_ENTERED")
            st.success(f"✅ Data '{jenis_layanan}' berhasil disimpan.")

            st.experimental_rerun()

    st.markdown("---")
    st.caption("ℹ️ Halaman ini hanya untuk input master data harga, layanan, pakaian & parfum.")

if __name__ == "__main__":
    show()
