# ===================== REPORT.PY (Laundry v1.5 - FIX BERAT & DESIMAL) =====================
import streamlit as st
import pandas as pd
import datetime
import json
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests

# ------------------- CONFIG -------------------
CONFIG_FILE = "config.json"
SPREADSHEET_ID = "1v_3sXsGw9lNmGPSbIHytYzHzPTxa4yp4HhfS9tgXweA"
SHEET_ORDER = "Order"
SHEET_PENGELUARAN = "Pengeluaran"

# ------------------- AUTH GOOGLE -------------------
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
    ws = sh.worksheet(sheet_name)
    return ws

def read_sheet(sheet_name):
    """
    Membaca sheet Google dan memastikan angka desimal dengan koma (misal 5,6 → 5.6)
    terbaca dengan benar sebagai float.
    Untuk kolom 'Berat (Kg)', jika 2 digit tanpa koma, paksa jadi 2.2 misal 22 → 2.2
    """
    try:
        ws = get_worksheet(sheet_name)
        all_values = ws.get_all_values()  # ambil semua sel persis
        if not all_values:
            return pd.DataFrame()
        
        header = all_values[0]
        data = all_values[1:]
        df = pd.DataFrame(data, columns=header)

        # ------------------- NORMALISASI -------------------
        def normalize_berat(x):
            """
            Memaksa format Berat (Kg) menjadi float:
            - Jika input string ada koma: 5,3 -> 5.3
            - Jika dua digit tanpa koma: 53 -> 5.3
            - Jika satu digit: tetap 5 -> 5.0
            """
            s = str(x).strip()
            s = s.replace(",", ".")
            s = "".join([c for c in s if c.isdigit() or c == "."])
            if s == "":
                return 0.0
            if "." in s:
                return float(s)
            f = float(s)
            if f >= 10 and f < 100:
                f = f / 10
            return f

        def normalize_general(x):
            s = str(x).strip().replace(",", ".")
            s = "".join([c for c in s if c.isdigit() or c == "."])
            if s == "":
                return 0.0
            return float(s)

        for col in ["Berat (Kg)", "Harga", "Total", "Subtotal", "Diskon", "Nominal", "Harga per Kg"]:
            if col in df.columns:
                if col == "Berat (Kg)":
                    df[col] = df[col].apply(normalize_berat)
                else:
                    df[col] = df[col].apply(normalize_general)

        # Pastikan kolom string tetap aman
        for col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].astype(str)

        return df

    except Exception as e:
        st.warning(f"Gagal membaca sheet {sheet_name}: {e}")
        return pd.DataFrame()


# ------------------- UTIL -------------------
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {
        "nama_toko": "TR Laundry",
        "alamat": "Jl. Buluh Cina, Panam",
        "telepon": "087899913595"
    }

def format_rp(n):
    try:
        nnum = float(n)
        return f"Rp {nnum:,.0f}".replace(",", ".")
    except:
        return str(n)

