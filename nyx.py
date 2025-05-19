#!/usr/bin/env python3
"""
Nyx - Secure CLI Chat (Improved Version)
"""

import socket
import threading
import getpass
import sys
import select
from datetime import datetime
import colorama
from colorama import Fore, Back, Style

# Initialize colors
colorama.init()

# ========== CONSTANTS & BANNER ==========
BANNER = f"""{Fore.CYAN}
============================================================

 ██████   █████                       
░░██████ ░░███                        
 ░███░███ ░███  █████ ████ █████ █████
 ░███░░███░███ ░░███ ░███ ░░███ ░░███ 
 ░███ ░░██████  ░███ ░███  ░░░█████░  
 ░███  ░░█████  ░███ ░███   ███░░░███ 
 █████  ░░█████ ░░███████  █████ █████
░░░░░    ░░░░░   ░░░░░███ ░░░░░ ░░░░░ 
                 ███ ░███             
                ░░██████              
                 ░░░░░░     
                          
============================================================
Author : 
▖  ▖    ▄▖    
▛▖▞▌▛▘  ▙▌▌▌▀▌
▌▝ ▌▌   ▌ ▙▌█▌

Version : 1.0
============================================================            

 {Fore.YELLOW}Secure CLI Chat (Project Nyx){Style.RESET_ALL}
"""

DEFAULT_PORT = 5050
BUFFER_SIZE = 4096
MESSAGE_END = b"\x00"  # Null byte delimiter

# ========== SHARED FUNCTIONS ==========
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "127.0.0.1"
    return ip

def prompt_secure_input():
    username = input(f"{Fore.GREEN}Enter your username:{Style.RESET_ALL} ").strip()
    channel = input(f"{Fore.GREEN}Enter channel name:{Style.RESET_ALL} ").strip()
    password = getpass.getpass(f"{Fore.GREEN}Enter channel password:{Style.RESET_ALL} ")
    return username, channel, password

def print_header(text):
    print(f"\n{Fore.YELLOW}=== {text} ==={Style.RESET_ALL}")

def print_success(text):
    print(f"{Fore.GREEN}[+] {text}{Style.RESET_ALL}")

def print_error(text):
    print(f"{Fore.RED}[!] {text}{Style.RESET_ALL}")

# ========== SERVER CODE ==========
class Server:
    def __init__(self):
        self.clients = []
        self.channel_info = {}
        self.client_channels = {}
        self.client_usernames = {}

    def broadcast(self, message, source=None, channel=None):
        """Send message to all clients in the same channel"""
        if channel is None:
            return

        for client in self.clients:
            if client != source and self.client_channels.get(client) == channel:
                try:
                    client.send(message + MESSAGE_END)
                except:
                    self.remove_client(client)

    def remove_client(self, client):
        if client in self.clients:
            username = self.client_usernames.get(client, "Unknown")
            channel = self.client_channels.get(client)
            if channel:
                leave_msg = f"{Fore.MAGENTA}[System] {username} left the channel{Style.RESET_ALL}"
                self.broadcast(leave_msg.encode(), client, channel)
            self.clients.remove(client)
            if client in self.client_channels:
                del self.client_channels[client]
            if client in self.client_usernames:
                del self.client_usernames[client]
            client.close()

    def handle_client(self, conn, addr):
        try:
            data = conn.recv(BUFFER_SIZE).decode().strip()
            if not data:
                return

            username, channel, password = data.split("|")
            self.client_usernames[conn] = username

            # Verify or create channel
            if channel in self.channel_info:
                if self.channel_info[channel] != password:
                    conn.send(f"{Fore.RED}[!] Incorrect password{Style.RESET_ALL}".encode() + MESSAGE_END)
                    conn.close()
                    return
            else:
                self.channel_info[channel] = password

            welcome = f"{Fore.MAGENTA}[System] {username} joined channel '{channel}'{Style.RESET_ALL}"
            conn.send(f"{Fore.MAGENTA}[System] Welcome to channel '{channel}'{Style.RESET_ALL}".encode() + MESSAGE_END)
            self.broadcast(welcome.encode(), conn, channel)

            self.clients.append(conn)
            self.client_channels[conn] = channel
            print_success(f"{username} joined channel '{channel}' from {addr[0]}")
            
            while True:
                try:
                    data = conn.recv(BUFFER_SIZE)
                    if not data:
                        break
                    
                    message = data.split(MESSAGE_END)[0].decode()
                    if not message:
                        continue
                    
                    # Echo back to sender first
                    timestamp = datetime.now().strftime("%H:%M")
                    formatted_msg = f"{Fore.BLUE}[{timestamp}] {username}:{Style.RESET_ALL} {message}"
                    conn.send(formatted_msg.encode() + MESSAGE_END)
                    
                    # Broadcast to others
                    self.broadcast(formatted_msg.encode(), conn, channel)
                    
                    print(f"{Fore.CYAN}[{channel}] {username}:{Style.RESET_ALL} {message}")
                    
                except Exception as e:
                    print_error(f"Error with client {username}: {e}")
                    break
                    
        finally:
            self.remove_client(conn)

    def start(self, username, channel, password):
        ip = get_local_ip()
        print_header(f"HOST MODE - Channel '{channel}' as '{username}'")
        print(f"{Fore.CYAN}IP:{Style.RESET_ALL} {ip}")
        print(f"{Fore.CYAN}Port:{Style.RESET_ALL} {DEFAULT_PORT}")
        print(f"{Fore.CYAN}Password:{Style.RESET_ALL} {'*' * len(password)}")

        self.channel_info[channel] = password
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", DEFAULT_PORT))
        server.listen()
        print_success("Server started. Waiting for connections...")

        try:
            while True:
                conn, addr = server.accept()
                thread = threading.Thread(target=self.handle_client, args=(conn, addr))
                thread.daemon = True
                thread.start()
        except KeyboardInterrupt:
            print_error("Server shutting down...")
            for client in self.clients.copy():
                self.remove_client(client)
            server.close()

