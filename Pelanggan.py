# ========================== pelanggan.py (Laundry v4.2) ==========================
import streamlit as st
import pandas as pd
import datetime
import json
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import urllib.parse

# ------------------- PAGE CONFIG -------------------
st.set_page_config(page_title="Pelanggan — Status Laundry", page_icon="🧺", layout="wide")

# ------------------- CONFIG -------------------
CONFIG_FILE = "config.json"
SPREADSHEET_ID = "1v_3sXsGw9lNmGPSbIHytYzHzPTxa4yp4HhfS9tgXweA"
SHEET_ORDER = "Order"

# ------------------- AUTH GOOGLE -------------------
def authenticate_google():
    creds_dict = st.secrets["gcp_service_account"]
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(credentials)
    return client

def get_worksheet(sheet_name):
    client = authenticate_google()
    sh = client.open_by_key(SPREADSHEET_ID)
    return sh.worksheet(sheet_name)

# ------------------- READ SHEET (cached) -------------------
@st.cache_data(ttl=60)
def read_sheet_once(sheet_name):
    ws = get_worksheet(sheet_name)
    df = pd.DataFrame(ws.get_all_records())
    return df

def clear_sheet_cache_and_reload():
    try:
        read_sheet_once.clear()
    except Exception:
        pass
    return read_sheet_once(SHEET_ORDER)

def load_df():
    if "df_cache" not in st.session_state:
        try:
            st.session_state.df_cache = read_sheet_once(SHEET_ORDER)
        except Exception as e:
            st.warning(f"Gagal membaca sheet: {e}")
            st.session_state.df_cache = pd.DataFrame()
    return st.session_state.df_cache.copy()

def reload_df():
    try:
        st.session_state.df_cache = clear_sheet_cache_and_reload()
    except Exception as e:
        st.warning(f"Gagal reload sheet: {e}")
        st.session_state.df_cache = pd.DataFrame()

# ------------------- UPDATE SHEET -------------------
def update_sheet_row_by_nota(sheet_name, nota, updates: dict):
    try:
        ws = get_worksheet(sheet_name)
        cell = ws.find(str(nota))
        if not cell:
            raise ValueError(f"Tidak ditemukan nota {nota}")
        row = cell.row
        headers = ws.row_values(1)
        for k, v in updates.items():
            if k in headers:
                col = headers.index(k) + 1
                ws.update_cell(row, col, v)
        return True
    except Exception as e:
        st.error(f"Gagal update sheet {sheet_name} untuk nota {nota}: {e}")
        return False

# ------------------- UTIL -------------------
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {"nama_toko": "TR Laundry", "alamat": "Jl. Buluh Cina, Panam", "telepon": "087899913595"}

def get_waktu_jakarta():
    tz = datetime.timezone(datetime.timedelta(hours=7))
    return datetime.datetime.now(tz)

def format_rp(n):
    try:
        nnum = int(float(n))
        return f"Rp {nnum:,.0f}".replace(",", ".")
    except:
        return str(n)

# ------------------- WA KONFIRMASI -------------------
def kirim_wa_konfirmasi(nama, no_nota, no_hp, total, jenis_transaksi, nama_toko):
    msg = f"""Halo {nama},
Laundry anda dengan nomor Nota {no_nota} sudah selesai diproses dan siap untuk diambil. 🧺

Total Biaya: {total}
Pembayaran: {jenis_transaksi}

Terima Kasih,
{nama_toko}"""
    no_hp_clean = str(no_hp).replace("+","").replace(" ","").replace("-","")
    if no_hp_clean.startswith("0"):
        no_hp_clean = "62" + no_hp_clean[1:]
    elif not no_hp_clean.startswith("62"):
        no_hp_clean = "62" + no_hp_clean
    if no_hp_clean.isdigit() and len(no_hp_clean) >= 10:
        wa_link = f"https://wa.me/{no_hp_clean}?text={urllib.parse.quote(msg)}"
        st.markdown(f"[📲 Kirim Konfirmasi Ambil]({wa_link})", unsafe_allow_html=True)
        js = f"""
        <script>
        setTimeout(function(){{
            window.open("{wa_link}", "_blank");
        }}, 500);
        </script>
        """
        st.markdown(js, unsafe_allow_html=True)
    else:
        st.warning("⚠️ Nomor HP pelanggan tidak valid.")

