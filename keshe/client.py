import socket
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import json
import base64
import os
from PIL import Image, ImageTk
from io import BytesIO
import math
import time
import pickle
import struct

CHUNK_SIZE = 1024 * 1024  # 1MB chunks for file transfer

class EmojiSelector(tk.Toplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.title("选择表情")
        self.callback = callback
        
        # 设置窗口大小和位置
        self.geometry("400x300")
        self.resizable(False, False)
        
        # 创建表情框架
        self.emoji_frame = ttk.Frame(self)
        self.emoji_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 加载表情图片
        self.load_emojis()
        
    def load_emojis(self):
        emoji_dir = "emojis"  # 表情包目录
        if not os.path.exists(emoji_dir):
            os.makedirs(emoji_dir)
            
        row = 0
        column = 0
        self.emoji_images = []  # 保持图片引用
        
        for file in os.listdir(emoji_dir):
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                try:
                    # 加载并调整图片大小
                    image = Image.open(os.path.join(emoji_dir, file))
                    image = image.resize((40, 40), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(image)
                    
                    # 创建按钮
                    btn = ttk.Button(self.emoji_frame, image=photo, 
                                   command=lambda f=file: self.select_emoji(f))
                    btn.grid(row=row, column=column, padx=5, pady=5)
                    
                    # 保存图片引用
                    self.emoji_images.append(photo)
                    
                    # 更新网格位置
                    column += 1
                    if column > 4:  # 每行5个表情
                        column = 0
                        row += 1
                except Exception as e:
                    print(f"加载表情失败: {file}, 错误: {str(e)}")
                    
    def select_emoji(self, emoji_file):
        self.callback(os.path.join("emojis", emoji_file))
        self.destroy()

class ChatClient:
    def __init__(self):
        self.setup_network()
        self.setup_gui()
        self.file_chunks = {}  # 用于存储文件传输的临时数据
        
    def setup_network(self):
        self.host = 'localhost'
        self.port = 5000
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
    def setup_gui(self):
        self.window = tk.Tk()
        self.window.title("聊天客户端")
        self.window.geometry("800x600")
        
        # 主分割面板
        self.paned = ttk.PanedWindow(self.window, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True)
        
        # 左侧面板（聊天区域）
        self.left_frame = ttk.Frame(self.paned)
        self.paned.add(self.left_frame, weight=3)
        
        # 聊天记录区域
        self.chat_area = scrolledtext.ScrolledText(self.left_frame)
        self.chat_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 消息输入区域
        self.input_frame = ttk.Frame(self.left_frame)
        self.input_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.message_entry = ttk.Entry(self.input_frame)
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.send_button = ttk.Button(self.input_frame, text="发送", command=self.send_message)
        self.send_button.pack(side=tk.LEFT, padx=5)
        
        self.file_button = ttk.Button(self.input_frame, text="发送文件", command=self.send_file_dialog)
        self.file_button.pack(side=tk.LEFT)
        
        self.emoji_button = ttk.Button(self.input_frame, text="发送表情", command=self.show_emoji_selector)
        self.emoji_button.pack(side=tk.LEFT, padx=5)
        
        # 右侧面板
        self.right_frame = ttk.Frame(self.paned)
        self.paned.add(self.right_frame, weight=1)
        
        # 在线用户列表
        self.users_frame = ttk.LabelFrame(self.right_frame, text="在线用户")
        self.users_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.users_list = tk.Listbox(self.users_frame)
        self.users_list.pack(fill=tk.BOTH, expand=True)
        
        # 服务器文件列表
        self.files_frame = ttk.LabelFrame(self.right_frame, text="服务器文件")
        self.files_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.files_list = tk.Listbox(self.files_frame)
        self.files_list.pack(fill=tk.BOTH, expand=True)
        
        self.download_button = ttk.Button(self.files_frame, text="下载选中文件", command=self.download_file)
        self.download_button.pack(pady=5)

    def show_emoji_selector(self):
        def on_emoji_selected(emoji_path):
            self.send_emoji(emoji_path)
            
        EmojiSelector(self.window, on_emoji_selected)
        
    def send_emoji(self, emoji_path):
        try:
            selected = self.users_list.curselection()
            to = self.users_list.get(selected[0]) if selected else "所有人"
            
            # 读取表情图片
            with open(emoji_path, 'rb') as f:
                image_data = f.read()
            
            # 创建表情数据包
            emoji_data = {
                'type': 'emoji',
                'to': to,
                'image': image_data
            }
            
            # 序列化数据
            data = pickle.dumps(emoji_data)
            
            # 发送消息类型标记（1字节）
            self.client_socket.send(b'\x01')
            # 发送数据长度（4字节）
            self.client_socket.send(struct.pack('>I', len(data)))
            # 发送序列化后的数据
            self.client_socket.send(data)
            
            # 显示发送的表情
            image = Image.open(emoji_path)
            image = image.resize((40, 40), Image.Resampling.LANCZOS)
            if to == "所有人":
                self.display_message("你: ")
            else:
                self.display_message(f"你对{to}说: ")
            self.display_image(image)
            
        except Exception as e:
            messagebox.showerror("发送错误", str(e))

    def send_file_dialog(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            selected = self.users_list.curselection()
            to = self.users_list.get(selected[0]) if selected else "所有人"
            
            try:
                with open(file_path, 'rb') as f:
                    file_data = f.read()
                    
                # 创建文件数据包
                file_package = {
                    'type': 'file',
                    'filename': os.path.basename(file_path),
                    'to': to,
                    'content': file_data
                }
                
                # 序列化数据
                data = pickle.dumps(file_package)
                
                # 发送消息类型标记（1字节）
                self.client_socket.send(b'\x02')  # 文件消息标记
                # 发送数据长度（4字节）
                self.client_socket.send(struct.pack('>I', len(data)))
                
                # 分块发送序列化数据
                chunk_size = 8192
                for i in range(0, len(data), chunk_size):
                    chunk = data[i:i + chunk_size]
                    self.client_socket.send(chunk)
                    
                self.display_message(f"文件 {os.path.basename(file_path)} 发送完成")
                
            except Exception as e:
                messagebox.showerror("文件发送错误", str(e))

    def receive_file_chunk(self, data):
        file_id = data.get('file_id')
        if file_id not in self.file_chunks:
            self.file_chunks[file_id] = {
                'filename': data['filename'],
                'chunks': {},
                'total_chunks': data['total_chunks']
            }
            
        self.file_chunks[file_id]['chunks'][data['chunk_number']] = data['content']
        
        # 检查是否收到所有块
        if len(self.file_chunks[file_id]['chunks']) == data['total_chunks']:
            self.save_complete_file(file_id)
            
    def save_complete_file(self, file_id):
        file_data = self.file_chunks[file_id]
        filename = file_data['filename']
        
        try:
            with open(filename, 'wb') as f:
                for i in range(file_data['total_chunks']):
                    chunk = base64.b64decode(file_data['chunks'][i])
                    f.write(chunk)
                    
            self.display_message(f"文件 {filename} 接收完成")
            del self.file_chunks[file_id]
        except Exception as e:
            self.display_message(f"文件保存失败: {str(e)}")

    def connect(self, username):
        try:
            self.client_socket.connect((self.host, self.port))
            self.username = username
            self.client_socket.send(username.encode())
            
            # 启动接收消息的线程
            receive_thread = threading.Thread(target=self.receive_messages)
            receive_thread.daemon = True
            receive_thread.start()
            
            return True
        except Exception as e:
            messagebox.showerror("连接错误", f"无法连接到服务器: {str(e)}")
            return False
            
    def send_message(self):
        message = self.message_entry.get().strip()
        if message:
            selected = self.users_list.curselection()
            to = self.users_list.get(selected[0]) if selected else 'all'
            
            data = {
                'type': 'message',
                'content': message,
                'to': to
            }
            
            try:
                self.client_socket.send(json.dumps(data).encode())
                self.message_entry.delete(0, tk.END)
                if to == 'all':
                    self.display_message(f"你: {message}")
                else:
                    self.display_message(f"你对{to}说: {message}")
            except:
                messagebox.showerror("发送错误", "消息发送失败")
                
    def display_image(self, image):
        # 在聊天区域显示图片
        photo = ImageTk.PhotoImage(image)
        self.chat_area.image_create(tk.END, image=photo)
        self.chat_area.image = photo  # 保持引用
        self.chat_area.insert(tk.END, "\n")
        self.chat_area.see(tk.END)
        
    def download_file(self):
        selected = self.files_list.curselection()
        if not selected:
            messagebox.showwarning("提示", "请先选择要下载的文件")
            return
            
        filename = self.files_list.get(selected[0])
        save_path = filedialog.asksaveasfilename(
            defaultextension=".*",
            initialfile=filename
        )
        
        if save_path:
            # 创建下载请求数据包
            download_request = {
                'type': 'file',
                'action': 'download',
                'filename': filename,
                'save_path': save_path
            }
            
            # 序列化数据
            data = pickle.dumps(download_request)
            
            # 发送消息类型标记（1字节）
            self.client_socket.send(b'\x02')  # 文件消息标记
            # 发送数据长度（4字节）
            self.client_socket.send(struct.pack('>I', len(data)))
            # 发送序列化后的数据
            self.client_socket.send(data)

    def display_message(self, message):
        self.chat_area.insert(tk.END, message + "\n")
        self.chat_area.see(tk.END)
        
    def update_users_list(self, users):
        self.users_list.delete(0, tk.END)
        self.users_list.insert(tk.END, "所有人")  # 添加群发选项
        for user in users:
            if user != self.username:  # 不显示自己
                self.users_list.insert(tk.END, user)

    def update_files_list(self, files):
        """更新服务器文件列表"""
        self.files_list.delete(0, tk.END)
        for file in files:
            self.files_list.insert(tk.END, file)

    def receive_messages(self):
        while True:
            try:
                # 读取消息类型标记（1字节）
                type_flag = self.client_socket.recv(1)
                if not type_flag:
                    break
                    
                if type_flag == b'\x01':  # 表情消息
                    # 读取数据长度（4字节）
                    length_data = self.client_socket.recv(4)
                    if not length_data:
                        break
                    msg_length = struct.unpack('>I', length_data)[0]
                    
                    # 读取序列化的表情数据
                    data = b''
                    while len(data) < msg_length:
                        chunk = self.client_socket.recv(min(msg_length - len(data), 8192))
                        if not chunk:
                            break
                        data += chunk
                        
                    if len(data) == msg_length:
                        emoji_data = pickle.loads(data)
                        # 显示接收到的表情
                        image = Image.open(BytesIO(emoji_data['image']))
                        image = image.resize((40, 40), Image.Resampling.LANCZOS)
                        if emoji_data.get('from'):
                            self.display_message(f"{emoji_data['from']}对你说: ")
                        self.display_image(image)
                        
                elif type_flag == b'\x02':  # 文件消息
                    # 读取数据长度（4字节）
                    length_data = self.client_socket.recv(4)
                    if not length_data:
                        break
                    msg_length = struct.unpack('>I', length_data)[0]
                    
                    # 读取序列化的文件数据
                    data = b''
                    while len(data) < msg_length:
                        chunk = self.client_socket.recv(min(msg_length - len(data), 8192))
                        if not chunk:
                            break
                        data += chunk
                        
                    if len(data) == msg_length:
                        file_data = pickle.loads(data)
                        # 保存接收到的文件
                        save_path = file_data.get('save_path', file_data['filename'])
                        with open(save_path, 'wb') as f:
                            f.write(file_data['content'])
                        if file_data.get('from'):
                            self.display_message(f"收到来自 {file_data['from']} 的文件: {file_data['filename']}")
                        else:
                            self.display_message(f"文件 {os.path.basename(save_path)} 下载完成")
                            
                else:  # 普通消息
                    # 读取剩余消息
                    message = self.client_socket.recv(8191)  # 8192 - 1
                    if not message:
                        break
                        
                    try:
                        data = json.loads((type_flag + message).decode())
                        if isinstance(data, dict):
                            if data['type'] == 'private_message':
                                self.display_message(f"{data['from']}对你说: {data['content']}")
                            elif data['type'] == 'users_list':
                                self.update_users_list(data['users'])
                            elif data['type'] == 'files_list':
                                self.update_files_list(data['files'])
                            elif data['type'] == 'server_message':
                                self.display_message(f"SERVER: {data['content']}")
                                # 检查是否被强制下线
                                if data['content'] == '您已被服务器强制下线':
                                    self.client_socket.close()
                                    self.window.after(0, self.handle_force_logout)
                                    break
                        else:
                            self.display_message((type_flag + message).decode())
                    except json.JSONDecodeError:
                        self.display_message((type_flag + message).decode())
                    
            except Exception as e:
                print(f"接收消息错误: {str(e)}")
                break
                
        if self.client_socket:
            self.client_socket.close()
            self.window.after(0, self.handle_disconnect)

    def handle_force_logout(self):
        """处理强制下线"""
        messagebox.showwarning("强制下线", "您已被服务器强制下线")
        self.window.quit()
        
    def handle_disconnect(self):
        """处理连接断开"""
        messagebox.showwarning("连接断开", "与服务器的连接已断开")
        self.window.quit()

    def start(self):
        # 登录对话框
        login = tk.Toplevel(self.window)
        login.title("登录")
        login.geometry("300x150")
        
        ttk.Label(login, text="用户名:").pack(pady=20)
        username_entry = ttk.Entry(login)
        username_entry.pack()
        
        def do_login():
            username = username_entry.get().strip()
            if username:
                if self.connect(username):
                    login.destroy()
                    self.window.deiconify()  # 显示主窗口
            else:
                messagebox.showwarning("提示", "请输入用户名")
                
        ttk.Button(login, text="登录", command=do_login).pack(pady=20)
        
        self.window.withdraw()  # 隐藏主窗口
        self.window.mainloop()

if __name__ == "__main__":
    client = ChatClient()
    client.start() 