# ========== CLIENT CODE ==========
class Client:
    def __init__(self):
        self.running = True
        self.sock = None

    def clear_input_line(self):
        sys.stdout.write("\033[F\033[K")  # Move up and clear line

    def receive_messages(self):
        """Handle incoming messages in real-time"""
        buffer = b""
        while self.running:
            try:
                # Check if there's data to read
                ready = select.select([self.sock], [], [], 0.1)
                if ready[0]:
                    data = self.sock.recv(BUFFER_SIZE)
                    if not data:
                        print_error("Connection closed by server")
                        self.running = False
                        break
                    
                    buffer += data
                    
                    # Process complete messages
                    while MESSAGE_END in buffer:
                        msg, buffer = buffer.split(MESSAGE_END, 1)
                        if msg:
                            self.clear_input_line()
                            print(msg.decode())
                            sys.stdout.write("> ")
                            sys.stdout.flush()
                            
            except ConnectionResetError:
                print_error("Server connection was reset")
                self.running = False
                break
            except Exception as e:
                print_error(f"Error receiving message: {e}")
                self.running = False
                break

    def start(self, username, channel, password, host_ip):
        print_header(f"CLIENT MODE - Connecting to {host_ip}:{DEFAULT_PORT}")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((host_ip, DEFAULT_PORT))
            auth = f"{username}|{channel}|{password}"
            self.sock.send(auth.encode())

            # Start message receiver thread
            recv_thread = threading.Thread(target=self.receive_messages)
            recv_thread.daemon = True
            recv_thread.start()

            print_success(f"Connected to channel '{channel}' as '{username}'")
            print(f"\n{Fore.YELLOW}Type your messages and press Enter to send")
            print(f"Type /exit to disconnect{Style.RESET_ALL}\n")
            
            # Main input loop
            while self.running:
                try:
                    msg = input("> ")
                    if not msg.strip():
                        continue
                        
                    if msg.lower() in ["/exit", "/quit"]:
                        break
                        
                    self.sock.send(msg.encode() + MESSAGE_END)
                    
                except KeyboardInterrupt:
                    print("\n" + Fore.YELLOW + "[!] Closing connection..." + Style.RESET_ALL)
                    break
                except Exception as e:
                    print_error(f"Error: {e}")
                    break
                
        except Exception as e:
            print_error(f"Connection failed: {e}")
        finally:
            self.running = False
            if self.sock:
                self.sock.close()

# ========== MAIN FUNCTION ==========
def main():
    print(BANNER)
    print(f"{Fore.YELLOW}Choose mode:{Style.RESET_ALL}")
    print(f"{Fore.CYAN}[1]{Style.RESET_ALL} Host a channel")
    print(f"{Fore.CYAN}[2]{Style.RESET_ALL} Join a channel")
    
    while True:
        choice = input(f"{Fore.GREEN}Select (1/2):{Style.RESET_ALL} ").strip()
        if choice in ["1", "2"]:
            break
        print_error("Invalid option. Please enter 1 or 2.")
    
    username, channel, password = prompt_secure_input()
    
    if choice == "1":
        server = Server()
        server.start(username, channel, password)
    else:
        host_ip = input(f"{Fore.GREEN}Enter host IP address:{Style.RESET_ALL} ").strip()
        client = Client()
        client.start(username, channel, password, host_ip)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n" + Fore.YELLOW + "[!] Interrupted." + Style.RESET_ALL)
    except Exception as e:
        print_error(f"Fatal error: {e}")