# ------------------- STYLES -------------------
STYLE = """
<style>
.stat-card { padding:14px; border-radius:10px; color:#fff; text-align:center; font-weight:700; }
.card-orange{ background:#FFA500 } .card-blue{ background:#0A84FF } .card-green{ background:#34C759 } .card-red{ background:#FF3B30 }
.small-muted { color:#666; font-size:13px; }
.limit-note { font-size:13px; color:#666; margin-bottom:6px; }
</style>
"""
st.markdown(STYLE, unsafe_allow_html=True)

# ------------------- DATAFRAME PREP -------------------
def prepare_df_for_view(df):
    for col in ["Tanggal Masuk","No Nota","Nama Pelanggan","No HP","Jenis Pakaian","Jenis Layanan","Total","Status","Status Antrian"]:
        if col not in df.columns:
            df[col] = ""
    # isi Status Antrian default dari Status lama jika kosong
    df["Status Antrian"] = df["Status Antrian"].fillna("").astype(str).str.strip()
    mask_copy = (df["Status Antrian"] == "") & (df["Status"].astype(str).str.strip() != "")
    df.loc[mask_copy, "Status Antrian"] = df.loc[mask_copy, "Status"]
    df["Tanggal_parsed"] = pd.to_datetime(df["Tanggal Masuk"].astype(str).str[:10], errors="coerce", dayfirst=True)
    return df

# ------------------- RENDER CARD -------------------
def render_card_entry(row, cfg, active_status):
    no_nota = row.get("No Nota","")
    nama = row.get("Nama Pelanggan","")
    no_hp = row.get("No HP","")
    jenis_pakaian = row.get("Jenis Pakaian","")
    jenis_layanan = row.get("Jenis Layanan","")
    total = format_rp(row.get("Total",0))
    status_antrian = (row.get("Status Antrian") or "").strip()
    jenis_transaksi = row.get("Jenis Transaksi","Cash")

    header_label = f"🧾 {no_nota} — {nama} — {jenis_pakaian} ({status_antrian or 'Antrian'})"
    with st.expander(header_label, expanded=False):
        st.write(f"📅 **Tanggal Masuk:** {row.get('Tanggal Masuk','')}")
        st.write(f"👤 **Nama:** {nama}")
        st.write(f"📞 **No HP:** {no_hp}")
        st.write(f"🧺 **Layanan:** {jenis_layanan}")
        st.write(f"💰 **Total:** {total}")
        st.write(f"📌 **Status Antrian:** {status_antrian or 'Antrian'}")

        # ---------- ACTIONS ----------
        # Antrian → Siap Diambil
        if (status_antrian == "" or status_antrian.lower() == "antrian") and active_status=="Antrian":
            if st.button("✅ Siap Diambil (Simpan & Kirim WA)", key=f"ambil_{no_nota}"):
                updates = {
                    "Status Antrian": "Siap Diambil",
                    "Status": "Siap Diambil",
                    "Jenis Transaksi": jenis_transaksi
                }
                ok = update_sheet_row_by_nota(SHEET_ORDER, no_nota, updates)
                if ok:
                    read_sheet_once.clear()
                    reload_df()
                    kirim_wa_konfirmasi(nama, no_nota, no_hp, total, jenis_transaksi, cfg['nama_toko'])
                    st.success(f"Nota {no_nota} → Siap Diambil")

        # Siap Diambil → Selesai / Batal
        elif status_antrian.lower() == "siap diambil" and active_status=="Siap Diambil":
            c1,c2 = st.columns(2)
            with c1:
                if st.button("✔️ Selesai", key=f"selesai_{no_nota}"):
                    ok = update_sheet_row_by_nota(SHEET_ORDER, no_nota, {"Status Antrian":"Selesai","Status":"Selesai"})
                    if ok:
                        read_sheet_once.clear()
                        reload_df()
                        st.success(f"Nota {no_nota} → Selesai")
            with c2:
                if st.button("❌ Batal", key=f"batal_{no_nota}"):
                    ok = update_sheet_row_by_nota(SHEET_ORDER, no_nota, {"Status Antrian":"Batal","Status":"Batal"})
                    if ok:
                        read_sheet_once.clear()
                        reload_df()
                        st.warning(f"Nota {no_nota} → Batal")
        else:
            st.info(f"📌 Status Antrian: {status_antrian or 'Antrian'}")