def get_internet_date():
    try:
        resp = requests.get("https://worldtimeapi.org/api/timezone/Asia/Jakarta", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            dt = datetime.datetime.fromisoformat(data["datetime"].replace("Z", "+00:00"))
            return dt.date()
    except Exception:
        pass
    return datetime.date.today()


# ------------------- MAIN -------------------
def show():
    cfg = load_config()
    st.title(f"📊 Laporan Laundry — {cfg['nama_toko']}")

    today = get_internet_date()
    df_order = read_sheet(SHEET_ORDER)
    df_pengeluaran = read_sheet(SHEET_PENGELUARAN)

    if df_order.empty and df_pengeluaran.empty:
        st.info("Belum ada data transaksi laundry.")
        return

    # ------------------- PARSE ORDER -------------------
    if not df_order.empty and "Tanggal Masuk" in df_order.columns:
        df_order["Tanggal Parsed"] = df_order["Tanggal Masuk"].str.split(" - ").str[0]
        df_order["Tanggal Parsed"] = pd.to_datetime(df_order["Tanggal Parsed"], dayfirst=True, errors="coerce").dt.date

    # ------------------- PARSE PENGELUARAN -------------------
    if not df_pengeluaran.empty and "Tanggal" in df_pengeluaran.columns:
        df_pengeluaran["Tanggal"] = pd.to_datetime(df_pengeluaran["Tanggal"], dayfirst=True, errors="coerce").dt.date

    # ------------------- FILTER -------------------
    st.sidebar.header("📅 Filter Data")
    mode = st.sidebar.radio("Mode Filter", ["Per Hari", "Per Bulan"], index=0)

    if mode == "Per Hari":
        tgl = st.sidebar.date_input("Tanggal", value=today)
        df_order_f = df_order[df_order["Tanggal Parsed"] == tgl] if not df_order.empty else pd.DataFrame()
        df_pengeluaran_f = df_pengeluaran[df_pengeluaran["Tanggal"] == tgl] if not df_pengeluaran.empty else pd.DataFrame()
    else:
        bulan_list = sorted(set(df_order["Tanggal Parsed"].dropna().map(lambda d: d.strftime("%Y-%m"))) if not df_order.empty else [])
        pilih_bulan = st.sidebar.selectbox("Pilih Bulan", ["Semua Bulan"] + bulan_list, index=0)
        if pilih_bulan == "Semua Bulan":
            df_order_f, df_pengeluaran_f = df_order.copy(), df_pengeluaran.copy()
        else:
            th, bln = map(int, pilih_bulan.split("-"))
            df_order_f = df_order[df_order["Tanggal Parsed"].apply(lambda d: pd.notna(d) and d.year == th and d.month == bln)]
            df_pengeluaran_f = df_pengeluaran[df_pengeluaran["Tanggal"].apply(lambda d: pd.notna(d) and d.year == th and d.month == bln)]

    # ------------------- HITUNG LABA -------------------
    total_cash = total_transfer = total_pengeluaran = 0
    if not df_order_f.empty:
        total_cash = df_order_f[df_order_f["Jenis Transaksi"].str.lower() == "cash"]["Total"].sum()
        total_transfer = df_order_f[df_order_f["Jenis Transaksi"].str.lower() == "transfer"]["Total"].sum()
    if not df_pengeluaran_f.empty:
        total_pengeluaran = df_pengeluaran_f["Nominal"].sum()

    total_bersih = total_cash + total_transfer - total_pengeluaran
    total_kg = df_order_f["Berat (Kg)"].sum() if not df_order_f.empty else 0

    # ------------------- METRIK -------------------
    st.markdown(f"""
    <style>
    .metric-container {{
        display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-start;
    }}
    .metric-card {{
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.1);
        padding: 10px 14px; border-radius: 8px;
        min-width: 160px; text-align: center;
        box-shadow: 0 1px 4px rgba(0,0,0,0.12);
    }}
    .metric-label {{ font-size: 0.8rem; opacity: 0.8; }}
    .metric-value {{ font-size: 1rem; font-weight: 600; margin-top: 6px; }}
    </style>

    <div class="metric-container">
        <div class="metric-card"><div class="metric-label">💵 Total Cash</div><div class="metric-value">{format_rp(total_cash)}</div></div>
        <div class="metric-card"><div class="metric-label">🏦 Total Transfer</div><div class="metric-value">{format_rp(total_transfer)}</div></div>
        <div class="metric-card"><div class="metric-label">🧺 Total Kg</div><div class="metric-value">{total_kg:.2f} Kg</div></div>
        <div class="metric-card"><div class="metric-label">💸 Pengeluaran</div><div class="metric-value" style="color:#ff6b6b;">- {format_rp(total_pengeluaran)}</div></div>
        <div class="metric-card"><div class="metric-label">📊 Total Bersih</div><div class="metric-value" style="color:#4ade80;">{format_rp(total_bersih)}</div></div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # ------------------- TABEL -------------------
    st.subheader("🧾 Data Transaksi Laundry")
    if not df_order_f.empty:
        st.dataframe(df_order_f[[
            "No Nota","Tanggal Masuk","Nama Pelanggan","Jenis Pakaian",
            "Jenis Layanan","Berat (Kg)","Harga per Kg","Total",
            "Parfum","Jenis Transaksi","Status"
        ]], use_container_width=True)
    else:
        st.info("Tidak ada transaksi laundry pada periode ini.")

    st.divider()
    st.subheader("💸 Data Pengeluaran")
    if not df_pengeluaran_f.empty:
        st.dataframe(df_pengeluaran_f[["Tanggal", "Keterangan", "Nominal", "Jenis Transaksi"]], use_container_width=True)
    else:
        st.info("Tidak ada data pengeluaran.")

    st.divider()
    if not df_order_f.empty:
        csv = df_order_f.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download Laporan Laundry (CSV)", csv, "laporan_laundry.csv", "text/csv")


# ------------------- MAIN -------------------
if __name__ == "__main__":
    show()
