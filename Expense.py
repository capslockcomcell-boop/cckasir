# ======================== EXPENSE.PY (v5.9 FINAL — Tambah Jenis Transaksi Cash/Transfer + Sinkronisasi Lokal Otomatis) ========================
# Updated: 2025-10-12
# Fitur:
# ✅ Input pengeluaran dengan pilihan jenis transaksi (Cash / Transfer)
# ✅ Cache lokal otomatis (CSV) jika koneksi Google Sheet gagal
# ✅ Sinkronisasi otomatis ke Google Sheet saat koneksi pulih
# ✅ Filter pengeluaran berdasarkan tanggal
# ✅ Kompatibel dengan sistem ORDER.PY v5.9

import streamlit as st
import pandas as pd
import datetime
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# =============== KONFIGURASI ===============
SPREADSHEET_ID = "1OsnO1xQFniBtEFCvGksR2KKrPt-9idE-w6-poM-wXKU"
SHEET_PENGELUARAN = "Pengeluaran"
CACHE_FILE = "pengeluaran_cache.csv"

# =============== AUTH GOOGLE ===============
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

# =============== CACHE CSV ===============
def load_local_data():
    if os.path.exists(CACHE_FILE):
        return pd.read_csv(CACHE_FILE)
    return pd.DataFrame(columns=["Tanggal", "Keterangan", "Nominal", "Jenis", "uploaded", "Jenis Transaksi"])

def save_local_data(df):
    df.to_csv(CACHE_FILE, index=False)

# =============== UPLOAD ULANG CACHE ===============
def sync_local_cache():
    df = load_local_data()
    if df.empty:
        return
    not_uploaded = df[df["uploaded"] == False]
    if not not_uploaded.empty:
        st.info(f"🔁 Mengupload ulang {len(not_uploaded)} data pengeluaran lokal...")
        for _, row in not_uploaded.iterrows():
            try:
                append_to_sheet(SHEET_PENGELUARAN, row.to_dict())
                df.loc[df["Keterangan"] == row["Keterangan"], "uploaded"] = True
            except Exception as e:
                st.warning(f"Gagal upload pengeluaran '{row['Keterangan']}': {e}")
        save_local_data(df)
        st.success("✅ Sinkronisasi cache selesai!")

# =============== SPREADSHEET OPS ===============
def append_to_sheet(sheet_name, data: dict):
    ws = get_worksheet(sheet_name)
    headers = ws.row_values(1)
    # Pastikan header Jenis Transaksi selalu ada
    if "Jenis Transaksi" not in headers:
        ws.update_cell(1, len(headers)+1, "Jenis Transaksi")
        headers.append("Jenis Transaksi")
    row = [data.get(h, "") for h in headers]
    ws.append_row(row, value_input_option="USER_ENTERED")

def read_sheet(sheet_name):
    ws = get_worksheet(sheet_name)
    df = pd.DataFrame(ws.get_all_records())
    return df

# =============== HALAMAN APP ===============
def show():
    st.title("💸 Pengeluaran Toko")
    sync_local_cache()

    tab1, tab2 = st.tabs(["➕ Input Pengeluaran", "📊 Riwayat Pengeluaran"])

    # ---------------- TAB INPUT ----------------
    with tab1:
        tanggal = st.date_input("Tanggal", value=datetime.date.today())
        keterangan = st.text_input("Keterangan", placeholder="Contoh: Bayar listrik bulan Oktober")
        nominal = st.number_input("Nominal (Rp)", min_value=0.0, format="%.0f")
        jenis = st.selectbox("Jenis Pengeluaran", ["Operasional", "Gaji", "Listrik", "Sewa", "Lainnya"])
        jenis_transaksi = st.radio("Jenis Transaksi", ["Cash", "Transfer"], horizontal=True)
        submit = st.button("💾 Simpan Pengeluaran")

        if submit:
            if not keterangan or nominal <= 0:
                st.error("❌ Keterangan dan nominal wajib diisi!")
            else:
                data = {
                    "Tanggal": tanggal.strftime("%d/%m/%Y"),
                    "Keterangan": keterangan,
                    "Nominal": nominal,
                    "Jenis": jenis,
                    "uploaded": False,
                    "Jenis Transaksi": jenis_transaksi
                }

                df = load_local_data()
                df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)

                try:
                    append_to_sheet(SHEET_PENGELUARAN, data)
                    df.loc[df["Keterangan"] == keterangan, "uploaded"] = True
                    st.success("✅ Pengeluaran berhasil disimpan ke Google Sheet!")
                except Exception as e:
                    st.warning(f"⚠️ Gagal upload ke Sheet: {e}. Disimpan lokal.")

                save_local_data(df)

    # ---------------- TAB RIWAYAT ----------------
    with tab2:
        try:
            df_pengeluaran = read_sheet(SHEET_PENGELUARAN)
        except Exception as e:
            st.warning(f"Gagal membaca sheet: {e}")
            df_pengeluaran = pd.DataFrame()

        if not df_pengeluaran.empty:
            st.subheader("📅 Filter")
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("Dari Tanggal", value=datetime.date.today().replace(day=1))
            with col2:
                end_date = st.date_input("Sampai Tanggal", value=datetime.date.today())

            # Convert date format
            df_pengeluaran["Tanggal_dt"] = pd.to_datetime(df_pengeluaran["Tanggal"], format="%d/%m/%Y", errors="coerce")
            mask = (df_pengeluaran["Tanggal_dt"] >= pd.to_datetime(start_date)) & (df_pengeluaran["Tanggal_dt"] <= pd.to_datetime(end_date))
            filtered = df_pengeluaran[mask]

            st.dataframe(filtered[["Tanggal", "Keterangan", "Nominal", "Jenis", "Jenis Transaksi"]])

            total = filtered["Nominal"].sum()
            st.metric("💰 Total Pengeluaran", f"Rp {total:,.0f}".replace(",", "."))

        else:
            st.info("Belum ada data pengeluaran.")


if __name__ == "__main__":
    show()