# ------------------- APP -------------------
def show():
    cfg = load_config()
    st.title("📱 Pelanggan — Status Laundry & Kirim WA")

    # reload
    colr,colr2 = st.columns([1,4])
    with colr:
        if st.button("🔄 Reload Data"):
            read_sheet_once.clear()
            reload_df()
            st.rerun()

    df = load_df()
    df = prepare_df_for_view(df)

    # statistics
    total_antrian = len(df[(df["Status Antrian"]=="")|(df["Status Antrian"].str.lower()=="antrian")])
    total_siap = len(df[df["Status Antrian"].str.lower()=="siap diambil"])
    total_selesai = len(df[df["Status Antrian"].str.lower()=="selesai"])
    total_batal = len(df[df["Status Antrian"].str.lower()=="batal"])

    s1,s2,s3,s4 = st.columns([1.1,1.1,1.1,1.1], gap="large")
    s1.markdown(f'<div class="stat-card card-orange">🕒<br>Antrian<br><div style="font-size:18px">{total_antrian}</div></div>',unsafe_allow_html=True)
    s2.markdown(f'<div class="stat-card card-blue">📢<br>Siap Diambil<br><div style="font-size:18px">{total_siap}</div></div>',unsafe_allow_html=True)
    s3.markdown(f'<div class="stat-card card-green">✅<br>Selesai<br><div style="font-size:18px">{total_selesai}</div></div>',unsafe_allow_html=True)
    s4.markdown(f'<div class="stat-card card-red">❌<br>Batal<br><div style="font-size:18px">{total_batal}</div></div>',unsafe_allow_html=True)

    tab_antrian,tab_siap,tab_selesai,tab_batal = st.tabs(["🕒 Antrian","📢 Siap Diambil","✅ Selesai","❌ Batal"])

    # filter
    with st.expander("🔧 Filter & Cari"):
        today = get_waktu_jakarta().date()
        tipe_filter = st.selectbox("Filter Waktu", ["Semua","Per Hari","Per Bulan"], index=0)
        if tipe_filter=="Per Hari":
            tanggal_pilih = st.date_input("Pilih Tanggal", today)
        elif tipe_filter=="Per Bulan":
            tahun = st.number_input("Tahun", value=today.year, step=1)
            bulan = st.number_input("Bulan", value=today.month, min_value=1,max_value=12, step=1)
        q = st.text_input("Cari Nama / Nota")

    def apply_filters(df_in):
        df_out = df_in.copy()
        if tipe_filter=="Per Hari":
            df_out = df_out[df_out["Tanggal_parsed"].dt.date==tanggal_pilih]
        elif tipe_filter=="Per Bulan":
            df_out = df_out[(df_out["Tanggal_parsed"].dt.year==tahun)&(df_out["Tanggal_parsed"].dt.month==bulan)]
        if q and str(q).strip():
            ql = str(q).strip().lower()
            df_out = df_out[df_out["Nama Pelanggan"].astype(str).str.lower().str.contains(ql) | df_out["No Nota"].astype(str).str.lower().str.contains(ql)]
        return df_out

    def show_tab(df_tab, active_status):
        df_tab = apply_filters(df_tab)
        if len(df_tab)==0:
            st.info(f"Tidak ada data untuk status {active_status}")
            return
        per_page=25
        total=len(df_tab)
        pages=(total-1)//per_page+1
        page=st.number_input(f"Halaman ({active_status})", 1, pages, 1, key=f"page_{active_status}")
        start=(page-1)*per_page
        end=start+per_page
        for idx,row in df_tab.iloc[start:end].iterrows():
            render_card_entry(row, cfg, active_status)

    with tab_antrian:
        show_tab(df[(df["Status Antrian"]=="")|(df["Status Antrian"].str.lower()=="antrian")], "Antrian")
    with tab_siap:
        show_tab(df[df["Status Antrian"].str.lower()=="siap diambil"], "Siap Diambil")
    with tab_selesai:
        show_tab(df[df["Status Antrian"].str.lower()=="selesai"], "Selesai")
    with tab_batal:
        show_tab(df[df["Status Antrian"].str.lower()=="batal"], "Batal")

if __name__=="__main__":
    show()
