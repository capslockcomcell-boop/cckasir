import streamlit as st
import json
import os

CONFIG_FILE = "config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {
        "nama_toko": "TR Laundry",
        "alamat": "Jl. Buluh Cina, Panam",
        "telepon": "0851-7217-4759"
    }

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=4)

def show():
    st.title("⚙️ Pengaturan Toko")

    cfg = load_config()
    nama_toko = st.text_input("Nama Toko", cfg["nama_toko"])
    alamat = st.text_area("Alamat", cfg["alamat"])
    telepon = st.text_input("Nomor HP / WhatsApp", cfg["telepon"])

    if st.button("💾 Simpan Pengaturan"):
        new_cfg = {"nama_toko": nama_toko, "alamat": alamat, "telepon": telepon}
        save_config(new_cfg)
        st.success("Pengaturan disimpan.")
